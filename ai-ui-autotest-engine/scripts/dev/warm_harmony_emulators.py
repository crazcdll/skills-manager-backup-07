#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鸿蒙云模拟器「预热池」—— 批量把美团可测性 HAP 预置到设备侧缓存，用完即释放。

【要解决的问题】
鸿蒙云模拟器（Conan，`cloud-emulator` + `harmony`）首次安装可测性 debug HAP 需要
约 1.4G 的 host→device 传输，第一位占用某台设备的同学要为此等很久。而设备侧缓存
（`HarmonyOps.DEVICE_APK_CACHE_DIR`）在 Conan **归还占用后依然保留**——实例只被
释放占用、并不销毁。于是"提前把一批设备喂饱缓存"，后续所有人占用到这些设备时
安装链路直接 `bm install -p <设备侧路径>`，省掉这次重传。

【本脚本做什么】
对 N 台鸿蒙云模拟器**逐台**执行：
    占用（conan-cli occupy，排除台账 / 本次已尝试序列号）
      → 清理设备侧遗留产物（文件 + 目录，保留我们的缓存目录）
      → 流式下发 HAP 到设备侧缓存（实时打印 百分比 / 已传 / 速率 / 剩余）
      → 校验缓存落盘（**只注入缓存、不做真实安装**）
      → 归还（conan-cli release，仅释放占用）
      → 同步到平台 device_registry（设备管理页可见，并进入后续「鸿蒙候选」）

【为什么逐台（不做并发）】
· 已实测：单台 ~3MB/s；4 台并发时各 ~1MB/s、**聚合仍 ~3.2MB/s**——瓶颈是本机/网关的
  共享上行，带宽总量固定，并发只是把管道切成 N 份，**总时长不变**（20 台 ≈ 2.2h 是带宽
  下限，与并发无关），反而把单台占用拉长、逼近 Conan 占用超时。
· 故采用逐台串行：占用时间短、可预测、失败隔离。

【为什么放在 scripts/dev/ 而不是做成 Skill 子命令】
这是**运维/预热**动作，不属于任何测试流程：它不需要 workspace / flow-context，
也不改变 Skill 的公共命令面。故只复用 Skill 的 Python 模块（制品缓存 /
设备清理 / 平台登记接口）与 conan-cli，生产代码零改动。

【为什么需要台账 / --black-numbers】
同一台归还后可能被再次分配；靠 `conan-cli occupy --black-numbers <序列号...>`
把「台账里已预热」+「本次已尝试（含失败）」的序列号整批排除，Conan 只在剩余设备里
分配。台账落在 `.device-pool/warm-ledger.json`（mis 级、跨 workspace 共享），
重复执行不会重复预热同一台。

用法：
    python3 scripts/dev/warm_harmony_emulators.py                  # 预热 20 台（默认）
    python3 scripts/dev/warm_harmony_emulators.py --count 10
    python3 scripts/dev/warm_harmony_emulators.py --dry-run           # 只看计划、不占用
    python3 scripts/dev/warm_harmony_emulators.py --no-clean          # 不清理设备侧遗留产物
    python3 scripts/dev/warm_harmony_emulators.py --no-clean-dirs     # 只清文件、保留遗留目录
    python3 scripts/dev/warm_harmony_emulators.py --keep              # 结束后不释放（谨慎）
    python3 scripts/dev/warm_harmony_emulators.py --reset-ledger      # 清空台账后重来

退出码：0 全部成功（达到 --count）/ 1 存在失败（设备不可达、缓存下发失败）/
       2 参数或配置错误 / 3 候选耗尽提前停止（非故障：当前空闲设备已全部预热）。
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time

# 源树零字节码：本文件是进程入口，开关必须在引擎包导入之前生效。
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import artifact_cache  # noqa: E402
from shared.case_utils import resolve_mis  # noqa: E402
from shared.context import create_app_descriptor  # noqa: E402
from shared.json_utils import read_json, write_json_atomic  # noqa: E402
from shared.paths import DEVICE_POOL_DIR, get_active_run, get_active_task  # noqa: E402
from devices.base import get_platform_module  # noqa: E402
from devices.harmony.hdc import ensure_hdc  # noqa: E402
from devices.toolchain.app_installer import load_apk_config  # noqa: E402
from platform.sandbox_api import api_post  # noqa: E402

