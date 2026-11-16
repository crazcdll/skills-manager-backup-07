# W8：基础实体获取

根据用户已有的 ID，选择对应路径完成 POI、供应商、合同、房型的构造，最终输出上单所需的全套 ID。

---

## 快速选路

| 你手上有什么 | 走哪条路径 |
|------------|----------|
| 什么都没有 | [路径A](#路径a-完全空白) |
| 只有 poiId | [路径C](#路径c-仅有-poiid) |
| 只有 partnerId | [路径D](#路径d-仅有-partnerid) |
| 已有 partnerId + poiId | [路径B](#路径b-已有-partnerid--poiid) |

四条路径最终都汇入[公共段 P1～P4](#公共段-p1p4)，输出完整 ID 集合。

---

## 原子操作（各路径复用）

### 创建 POI
```bash
python3 factory/infra/create-poi.py [--city 北京] [--overseas] [--category-id 352]
# 境外默认 category-id=387
# 输出：poiId
```

### 私海认领 ⚠️ 每次新 poiId 必做
```bash
python3 factory/infra/claim-poi.py --poi-id <poiId>
# 必须在「绑定门店」前完成，否则 bind 报"不在私海"
# 输出：认领到 crstest（empId=2196240）
```

### 绑定门店
```bash
python3 factory/infra/bind-partner-poi.py --poi-id <poiId> --partner-id <partnerId>
# 输出：partnerId + poiId 就绪，可进入公共段
```

### 创建供应商
```bash
python3 factory/infra/create-partner.py --poi-id <poiId> [--partner-type 2] [--entity-type 0] [--currency CNY] [--cooperation-type 2]
# partner-type: 2=境内自采预付 | 3=境外 | 9=境内女娲
# entity-type: 0=酒店集团 | 2=单体酒店（通兑超团必填）
# cooperation-type: 1=直连 | 2=团购+预订合同（默认） | 4=现付 | 6=预付包销
# ⚠️ 工具49 异步，供应商约需 1 分钟就绪（公共段 P1 会自动等待）
# 输出：partnerId + platformContractId（数字）
```

> **合作类型判断规则**：
> - 用户**未明确说明**合作类型时，一律按默认 `cooperation-type=2`（团购+预订合同）处理，这就是通常语义上的"预付"，不要主动问、不要臆测成其他类型。
> - 只有用户**明确要求"预付包销"**时，才使用 `cooperation-type=6`（预付包销）新建/筛选供应商。
> - 若要构造**现付商品**，创建供应商时必须显式传 `--cooperation-type 4`，不能用默认（团购+预订合同）供应商顶替。
> - 现付商品还需在创建产品时配合 `paymentType=1`（现付担保）或 `paymentType=2`（现付非担保），详见 `w1-create-fullday.md`。

### 数据池查询
固定参数：`--query-tab 1 --biz-line 20`；`--tags 107=境内供应商`（境外改 `境外供应商`）。

> **境内/境外参数说明**：`--tags 107=xxx` 取决于本次构造目标——构造**境内**商品时填 `107=境内供应商`，构造**境外**商品时填 `107=境外供应商`，与用户当前的构造意图保持一致，避免用境内供应商上境外商品或反之。
```bash
# ⚠️ 必须在 hotel_testdata_cli/ 目录下执行（scripts/utils.py 在该目录中）
MIS=$(cd "$SKILL_DIR/hotel-testdata-cli" && python3 -c "from scripts.utils import get_operator; print(get_operator())" 2>/dev/null)

# 第一阶段：优先查自己历史数据
testdata-cli query-testdata query --query-tab 1 --biz-line 20 --tags "<tags>" --mis-id "$MIS" --occupier "$MIS" --limit 5 --pretty

# count=0 时，第二阶段：查全量（不限操作人）
testdata-cli query-testdata query --query-tab 1 --biz-line 20 --tags "<tags>" --mis-id "$MIS" --limit 5 --pretty
```

常用 tags（可逗号叠加，完整列表可用 `testdata-cli query-testdata list-tags --query-tab 1 --biz-line 20` 查询）：

| tag | 含义 | 可选值 |
|-----|------|--------|
| `107` | 境内/境外 **必填** | `境内供应商` / `境外供应商` |
| `117=单体酒店` | 通兑超团必加 | — |
| `108` | 财务类型（**可精确筛选现付/预付**） | `现付` / `预付` |
| `115` | 合作类型（**可精确筛选，等价于 cooperationType**） | `团购+预订合同` / `直连合同` / `现付合同` / `预付包销合同` / `广告合同` |
| `105` | 币种 | `人民币` / `美元` / `日元` / `港元` |
| `226` | 境内价格模式 | `卖价模式` / `底价模式` |

返回字段映射：`bpCustomerId` → `partnerId` ｜ `poiIds[0]` → `poiId` ｜ `contract` → `contractNo`（字符串）｜ `contractId` → `platformContractId`（数字）

> **查询结果的处理规则**：查到数据后，返回结果中会带有各种 tags 标签值（如财务类型、合作类型、币种、价格模式等）。**这些标签值仅供展示，不影响是否可以使用的判断**——无论 tags 值是什么，只要查到了记录，就直接列出来让用户确认，由用户决定是否使用。
>
> ⚠️ **特别注意**：tags 中可能出现「是否可上单: false」，**这不代表该供应商不可用**，不要因为这个标签就跳过或排除该条数据，照常展示给用户确认。
>
> **数据池支持按现付/预付精确筛选**（2026-07-29 实测验证）：
> - 筛选**现付**供应商：`--tags "115=现付合同"` 或 `--tags "108=现付"`（可与 `107=境内供应商` 叠加）
> - 筛选**预付**供应商（用户未明确要求"预付包销"时的默认口径）：`--tags "115=团购+预订合同"`，对应 `cooperation-type=2`
> - 用户**明确要求"预付包销"**时才筛选：`--tags "115=预付包销合同"`，对应 `cooperation-type=6`；不要在普通"预付"语境下混用这个类型
> - `108=预付` 会同时匹配「团购+预订合同」和「预付包销合同」两种，语义较粗，优先用 `115=合作类型` 精确筛选
> - `customerTags` 返回结果中的「财务类型」「合作类型」字段与查询时传入的 `108`/`115` 语义完全对应，可直接作为是否满足现付/预付需求的判断依据，无需再走新建路径兜底。

### 数据池写入 ⚠️ 新建供应商后必做
> **商品创建有结果后执行**（成功或失败均需写入）。不阻断主流程；失败不影响已创建数据。
>
> **三个入参缺一不可**：
> - `--origin-customer-id`：**供应商** partnerId
> - `--contract-id`：**合同** platformContractId（数字）
> - `--poi-id`：**门店** poiId
>
> 另外必须填 `--occupier`（占用人 mis），否则别人复用时无法按占用人筛选。

```bash
python3 factory/infra/query-customer-id.py \
  --origin-customer-id <partnerId> \        # 供应商（必填）
  --contract-id <platformContractId> \      # 合同（必填）
  --poi-id <poiId> \                        # 门店（必填）
  --occupier <你的mis> \                    # 占用人（必填）
  --tag
```

---

## 路径A：完全空白

**前提**：用户没有提供任何 ID。

### Step 0 [BLOCKING]：数据池查询
目的是复用已有供应商，避免重复创建。

- **命中** → 文字列出候选，请用户确认选哪个 partnerId
  - 用户确认 → 进入**命中路径**（Step 1 起）
  - 用户拒绝 → 进入**新建路径**（Step 1 起）
- **两阶段均 count=0** → 告知用户，开始新建路径

### 命中路径（用户从数据池选了 partnerId）

**Step 1**：创建 POI → 得到 `poiId`

**Step 2**：私海认领

**Step 3**：绑定门店（新建的 poiId 与数据池 partnerId 绑定）

**[按需]** POI 资质添加（商品上线需资质时执行）

**出口** → 进入公共段 P2，携带 `partnerId / poiId`

---

### 新建路径（数据池无结果或用户拒绝复用）

**Step 1**：创建 POI → 得到 `poiId`

**Step 2**：私海认领

**Step 3**：创建供应商 → 得到 `partnerId + platformContractId`

> ⚠️ **若目标是现付商品**，本步必须显式传 `--cooperation-type 4`：
> `python3 factory/infra/create-partner.py --poi-id <poiId> --cooperation-type 4`，不要用默认参数（预付）。

**出口** → 进入公共段 **P1**（带"需等待"标记），携带 `partnerId / poiId / platformContractId`

> ✅ **数据池写入**：商品创建有结果后执行[数据池写入](#数据池写入-新建供应商后必做)，**无论商品成功还是失败都要写**。
> 需要：**供应商** `partnerId` ＋ **合同** `platformContractId` ＋ **门店** `poiId` ＋ 占用人 `mis`，三者缺一不可。

---

## 路径B：已有 partnerId + poiId

**前提**：用户直接提供了 partnerId 和 poiId。

**Step 1**：私海认领

**Step 2**：绑定门店

**[按需]** POI 资质添加（工具476，商品上线需资质时执行）

**出口** → 进入公共段 P2，携带 `partnerId / poiId`

---

## 路径C：仅有 poiId

**前提**：用户只有 poiId，没有 partnerId。

### Step 0 [BLOCKING]：数据池查询
目的是找一个可用 partnerId 来绑定。

- **命中** → 文字列出供应商列表，请用户回复编号
  - 确认后取 `bpCustomerId` 为 `partnerId` → 进入**命中路径**（Step 1 起）
- **count=0** → 询问是否新建供应商
  - 同意 → 进入**新建路径**（Step 1 起）
  - 放弃 → 退出

### 命中路径

**Step 1**：私海认领

**Step 2**：绑定门店

**[按需]** POI 资质添加（工具476）

**出口** → 进入公共段 P2，携带 `partnerId / poiId`

---

### 新建路径

**Step 1**：私海认领

**Step 2**：创建供应商（`create-partner.py --poi-id <poiId>`）→ 得到 `partnerId + platformContractId`

> ⚠️ **若目标是现付商品**，本步必须显式传 `--cooperation-type 4`：
> `python3 factory/infra/create-partner.py --poi-id <poiId> --cooperation-type 4`，不要用默认参数（预付）。

**出口** → 进入公共段 **P1**（带"需等待"标记），携带 `partnerId / poiId / platformContractId`

> ✅ **数据池写入**：商品创建有结果后执行[数据池写入](#数据池写入-新建供应商后必做)，**无论商品成功还是失败都要写**。
> 需要：**供应商** `partnerId` ＋ **合同** `platformContractId` ＋ **门店** `poiId` ＋ 占用人 `mis`，三者缺一不可。

---

## 路径D：仅有 partnerId

**前提**：用户只有 partnerId，没有 poiId。

**Step 1**：创建 POI → 得到 `poiId`

**Step 2**：私海认领

**Step 3**：绑定门店

**出口** → 进入公共段 P2，携带 `partnerId / poiId`

---

## 公共段 P1～P4

四条路径的汇聚点，按顺序执行。

### P1：等待供应商就绪
**仅路径A/C 新建供应商时执行**；其他路径直接跳到 P2。

供应商由工具49异步创建，需要等待初始化完成：

1. 固定等待 **60s**
2. 每 10s 轮询一次合同（优先用方式二；无 platformContractId 时用方式一），最多再等 **60s**
   - 查到合同 → 跳过 P2/P3，直接进 P4
   - 超时仍无合同 → 进 P3 新建合同

### P2：查询可用合同
**非房、超团不需要合同** → 跳过 P2/P3，直接进 P4。

**方式一**：按 partnerId 查（通用）
```bash
python3 factory/infra/query-contract-by-partner.py --partner-id <partnerId>
# 有生效合同 → 取 contractNo → 进 P4
# 无合同 → 进 P3
```

**方式二**：按 platformContractId 查（路径A/C 新建后推荐，更精准）
```bash
python3 factory/infra/query-contract.py --platform-contract-id <platformContractId>
# 输出：contractNo 字符串（如 ZSFW-A9-75178816）
```

### P3：新建合同（P2 无合同时）
```bash
python3 factory/infra/create-contract.py --partner-id <partnerId>
# 输出：contractNo（字符串）+ platformContractId（数字）
```

### P4：创建房型
**全日房/钟点房必做**；非房/套餐/超团按需。
```bash
python3 factory/infra/create-room.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  [--room-type 0] [--overseas] [--capacity 2] [--room-area 11-15] [--window-type 2]
# room-type: 0=大床间 1=单人间 2=双床间 3=三人间 4=套房 5=独栋 6=床位房
# 输出：roomInfoId（上单必填）+ realRoomId
```

---

## 各商品类型所需 ID

| 商品类型 | 必需 ID |
|---------|--------|
| 全日房 / 钟点房 | `partnerId` + `poiId` + `roomInfoId` + `contractNo`（**字符串**，如 ZSFW-A9-75178816） |
| 非房 xGoods | `partnerId` + `poiId` |
| 套餐 | `partnerId` + `poiId` + `contractId`（= platformContractId，**数字**） |
| 超团-非通兑 | `partnerId` + `poiId`（门店下须有房型） |

> ⚠️ `contractNo`（字符串）和 `platformContractId`（数字）是两个不同字段，**不可混用**。

---

## 附：按需工具

**住宿门店资质添加**（工具476）：
```bash
python3 factory/infra/add-poi-qualification.py --poi-id <poiId>
# 写入资质数据；与工具498（资质审核）独立，各自按需执行
```

**供应商门店资质审核**（工具498）：
```bash
python3 factory/infra/audit-poi-qualification.py --poi-id <poiId>
# 资质审核通过；与工具476（资质添加）独立
```

**价格模式切换**（仅需指定底价/卖价模式时执行；默认卖价，用户未提及价格模式时不要调用）：

境内价格模式定义在**合同**上，系统按供应商/合同自动识别；境外价格模式定义在 **VPOI（门店）**上，需显式切换。两者都应在本阶段（创建产品前）完成，切换失败需立即中断，不带着错误的价格模式继续创建产品。

```bash
python3 factory/infra/switch-price-mode.py --contract-id <platformContractId> --mode BASE_PRICE    # 境内切底价
python3 factory/infra/switch-price-mode.py --contract-id <platformContractId> --mode SELLING_PRICE # 境内切卖价
python3 factory/infra/switch-price-mode.py --overseas --partner-id <partnerId> --poi-id <poiId> --mode 2  # 境外切底价
python3 factory/infra/switch-price-mode.py --overseas --partner-id <partnerId> --poi-id <poiId> --mode 1  # 境外切卖价
```

> ℹ️ 本工具与创建产品（`create-fullday.py` 等）相互独立，创建产品脚本不负责价格模式切换。
> ⚠️ **境外底价模式**下创建产品时，价格字段须用 `basePrice`（而非 `salePrice`），并自行通过 `--set` 补充
> `priceChangeMode=9` / `priceRecodeWay=2` / `expectPriceChangeMode=9` / `priceInfo.priceRecordWay=2` 等字段，
> 详见 `w1-create-fullday.md` 「境外产品价格模式（提示）」。

**ID 互查**（排查用）：
```bash
python3 factory/infra/transform-customer-id.py --origin-customer-id <partnerId>   # partnerId → platformCustomerId
python3 factory/infra/transform-contract-id.py --platform-contract-id <id>        # platformContractId → contractNumber
```

---

## 踩坑速查

| 现象 | 原因 | 解决 |
|------|------|------|
| 创建房型报「TDC创建房型异常」 | 供应商异步未完成 | 等约 1 分钟后重试 |
| 现付商品创建/校验失败（合作类型不符） | 用了默认供应商（`cooperation-type=2` 团购+预订合同）造现付商品 | 重新用 `--cooperation-type 4` 新建现付供应商，不能用预付供应商顶替 |
| 把普通"预付"需求误配成"预付包销"（`cooperation-type=6`） | 用户只说"预付"，未提"包销"，却按预付包销筛选/创建 | 用户未明确说"预付包销"时一律按默认 `cooperation-type=2`（团购+预订合同）处理，只有明确说"预付包销"才用 `--cooperation-type 6` / `--tags "115=预付包销合同"` |
| 「已存在同名物理房型」 | 房型名冲突 | 使用默认命名（含时间戳） |
| 上单 contractNo 不对 | 误用了数字型 platformContractId | 用 `query-contract-by-partner.py` 取字符串格式 |
| 通兑超团创建失败 | entity-type 未设为 2 | 创建供应商时加 `--entity-type 2` |
| 绑定门店报「不在私海」 | 未先做私海认领 | 先执行 `claim-poi.py` 再绑定 |
| 价格模式切换失败 | 传了 businessContractId | 传 `create-partner.py` 返回的 platformContractId |
| 境外底价产品创建报"参数错误" | VPOI 已切底价但产品价格字段仍用 salePrice | 改用 basePrice，并补充 priceChangeMode=9 等字段（见上方价格模式切换说明） |
| 数据池写入后别人搜不到 | 未填 `--occupier` | 补填占用人 mis 重新写入 |

更多踩坑详见 `references/pitfalls/infra.md`

