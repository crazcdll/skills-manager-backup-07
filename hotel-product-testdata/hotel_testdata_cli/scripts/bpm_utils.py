#!/usr/bin/env python3
"""
BPM 审核系统工具函数 - skill

提供 BPM（Business Process Management）审核的公共工具函数：
- 浏览器 Cookie 获取（通过 CatDesk）
- BPM 登录检测与 SSO 自动登录
- BPM 审核任务查询
- BPM 任务委托
- BPM taskform complete（礼包/通兑超团审核直接走此接口）

认证机制：
  脚本通过 `catdesk browser-action cookies_get` 从浏览器获取 BPM session cookie，
  然后通过 curl 使用该 cookie 调用 BPM API。
  若 cookie 无效，自动尝试导航到 BPM 触发 SSO 登录。
"""

import json
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta


# ── 配置 ──────────────────────────────────────────────────────────────────────
BPM_BASE = "https://bpm.inf.test.sankuai.com"
DELEGATE_USER_ID = "53490113"  # 固定审核委托账号（crstest）


# ════════════════════════════════════════════════════════════════════════════
# Cookie 获取
# ════════════════════════════════════════════════════════════════════════════

def get_browser_cookies(url: str):
    """通过 catdesk browser-action 获取指定 URL 的 Cookie 字符串，失败返回 None。"""
    try:
        r = subprocess.run(
            ["catdesk", "browser-action", json.dumps({"action": "cookies_get", "url": url})],
            capture_output=True, text=True, timeout=15,
        )
    except FileNotFoundError:
        print("[ERROR] catdesk 命令不存在，请确认 CatDesk 已安装并在 PATH 中", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("[ERROR] catdesk browser-action 超时", file=sys.stderr)
        return None

    if r.returncode != 0:
        print(f"[ERROR] catdesk browser-action 失败: {r.stderr.strip()[:200]}", file=sys.stderr)
        return None

    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"[ERROR] 浏览器响应解析失败: {r.stdout[:200]}", file=sys.stderr)
        return None

    cookies = data.get("data", {}).get("cookies", [])
    if not cookies:
        return None

    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def navigate_browser(url: str) -> bool:
    """通过 catdesk 浏览器导航到指定 URL，返回是否成功。"""
    try:
        r = subprocess.run(
            ["catdesk", "browser-action", json.dumps({"action": "navigate", "url": url})],
            capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0
    except Exception:
        return False


def browser_evaluate(script: str):
    """通过 catdesk 浏览器执行 JS 脚本，返回结果字符串，失败返回 None。"""
    try:
        r = subprocess.run(
            ["catdesk", "browser-action", json.dumps({"action": "evaluate", "script": script})],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        return data.get("data", {}).get("result")
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════════
# HTTP 工具
# ════════════════════════════════════════════════════════════════════════════

def http_post_form(url: str, form_data: dict, cookie_str: str):
    """发送 POST form-urlencoded 请求（带 BPM Cookie），返回 JSON dict 或 None。"""
    encoded = urllib.parse.urlencode(form_data)
    r = subprocess.run(
        [
            "curl", "-s", "--location", "--request", "POST", url,
            "-H", "Content-Type: application/x-www-form-urlencoded; charset=UTF-8",
            "-H", "Accept: */*",
            "-H", "X-Requested-With: XMLHttpRequest",
            "-b", cookie_str,
            "--data-raw", encoded,
        ],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        print(f"[ERROR] curl 失败: {r.stderr.strip()}", file=sys.stderr)
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"raw": r.stdout.strip()}


def http_get_bpm(url: str, cookie_str: str):
    """发送 GET 请求（带 BPM Cookie），返回 JSON dict 或 None。"""
    r = subprocess.run(
        [
            "curl", "-s", "--location", url,
            "-H", "Accept: */*",
            "-H", "X-Requested-With: XMLHttpRequest",
            "-b", cookie_str,
        ],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        print(f"[ERROR] curl 失败: {r.stderr.strip()}", file=sys.stderr)
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"raw": r.stdout.strip()}


# ════════════════════════════════════════════════════════════════════════════
# BPM 登录检测
# ════════════════════════════════════════════════════════════════════════════

def _test_bpm_cookie(cookie_str: str) -> bool:
    """用轻量请求验证 BPM cookie 是否有效，返回布尔值。"""
    now = datetime.now()
    form_data = {
        "createTimeStart": (now - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00"),
        "createTimeEnd":   now.strftime("%Y-%m-%d 23:59:59"),
        "keyword": "__test_cookie_check__",
        "pageNo": "1", "pageSize": "1",
        "queryNullAssignee": "false",
        "pageStart": "0", "totalPageCount": "1",
        "totalCount": "1",
        "result": "[object Object]",
        "hasNextPage": "false", "nextPage": "1",
        "hasPrePage": "false", "prePage": "1",
        "inputPageStart": "0",
        "taskTreeId": "", "taskDefinitionKey": "", "processDefinitionKey": "",
        "taskGroup": "", "taskId": "", "isAssign": "", "taskStatus": "",
        "priority": "", "assignee": "", "definitionKey": "", "taskKey": "",
    }
    resp = http_post_form(f"{BPM_BASE}/workbench/delegatetasks/page", form_data, cookie_str)
    if not resp:
        return False
    if resp.get("status") == 401:
        return False
    if resp.get("isSuccess") is True or "data" in resp or "page" in resp:
        return True
    return False


def ensure_bpm_login() -> str:
    """
    确保浏览器已登录 BPM，返回有效的 Cookie 字符串。
    若获取失败，打印错误并返回 None。
    """
    print("[Init] 获取 BPM 浏览器 Cookie...", file=sys.stderr)

    cookie = get_browser_cookies(BPM_BASE)
    if cookie and _test_bpm_cookie(cookie):
        print("[Init] BPM Cookie 有效", file=sys.stderr)
        return cookie

    print("[Init] Cookie 无效或不存在，尝试通过浏览器登录 BPM...", file=sys.stderr)
    navigate_browser(BPM_BASE)
    time.sleep(3)

    page_info = browser_evaluate("document.title + ' | ' + location.href")
    if page_info and "ssosv.it.test.sankuai.com" in page_info:
        print("[Init] 在 SSO 登录页，尝试自动点击登录...", file=sys.stderr)
        browser_evaluate("document.querySelector('button[class*=login-box-submit]')?.click()")
        for _ in range(10):
            time.sleep(2)
            page_info = browser_evaluate("location.href")
            if page_info and "bpm.inf.test.sankuai.com" in page_info:
                print("[Init] SSO 登录成功，已回到 BPM", file=sys.stderr)
                break
        else:
            print("[WARN] SSO 自动登录超时，请手动在浏览器中完成登录", file=sys.stderr)

    cookie = get_browser_cookies(BPM_BASE)
    if cookie and _test_bpm_cookie(cookie):
        print("[Init] BPM Cookie 获取成功", file=sys.stderr)
        return cookie

    print("[ERROR] 无法获取有效的 BPM Cookie，请在浏览器中手动登录后重试", file=sys.stderr)
    return None


# ════════════════════════════════════════════════════════════════════════════
# BPM 任务操作
# ════════════════════════════════════════════════════════════════════════════

def query_bpm_task(keyword: str, bpm_cookie: str, entity_desc: str = ""):
    """
    查询 BPM 审核任务（根据业务ID关键字）。

    参数：
        keyword    - 查询关键字（非房ID/套餐spuId/超团spuId/礼包giftId 等）
        bpm_cookie - BPM Cookie 字符串
        entity_desc - 实体描述（用于错误提示，如"非房ID=xxx"）

    返回：任务字典（包含 taskId, processInstanceId, variables 等），失败返回 None。
    """
    now = datetime.now()
    form_data = {
        "createTimeStart": (now - timedelta(days=90)).strftime("%Y-%m-%d 00:00:00"),
        "createTimeEnd":   now.strftime("%Y-%m-%d 23:59:59"),
        "keyword": str(keyword),
        "pageNo": "1", "pageSize": "20",
        "queryNullAssignee": "false",
        "pageStart": "0", "totalPageCount": "1",
        "totalCount": "1",
        "result": "[object Object]",
        "hasNextPage": "false", "nextPage": "1",
        "hasPrePage": "false", "prePage": "1",
        "inputPageStart": "0",
        "taskTreeId": "", "taskDefinitionKey": "", "processDefinitionKey": "",
        "taskGroup": "", "taskId": "", "isAssign": "", "taskStatus": "",
        "priority": "", "assignee": "", "definitionKey": "", "taskKey": "",
    }

    url = f"{BPM_BASE}/workbench/delegatetasks/page"
    resp = http_post_form(url, form_data, bpm_cookie)

    if not resp:
        print("[ERROR] 查询审核任务请求失败", file=sys.stderr)
        return None
    if resp.get("status") == 401:
        print("[ERROR] BPM 认证失败 (401)，请在浏览器中重新登录 BPM", file=sys.stderr)
        return None

    task = None
    data = resp.get("data") or resp.get("result")
    if isinstance(data, list) and len(data) > 0:
        task = data[0]
    elif isinstance(resp, dict) and resp.get("rows"):
        task = resp["rows"][0]

    if not task:
        label = entity_desc or f"keyword={keyword}"
        if resp.get("isSuccess") is False:
            print(f"[ERROR] BPM 查询失败: {resp.get('msg', '未知错误')}", file=sys.stderr)
        else:
            print(f"[ERROR] 未找到 {label} 的审核任务", file=sys.stderr)
            print(f"  响应内容: {json.dumps(resp, ensure_ascii=False)[:500]}", file=sys.stderr)
        return None

    # 解析流程变量
    variables = task.get("processVariables") or task.get("variables") or {}
    if isinstance(variables, list):
        var_dict = {v.get("name"): v.get("value") for v in variables if isinstance(v, dict)}
    elif isinstance(variables, dict):
        var_dict = variables
    else:
        var_dict = {}

    # 从 page.result 层级补充 variables（如果 data 层级为空）
    if not var_dict and "page" in resp:
        page_result = resp.get("page", {}).get("result", [])
        if page_result:
            page_vars = page_result[0].get("variables", [])
            if isinstance(page_vars, list):
                var_dict = {v.get("name"): v.get("value") for v in page_vars if isinstance(v, dict)}

    task["_var_dict"] = var_dict
    return task


def delegate_bpm_task(task_id: str, bpm_cookie: str, target_user_id: str = None) -> bool:
    """委托 BPM 任务给审核账号，返回是否成功。

    参数：
        task_id         - BPM 任务 ID
        bpm_cookie      - BPM Cookie 字符串
        target_user_id  - 委托目标用户 ID；不传时使用默认的 DELEGATE_USER_ID
    """
    delegate_to = target_user_id or DELEGATE_USER_ID
    print(f"\n[Step 2] 委托任务: taskId={task_id} → userId={delegate_to}", file=sys.stderr)
    url = f"{BPM_BASE}/workbench/task/{task_id}/delegate?userId={delegate_to}"
    resp = http_get_bpm(url, bpm_cookie)

    if resp is None:
        print("[ERROR] 委托任务请求失败", file=sys.stderr)
        return False

    if isinstance(resp, dict):
        if resp.get("isSuccess") is True:
            print("  ✓ 任务委托成功", file=sys.stderr)
            return True
        raw = resp.get("raw", "")
        if raw and ("error" in raw.lower() or "失败" in raw):
            print(f"[ERROR] 委托任务失败: {raw[:200]}", file=sys.stderr)
            return False

    print("  ✓ 任务委托成功", file=sys.stderr)
    return True


def complete_bpm_task(task_id: str, form_data: dict, bpm_cookie: str) -> bool:
    """
    通过 BPM taskform complete 接口提交审核结果（适用于礼包/通兑超团审核）。
    form_data 包含业务字段 + auditResult。
    返回是否成功。
    """
    url = f"{BPM_BASE}/taskform/{task_id}/complete"
    resp = http_post_form(url, form_data, bpm_cookie)

    if resp is None:
        print("[ERROR] 审核提交请求失败", file=sys.stderr)
        return False

    if isinstance(resp, dict):
        if resp.get("isSuccess") is True:
            print("  ✓ 审核提交成功", file=sys.stderr)
            return True
        if resp.get("status") == 401:
            print("[ERROR] BPM 认证失败 (401)", file=sys.stderr)
            return False
        # isSuccess 明确为 false 时，说明业务层拒绝（如无权限）
        if resp.get("isSuccess") is False:
            msg = resp.get("msg") or resp.get("message") or json.dumps(resp, ensure_ascii=False)
            print(f"[ERROR] 审核提交失败: {msg[:300]}", file=sys.stderr)
            return False
        raw = resp.get("raw", "")
        if raw and ("error" in raw.lower() or "失败" in raw or "exception" in raw.lower()):
            print(f"[ERROR] 审核提交失败: {raw[:300]}", file=sys.stderr)
            return False

    print("  ✓ 审核提交成功", file=sys.stderr)
    return True

