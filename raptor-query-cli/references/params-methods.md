# methods — 服务接口列表

通过 Raptor MCP `get_methods_by_appkey` 查询指定 appkey 下已记录的方法/接口。

## 参数

| 参数 | 必填 | 说明 |
|---|---:|---|
| `-a, --appkey` | ✅ | 服务 appkey |
| `--start-date` | 否 | 起始日期，格式 `yyyy-MM-dd` |
| `--set` | 否 | set 信息 |
| `--timeout` | 否 | MCP 超时秒数，默认 30 |
| `--json` | 否 | 输出原始 JSON |

## 示例

```bash
# 查询服务所有已记录接口
raptor-prod methods -a com.sankuai.mall.order.serviceapi

# 查询指定日期后更新的接口数据
raptor-prod methods -a com.sankuai.mall.order.serviceapi --start-date 2026-09-01

# 按 set 过滤，并输出 JSON
raptor-prod methods -a com.sankuai.mall.order.serviceapi --set prod --json
```

## 输出字段

每个接口项通常包含：`appkey`、`methodName`、`type`、`url`、`createTime`、`updateTime`。字段实际返回以 MCP 为准。
