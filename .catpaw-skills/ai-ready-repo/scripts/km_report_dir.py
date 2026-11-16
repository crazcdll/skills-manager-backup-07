#!/usr/bin/env python3
"""
学城报告归档目录管理（按月分卷）

背景：AI-Ready 评估报告此前全部平铺挂在同一个学城父目录下。学城对
「单个父文档下的子文档数量」存在硬上限（实测 500，超出后 createDocument
直接返回 code=708），一旦打满，**新报告将完全无法保存**。

本模块把归档结构从「一层平铺」改为「按月分目录 + 单月自动分卷」：

    <ROOT>  AI-Ready-Repo 打分报告归档
      ├── 【2026-05】AI-Ready-Repo 打分
      ├── 【2026-06】AI-Ready-Repo 打分
      ├── 【2026-06】AI-Ready-Repo 打分 · 卷2      ← 单月超 480 篇自动开卷
      └── 【2026-07】AI-Ready-Repo 打分

这样 ROOT 每年只新增 12~15 个子节点，永不触顶；单月目录也有分卷兜底。

子命令
------
  audit    只读盘点 ROOT 下的子文档：总数、月度分布、标题规范度、容量水位
  resolve  解析（不存在则创建）当月归档目录，输出其 contentId —— 供写报告前调用
  title    生成规范化的报告标题（同一天重复评估自动追加 #N 后缀）
  migrate  把 ROOT 下已平铺的历史报告按创建月份迁移进各月目录（默认 dry-run）

典型用法
--------
  # 写报告前：拿到当月目录 ID
  PARENT_ID=$(python3 km_report_dir.py resolve --quiet)

  # 生成规范标题（带综合得分）
  TITLE=$(python3 km_report_dir.py title --repo-name deal-shelf --score 78.5 --parent-id "$PARENT_ID")

  # 落库
  oa-skills citadel createDocument --title "$TITLE" --file report.md --parentId "$PARENT_ID"

  # 一次性历史治理（先看计划，确认后加 --execute）
  python3 km_report_dir.py migrate
  python3 km_report_dir.py migrate --execute
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 归档根目录（历史上直接往这里塞报告，现在只放各月子目录）
DEFAULT_ROOT_ID = "2756859002"

#: 学城单父目录子文档硬上限（实测：满 500 后 createDocument 返回 code=708）
KM_CHILD_HARD_LIMIT = 500

#: 单月目录写满多少篇就开新卷。留 20 篇安全垫，避免并发写入正好卡在边界上
MONTH_DIR_SOFT_LIMIT = 480

#: ROOT 下剩余容量低于此值时告警（ROOT 只放月目录，正常一年才 12 个）
ROOT_WARN_THRESHOLD = 30

#: 月度目录标题：【YYYY-MM】AI-Ready-Repo 打分  /  第 N 卷追加 " · 卷N"
MONTH_DIR_PREFIX = "AI-Ready-Repo 打分"
MONTH_DIR_RE = re.compile(
    r"^【(?P<ym>\d{4}-\d{2})】"
    + re.escape(MONTH_DIR_PREFIX)
    + r"(?:\s*·\s*卷(?P<vol>\d+))?\s*$"
)

#: 学城目录**按标题字典序**展示（已实测，非按创建时间），因此排序效果
#: 完全由标题开头的字段决定。两种排序形态：
#:
#:   repo（默认）：<repo> AI-Ready 评估报告 YYYY-MM-DD[ #N][ | <score>分]
#:                 → 同一仓库的历次评估相邻，方便看分数趋势
#:   date：         YYYY-MM-DD <repo> AI-Ready 评估报告[ #N][ | <score>分]
#:                 → 目录内按日期倒序聚合，方便看“最近评了哪些”
#:
#: 两种形态共用同一套字段，同一个正则均可解析，可混存于同一目录。
#: 分数固定在**末尾**且整段可选——保证：
#:   1. 已归档的无分数旧标题仍被识别为合规（向后兼容）
#:   2. 排序主键始终是开头字段，不被分数打乱
#:   3. 同日去重只看 repo + date，不受分数变化干扰

#: 分隔符：新格式用 `|`，旧格式用空格；正则两者都兼容
#: 用非捕获组 (?:...) 包裹，避免 `|` 被当作正则 or 运算符
_SEP = r"(?:\s*\|\s*|\s+)"

#: 形态 A：仓库名在前
_TITLE_RE_REPO_FIRST = re.compile(
    r"^(?P<repo>.+?)" + _SEP + r"AI-Ready\s+评估报告" + _SEP +
    r"(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:" + _SEP + r"#(?P<seq>\d+))?"
    r"(?:" + _SEP + r"·?\s*(?P<score>\d+(?:\.\d+)?)\s*分)?"
    r"\s*$"
)

#: 形态 B：日期在前
_TITLE_RE_DATE_FIRST = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})" + _SEP +
    r"(?P<repo>.+?)" + _SEP + r"AI-Ready\s+评估报告"
    r"(?:" + _SEP + r"#(?P<seq>\d+))?"
    r"(?:" + _SEP + r"·?\s*(?P<score>\d+(?:\.\d+)?)\s*分)?"
    r"\s*$"
)

#: 标题排序形态："date"（默认）或 "repo"，可用环境变量覆盖
TITLE_ORDER = os.environ.get("AI_READY_TITLE_ORDER", "date").strip().lower()


def match_report_title(title: str):
    """解析报告标题，两种形态都认。不匹配返回 None。"""
    return _TITLE_RE_REPO_FIRST.match(title) or _TITLE_RE_DATE_FIRST.match(title)


#: 向后兼容的别名（旧代码/外部调用可能引用）
REPORT_TITLE_RE = _TITLE_RE_REPO_FIRST

CLI_TIMEOUT = 120


class KmError(RuntimeError):
    """citadel CLI 调用失败 / 输出无法解析。"""


# ---------------------------------------------------------------------------
# citadel CLI 封装
# ---------------------------------------------------------------------------
def _resolve_cli() -> list[str]:
    """
    定位 oa-skills 可执行文件。

    优先 PATH；兜底扫常见 npm global 安装位置（部分环境 PATH 未注入 npm prefix）。
    """
    override = os.environ.get("OA_SKILLS_BIN")
    if override:
        return [override, "citadel"]
    found = shutil.which("oa-skills")
    if found:
        return [found, "citadel"]
    for cand in (
        os.path.expanduser("~/.npm-global/bin/oa-skills"),
        "/usr/local/bin/oa-skills",
        "/opt/homebrew/bin/oa-skills",
    ):
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return [cand, "citadel"]
    raise KmError(
        "未找到 oa-skills（citadel skill）。请先安装：\n"
        "  npm install -g @it/oa-skills --registry=http://r.npm.sankuai.com"
    )


#: 可重试的瞬时故障特征（SSO token 交换抖动、网络超时等）。
#: 批量迁移会发出数百次 CLI 调用，不重试的话一次抖动就会中断整批。
_TRANSIENT_PAT = re.compile(
    r"token_exchange_command|获取 token 失败|ETIMEDOUT|ECONNRESET|ECONNREFUSED|"
    r"socket hang up|EAI_AGAIN|执行超时|timeout|502|503|504",
    re.I,
)


def _run_cli(
    args: list[str], *, timeout: int = CLI_TIMEOUT, retries: int = 3
) -> str:
    """
    调 citadel CLI。瞬时故障（token 抖动 / 网络超时）自动退避重试。

    非瞬时故障（如 code=708 目录已满、无权限）立即抛出，不浪费重试次数。
    """
    cmd = _resolve_cli() + args
    last = ""
    for attempt in range(1, retries + 1):
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=False
            )
            if proc.returncode == 0:
                # citadel 的写操作（createDocument 等）把结果打到 stderr，
                # 读操作（--raw JSON）打到 stdout，这里合并返回交由调用方解析
                return (proc.stdout or "") + (proc.stderr or "")
            last = (proc.stderr or proc.stdout or "").strip()[-400:]
            err = KmError(f"citadel 调用失败（exit={proc.returncode}）: {last}")
        except subprocess.TimeoutExpired:
            last = f"调用超时（{timeout}s）"
            err = KmError(f"citadel {last}: {' '.join(args[:3])}")
        except FileNotFoundError as e:
            raise KmError(f"citadel CLI 不可执行: {e}")

        if attempt >= retries or not _TRANSIENT_PAT.search(last):
            raise err
        backoff = 2 ** (attempt - 1) * 3  # 3s, 6s
        _log(f"  ⏳ 瞬时故障，{backoff}s 后重试（{attempt}/{retries - 1}）：{last[:90]}")
        time.sleep(backoff)
    raise KmError(f"citadel 调用失败: {last}")


def _extract_json(text: str) -> dict:
    """CLI 的 --raw 输出可能混入进度行，这里抠出第一个完整 JSON 对象。"""
    start = text.find("{")
    if start < 0:
        raise KmError(f"输出中未找到 JSON: {text.strip()[:200]}")
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as e:
                    raise KmError(f"JSON 解析失败: {e}")
    raise KmError("输出中的 JSON 不完整（括号未闭合）")


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
@dataclass
class Child:
    content_id: str
    title: str
    create_time: int  # epoch millis
    is_child_exist: bool = False

    @property
    def created(self) -> _dt.datetime:
        return _dt.datetime.fromtimestamp(self.create_time / 1000)

    @property
    def ym(self) -> str:
        return self.created.strftime("%Y-%m")


@dataclass
class MonthDir:
    """一个月度归档目录（可能有多卷）。"""

    ym: str
    volume: int
    content_id: str
    child_count: int = 0
    #: True 表示该目录暂挂在个人空间根（因 ROOT 已满而无法直接创建），
    #: 待迁移腾出空位后再 moveDocument 挂回 ROOT
    detached: bool = False

    @property
    def title(self) -> str:
        return month_dir_title(self.ym, self.volume)

    @property
    def has_room(self) -> bool:
        return self.child_count < MONTH_DIR_SOFT_LIMIT


@dataclass
class RootView:
    """ROOT 目录的一次快照。"""

    root_id: str
    children: list[Child] = field(default_factory=list)
    month_dirs: list[MonthDir] = field(default_factory=list)
    #: ROOT 下直挂的、本该归入月目录的报告（历史遗留）
    stray_reports: list[Child] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.children)

    @property
    def remaining(self) -> int:
        return max(0, KM_CHILD_HARD_LIMIT - self.total)

    @property
    def is_full(self) -> bool:
        return self.total >= KM_CHILD_HARD_LIMIT


def month_dir_title(ym: str, volume: int = 1) -> str:
    base = f"【{ym}】{MONTH_DIR_PREFIX}"
    return base if volume <= 1 else f"{base} · 卷{volume}"


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------
def fetch_children(content_id: str) -> list[Child]:
    raw = _run_cli(["getChildContent", "--contentId", str(content_id), "--raw"])
    data = _extract_json(raw)
    out: list[Child] = []
    for item in data.get("children") or []:
        cid = str(item.get("contentId") or "").strip()
        if not cid:
            continue
        out.append(
            Child(
                content_id=cid,
                title=(item.get("title") or "").strip(),
                create_time=int(item.get("createTime") or 0),
                is_child_exist=bool(item.get("isChildExist")),
            )
        )
    return out


def load_root(root_id: str, *, count_month_children: bool = False) -> RootView:
    """
    读 ROOT 一层，识别哪些子节点是「月度目录」、哪些是历史遗留的散报告。

    count_month_children=True 时会为每个月目录再发一次请求统计其子文档数
    （用于分卷判断），成本较高，仅在 resolve/audit 需要时开启。
    """
    children = fetch_children(root_id)
    view = RootView(root_id=root_id, children=children)

    for ch in children:
        m = MONTH_DIR_RE.match(ch.title)
        if m:
            view.month_dirs.append(
                MonthDir(
                    ym=m.group("ym"),
                    volume=int(m.group("vol") or 1),
                    content_id=ch.content_id,
                )
            )
        else:
            view.stray_reports.append(ch)

    view.month_dirs.sort(key=lambda d: (d.ym, d.volume))

    if count_month_children:
        for d in view.month_dirs:
            try:
                d.child_count = len(fetch_children(d.content_id))
            except KmError:
                # 单个目录读失败不应阻断整体流程，按满处理触发开新卷更安全
                d.child_count = MONTH_DIR_SOFT_LIMIT
    return view


# ---------------------------------------------------------------------------
# resolve：拿到「当月该写哪个目录」
# ---------------------------------------------------------------------------
def resolve_month_dir(
    root_id: str = DEFAULT_ROOT_ID,
    ym: str | None = None,
    *,
    create: bool = True,
    verbose: bool = True,
    allow_detached: bool = False,
    view: RootView | None = None,
) -> MonthDir:
    """
    返回 ym 月份当前可写的归档目录；不存在且 create=True 时创建。

    分卷规则：同月已有目录按卷号升序，取第一个未满（<480）的；全满则开下一卷。

    allow_detached：ROOT 已满时是否允许把新目录先建在个人空间根（detached）。
      这是为了打破「ROOT 满 → 建不了月目录 → 没法迁移 → ROOT 一直满」的死锁：
      migrate 会先 detached 建目录、迁走文档腾出空位，最后再把目录挂回 ROOT。
    """
    ym = ym or _dt.date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", ym):
        raise KmError(f"月份格式应为 YYYY-MM，收到: {ym!r}")

    view = view if view is not None else load_root(root_id, count_month_children=True)
    same_month = [d for d in view.month_dirs if d.ym == ym]

    for d in same_month:
        if d.has_room:
            if verbose:
                _log(f"✅ 复用已有月度目录：{d.title}（{d.child_count} 篇）→ {d.content_id}")
            return d

    next_vol = (max((d.volume for d in same_month), default=0)) + 1
    title = month_dir_title(ym, next_vol)

    if not create:
        raise KmError(f"月度目录不存在且未开启创建：{title}")

    detached = False
    if view.is_full:
        if not allow_detached:
            raise KmError(
                f"归档根目录 {root_id} 已达学城子文档上限（{view.total}/{KM_CHILD_HARD_LIMIT}），"
                f"无法创建 {title}。\n"
                f"根目录下仍有 {len(view.stray_reports)} 篇历史报告平铺占位，"
                f"请先执行：python3 km_report_dir.py migrate --execute"
            )
        detached = True

    if verbose:
        _log(f"📁 创建月度目录：{title}" + ("（根目录已满，暂挂个人空间）" if detached else ""))
    new_id = _create_month_dir(root_id if not detached else None, ym, next_vol)
    if verbose:
        _log(f"✅ 已创建 → {new_id}")

    created = MonthDir(
        ym=ym, volume=next_vol, content_id=new_id, child_count=0, detached=detached
    )
    view.month_dirs.append(created)
    view.month_dirs.sort(key=lambda d: (d.ym, d.volume))
    if not detached:
        # 占用了 ROOT 一个位置，让同一次 migrate 内的后续判断看到最新水位
        view.children.append(
            Child(content_id=new_id, title=created.title, create_time=0)
        )
    return created


def attach_month_dir(root_id: str, d: MonthDir) -> None:
    """把 detached 的月度目录挂回 ROOT（迁移腾出空位后调用）。"""
    _run_cli(
        ["moveDocument", "--contentId", d.content_id, "--newParentId", str(root_id)]
    )
    d.detached = False


def discover_detached_dirs(mis: str | None = None) -> list[MonthDir]:
    """
    扫个人空间根，找出此前引导阶段遗留（未挂回 ROOT）的月度目录。

    使 migrate 可安全重跑：上一轮中途失败留下的空目录会被复用，
    而不是每跑一次就新建一批同名目录。
    """
    mis = mis or os.environ.get("SSO_USER_ID") or os.environ.get("USER") or ""
    if not mis:
        return []
    try:
        space = _extract_json(_run_cli(["getSpaceIdByMis", "--targetMis", mis]))
        space_id = str(space.get("spaceId") or "").strip()
        if not space_id:
            return []
        data = _extract_json(
            _run_cli(["getSpaceRootDocs", "--spaceId", space_id, "--raw"])
        )
    except KmError:
        return []

    found: list[MonthDir] = []
    for it in data.get("items") or []:
        m = MONTH_DIR_RE.match((it.get("title") or "").strip())
        cid = str(it.get("contentId") or it.get("id") or "").strip()
        if not m or not cid:
            continue
        d = MonthDir(
            ym=m.group("ym"),
            volume=int(m.group("vol") or 1),
            content_id=cid,
            detached=True,
        )
        try:
            d.child_count = len(fetch_children(cid))
        except KmError:
            d.child_count = 0
        found.append(d)
    return found


def _create_month_dir(root_id: str | None, ym: str, volume: int) -> str:
    title = month_dir_title(ym, volume)
    body = (
        f"# {title}\n\n"
        f"本目录归档 {ym} 期间产出的 AI-Ready 仓库评估报告。\n\n"
        f"- 报告标题规范：`YYYY-MM-DD | <仓库名> | AI-Ready 评估报告`\n"
        f"  （同一仓库同日多次评估追加 ` | #2`；综合分追加 ` | 78.5分`）\n"
        f"- 单目录容量上限 {KM_CHILD_HARD_LIMIT} 篇，写满 {MONTH_DIR_SOFT_LIMIT} 篇后自动开「· 卷2」\n"
        f"- 由 skill `ai-ready-repo` 的 `scripts/km_report_dir.py` 自动维护，请勿手工改名\n"
    )
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(body)
        tmp = fh.name
    try:
        cli_args = ["createDocument", "--title", title, "--file", tmp]
        # root_id=None → 不传 --parentId，落到个人空间根（detached 引导场景）
        if root_id:
            cli_args += ["--parentId", str(root_id)]
        out = _run_cli(cli_args)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    cid = _parse_created_id(out)
    if not cid:
        raise KmError(f"创建月度目录成功但未解析出 contentId，原始输出：\n{out[-500:]}")
    return cid


def _parse_created_id(out: str) -> str | None:
    """从 createDocument 输出中抠出新文档 ID（兼容 JSON / 文本两种形态）。"""
    try:
        data = _extract_json(out)
        for key in ("contentId", "id", "pageId"):
            if data.get(key):
                return str(data[key])
        inner = data.get("data")
        if isinstance(inner, dict):
            for key in ("contentId", "id", "pageId"):
                if inner.get(key):
                    return str(inner[key])
    except KmError:
        pass
    m = re.search(r"collabpage/(\d+)", out)
    if m:
        return m.group(1)
    m = re.search(r"(?:contentId|文档ID|ID)[^\d]{0,8}(\d{6,})", out)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# title：统一标题 + 同日去重
# ---------------------------------------------------------------------------
def _fmt_score(score: float | str) -> str:
    """
    分数格式化：最多一位小数，去掉无意义的尾零。

      78    → "78"      78.0  → "78"
      78.5  → "78.5"    71.46 → "71.5"
    """
    try:
        v = float(score)
    except (TypeError, ValueError):
        raise KmError(f"分数应为 0–100 的数字，收到: {score!r}")
    if not 0 <= v <= 100:
        raise KmError(f"分数应在 0–100 之间，收到: {v}")
    return f"{v:.1f}".rstrip("0").rstrip(".") or "0"


def build_report_title(
    repo_name: str,
    *,
    score: float | str | None = None,
    parent_id: str | None = None,
    date: str | None = None,
    siblings: list[Child] | None = None,
    order: str | None = None,
) -> str:
    """
    生成规范标题。学城目录按标题字典序展示，故 order 决定目录怎么排：

      order="date"（默认） → `2026-07-31 | deal-shelf | AI-Ready 评估报告 | 78.5分`
                          目录内按日期聚合，便于看"最近评了哪些"
      order="repo"        → `deal-shelf | AI-Ready 评估报告 | 2026-07-31 | 78.5分`
                          同一仓库历次评估相邻，便于看分数趋势

    两种形态字段一致、均可被 `match_report_title` 解析，可混存于同一目录，
    切换 order 不需要改名历史文档。

    - 传入 score 则末尾追加 ` | 78.5分`，便于在目录列表直接横向对比得分
    - 若同一仓库同日在该目录下已有报告，追加 ` | #2` / ` | #3`

    去重只比对 repo + date，**不看分数、不看排序形态**：同一仓库同一天
    重跑一次，哪怕分数变了也属于第 2 次评估，应拿到 `#2` 而非另起同名文档。
    """
    order = (order or TITLE_ORDER).strip().lower()
    if order not in ("repo", "date"):
        raise KmError(f"order 只支持 'repo' 或 'date'，收到: {order!r}")

    repo_name = _normalize_repo_name(repo_name)
    date = date or _dt.date.today().strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise KmError(f"日期格式应为 YYYY-MM-DD，收到: {date!r}")

    score_str = _fmt_score(score) if score is not None and score != "" else None

    def _compose(seq: int | None) -> str:
        parts = [date, repo_name, "AI-Ready 评估报告"] if order == "date" \
            else [repo_name, "AI-Ready 评估报告", date]
        if seq:
            parts.append(f"#{seq}")
        if score_str:
            parts.append(f"{score_str}分")
        return " | ".join(parts)

    if siblings is None:
        if not parent_id:
            return _compose(None)
        try:
            siblings = fetch_children(parent_id)
        except KmError:
            return _compose(None)

    used: set[int] = set()
    for ch in siblings:
        m = match_report_title(ch.title)
        if not m:
            continue
        if _normalize_repo_name(m.group("repo")) != repo_name:
            continue
        if m.group("date") != date:
            continue
        used.add(int(m.group("seq") or 1))

    if not used:
        return _compose(None)
    seq = 2
    while seq in used:
        seq += 1
    return _compose(seq)


def _normalize_repo_name(name: str) -> str:
    """
    仓库名归一：去掉 git URL 外壳与 org 前缀，只留仓库名本体。

      ssh://git@git.sankuai.com/tuangou/deal-shelf.git → deal-shelf
      tuangou/deal-shelf                               → deal-shelf
      @game/com-floating-window-seed                   → @game/com-floating-window-seed（npm scope 保留）
    """
    name = (name or "").strip()
    if not name:
        raise KmError("仓库名为空")
    name = re.sub(r"^(?:ssh|https?)://", "", name)
    name = re.sub(r"^[^@/]+@", "", name)
    if name.endswith(".git"):
        name = name[:-4]
    # npm scope（@scope/pkg）整体保留，其余取最后一段
    if not name.startswith("@"):
        name = name.rstrip("/").split("/")[-1]
    return name.strip()


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------
def cmd_audit(args: argparse.Namespace) -> int:
    view = load_root(args.root_id, count_month_children=not args.fast)

    _log(f"归档根目录：https://km.sankuai.com/collabpage/{args.root_id}")
    _log(
        f"子节点总数：{view.total}/{KM_CHILD_HARD_LIMIT}"
        f"（剩余 {view.remaining}）"
    )
    if view.is_full:
        _log("🚨 根目录已打满，新文档创建会直接失败（code=708）")
    elif view.remaining < ROOT_WARN_THRESHOLD:
        _log(f"⚠️  根目录剩余容量不足 {ROOT_WARN_THRESHOLD}")

    _log(f"\n月度目录：{len(view.month_dirs)} 个")
    for d in view.month_dirs:
        cnt = "?" if args.fast else f"{d.child_count}"
        flag = "" if args.fast or d.has_room else "  ← 已满，将开新卷"
        _log(f"  {d.title:<44} {cnt:>4} 篇  {d.content_id}{flag}")

    _log(f"\n根目录下平铺的历史文档：{len(view.stray_reports)} 篇")
    if view.stray_reports:
        buckets: dict[str, int] = {}
        for ch in view.stray_reports:
            buckets[ch.ym] = buckets.get(ch.ym, 0) + 1
        for ym in sorted(buckets):
            _log(f"  {ym}: {buckets[ym]} 篇")

        # 两种排序形态都算合规，避免 date 形态标题被误判为不规范
        good = sum(1 for c in view.stray_reports if match_report_title(c.title))
        _log(
            f"\n标题规范度：{good}/{len(view.stray_reports)} 符合 "
            f"`<repo> AI-Ready 评估报告 YYYY-MM-DD[ #N][ | <score>分]`"
            f" 或其 date 形态"
        )
        bad = [c for c in view.stray_reports if not match_report_title(c.title)]
        for ch in bad[: args.show_bad]:
            _log(f"  ✗ [{ch.created:%Y-%m-%d}] {ch.title}")
        if len(bad) > args.show_bad:
            _log(f"  … 另有 {len(bad) - args.show_bad} 条不规范标题")
        _log("\n建议执行：python3 km_report_dir.py migrate  （先 dry-run 查看计划）")

    if args.json:
        print(
            json.dumps(
                {
                    "root_id": view.root_id,
                    "total": view.total,
                    "remaining": view.remaining,
                    "is_full": view.is_full,
                    "month_dirs": [
                        {
                            "ym": d.ym,
                            "volume": d.volume,
                            "content_id": d.content_id,
                            "child_count": d.child_count,
                        }
                        for d in view.month_dirs
                    ],
                    "stray_count": len(view.stray_reports),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------
def cmd_resolve(args: argparse.Namespace) -> int:
    d = resolve_month_dir(
        args.root_id, args.month, create=not args.no_create, verbose=not args.quiet
    )
    if args.json:
        print(
            json.dumps(
                {
                    "content_id": d.content_id,
                    "title": d.title,
                    "ym": d.ym,
                    "volume": d.volume,
                    "url": f"https://km.sankuai.com/collabpage/{d.content_id}",
                },
                ensure_ascii=False,
            )
        )
    else:
        print(d.content_id)
    return 0


# ---------------------------------------------------------------------------
# title
# ---------------------------------------------------------------------------
def cmd_title(args: argparse.Namespace) -> int:
    title = build_report_title(
        args.repo_name,
        score=args.score,
        parent_id=args.parent_id,
        date=args.date,
        order=args.order,
    )
    print(title)
    return 0


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------
def cmd_migrate(args: argparse.Namespace) -> int:
    view = load_root(args.root_id, count_month_children=True)
    strays = view.stray_reports

    if args.only_reports:
        strays = [c for c in strays if re.search(r"AI[- ]?Ready", c.title, re.I)]

    if not strays:
        _log("✅ 根目录下没有需要迁移的平铺文档")
        return 0

    plan: dict[str, list[Child]] = {}
    for ch in strays:
        plan.setdefault(ch.ym, []).append(ch)

    _log(
        f"{'执行' if args.execute else 'DRY-RUN'} 迁移计划："
        f"{len(strays)} 篇 → {len(plan)} 个月度目录\n"
    )
    for ym in sorted(plan):
        _log(f"  【{ym}】{len(plan[ym])} 篇")
        for ch in plan[ym][:3]:
            _log(f"      {ch.title[:64]}")
        if len(plan[ym]) > 3:
            _log(f"      … 另 {len(plan[ym]) - 3} 篇")

    if not args.execute:
        _log("\n以上为预演。确认无误后追加 --execute 实际执行。")
        return 0

    _log("")
    moved = failed = 0
    #: 因 ROOT 打满而暂挂个人空间的目录，迁移腾出空位后统一挂回
    pending_attach: list[MonthDir] = []

    # 纳管上一轮中途失败遗留在个人空间的月度目录，避免重复创建同名目录
    known = {(d.ym, d.volume) for d in view.month_dirs}
    for d in discover_detached_dirs():
        if (d.ym, d.volume) in known:
            continue
        _log(f"  ♻️  复用上轮遗留目录：{d.title}（{d.child_count} 篇）")
        view.month_dirs.append(d)
        pending_attach.append(d)
        known.add((d.ym, d.volume))
    view.month_dirs.sort(key=lambda x: (x.ym, x.volume))

    for ym in sorted(plan):
        try:
            # 复用同一份 view：让本轮已迁走的文档数实时反映到 ROOT 水位上，
            # 从而在腾出空位后能正常在 ROOT 下建目录，而不是继续 detached
            target = resolve_month_dir(
                args.root_id, ym, verbose=False, allow_detached=True, view=view
            )
        except KmError as e:
            _log(f"❌ 无法准备 {ym} 目录，跳过该月：{e}")
            failed += len(plan[ym])
            continue
        if target.detached and target not in pending_attach:
            pending_attach.append(target)

        for ch in plan[ym]:
            # 目标目录写满就滚到下一卷
            if target.child_count >= MONTH_DIR_SOFT_LIMIT:
                try:
                    target = resolve_month_dir(
                        args.root_id, ym, verbose=False, allow_detached=True, view=view
                    )
                except KmError as e:
                    _log(f"❌ {ym} 开新卷失败：{e}")
                    failed += 1
                    continue
                if target.detached and target not in pending_attach:
                    pending_attach.append(target)
            try:
                _run_cli(
                    [
                        "moveDocument",
                        "--contentId",
                        ch.content_id,
                        "--newParentId",
                        target.content_id,
                    ]
                )
                target.child_count += 1
                moved += 1
                # 该文档已不再占用 ROOT 的名额
                view.children = [c for c in view.children if c.content_id != ch.content_id]
                _log(f"  ✅ {ch.title[:56]} → 【{ym}】")
            except KmError as e:
                failed += 1
                _log(f"  ❌ {ch.title[:56]}：{e}")

    # 把引导期暂挂个人空间的月度目录挂回 ROOT
    for d in pending_attach:
        try:
            attach_month_dir(args.root_id, d)
            _log(f"  📎 {d.title} 已挂回归档根目录")
        except KmError as e:
            failed += 1
            _log(
                f"  ❌ {d.title}（{d.content_id}）挂回根目录失败：{e}\n"
                f"     该目录当前仍在个人空间，请手工 moveDocument 到 {args.root_id}"
            )

    _log(f"\n迁移完成：成功 {moved}，失败 {failed}")
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
def _log(msg: str) -> None:
    """所有人类可读输出走 stderr，stdout 只留纯数据供 $(...) 捕获。"""
    print(msg, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="AI-Ready 评估报告的学城归档目录管理（按月分卷）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--root-id",
        default=os.environ.get("AI_READY_KM_ROOT_ID", DEFAULT_ROOT_ID),
        help=f"归档根目录 contentId（默认 {DEFAULT_ROOT_ID}，可用 AI_READY_KM_ROOT_ID 覆盖）",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("audit", help="盘点根目录容量、月度分布与标题规范度")
    p.add_argument("--fast", action="store_true", help="跳过逐个月度目录计数（更快）")
    p.add_argument("--show-bad", type=int, default=10, help="展示多少条不规范标题")
    p.add_argument("--json", action="store_true", help="额外输出 JSON 摘要到 stdout")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("resolve", help="解析/创建当月归档目录，stdout 输出 contentId")
    p.add_argument("--month", help="目标月份 YYYY-MM，默认当月")
    p.add_argument("--no-create", action="store_true", help="不存在时报错而非创建")
    p.add_argument("--quiet", action="store_true", help="静默（只输出 contentId）")
    p.add_argument("--json", action="store_true", help="stdout 输出 JSON")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("title", help="生成规范化报告标题（含分数，同日自动去重）")
    p.add_argument("--repo-name", required=True, help="仓库名或 git URL")
    p.add_argument("--score", help="综合得分 0–100，传入则标题末尾追加 ` | 78.5分`")
    p.add_argument("--parent-id", help="目标月度目录 ID（用于同日重名检测）")
    p.add_argument("--date", help="报告日期 YYYY-MM-DD，默认今天")
    p.add_argument(
        "--order",
        choices=["repo", "date"],
        help="标题排序形态：date=日期在前（默认，目录内按日期聚合），"
        f"repo=仓库名在前（同仓库历次评估相邻）；可用 AI_READY_TITLE_ORDER 覆盖，"
        f"当前默认 {TITLE_ORDER}",
    )
    p.set_defaults(func=cmd_title)

    p = sub.add_parser("migrate", help="把根目录下平铺的历史报告迁入月度目录")
    p.add_argument("--execute", action="store_true", help="真正执行（默认 dry-run）")
    p.add_argument(
        "--only-reports",
        action="store_true",
        help="仅迁移标题含 AI-Ready 的文档，跳过无关文档",
    )
    p.set_defaults(func=cmd_migrate)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except KmError as e:
        _log(f"❌ {e}")
        return 1
    except KeyboardInterrupt:
        _log("已中断")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
