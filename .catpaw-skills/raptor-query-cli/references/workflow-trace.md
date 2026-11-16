# 链路追踪 & 接口性能分析 — 详细参考

## trace 命令参数

| 参数 | 说明 |
|------|------|
| `--id` | traceId（必填） |
| `-a` | appKey（可选；不传=全量查询，传=按appKey精准过滤） |
| `-v` | 完整调用树 |
| `-d` | 自动诊断（慢查询/重复调用/RPC超时） |
| `-f` | ASCII 火焰图 |
| `--span` | 子树下钻（如 `0-22`） |

### 两种查询模式

- **精准查询**（传 `-a`）：通过 MCP `get_by_traceid_and_appkey` 按 appKey 过滤 span，数据精准，适合已知目标服务
- **全量查询**（不传 `-a`）：通过 MCP `get_tracedetail_by_traceid` 返回完整链路所有 span，数据量大，适合不确定哪个服务出问题时全局排查

CLI 按 JSON-RPC 响应 id 匹配 MCP SSE 消息，避免 `tools/list` 响应与查询结果的消息顺序相互干扰。

### trace 示例

```bash
raptor-prod trace --id <traceId>                          # 全量查询（所有 span）
raptor-prod trace --id <traceId> -a <appkey>              # 精准查询（按 appKey 过滤）
raptor-prod trace --id <traceId> -a <appkey> -v           # 完整调用树
raptor-prod trace --id <traceId> -a <appkey> -d           # 自动诊断
raptor-prod trace --id <traceId> -a <appkey> -f           # ASCII 火焰图
raptor-prod trace --id <traceId> -a <appkey> --span 0-22  # 子树下钻
```

## 接口性能分析示例

```bash
raptor-prod names -a <appkey> -t URL              # 接口列表
raptor-prod tx -a <appkey> -t URL -n "/api/xxx"   # 指定接口 TP99
raptor-prod rpc -a <appkey> -d down -s 1h         # 下游 RPC 耗时排行
raptor-prod topoapi -a <appkey> -m "/api/xxx"     # 该接口的直接上下游（1跳）
```
