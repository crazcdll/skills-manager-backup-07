# host-metrics 参数详表

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `-a, --appkey` | ✅ | | 服务名 |
| `-e, --endpoints` | ✅ | | 主机名，多个逗号分隔 |
| `-m, --metrics` | | cpu.busy,mem.memfree.percent,load.1minPerCPU | 指标名，多个用逗号分隔或多次 `-m` 指定；含 tag 的指标（如 `name/key=val,key=val`）自动识别不误分割 |
| `-s, --start` | | 1h | 时间范围 |
| `--end` | | 当前时间 | 结束时间（绝对时间，配合 `-s` 绝对时间使用） |
| `-q, --query-type` | | 自动 | 粒度：minute/second/2h/hour/day |
| `--sample` | | AVG | 聚合：AVG/MIN/MAX/COUNT |
| `--trend` | | | 单指标时输出逐点时序 |
| `--list` | | | 列出主机自定义指标 |
| `--json` | | | JSON 输出 |

## 常用系统指标
| 指标 | 说明 |
|------|------|
| `cpu.busy` | CPU 使用率 |
| `load.1minPerCPU` | 每核负载 |
| `mem.memfree.percent` | 内存剩余百分比 |
| `net.if.in.Mbps.all` | 网络入流量 |
| `net.if.out.Mbps.all` | 网络出流量 |
| `disk.io.util/device=max` | 磁盘 IO 利用率 |
| `jvm.gc.count` | JVM GC 次数 |
| `jvm.memory.used` | JVM 堆内存使用 |
