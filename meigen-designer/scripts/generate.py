#!/usr/bin/env python3
"""
美境设计师 V3 提交任务脚本（send only）

用法: python3 generate.py <prompt> [--file <url>]... [--model <name>] [--config <json>]
      python3 generate.py --abort <sessionId>

职责: 创建/复用会话 → 组装参数 → send → 输出 JSON Lines 后退出
不包含轮询逻辑（由 poll.py 负责）

prompt 组装由宿主 agent 完成（含原位 [@image:#N]/[@video:#N] 占位符 + 末尾引用行），
脚本原样透传，不再拼接占位符或构建 blocks。本地文件上传由 agent 调 upload-to-s3.py。

凭证由脚本内部 `meigen status --json` 获取（FR-022），不作为命令行参数流经宿主 agent。

输出: stdout JSON Lines（与 poll.py 协议统一，宿主 agent 流式逐行读取，按 _action 分发）：
      - 进度行: {"type":"progress","_action":"display","content":"..."}（实时透传给用户）
      - 提交成功终态: {"type":"submit_result","_action":"submitted","sessionId":int,"userMessageId":int,"assistantMessageId":int,"status":"submitted"}
      - 失败: {"status":"failed","_action":"failed","msg":"..."}（退出码 1，宿主 agent 读 msg 处理）
      stderr 仅保留人类排查用日志，不作为 agent 信息源。
"""

from __future__ import annotations

import sys
import json
import os
from typing import Any, NamedTuple

from common import AuthError, fail, get_access_token, refresh_token, request


# ─── 文件类型 ────────────────────────────────────────────────────

FILE_TYPE_MAP = {
    ".pdf": "pdf", ".xlsx": "excel", ".xls": "excel",
    ".csv": "excel", ".docx": "word", ".doc": "word",
}


def _file_ext_type(url: str) -> str | None:
    """根据扩展名返回 files 项的 type 字段（pdf/excel/word），无法识别返回 None。"""
    lower = url.lower().split("?")[0].split("#")[0]
    _, ext = os.path.splitext(lower)
    return FILE_TYPE_MAP.get(ext)


# ─── 文件路径工具 ──────────────────────────────────────────────────

_SESSION_ID_FILE = os.path.join(
    os.path.expanduser("~"), ".meigen-cli", "meigen-designer", "session_id"
)


# ─── JSON Lines 输出 ─────────────────────────────────────────────────

def _output_json_line(obj: dict) -> None:
    """输出一行 JSON 到 stdout（与 poll.py 协议统一）。

    generate.py 全程以 JSON Lines 输出：进度行（_action=display）、
    提交成功终态行（_action=submitted）、失败行（_action=failed，由 fail() 输出）。
    宿主 agent 流式逐行读取，按 _action 分发处理，进度实时可见。
    """
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def _progress(content: str) -> None:
    """输出进度 JSON Line（_action=display），供宿主 agent 实时透传给用户。"""
    _output_json_line({"type": "progress", "_action": "display", "content": content})


# ─── 会话管理 ────────────────────────────────────────────────────────

def _get_or_create_session(access_token: str) -> int:
    """获取或创建 V3 会话，返回 sessionId。

    如果本地已持久化 sessionId，直接读取。
    否则调用 /session/create 创建新会话并持久化。
    """
    if os.path.exists(_SESSION_ID_FILE):
        with open(_SESSION_ID_FILE) as f:
            sid_str = f.read().strip()
        if sid_str:
            sid = int(sid_str)
            _progress(f"🔗 复用现有会话: {sid}")
            return sid

    _progress("🆕 创建新会话...")
    resp = request("POST", "/session/create", access_token, body={})
    sid = resp.get("data")
    if not sid:
        fail(f"创建会话失败: {json.dumps(resp, ensure_ascii=False)}")

    os.makedirs(os.path.dirname(_SESSION_ID_FILE), exist_ok=True)
    with open(_SESSION_ID_FILE, "w") as f:
        f.write(str(sid))
    _progress(f"✅ 会话已创建: {sid}")
    return sid


def reset_session() -> None:
    """重置会话: 删除本地 sessionId 文件。"""
    _delete_session_file()
    _progress("🗑️ 会话已重置")


def _delete_session_file() -> None:
    """删除本地 sessionId 文件，下次调用时重新创建会话。"""
    if os.path.exists(_SESSION_ID_FILE):
        os.remove(_SESSION_ID_FILE)


# ─── CLI 参数解析 ───────────────────────────────────────────────────

class CliArgs(NamedTuple):
    prompt: str
    file_urls: list[str]
    model: str | None
    config: dict


class AbortArgs(NamedTuple):
    session_id: int


