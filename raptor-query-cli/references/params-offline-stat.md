# offline-stat 参数详表

支持 **event / transaction / problem** 三种离线统计维度。

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `-m, --mode` | | event | 统计维度：`event` / `transaction` / `problem` |
| `--list` | | | 列出该维度下所有可查的 type × name |
| `-t, --type` | 查数据时✅ | | 指标类型（通过 `--list` 查看） |
| `-n, --name` | 查数据时✅ | | 指标名称（通过 `--list` 查看，常用 `*`） |
| `-a, --appkey` | | | 按 appkey 过滤（可多次 `-a xxx -a yyy`） |
| `-c, --category` | | month | 时间粒度：`month` / `week` / `day` / `hour` |
| `-s, --start` | | 自动取整 | 起始时间（`2026-04-20` / `20260420` / 毫秒时间戳） |
| `--sort` | | total | 排序字段：`total` / `failure` / `successRate` / `qps` |
| `--top` | | 30 | 无 `-a` 过滤时最多展示前 N 条（0=全量） |
| `--json` | | | 输出原始 JSON |

## 三种模式说明

- **event**（默认）：Event 维度的离线统计，如 URL.status、SQL.Method 等
- **transaction**：Transaction 维度，如 URL、System、OctoCall 等
- **problem**：Problem 维度，如 error、long-url、long-sql 等

## 使用示例

```bash
# 列出 event 维度所有可查指标
raptor-prod ofs --list

# 列出 transaction 维度可查指标
raptor-prod ofs -m transaction --list

# 列出 problem 维度可查指标
raptor-prod ofs -m problem --list

# Event: 本月 Appkey 请求量排行
raptor-prod ofs -t "CLion.Version" -n "*"

# Transaction: URL 维度按天粒度（T+1 产出，当天无数据）
raptor-prod ofs -m transaction -t URL -n "*" -c day

# Problem: error 类型失败数排行
raptor-prod ofs -m problem -t error -n "*" --sort failure

# 筛选指定 appkey
raptor-prod ofs -t "CLion.Version" -n "*" -a com.sankuai.xxx

# 按天粒度 + 指定起始日期
raptor-prod ofs -t "CLion.Version" -n "*" -c day -s 2026-04-01

# 展示前 50 条
raptor-prod ofs -t "CLion.Version" -n "*" --top 50
```

## 注意事项

- `day` 粒度数据 T+1 产出，当天无数据
- `hour` 粒度数据延迟约 1-2 小时
- 不传 `-s` 时自动取整到当前粒度起点（month→月初，week→周一，day→今天 00:00）
