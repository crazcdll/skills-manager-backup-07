# raptor-query-cli 测试用例集

> 格式：`CMD:` 执行命令，`EXPECT:` 预期关键字（grep 校验），`EXPECT_FAIL:` 预期失败，`EXPECT_EMPTY:` 预期无输出
> `run_tests.sh` 自动解析本文件执行测试。新增 case 只改此文件。

---

## 1. hosts — 主机列表

### Case 1.1: hosts 基础 [smoke]
CMD: raptor-prod hosts -a cat -l 5
EXPECT: 主机

### Case 1.2: hosts JSON
CMD: raptor-prod hosts -a cat -l 2 --json
EXPECT: result

---

## 2. types — 类型列表

### Case 2.1: Transaction 类型 [smoke]
CMD: raptor-prod types -a cat -t transaction -s 5m
EXPECT: 类型列表

### Case 2.2: Event 类型
CMD: raptor-prod types -a cat -t event -s 5m
EXPECT: 类型列表

### Case 2.3: Problem 类型
CMD: raptor-prod types -a cat -t problem -s 5m
EXPECT: error

---

## 3. names — 名称列表

### Case 3.1: URL 下的接口
CMD: raptor-prod names -a cat -t URL -s 5m
EXPECT: /

---

## 4. transaction — Transaction 指标

### Case 4.1: 单 type [smoke]
CMD: raptor-prod tx -a cat -t URL -s 5m
EXPECT: QPS

### Case 4.2: 多 type 合并对比
CMD: raptor-prod tx -a cat -t "URL,SQL,System" -s 1h
EXPECT: URL
EXPECT: SQL

### Case 4.3: 指定 name
CMD: raptor-prod tx -a cat -t URL -n All -s 5m
EXPECT: QPS

### Case 4.4: JSON
CMD: raptor-prod tx -a cat -t URL -s 5m --json
EXPECT: result

---

## 5. event — Event 指标

### Case 5.1: 单 type
CMD: raptor-prod event -a cat -t "jvm.gc" -s 1h
EXPECT: jvm.gc

---

## 6. problem — Problem 指标

### Case 6.1: 单 type [smoke]
CMD: raptor-prod problem -a cat -t error -s 1h
EXPECT: error

---

## 7. business — Business 指标

### Case 7.1: 列出 business key
CMD: raptor-prod business -a com.sankuai.raptor.logcenter.access
EXPECT: access

### Case 7.2: --list-tags
CMD: raptor-prod business -a com.sankuai.raptor.logcenter.access --list-tags -s 24h
EXPECT: storage

### Case 7.3: -b 指定 key + --list-tags
CMD: raptor-prod business -a com.sankuai.raptor.logcenter.access -b access --list-tags
EXPECT: progress

### Case 7.4: -g groupBy
CMD: raptor-prod business -a com.sankuai.raptor.logcenter.access -b access -g progress -s 24h
EXPECT: 占比

### Case 7.5: -g + --trend
CMD: raptor-prod business -a com.sankuai.raptor.logcenter.access -b access -g progress -s 24h --trend
EXPECT: 占比

### Case 7.6: -f tag 过滤
CMD: raptor-prod business -a com.sankuai.raptor.logcenter.access -b access -f progress=RtTask -s 24h
EXPECT: access

---

## 8. logview — Logview ID 列表

### Case 8.1: error logview
CMD: raptor-prod logview -a cat -s 10m --type error -l 3
EXPECT: logview

---

## 9. logview-detail — 调用树

### Case 9.1: --url 解析
CMD: raptor-prod logview-detail --url "https://raptor.mws.sankuai.com/application/logview?domain=cat&message=cat-0af2619a-492607-125578&logViewType=error"
EXPECT: cat

---

## 10. topology — 上下游拓扑

### Case 10.1: 上游 [smoke]
CMD: raptor-prod topology -a cat -s 5m -d up
EXPECT: 上游

### Case 10.2: 下游
CMD: raptor-prod topology -a cat -s 5m -d down
EXPECT: 拓扑

---

## 11. host-metrics — 主机指标

