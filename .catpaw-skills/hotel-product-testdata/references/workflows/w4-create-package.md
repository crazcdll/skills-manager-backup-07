# W4：构造套餐

## 场景覆盖

| 用户描述 | 关键参数差异 |
|---------|------------|
| 普通套餐（境内，预付自建） | 默认参数（不传 `--goods-source`） |
| 境外套餐（预付自建） | 额外加 `--overseas` |
| 直连产品包装成套餐（直连落地） | `--goods-source direct-land`（或 `2`），传入直连产品 goodsId |
| 直连产品包装成套餐（直连不落地） | `--goods-source direct-noland`（或 `3`），传入直连产品 goodsId |

---

## 数据依赖说明

套餐依赖两个前置组件，**必须在执行本脚本前分别完成**：

| 组件 | 说明 | 来源 |
|-----|------|------|
| **全日房产品**（goodsId） | 套餐关联的住宿产品 | 先通过 **W1 流程**创建，拿到 `goodsId`/`goodsName`/`realRoomName` 再传入本脚本 |
| **直连产品**（goodsId） | 套餐关联的直连住宿产品 | 先通过 **zl-hotel-testdata skill** 创建直连产品，拿到 `goodsId` 后传入本脚本（`goodsName`/`realRoomName` 可省略，脚本自动调 `queryGoodsInfo` 查询补全）。**若 `submitSpu` 报 `200013028` 查询套餐关联房型信息失败，再补调 zl-hotel-room-mapping skill（mode2）添加物理房型映射**（该报错为概率性问题，非必现，无需提前执行） |
| **非房**（xGoodsId） | 套餐关联的非住宿服务（如早餐、餐饮） | 先通过 **W3 流程**创建并审核，拿到审核通过的 `xGoodsId` 再传入本脚本 |

> ⚠️ **直连产品 vs 预付自建全日房**：
> - 预付自建全日房（`--goods-source 1`，默认）：走 W1 流程创建，goodsName 由 W1 返回
> - 直连产品（`--goods-source 2/3`）：走 zl-hotel-testdata skill 创建，skill 返回 taskId 后，
>   用 taskId 调 `queryCreateProductTaskResult` 接口查询拿到 `goodsId`，
>   再传入本脚本（`--goods-id`）。`--goods-name`/`--real-room-name` 可省略，
>   脚本自动调 `queryGoodsInfo` 查询补全。

---

## 前置流程

### 前置 A（预付模式）：W1 创建全日房

参考 `references/workflows/w1-create-fullday.md`，完成后得到 `goodsId`。

### 前置 A'（直连模式）：zl-hotel-testdata skill 创建直连产品

调用 `zl-hotel-testdata` skill 创建直连产品，推荐提示词：

> 调用酒店直连的造数据 skill，帮我构造一个直连商品，要求是全新的门店，商品近 30 天要有库存、价格

skill 返回 `taskId` 后，用 taskId 调 `queryCreateProductTaskResult` 接口查询
（直连 skill 已有脚本在末尾会打印查询地址，直接 curl 调几次即可），
拿到 `goodsId` 后传入本脚本。`goodsName`/`realRoomName` 无需手动查询，
脚本会自动调 `queryGoodsInfo`，从返回的 `preGoodsId` 中解析 `sourceRoomCode` 作为 `realRoomName`。

> `preGoodsId` 格式：`ZL-{partnerId}-{poiId}-{ratePlanCode}-{sourceRoomCode}`
> `sourceRoomCode` 即直连产品的商家房型码，`submitSpu` 的 `relatedGoodsList[].realRoomName` 需要传此值。

### 异常处置（直连模式）：`submitSpu` 报 `200013028` 时才需补做物理房型映射

> ℹ️ **非必执行步骤**，仅当创建直连套餐时 `submitSpu` 实际报错 `200013028 查询套餐关联房型信息失败` 时，再执行下述补救操作，不要提前预执行。

