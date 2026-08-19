#!/usr/bin/env python3
"""
get_offline_cookie.py
自动通过浏览器登录测试环境，提取 e5b3c6fa19_ssoid Cookie 并缓存。
缓存文件：~/.openclaw/org-auth-offline-cookie.json（有效期 8 小时）
"""

import json
import os
import subprocess
import sys
import time

CACHE_FILE = os.path.expanduser("~/.openclaw/org-auth-offline-cookie.json")
CACHE_TTL = 8 * 3600  # 8小时
COOKIE_KEY = "e5b3c6fa19_ssoid"
TARGET_URL = "https://org.it.test.sankuai.com/org/api/index/resources"

def log(msg):
    print(f"[*] {msg}", file=sys.stderr)

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def load_cache():
    try:
        with open(CACHE_FILE) as f:
            d = json.load(f)
        age = int(time.time()) - d.get("timestamp", 0)
        if age < CACHE_TTL:
            return d.get("cookie", "")
    except Exception:
        pass
    return None

def save_cache(cookie_str):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"cookie": cookie_str, "timestamp": int(time.time())}, f)
    os.chmod(CACHE_FILE, 0o600)

def ensure_agent_browser():
    _, rc = run("command -v agent-browser")
    if rc != 0:
        log("安装 agent-browser...")
        subprocess.run("npm i -g agent-browser", shell=True)

def get_current_mis() -> str:
    """从本地 MOA token 自动解析当前登录 MIS"""
    import base64
    out, rc = run("npx mtsso-moa-local-exchange --audience c554e69579 2>/dev/null")
    if rc != 0 or not out:
        return ""
    try:
        token = json.loads(out).get("access_token", "")
        # token 格式：<base64>**<audience>**<sig>**<base64_userinfo>
        last_part = token.split("**")[-1]
        padded = last_part + "=" * (4 - len(last_part) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
        # 格式：uid,mis,name,email,...
        fields = decoded.split(",")
        if len(fields) >= 2:
            return fields[1]
    except Exception:
        pass
    return ""


def fetch_cookie_via_browser():
    log("缓存不存在或已过期，通过浏览器自动登录测试环境...")
    ensure_agent_browser()

    # 自动获取当前 MIS，失败则重试 3 次
    current_mis = ""
    for attempt in range(1, 4):
        current_mis = get_current_mis()
        if current_mis:
            log(f"当前 MIS：{current_mis}")
            break
        log(f"⚠️ 无法获取当前 MIS（第 {attempt}/3 次），稍后重试...")
        time.sleep(2)

    if not current_mis:
        log("❌ 无法自动获取当前 MIS，登录中止。可能原因：")
        log("   1. 大象（MOA）客户端未登录或未运行")
        log("   2. 本地 MOA WSS 服务不可用（wss://localhost.moa.sankuai.com:16161）")
        log("   3. 网络异常导致 token 获取失败")
        log("解决方法：确认大象客户端已启动并登录后，重新执行查询命令。")
        subprocess.run("agent-browser close 2>/dev/null || true", shell=True, capture_output=True)
        sys.exit(1)

    # 关闭旧会话
    subprocess.run("agent-browser close 2>/dev/null || true", shell=True, capture_output=True)

    # 打开测试环境（会触发 SSO 跳转到 Login 页面）
    log(f"打开 {TARGET_URL}...")
    subprocess.run(f'agent-browser open "{TARGET_URL}"', shell=True, capture_output=True)

    # 等待页面稳定（SSO 登录页）
    time.sleep(2)

    # 检查是否跳到了 SSO 登录页，若是则自动填入 MIS 并点击免密登录
    url_out, _ = run("agent-browser get url 2>/dev/null")
    if "ssosv.it.test.sankuai.com" in url_out:
        log("检测到 SSO 登录页，自动填写 MIS 并发起免密登录...")
        snapshot_out, _ = run("agent-browser snapshot -i 2>/dev/null")

        # 找到账号输入框 ref（通常是 e3）
        import re
        input_ref = "e3"
        btn_ref = "e2"
        for line in snapshot_out.splitlines():
            if "account" in line.lower() or "账号" in line:
                m = re.search(r'\[ref=(e\d+)\]', line)
                if m:
                    input_ref = m.group(1)
            if "password free" in line.lower() or "免密" in line:
                m = re.search(r'\[ref=(e\d+)\]', line)
                if m:
                    btn_ref = m.group(1)

        subprocess.run(f"agent-browser fill {input_ref} {current_mis}", shell=True, capture_output=True)
        subprocess.run(f"agent-browser click {btn_ref}", shell=True, capture_output=True)

    # 等待跳转回 org.it.test.sankuai.com（最多 30s）
    log("等待 SSO 登录完成...")
    for i in range(15):
        time.sleep(2)
        url_out, _ = run("agent-browser get url 2>/dev/null")
        if "org.it.test.sankuai.com" in url_out and "ssosv" not in url_out:
            log(f"登录成功！当前页面：{url_out[:60]}")
            break
        if i == 14:
            log("⚠️ 等待登录超时")

    # 用 agent-browser cookies get 提取 httpOnly Cookie
    cookie_output, _ = run(f"agent-browser cookies get --domain org.it.test.sankuai.com 2>/dev/null")
    cookie_value = ""
    for line in cookie_output.splitlines():
        line = line.strip()
        if line.startswith(f"{COOKIE_KEY}="):
            cookie_value = line.split("=", 1)[1]
            break

    subprocess.run("agent-browser close 2>/dev/null || true", shell=True, capture_output=True)

    if not cookie_value:
        log("❌ 未能提取到 Cookie。可能原因：")
        log("   1. MOA 未登录（大象客户端需在线）")
        log("   2. 测试环境 SSO 需要额外确认")
        sys.exit(1)

    return f"{COOKIE_KEY}={cookie_value}"

def main():
    force = "--force" in sys.argv

    if not force:
        cached = load_cache()
        if cached:
            print(cached)
            return

    cookie_str = fetch_cookie_via_browser()
    save_cache(cookie_str)
    log("✅ Cookie 已获取并缓存（有效期 8 小时）")
    print(cookie_str)

if __name__ == "__main__":
    main()