### Case 11.1: 默认指标
CMD: raptor-prod host-metrics -a cat -e hldy-infsh-cat-cat01 -s 1h
EXPECT: cpu

### Case 11.2: 指定指标
CMD: raptor-prod host-metrics -a cat -e hldy-infsh-cat-cat01 -m "cpu.busy" -s 30m
EXPECT: cpu.busy

### Case 11.3: --list
CMD: raptor-prod host-metrics -a cat -e hldy-infsh-cat-cat01 --list -l 5
EXPECT: metric

---

## 12. ips — IP 列表

### Case 12.1: 基础
CMD: raptor-prod ips -a cat -s 1h
EXPECT: 10.

---

## 13. help & 防御性

### Case 13.1: help [smoke]
CMD: raptor-prod help
EXPECT: transaction
EXPECT: business
EXPECT: logview

### Case 13.2: 子命令 help [smoke]
CMD: raptor-prod tx --help
EXPECT: appkey

### Case 13.3: 无参数
CMD: raptor-prod
EXPECT: transaction

---

## 14. 别名

### Case 14.1: tx = transaction
CMD: raptor-prod tx -a cat -t URL -s 5m
EXPECT: cat

### Case 14.2: ev = event
CMD: raptor-prod ev -a cat -t "jvm.gc" -s 1h
EXPECT: cat

### Case 14.3: pb = problem
CMD: raptor-prod pb -a cat -t error -s 1h
EXPECT: cat

### Case 14.4: biz = business
CMD: raptor-prod biz -a com.sankuai.raptor.logcenter.access
EXPECT: access

### Case 14.5: topo = topology
CMD: raptor-prod topo -a cat -s 5m -d up
EXPECT: cat

### Case 14.6: hm = host-metrics
CMD: raptor-prod hm -a cat -e hldy-infsh-cat-cat01 -s 1h
EXPECT: cat

### Case 14.7: ld = logview-detail
CMD: raptor-prod ld --url "https://raptor.mws.sankuai.com/application/logview?domain=cat&message=cat-0af2619a-492607-125578&logViewType=error"
EXPECT: cat

---

## 15. 语法 & 自包含

### Case 15.1: Python wrapper 语法 [smoke]
CMD: cd "$SKILL_DIR" && python3 -c "import py_compile, sys; py_compile.compile('raptor-prod', doraise=True)" 2>&1; echo ok
EXPECT: ok

### Case 15.2: Python 语法
CMD: cd "$SKILL_DIR" && python3 -c "import ast; ast.parse(open('cli.py').read())"
EXPECT_EMPTY: true

### Case 15.3: client 语法
CMD: cd "$SKILL_DIR" && python3 -c "import ast; ast.parse(open('client.py').read())"
EXPECT_EMPTY: true

---

## 16. 大哥对话中的真实查询场景（2026-03-13）

### Case 16.1: logview 绝对时间查询
CMD: raptor-prod logview -a com.sankuai.mpmkt.coupon.assistant -s "2026-03-12 20:00:00" -e "2026-03-12 20:59:00" --type error -l 20
EXPECT: logview

### Case 16.2: logview-detail 从 URL 解析（真实 URL）
CMD: raptor-prod logview-detail --url "https://raptor.mws.sankuai.com/application/logview?domain=com.sankuai.search.waimai.recall&message=com.sankuai.search.waimai.recall-0ada086b-492589-22571788&logViewType=error"
EXPECT: waimai.recall

### Case 16.3: logview-detail 耗时+折叠+汇总
SKIP: logview ID 过期，数据生命周期有限
CMD: raptor-prod logview-detail -a cat --id cat-0af2619a-492607-125578 -d 5
EXPECT: Logview

### Case 16.4: logview-detail 复杂调用树（266 节点）
SKIP: logview ID 过期，数据生命周期有限
CMD: raptor-prod logview-detail -a com.sankuai.search.waimai.recall --id com.sankuai.search.waimai.recall-0a23121e-492607-9917206 -d 4
EXPECT: waimai.recall

### Case 16.5: host-metrics --list 过滤 hdd_id 指标
CMD: raptor-prod host-metrics -a com.sankuai.s3plus.store -e zwyd-s3plus-zwmad-store121 --list -l 200
EXPECT: 指标

