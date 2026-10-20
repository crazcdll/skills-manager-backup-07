#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""制品缓存守卫 —— 固化 L1 缓存的命中/并发/原子口径，防止回退。

用法：
    python3 scripts/dev/check_artifact_cache.py

覆盖不变量（临时缓存目录 + 假下载，不联网、不动真实 `.cache`）：

  A. 首次   未命中 → 下载一次 → 落盘 + sidecar 元数据，无 `.part.*` 残留
  B. 命中   再取同一 URL → 不再下载（缓存优先）
  C. 并发   4 个线程同时取同一制品 → 只下载一次（锁 + 等锁后二次判定）
  D. 隔离   不同制品并发 → 各下各的，互不阻塞
  E. 截断   文件被截断（磁盘大小 ≠ 元数据）→ 视为未命中并重下
  F. 漂移   远端大小已变化（同名换内容）→ 视为未命中并重下
  G. 原子   下载进行中，其他读者看不到半截文件（最终路径不存在）
  H. 来历   文件存在但无 sidecar → 不复用（避免复用来历不明文件）
  I. 推导   `artifact_path` / `is_cache_path` 路径推导与保留判定
  J. 入口   统一入口 `resolve`：本地路径（随仓制品）原样透传、远程 URL 落缓存
  K. 通道   安装通道声明组合：sandbox / 鸿蒙真机 = 不适用（制品不经本地）；其余 = 适用

退出码：0 全部通过 / 1 有失败。

