# 大象群推送 API 实现参考

## 凭证配置

```python
AICR_BOT_APP_ID     = "82146c9c1d"
AICR_BOT_APP_SECRET = "29c4100da6ff4758a608fb45cbee5874"
AICR_GLOBAL_GID     = 70457605151   # 全局汇总群（整数，非字符串）
TOKEN_URL           = "https://ssosv.sankuai.com/sson/auth/oidc/v1/token"
SEND_URL            = "https://xopen.sankuai.com/open-apis/dx-msg/sendGroupMsgByRobot"
```

## 获取 Access Token（client_secret_jwt 方式）

```python
import time, uuid, json, base64, hmac, hashlib, urllib.request, urllib.parse

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
        "scope": "client_id:xm-xai"   # ⚠️ 必须传，否则 token.aud 不含大象，API 返回 30002
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]
```

## 发送群消息

```python
def send_group_msg(token, gid, text):
    payload = json.dumps({
        "gid": gid,
        "sendMsgInfo": {
            "type": "text",                        # ⚠️ 字符串，不是整数
            "body": json.dumps({"text": text})     # ⚠️ body 是 JSON.stringify 后的字符串，不是对象
        }
    }).encode()
    req = urllib.request.Request(SEND_URL, data=payload, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {token}"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
        if result["status"]["code"] != 0:
            raise Exception(f"发送失败: {result}")
        return result
```

## 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `code=30002 auth fail` | scope 未传或写错 | 检查 `scope=client_id:xm-xai` |
| `code=70003 机器人不在该群` | bot 未加入目标群 | 联系木子（mengmuzi）将 bot 加入 |
| `unsupported message type` | type 传了整数 `1` | 改为字符串 `"text"` |
| `40001 type和body非空` | body 传了对象而非字符串 | 用 `json.dumps({"text": "..."})` |
