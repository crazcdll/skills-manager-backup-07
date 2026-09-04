#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取 agent-data-scan.mynocode.host 的 Supabase JWT access_token。

流程：
1. 用 playwright 打开目标 URL，引导用户完成美团 SSO 登录
2. 等待页面完全加载（Supabase session 写入 localStorage）
3. 从 localStorage key `sb-<project>-auth-token` 提取 access_token
4. 输出到 stdout（不写本地文件）
"""
import sys
import json
import time

TARGET_URL = "https://agent-data-scan.mynocode.host"
# Supabase project ref（从 localStorage key 中推断）
SUPABASE_LS_KEY_PREFIX = "sb-"
SUPABASE_LS_KEY_SUFFIX = "-auth-token"

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("ERROR: playwright 未安装", file=sys.stderr)
    print("安装命令: pip3 install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(1)


def get_token_via_playwright() -> str | None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()

        print(f"正在打开 {TARGET_URL}，请在弹出的浏览器中完成美团 SSO 登录...", file=sys.stderr)
        page.goto(TARGET_URL)

        # 等待跳转回目标域名（SSO 完成后）
        print("等待 SSO 登录完成...", file=sys.stderr)
        try:
            page.wait_for_url(
                lambda url: "agent-data-scan.mynocode.host" in url and "sso.sankuai.com" not in url,
                timeout=120_000,
            )
        except PlaywrightTimeoutError:
            print("ERROR: 登录超时（120秒），请重试", file=sys.stderr)
            browser.close()
            return None

        # 等待 Supabase session 写入 localStorage（页面 JS 初始化需要几秒）
        print("登录成功，等待 Supabase session 初始化...", file=sys.stderr)
        token = None
        deadline = time.time() + 30  # 最多等 30 秒
        while time.time() < deadline:
            time.sleep(2)
            try:
                ls_keys = page.evaluate("() => Object.keys(localStorage)")
                for key in (ls_keys or []):
                    if key.startswith(SUPABASE_LS_KEY_PREFIX) and key.endswith(SUPABASE_LS_KEY_SUFFIX):
                        val_str = page.evaluate(f"() => localStorage.getItem({json.dumps(key)})")
                        if not val_str:
                            continue
                        val = json.loads(val_str)
                        token = val.get("access_token")
                        if token:
                            break
                if token:
                    break
            except Exception:
                continue

        browser.close()
        return token


def main():
    token = get_token_via_playwright()
    if not token:
        print("ERROR: 无法从 Supabase localStorage session 提取 access_token", file=sys.stderr)
        print("请确认已在弹出的浏览器中完成美团 SSO 登录", file=sys.stderr)
        sys.exit(1)
    print(token)  # 输出到 stdout，不写文件


if __name__ == "__main__":
    main()