【为什么需要它】L1 制品缓存是**跨 run / 跨子 Agent 共享**的资源，它的三个口径
（命中即免下载、并发只下一次、落盘原子）都没有编译期保护：改坏了不会报错，只会
悄悄变成"每个 run 重复拉 1.4G"或"读到半截包导致安装失败"。本脚本把口径固化成一条
命令（分层模型见 `shared/artifact_cache.py`）。
"""
import os
import shutil
import sys
import tempfile
import threading
import time

# 源树零字节码：本文件是进程入口，开关必须在引擎包导入之前生效。
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import artifact_cache  # noqa: E402

_URL = "https://example.invalid/artifacts/meituan-1.0.0-debug.hap"
_SCOPE = "harmony/emulator/com.sankuai.hmeituan"
_PAYLOAD = b"x" * 4096


class _FakeHttp:
    """假下载：可计数、可注入延迟、可指定远端大小（默认与 payload 一致）。"""

    def __init__(self, payload=_PAYLOAD):
        self.payload = payload
        self.downloads = []
        self.spans = []          # (start, end)：用于判定“并发确实并行”
        self.remote = len(payload)
        self.delay = 0.0
        self._lock = threading.Lock()

    def download(self, url, part_path, timeout):
        with self._lock:
            self.downloads.append(url)
        start = time.time()
        if self.delay:
            time.sleep(self.delay)
        with open(part_path, "wb") as fh:
            fh.write(self.payload)
        with self._lock:
            self.spans.append((start, time.time()))
        return os.path.getsize(part_path)

    def remote_size(self, url, timeout=60):
        return self.remote

    def count(self, url=None):
        with self._lock:
            return sum(1 for u in self.downloads if url is None or u == url)


def _install_fake_http(fake):
    artifact_cache._download = fake.download
    artifact_cache.remote_size = fake.remote_size


def _with_temp_cache(fn):
    """在临时缓存根下跑用例（不动真实 .cache，结束后恢复）。"""
    real_artifacts, real_root = artifact_cache.ARTIFACTS_DIR, artifact_cache.CACHE_ROOT
    tmp = tempfile.mkdtemp(prefix="artifact_cache_check_")
    artifact_cache.ARTIFACTS_DIR = os.path.join(tmp, "artifacts")
    artifact_cache.CACHE_ROOT = tmp
    try:
        return fn()
    finally:
        artifact_cache.ARTIFACTS_DIR, artifact_cache.CACHE_ROOT = real_artifacts, real_root
        shutil.rmtree(tmp, ignore_errors=True)


def _parts_left(path):
    directory = os.path.dirname(path)
    return [n for n in os.listdir(directory) if ".part." in n] if os.path.isdir(directory) else []


def case_a_first_download():
    fake = _FakeHttp()
    _install_fake_http(fake)
    path = artifact_cache.ensure(_URL, _SCOPE)
    ok = (os.path.isfile(path) and os.path.getsize(path) == len(_PAYLOAD)
          and fake.count() == 1 and not _parts_left(path)
          and os.path.isfile(path + ".meta.json"))
    extra = f"downloads={fake.count()} parts={_parts_left(path)}"
    return ok, f"首次下载一次并落盘（{extra}）"


def case_b_cache_hit():
    fake = _FakeHttp()
    _install_fake_http(fake)
    artifact_cache.ensure(_URL, _SCOPE)
    artifact_cache.ensure(_URL, _SCOPE)
    artifact_cache.ensure(_URL, _SCOPE)
    return fake.count() == 1, f"3 次安装只下载 1 次（downloads={fake.count()}）"


def case_c_concurrent_single_download():
    fake = _FakeHttp()
    fake.delay = 0.2  # 拉长下载窗口，制造真实竞争
    _install_fake_http(fake)
    errors = []

    def worker():
        try:
            artifact_cache.ensure(_URL, _SCOPE)
        except Exception as e:  # noqa: BLE001 —— 用例内收集异常
            errors.append(repr(e))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ok = not errors and fake.count() == 1
    return ok, f"4 线程并发只下载 1 次（downloads={fake.count()} errors={errors}）"


def case_d_different_artifacts_parallel():
    fake = _FakeHttp()
    fake.delay = 0.1
    _install_fake_http(fake)
    other = _URL.replace("meituan-1.0.0", "dianping-2.0.0")
    threads = [threading.Thread(target=artifact_cache.ensure, args=(u, _SCOPE))
               for u in (_URL, other)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # 判定“并行”用两次下载的时间区间是否重叠（不用耗时阈值，避免机器负载导致偶发失败）：
    # 不同制品各自持锁，若锁被误用成全局锁就会出现串行（区间不重叠）。
    spans = list(fake.spans)
    overlapped = (len(spans) == 2
                  and spans[0][0] < spans[1][1] and spans[1][0] < spans[0][1])
    ok = fake.count() == 2 and overlapped
    return ok, f"不同制品并发各下一次且区间重叠（downloads={fake.count()} spans={spans})"


def case_e_truncated_file():
    fake = _FakeHttp()
    _install_fake_http(fake)
    path = artifact_cache.ensure(_URL, _SCOPE)
    with open(path, "wb") as fh:  # 模拟中断留下的半截文件
        fh.write(_PAYLOAD[:100])
    info = artifact_cache.lookup(_URL, _SCOPE)
    artifact_cache.ensure(_URL, _SCOPE)
    ok = (info["hit"] is False and fake.count() == 2
          and os.path.getsize(path) == len(_PAYLOAD))
    return ok, f"截断文件不复用并重下（hit={info['hit']} downloads={fake.count()}）"


def case_f_remote_drift():
    fake = _FakeHttp()
    _install_fake_http(fake)
    artifact_cache.ensure(_URL, _SCOPE)
    fake.remote = len(_PAYLOAD) + 1  # 同名制品在远端已被替换
    info = artifact_cache.lookup(_URL, _SCOPE, verify_remote=True)
    artifact_cache.ensure(_URL, _SCOPE)
    return info["hit"] is False and fake.count() == 2, f"远端漂移触发重下（downloads={fake.count()}）"


def case_g_atomic_visibility():
    fake = _FakeHttp()
    fake.delay = 0.3
    _install_fake_http(fake)
    path = artifact_cache.artifact_path(_URL, _SCOPE)
    seen = []
    t = threading.Thread(target=artifact_cache.ensure, args=(_URL, _SCOPE))
    t.start()
    time.sleep(0.1)  # 下载进行中
    seen.append(os.path.exists(path))
    t.join()
    ok = seen == [False] and os.path.isfile(path)
    return ok, f"下载期间最终路径不可见（下载中 exists={seen} → 完成后 True）"


def case_h_no_sidecar():
    fake = _FakeHttp()
    _install_fake_http(fake)
    path = artifact_cache.artifact_path(_URL, _SCOPE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(_PAYLOAD)
    info = artifact_cache.lookup(_URL, _SCOPE)
    return info["hit"] is False, f"无 sidecar 的文件不复用（reason={info['reason'][:28]}…）"


def case_i_path_contract():
    artifact_cache.ARTIFACTS_DIR = "/tmp/_probe_cache/artifacts"
    artifact_cache.CACHE_ROOT = "/tmp/_probe_cache"
    path = artifact_cache.artifact_path(_URL, _SCOPE)
    ok = (path == "/tmp/_probe_cache/artifacts/harmony/emulator/com.sankuai.hmeituan/"
          "meituan-1.0.0-debug.hap"
          and artifact_cache.is_cache_path(path)
          and not artifact_cache.is_cache_path("/tmp/_probe_cache_other/x"))
    return ok, f"路径推导与保留判定（{path}）"


def case_j_resolve_passthrough():
    fake = _FakeHttp()
    _install_fake_http(fake)
    local = "/tmp/ADBKeyboard.apk"
    out_local = artifact_cache.resolve(local, _SCOPE)   # 本地路径：原样返回，零下载
    out_remote = artifact_cache.resolve(_URL, _SCOPE)   # 远程 URL：落 L1 缓存
    ok = (out_local == local and fake.count() == 1
          and os.path.isfile(out_remote)
          and artifact_cache.is_cache_path(out_remote))
    return ok, f"resolve 统一入口（本地透传={out_local} downloads={fake.count()}）"


def case_k_channel_declarations():
    """通道声明组合：两类“制品不经本地”的通道必须被标成不适用。

    · DeviceLifecycle 层：sandbox（yooz-server 下载并投递）；
    · PlatformOps 层：HarmonyOS form=real（HPX 企业安装页，下载由设备系统完成）。
    任一为 False 即不适用（取与），避免安装报告出现“未命中，安装时下载一次”的误导。
    """
    from devices.toolchain.app_installer import _apply_artifact_channel

    def _decl(value):
        return type("Decl", (), {"uses_local_artifact": value})()

    base = {"hit": False, "path": "/x/a.apk", "reason": "缓存无此制品"}
    results = {}
    for name, lifecycle_flag, ops_flag in (
        ("sandbox", False, True),
        ("harmony-real", True, False),
        ("android-local", True, True),
        ("harmony-emulator", True, True),
    ):
        version_check = {"artifactCache": dict(base)}
        _apply_artifact_channel(version_check, _decl(lifecycle_flag), _decl(ops_flag))
        results[name] = version_check["artifactCache"].get("applicable", True)
    ok = (results == {"sandbox": False, "harmony-real": False,
                      "android-local": True, "harmony-emulator": True})
    return ok, f"通道适用性判定 {results}"


CASES = [
    ("A 首次下载", case_a_first_download),
    ("B 命中缓存", case_b_cache_hit),
    ("C 并发只下一次", case_c_concurrent_single_download),
    ("D 不同制品并行", case_d_different_artifacts_parallel),
    ("E 截断重下", case_e_truncated_file),
    ("F 远端漂移重下", case_f_remote_drift),
    ("G 落盘原子性", case_g_atomic_visibility),
    ("H 无元数据不复用", case_h_no_sidecar),
    ("I 路径契约", case_i_path_contract),
    ("J 统一入口 resolve", case_j_resolve_passthrough),
    ("K 通道声明组合", case_k_channel_declarations),
]


def main():
    passed = 0
    for name, fn in CASES:
        try:
            ok, detail = _with_temp_cache(fn)
        except Exception as e:  # noqa: BLE001 —— 用例异常按失败处理并打印
            ok, detail = False, f"异常: {e!r}"
        print(f"{'✅' if ok else '❌'} {name}: {detail}")
        passed += 1 if ok else 0
    total = len(CASES)
    print(f"\n{'✅ 全部通过' if passed == total else '❌ 存在失败'}: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
