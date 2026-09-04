# 维度 3：代码可读性（8%，L3）

**核心原则**：AI 靠代码本身理解逻辑，过期注释比没有注释更危险（会误导 AI）。
**本地可理解性要求**：评估不依赖全仓库 grep 统计覆盖率，而是通过「本地可理解性测试（LCT）」——仅凭函数签名与类型/注释，AI 能否推断该函数的意图、参数含义、返回值和失败条件。必须读实现体才能理解的，视为本地可理解性不合格。

## 评估标准（通用）

- [ ] 类/方法/变量命名自解释（禁止 temp/a/b/obj/res/flag1/flag2）
- [ ] **本地可理解性测试（LCT）通过**：从核心业务类中抽取 3 个有代表性的公开方法/函数，仅读签名和类型/注释（不读实现体），能够推断方法用途、参数业务含义、返回值含义、失败/异常条件
- [ ] 类型/注释覆盖充分（不缺项、不写废话）
- [ ] **无过期误导性注释**（注释与代码实现一致）
- [ ] 单文件行数合理（超大文件影响可读性）

## LCT 操作规程

**抽样方式**：在核心业务类中（非工具类、非 CRUD 生成代码），选取 3 个代表性公开方法/函数，优先选择：
1. 一个核心业务流程入口（如 createOrder、useCheckout）
2. 一个带条件分支的查询/计算方法
3. 一个跨模块的编排/组合方法

**评估方式**：对每个方法，**只读函数签名行 + 类型声明 + 其上方的注释块**，不展开实现体，判断：

| 判断维度 | 可推断 | 需读实现体 |
|---------|--------|-----------|
| 方法的业务用途是什么 | | |
| 各参数的业务含义是什么 | | |
| 返回值代表什么（成功/失败语义） | | |
| 在什么情况下抛出异常/返回错误 | | |

**LCT 评级**：
- **高**：3 个方法中 ≥2 个，四项判断维度均可推断
- **中**：3 个方法中 ≥2 个，至少 2 项判断维度可推断
- **低**：多数方法需要读实现体才能理解任意判断维度

### LCT 评分锚点示例（减少主观歧义）

**高分样本（LCT 评级"高"，对应 90+ 分）**：
```java
/**
 * 创建订单并锁定库存。
 * 若用户余额不足或库存不足，抛出 BusinessException；
 * 若商品已下架，抛出 ProductOffShelfException。
 *
 * @param userId  下单用户 ID（不能为空）
 * @param skuId   商品 SKU ID
 * @param qty     购买数量（必须 > 0，上限 99）
 * @return 创建成功的订单 ID
 * @throws BusinessException 余额不足或库存不足
 * @throws ProductOffShelfException 商品已下架
 */
public Long createOrder(Long userId, Long skuId, int qty)
```
→ 四个判断维度全部可推断，无需读实现体。

**中分样本（LCT 评级"中"，对应 75–89 分）**：
```java
/**
 * 查询用户订单列表。
 *
 * @param userId 用户 ID
 * @param status 订单状态
 * @return 订单列表
 */
public List<Order> getOrders(Long userId, Integer status)
```
→ 用途和参数可推断；但返回值（空列表 vs null 的语义）和异常条件不可推断，需读实现体。

**低分样本（LCT 评级"低"，对应 <75 分）**：
```java
// 处理订单
public Result handle(Map<String, Object> params)
```
→ 四个判断维度均不可推断：不知道"处理"是什么操作，params 内容未知，Result 含义未知，异常条件未知。

**前端 Hook 高分样本**：
```typescript
/**
 * 管理购物车商品的增删改操作。
 * 
 * @param cartId - 购物车 ID，传 undefined 时自动创建新购物车
 * @returns items: 当前购物车商品列表；addItem/removeItem/updateQty: 操作函数；
 *          loading: 操作进行中；error: 最近一次操作的错误信息（操作成功后自动清空）
 */
export function useCart(cartId: string | undefined): {
  items: CartItem[];
  addItem: (skuId: string, qty: number) => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
  updateQty: (itemId: string, qty: number) => Promise<void>;
  loading: boolean;
  error: Error | null;
}
```
→ 四个判断维度全部可推断。

