# business 参数详表

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `-a, --appkey` | ✅ | | 服务名 |
| `-b, --business` | | | 业务指标 key（不填则列出所有） |
| `-s, --start` | | 24h | 时间范围 |
| `-m, --metric` | | SUM | 聚合方式：COUNT/SUM/AVG/MAX/MIN |
| `-q, --query-type` | | hour | 时间粒度：minute/5m/20m/2h/hour/day |
| `-g, --group-by` | | | 按 tag 分组（需配合 -b） |
| `-f, --filter` | | | tag 过滤，可多次（如 `-f progress=RtTask`） |
| `--trend` | | | 输出 groupBy 时序趋势（需配合 -g） |
| `--list-tags` | | | 列出 tag 定义及实际值 |
| `--json` | | | 输出原始 JSON |

## Tag 含义说明
- `logName`：操作的日志主题名（appkey）。values 超过 limit=10 时显示为 `Others; <KM链接>`
- `storage`：存储后端类型，如 `eagle` / `influxdb`
- `progress`：操作阶段，如 `RtTask`、`Meta`、`Auth`、`Degrade`、`Cluster`

## 注意事项
- `--list-tags` 默认查 24h，时间太短（如 5m）可能无数据导致 values 为空
- `deployCluster` 等低频指标需适当延长时间范围（`-s 7d`）
- tag values 为空不代表该 tag 无效，可能是该时间段无打点数据
