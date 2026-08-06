#!/usr/bin/env python3
"""
美境设计师 V3 轮询结果脚本（poll + report）

用法: python3 poll.py <sessionId> <assistantMessageId> [--video]

职责: 按 assistantMessageId 轮询 history 接口 + 增量输出 JSON Lines + 终态后 report

凭证由脚本内部 `meigen status --json` 获取（FR-022），不作为命令行参数流经宿主 agent。

输出: stdout JSON Lines（每行一个 JSON 对象，按 _action 分发；与 generate.py 协议统一）。
      进度信息（等待创作/Token 重新认证等）也以 _action=display 的 JSON Line 输出，
      stderr 不再有进度日志。宿主 agent 流式逐行读取，按 _action 分发处理。
终止条件（分场景）:
  - 生图/对话场景: message status 为终态（DONE/FAILED/ABORTED）
  - 视频场景: 检测到首个 Video block status=RUNNING 即终态（视频还在生成，
    输出含 web 链接的 wait_video 让用户去 web 端自查，不等待视频完成）
"""

from __future__ import annotations

import sys
import json
import os
import time
import shutil
import subprocess

from common import AuthError, fail, get_access_token, get_mis_id, refresh_token, request


# ─── 常量 ────────────────────────────────────────────────────────

POLL_INTERVAL_SECONDS = 3
MAX_POLL_DURATION_IMAGE_SECONDS = 600  # 10 分钟（生图/对话场景）
MAX_POLL_DURATION_VIDEO_SECONDS = 600  # 10 分钟（视频场景，与生图一致；检测到 Video RUNNING 即终态退出）

# 消息状态
STATUS_STREAMING = 0
STATUS_DONE = 1
STATUS_ABORTED = 2
STATUS_FAILED = 3
STATUS_QUEUING = 4

ACTIVE_STATUSES = {STATUS_STREAMING, STATUS_QUEUING}
TERMINAL_STATUSES = {STATUS_DONE, STATUS_ABORTED, STATUS_FAILED}

# 文件路径工具
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)


# ─── CLI 参数解析 ───────────────────────────────────────────────────

def _parse_args(argv: list[str]) -> dict:
    """解析命令行参数。"""
    positional: list[str] = []
    is_video: bool = False

    i = 0
    while i < len(argv):
        if argv[i] == "--video":
            is_video = True
            i += 1
        else:
            positional.append(argv[i])
            i += 1

    if len(positional) < 2:
        print(
            "用法: python3 poll.py <sessionId> <assistantMessageId> [--video]",
            file=sys.stderr,
        )
        sys.exit(1)

    return {
        "session_id": int(positional[0]),
        "assistant_message_id": int(positional[1]),
        "is_video": is_video,
    }


# ─── JSON Lines 输出 ─────────────────────────────────────────────────

def _output_json_line(obj: dict) -> None:
    """输出一行 JSON 到 stdout。"""
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def _progress(content: str) -> None:
    """输出进度 JSON Line（_action=display），供宿主 agent 实时透传给用户。

    文案用用户视角，不暴露轮询/history/token 等实现细节。
    """
    _output_json_line({"type": "progress", "_action": "display", "content": content})


# ─── Block 解析与 JSON Lines 格式化 ──────────────────────────────────

