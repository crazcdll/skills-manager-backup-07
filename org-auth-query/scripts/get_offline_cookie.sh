#!/usr/bin/env bash
# get_offline_cookie.sh
# 通过 agent-browser 登录 org.it.test.sankuai.com，提取 e5b3c6fa19_ssoid Cookie 并缓存到本地
# 缓存文件：~/.openclaw/org-auth-offline-cookie
# 用法：bash get_offline_cookie.sh [--force]

set -e

CACHE_FILE="$HOME/.openclaw/org-auth-offline-cookie"
CACHE_TTL=28800  # 8小时，单位秒
TARGET_URL="https://org.it.test.sankuai.com/org/api/index/resources"
SSO_URL="http://ssosv.it.test.sankuai.com/sson/login"
COOKIE_KEY="e5b3c6fa19_ssoid"

# ---- 安装检查 ----
if ! command -v agent-browser &>/dev/null; then
    echo "[*] 安装 agent-browser..." >&2
    npm i -g agent-browser >&2
fi

# ---- 缓存有效性检查 ----
force=${1:-""}
if [[ "$force" != "--force" && -f "$CACHE_FILE" ]]; then
    cached_time=$(cat "$CACHE_FILE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('timestamp',0))" 2>/dev/null || echo 0)
    now=$(date +%s)
    age=$(( now - cached_time ))
    if [[ $age -lt $CACHE_TTL ]]; then
        # 直接输出缓存的 cookie 值
        cat "$CACHE_FILE" | python3 -c "import sys,json; print(json.load(sys.stdin)['cookie'])"
        exit 0
    fi
fi

echo "[*] 缓存不存在或已过期，通过浏览器自动登录测试环境获取 Cookie..." >&2

# ---- 打开测试环境，触发 SSO 登录 ----
agent-browser close 2>/dev/null || true
agent-browser open "$TARGET_URL" 2>/dev/null
agent-browser wait --load networkidle 2>/dev/null || true

# 等待 SSO 登录重定向完成（最多 60s）
for i in $(seq 1 30); do
    current_url=$(agent-browser get url 2>/dev/null || echo "")
    if echo "$current_url" | grep -q "org.it.test.sankuai.com"; then
        break
    fi
    sleep 2
done

# ---- 提取 Cookie ----
cookie_value=$(agent-browser eval 'document.cookie' 2>/dev/null | grep -oP '(?<=e5b3c6fa19_ssoid=)[^;]+' || echo "")

if [[ -z "$cookie_value" ]]; then
    # 尝试通过 CDP 获取 httpOnly Cookie
    cookie_value=$(agent-browser eval --stdin <<'EOF' 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read().strip())
    cookies = data if isinstance(data, list) else []
    for c in cookies:
        if c.get('name') == 'e5b3c6fa19_ssoid':
            print(c.get('value',''))
            break
except:
    pass
" || echo "")
EOF
fi

agent-browser close 2>/dev/null || true

if [[ -z "$cookie_value" ]]; then
    echo "[ERROR] 未能获取到 Cookie，请确认 MOA 已登录并能访问测试环境 SSO" >&2
    exit 1
fi

# ---- 缓存到文件 ----
now=$(date +%s)
echo "{\"cookie\": \"${COOKIE_KEY}=${cookie_value}\", \"timestamp\": ${now}}" > "$CACHE_FILE"
chmod 600 "$CACHE_FILE"

echo "[✓] Cookie 已获取并缓存（有效期 8 小时）" >&2
echo "${COOKIE_KEY}=${cookie_value}"
