# 大象群推送 API 实现参考

## 凭证配置

机器人密钥与 appId 配套，内置在 `publish_results.py` 常量区（如下）。
密钥在 Step 8 获取 token 时使用，不在模块导入时加载。

```python
AICR_BOT_APP_ID     = "82146c9c1d"
AICR_BOT_APP_SECRET = "29c4100da6ff4758a608fb45cbee5874"
AICR_GLOBAL_GID     = 70457605151
TOKEN_URL            = "https://ssosv.sankuai.com/sson/auth/oidc/v1/token"
SEND_URL             = "https://xopen.sankuai.com/open-apis/dx-msg/sendGroupMsgByRobot"
MIS2UID_URL          = "https://xopen.sankuai.com/open-apis/dx/queryEmpIdentityByMisList"
```

## 获取 Access Token（client_secret_jwt 方式）

```python
import time, uuid, json, base64, hmac, hashlib, urllib.request, urllib.parse

def b64url(data):
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def get_dx_token():
    secret = AICR_BOT_APP_SECRET
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": AICR_BOT_APP_ID, "sub": AICR_BOT_APP_ID,
        "aud": TOKEN_URL,
        "jti": str(uuid.uuid4()), "iat": now, "exp": now + 300
    }
    h = b64url(json.dumps(header, separators=(',', ':')))
    p = b64url(json.dumps(payload, separators=(',', ':')))
    sig = hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
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
```

`scope` 必须包含 `client_id:xm-xai`。不要记录密钥、JWT、token 或认证请求正文。

## 发送群消息

```python
def send_group_msg(token, gid, text, at_uids=None):
    # at_uids 传大象 uid 字符串列表时携带 extension.at，实现真实 @（要求 text 内已含 @ 高亮协议，两者缺一不可）
    send_info = {"type": "text", "body": json.dumps({"text": text})}
    if at_uids:
        send_info["extension"] = json.dumps({"at": [str(u) for u in at_uids]})
    payload = json.dumps({"gid": gid, "sendMsgInfo": send_info}).encode()
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

## 群内真实 @ 人（团队群 @ 模板 people 行人员）

真实 @ 需要**两处配合，缺一不可**（协议文档：km.sankuai.com/collabpage/1401295987 消息 extension）：

1. `sendMsgInfo.extension.at`：大象 uid **字符串**数组（不是 mis）；`@所有人` 填 `"-1"`
2. body.text 内嵌高亮协议：`[@姓名|mtdaxiang://www.meituan.com/profile?uid={uid}&isAt=true]`（姓名仅展示用，可任意）

实现函数（publish_results.py）：`format_at_text(name, uid)` 生成高亮协议、`apply_at_to_person(...)` 把「提交人/触发人」行替换为 @ 版本、`get_uid_by_mis(token, mis_list)` 做 mis→uid 批量转换（POST MIS2UID_URL，同一 bot token，QPS≤5，单次上限 100 个 mis）。

**策略与降级**：
- **@ 范围 = 模板 people 行人员**：团队群 @ 提交人 + 触发人（同一人时两行都高亮，`extension.at` 去重）；全局群一律纯文本（人员大概率不在全量群，@ 只会灰色展示）
- 逐人降级：某人的 mis 查不到 uid / 未匹配到对应行 → 该人保持纯文本，其余人照常 @，推送不中断（不能只去掉 extension 留高亮链接，否则渲染成普通蓝色超链接——替换与 at_uids 按人同步，天然无中间态）

**约束**：仅群消息支持 @（单聊不支持）；模板消息（custom）不支持 @；被 @ 人不在群里时接口仍返回成功，但 @ 显示灰色且无强提醒；uid 线上/测试环境隔离不可混用；@所有人需群开启对应权限（否则 40005）。

## 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `code=30002 auth fail` | scope 未传或写错 | 检查 `scope=client_id:xm-xai` |
| `code=70003 机器人不在该群` | bot 未加入目标群 | 联系机器人管理方将 bot 加入 |
| `unsupported message type` | type 传了整数 `1` | 改为字符串 `"text"` |
| `40001 type和body非空` | body 传了对象而非字符串 | 用 `json.dumps({"text": "..."})` |
| `40005 @所有人权限不足` | 群未开启 @所有人 | 群管理里开启或改 @ 具体人 |
| `@ 显示灰色/无提醒` | 被 @ 人不在该群（接口仍返回成功） | 属预期行为；全局群不 @ 就是为此 |