def _format_block(block: dict, message_id: int, block_index: int, session_id: int, is_update: bool = False) -> dict | None:
    """解析一个 RenderBlock，返回 JSON Lines 对象。

    透传 RenderBlock 的原始 type 字段，不做类型名转换。
    每个输出包含 `_action` 语义化字段（FR-026），为宿主 agent 提供处理提示。
    更新的 block 附带 blockIndex 标识哪个 block 更新了（不使用 updated 标记，
    因为大多数宿主 agent 环境无法替换已发出的消息，block 更新作为新增输出）。

    Args:
        is_update: True 表示这是一个已输出过的 block 的后续更新，需要附带 blockIndex

    Returns:
        dict to output as JSON Line, or None if block should be skipped
    """
    block_type = block.get("type", "")
    base: dict = {
        "type": block_type,
        "messageId": message_id,
    }

    # 更新的 block 附带 blockIndex 让宿主 agent 知道是哪个 block 更新了
    if is_update:
        base["blockIndex"] = block_index

    if block_type == "Text":
        content = block.get("content", "")
        if not content:
            return None
        return {**base, "_action": "display", "content": content, "html": block.get("html", "")}

    if block_type == "Image":
        url = block.get("url", "")
        status = block.get("status", "")
        # 独立 Image: FINISH → show_images, 否则 display（展示状态信息）
        action = "show_images" if status == "FINISH" and url else "display"
        return {
            **base,
            "_action": action,
            "url": url,
            "status": status,
            "prompt": block.get("prompt", ""),
            "model": block.get("model", ""),
            "size": block.get("size", ""),
        }

    if block_type == "ImageList":
        images: list[dict] = []
        for img in block.get("content", []):
            if img.get("type") == "Image":
                images.append({
                    "type": "Image",
                    "url": img.get("url", ""),
                    "status": img.get("status", ""),
                    "prompt": img.get("prompt", ""),
                    "model": img.get("model", ""),
                })
        list_status = block.get("status", "")
        # ImageList: 有 FINISH 的图 → show_images, 否则 display（更新时保持语义，blockIndex 在 base 中标识）
        has_finish = any(img.get("status") == "FINISH" for img in images)
        action = "show_images" if has_finish else "display"
        return {
            **base,
            "_action": action,
            "title": block.get("title", ""),
            "content": images,
            "status": list_status,
        }

    if block_type == "Video":
        video_url = block.get("url", "")
        video_status = block.get("status", "")
        # 视频场景：检测到 Video RUNNING 即终态（FR-010/FR-027）。
        # wait_video 注入 web 链接（与 brand 动态 URL 同源），让用户去 web 端自查，
        # poll.py 输出后即退出，不等待视频完成、不追踪 RUNNING→FINISH 变化。
        web_url = f"https://aidesign.meituan.com/creativeAssistant/{session_id}"
        if video_status == "RUNNING" and not video_url:
            action = "wait_video"
            # url 字段放 web 链接，供宿主 agent 告知用户前往查看
            result_url = web_url
        elif video_status == "FINISH" and video_url:
            # 视频场景理论不会到达（RUNNING 即终态退出），防御性降级为 display
            action = "display"
            result_url = video_url
        else:
            action = "display"
            result_url = video_url
        # 视频场景不追踪状态更新（FR-025：检测到 RUNNING 即终态退出，无 RUNNING→FINISH 更新），
        # 故不处理 is_update 分支；blockIndex 已在 base 中附带（若传入）
        video_result: dict = {
            **base,
            "_action": action,
            "url": result_url,
            "status": video_status,
            "taskId": block.get("taskId", ""),
            "prompt": block.get("prompt", ""),
            "model": block.get("model", ""),
            "preview": block.get("preview", ""),
            "duration": block.get("duration", 0),
            "ratio": block.get("ratio", ""),
            "resolution": block.get("resolution", ""),
        }
        return video_result

    if block_type == "Card":
        # Card 类型丢弃不处理（子 block 独立出现，直接跳过）
        return None

    if block_type == "TextQuestion":
        options: list[dict] = []
        status = block.get("status", "PENDING")
        for sub in block.get("content", []):
            if sub.get("type") == "TextQuestionList":
                for item in sub.get("items", []):
                    options.append({
                        "type": "TextQuestionListItem",
                        "index": item.get("index", 0),
                        "title": item.get("title", ""),
                        "prompt": item.get("prompt", ""),
                    })
        action = "ask_user" if status == "PENDING" else "display"
        return {
            **base,
            "_action": action,
            "title": block.get("title", ""),
            "content": options,
            "status": status,
        }

    if block_type == "ImageQuestion":
        image_options: list[dict] = []
        status = "PENDING"
        for sub in block.get("content", []):
            if sub.get("type") == "ImageQuestionGrid":
                for item in sub.get("items", []):
                    image_options.append({
                        "type": "ImageQuestionGridItem",
                        "index": item.get("index", 0),
                        "url": item.get("url", ""),
                        "prompt": item.get("prompt", ""),
                    })
                if sub.get("status"):
                    status = sub.get("status", status)
        action = "ask_user" if status == "PENDING" else "display"
        return {
            **base,
            "_action": action,
            "content": image_options,
            "status": status,
        }

    if block_type == "Tool":
        # Tool 类型丢弃不处理（V3 通道永远不产出，防御性跳过）
        return None

    if block_type == "ArticleList":
        # ArticleList 类型丢弃不处理（搜索参考是 agent 中间过程，skill 场景下用户关注生成结果）
        return None

    # 未知 block 类型，简单透传
    return {**base, "_action": "display", "content": json.dumps(block, ensure_ascii=False)}


# ─── 增量对比 ──────────────────────────────────────────────────────

