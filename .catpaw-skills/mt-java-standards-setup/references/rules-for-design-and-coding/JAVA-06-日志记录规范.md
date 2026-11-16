---
ruleType: Model Request
description: 写日志(log.info/error/warn)或配置log4j2时读我。规定ERROR仅用于需人工介入系统异常/WARN可自动恢复/INFO关键业务节点、traceId自动透传、业务标识显式输出、异常必须传异常对象、密码/Token/手机号/身份证脱敏(规则见SEC-02)。打日志时必读。
category: Java编码规范
priority: high
---

# Java日志记录规范

## 一、说明

本规范定义了Java日志记录的完整标准，涵盖日志框架配置、日志级别使用、日志格式规范和敏感信息处理。统一的日志规范能够提高系统可维护性，便于故障排查和系统监控。

**可观测性大盘（Metrics 埋点/Trace 全链路/告警配置）规范详见 `HA-02`。**

## 二、规则内容

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### N001 [强制] 日志配置规范

统一使用XML形式的配置文件，文件名为 `resources/log4j2.xml`。

**说明**：
- 磁盘appender统一使用XMDFileAppender
- 远程日志统一使用scribeAppender
- **远程日志上报必须使用 `AsyncScribe`，禁止将 `Async` 与 `Scribe` 组合使用**（`<Scribe>` 外包裹 `<Async>` 的方式会阻塞日志线程）；`AsyncScribe` 应配置 `blocking="false"`
- 默认按天&按512M文件大小切分日志
- 默认最多保留30个日志文件
- 使用非阻塞模式（`blocking="false"`）

#### good case:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration status="info">
    <appenders>
        <!--默认按天&按512M文件大小切分日志，默认最多保留30个日志文件，非阻塞模式-->
        <XMDFile name="infoAppender" fileName="info.log" sizeBasedTriggeringSize="512M" rolloverMax="30">
            <Filters>
                <ThresholdFilter level="warn" onMatch="DENY" onMismatch="NEUTRAL"/>
                <ThresholdFilter level="info" onMatch="ACCEPT" onMismatch="DENY"/>
            </Filters>
        </XMDFile>
        <XMDFile name="warnAppender" fileName="warn.log" sizeBasedTriggeringSize="512M" rolloverMax="30">
            <Filters>
                <ThresholdFilter level="error" onMatch="DENY" onMismatch="NEUTRAL"/>
                <ThresholdFilter level="warn" onMatch="ACCEPT" onMismatch="DENY"/>
            </Filters>
        </XMDFile>
        <XMDFile name="errorAppender" fileName="error.log" sizeBasedTriggeringSize="512M" rolloverMax="30">
            <ThresholdFilter level="error" onMatch="ACCEPT" onMismatch="DENY"/>
        </XMDFile>
        <!--日志远程上报：必须使用 AsyncScribe，禁止 Async + Scribe 组合-->
        <AsyncScribe name="ScribeAsyncAppender" blocking="false">
            <LcLayout/>
        </AsyncScribe>
        <CatAppender name="catAppender"/>
    </appenders>
    <loggers>
        <logger name="scribe" level="info" additivity="false">
            <appender-ref ref="ScribeAsyncAppender"/>
        </logger>
        <root level="info">
            <appender-ref ref="infoAppender"/>
            <appender-ref ref="warnAppender"/>
            <appender-ref ref="errorAppender"/>
            <appender-ref ref="catAppender"/>
            <appender-ref ref="ScribeAsyncAppender"/>
        </root>
    </loggers>
</configuration>
```

---

### N002 [强制] 日志级别使用规范

日志级别必须按场景正确使用，禁止滥用 ERROR 级别。

**说明**：

| 级别 | 适用场景 | 禁止用于 |
|------|---------|---------|
| ERROR | 需要人工介入的系统异常（数据库不可用、OOM、关键 RPC 彻底失败） | 可预期的业务分支（用户不存在、参数校验失败） |
| WARN | 系统可自动恢复的异常（降级触发、重试成功、缓存 miss 回源） | 正常的业务流程 |
| INFO | 关键业务节点流水（订单创建、支付完成） | 高频接口的每次调用（日志风暴） |
| DEBUG | 调试信息 | 生产环境不应输出 |

#### good case:

```java
// ERROR：系统异常，需要人工介入
log.error("DB connection failed, orderId={}", orderId, e);

// WARN：可自动恢复
log.warn("recommend service degraded, fallback to default, userId={}", userId);

// INFO：关键业务节点
log.info("order created, orderId={}, userId={}", orderId, userId);
```

#### bad case:

```java
// 错误：业务分支用 ERROR，会导致告警风暴
log.error("user not found, userId={}", userId);

// 错误：高频接口每次调用都打 INFO，日志风暴
for (Order order : orders) {
    log.info("processing order: {}", order); // 可能产生百万条日志
}
```

---

### N003 [强制] 日志格式规范（traceId 与业务标识）

所有日志必须包含 traceId 和关键业务标识，异常日志必须打印完整堆栈。

**说明**：
- traceId 通过 Mtrace 框架自动注入到 MDC，日志框架会自动输出，无需手动添加
- 异常日志必须传入异常对象 `log.error("msg", e)`，**禁止仅打印 `e.getMessage()`**
- 关键业务标识（orderId、userId 等）必须显式输出在日志中

#### good case:

```java
// 包含业务标识 + 完整异常堆栈
log.error("createOrder failed, orderId={}, userId={}", orderId, userId, e);

// 包含业务标识的 WARN
log.warn("stock insufficient, productId={}, required={}, available={}",
    productId, required, available);
```

#### bad case:

```java
// 仅打印 message，丢失堆栈信息
log.error("createOrder failed: " + e.getMessage());

// 无任何业务标识，无法定位具体请求
log.error("system error", e);
```

---

### N004 [强制] 敏感信息脱敏规范

日志中禁止输出密码、Token、完整手机号、身份证号等敏感信息，必须脱敏处理。

**说明**：脱敏规则（各类信息的掩码方式与示例）以 `SEC-02` SEC-B001 为唯一正本，日志场景同样适用。日志中额外要求：密码/Token/密钥禁止输出（不脱敏、直接不打印）。

#### good case:

```java
// 脱敏输出
log.info("user login, phone={}", maskPhone(phone)); // 138******78
log.info("payment, cardNo={}", maskCard(cardNo));   // ****8639
```

#### bad case:

```java
// 直接输出敏感信息
log.info("user login, phone={}, password={}", phone, password);
log.info("token={}", jwtToken);
```

---

## 三、执行要求

- ✗ 禁止使用 properties 格式日志配置文件
- ✗ 禁止使用阻塞模式（影响性能）
- ✗ 禁止生产环境不配置远程日志上报
- ✗ 禁止 ERROR 级别用于可预期的业务分支
- ✗ 禁止异常日志仅打印 `e.getMessage()` 而不传入异常对象
- ✗ 禁止在循环中打印日志（可能导致日志风暴）
- ✗ 禁止日志输出密码、Token、完整手机号、身份证号
