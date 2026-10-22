"""
共享的 Raptor MCP SSE 客户端

底层：Raptor MCP（HTTP SSE，内网直连）
- 按响应 id 匹配 JSON-RPC 消息（不再依赖消息序号，规避 tools/list 响应干扰）
- 工具名集中注册，便于底层 MCP 工具更名时统一维护
"""
import json
import re
import subprocess
import tempfile
import time
import os

MCP_ENDPOINT = "http://mcphub-server.sankuai.com/mcphub-api/09c9d720d0bb4b"  # internal: .sankuai.com intranet, HTTP allowed

# MCP 工具名注册表（老工具已下线：traceid_without_innner / get_trace_info_by_traceid_and_appkey / topology_api_onestep）
MCP_TOOLS = {
    "trace_all": "get_tracedetail_by_traceid",            # 全量 trace（仅 traceId）
    "trace_by_appkey": "get_by_traceid_and_appkey",        # 按 appKey 过滤 trace
    "topo_api_onestep": "get_method_topology_onestep",     # 方法级单步拓扑
    "methods_by_appkey": "get_methods_by_appkey",          # 查询 appkey 下所有方法
}


def call_mcp_tool(tool_key: str, arguments: dict, timeout: int = 30):
    """
    调用 MCP 工具并返回解析后的 JSON 对象（即 content[0].text 的内容）。

    - 按 JSON-RPC id 匹配响应（id=1 为本次 tools/call 的响应）
    - text 若为纯文本错误信息（非 JSON），抛出 RuntimeError 并携带原始文本
    """
    tool_name = MCP_TOOLS.get(tool_key)
    if not tool_name:
        raise RuntimeError(f"未注册的 MCP 工具 key: {tool_key}")

    tmp_fd, sse_path = tempfile.mkstemp(suffix='.log')
    os.close(tmp_fd)
    sse_proc = None
    try:
        sse_proc = subprocess.Popen(
            ["curl", "-s", "-N", "--noproxy", "*",
             "-H", "Accept: text/event-stream", MCP_ENDPOINT],
            stdout=open(sse_path, 'w'),
            stderr=subprocess.DEVNULL
        )

        session_id = None
        for _ in range(33):
            time.sleep(0.3)
            try:
                with open(sse_path) as f:
                    content = f.read()
                m = re.search(r'sessionId=([a-z0-9\-]+)', content)
                if m:
                    session_id = m.group(1)
                    break
            except Exception:
                pass

        if not session_id:
            raise RuntimeError("SSE 连接超时，未获取到 sessionId")

        def post_mcp(payload):
            subprocess.run(
                ["curl", "-s", "--noproxy", "*", "-m", "10",
                 "-X", "POST", f"{MCP_ENDPOINT}?sessionId={session_id}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps(payload)],
                capture_output=True
            )

        post_mcp({"jsonrpc": "2.0", "id": 0, "method": "tools/list", "params": {}})
        time.sleep(3)
        post_mcp({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        })

        wait_until = time.time() + max(10, timeout - 14)
        while time.time() < wait_until:
            time.sleep(1)
            with open(sse_path) as f:
                raw = f.read()
            for msg in _iter_message_payloads(raw):
                obj = msg
                if obj.get('id') != 1:
                    continue
                result = obj.get('result') or {}
                if result.get('isError'):
                    text = _first_text(result)
                    raise RuntimeError(f"MCP 工具返回错误: {text[:300]}")
                text = _first_text(result)
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    raise RuntimeError(f"MCP 返回非 JSON 响应: {text[:300]}")

        raise RuntimeError("等待 MCP 响应超时，请重试或增大 --timeout")
    finally:
        if sse_proc:
            try:
                sse_proc.terminate()
            except Exception:
                pass
        try:
            os.unlink(sse_path)
        except Exception:
            pass


def _first_text(result: dict) -> str:
    for item in result.get('content', []) or []:
        if isinstance(item, dict) and item.get('type') == 'text':
            return str(item.get('text', ''))
    return ''


def _iter_message_payloads(raw: str):
    """逐条解析 SSE 流中 event=message 的 data，返回已 JSON 解析的对象；解析失败的跳过"""
    lines = raw.split('\n')
    cur_event, cur_data = None, []
    for line in lines:
        if line.startswith('event:'):
            cur_event = line[6:].strip(); cur_data = []
        elif line.startswith('data:'):
            cur_data.append(line[5:].lstrip())
        elif line == '' and cur_event == 'message' and cur_data:
            payload = '\n'.join(cur_data)
            try:
                yield json.loads(payload)
            except json.JSONDecodeError:
                pass
            cur_event, cur_data = None, []