def _block_identity(block: dict) -> str:
    """生成 block 的唯一标识，用于判断是否为同一个 block。

    使用 (type, 关键字段) 作为标识，而非内容哈希。
    同一个 block 的内容可以变化（如 ImageList status RUNNING→FINISH），
    但标识不变，表示是"同一个 block 的更新"。
    """
    b_type = block.get("type", "")
    if b_type == "Text":
        return f"Text:{block.get('content', '')[:100]}"
    if b_type == "Image":
        return f"Image:{block.get('url', '')}"
    if b_type == "ImageList":
        return f"ImageList:{block.get('title', '')}"
    if b_type == "Video":
        # Video 用 taskId 做标识（status/url 会变，但 taskId 不变）
        return f"Video:{block.get('taskId', '')}"
    if b_type == "TextQuestion":
        return f"TextQuestion:{block.get('title', '')}"
    if b_type == "ImageQuestion":
        # 用子项 URL 列表做标识（内容相同则标识相同）
        urls: list[str] = []
        for sub in block.get("content", []):
            if sub.get("type") == "ImageQuestionGrid":
                for item in sub.get("items", []):
                    urls.append(item.get("url", ""))
        return f"ImageQuestion:{'|'.join(urls)}"
    if b_type == "Tool":
        # Tool 类型已丢弃，但仍需标识用于增量对比
        return f"Tool:{block.get('content', '')[:100]}"
    if b_type == "ArticleList":
        # ArticleList 类型已丢弃，但仍需标识用于增量对比
        return f"ArticleList:{block.get('title', '')}"
    # fallback: 用关键字段拼接做标识，避免 id() 的非确定性问题
    key_fields = sorted(f"{k}={v}" for k, v in block.items() if k != "type")
    return f"{b_type}:{'|'.join(key_fields[:5])}"


def _block_has_changed(prev_block: dict, curr_block: dict) -> bool:
    """判断 block 是否有关键字段变化，需要重新输出。"""
    b_type = curr_block.get("type", "")

    if b_type == "Video":
        # Video: status 或 url 变化即视为更新
        return (
            prev_block.get("status") != curr_block.get("status")
            or prev_block.get("url") != curr_block.get("url")
        )

    if b_type == "ImageList":
        # ImageList: status 变化或内部 Image 列表变化
        return prev_block.get("status") != curr_block.get("status")

    if b_type == "Image":
        return prev_block.get("status") != curr_block.get("status")

    if b_type in ("TextQuestion", "ImageQuestion"):
        return prev_block.get("status") != curr_block.get("status")

    # 其他类型默认不变（不重复输出）
    return False


def _diff_blocks(
    prev_snapshot: list[dict] | None,
    curr_blocks: list[dict],
    message_id: int,
    session_id: int,
) -> list[dict]:
    """对比前后 blocks 快照，返回增量输出列表。

    策略:
    - 首次（prev_snapshot=None）: 输出所有 blocks
    - 新增 block（index 超出上次快照长度）: 完整输出
    - 已有 block 关键字段变化: 重新输出完整内容，附带 blockIndex（作为新增输出，不替换旧消息）
    - Card / Tool / ArticleList 等丢弃类型: 统一由 _format_block 返回 None 过滤
    """
    output: list[dict] = []

    if prev_snapshot is None:
        # 首次: 完整输出所有 blocks
        for idx, block in enumerate(curr_blocks):
            formatted = _format_block(block, message_id, idx, session_id)
            if formatted is not None:
                output.append(formatted)
        return output

    for idx, curr_block in enumerate(curr_blocks):
        if idx >= len(prev_snapshot):
            # 新增 block
            formatted = _format_block(curr_block, message_id, idx, session_id)
            if formatted is not None:
                output.append(formatted)
        else:
            prev_block = prev_snapshot[idx]
            # 同位置 block 是否变化
            curr_id = _block_identity(curr_block)
            prev_id = _block_identity(prev_block)

            if curr_id != prev_id:
                # 位置 idx 的 block 被替换了，作为新 block 输出
                formatted = _format_block(curr_block, message_id, idx, session_id)
                if formatted is not None:
                    output.append(formatted)
            elif _block_has_changed(prev_block, curr_block):
                # 同一个 block 但关键字段变化，附带 blockIndex 作为更新输出
                formatted = _format_block(curr_block, message_id, idx, session_id, is_update=True)
                if formatted is not None:
                    output.append(formatted)

    return output


# ─── History 轮询 ──────────────────────────────────────────────────