原因：`submitSpu` 后端会用直连产品的 `roomId` 查询 MTA 真实房型关系（`getMtaRealRoomRelationsByMtaRoomIds`）。
部分直接调 `/createProduct` 创建的直连产品可能没有 MTA 真实房型关系，导致查询失败。遇到此报错时，可显式调用
`zl-hotel-room-mapping` skill 的 **mode2**（为指定 GoodsId 添加物理房型映射）补全，补全后重新执行 `create-package.py` 即可。

调用方式：

> 调用 zl-hotel-room-mapping skill，用 mode2 为 goodsId=<直连产品goodsId>、partnerId=<partnerId> 添加物理房型映射

skill 执行成功后会返回 `physicalRoomId`，表示物理房型映射已建立。此后该直连产品即可用于套餐上单。

### 前置 B：W3 创建非房

```bash
python3 factory/non-room/create-non-room.py \
  --partner-id <partnerId> \
  --poi-id <poiId>
# → 同步返回 xGoodsId
```

### 前置 C：W3 审核非房

`submitSpu` 要求传入的非房必须已审核通过，否则创建套餐会报错。

```bash
python3 factory/audit/gift/audit.py \
  --xgoods-id <xGoodsId> \
  --partner-id <partnerId> \
  --shop-id <poiId>
```

> 完整 W3 步骤参考：`references/workflows/w3-create-non-room.md`

---

## 执行命令

参数约束参考：`factory/package/schema.json`

### 预付模式（默认，goodsSource=1）

```bash
python3 factory/package/create-package.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-id <goodsId> \
  --goods-name "<全日房产品名称>" \
  --real-room-name "<真实房型名称>" \
  [--xgoods-id <xGoodsId>] \
  [--poi-name "<门店名称>"] \
  [--check-days 2] \
  [--overseas]
```

> `--poi-name` 为可选参数，**仅用于拼接套餐展示名称 title**（格式：`<门店名><间夜数>晚+<非房名>`）。
> 不传时 `title` 落库为空字符串（接口不会报错，但套餐展示名称为空）。

### 直连模式（goodsSource=2/3）

先通过 zl-hotel-testdata skill 创建直连产品，拿到 goodsId 后传入。
`--goods-name`/`--real-room-name` 可省略，脚本自动调 `queryGoodsInfo` 查询补全：

```bash
python3 factory/package/create-package.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-id <直连产品goodsId> \
  --goods-source direct-land \   # 或 direct-noland / 2 / 3
  [--xgoods-id <xGoodsId>] \
  [--poi-name "<门店名称>"] \
  [--check-days 2] \
  [--overseas]
```

**脚本内部自动执行（四步编排）：**

```
Step 0: 查询直连产品详情（MeGoodsFacade#queryGoodsInfo） → goodsName/realRoomName（仅直连模式且未传名称时执行）
Step 1: 创建非房（MeResourceFacade#submitXgoods）   → 同步返回 xGoodsId
Step 2: 创建套餐（MeResourceFacade#submitSpu）        → 同步返回 spuId
Step 3: 查询验证（MeResourceFacade#querySpuListPage）  → 轮询确认 B 端数据生效
```

> ✅ `spuId` 由 Step 2 同步直接返回，**无需等待大象推送**。
> ✅ Step 3 轮询验证 `spuBaseModel.status=1`（已上线）且 `spuAuditModel.auditStatus=4`（审核通过）。
> ✅ `submitSpu` 接口默认审核通过并发布上线，本脚本**无需额外审核步骤**。

---

## 完整执行链路

### 预付模式

```
[前置 A] W1：factory/fullday/create-fullday.py → goodsId
[前置 B] W3：factory/non-room/create-non-room.py → xGoodsId
[前置 C] W3：factory/audit/gift/audit.py → 非房审核通过
[W4]     factory/package/create-package.py --goods-id <goodsId> --goods-name <name> ... → spuId + 验证
```