## 评分细则（通用）

| 分段 | 描述 | 量化判定依据 |
|------|------|------------|
| 90–100 | 命名规范，LCT 评级"高"（≥2 方法四维全推断），无过期注释，无超大文件 | 对照"高分样本"：签名+注释即可完整推断四维 |
| 75–89 | LCT 评级"中"，命名基本规范，偶有注释缺项 | 对照"中分样本"：2–3 维可推断，1–2 维需读实现体 |
| 60–74 | LCT 评级"低"但部分方法可推断，存在命名问题或超大文件 | 对照"低分样本"：仅用途可推断，参数/返回值/异常均不可推断 |
| <60 | LCT 基本不通过（签名和注释几乎无法帮助推断业务意图），命名混乱或充斥误导性注释 | 签名无注释 + 命名如 handle/process/do/temp，四维均不可推断 |

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| LCT 抽样目标 | `find . -path "*/service/*Service.java" -not -path "*/test/*" 2>/dev/null \| head -10` | `find . \( -path "*/hooks/use*.ts" -o -path "*/hooks/use*.tsx" \) -not -path "*/node_modules/*" 2>/dev/null \| head -10; find . -path "*/utils/*.ts" -not -path "*/node_modules/*" 2>/dev/null \| head -5` |
| LCT 执行（读签名+注释） | `find . -path "*/service/*Service.java" -not -path "*/test/*" 2>/dev/null \| head -3 \| while read f; do echo "=== LCT: $f ==="; awk '/\/\*\*/{in_javadoc=1;block=""} in_javadoc{block=block"\n"$0} /\*\//{if(in_javadoc){pending_block=block;in_javadoc=0}} /public [^{]+\(/ && !in_javadoc && pending_block!=""{print pending_block; print $0; print "---"; pending_block=""}' "$f" \| head -80; done` | `find . \( -path "*/hooks/use*.ts" -o -path "*/utils/*.ts" \) -not -path "*/node_modules/*" 2>/dev/null \| head -3 \| while read f; do echo "=== LCT-FE: $f ==="; grep -n "export\|/\*\*\|@param\|@returns\|@throws\|interface \|type \|: " "$f" \| head -30; done` |
| 命名检查（无意义变量名） | `grep -rn "\btemp\b\|\bobj\b\|\bflag[0-9]\?\b\|\bres\b\|\btmp\b" . --include="*.java" 2>/dev/null \| grep -v "test\|Test" \| wc -l` | `grep -rn "\btemp\b\|\bobj\b\|\bflag[0-9]\?\b\|\btmp\b\|\bdata\b" . --include="*.ts" --include="*.tsx" 2>/dev/null \| grep -v "node_modules\|test\|spec" \| wc -l` |
| 超大文件检查 | `find . -name "*.java" -type f -exec wc -l {} \; \| awk '$1 > 500 {print}' \| sort -rn \| head -10` | `find . \( -name "*.tsx" -o -name "*.ts" \) -not -path "*/node_modules/*" -not -path "*/dist/*" -exec wc -l {} \; 2>/dev/null \| awk '$1 > 500 {print}' \| sort -rn \| head -10` |
| any 滥用（前端专用） | 无 | `grep -rn ": any\b\|as any\b" . --include="*.ts" --include="*.tsx" 2>/dev/null \| grep -v "node_modules\|test\|spec\|\.d\.ts" \| wc -l` |

## 结构性差异说明

- **后端 LCT**：抽样 Service 方法，检查 Javadoc（`@param`/`@return`/`@throws`）；单文件行数阈值 < 500 行
- **前端 LCT-FE**：抽样 Hook 或工具函数，检查 TypeScript 类型签名 + JSDoc（`@param`/`@returns`）；前端无 `@throws` 惯例，以 Promise 错误类型或 `@throws` JSDoc 替代；组件文件行数阈值 < 500 行，Hook 文件行数阈值 < 300 行
