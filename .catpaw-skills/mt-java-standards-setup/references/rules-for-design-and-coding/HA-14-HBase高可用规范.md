---
ruleType: Model Request
description: 写HBase读写/RowKey设计/批量操作时读我。规定RowKey Hash前缀散列、重要数据同步写入、不建议逐条flush、timeout/retries配置、Lion动态切流。操作HBase时必读。
category: 高可用规范
priority: medium
---

# HBase 高可用规范

## 一、说明

本规范定义了 HBase 操作的高可用标准，涵盖 RowKey 设计、写入操作、配置优化和容灾四个领域。HBase 的性能和稳定性高度依赖 RowKey 设计和操作规范，不当的操作（如逐条 flush）可能导致 RegionServer 不可用。

## 二、规则内容

### HA-HB001 [推荐] RowKey 建议散列设计

RowKey 建议使用 Hash 前缀（0000-9999）散列到不同 Region，防止热点写入。

**说明**：
- Hash 前缀建议使用 `CRC32(业务Key) % 10000` 格式化为 4 位
- 在线和离线（Hive）场景的 RowKey 设计建议一致，通过 Hive 验证数据
- 不建议使用时间戳作为 RowKey 前缀（会导致写入集中在最新的 Region）

### HA-HB003 [推荐] 写入建议安全

重要数据建议同步写入（关闭 autoFlush），异步写入建议监听异常。

**说明**：
- 重要数据（如交易记录）使用同步写入（`setAutoFlush(true)` 或手动 `flushCommits()`）
- 异步批量写入建议设置异常监听器（`BufferedMutator.ExceptionListener`）
- 不建议在循环中逐条 `flush()`（每次 flush 都是一次 RPC，严重影响性能）
- 单个 Cell 大小 ≤10MB

### HA-HB004 [推荐] 客户端配置建议优化

HBase 客户端超时和重试参数建议显式配置。

**说明**：
- `hbase.rpc.timeout` 建议 30s
- `hbase.client.meta.operation.timeout` 建议 ≤10s
- `hbase.client.retries.number` 建议 3~5 次
- `commons-io` 依赖版本建议 ≥2.4（低版本存在兼容性问题）

### HA-HB005 [推荐] HBase 建议有容灾能力

HBase 操作建议有容灾降级能力。

**说明**：
- 通过 Lion 开关控制 HBase 切流（如切到备集群或降级缓存）
- HBase 不可用时，降级路径不建议阻断核心业务
- 配置 Raptor 告警：操作延迟、失败率、RegionServer 状态

## 三、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### HA-HB001 RowKey 设计示例

#### good case:

```java
// Hash 前缀散列 RowKey
public String buildRowKey(String bizKey) {
    int hash = Math.abs(CRC32Utils.crc32(bizKey) % 10000);
    return String.format("%04d_%s", hash, bizKey);
}
// 结果示例：3721_order_123456
```

#### bad case:

```java
// 时间戳前缀 — 导致热点写入
public String buildRowKey(String bizKey) {
    return System.currentTimeMillis() + "_" + bizKey;
}
// 所有写入都集中在最新时间段的 Region
```

## 四、规范执行要点

- ✗ 不建议使用时间戳作为 RowKey 前缀
- ✗ 不建议在循环中逐条 flush
- ✗ 不建议单个 Cell 超过 10MB
- ✗ 不建议不配置 HBase 容灾降级