### 直连模式

```
[前置 A']  zl-hotel-testdata skill：创建直连产品 → taskId → 调 queryCreateProductTaskResult 查询 → goodsId
[前置 B]  W3：factory/non-room/create-non-room.py → xGoodsId
[前置 C]  W3：factory/audit/gift/audit.py → 非房审核通过
[W4]      factory/package/create-package.py --goods-source direct-land --goods-id <goodsId> --xgoods-id <xGoodsId> ... → spuId + 验证
[若报错 200013028]  zl-hotel-room-mapping skill（mode2）：为 goodsId 添加物理房型映射 → physicalRoomId → 重试 [W4]
```

---

## 字段来源分析

submitSpu 接口各关键字段的数据来源：

| 字段 | 来源 |
|-----|------|
| `spuBaseModel.partnerId` | 用户传入的 `--partner-id` |
| `spuBaseModel.poiId` | 用户传入的 `--poi-id` |
| `spuBaseModel.giftsName` / `title` | 接口**不支持自定义任意值**，也**不会由后端自动拼接兜底**：不传则落库为空字符串。若需非空展示名称，需调用方按约定格式 `<门店名><间夜数>晚+<非房名>` 自行拼接后传入（脚本通过可选参数 `--poi-name` 支持此拼接，间夜数取 `--check-days`，非房名取 Step 1 返回的 `xgoods_name`） |
| `relateXgoodsInfoModels[].xgoodsId` | 用户传入的 `--xgoods-id`（来自 **W3**） |
| `relateXgoodsInfoModels[].partnerId/poiId` | 与 `spuBaseModel` 相同 |
| `relatedGoodsList[].goodsId` | 用户传入的 `--goods-id`（来自 **W1** 或直连 skill） |
| `relatedGoodsList[].goodsName` | 预付模式：用户传入的 `--goods-name`；直连模式：自动调 `queryGoodsInfo` 查询补全（或用户手动传入） |
| `relatedGoodsList[].realRoomName` | 预付模式：用户传入的 `--real-room-name`；直连模式：自动调 `queryGoodsInfo` 查询补全（或用户手动传入） |
| `spuImageInfoModel` | 固定模板（测试图片，无需动态填充） |
| `dayTripModel.spuCheckDays` | `--check-days`（默认 2） |

---

## 关键约束

- 非房必须先通过 **W3 审核通过**，再传入本脚本；未审核通过的非房会导致 `submitSpu` 报错
- 接口为**同步直调**，spuId **直接返回**，无需等待大象推送
- `submitSpu` 接口默认审核通过并发布上线，**本脚本无需额外审核步骤**
- 创建后自动调用 `querySpuListPage` 验证 B 端数据生效（`status=1` 且 `auditStatus=4`）
- 套餐 `spuId` 与全日房 `goodsId` 是不同概念
- 参数约束参考：`factory/package/schema.json`
- **直连模式**需先通过 zl-hotel-testdata skill 创建直连产品，拿到 goodsId 后传入（`--goods-id`/`--goods-name`/`--real-room-name` 三者同时传）
- `--goods-source` 枚举：`1`/`prepaid`=预付自建，`2`/`direct-land`=直连落地，`3`/`direct-noland`=直连不落地
- 直连模式下若 `submitSpu` 报 `200013028 查询套餐关联房型信息失败`，再调 zl-hotel-room-mapping skill（mode2）补齐物理房型映射后重试，**无需预先执行**（该报错为概率性问题，非必现）

---

## 与非房的区别

| 项目 | 非房 xGoods | 套餐 SPU |
|-----|-----------|---------|
| 接口 | `MeResourceFacade#submitXgoods` | `MeResourceFacade#submitSpu` |
| 需要 contractId | 否 | 否 |
| 同步/异步 | 同步 | **同步** |
| 审核 ID | xGoodsId | spuId |

