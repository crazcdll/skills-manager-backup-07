#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多 Agent 编排层 CLI —— 拆分 + 调度编排（plan）。

职责边界：
  · 编排层（本 Skill = ai-auto-ui-test）负责「拆分 / 派发 / 汇总」；
  · 本脚本只承担其中的 **拆分与调度编排**（纯本地、确定性、零外部依赖）；
  · 「派发子 Agent」由 AI 按 SKILL.md 执行（并行 Task）；子 Agent 执行完成后，结果
    **随 Task 直接返回编排层** —— 无需回写状态文件（Task 同步并行模型，子 Agent 非游离进程）；
  · 报告 **一个任务一份**：plan 预置共享报告行并把 report_id 写进每个分片，
    子 Agent 统一 append 到同一行（平台侧仍是逐 Case 原子追加，不会互相覆盖）；

输入（二选一，互斥）：
  · `--from-platform <需求 id | 需求名>` —— 调平台 `test-case-review/export`，服务端**只导出审核通过**
    的用例，再落成一用例一 `steps.json`（审核卡控在服务端，执行侧拿不到未审内容）。
  · `--local-cases <用例根目录>` —— 已完成转化、无平台审核记录的用例（如 MMCD）：
    目录下每个 `steps.json` = 一个用例，`case_id` = 所在目录名。
    必须显式 `--skip-review`（或每条自带 `reviewStatus=approved`）才放行，
    manifest 里记 `review_bypass` 供审计。

共享环境信息经 `--env` / `--env-file` 传入；平台 env 作为默认值，`--env` 覆盖。

调度模型（滚动补位 / 滑动窗口）：
  · **启用门槛**：用例数 < 3（1~2 个）时**不使用子 Agent**（单份直接执行），plan 会拒绝；
  · **每 Agent 用例上限** `--max-cases`（默认 2）→ 分片 = 按该上限连续切块（有序 = 待跑队列）；
  · **并发上限** `--concurrency`（默认 4）→ 同时在跑的子 Agent 上限；
  · AI 滚动派发：先起 `concurrency` 个，**谁先跑完就立刻从队首补下一个**，直到队列跑空且全部结束
    （一个慢分片不拖住其他分片）。

编排产物目录：$AI_UITEST_HOME/orchestration/<task_id>/（默认 ~/.local/share/ai-ui-autotest/orchestration）
用例资产根  ：$AI_UITEST_HOME/cases/{local,platform}/{...}/<caseId>/steps.json（长期维护，不被 prune）
  manifest.json          任务级索引：task 元信息 + 共享环境 + 分片列表（= 待跑队列）
  cases/                 平台 export 落盘的用例快照（一用例一 steps.json，本任务只读）
  shards/shard-NN.json   分片输入：env + cases（steps_path 指向 cases/ 快照，子 Agent 直接喂给
                       `steps-generate --steps <steps_path>`，中间无手写 CASES 环节）

清理归属：用例资产（cases/）由转化 Skill `ai-app-flow` 在开工前执行
`prune_cases.py`（需求维度）回收；**编排产物由本 Skill 自己回收**：`plan` 在创建新任务前
按 keep-latest-N（默认 5，`AI_UITEST_KEEP_ORCH_TASKS` 可调）删除旧任务目录。

用法：
  python3 scripts/orchestrate.py plan --from-platform <需求 id | 需求名> [--max-cases 2] [--concurrency 4]
  python3 scripts/orchestrate.py plan --local-cases <用例根目录> --skip-review [--run-type regression]
  python3 scripts/orchestrate.py fetch --from-platform <需求 id | 需求名> [--out <目录>]
  python3 scripts/orchestrate.py report-close --task <task_id>   # 全部分片结束后收尾共享报告
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
import uuid
from urllib.parse import quote

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)

# 机器级过程目录根：本 Skill 自有（不借住 ai-app-flow，也不落 Skill 安装目录）
HOME_ENV = "AI_UITEST_HOME"