# Conan 单人占用上限（`conan-cli device occupy -n` 超过即失败），并发数不得超过它。
CONAN_MAX_OCCUPY_PER_BATCH = 10
DEFAULT_PLATFORM = "harmony"
DEFAULT_APP = "meituan"
_LEDGER_PATH = os.path.join(DEVICE_POOL_DIR, "warm-ledger.json")
_OCCUPY_TIMEOUT = 180
_RELEASE_TIMEOUT = 60
_PLATFORM_TIMEOUT = 8
_SEND_TIMEOUT = 2400  # 1.3G 慢链路兜底上限（40 分钟）


# ═══════════════════════════════════════════════════════════════════
# 预热台账（.device-pool/warm-ledger.json）
# ═══════════════════════════════════════════════════════════════════

def load_ledger() -> dict:
    """读台账 {serial: {platform, app, hap, warmed_at}}，无文件返回空 dict。"""
    data = read_json(_LEDGER_PATH, default={}) or {}
    warmed = data.get("warmed")
    return warmed if isinstance(warmed, dict) else {}


def save_ledger(warmed: dict) -> None:
    os.makedirs(DEVICE_POOL_DIR, exist_ok=True)
    write_json_atomic(_LEDGER_PATH, {
        "version": 1,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "warmed": dict(warmed or {}),
    })


# ═══════════════════════════════════════════════════════════════════
# conan-cli（占用 / 释放）—— 直接子进程调用
# ═══════════════════════════════════════════════════════════════════

def _conan(args: list, timeout: int) -> dict:
    """执行 `conan-cli <args...> --output json`，解析出 JSON 对象。

    conan-cli 会先打印进度行再输出 JSON，故取第一个 `{` 到最后一个 `}` 之间的内容。
    """
    cmd = ["conan-cli", *[str(a) for a in args], "--output", "json"]
    print(f"[warm] $ {' '.join(cmd)}", flush=True)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError("未找到 conan-cli，请先安装："
                           "npm install -g @ee/conan-cli --registry=http://r.npm.sankuai.com")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"conan-cli 超时（{timeout}s）: {' '.join(cmd)}")
    text = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
    if r.returncode != 0:
        raise RuntimeError(f"conan-cli 失败（exit={r.returncode}）: {text.strip()[:300]}")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise RuntimeError(f"conan-cli 未返回 JSON: {text.strip()[:300]}")
    return json.loads(text[start:end + 1])


def occupy(count: int, platform: str, business_line: str, black_numbers: list) -> list:
    """占用 count 台模拟器，排除 black_numbers 里的序列号。返回标准化设备列表。"""
    args = ["device", "occupy", "-p", platform, "-t", "emulator",
            "-n", count, "-b", business_line]
    if black_numbers:
        args += ["--black-numbers", ",".join(black_numbers)]
    data = _conan(args, timeout=_OCCUPY_TIMEOUT)
    devices = []
    for d in (data.get("devices") or []):
        serial = d.get("serialNumber")
        if serial:
            devices.append({
                "serial": serial,
                "remote": d.get("remoteConnectAddress", ""),
                "occupationId": d.get("occupationId"),
            })
    return devices