def _poll_history(session_id: int, access_token: str) -> list[dict]:
    """请求 /history 接口，返回 resultList。"""
    resp = request(
        "GET",
        "/history",
        access_token,
        query={"sessionId": session_id, "pageNo": 1, "pageSize": 10},
    )
    data = resp.get("data", {})
    return data.get("resultList", [])


def _find_assistant_message(
    messages: list[dict],
    assistant_message_id: int,
) -> dict | None:
    """从 resultList 中找到指定 assistantMessageId 的消息。"""
    for msg in messages:
        if (
            msg.get("messageId") == assistant_message_id
            and msg.get("role") == "assistant"
        ):
            return msg
    return None


def _has_running_video(blocks: list[dict]) -> bool:
    """检查 blocks 中是否有 status=RUNNING 的 Video block。"""
    for block in blocks:
        if block.get("type") == "Video" and block.get("status") == "RUNNING":
            return True
    return False


# ─── Meigen Report 上报 ──────────────────────────────────────────────

def _read_skill_meta() -> tuple[str | None, str | None]:
    """读取 SKILL.md 中的 skill_id 和 version。"""
    skill_md = os.path.join(_SKILL_DIR, "SKILL.md")
    sid, ver = None, None
    in_frontmatter = False
    try:
        with open(skill_md) as f:
            for line in f:
                line = line.strip()
                if line == "---":
                    if in_frontmatter:
                        # 第二个 --- ，frontmatter 结束
                        break
                    in_frontmatter = True
                    continue
                if not in_frontmatter:
                    continue
                if line.startswith("skillhub.skill_id:"):
                    sid = line.split(":", 1)[1].strip().strip('"')
                elif line.startswith("skillhub.version:"):
                    ver = line.split(":", 1)[1].strip().strip('"')
                # 两个字段都找到后提前退出
                if sid is not None and ver is not None:
                    break
    except (OSError, IOError):
        pass
    return sid, ver


