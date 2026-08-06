# 创建测试账号接口

## 接口信息

| 项目 | 值 |
|------|-----|
| URL | `https://qahome.sankuai.com/user/regNewUser/` |
| 方法 | GET |
| 认证 | `access-token: ${user_access_token}` |
| 用途 | 在 QAHome 测试环境自动注册一个新测试账号，返回手机号和 userId |

## 请求示例

```bash
curl -s -X GET "https://qahome.sankuai.com/user/regNewUser/" \
  -H "access-token: ${user_access_token}"
```

## 返回字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| resultCode | int | 0=成功，非0=失败 |
| message | string | 错误信息（失败时） |
| result | object | 创建的账号信息 |
| result.mobileNo | string | 新账号手机号（脱敏，中间4位为****） |
| result.userId | string/long | 新账号 userId |
| result.userNickName | string | 自动生成的昵称 |
| result.userAddDate | long | 注册时间戳（毫秒） |
| result.userSource | string | 账号来源 |

## 错误处理

| 现象 | 原因 | 处理方式 |
|------|------|---------|
| HTTP 302 跳转 SSO | token 失效 | 平台自动刷新，重新执行 |
| `resultCode` 非 0 | 接口异常 | 展示 message 字段 |
| result 为 null | 创建失败 | 提示用户重试 |

## 注意事项

- 本接口仅在 QAHome **测试环境**有效，不影响线上真实用户
- 每次调用自动生成一个新账号，无需传入任何用户参数
- 返回的是测试环境账号，无真实用户信息风险，手机号无需脱敏，完整展示即可