### Case 16.6: business groupBy + 占比（logcenter.access progress）
CMD: raptor-prod business -a com.sankuai.raptor.logcenter.access -b access -g progress -s 24h
EXPECT: 占比
EXPECT: RtTask

### Case 16.7: business tag 过滤
CMD: raptor-prod business -a com.sankuai.raptor.logcenter.access -b access -f progress=RtTask -s 24h
EXPECT: access

### Case 16.8: logview 相对时间回归
CMD: raptor-prod logview -a cat -s 10m --type error -l 5
EXPECT: logview

---

## 17. rpc — 接口粒度上下游（新增）

### Case 17.1: rpc 下游（我调谁）
CMD: raptor-prod rpc -a cat -d down -s 0h -l 5
EXPECT: 下游
EXPECT: 接口

### Case 17.2: rpc 上游（谁调我）
CMD: raptor-prod rpc -a cat -d up -s 0h -l 5
EXPECT: 上游
EXPECT: 接口

### Case 17.3: rpc 按 avg 排序
CMD: raptor-prod rpc -a cat -d down -s 1h --sort avg -l 3
EXPECT: 下游

### Case 17.4: rpc day 粒度
CMD: raptor-prod rpc -a cat -d down -s 0d -q day -l 3
EXPECT: day

### Case 17.5: rpc JSON
CMD: raptor-prod rpc -a cat -d up -s 0h --json
EXPECT: rpcDomains

### Case 17.6: rpc help
CMD: raptor-prod rpc --help
EXPECT: appkey
EXPECT: direction

## 18. trace — 链路追踪分析（v1.9.4 新增）

> 真实 traceId 来自对话中实测（2026-03-19）
> appkey: com.sankuai.maiot.mios.isac

### Case 18.1: trace help
CMD: raptor-prod trace --help
EXPECT: traceId
EXPECT: appkey
EXPECT: flame
EXPECT: diagnose
EXPECT: span

### Case 18.2: trace 别名 tr
CMD: raptor-prod tr --help
EXPECT: traceId

### Case 18.3: 缺 --id 报错
CMD: raptor-prod trace -a com.sankuai.maiot.mios.isac
EXPECT_FAIL: true
EXPECT: required

### Case 18.5: 慢 Span 树形展示（默认模式）
CMD: raptor-prod trace --id -8686063535056501832 -a com.sankuai.grouptrade.precreate.apic
EXPECT: 共
EXPECT: span
EXPECT: createOrder
EXPECT: 🟡

### Case 18.6: --flame ASCII 甘特图
CMD: raptor-prod trace --id -8686063535056501832 -a com.sankuai.grouptrade.precreate.apic --flame
EXPECT: ASCII 甘特图
EXPECT: 时间范围
EXPECT: 最慢 Span
EXPECT: ▓

### Case 18.7: --diagnose 自动诊断
CMD: raptor-prod trace --id -8686063535056501832 -a com.sankuai.grouptrade.precreate.apic --diagnose
EXPECT: 自动诊断分析
EXPECT: 诊断总结
EXPECT: RPC 慢调用
EXPECT: 错误 Span

### Case 18.8: --span 子树下钻
CMD: raptor-prod trace --id -8686063535056501832 -a com.sankuai.grouptrade.precreate.apic --span 0-16 -v
EXPECT: 调用子树
EXPECT: 0-16
EXPECT: createOrder

### Case 18.9: -v 完整树
CMD: raptor-prod trace --id -8686063535056501832 -a com.sankuai.grouptrade.precreate.apic -v
EXPECT: 完整 Span 列表
EXPECT: caller=

### Case 18.10: 有慢有错 trace（2 span）
CMD: raptor-prod trace --id -8686063535056501832 -a com.sankuai.grouptrade.precreate.apic
EXPECT: 共 2 个 span
EXPECT: 慢 Span（≥500ms）: 2
EXPECT: 错误 Span: 1