def _report(
    session_id: int,
    status: int,
    duration_ms: int,
) -> None:
    """异步调用 meigen report 上报使用数据，不阻塞主流程。"""
    cli = shutil.which("meigen")
    if not cli:
        return

    # mis_id 通过脚本内部 meigen status --json 获取（FR-022）
    try:
        resolved_mis_id = get_mis_id()
    except SystemExit:
        resolved_mis_id = None

    skill_id, skill_ver = _read_skill_meta()

    request_obj: dict = {"sessionId": session_id}

    cmd = [
        cli, "report",
        "--scene", "meigen-designer",
        "--skill-name", "meigen-designer",
        "--status", str(status),
        "--request", json.dumps(request_obj, ensure_ascii=False),
        "--task-duration", str(duration_ms // 1000),
    ]

    if skill_id:
        cmd += ["--skill-id", skill_id]
    if skill_ver:
        cmd += ["--skill-version", skill_ver]
    if session_id:
        cmd += ["--conversation-id", str(session_id)]
    if resolved_mis_id:
        cmd += ["--user-id", resolved_mis_id]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


# ─── 品牌水印 ────────────────────────────────────────────────────────

def _has_image_finish(blocks: list[dict]) -> bool:
    """判断 blocks 中是否存在已完成的图片产出（独立 Image 或 ImageList 内 Image FINISH）。"""
    for block in blocks:
        btype = block.get("type", "")
        if btype == "Image" and block.get("status") == "FINISH" and block.get("url"):
            return True
        if btype == "ImageList":
            for img in block.get("content", []):
                if img.get("type") == "Image" and img.get("status") == "FINISH" and img.get("url"):
                    return True
    return False


def _build_watermark(session_id: int, media: str) -> str:
    """构造品牌水印文案。url 为带 session_id 的美境主站链接，原样输出给用户。"""
    web_url = f"https://aidesign.meituan.com/creativeAssistant/{session_id}"
    return f"🎨 本{media}由 美境AI设计师 | [前往美境]({web_url})({web_url})"


# ─── 轮询主循环 ────────────────────────────────────────────────────

def poll(
    session_id: int,
    assistant_message_id: int,
    max_duration_seconds: int = MAX_POLL_DURATION_IMAGE_SECONDS,
    is_video: bool = False,
) -> int:
    """执行轮询主循环，直到终态或超时。

    凭证由脚本内部 `meigen status --json` 获取（FR-022），不作为参数传入。

    Args:
        max_duration_seconds: 最大轮询时限（秒），生图/对话与视频均默认 10 分钟
        is_video: 视频场景为 True。视频场景检测到首个 Video block status=RUNNING 即终态
            （输出含 web 链接的 wait_video 后退出，不等待视频完成）

    Returns:
        exit code: 0=轮询到终态, 1=失败/超时
    """
    # 获取 access_token（脚本内部 meigen status --json + 必要时 login）
    current_access_token = get_access_token()

    start_time_ms = int(time.time() * 1000)
    last_blocks_snapshot: list[dict] | None = None
    message_started = False

    _progress("⏳ 等待设计师创作中...")

    while True:
        elapsed = time.time() * 1000 - start_time_ms
        if elapsed > max_duration_seconds * 1000:
            _output_json_line({
                "type": "message_status",
                "_action": "notify_timeout",
                "messageId": assistant_message_id,
                "status": 3,
                "statusText": "TIMEOUT",
            })
            _report(session_id, 3, int(elapsed))
            return 0

        # 请求 history
        try:
            messages = _poll_history(session_id, current_access_token)
        except AuthError:
            # 401 → 刷新 token 重试
            _progress("🔄 Token 过期，重新认证...")
            new_token = refresh_token()
            if new_token:
                current_access_token = new_token
                try:
                    messages = _poll_history(session_id, current_access_token)
                except Exception:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue
            else:
                fail("Token 刷新失败，请运行 meigen login --force")
        except Exception:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        # 定位目标 assistant 消息
        msg = _find_assistant_message(messages, assistant_message_id)
        if msg is None:
            # 消息尚未出现，继续等待
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        message_id = msg["messageId"]
        status = msg.get("status")
        blocks = msg.get("content", {}).get("blocks", [])

        # 首次看到此消息
        if not message_started:
            message_started = True
            _output_json_line({
                "type": "message_start",
                "_action": "display",
                "messageId": message_id,
                "role": "assistant",
            })

        # 排队状态
        if status == STATUS_QUEUING:
            queue_pos = msg.get("queuePosition")
            _output_json_line({
                "type": "queue",
                "_action": "notify_queue",
                "messageId": message_id,
                "position": queue_pos,
            })

        # 增量对比 blocks
        incremental_output = _diff_blocks(last_blocks_snapshot, blocks, message_id, session_id)
        for item in incremental_output:
            _output_json_line(item)

        # 更新快照
        last_blocks_snapshot = blocks

        # 视频场景：检测到首个 Video RUNNING 即终态（FR-003/FR-027）
        # wait_video 已在上方增量输出中输出（含 web 链接），此处直接收尾
        if is_video and _has_running_video(blocks):
            # wait_video 已在上方增量输出中输出（含 web 链接），此处直接收尾
            duration_ms = int(time.time() * 1000) - start_time_ms
            _report(session_id, 2, duration_ms)
            return 0

        # 检查终止条件（生图/对话场景：message status 为终态即可）
        if status in TERMINAL_STATUSES:
            # 真正终止
            status_text = {1: "DONE", 2: "ABORTED", 3: "FAILED"}.get(status, "UNKNOWN")
            action = {
                STATUS_DONE: "notify_done",
                STATUS_FAILED: "notify_failed",
                STATUS_ABORTED: "notify_failed",
            }.get(status, "notify_failed")
            notify_line: dict = {
                "type": "message_status",
                "_action": action,
                "messageId": message_id,
                "status": status,
                "statusText": status_text,
            }
            # 生图任务成功且有图片产出时，水印随完成信号一起输出（纯文本对话不带）
            if status == STATUS_DONE and _has_image_finish(blocks):
                notify_line["watermark"] = _build_watermark(session_id, "图")
            _output_json_line(notify_line)

            # 上报
            duration_ms = int(time.time() * 1000) - start_time_ms
            report_status = 2 if status == STATUS_DONE else 3
            _report(session_id, report_status, duration_ms)

            return 0

        time.sleep(POLL_INTERVAL_SECONDS)


# ─── CLI 入口 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "用法: python3 poll.py <sessionId> <assistantMessageId> [--video]",
            file=sys.stderr,
        )
        sys.exit(1)

    args = _parse_args(sys.argv[1:])
    # 生图/对话与视频均 10 分钟（视频检测到 Video RUNNING 即终态退出，通常远小于 10 分钟）
    max_duration = (
        MAX_POLL_DURATION_VIDEO_SECONDS
        if args["is_video"]
        else MAX_POLL_DURATION_IMAGE_SECONDS
    )

    exit_code = poll(
        session_id=args["session_id"],
        assistant_message_id=args["assistant_message_id"],
        max_duration_seconds=max_duration,
        is_video=args["is_video"],
    )
    sys.exit(exit_code)
