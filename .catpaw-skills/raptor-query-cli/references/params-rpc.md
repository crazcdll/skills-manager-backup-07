# rpc 参数详表

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `-a, --appkey` | ✅ | | 应用 appkey |
| `-d, --direction` | | down | `up`=上游（谁调我），`down`=下游（我调谁） |
| `-m, --method` | | All | 接口名，需与 API 返回的 methodName 完全一致；可先用 `--expand-all` 查看可用值 |
| `-s, --start` | | 0h（当前小时） | 相对（`1h`/`1d`/`1w`）或绝对（`2026-05-29 09:00` / `20260529090000`） |
| `-q, --query-type` | | hour | 粒度：`hour`/`day`/`week`/`month`；时间自动对齐到粒度起点 |
| `-l, --limit` | | 50 | 显示条数上限 |
| `--sort` | | failrate | 排序：`total`/`avg`/`fail`/`failrate`/`qps` |
| `--target` | | | 按 appkey 子串过滤，命中自动展开接口明细 |
| `--target-method` | | | 按方法名子串过滤，只显示含匹配方法的下游并展开 |
| `--expand` | | | 展开指定下游的接口明细（appkey 子串匹配，不过滤其他行） |
| `--expand-all` | | | 全部展开接口明细 |
| `--json` | | | 输出原始 JSON |

## 输出列

| 列 | 说明 |
|----|------|
| total | 请求次数 |
| avg(ms) | 平均耗时 |
| timeout | 代码中配置的 RPC 超时阈值(ms) |
| fail | 失败次数 |
| fail% | 失败率 |
| qps | 每秒请求数 |
| 🌍 | 跨 Region |
| 🏢 | 跨 IDC |

## 注意事项

- `--target` 和 `--target-method` 可组合使用（AND 逻辑）
- `-m` 不匹配时返回为空，接口名以 `--expand-all` 输出为准
- 默认按失败率降序排列，与 Raptor 页面一致
