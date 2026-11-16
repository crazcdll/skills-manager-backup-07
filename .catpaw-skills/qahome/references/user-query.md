# 用户信息查询接口详情

## 接口信息

| 字段 | 值 |
|------|---|
| 地址 | `https://qahome.sankuai.com/user` |
| 方法 | POST |
| Content-Type | `application/json` |
| 鉴权 | SSO access-token（由 `bin/ciba-request.mjs` 自动处理） |

## 环境说明

本接口查询的是 **QAHome 测试环境** 的用户数据，所有操作均针对测试账号，无线上风险。

## 请求 Body

```json
{
  "userId": "",
  "mobileNo": ""
}
```

- 根据手机号查 userId → 填 `mobileNo`，`userId` 留空
- 根据 userId 查手机号 → 填 `userId`，`mobileNo` 留空
- 两个字段至少填一个

## 返回示例

```json
{
  "resultCode": 0,
  "result": {
    "userId": 9000000000057607812,
    "userEmail": "",
    "userNickName": "哈哈哈60",
    "mobile": "13262298960",
    "mobileNoStatus": 2,
    "userAddDate": 1676881710000,
    "userSource": 200,
    "userPW": "0",
    "emailStatus": 0
  },
  "message": "Success",
  "resultNum": 0,
  "note": "9000000000057607812"
}
```

## 返回字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| userId | number | 大众点评用户ID |
| mobile | string | 手机号 |
| userNickName | string | 用户昵称 |
| userAddDate | number | 注册时间（毫秒时间戳） |
| userSource | number | 用户来源 |
| mobileNoStatus | number | 手机号状态（2=正常绑定） |
| userEmail | string | 邮箱 |
| emailStatus | number | 邮箱状态 |

## 错误处理

| 现象 | 原因 | 处理方式 |
|------|------|---------|
| `status: 401` | SSO token 失效 | 重新执行，ciba-request.mjs 会自动续期 |
| `resultCode: 0` 但 result 为空/null | 该手机号/userId 不存在 | 提示用户确认输入是否正确 |
| `resultCode` 非 0 | 接口异常 | 展示 message 字段信息 |
