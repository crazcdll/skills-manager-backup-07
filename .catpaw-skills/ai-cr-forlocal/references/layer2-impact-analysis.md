# Layer 2 变更影响分析指南（Step 2B）

### 3B. Layer 2 — 变更影响（**强制执行，不可跳过**）

**核心思路：diff 只告诉你"改了什么"，Layer 2 要告诉你"改了之后，谁受影响"。**

两个方向，哪个被 diff 触发就执行哪个（可同时触发）：

---

#### 🔀 路径选择

| 条件 | 执行路径 |
|------|---------|
| `$GITNEXUS_AVAILABLE=true` | **GitNexus 主路径**（下方 3B-GN 系列，图谱已全量重建，100% 反映当前分支） |
| `$GITNEXUS_AVAILABLE=false` | **grep fallback 路径**（下方 3B-1、3B-2，即原版逻辑） |
| GitNexus 部分查询超时 | 已完成结果保留 + 降级 grep 补充 |

---

#### 3B-GN. GitNexus 主路径（三阶段）

**阶段一：精确影响分析**（替代触发器 + grep）

```bash
cd "$LOCAL_REPO_PATH"
LAYER2_RESULT_DIR="/tmp/cr_layer2_results"
mkdir -p "$LAYER2_RESULT_DIR"

for each changed_symbol from Step 2E:
  # 执行 depth=2 影响分析，结果写入文件
  gitnexus impact "{symbol}" -d upstream --depth 2 > "$LAYER2_RESULT_DIR/{symbol}.impact" 2>/dev/null
  
  # 解析输出，分为四层：
  # ├── L1 CHANGED: 直接变更（已知）
  # ├── L2 WILL_BREAK: 直接调用方（等同 grep d=1 但更精确）
  # ├── L3 LIKELY_AFFECTED: 间接调用方 d=2~3（全新能力！grep 做不到）
  # └── L4 SCHEMA_CHANGED: DTO 字段传播链（全新能力！）
```

- L2 WILL_BREAK → **强制精读消费方**，不兼容直接 P0
- L3 LIKELY_AFFECTED → 精读方法体，评估间接影响，不兼容 P1
- L4 SCHEMA_CHANGED → 检查序列化/反序列化兼容性
- 单次 CLI 调用超时 10s，超时走 grep fallback

**阶段二：消费方代码精读**（替代 grep + 猜测）

```bash
cd "$LOCAL_REPO_PATH"
for each impacted_symbol with confidence > 0.7:
  # 获取受影响符号的完整上下文（方法体 + 参数 + 返回值）
  gitnexus context "{impacted_symbol}" --content 2>/dev/null
  # → 直接判断兼容性，无需 grep 找文件再 cat
```

**阶段三：数据流追踪**（全新能力，grep 无平替）

```bash
cd "$LOCAL_REPO_PATH"
for each SCHEMA_CHANGED symbol (DTO/VO 字段变更):
  # 用 Cypher 查询追踪字段的数据流传播链
  gitnexus cypher "MATCH (s)-[:CodeRelation {type:'CALLS'}*1..3]->(t) WHERE s.name = '{fieldName}' RETURN t.name, t.filePath" 2>/dev/null
  # → 追踪字段从 A 传到 B 传到 C 的完整数据流
  # → 发现"A 加了字段但 C 的 Converter 没处理"
```

**阶段一~三完成后**，合并去重所有发现的影响点，输出影响汇总表。

**播报**：
```
✅ Step 3B (GitNexus)：
   L2 直接影响: {n} 个 symbols
   L3 间接影响: {m} 个 symbols (d=2~3)
   L4 数据流: {k} 条传播链
   已精读消费方: {p} 个
```

**降级**：GitNexus 任一阶段超时/失败 → 已完成结果保留，未完成部分降级走下方 3B-1/3B-2 grep fallback。

---

#### grep fallback 路径

**3B-1「我新增了东西，谁在消费我？」— 适用场景举例**

- 新增枚举值（如 `ProductFilterTypeEnum.TECHNICIAN_XXX`）→ 哪些 switch/if 没有覆盖这个新值？
- 新增 DTO 字段（如 `filteredProductIds`）→ 哪些 Converter/序列化逻辑会读这个字段？
- 新增接口方法 / 公共方法 → 现有实现类是否都已同步？

**操作（本地模式）：**

```bash
LAYER2_RESULT_DIR="/tmp/cr_layer2_results"
mkdir -p "$LAYER2_RESULT_DIR"

# 本地模式：grep -r 在本地文件系统反查引用
# 搜索字段名/枚举值/方法名
# 结果写入 $LAYER2_RESULT_DIR/ 供 Step 3/4 读取
grep -r "{从diff提取的实际名称}" "$LOCAL_REPO_PATH/src/main/java" \
  --include="*.java" -l > "$LAYER2_RESULT_DIR/{symbol}.files" 2>/dev/null
grep -r "{名称}" "$LOCAL_REPO_PATH/src/main/java" \
  --include="*.java" -n > "$LAYER2_RESULT_DIR/{symbol}.lines" 2>/dev/null
```

结果中每个命中文件，精准读 1~3 个相关方法，判断「消费方是否兼容新增内容」。**发现不兼容 → 直接升级 P1。**

> **降级处理**：grep 未命中时，说明仓库内无引用，可能是纯新增逻辑，在 CR 结论中注明"本地反查，无跨服务引用确认"。

---

**3B-2「我新调用了别人，被调用方的行为是什么？」— 适用场景举例**

- 新增 RPC/Pigeon 调用（新增 `@Reference` 注入或新增调用语句）→ 被调用接口在不同入参下返回什么？
- 新增对外部 Wrapper/Client 的方法调用 → 该方法的异常行为、null 返回、超时表现是什么？

> **触发条件**：diff 中出现新增的外部服务调用（新注入依赖 或 新增调用语句）

**禁止猜测被调用接口的语义**，必须实际读取：
1. 用 grep -r 在本地文件系统找到被调用接口的实现
2. 读接口定义：方法签名 + JavaDoc + 返回值 DTO 的字段注释
3. 确认在当前入参组合下的实际行为（尤其是空值/异常路径）
4. 重点检查：返回值字段的语义（特别是携带多种 ID 的字段，要确认装的是哪种 ID）

---

## 全量并行方案

所有 symbol 一次性并发反查，无批次限制。

### 方案

- `xargs -P 8` 全量并发（8 个并行进程）
- 单个 symbol 查询超时 10s（`timeout 10` 包裹），超时跳过
- 无需分批等待，全部完成后直接汇总

### 示例代码

```bash
#!/usr/bin/env bash
# 全量并行 Layer 2 反查

RESULT_DIR="/tmp/cr_layer2_results"
mkdir -p "$RESULT_DIR"

# 从 JSON 提取 symbol 列表后全量并发
cat /tmp/cr_changed_symbols.list | grep -v '^$' | xargs -P 8 -I{} sh -c 'timeout 10 grep -rn "$1" "$LOCAL_REPO_PATH/src/main/java" --include="*.java" > "'$RESULT_DIR'/$1.grep" 2>/dev/null' _ {}

echo "=== Layer 2 反查完成 ==="
ls "$RESULT_DIR" | wc -l
```

