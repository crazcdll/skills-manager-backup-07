#!/usr/bin/env python3
"""
AI-CR 进度通知脚本
用法: python3 notify.py "消息内容" [mis_id]
- mis_id 可选，传了就同时发个人消息（通过 OpenClaw message 工具）
- 默认发到全局群 group_70457605151
失败不抛异常，直接退出码 0（不阻塞主流程）
"""
import sys, time, uuid, json, base64, hmac, hashlib, urllib.request, urllib.parse

AICR_BOT_APP_ID     = "82146c9c1d"
AICR_BOT_APP_SECRET = "29c4100da6ff4758a608fb45cbee5874"
AICR_GLOBAL_GID     = 70457605151
TOKEN_URL           = "https://ssosv.sankuai.com/sson/auth/oidc/v1/token"
SEND_URL            = "https://xopen.sankuai.com/open-apis/dx-msg/sendGroupMsgByRobot"
SEND_PERSONAL_URL   = "https://xopen.sankuai.com/open-apis/dx-msg/sendPersonalMsgByRobot"

def b64url(data):
    if isinstance(data, str): data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def get_dx_token():
    header  = {"alg": "HS256", "typ": "JWT"}
    now     = int(time.time())
    payload = {
        "iss": AICR_BOT_APP_ID, "sub": AICR_BOT_APP_ID,
        "aud": TOKEN_URL,
        "jti": str(uuid.uuid4()), "iat": now, "exp": now + 300
    }
    h   = b64url(json.dumps(header,  separators=(',',':')))
    p   = b64url(json.dumps(payload, separators=(',',':')))
    sig = hmac.new(AICR_BOT_APP_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    jwt = f"{h}.{p}.{b64url(sig)}"
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": jwt,
        "client_id": AICR_BOT_APP_ID,
        "scope": "client_id:xm-xai"
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]

def send_group_msg(token, gid, text):
    payload = json.dumps({
        "gid": gid,
        "sendMsgInfo": {
            "type": "text",
            "body": json.dumps({"text": text})
        }
    }).encode()
    req = urllib.request.Request(SEND_URL, data=payload, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {token}"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def send_personal_msg(token, mis_id, text):
    """发个人消息（通过 misId）"""
    payload = json.dumps({
        "misId": mis_id,
        "sendMsgInfo": {
            "type": "text",
            "body": json.dumps({"text": text})
        }
    }).encode()
    req = urllib.request.Request(SEND_PERSONAL_URL, data=payload, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {token}"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("用法: python3 notify.py '消息' [mis_id]", file=sys.stderr)
        print("  消息内容不能以 '-' 开头（防止误将命令行参数当作消息发送）", file=sys.stderr)
        sys.exit(0)

    text   = sys.argv[1]

    # 安全校验：以 "-" 开头的参数不允许作为消息内容直接发送
    if text.startswith("-"):
        print(f"[notify] ❌ 拒绝发送：消息内容以 '-' 开头（\"{text}\"），疑似命令行参数误传", file=sys.stderr)
        sys.exit(1)

    mis_id = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        token = get_dx_token()
        # 发全局群
        send_group_msg(token, AICR_GLOBAL_GID, text)
        # 如果传了 mis，额外发个人
        if mis_id:
            try:
                send_personal_msg(token, mis_id, text)
            except Exception as e:
                print(f"[notify] 个人消息发送失败（不影响主流程）: {e}", file=sys.stderr)
        print(f"[notify] ✅ 发送成功: {text[:50]}...")
    except Exception as e:
        print(f"[notify] ⚠️ 通知发送失败（不影响主流程）: {e}", file=sys.stderr)
    sys.exit(0)  # 永远成功，不阻塞主流程
