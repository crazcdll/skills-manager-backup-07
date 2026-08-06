# 经验规则库 — CR 风险规则

> 基于近三年 COE 复盘总结提炼。
> CR 时按触发关键词 match，命中则注入对应规则到审查 prompt。
> 维护人：孟木子 | 最后更新：2026-03-17

---

## 规则分类

### CR:R1 — ID 体系 / 字段升级类

**规则 CR:R1-1：ID 升级不得删除原有传值逻辑**

- **来源 COE**：[#281065](https://coe.mws.sankuai.com/detail/281065) 商品ID升级-线上故障
- **触发关键词**：ID 升级、字段迁移、`newField` 替换 `oldField`、`productId`/`dealId`/`shopId`/`skuId` 字段变更
- **规则**：ID 升级类改动必须采用「新增字段赋值 + 保留原字段逻辑」的方式，不能直接删除原字段传值。下游接口若存在依赖原字段的情况，必须提前与下游服务负责人确认改造完成再上线。
- **CR 检查点**：发现 diff 中删除了原有 ID/字段的赋值逻辑，且同时新增了新字段 → **P1**，要求说明下游兼容性

---

**规则 CR:R1-2：ShopId/PoiId 加密/格式变更需全链路评估**

- **来源 COE**：[#270776](https://coe.mws.sankuai.com/detail/270776) shopid加密导致下单失败
- **触发关键词**：shopId 加密、ID 格式变更、encode、加密工具类、统一技改
- **规则**：涉及 ShopId/PoiId 等关键交易 ID 的格式变更（加密、编码转换等），需要评估全链路影响，包括：商品链接、分销缓存、页面按钮、下单、结算等所有环节。不能以 appkey 维度粗放推进，涉资链路必须单独专项 review。
- **CR 检查点**：发现 ID 字段的序列化/格式相关改动 → 要求提交人说明全链路评估范围

---

### CR:R2 — 空值/NPE 类

**规则 CR:R2-1：字段拼接前必须判空**

- **来源 COE**：[#280887](https://coe.mws.sankuai.com/detail/280887) poi页地址电话栏导航拼接null字段
- **触发关键词**：字符串拼接（`+`）、`String.format`、`StringBuilder.append`，操作数涉及从外部传入的字段
- **规则**：任何字符串拼接操作，拼接对象若来自外部数据（DB、接口返回、Map 取值），必须先判空，不能直接拼接 null。
- **CR 检查点**：发现 `field1 + field2` 且 field1/field2 可能为 null → **P1**

---

**规则 CR:R2-2：JSON 反序列化异常需要有 fallback**

- **来源 COE**：[#277807](https://coe.mws.sankuai.com/detail/277807) 团详主接口JsonSyntaxException
- **触发关键词**：`JSON.parseObject`、`Gson.fromJson`、`ObjectMapper.readValue`、跳链参数解析
- **规则**：对来自外部（跳链、接口入参、DB 存储字段）的 JSON 字符串反序列化，必须有 try-catch + 降级逻辑。不能让反序列化异常直接传播到主链路。
- **CR 检查点**：发现裸 JSON 解析无异常处理 → **P1**

---

### CR:R3 — 业务逻辑/条件覆盖类

**规则 CR:R3-1：新逻辑必须覆盖所有状态/场景**

- **来源 COE**：[#277633](https://coe.mws.sankuai.com/detail/277633) 无忧通服务后用户退款逻辑异常
- **触发关键词**：退款、状态机、`if (status == X)`、业务状态枚举
- **规则**：涉及退款、状态流转、订单处理的改动，单测必须覆盖所有状态分支。新逻辑上线前须配合开关（Lion 配置），方便快速切换。
- **CR 检查点**：退款/状态相关改动无开关保护 → **P2**；单测明显缺失状态分支 → **P1**

---

**规则 CR:R3-2：不要轻信代码注释，存疑必须主动确认**

- **来源 COE**：[#277944](https://coe.mws.sankuai.com/detail/277944) KTV订单上的履约时间超出商品实际适用时间
- **触发关键词**：时间计算、日期范围、有效期、`startTime`/`endTime`/`validTime`/`expireTime`
- **规则**：时间相关计算逻辑（履约时间、有效期、过期判断），不能依赖注释理解语义，必须通过实际用例验证。参数含义必须明确，非必要参数不传递，使用时需做校验。
- **CR 检查点**：时间字段语义不明确、参数用途仅靠注释说明 → **P2**

---

**规则 CR:R3-3：金额单位与币种转换必须显式标注且双向兼容**

- **来源 COE**：[#155860](https://coe.mws.sankuai.com/detail/155860) 售价由元改分未兼容老格式，日均~100商品出清失败、[#117234](https://coe.mws.sankuai.com/detail/117234) 海外酒店币种错配，CNY 支付 USD 价格、[#212511](https://coe.mws.sankuai.com/detail/212511) 售价0.02元团单用户实付0.1元，价格精度换算错误、[CaseStudy-20180510](https://km.sankuai.com/page/40925042) 客户端元改分，返券缓存新老格式不兼容
- **触发关键词**：`fenToYuan`、`yuanToFen`、`divide(BigDecimal.valueOf(100))`、`multiply(BigDecimal.valueOf(100))`、`/ 100`、`* 100`、`MoneyUtil`、`PriceUtil`、`amount`/`price`/`money`/`discount`/`fee` 字段的赋值或类型变更、接口返回值单位变更（元↔分↔万元）、币种转换（CNY↔USD等）、`Currency`/`currencyCode` 字段
- **规则**：涉及金额单位转换（分↔元↔万元）或币种转换的代码变更，必须：
  1. **显式标注单位**：金额字段/参数/返回值必须通过命名或注释标明单位（分/元/万元），禁止隐性约定
  2. **双向兼容**：单位切换时必须兼容存量数据的旧格式（缓存、DB 历史数据、下游接口），不能仅处理新格式
  3. **精度安全**：使用 `BigDecimal` 并显式指定 `RoundingMode`，禁止用 `double`/`float` 做金额运算
  4. **币种隔离**：外币与人民币金额不能混用同一字段，必须通过 `currencyCode` 等标识字段区分
- **CR 检查点**：
  - 金额字段单位变更（元改分/分改元）且无兼容存量数据 → **P0**
  - 金额运算使用 `double`/`float` → **P1**
  - 外币金额无币种标识字段 → **P1**
  - 金额字段参与 RPC 返回值变更但未同步更新接口文档/Mock → **P2**

---

### CR:R4 — 接口/配置变更类

**规则 CR:R4-1：接口调用变更需提前与服务负责人确认**

- **来源 COE**：[#281065](https://coe.mws.sankuai.com/detail/281065)、[#281353](https://coe.mws.sankuai.com/detail/281353)
- **触发关键词**：调用下游接口参数变更、新增/删除接口字段、`serviceProxy.xxx()` 调用
- **规则**：对下游接口调用的改动（新增参数、修改参数语义、删除字段），需要提前与下游服务负责人确认对方是否已完成适配，不能单方面上线。
- **CR 检查点**：发现下游接口调用有参数变更但 PR 描述无说明 → 要求提交人补充说明

---

**规则 CR:R4-2：配置变更（跳链/URL）需全面自测**

- **来源 COE**：[#280532](https://coe.mws.sankuai.com/detail/280532) iOS点评侧美发列表搜索结果页跳转异常
- **触发关键词**：跳链配置、URL 拼接、encode/decode、Lion 配置变更
- **规则**：涉及跳链类配置的改动，必须验证到完整路径（列表页→搜索结果页→详情页），不能只验证某一个环节。URL 编码问题需要有专项 case 验证。
- **CR 检查点**：跳链相关配置改动，PR 中未说明测试范围 → **P2**

---

### CR:R5 — 性能/资源类

**规则 CR:R5-1：静态集合/缓存的内存泄漏风险**

- **来源 COE**：[#282036](https://coe.mws.sankuai.com/detail/282036) 商品页commonmodule服务大量Reject（内存泄漏→FullGC）
- **触发关键词**：`static List/Map/Set`、`@Autowired` 单例 Bean 中的成员集合、Lambda 在 Bean 中的使用、Lion 监听器注册
- **规则**：单例 Bean 中的成员变量若为集合类型且会累积数据，必须有清理机制。Lambda 表达式在单例 Bean 中使用时注意隐式捕获 this 引用。Lion 监听器注册必须避免重复注册。
- **CR 检查点**：单例 Bean 中出现 `static` 集合或无界缓存 → **P1**

---

**规则 CR:R5-2：批量写操作需评估 DB 主从延迟影响**

- **来源 COE**：[#279592](https://coe.mws.sankuai.com/detail/279592) 群发任务产生的批量写操作导致集群主从延迟故障
- **触发关键词**：批量写入、`batchInsert`、`for` 循环中的 DB 写操作、定时任务、群发消息
- **规则**：批量写操作必须评估对 DB 集群主从延迟的影响，高频批量写需有限流/分批机制，避免因写入过于密集导致从库延迟，影响读操作。
- **CR 检查点**：循环内 DB 写操作无限流 → **P1**；批量任务无分批控制 → **P2**

---

### CR:R6 — 调试代码/遗留逻辑类

**规则 CR:R6-1：直连/特殊路由代码上线前必须清除**

- **来源 COE**：[#278683](https://coe.mws.sankuai.com/detail/278683) 综POI搜猜渲染服务rc链路流量突增
- **触发关键词**：直连、指定 set、`env == "rc"`、`host == "xxx"`、测试代码标记
- **规则**：PR 中不允许包含直连特定机器/指定 set/RC 环境特殊路由的代码，上线前必须清除。
- **CR 检查点**：发现硬编码的 IP/host/env 判断 → **P0**（零容忍）

---

## 触发规则映射

| 关键词 | 触发规则 |
|--------|---------|
| ID 升级、字段迁移、新旧字段并存 | CR:R1-1 |
| shopId/poiId 加密、encode | CR:R1-2 |
| 字符串拼接 `+`、`format`，操作数可能为 null | CR:R2-1 |
| JSON.parseObject、Gson.fromJson，无 try-catch | CR:R2-2 |
| 退款逻辑、状态机变更 | CR:R3-1 |
| 时间/日期/有效期计算 | CR:R3-2 |
| 金额单位转换、fenToYuan/yuanToFen、币种转换 | CR:R3-3 |
| 下游接口参数变更 | CR:R4-1 |
| 跳链配置、URL encode | CR:R4-2 |
| static 集合、单例 Bean 成员集合、Lion 监听器 | CR:R5-1 |
| 批量写、for 循环 DB 写入 | CR:R5-2 |
| 直连、指定 set、硬编码 IP/host | CR:R6-1 |