### Case 18.11: 慢调用诊断（submit 1162ms）
CMD: raptor-prod trace --id -8686063535056501832 -a com.sankuai.grouptrade.precreate.apic --diagnose
EXPECT: AbstractUnifiedController.submit
EXPECT: 1162ms
EXPECT: RPC 慢调用
EXPECT: 关键瓶颈 Span

### Case 18.12: --flame + --diagnose 组合
CMD: raptor-prod trace --id -8686063535056501832 --flame --diagnose
EXPECT: ASCII 甘特图

### Case 18.13: 全量 -v 含 mtthrift span
CMD: raptor-prod trace --id -8686063535056501832 -v
EXPECT: mtthrift
EXPECT: caller=

### Case 18.14: 全量查询（不传 -a）
CMD: raptor-prod trace --id -8686063535056501832
EXPECT: 全量模式

### Case 18.15: 全量查询 + verbose
CMD: raptor-prod trace --id -8686063535056501832 -v
EXPECT: 全量模式
EXPECT: 完整 Span 列表

### Case 18.16: 全量查询 + diagnose
CMD: raptor-prod trace --id -8686063535056501832 -d
EXPECT: 全量模式

### Case 18.17: 全量查询 + flame
CMD: raptor-prod trace --id -8686063535056501832 -f
EXPECT: 全量模式
EXPECT: ASCII 甘特图

### Case 18.18: 全量查询 + JSON
CMD: raptor-prod trace --id -8686063535056501832 --json
EXPECT: 全量模式


## 19. topo-api（接口级拓扑）

### Case 19.1: 基本查询（上下游全）
CMD: raptor-prod topo-api -a com.sankuai.raptor.dw.openapi -m /raptor/dw/openapi/event/meta/types
EXPECT: 接口级拓扑（仅 1 跳）
EXPECT: ⬆️  上游（谁调了我）
EXPECT: ⬇️  下游（我调了谁）
EXPECT: com.sankuai.apigw.inf.mcpdefault
EXPECT: redis-raptor-common_product

### Case 19.2: 只看上游
CMD: raptor-prod topo-api -a com.sankuai.raptor.dw.openapi -m /raptor/dw/openapi/event/meta/types -d up
EXPECT: ⬆️  上游（谁调了我）
EXPECT_NOT: ⬇️  下游

### Case 19.3: 只看下游
CMD: raptor-prod topo-api -a com.sankuai.raptor.dw.openapi -m /raptor/dw/openapi/event/meta/types -d down
EXPECT: ⬇️  下游（我调了谁）
EXPECT_NOT: ⬆️  上游

### Case 19.4: JSON 输出
CMD: raptor-prod topo-api -a com.sankuai.raptor.dw.openapi -m /raptor/dw/openapi/event/meta/types --json
EXPECT: "methodName"
EXPECT: "parents"
EXPECT: "children"

### Case 19.5: 别名 topoapi
CMD: raptor-prod topoapi -a com.sankuai.raptor.dw.openapi -m /raptor/dw/openapi/event/meta/types
EXPECT: 接口级拓扑（仅 1 跳）

---

## 20. offline-stat（离线统计）

### Case 20.1: help [smoke]
CMD: raptor-prod ofs --help
EXPECT: appkey
EXPECT: category

### Case 20.2: --list 列出可查指标
CMD: raptor-prod ofs --list
EXPECT: 离线统计指标

### Case 20.3: --list JSON
CMD: raptor-prod ofs --list --json
EXPECT: "data"

### Case 20.4: 基本查询（month 粒度）
CMD: raptor-prod ofs -t "CLion.Version" -n "*"
EXPECT: 离线统计
EXPECT: Appkey

### Case 20.5: day 粒度
CMD: raptor-prod ofs -t "CLion.Version" -n "*" -c day
EXPECT: 离线统计

### Case 20.6: JSON 输出
CMD: raptor-prod ofs -t "CLion.Version" -n "*" --json
EXPECT: "total"
EXPECT: "statistic"

### Case 20.7: 缺 -t 报错
CMD: raptor-prod ofs -n "*"
EXPECT_FAIL: true

### Case 20.8: 别名 offline-stat
CMD: raptor-prod offline-stat --help
EXPECT: appkey
