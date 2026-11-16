# 缺陷分类体系

## 缺陷类别（defect_class）

用于对 AI-CR 检出的问题进行标准化分类，支撑覆盖矩阵采样。

### C1: NPE / 空指针

**关键特征词**：NPE、NullPointerException、空指针、判空、null、Optional、Objects.requireNonNull、拆箱

**典型模式**：
- Map.get() 返回值直接拆箱（Integer → int）
- 链式调用无判空（a.getB().getC()）
- 集合操作未判空（list.size() / list.stream()）
- Optional 不当使用（.get() 无 isPresent）

**对应 Skill 规则**：zero-tolerance-checklist NPE 章节

---

### C2: 资源泄漏 / 超限

**关键特征词**：资源泄漏、连接未释放、未关闭、close、try-with-resources、大 Value、批量、超限、OOM

**典型模式**：
- Squirrel/Redis 大 Value（> 10KB）
- 数据库连接未关闭
- InputStream/OutputStream 未 close
- 批量 SQL 无分批（> 500 条）
- 集合无限增长（static Map 无淘汰）

**对应 Skill 规则**：zero-tolerance KV/SQL 章节、stability RM-*

---

### C3: 逻辑错误 / 条件遗漏

**关键特征词**：逻辑错误、条件遗漏、分支遗漏、switch default、枚举覆盖、ID 混用、状态机、边界条件

**典型模式**：
- 枚举新增值但 switch 无 default
- 状态机状态覆盖不全
- ID 体系混用（shopId/poiId/spuId 混淆）
- 边界条件未处理（空集合、负数、溢出）
- 布尔表达式短路逻辑错误

**对应 Skill 规则**：coe-rules R1-1/R1-2/R3-1/R3-2

---

### C4: 并发 / 线程安全

**关键特征词**：并发、线程安全、synchronized、volatile、ConcurrentModificationException、单例、共享变量、竞态

**典型模式**：
- 单例 Bean 成员变量（非 final 集合）
- SimpleDateFormat 线程共享
- HashMap 多线程写入
- double-check locking 错误
- 非原子操作的 check-then-act

**对应 Skill 规则**：zero-tolerance CME 章节、stability CC-*

---

### C5: 安全 / 注入

**关键特征词**：SQL 注入、XSS、SSRF、硬编码、密码、凭证、token、secret、直连

**典型模式**：
- SQL 字符串拼接（非 PreparedStatement）
- 硬编码 IP / 密码 / Token
- 直连特定 set（绕过 OCTO 路由）
- 反序列化漏洞（不受信输入直接反序列化）
- 日志打印敏感信息

**对应 Skill 规则**：stability SEC-*、coe-rules R6-1

---

### C6: 性能退化

**关键特征词**：性能、N+1、循环内、批量查询、全量查询、无分页、串行、同步阻塞、超时

**典型模式**：
- 循环内 DB/RPC 调用（N+1）
- 无分页全量查询
- 无限增长集合（内存泄漏）
- 同步调用应改异步
- 缓存穿透（无 null 值缓存）
- 串行可并行的操作

**对应 Skill 规则**：performance-checklist DB/CACHE/COLL、coe-rules R5-1/R5-2

---

### C7: 跨仓库兼容

**关键特征词**：跨仓库、DTO、序列化、反序列化、FAIL_ON_UNKNOWN、上下游、接口变更、版本兼容、上线顺序

**典型模式**：
- DTO 新增字段但消费方未适配
- 反序列化配置不兼容（FAIL_ON_UNKNOWN_PROPERTIES）
- 枚举新增值导致下游解析失败
- 接口签名变更但调用方未更新
- 上线顺序依赖（先上下游再上上游）

**对应 Skill 规则**：Cross-Repo CX-01~08

---

## 上下文层级（context_layer_required）

标注检出此缺陷**至少**需要哪一层上下文。

| 层级 | 含义 | 判定标准 |
|------|------|---------|
| `L1_diff_visible` | 仅看 diff 即可发现 | 问题完全存在于新增/修改的代码行中，无需看上下文 |
| `L2_intra_repo_search` | 需仓库内搜索引用 | 需要 grep/搜索同仓库其他文件才能判定（如消费方 switch 覆盖） |
| `L3_cross_repo_or_business` | 需跨仓库或业务语义 | 需要搜索其他仓库、或结合 ONES 需求/spec 文档才能判定 |

**判定逻辑**：
- 如果 AI-CR 文档中显示使用了 `code-repo-search` → 至少 L2
- 如果文档中提到跨仓库搜索或 CX-0x 规则 → L3
- 如果只引用了 diff 中的代码 → L1

---

## 触发类型（trigger_type）

映射到 Skill 的审查模型层级。

| 类型 | 对应 Step | 说明 |
|------|----------|------|
| `zero_tolerance` | Step 4B | P0 零容忍（NPE、CME、SQL注入等） |
| `stability` | Step 4C | P1 稳定性（资源泄漏、超时、线程安全等） |
| `coding_standard` | Step 4D | P2 规范（命名、重复代码、设计模式等） |
| `performance` | Step 4E | P3 性能建议 |
| `cross_repo` | Step 5 | 跨仓库兼容性（CX 层规则） |

---

## 自动分类提示词

对检出项描述做自动分类时，使用以下判定逻辑：

```
1. 扫描描述中的关键特征词 → 初步判定 defect_class
2. 检查 AI-CR 文档中该项引用了哪些 Step → 判定 trigger_type
3. 检查是否使用了 code-repo-search / 跨仓库搜索 → 判定 context_layer
4. 如果关键词命中多个类别 → 取与 severity 最匹配的类别
   - P0 → 优先 C1(NPE)/C4(并发)/C5(安全)
   - P1 → 优先 C2(资源)/C3(逻辑)/C6(性能)
   - CX 规则 → C7
```