def release(serials: list) -> bool:
    """归还这些设备（仅释放占用，不销毁实例）。"""
    serials = [str(s).strip() for s in (serials or []) if str(s).strip()]
    if not serials:
        return True
    try:
        _conan(["device", "release", *serials], timeout=_RELEASE_TIMEOUT)
        return True
    except Exception as e:  # noqa: BLE001 —— 释放失败只告警，不阻断（人工可再释放）
        print(f"[warm] ⚠️ 归还失败（请人工确认）: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════
# 平台登记（device_registry）—— 复用 Skill 的 yooz 代理接口
# ═══════════════════════════════════════════════════════════════════

def platform_record_occupy(serial: str, remote: str, action: str) -> None:
    """best-effort 登记一次占用（写平台设备登记表）。失败只告警，不影响预热。

    `owner_mis` 记**实际占用人 mis**（`resolve_mis()`）——云模拟器虽是团队共享池，
    但平台要展示“占用人”，故按实际操作人记录。
    """
    if not serial:
        return
    try:
        api_post("/node/api/data/monitor/device/occupy", {
            "device_id": serial,
            "owner_mis": resolve_mis(),
            "device_type": "cloud-emulator",
            "platform": DEFAULT_PLATFORM,
            "app": DEFAULT_APP,
            "platform_state": "running",
            "connect_address": remote,
            "view_url": "",
            "owner_run": get_active_run(),
            "owner_task": get_active_task(),
            "action": action,
        }, timeout=_PLATFORM_TIMEOUT)
    except Exception as e:  # noqa: BLE001 —— 登记失败不影响预热
        print(f"[warm] ⚠️ 平台占用登记失败（忽略）: {e}")


def platform_record_release(serial: str) -> None:
    """best-effort 登记一次归还（把设备行显示为「空闲」）。失败只告警。"""
    if not serial:
        return
    try:
        api_post("/node/api/data/monitor/device/release", {
            "device_id": serial,
            "owner_run": get_active_run(),
        }, timeout=_PLATFORM_TIMEOUT)
    except Exception as e:  # noqa: BLE001 —— 登记失败不影响预热
        print(f"[warm] ⚠️ 平台归还登记失败（忽略）: {e}")


# 当前占用中的序列号（供信号处理时归还）；进程级、单线程读写（本脚本已改回逐台串行）
_HELD = set()


def _occupied_serials() -> set:
    """查 Conan 当前实际占用中的序列号（用于平台状态对账）。查不到返回空集。"""
    try:
        data = _conan(["device", "status"], timeout=_OCCUPY_TIMEOUT)
    except Exception as e:  # noqa: BLE001 —— 查不到就不对账，避免误清
        print(f"[warm] ⚠️ 查询 Conan 占用失败（跳过对账）: {e}")
        return set()
    return {d.get("serialNumber") for d in (data.get("devices") or []) if d.get("serialNumber")}


def reconcile_platform_state(warmed: dict) -> None:
    """把「台账里已预热、但当前并未被占用」的设备在平台上补记 release，清掉残留的「使用中」。

    平台的行态由**最后一条 occupy/release 事件**派生（页面按 `last_action == 'release'`
    判空闲）：被 kill 的 run、或人工直接 `conan-cli device release`，都不会写 release 事件，
    行会永久停在「使用中」。这里按 Conan 的**真实占用**对账：不在占用列表里的台账设备，
    补一条 release 使其回到空闲（被占用中的设备自动跳过，不会误清正在用的）。
    """
    occupied = _occupied_serials()
    stale = sorted(s for s in warmed if s not in occupied)
    if not stale:
        return
    print(f"[warm] 平台状态对账：{len(stale)} 台已预热但未占用，补记 release ...", flush=True)
    for s in stale:
        platform_record_release(s)


# ═══════════════════════════════════════════════════════════════════
# 传输进度：轮询设备侧文件大小
# ═══════════════════════════════════════════════════════════════════

def _tag_of(serial: str) -> str:
    """并发日志前缀用的短标签（如 127.0.0.1:10066 → 10066）。"""
    return str(serial).rsplit(":", 1)[-1]


def _hdc_base(serial: str, remote: str) -> list:
    """拼装 hdc 命令前缀：`hdc [-s <remote>] -t <serial>`（与 Hdc 句柄同口径）。"""
    bin_path = None
    try:
        found = ensure_hdc(install=False)
        if found:
            bin_path = found[0]
    except Exception:  # noqa: BLE001 —— 找不到就走 PATH 里的 hdc
        bin_path = None
    cmd = [bin_path or "hdc"]
    if remote:
        cmd += ["-s", remote]
    cmd += ["-t", serial]
    return cmd


def _fmt_dur(sec: float) -> str:
    sec = int(max(0, sec))
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def _device_file_size(ops, device_path: str):
    """读设备侧文件大小（字节）；不可读返回 None。"""
    try:
        out = (ops.shell("stat", "-c", "%s", device_path).stdout or "").strip()
        return int(out) if out.isdigit() else None
    except Exception:  # noqa: BLE001
        return None


def _fmt_bar(pct: int) -> str:
    n = max(0, min(20, int(pct / 5)))
    return "█" * n + "░" * (20 - n)


def _emit_progress(tag: str, done: int, total: int, start: float) -> None:
    """打印一行进度：百分比 / 已传 / 平均速率 / 预计剩余。

    ETA 用**开工至今的平均速率**而非瞬时速率——瞬时值在 2s 采样窗里抖动极大
    （云模拟器链路带宽不稳），平均速率单调收敛，"还剩多少"才可读。
    """
    done = max(0, min(done, total))
    done_mb = done / 1024 / 1024
    total_mb = total / 1024 / 1024
    pct = min(100, int(done * 100 / total)) if total else 0
    avg_speed = done / max(time.time() - start, 0.001)
    eta = (total - done) / avg_speed if avg_speed > 0 else 0
    print(f"[warm:{tag}]   ↓ [{_fmt_bar(pct)}] {pct:3d}%  {done_mb:5.0f}/{total_mb:.0f}MB  "
          f"{avg_speed / 1024 / 1024:5.1f}MB/s  剩余约 {_fmt_dur(eta)}", flush=True)


def send_with_progress(ops, serial: str, remote: str, local_path: str,
                       remote_path: str, total_bytes: int, timeout: int) -> None:
    """下发 HAP 到设备侧缓存，并**轮询设备侧文件大小**实时打印进度。

    为什么不解析 hdc 自己的输出：hdc 在传输期间不输出任何进度（stdout 一直阻塞，
    连 `\\r` 刷新都没有）。改为每 2s 用一次独立 hdc 连接 `stat` 设备侧文件，按已落盘
    字节数计算百分比 / 平均速率 / 预计剩余——这才是真实可用的进度来源。
    """
    tag = _tag_of(serial)
    cmd = _hdc_base(serial, remote) + ["file", "send", local_path, remote_path]
    total_mb = total_bytes / 1024 / 1024
    print(f"[warm:{tag}]   ↓ 下发 {os.path.basename(local_path)} → {remote_path}（{total_mb:.0f}MB）",
          flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    start = time.time()
    last_emit = 0.0
    try:
        while proc.poll() is None:
            now = time.time()
            if now - start > timeout:
                proc.kill()
                raise RuntimeError(f"hdc file send 超时（{timeout}s）")
            if now - last_emit >= 2.0:
                done = _device_file_size(ops, remote_path) or 0
                if done <= 0:
                    print(f"[warm:{tag}]   ↓ 传输中 ... 已耗时 {_fmt_dur(now - start)}", flush=True)
                else:
                    _emit_progress(tag, done, total_bytes, start)
                last_emit = now
            time.sleep(0.5)
    finally:
        if proc.poll() is None:
            proc.kill()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"hdc file send 退出码 {rc}")
    _emit_progress(tag, total_bytes, total_bytes, start)


# ═══════════════════════════════════════════════════════════════════
# 单台预热：清理遗留产物 → 落设备侧缓存 → 校验大小
# ═══════════════════════════════════════════════════════════════════

def _clean_device(ops, tag: str, clean_dirs: bool = True) -> None:
    """清理设备临时目录里历次占用遗留的产物（保留本 Skill 的设备侧安装包缓存）。

    两段：
      · **文件**：复用 Skill 现成能力 `clean_device_temp_artifacts`——删 `/data/local/tmp`
        下白名单模式的可再生产物（hap/apk/hsp/part/log/png/jpg/json…，非递归）；
      · **目录**（clean_dirs=True）：删 `/data/local/tmp` 下**除白名单外的所有子目录**
        （debugserver/kingkongDir/hilog_tmp_* 等）。
    两段都跳过 `device_temp_keep_paths`（我们的 HAP 缓存目录）。

    ⚠️ 目录段是**激进清理**：云模拟器实例归还后仍保留，历次遗留会累积；这里按
    "只留自己的缓存目录、其余全清"处理（用 `--no-clean-dirs` 可只清文件、保留目录）。
    """
    try:
        res = ops.clean_device_temp_artifacts()
        deleted = res.get("deleted") or []
        if deleted:
            mb = (res.get("bytes") or 0) / 1024 / 1024
            print(f"[warm:{tag}]   🧹 清理遗留文件 {len(deleted)} 个，释放约 {mb:.0f}MB", flush=True)
        else:
            print(f"[warm:{tag}]   🧹 无遗留文件", flush=True)
    except Exception as e:  # noqa: BLE001 —— 清理失败不影响预热
        print(f"[warm:{tag}]   ⚠️ 清理遗留文件失败（忽略）: {e}", flush=True)

    if not clean_dirs:
        return
    try:
        keep = tuple(k.rstrip("/") for k in ops.device_temp_keep_paths)
        out = ops.shell("find", "/data/local/tmp", "-maxdepth", "1", "-mindepth", "1",
                        "-type", "d").stdout or ""
        base = "/data/local/tmp/"
        removed = []
        for line in out.splitlines():
            d = line.strip()
            if not d.startswith(base):
                continue
            if any(d == k or d.startswith(k + "/") for k in keep):
                continue
            if ops.shell("rm", "-rf", d).returncode == 0:
                removed.append(os.path.basename(d))
        if removed:
            print(f"[warm:{tag}]   🧽 清理遗留目录 {len(removed)} 个: {', '.join(removed)}", flush=True)
        else:
            print(f"[warm:{tag}]   🧽 无遗留目录", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[warm:{tag}]   ⚠️ 清理遗留目录失败（忽略）: {e}", flush=True)


def warm_one(serial: str, remote: str, app_desc,
             hap_path: str, hap_size: int, clean: bool = True,
             clean_dirs: bool = True) -> dict:
    """对一台设备：清理无用缓存 → 把 HAP 落到设备侧缓存（带进度）→ 校验大小。

    **只注入缓存、不做真实安装**：预热的目的只是让后续占用方免去 1.4G 重传；
    安装交给真正要用 App 的占用方（`install_app` 届时命中设备侧缓存、只做 bm install）。
    """
    tag = _tag_of(serial)
    ops_cls = get_platform_module(DEFAULT_PLATFORM).PlatformOpsClass
    ops = ops_cls(serial, app_desc, remote_address=remote or None)

    if not ops.device_alive():
        return {"ok": False, "cache_ok": False, "error": "设备不可达（hdc 连接失败）"}

    if clean:
        _clean_device(ops, tag, clean_dirs)

    remote_path = f"{ops.DEVICE_APK_CACHE_DIR}/{os.path.basename(hap_path)}"
    ops.shell("mkdir", "-p", ops.DEVICE_APK_CACHE_DIR)
    dev_size = _device_file_size(ops, remote_path)

    if dev_size == hap_size:
        print(f"[warm:{tag}]   ✅ 命中设备侧缓存（{dev_size // 1024 // 1024}MB），跳过传输", flush=True)
    else:
        if dev_size is not None:
            print(f"[warm:{tag}]   ℹ️ 设备侧缓存不完整（{dev_size} != {hap_size}），重新下发", flush=True)
        try:
            send_with_progress(ops, serial, remote, hap_path, remote_path, hap_size, _SEND_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "cache_ok": False, "error": f"HAP 下发失败: {e}"}

    # 只注入缓存：以"设备侧文件大小 == 本地 L1 大小"为准，不触发真实安装
    final_size = _device_file_size(ops, remote_path)
    cache_ok = final_size == hap_size
    return {
        "ok": cache_ok,
        "cache_ok": cache_ok,
        "cache_bytes": final_size,
        "error": None if cache_ok else f"设备侧缓存校验失败（{final_size} != {hap_size}）",
    }


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="鸿蒙云模拟器预热池：分批并发把美团可测性 HAP 预置到设备侧缓存。")
    p.add_argument("--count", type=int, default=20, help="目标预热设备数（默认 20）")
    p.add_argument("--platform", default=DEFAULT_PLATFORM,
                   help="平台（当前仅支持 harmony）")
    p.add_argument("--app", default=DEFAULT_APP, help="目标 App（默认 meituan）")
    p.add_argument("--mis", default="",
                   help="[已废弃] 云模拟器无归属，登记恒记 public；保留仅为兼容旧命令")
    p.add_argument("--business-line", default=os.environ.get("AI_UITEST_CONAN_BUSINESS_LINE", "193"),
                   help="Conan 业务线 ID（默认 193）")
    p.add_argument("--no-clean", dest="clean", action="store_false",
                   help="不清理设备侧遗留产物（默认会清理）")
    p.add_argument("--no-clean-dirs", dest="clean_dirs", action="store_false",
                   help="只清文件、保留 /data/local/tmp 下的遗留目录")
    p.add_argument("--dry-run", action="store_true", help="只打印计划，不占用/不预热")
    p.add_argument("--keep", action="store_true", help="结束后不归还占用（谨慎使用）")
    p.add_argument("--reset-ledger", action="store_true", help="先清空预热台账再执行")
    return p.parse_args()


def main() -> int:
    # 后台/重定向运行时 stdout 默认块缓冲，进度会"憋"到进程结束才可见；
    # 切行缓冲，让 tail 日志能实时看到每台设备的进展。
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:  # noqa: BLE001 —— 不支持时退化为默认缓冲
        pass

    args = _parse_args()

    if args.platform != DEFAULT_PLATFORM:
        print(f"[warm] ❌ 目前仅支持 platform={DEFAULT_PLATFORM}（收到 {args.platform}）")
        return 2
    if args.count <= 0:
        print("[warm] ❌ --count 必须为正整数")
        return 2

    # 被 kill（Ctrl-C / SIGTERM）时也要归还占用并补记平台 release——否则平台行会停在
    # 「使用中」（本脚本此前的多轮 kill 就留下了这种残留）。
    def _handle_signal(signum, _frame):
        print(f"\n[warm] 收到信号 {signum}；归还占用并退出 ...", flush=True)
        held = sorted(_HELD)
        if held and not args.keep and release(held):
            for s in held:
                platform_record_release(s)
        sys.exit(130)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    app_desc = create_app_descriptor(args.app, platform=args.platform, form="emulator")
    apk_cfg = load_apk_config(platform=args.platform, form="emulator")
    hap_url = apk_cfg.get("testability_apk_url")
    if not hap_url:
        print(f"[warm] ❌ apk_sources.json 缺少 {args.platform}/emulator 的 testability_apk_url")
        return 2

    if args.reset_ledger:
        save_ledger({})
        print("[warm] 台账已清空")

    warmed = load_ledger()
    print(f"[warm] 目标 {args.count} 台；台账已有 {len(warmed)} 台；逐台串行；包 "
          f"{app_desc.package_name}；HAP {os.path.basename(hap_url)}")
    if args.dry_run:
        print("[warm] (dry-run) 计划：逐台占用 → 清理 → 下发 → 释放；不实际执行")
        return 0

    # 平台状态对账：清掉历史残留的「使用中」
    # （被 kill 的 run / 人工 release 都不会补 release 事件，会留下永久占用态）
    reconcile_platform_state(warmed)

    # L1 制品路径/大小在主线程先解析一次（可能触发一次下载），避免多线程竞争
    hap_path = _hap_local_path(hap_url, app_desc)
    hap_size = _hap_local_size(hap_url, app_desc)

    warmed_ok, failed = [], []
    attempted = set()
    done = 0
    stopped_reason = None   # 非 None 表示未达 --count 就提前停止（exit 3）

    while done < args.count:
        # 台账 + 本次已尝试（含失败）一并排除，避免同一台被反复分配/重试
        blacklist = sorted(set(warmed) | attempted)
        try:
            devices = occupy(1, args.platform, args.business_line, blacklist)
        except Exception as e:  # noqa: BLE001 —— 占用失败（含资源耗尽）即停止
            stopped_reason = f"占用失败：{e}"
            print(f"[warm] ⛔ 占用失败，停止：{e}")
            break
        if not devices:
            stopped_reason = "占用返回 0 台（候选耗尽 / 资源不足）"
            print("[warm] ⛔ 占用返回 0 台（候选耗尽 / 资源不足），停止")
            break

        d = devices[0]
        serial, remote = d["serial"], d.get("remote", "")
        attempted.add(serial)
        _HELD.add(serial)
        print(f"\n[warm] ══════ 处理 {serial} @ {remote}（已完成 {done}/{args.count}）══════",
              flush=True)
        t0 = time.time()
        try:
            res = warm_one(serial, remote, app_desc, hap_path, hap_size,
                           clean=args.clean, clean_dirs=args.clean_dirs)
        except Exception as e:  # noqa: BLE001 —— 未捕获异常也要记账，不能吞
            res = {"ok": False, "error": f"未捕获异常: {e}"}

        if res.get("ok"):
            warmed[serial] = {
                "platform": args.platform,
                "app": args.app,
                "hap": os.path.basename(hap_url),
                "warmed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "cache_bytes": res.get("cache_bytes"),
            }
            # 每台成功即落台账：中途失败/中断也不会丢掉已预热的记录
            save_ledger(warmed)
            warmed_ok.append({"serial": serial, "remote": remote})
            done += 1
            print(f"[warm] ✅ {serial} 缓存注入完成（耗时 {_fmt_dur(time.time() - t0)}，"
                  f"进度 {done}/{args.count}）", flush=True)
            # 只登记**确有缓存**的设备到平台，使其进入后续「鸿蒙候选」
            platform_record_occupy(serial, remote, action="warm")
        else:
            failed.append({"serial": serial, "error": res.get("error")})
            print(f"[warm] ❌ {serial} 预热失败（耗时 {_fmt_dur(time.time() - t0)}）："
                  f"{res.get('error')}", flush=True)

        if args.keep:
            print(f"[warm] --keep：保留占用（{serial}）")
        else:
            if release([serial]):
                platform_record_release(serial)
                _HELD.discard(serial)
                print(f"[warm] 已归还占用（{serial}）", flush=True)
            else:
                print("[warm] ⚠️ 归还未确认，请用 `conan-cli device status` 复核")

    # ── 汇总 ──
    print("\n" + "=" * 60)
    print(f"[warm] 完成：本次新增 {done} 台，失败 {len(failed)} 台，台账累计 {len(warmed)} 台")
    if stopped_reason:
        print(f"[warm] ⚠️ 提前停止（未达 --count {args.count}）：{stopped_reason}")
        print("[warm]    通常意味着「当前空闲设备已全部预热」——等设备释放后再跑即可继续")
    print(f"[warm] 台账：{_LEDGER_PATH}")
    if failed:
        for f in failed:
            print(f"[warm]   ❌ {f['serial']}: {f['error']}")
    print("=" * 60)
    if failed:
        return 1
    if stopped_reason:
        return 3   # 3 = 候选耗尽提前停止（非故障）
    return 0


# 制品（L1）路径/大小缓存：一次解析多次复用，避免每台都重新 resolve
_ARTIFACT_CACHE = {}


def _hap_local_path(hap_url: str, app_desc) -> str:
    key = ("path", hap_url)
    if key not in _ARTIFACT_CACHE:
        scope = artifact_cache.scope_of(app_desc)
        _ARTIFACT_CACHE[key] = artifact_cache.resolve(hap_url, scope, label=scope)
    return _ARTIFACT_CACHE[key]


def _hap_local_size(hap_url: str, app_desc) -> int:
    return os.path.getsize(_hap_local_path(hap_url, app_desc))


if __name__ == "__main__":
    sys.exit(main())