def _uitest_home():
    """$AI_UITEST_HOME 优先，缺省 ~/.local/share/ai-ui-autotest（机器顶层唯一产物根）。"""
    override = (os.environ.get(HOME_ENV) or "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(os.path.expanduser("~"), ".local", "share", "ai-ui-autotest")


# 机器顶层根下的三类产物（Skill 安装目录内不落任何运行态）：
#   cases/          用例资产（人工/脚本维护，不被 prune）
#   orchestration/  编排过程目录（任务级，可滚动保留）
#   engine/         引擎运行态（run/reports/console/...，见 ai-ui-autotest-engine paths.py）
ORCH_ROOT = os.path.join(_uitest_home(), "orchestration")
CASES_ROOT = os.path.join(_uitest_home(), "cases")
# 用例资产的两个命名空间（同属 cases/，都在机器顶层根下，不被 prune）：
#   local/     已完成转化、人工/脚本维护（MMCD 等）
#   platform/ 平台审核通过用例的本地镜像（可随时从服务端刷新）
LOCAL_CASES_ROOT = os.path.join(CASES_ROOT, "local")
PLATFORM_CASES_ROOT = os.path.join(CASES_ROOT, "platform")
# 平台客户端复用 ai-app-flow（同一个 API_BASE / SSL 策略 / 失败收敛）
AI_APP_FLOW_SCRIPTS = os.path.join(os.path.dirname(SKILL_DIR), "ai-app-flow", "scripts")

DEFAULT_MAX_CASES = 2
DEFAULT_CONCURRENCY = 4
MIN_CASES_FOR_ORCHESTRATION = 3
# 编排任务目录滚动保留：默认留最近 5 个（环境变量可调，0 = 关闭）
DEFAULT_KEEP_ORCH_TASKS = 5
ENV_KEEP_ORCH_TASKS = "AI_UITEST_KEEP_ORCH_TASKS"
# 自动收尾上一个任务的共享报告：任务无活动超过该分钟数才动（防误收尾长跑任务）
DEFAULT_AUTOCLOSE_MINUTES = 360
ENV_AUTOCLOSE_MINUTES = "AI_UITEST_AUTOCLOSE_MINUTES"

# 审核平台前端（HashRouter）：未审核 / 无已审用例时把这条链接交给用户
REVIEW_BASE = os.environ.get("AI_TEST_REVIEW_BASE", "https://aimonitor.mynocode.host").rstrip("/")
# 报告门户 + 共享报告 id 环境变量（与引擎 transport.py 同一约定）
REPORT_PORTAL_BASE = REVIEW_BASE + "/#/test-reports/"
REPORT_ID_ENV = "AI_UITEST_REPORT_ID"


def _review_url(requirement_id):
    return f"{REVIEW_BASE}/#/test-cases/{requirement_id}"


# ─── 通用工具 ───────────────────────────────────────────────────────────────

def _task_dir(task_id):
    return os.path.join(ORCH_ROOT, task_id)


def _keep_orch_tasks():
    raw = (os.environ.get(ENV_KEEP_ORCH_TASKS) or "").strip()
    if not raw:
        return DEFAULT_KEEP_ORCH_TASKS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_KEEP_ORCH_TASKS


def _autoclose_minutes():
    raw = (os.environ.get(ENV_AUTOCLOSE_MINUTES) or "").strip()
    if not raw:
        return DEFAULT_AUTOCLOSE_MINUTES
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_AUTOCLOSE_MINUTES


def _patch_report_duration(rid, duration):
    """PATCH 共享报告的 duration；失败返回 (False, detail)，不抛异常。"""
    try:
        API_BASE, request_json = _platform_client()
        resp = request_json(f"{API_BASE}/test-report/update", {"id": rid, "duration": duration}) or {}
        body = resp.get("data") if isinstance(resp.get("data"), dict) else {}
        ok = resp.get("status") == "success" or body.get("status") == "success" or resp.get("code") == 0
        return ok, (resp.get("message") or "")
    except SystemExit as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001 —— 收尾失败不拉断编排
        return False, str(exc)


def _close_report_manifest(manifest_path, guard_minutes=DEFAULT_AUTOCLOSE_MINUTES):
    """给单个任务的共享报告收尾（幂等）。

    guard_minutes 内还有活动则跳过，避免把可能长跑的上一任务提前收尾。
    收尾后写回 manifest（`report.closed_at` / `duration`），下次不再重复请求。
    """
    if not os.path.isfile(manifest_path):
        return False
    try:
        manifest = _read_json(manifest_path)
    except (OSError, ValueError):
        return False
    report = manifest.get("report") or {}
    rid = report.get("id")
    if not rid or report.get("closed_at"):
        return False
    try:
        last_active = os.path.getmtime(manifest_path)
    except OSError:
        last_active = time.time()
    if guard_minutes > 0 and (time.time() - last_active) < guard_minutes * 60:
        return False
    try:
        started = time.mktime(time.strptime(manifest.get("created_at", ""), "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        started = last_active
    duration = _format_duration(max(0, int((last_active - started) * 1000)))
    ok, detail = _patch_report_duration(rid, duration)
    report["duration"] = duration
    report["closed_at"] = _now()
    report["auto_closed"] = True
    report["close_ok"] = ok
    if not ok:
        report["close_error"] = detail
    manifest["report"] = report
    try:
        _write_json(manifest_path, manifest)
    except OSError:
        pass
    return True


def _close_stale_reports(guard_minutes=DEFAULT_AUTOCLOSE_MINUTES):
    """plan 前扫一遍历史任务，把已结束但没收尾的共享报告自动收尾。

    调用方不必再手动跑 `report-close`；紧急想看当前任务时长时仍可手动执行。
    """
    if not os.path.isdir(ORCH_ROOT):
        return []
    closed = []
    for name in sorted(os.listdir(ORCH_ROOT)):
        if name.startswith("."):
            continue
        if _close_report_manifest(os.path.join(ORCH_ROOT, name, "manifest.json"), guard_minutes):
            closed.append(name)
    if closed:
        print(
            f"  🧾 已自动收尾 {len(closed)} 个历史共享报告"
            f"（最后活动 ≥ {guard_minutes} 分钟）：{', '.join(closed[:6])}"
        )
    return closed


def _prune_orchestration(keep):
    """滚动保留最近 N 个编排任务（含 cases 快照/分片/清单）。

    MMCD 路径不经过 ai-app-flow，因此不能只依赖 `prune_cases.py`；plan 自己回收。
    keep=0 关闭。当前任务在剪枝之后才创建，不会被误删。
    """
    if keep <= 0 or not os.path.isdir(ORCH_ROOT):
        return []
    items = []
    for name in os.listdir(ORCH_ROOT):
        if name.startswith("."):
            continue
        path = os.path.join(ORCH_ROOT, name)
        if not os.path.isdir(path):
            continue
        try:
            items.append((os.path.getmtime(path), name, path))
        except OSError:
            continue
    items.sort(reverse=True)
    dropped = [name for _mtime, name, _path in items[keep:]]
    for _mtime, _name, path in items[keep:]:
        # 删除任务目录前先把它未收尾的报告行关掉，避免留下时长不对的旧行
        _close_report_manifest(os.path.join(path, "manifest.json"), guard_minutes=0)
        shutil.rmtree(path, ignore_errors=True)
    if dropped:
        print(f"  🧹 编排产物已清理 {len(dropped)} 个旧任务（保留最近 {keep} 个）：{', '.join(dropped[:6])}")
    return dropped


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _new_task_id():
    return "orch-" + time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]


def _new_report_id():
    """共享报告 id：与引擎独立运行的 batch id 同形，便于门户按时间排序。"""
    return "batch-" + time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4]


def _format_duration(ms):
    """与引擎 transport.format_duration 保持一致：<60s → 12s，否则 3m05s。"""
    if ms is None:
        return ""
    seconds = int(ms) // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes, remaining = divmod(seconds, 60)
    return f"{minutes}m{remaining}s" if remaining else f"{minutes}m"


def _open_shared_report(report_id, title, env, run_type, device_hint):
    """Open：预置一行共享报告（best-effort）。

    引擎在检测到 `AI_UITEST_REPORT_ID` 后会跳过自己的 Open，只向这行 append；
    因此这里失败也不阻断编排：首个 Case 追加时平台会按同一个 id 自动建行。
    """
    try:
        API_BASE, request_json = _platform_client()
    except SystemExit as exc:
        print(f"  ⚠️ 共享报告未预置（{exc}）")
        return False
    payload = {
        "id": report_id,
        "title": title,
        "device": None,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": (device_hint or {}).get("platform") or "Android",
        "app": (device_hint or {}).get("app") or "美团",
        "duration": "",
        "total_cases": 0,
        "total_steps": 0,
        "success_steps": 0,
        "failed_steps": 0,
        "cases": [],
        "ec_case_id": None,
        "user_id": env.get("resource_mis") or env.get("mis") or None,
        "run_type": run_type,
    }
    try:
        resp = request_json(f"{API_BASE}/test-report/insert", payload) or {}
    except Exception as exc:  # noqa: BLE001 —— 预置失败不阻断编排
        print(f"  ⚠️ 共享报告预置失败（首个 Case 追加时会自动建行）: {exc}")
        return False
    body = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    ok = resp.get("status") == "success" or body.get("status") == "success" or resp.get("code") == 0
    if ok:
        print(f"  🧾 共享报告已预置: {REPORT_PORTAL_BASE}{report_id}")
    else:
        print(
            "  ⚠️ 共享报告预置失败（首个 Case 追加时会自动建行）: "
            f"{resp.get('message') or resp.get('raw') or 'unknown'}"
        )
    return ok


def _safe_slug(text, fallback="requirement"):
    """目录名安全化（保留中文/字母/数字/._-）。"""
    slug = re.sub(r"[^\w\u4e00-\u9fa5.-]+", "-", str(text or "")).strip("-.")
    return slug[:80] or fallback


def _platform_cases_dir(payload):
    """平台用例镜像目录：$AI_UITEST_HOME/cases/platform/<需求id-需求名>/。"""
    req = payload.get("requirement") or {}
    key = f"{req.get('id') or ''}-{req.get('name') or req.get('id') or 'requirement'}"
    return os.path.join(PLATFORM_CASES_ROOT, _safe_slug(key))


def _mirror_payload(payload, dest_dir):
    """平台 payload → 本地镜像（覆盖写 + 清掉已不在服务端的用例目录）。

    仅清理 cases/platform/<需求>/ 下的子目录（可由服务端随时重建），
    不碰 cases/local/，也不碰其他需求目录。
    """
    os.makedirs(dest_dir, exist_ok=True)
    cases = _materialize_payload(payload, dest_dir)
    keep = {c["case_id"] for c in cases}
    removed = []
    for name in sorted(os.listdir(dest_dir)):
        path = os.path.join(dest_dir, name)
        if os.path.isdir(path) and name not in keep:
            shutil.rmtree(path, ignore_errors=True)
            removed.append(name)
    return cases, removed


def _snapshot_cases(cases, dest_dir):
    """把用例快照到任务目录（子 Agent 只读快照，源目录运行期被改不影响本任务）。"""
    snapshot = []
    for case in cases:
        path = os.path.join(dest_dir, case["case_id"], "steps.json")
        _write_json(path, _read_json(case["steps_path"]))
        snapshot.append({**case, "steps_path": path})
    return snapshot


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _chunk(seq, size):
    """按固定大小连续切块（最后一块可不足 size）。"""
    size = max(1, int(size))
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def _load_env(args):
    """共享环境信息：--env-file 先，--env 后（后者覆盖前者）。缺省 {}。"""
    env = {}
    if args.env_file:
        env.update(_read_json(args.env_file))
    if args.env:
        try:
            env.update(json.loads(args.env))
        except json.JSONDecodeError as e:
            raise SystemExit(f"❌ --env 不是合法 JSON: {e}")
    return env


# ─── 审核门禁（审核链接 + 审核态）─────────────────────────────────────────

def _fetch_requirement(target):
    """取需求记录（含 cases 审核态）；不存在时直接提示先去入库。"""
    key = str(target or "").strip()
    if not key:
        raise SystemExit("❌ --from-platform 必传（需求 id 或需求名）")
    API_BASE, request_json = _platform_client()
    query = ("id=" + quote(key)) if key.isdigit() else ("requirement_name=" + quote(key))
    resp = request_json(f"{API_BASE}/test-case-review/get?{query}")
    body = (resp or {}).get("data") or {}
    if body.get("status") != "success":
        raise SystemExit(f"❌ 查询需求失败：{body.get('error')}")
    row = body.get("data")
    if not isinstance(row, dict) or not row.get("id"):
        raise SystemExit(f"❌ 平台上没有这个需求（{key}）：先由 ai-app-flow 生成 steps.json 并入库")
    return row


def cmd_review(args):
    """审核门禁：输出审核链接与审核态。

    退出码语义：
      0 = 全部审核通过，可直接执行
      3 = 部分通过（≥1 条 approved），需用户确认后只执行已通过用例
      2 = 0 条通过（全待审 / 全驳回 / 无用例），彻底阻断
    """
    row = _fetch_requirement(args.from_platform)
    cases = row.get("cases") or []
    approved = [c for c in cases if c.get("reviewStatus") == "approved"]
    pending = [c for c in cases if c.get("reviewStatus") == "pending"]
    rejected = [c for c in cases if c.get("reviewStatus") == "rejected"]

    print("=" * 60)
    print("  人工审核门禁")
    print("=" * 60)
    print(f"  需求  : {row.get('requirement_name')}（id={row.get('id')}）")
    print(f"  审核页: {_review_url(row.get('id'))}")
    print(f"  用例  : 共 {len(cases)} · 通过 {len(approved)} · 待审 {len(pending)} · 驳回 {len(rejected)}")
    if pending:
        print(f"  待审  : {', '.join(str(c.get('caseKey')) for c in pending[:8])}" + ("…" if len(pending) > 8 else ""))
    if rejected:
        print(f"  驳回  : {', '.join(str(c.get('caseKey')) for c in rejected[:8])}" + ("…" if len(rejected) > 8 else ""))
    print()
    if not cases:
        print("  ⏸  该需求下没有用例，先由 ai-app-flow 生成 steps.json 并入库")
        return 2
    if not approved:
        print("  ⛔ 没有任何用例审核通过：把上面的审核页链接给用户，审核通过后再执行")
        print(f"     审核后：python3 scripts/orchestrate.py review --from-platform {row.get('id')}")
        return 2
    if pending or rejected:
        skipped = len(pending) + len(rejected)
        print(
            f"  ⚠️  部分通过：本次只执行已通过的 {len(approved)} 条，"
            f"跳过 {skipped} 条（待审 {len(pending)} / 驳回 {len(rejected)}）"
        )
        print("     需要用户确认「只跑已通过的用例」后再继续（服务端 export 只下发 approved，不会跑到未审用例）")
        print(f"     确认后：python3 scripts/orchestrate.py fetch --from-platform {row.get('id')}")
        return 3
    print("  ✅ 全部审核通过，可以执行")
    print(f"     下一步：python3 scripts/orchestrate.py fetch --from-platform {row.get('id')}")
    return 0


# ─── 平台取数（审核通过用例）──────────────────────────────────────────────

def _platform_client():
    """复用 ai-app-flow 的平台客户端（同一 API_BASE / SSL 策略 / 失败收敛）。

    本 Skill 已声明依赖 `ai-app-flow`（env_setup 安装），这里只在路径上接一次，
    避免再维护一份 API_BASE 与证书策略。
    """
    if AI_APP_FLOW_SCRIPTS not in sys.path:
        sys.path.insert(0, AI_APP_FLOW_SCRIPTS)
    try:
        from platform_api import API_BASE, request_json  # noqa: WPS433 —— 延迟导入，避免无平台依赖时炸启
    except ImportError as exc:
        raise SystemExit(
            f"❌ 找不到平台客户端（{AI_APP_FLOW_SCRIPTS}）：{exc}\n"
            "   先跑 `python3 scripts/env_setup.py` 安装依赖 Skill `ai-app-flow`。"
        )
    return API_BASE, request_json


def _resolve_requirement_id(target):
    """按 id / 需求名定位平台记录 id（仅用于给用户拼审核链接）。"""
    key = str(target or "").strip()
    if not key:
        return None
    if key.isdigit():
        return key
    try:
        API_BASE, request_json = _platform_client()
        resp = request_json(f"{API_BASE}/test-case-review/get?requirement_name={quote(key)}")
    except Exception:  # noqa: BLE001 —— 拼链接失败不阻断主流程
        return None
    body = (resp or {}).get("data") or {}
    row = body.get("data") if body.get("status") == "success" else None
    return str((row or {}).get("id") or "").strip() or None


def _fetch_export(target):
    """从平台取「审核通过用例」的执行 payload（服务端已过滤，不会再含未审/驳回）。"""
    key = str(target or "").strip()
    if not key:
        raise SystemExit("❌ --from-platform 必传（需求 id 或需求名）")

    API_BASE, request_json = _platform_client()
    # 纯数字当 id，其余当需求名（同名即同一需求，与平台 get 语义一致）
    query = ("id=" + quote(key)) if key.isdigit() else ("requirement_name=" + quote(key))
    resp = request_json(f"{API_BASE}/test-case-review/export?{query}")
    body = (resp or {}).get("data")
    if not isinstance(body, dict):
        hint = "（该环境可能还未部署 /test-case-review/* 接口）" if (resp or {}).get("code") == 404 else ""
        raise SystemExit(f"❌ 平台接口返回异常{hint}：{resp}")
    if body.get("status") != "success":
        err = str(body.get("error") or "")
        if "approved" in err:
            rid = _resolve_requirement_id(key)
            link = f"\n   🔎 先人工审核：{_review_url(rid)}" if rid else ""
            raise SystemExit(
                "❌ 该需求还没有审核通过的用例（服务端只导出 approved，未审/驳回不可执行）。"
                f"{link}\n   审核通过后再重新执行本命令（不要绕过平台直跑本地文件）。"
            )
        raise SystemExit(f"❌ 平台取数失败：{err}")

    payload = body.get("data") or {}
    if not payload.get("cases"):
        raise SystemExit("❌ 平台没有可执行用例（执行只允许审核通过的用例）")
    return payload


def _env_seed(engine_env):
    """平台 env（引擎形状）→ input-seed 可用的环境字段。

    只映射引擎**已有问题 id**：`env_type` / `swim_lane_name` / `swim_url_mappings`。
    `platform` / `app` 不属问题 id，改以 device_hint 交给子 Agent 选 `device_combo`。
    """
    seed = {}
    if engine_env.get("type"):
        seed["env_type"] = engine_env["type"]

    lane = (engine_env.get("swimline") or {}).get("lane_name")
    if lane:
        seed["swim_lane_name"] = lane

    mappings = engine_env.get("url_mappings")
    if mappings:
        seed["swim_url_mappings"] = mappings
    return seed


# steps.json 的 env 白名单（与引擎 flow_json.ENV_KEYS 对齐；platform/app 不在内）
STEPS_ENV_KEYS = ("type", "swimline", "url_mappings", "bundle_lock", "testability", "preconditions")


def _engine_flow_json():
    """引擎解析器（真正的消费方）。

    落盘前用它校一遍：平台数据是**人工编辑过的**，不能假定合法；
    宁可在 fetch/plan 阶段带着 caseKey 报错，也不要让引擎跑到一半报。
    """
    engine_scripts = os.path.join(os.path.dirname(SKILL_DIR), "ai-ui-autotest-engine", "scripts")
    if engine_scripts not in sys.path:
        sys.path.insert(0, engine_scripts)
    try:
        from aitest.execution.engine.flow import flow_json  # noqa: WPS433 —— 延迟导入
    except ImportError as exc:
        raise SystemExit(
            f"❌ 找不到引擎解析器（{engine_scripts}）：{exc}\n"
            "   先跑 `python3 scripts/env_setup.py` 安装依赖 Skill `ai-ui-autotest-engine`。"
        )
    return flow_json


def _materialize_payload(payload, dest_dir):
    """平台 export payload → 一用例一 `steps.json`（引擎唯一输入形态）。

    只做形状搬运 + 一次引擎侧校验：payload 已由服务端把 vars / env 压成引擎态，
    但 cases 是人工编辑过的，必须确认引擎真能消费，否则带着 caseKey 直接失败。
    """
    env = payload.get("env") or {}
    shared = {key: env[key] for key in STEPS_ENV_KEYS if env.get(key)}
    flow_json = _engine_flow_json()

    cases = []
    for index, case in enumerate(payload.get("cases") or [], 1):
        case_key = str(case.get("caseKey") or "").strip()
        if not case_key:
            raise SystemExit(f"❌ 平台 payload 第 {index} 条用例缺少 caseKey")

        scheme = str(case.get("scheme") or "").strip()
        if not scheme:
            raise SystemExit(f"❌ {case_key}: 平台 payload 的 scheme 为空（落地入口必须存在）")

        steps = case.get("steps") or []
        if not steps:
            raise SystemExit(f"❌ {case_key}: 平台 payload 没有 steps，无法执行")

        raw_mocks = case.get("mockIds")
        mock_ids = [str(item).strip() for item in raw_mocks if str(item).strip()] if isinstance(raw_mocks, list) else []

        flow = {
            "caseId": case_key,
            "title": str(case.get("title") or case_key),
            "env": {**shared, "scheme": scheme},
            "steps": steps,
        }
        if mock_ids:
            # AppMock 是 case 级配置（引擎 env.mock_ids 原样透传），不能提升到需求级
            flow["env"]["mock_ids"] = mock_ids
        if case.get("vars"):
            flow["env"]["vars"] = case["vars"]

        try:
            flow_json.to_cases(flow)
        except Exception as exc:  # noqa: BLE001 —— 引擎校验异常统一带 caseKey 上抛
            raise SystemExit(
                f"❌ {case_key}: 平台数据引擎无法执行 —— {exc}\n"
                "   请在审核端修正后重新同步（不要绕过平台直接跑本地文件）。"
            )

        path = os.path.join(dest_dir, case_key, "steps.json")
        _write_json(path, flow)
        cases.append({
            "case_id": case_key,
            "case_name": flow["title"],
            "steps_path": path,
            "revision": case.get("revision"),
            "source": "platform",
        })
    return cases


# ─── 本地用例（已完成转化 / 无平台审核记录）──────────────────────────

# 本地 steps.json 里可提到共享环境的字段（与引擎 flow_json.ENV_KEYS 对齐）
LOCAL_SHARED_ENV_KEYS = ("type", "swimline", "url_mappings", "bundle_lock", "testability", "preconditions")


def _iter_steps_files(root):
    """递归找出所有 `steps.json`（一用例一目录）。"""
    for dirpath, _dirnames, filenames in os.walk(root):
        if "steps.json" in filenames:
            yield os.path.join(dirpath, "steps.json")


def _collect_local_flows(cases_dir):
    """本地用例根 → 引擎形状 flows。

    只做「读取 + caseId 对齐 + 引擎校验」：本地 steps.json 本来就是引擎唯一输入形态，
    不需要再翻译；case_id 以**所在目录名**为准（平台/报告都按它引用）。
    """
    root = os.path.abspath(os.path.expanduser(cases_dir))
    if not os.path.isdir(root):
        raise SystemExit(f"❌ --local-cases 目录不存在: {root}")

    flow_json = _engine_flow_json()
    flows = []
    for path in sorted(_iter_steps_files(root)):
        case_id = os.path.basename(os.path.dirname(path))
        try:
            flow = _read_json(path)
        except (OSError, ValueError) as exc:
            raise SystemExit(f"❌ 读取失败 {path}: {exc}")
        if not isinstance(flow, dict):
            raise SystemExit(f"❌ {path}: 顶层必须是对象")

        declared = str(flow.get("caseId") or "").strip()
        if declared and declared != case_id:
            raise SystemExit(
                f"❌ {path}: caseId({declared}) 与目录名({case_id}) 不一致；"
                "case_id 以目录名为准，请对齐后重试"
            )
        flow["caseId"] = case_id

        if not str((flow.get("env") or {}).get("scheme") or "").strip():
            raise SystemExit(f"❌ {case_id}: env.scheme 为空（落地入口必须存在）")
        if not flow.get("steps"):
            raise SystemExit(f"❌ {case_id}: steps 为空，无法执行")

        try:
            flow_json.to_cases(flow)
        except Exception as exc:  # noqa: BLE001 —— 引擎校验异常统一带 caseId 上抛
            raise SystemExit(f"❌ {case_id}: steps.json 引擎无法执行 —— {exc}")
        flows.append(flow)

    if not flows:
        raise SystemExit(f"❌ {root} 下没有 steps.json（一用例一目录）")
    return root, flows


def _local_shared_env(flows):
    """本地用例的共享环境：从各 case env 的 env 字段提（先到先得）。"""
    shared = {}
    for flow in flows:
        env = flow.get("env") or {}
        for key in LOCAL_SHARED_ENV_KEYS:
            if key not in shared and env.get(key):
                shared[key] = env[key]
    return shared


def _materialize_local(flows, dest_dir):
    """本地用例 → 任务快照（一用例一 steps.json）。"""
    cases = []
    for flow in flows:
        case_id = flow["caseId"]
        path = os.path.join(dest_dir, case_id, "steps.json")
        _write_json(path, flow)
        cases.append({
            "case_id": case_id,
            "case_name": str(flow.get("title") or case_id),
            "steps_path": path,
            "source": "local",
        })
    return cases


def _local_review_gate(flows, skip_review):
    """审核旁路门禁：全部自带 approved 才能免 --skip-review。

    返回是否实际使用旁路（写进 manifest，便于审计）。
    """
    states = [
        str(f.get("reviewStatus") or f.get("review_status") or "").strip().lower()
        for f in flows
    ]
    if all(state == "approved" for state in states):
        return False
    if skip_review:
        return True
    blocked = [f["caseId"] for f, state in zip(flows, states) if state != "approved"]
    raise SystemExit(
        f"❌ 本地用例未全部标记审核通过（{', '.join(blocked[:8])}）。\n"
        "   已完成转化、无平台审核记录的用例（如 MMCD）请显式加 --skip-review；\n"
        "   需要审核卡控请改用 --from-platform <需求 id>。"
    )


# ─── plan ───────────────────────────────────────────────────────────────────

def cmd_plan(args):
    local_dir = (getattr(args, "local_cases", "") or "").strip()
    target = (args.from_platform or "").strip()
    if bool(local_dir) == bool(target):
        raise SystemExit("❌ --from-platform 与 --local-cases 必须且只能传一个")

    review_bypass = False
    review_url = ""

    if local_dir:
        root, flows = _collect_local_flows(local_dir)
        if len(flows) < MIN_CASES_FOR_ORCHESTRATION:
            raise SystemExit(
                f"❌ 本地用例只有 {len(flows)} 条（< {MIN_CASES_FOR_ORCHESTRATION}），无需多 Agent 编排。\n"
                "   请走「单份执行」：把用例目录直接交给 ai-ui-autotest-engine（见 SKILL.md 执行规则 5）。"
            )
        review_bypass = _local_review_gate(flows, bool(getattr(args, "skip_review", False)))
        # 用例自带 env 作板底，--env 显式值优先（与平台路径同口径）
        env = {**_local_shared_env(flows), **_load_env(args)}
        req_name = os.path.basename(root.rstrip(os.sep)) or root
        source_label = f"local:{root}"
        payload_env = {}

        def _materialize(dest_dir):
            return _materialize_local(flows, dest_dir)
    else:
        payload = _fetch_export(target)
        platform_cases = payload.get("cases") or []
        if len(platform_cases) < MIN_CASES_FOR_ORCHESTRATION:
            raise SystemExit(
                f"❌ 平台只导出 {len(platform_cases)} 条已通过用例（< {MIN_CASES_FOR_ORCHESTRATION}），"
                "无需多 Agent 编排。\n"
                f"   请走「单份执行」：`python3 scripts/orchestrate.py fetch --from-platform {target}` 取用例，\n"
                "   再由当前 AI 直接执行 ai-ui-autotest-engine（见 SKILL.md 执行规则 5）。"
            )
        review_url = _review_url((payload.get("requirement") or {}).get("id") or target)
        env = {**_env_seed(payload.get("env") or {}), **_load_env(args)}
        req_name = str((payload.get("requirement") or {}).get("name") or target)
        source_label = f"platform:{target}"
        payload_env = payload.get("env") or {}

        def _materialize(dest_dir):
            # 先刷机器顶层用例镜像（cases/platform/），再快照到任务目录（与源解耦）
            mirror, removed = _mirror_payload(payload, _platform_cases_dir(payload))
            if removed:
                print(f"  🧹 用例镜像已清理过期 {len(removed)} 条：{', '.join(removed[:8])}")
            print(f"  用例镜像: {mirror}")
            return _snapshot_cases(mirror, dest_dir)

    max_cases = int(args.max_cases or DEFAULT_MAX_CASES)
    concurrency = int(args.concurrency or DEFAULT_CONCURRENCY)
    if max_cases < 1:
        raise SystemExit("❌ --max-cases 必须 ≥ 1")
    if concurrency < 1:
        raise SystemExit("❌ --concurrency 必须 ≥ 1")

    task_id = args.task or _new_task_id()
    tdir = _task_dir(task_id)
    if os.path.exists(tdir):
        raise SystemExit(f"❌ 任务已存在: {task_id}（换 --task 或先删除 {tdir}）")

    # 先自动收尾历史共享报告（超时的），再回收旧任务目录，最后落本次快照
    _close_stale_reports()
    _prune_orchestration(max(0, _keep_orch_tasks() - 1))

    # ⓪ 用例快照：两路输入统一落成「一用例一 steps.json」，运行期不再回读源
    cases = _materialize(os.path.join(tdir, "cases"))

    # ① 按「每 Agent 用例上限」连续切分片
    groups = _chunk(cases, max_cases)
    os.makedirs(os.path.join(tdir, "shards"), exist_ok=True)

    manifest_shards = []
    # 运行类型：显式参数 > 环境变量 > adhoc；写入每个分片，子 Agent 据此导出给引擎
    run_type = (getattr(args, "run_type", "") or os.environ.get("AI_UITEST_RUN_TYPE", "") or "adhoc").strip().lower()
    if run_type not in ("regression", "feature", "adhoc"):
        run_type = "adhoc"

    # 共享报告：一个任务只一行。plan 先 Open，再把 report_id 写进每个分片；
    # 子 Agent 导出 AI_UITEST_REPORT_ID 后，引擎会跳过自己的 Open，只向这行 append。
    device_hint = {
        "platform": payload_env.get("platform"),
        "app": payload_env.get("app"),
    }
    report_id = (getattr(args, "report_id", "") or "").strip() or _new_report_id()
    report_title = (getattr(args, "report_title", "") or "").strip() or req_name
    report_opened = False
    if not getattr(args, "no_report", False):
        report_opened = _open_shared_report(report_id, report_title, env, run_type, device_hint)
    report = {
        "id": report_id,
        "title": report_title,
        "run_type": run_type,
        "opened": report_opened,
        "url": f"{REPORT_PORTAL_BASE}{report_id}",
    }

    for idx, group in enumerate(groups, 1):
        sid = f"shard-{idx:02d}"
        shard = {
            "task_id": task_id,
            "shard_id": sid,
            # 本地归档标题（flow-init --flow-name）；平台报告行标题统一用 report.title
            "report_name": f"{req_name} · {sid}",
            # 全部分片共用的报告 id：子 Agent 必须 export AI_UITEST_REPORT_ID=<该值>
            "report_id": report_id,
            "run_type": run_type,
            "env": env,
            "cases": group,
        }
        _write_json(os.path.join(tdir, "shards", f"{sid}.json"), shard)
        manifest_shards.append({
            "shard_id": sid,
            "report_name": shard["report_name"],
            "case_count": len(group),
            "case_ids": [c["case_id"] for c in group],
        })

    # 分片按序号有序 = 待跑队列；并发上限由 `concurrency` 表达（AI 滚动补位，不再分轮）
    manifest = {
        "task_id": task_id,
        "created_at": _now(),
        "source": source_label,
        "review_bypass": review_bypass,
        "cases_dir": os.path.join(tdir, "cases"),
        "case_count": len(cases),
        "shard_count": len(manifest_shards),
        "run_type": run_type,
        "max_cases_per_agent": max_cases,
        "concurrency": concurrency,
        "env": env,
        "shards": manifest_shards,
        "report": report,
        # platform/app 不属于引擎问题 id，作为选 device_combo 的提示交给子 Agent
        "device_hint": device_hint,
    }
    _write_json(os.path.join(tdir, "manifest.json"), manifest)
    if review_url:
        print(f"  审核页  : {review_url}")
    _print_plan(manifest, tdir)
    return 0


def _print_plan(manifest, tdir):
    print("=" * 60)
    print("  多 Agent 编排 · 派发计划")
    print("=" * 60)
    print(f"  task_id : {manifest['task_id']}")
    report = manifest.get("report") or {}
    if report.get("id"):
        print(f"  报告    : {report.get('url') or report['id']}（全部分片共用一行）")
    print(f"  用例源  : {manifest['source']}")
    if manifest.get("review_bypass"):
        print("  审核    : 本地用例 · 已显式跳过平台审核（review_bypass=true）")
    print(f"  用例快照: {manifest['cases_dir']}")
    print(f"  用例数  : {manifest['case_count']}")
    print(f"  分片数  : {manifest['shard_count']}（每个 ≤ {manifest['max_cases_per_agent']} 用例）")
    print(f"  并发上限: {manifest['concurrency']}")
    print(f"  编排产物目录: {tdir}")
    hint = manifest.get("device_hint") or {}
    if hint.get("platform") or hint.get("app"):
        print(
            f"  设备提示: platform={hint.get('platform') or '-'} app={hint.get('app') or '-'}"
            "（选 device_combo 时对齐，勿直接 input-seed）"
        )
    print()
    print(f"  [待跑队列 · 维持 ≤ {manifest['concurrency']} 个在跑，谁先完成谁补下一个]")
    for i, s in enumerate(manifest["shards"], 1):
        path = os.path.join(tdir, "shards", f"{s['shard_id']}.json")
        print(f"    {i}. {s['shard_id']}  cases={s['case_count']}  → {path}")
        print(f"         {', '.join(s['case_ids'])}")
        print(f"         共用报告: {manifest.get('report', {}).get('id', '-')}")
        try:
            for c in _read_json(path).get("cases", []):
                print(f"         · {c['case_id']}: <入口> steps-generate --steps {c['steps_path']} --tag {c['case_id']}")
        except (OSError, ValueError):
            pass
    print()
    print("  [下一步 · AI]")
    print(f"    滚动补位派发（滑动窗口 = {manifest['concurrency']}）——")
    print(f"      · 先并行启动队列前 {manifest['concurrency']} 个分片（各 1 个子 Agent）；")
    print("      · 之后谁先跑完，就立刻从队首取下一个分片补上，保持同时在跑 ≤ 上限；")
    print("      · 子 Agent 读自己的 shards/<shard>.json（env + cases），")
    print("        按 SKILL.md「子 Agent 派发契约」执行 ai-ui-autotest-engine 单份路径；")
    print("      · 直到队列跑空且全部结束；结果随 Task 直接返回，无需回写（全部分片写入同一报告行）。")
    print("      · 共享报告无需手动收尾：下一次 plan 会自动收尾超过保护期（6 小时）的旧任务；")
    print("        需要立刻修正 duration 时才跑 report-close --task <task_id>。")
    print()


# ─── report-close（共享报告收尾）──────────────────────────────

def cmd_report_close(args):
    """Close：全部分片结束后收尾共享报告。

    子 Agent 各自 finalize 时不再新建报告（已注入 AI_UITEST_REPORT_ID），
    但行级 duration 会被子 Agent 覆盖；这里用任务起止时间统一回写一份全量口径。
    """
    tdir = _task_dir(args.task)
    manifest_path = os.path.join(tdir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise SystemExit(f"❌ 找不到编排任务: {manifest_path}")
    manifest = _read_json(manifest_path)
    report = manifest.get("report") or {}
    rid = report.get("id") or (args.report_id or "").strip()
    if not rid:
        raise SystemExit("❌ manifest 里没有共享报告 id（plan 未生成）")

    if args.duration_ms is not None:
        elapsed_ms = max(0, int(args.duration_ms))
    else:
        try:
            started = time.mktime(time.strptime(manifest.get("created_at", ""), "%Y-%m-%dT%H:%M:%S"))
        except (TypeError, ValueError):
            started = None
        elapsed_ms = int((time.time() - started) * 1000) if started else 0
    duration = _format_duration(elapsed_ms)

    detail = ""
    ok, detail = _patch_report_duration(rid, duration)

    report["duration"] = duration
    report["closed_at"] = _now()
    manifest["report"] = report
    _write_json(manifest_path, manifest)

    if ok:
        print(f"✅ 共享报告已收尾: {report.get('url') or REPORT_PORTAL_BASE + rid}（duration={duration or '-'}）")
    else:
        print(f"⚠️ 共享报告收尾失败（报告内容不受影响）: {detail or 'unknown'}")
        print(f"   报告入口: {report.get('url') or REPORT_PORTAL_BASE + rid}")
    return 0


# ─── fetch（平台取数 → 本地用例目录）────────────────────────────────────

def cmd_fetch(args):
    """只取数不编排：把平台审核通过的用例落成 `cases/<caseKey>/steps.json`。

    默认写入机器顶层用例镜像 `$AI_UITEST_HOME/cases/platform/<需求>/`（可刷新，不被 prune）；
    `--out` 可指定任意目录（此时保持「目录必须为空」的保护）。
    单份跑（或不足 3 条）时用：产物目录可直接交给 ai-ui-autotest-engine。
    """
    target = (args.from_platform or "").strip()
    payload = _fetch_export(target)

    removed = []
    if (args.out or "").strip():
        out = os.path.abspath(os.path.expanduser(args.out.strip()))
        if os.path.isdir(out) and os.listdir(out):
            raise SystemExit(f"❌ 输出目录非空：{out}（换 --out 或先清理）")
        os.makedirs(out, exist_ok=True)
        cases = _materialize_payload(payload, out)
    else:
        out = _platform_cases_dir(payload)
        cases, removed = _mirror_payload(payload, out)
    req = payload.get("requirement") or {}
    env = payload.get("env") or {}
    lane = (env.get("swimline") or {}).get("lane_name") or "-"

    print("=" * 60)
    print("  平台取数 · 已审核通过用例")
    print("=" * 60)
    print(f"  需求  : {req.get('name') or target}（id={req.get('id')}）")
    print(f"  用例数: {len(cases)}（只含 approved）")
    print(f"  设备  : platform={env.get('platform') or '-'} app={env.get('app') or '-'}")
    print(f"  环境  : type={env.get('type') or '-'} 泳道={lane}")
    print(f"  输出  : {out}")
    if removed:
        print(f"  清理  : 已移除过期用例 {len(removed)} 条（{', '.join(removed[:8])}）")
    for c in cases:
        print(f"    · {c['case_id']} {c['case_name']}")
    print()
    print("  [下一步]")
    print(f"    · 多份（≥ {MIN_CASES_FOR_ORCHESTRATION}）：直接用 plan --from-platform 编排（不需要先 fetch）")
    print("    · 单份：交给 ai-ui-autotest-engine 单份执行，用例目录为:")
    print(f"        {out}")
    print()
    return 0


# ─── 入口 ───────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(description="多 Agent 编排层：拆分 + 调度编排（plan）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="按用例源（平台 / 本地）拆分为待跑队列（滚动补位派发）")
    p.add_argument("--from-platform", default="",
                   help="平台需求 id 或需求名（服务端只导出审核通过用例）；与 --local-cases 互斥")
    p.add_argument("--local-cases", default="", dest="local_cases",
                   help="本地用例根目录（一用例一 steps.json，case_id=目录名）；与 --from-platform 互斥")
    p.add_argument("--skip-review", action="store_true", dest="skip_review",
                   help="本地用例未自带 approved 时，显式声明跳过平台审核（写入 manifest.review_bypass 供审计）")
    p.add_argument("--max-cases", type=int, default=DEFAULT_MAX_CASES,
                   help=f"每个子 Agent 的用例上限（默认 {DEFAULT_MAX_CASES}）")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help=f"同时在跑的子 Agent 上限（默认 {DEFAULT_CONCURRENCY}）")
    p.add_argument("--env", default="", help="共享环境信息 JSON（所有子 Agent 共享）")
    p.add_argument("--env-file", default="", help="共享环境信息 JSON 文件")
    p.add_argument("--run-type", default="",
                   choices=("regression", "feature", "adhoc"),
                   help="运行类型（缺省读 AI_UITEST_RUN_TYPE，再缺省 adhoc）")
    p.add_argument("--task", default="", help="任务 id（默认自动生成）")
    p.add_argument("--report-id", default="", dest="report_id",
                   help="复用已有的共享报告 id（缺省自动生成）")
    p.add_argument("--report-title", default="", dest="report_title",
                   help="共享报告标题（缺省用需求名）")
    p.add_argument("--no-report", action="store_true", dest="no_report",
                   help="不预置报告行（仍会生成并下发共享 report_id；首个 Case 追加时自动建行）")

    f = sub.add_parser("fetch", help="从平台取已通过用例 → 落成本地用例目录（不编排）")
    f.add_argument("--from-platform", required=True, help="平台需求 id 或需求名")
    f.add_argument("--out", default="",
                   help="输出目录（缺省 $AI_UITEST_HOME/cases/platform/<需求>/，可重复执行刷新）")

    r = sub.add_parser(
        "review",
        help="审核门禁：输出审核链接与审核态（0=全部通过 3=部分通过需确认 2=零通过阻断）",
    )
    r.add_argument("--from-platform", required=True, help="平台需求 id 或需求名")

    c = sub.add_parser("report-close", help="全部子 Agent 结束后收尾共享报告（回写 duration）")
    c.add_argument("--task", required=True, help="plan 输出的 task_id")
    c.add_argument("--report-id", default="", dest="report_id", help="manifest 缺失时手传报告 id")
    c.add_argument("--duration-ms", type=int, default=None, dest="duration_ms",
                   help="报告时长（缺省 = 从 plan 开始到现在）")

    return parser


def main():
    args = build_parser().parse_args()
    if args.cmd == "fetch":
        sys.exit(cmd_fetch(args))
    if args.cmd == "review":
        sys.exit(cmd_review(args))
    if args.cmd == "report-close":
        sys.exit(cmd_report_close(args))
    sys.exit(cmd_plan(args))


if __name__ == "__main__":
    main()