def _parse_args(argv: list[str]) -> CliArgs | AbortArgs:
    """解析命令行参数。支持 --abort 子命令和标准 generate 模式。"""
    # --abort 子命令: python3 generate.py --abort <sessionId>
    if len(argv) >= 2 and argv[0] == "--abort":
        try:
            session_id = int(argv[1])
        except ValueError:
            fail(f"--abort: sessionId 必须是整数, 收到: {argv[1]}")
        return AbortArgs(session_id=session_id)

    # 标准 generate 模式
    file_urls: list[str] = []
    positional: list[str] = []
    model: str | None = None
    config_str: str = "{}"

    i = 0
    while i < len(argv):
        if argv[i] == "--file" and i + 1 < len(argv):
            file_urls.append(argv[i + 1])
            i += 2
        elif argv[i] == "--model" and i + 1 < len(argv):
            model = argv[i + 1]
            i += 2
        elif argv[i] == "--config" and i + 1 < len(argv):
            config_str = argv[i + 1]
            i += 2
        else:
            positional.append(argv[i])
            i += 1

    if len(positional) < 1:
        print(
            "用法: python3 generate.py <prompt> "
            "[--file <url>]... [--model <name>] [--config <json>]\n"
            "      python3 generate.py --abort <sessionId>",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        config = json.loads(config_str)
    except json.JSONDecodeError:
        fail(f"--config 参数不是合法 JSON: {config_str}")

    return CliArgs(
        prompt=positional[0],
        file_urls=file_urls,
        model=model,
        config=config,
    )


# ─── Send 请求参数组装 ───────────────────────────────────────────────

def _build_content(prompt: str, file_urls: list[str], config: dict) -> dict:
    """组装 /send 请求的 content 字段。

    prompt 由宿主 agent 组装（含原位 [@image:#N]/[@video:#N] 占位符 + 末尾引用行），
    原样透传，脚本不拼接占位符、不构建 blocks（gateway 不消费 blocks，
    agent 收图靠 prompt 文本，见后端调查结论）。
    """
    files: list[dict] = []
    for url in file_urls:
        ft = _file_ext_type(url)
        files.append({"type": ft or "file", "url": url})

    content_config: dict[str, Any] = {}
    if config:
        content_config.update(config)
    if "openSearch" not in content_config:
        content_config["openSearch"] = False

    return {
        "prompt": prompt,
        "files": files,
        "config": content_config,
    }


# ─── 主流程 ──────────────────────────────────────────────────────────

def generate(
    prompt: str,
    file_urls: list[str] | None = None,
    model: str | None = None,
    config: dict | None = None,
) -> dict:
    """V3 generate 主流程: 创建/复用会话 → 组装参数 → send → 输出 JSON 后退出。

    凭证由脚本内部 `meigen status --json` 获取（FR-022），不作为参数传入。

    Returns:
        dict with sessionId, assistantMessageId, status
    """
    file_urls = file_urls or []
    config = config or {}

    # 获取 access_token（脚本内部 meigen status --json + 必要时 login）
    access_token = get_access_token()

    # --model 映射到 config.fastModel（仅用户明确指定时传递）
    if model:
        config = {**config, "fastModel": model}

    # 1. 创建/复用会话
    try:
        session_id = _get_or_create_session(access_token)
    except AuthError:
        # 401 → 刷新 token 重试
        new_token = refresh_token()
        if not new_token:
            fail("Token 过期，刷新失败，请运行 meigen login --force")
        _delete_session_file()
        session_id = _get_or_create_session(new_token)
        access_token = new_token

    # 2. 组装 send content
    content = _build_content(prompt=prompt, file_urls=file_urls, config=config)

    # 3. 发送消息
    _progress("🚀 发送任务给设计师...")
    send_body = {
        "sessionId": session_id,
        "content": content,
        "businessInfo": {"channelId": "Meigen-AgentV3-Skill"},
    }
    try:
        send_resp = request("POST", "/skill/send", access_token, body=send_body)
    except AuthError:
        # 401 → 刷新 token 重试
        new_token = refresh_token()
        if not new_token:
            fail("Token 过期，刷新失败，请运行 meigen login --force")
        _delete_session_file()
        session_id = _get_or_create_session(new_token)
        send_body = {**send_body, "sessionId": session_id}
        send_resp = request("POST", "/skill/send", new_token, body=send_body)
        access_token = new_token

    send_data = send_resp.get("data", {})
    user_message_id = send_data.get("userMessageId")
    assistant_message_id = send_data.get("assistantMessageId")
    _progress(f"📨 消息已发送 (userMessageId={user_message_id}, assistantMessageId={assistant_message_id})")

    # 4. 输出提交成功终态 JSON Line（_action=submitted，send only，不轮询）
    result = {
        "type": "submit_result",
        "_action": "submitted",
        "sessionId": session_id,
        "userMessageId": user_message_id,
        "assistantMessageId": assistant_message_id,
        "status": "submitted",
    }
    _output_json_line(result)
    return result


# ─── 会话管理 API ──────────────────────────────────────────────────────

def abort_task(session_id: int) -> None:
    """中止正在执行的任务。token 由脚本内部 meigen status --json 获取（FR-022）。"""
    access_token = get_access_token()
    request("POST", "/message/abort", access_token, body={"sessionId": session_id})
    _progress("⏹️ 任务已中止")


def delete_session(session_id: int) -> None:
    """删除服务端会话。token 由脚本内部 meigen status --json 获取（FR-022）。"""
    access_token = get_access_token()
    request("POST", "/session/delete", access_token, body={"id": session_id})
    _delete_session_file()
    _progress("🗑️ 会话已删除")


# ─── CLI 入口 ────────────────────────────────────────────────────────

def _print_usage() -> None:
    """输出用法到 stderr。"""
    print(
        "用法: python3 generate.py <prompt> "
        "[--file <url>]... [--model <name>] [--config <json>]\n"
        "      python3 generate.py --abort <sessionId>",
        file=sys.stderr,
    )


if __name__ == "__main__":
    # 不变式：stdout 永远是单个合法 JSON（成功为 submitted，失败为 failed 带 msg）。
    # 未捕获异常的 traceback 默认走 stderr 会被宿主 agent 的 2>/dev/null 丢弃，
    # 此处全局兜底转为 fail()，确保错误信息经 stdout JSON 可达。
    try:
        if len(sys.argv) < 2:
            _print_usage()
            sys.exit(1)

        args = _parse_args(sys.argv[1:])

        if isinstance(args, AbortArgs):
            abort_task(args.session_id)
        else:
            generate(
                prompt=args.prompt,
                file_urls=args.file_urls,
                model=args.model,
                config=args.config,
            )
    except SystemExit:
        raise  # fail() 的 sys.exit(1) / 用法提示正常传播
    except BaseException as e:
        fail(f"未捕获异常: {type(e).__name__}: {e}")
