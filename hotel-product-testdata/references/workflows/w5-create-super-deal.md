# W5：构造超团（非通兑/通兑）+ 审核

## 场景覆盖

| 用户描述 | 类型 | 关键差异 |
|---------|------|---------|
| 超团、非通兑超团、单店超团 | 非通兑 | spuExchangeType=1，单 poiId |
| 通兑超团、多店超团 | 通兑 | spuExchangeType=0，poiId=null，≥2个 poiId |
| 境外超团、境外通兑 | 境外变体 | 加 `--overseas`，专属全日房用多人同价模式（priceSameTag=1 + priceFactorInfos） |
| 直连通兑超团、直连商品通兑超团 | 直连通兑 | 关联商品是直连商品（非预付专属全日房），先调 zl-hotel-testdata skill 创建 isSuperDeal=true 直连商品，再用 `--goods-ids` 复用 |
| 图文审核 | 共用 | BPM 基础信息审核通过后调 `auditProduct` RPC 提交图文（code=2024 预期） |

---

## 类型判断

```
用户说"超团"或"非通兑超团"或"单店超团" → 走【非通兑流程】
用户说"通兑超团"或"多店超团" → 走【通兑流程】
用户说"直连通兑超团"或"直连商品包装成通兑超团"或"直连商品做通兑" → 走【境内通兑直连超团流程】
用户说"境外"或"海外" → 追加 `--overseas`，并视需要加 `--max-adult N`
```

---

## 数据依赖说明

超团依赖一个前置组件，**必须在执行本脚本前单独完成**：

| 组件 | 说明 | 来源 |
|-----|------|------|
| **专属全日房产品**（goodsId） | 超团关联的住宿产品，售价须满足超团价格公式 | 先通过 **W1 流程**（`factory/fullday/create-fullday.py`）创建，拿到 `goodsId` 再传入超团脚本 |
| **非房**（xGoodsId，仅非通兑可选） | 非通兑超团默认自动新建+审核并绑定一条非房；也可传 `--xgoods-id` 复用已审核通过的非房 | 若需手动准备，走 **W3 流程**（`create-non-room.py` + `audit/gift/audit.py`） |
| **直连商品**（goodsId，仅境内通兑直连场景） | 通兑超团关联商品可替换为直连商品 | 调用 `zl-hotel-testdata` skill 创建（`isSuperDeal=true`） |

> 与 W4 套餐编排方式一致：**本 skill 不再自动创建全日房**，超团脚本本身只负责组装 `relatedGoodsList` 并提交 `submitSpu`。

---

## 前置条件

### 非通兑超团

| 所需 ID | 是否必填 | 说明 |
|---------|------|------|
| `partnerId` | ✅ 必填 | 供应商ID（partnerType=2，境内预付） |
| `poiId` | ✅ 必填 | 单个门店ID |
| `goodsId`（专属全日房） | ✅ 必填 | 先按 **前置 A：W1 创建专属全日房** 完成后得到 |
| `contract-no` |  可选 | 生效合同编号；不传则脚本内部自动查询 |

### 通兑超团（比非通兑多几项）

| 所需 ID | 是否必填 | 说明 |
|---------|------|------|
| `partnerId` | ✅ 必填 | 供应商ID，且**必须绑定≥2个门店**，主体类型 type=2（单体酒店） |
| `shop-ids` | ✅ 必填 | **≥2个门店**ID，逗号分隔 |
| `goodsIds`（专属全日房） | ✅ 必填 | 为每个门店按 **前置 A：W1 创建专属全日房** 各创建一条，按 `--shop-ids` 顺序拼成 `--goods-ids` |
| `contract-no` | 可选 | 生效合同编号；不传则脚本内部自动查询（供应商维度，所有门店共用） |

> ⚠️ 通兑超团的前置链路：工具534（私海认领）→ 工具49（供应商，绑定2门店，entity-type=2）→ 工具498（资质审核）。

---

## 前置流程

### 前置 A：W1 创建专属全日房

参考 `references/workflows/w1-create-fullday.md`，为超团单独创建一条**专属全日房**，完成后得到 `goodsId`。

**关键约束：全日房售价必须满足超团价格公式**

```
全日房基础卖价 = 超团价格(mtPrice) ÷ 间夜(roomNights)
```

为避免手工换算嵌套 `weekPriceInfos` JSON 出错，可先用超团脚本自带的 `--calc-fullday-price` 辅助命令一次性打印换算结果和可直接粘贴的 `--set` 参数：

```bash
# 非通兑超团用 factory/super-deal/create-super-deal.py
# 通兑超团用 factory/super-deal-unified/create-super-deal-unified.py（每个门店各算一次）
python3 factory/super-deal/create-super-deal.py \
  --partner-id <partnerId> --poi-id <poiId> \
  --sale-price 20000 --room-nights 1 \
  [--overseas] [--max-adult 2] \
  --calc-fullday-price
```

输出示例（境内）：

```
📐 超团专属全日房价格换算
  超团价格(mtPrice) = 20000分 (200.00元)
  间夜(roomNights)   = 1
  基础卖价 = 20000 ÷ 1 = 20000分 (200.00元)
  全日房统一卖价 = 20000分 (200.00元)（全周单组）

可直接粘贴给 create-fullday.py 的 --set 参数：
  --set 'goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos=[{"inWeek":[1,2,3,4,5,6,7],"priceInfo":{"salePrice":"20000","basePrice":"","subPrice":"","subRatio":"1100"},"priceFactorInfos":null}]'
  --set goodsDetailList.0.goodsBaseInfo.contractNo=<自动查到的合同编号>

⚠️ 全日房 goodsName 建议包含"超级团购"字样，例如：
  --goods-name "<房型名>-<早餐/取消描述>-超级团购<时间戳>"
创建完成并确认 [Step 6] 上线成功（batchOnlineSwitch status=2）后，
再把拿到的 goodsId 传给本脚本的 --goods-id。
```

拿到打印的 `--set` 参数后，正式执行 W1（`factory/fullday/create-fullday.py`），把这些 `--set` 片段和 `--goods-name` 一并传入，等全日房成功上线（`batchOnlineSwitch status=2`）后记录 `goodsId`。

> 境外场景 `--calc-fullday-price` 会额外打印多人同价（priceSameTag=1 + priceFactorInfos）相关的 `--set` 片段，用法一致。
>
> 通兑超团需要**为每个门店重复本步骤**，每个门店单独创建一条专属全日房，得到各自的 `goodsId`，按 `--shop-ids` 的顺序拼接备用。

### 前置 B（可选）：W3 创建 + 审核非房（仅非通兑）

非通兑超团脚本**默认自动执行**本步骤（新建一条餐饮类非房并审核通过），无需手动操作。仅当希望**手动准备/复用已有非房**时才需要：

```bash
# 创建非房
python3 factory/non-room/create-non-room.py \
  --partner-id <partnerId> --poi-id <poiId> --type catering
# → 同步返回 xGoodsId

# 审核非房
python3 factory/audit/gift/audit.py \
  --xgoods-id <xGoodsId> --partner-id <partnerId> --shop-id <poiId>
```

审核通过后，创建超团时传 `--xgoods-id <xGoodsId>` 复用；传 `--skip-xgoods` 则完全不绑定非房。完整 W3 步骤参考 `references/workflows/w3-create-non-room.md`。

---

## 【非通兑超团】创建流程

参数约束参考：`factory/super-deal/schema.json`。

创建阶段直接调用研发 Thrift RPC：

- appkey：`com.sankuai.hotel.biz.platform`
- service：`com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade`
- method：`submitSpu(java.lang.Long userId, SpuModel)`
- 返回：`MeBaseResult`
- 第一个参数为 userId（操作人），partnerId 在 SpuModel 内；当前登录用户由 `invoke()` 通过 `trace_context.meUser` 注入

### Step 1：dry-run 校验（可选）

```bash
python3 factory/super-deal/create-super-deal.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-id <goodsId> \
  [--product-name "<超团名称>"] \
  [--sale-price 20000] \
  [--line-price 30000] \
  [--inventory 1000] \
  [--person-bind-limit 5] \
  [--room-nights 1] \
  [--base-add-price '[{"startDate":"YYYYMMDD","endDate":"YYYYMMDD","weekPrices":[{"inWeek":[6,7],"addPrice":1000}]}]'] \
  [--sell-end YYYY-MM-DD] \
  [--checkin-start YYYY-MM-DD --checkin-end YYYY-MM-DD] \
  [--skip-xgoods] \
  [--xgoods-id <已有非房xgoodsId>] \
  [--payload-file /path/to/custom-spu-payload.json] \
  [--swimlane <泳道>] \
  [--skip-refresh-spu-cache] \
  [--cache-env test|prod] \
  --dry-run
```

`--goods-id` 为**必填参数**，必须是**前置 A**中已成功上线的专属全日房 `goodsId`；`--dry-run` 只打印最终 `SpuModel`（不实际提交，也不会新建/查询非房）。正式端到端验证必须去掉 `--dry-run`。

> 📌 **加价日历（周末/节假日等特定日期加价）通过 `--base-add-price` 支持，与全日房创建解耦互不影响**：数组每项结构为 `{startDate: "YYYYMMDD", endDate: "YYYYMMDD", weekPrices: [{inWeek: [1~7], addPrice: 分}]}`，仅写入 SPU 顶层 `superDealModel.spuBaseAddPriceModelList`，**不写入全日房的 `weekPriceInfos`**（后端兑换时自行按「全日房基础价 + 加价」计算实际卖价）。加价日期范围必须落在 `--checkin-start`~`--checkin-end` 入住日期范围内，否则脚本报错。

### Step 2：正式提交

去掉 `--dry-run` 执行同一命令。脚本按顺序执行：

1. 使用传入的 `--goods-id` 组装必填的 `relatedGoodsList`
2. **（自动）** 若传 `--xgoods-id` → 查询该非房快照并绑定；若未传且未加 `--skip-xgoods` → 调用 W3 创建+审核非房（`create-non-room.py` + `audit/gift/audit.py`），再查询非房快照注入 `relateXgoodsInfoModels`
3. 等待 60s（确保专属全日房型信息在后端传播完成，避免 `submitSpu` 报「查询套餐关联房型信息失败」）
4. `MeResourceFacade#submitSpu` 提交非通兑超团（autoPublish=true，含 `spuImageInfoModel` 图文信息）
5. **（自动）** autoPublish=true，SPU 创建即自动完成审核并发布上线，**无需手动调用审核脚本**
6. **（自动）** 上线后刷新 SPU 缓存（SPU 套餐产品缓存 + POI-SPU 映射缓存），通过 goodsoperator-cli 调用；加 `--skip-refresh-spu-cache` 可跳过，`--cache-env` 控制环境（默认 `test`）

> ⚠️ **异步入库延迟**：`submitSpu` 返回 `spuId` 后，后端魔盒（商品中心）创建 SPU 实体数据是**异步**的，通常需要 10-30 秒才真正落库。在落库完成前，前端/查询接口可能显示「基本信息模块未入库」「关联选单未入库」「关联魔盒未入库，魔盒创建失败,原因:依赖系统异常」「110003 魔盒 thrift 连接异常」「13001提交审核失败」「13013关联套餐礼包不存在或不是套餐礼包」等报错——多数是**正常的异步延迟表现，不代表创建失败**。
> - 脚本返回 `spuId` 即代表创建受理成功
> - ❌ **不要用 `querySpuListPage` 验证入库**：该接口对超团（spuType=1）查询不可靠，无论传不传 spuId、加不加 onLineStatus 过滤，RPC 均正常返回 `code=10000,success=true`，但恒为 `totalCount=0, list=[]`，会造成误判（该方法内部查询分支疑似未适配超团数据源，仅套餐 spuType=0 可靠）
> - ✅ **用 `factory/super-deal/query-spu.py` 验证入库+在线状态**（`MeResourceFacade#getSpuDetail`，按 `partnerId+spuId` 精确查询，已实测验证可靠）：
>   ```bash
>   python3 factory/super-deal/query-spu.py --partner-id <partnerId> --spu-id <spuId>
>   # 加 --wait 可自动重试（最多8次，每次间隔15s，覆盖异步入库延迟）
>   python3 factory/super-deal/query-spu.py --partner-id <partnerId> --spu-id <spuId> --wait
>   ```
>   关注输出中的 `status`（0=下架 1=上架 2=归档）、`spuAuditModel.auditStatus`、`superDealCouponModel.couponAuditStatus/giftCardAuditStatus/sieveAuditStatus`（均为4代表通过）、`mboxId`（非空代表魔盒已生成）、`relatedGoodsList`（确认关联的全日房是否正确）。`status=1` 即代表入库+上线成功，无需再等待报错消失。
> - 🔁 **`110003 魔盒 thrift 连接异常` / `13001提交审核失败`（基本信息模块未入库）均需调用 `editSpu` 重新编辑提交修复（已实测验证，2026-07-22）**：SPU 此时**已经创建成功、`spuId` 已存在**，只是某个模块（魔盒/基本信息）因 Thrift 连接断开或异步入库异常未正常落库，**不要重新调用 `submitSpu` 新建一条**（会产生脏数据、留下无用的旧 spuId），而应针对同一 `spuId` 编辑重提：
>   1. `interface/super-deal/interface.py` 的 `get_spu_detail(partner_id, spu_id)` 取回该 `spuId` 的完整 `SpuModel`
>   2. **不修改任何字段**，原样传给 `edit_spu(partner_id, spu_model)`（`MeResourceFacade#editSpu(Long partnerId, SpuModel)`，与 `submitSpu` 的关键区别是 `spuModel.spuBaseModel.spuId` 必须保留，不能像新建那样 pop 掉）——这与 ME 前端报错提示的「请点击编辑按钮，不修改任何信息重新提交一次」完全对应
>   3. **`110003`/`13013` 均是瞬时性异步索引/连接抖动，`edit_spu` 调用本身也可能立即失败并原样复现同样报错**（已实测两个独立案例：①连续 2 次间隔 20-25s 的 `edit_spu` 仍报 `110003`，第 3 次间隔约 45s 后才返回 `success=true`；②`edit_spu` 成功后审核状态卡住，重试时又复现 `13013`）——需要**间隔 30-45s 重试 `edit_spu` 本身**（而非只重试查询），最多重试 3-4 次
>   4. `edit_spu` 返回 `success=true` 后等待 20-30s，再用 `query-spu.py` 确认：多数情况下 `submitStatus` 先从 0 变为 1、`spuAuditModel.auditStatus` 从 4 变为 8（提交中间态，此时 `auditMsg` 变为空），这个中间态**可能持续 60-90s**，最终 `status` 才会自动从 0 流转为 1（上架）——**已实测完整自愈案例**：`edit_spu` 成功后 30s 查询仍是 `submitStatus=1/auditStatus=8/status=0`，再等 30s 依旧不变，再等 60s 后 `status` 才变为 1（从 `edit_spu` 成功到最终上架总耗时约 90-120s），期间**无需再手动调用 `updateSpuStatus`**，耐心等待即可
>   5. ⚠️ **已知问题（2026-07-22 实测遇到过一次）**：`edit_spu` 返回 `success=true` 后，`status` 未流转为 1，而是卡在 `superDealCouponModel.couponAuditStatus=5`、`superDealSieveModel.sieveAuditStatus=2`（均非文档预期的 4=通过）的中间态超过 2 分钟，再重试 `edit_spu`（成功返回）也无法继续推动流转。这种情况已不是普通异步延迟，大概率是关联选单/魔盒关系在后端彻底断裂，**不建议在同一 spuId 上无限重试**，超过 3-4 次 `edit_spu` 后状态仍未流转到 1，直接放弃该 spuId，重新走一遍完整流程新建
>   6. 若 `edit_spu` 重试后长期卡住，才考虑联系人工排查
> - ⚠️ **`update_spu_status`（`MeResourceFacade#updateSpuStatus`，入参 `UpdateSpuStatusParam{spuId,partnerId,poiId,status}`）不能用于修复上述报错（已实测验证，2026-07-22）**：无论是 `13001`（基本信息模块未入库）还是 `edit_spu` 已成功但审核卡在中间态的场景，直接调用 `status=1` 均会复现同样的 `13001` 报错；该接口仅适用于**基本信息/关联选单/关联魔盒均已正常入库、只是需要显式上/下线切换**的场景（例如下架后重新上架）

非房查询 RPC 信息：

- service：`com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade`
- method：`querySpuXgoodsList`
- 参数：`com.meituan.hotel.biz.platform.goods.model.xgoods.XgoodsListQueryParam`
- 返回：`MeBaseResult`

随后调用 `submitSpu`。直接调用研发 Thrift RPC（两参数版本，与套餐共用同一已注册 OCTO 接口）：

- service：`com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade`
- method：`submitSpu(Long userId, SpuModel spuModel)`
- 第一个参数为 userId（操作人），partnerId 在 SpuModel 内
- 当前登录用户由 `invoke()` 通过 `trace_context.meUser` 注入（@Login4Me 切面读取）
- 不再需要第三个 Boolean 参数——SpuModel 内已包含 autoPublish 等全部业务字段

不再依赖 `mtcurl` CLI 和浏览器 ssoid，通过 `mt-qa-tool` 的 `du_thrift` 模块直接发起 Thrift RPC 调用。

脚本从 `MeBaseResult` 的顶层或 `data` 中兼容提取 `spuId`；若返回未携带 `spuId`，
必须通过商品查询接口回查，不能以 RPC 返回成功代替数据落库验证。

> `sale-price` 映射 `superDealGiftCardModel.mtPrice`，`line-price` 映射顶层
> `linePrice`，两者单位均为**分**，且 `linePrice >= mtPrice`。

### Step 3：审核说明

> ✅ 非通兑超团 `autoPublish=true`，自动审核发布。
> **不需要额外调用审核脚本**，SPU 创建后自动上线。

`factory/audit/super-deal/audit.py` 保留为手动诊断工具，非通兑正常流程不调用。

---

## 【通兑超团】创建流程

参数约束参考：`factory/super-deal-unified/schema.json`。

创建阶段直接调用研发 Thrift RPC（与非通兑共用同一实现类）：

- appkey：`com.sankuai.hotel.biz.platform`
- service：`com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade`
- method：`submitSpu(Long userId, SpuModel spuModel)`
- 响应同步返回 `spuId`（不再需要等大象推送）

### Step 1：dry-run 校验（可选）

```bash
python3 factory/super-deal-unified/create-super-deal-unified.py \
  --partner-id <partnerId> \
  --shop-ids "<poiId1>,<poiId2>" \
  --goods-ids "<goodsId1>,<goodsId2>" \
  [--product-name "<超团名称>"] \
  [--sale-price 20000] \
  [--line-price 30000] \
  [--inventory 1000] \
  [--person-bind-limit 5] \
  [--room-nights 1] \
  [--base-add-price '[{"startDate":"YYYYMMDD","endDate":"YYYYMMDD","weekPrices":[{"inWeek":[6,7],"addPrice":1000}]}]'] \
  [--sell-end YYYY-MM-DD] \
  [--checkin-start YYYY-MM-DD --checkin-end YYYY-MM-DD] \
  [--swimlane <泳道>] \
  [--skip-refresh-spu-cache] \
  [--cache-env test|prod] \
  --dry-run
```

`--goods-ids` 为**必填参数**（数量须与 `--shop-ids` 一致），需按 `--shop-ids` 顺序传入**前置 A** 中为每个门店各自创建好的专属全日房 `goodsId`。`--dry-run` 只打印最终 SpuModel，不实际提交。

> 📌 **加价日历同样通过 `--base-add-price` 支持**：所有门店共用同一份加价规则（写入 SPU 顶层 `superDealModel.spuBaseAddPriceModelList`，不写入各门店全日房的 `weekPriceInfos`），加价日期范围必须落在 `--checkin-start`~`--checkin-end` 内。

### Step 2：正式提交

去掉 `--dry-run` 执行同一命令。脚本按顺序执行：

1. 使用传入的各门店 `goodsId` 组装 `relatedGoodsList`（每项仅需 `{poiIdStr, goodsId}`）
2. 构建 SpuModel 并通过 `MeResourceFacade#submitSpu` RPC 提交通兑超团
3. 响应同步返回 `spuId`

```bash
python3 factory/super-deal-unified/create-super-deal-unified.py \
  --partner-id <partnerId> \
  --shop-ids "<poiId1>,<poiId2>" \
  --goods-ids "<goodsId1>,<goodsId2>"
```

> **创建成功后自动串联完整审核流程**（BPM 基础信息审核 + auditProduct 图文信息审核，详见 Step 3）。
> 如需跳过自动审核，加 `--skip-audit` 参数。
>
> `--shop-ids` 和 `--goods-ids` 均为逗号分隔的多值参数，数量必须一致。
>
> `sale-price` 和 `line-price` 单位均为**分**（与非通兑一致）。

> `submitSpu` 直接调用研发 Thrift RPC（`MeResourceFacade#submitSpu` 两参数版本，与套餐共用同一已注册 OCTO 接口），通过 `mt-qa-tool` 的 `du_thrift` 模块发起调用，不再依赖 `mtcurl` CLI。

### Step 3：审核（auditProduct 图文信息审核）—— 创建后自动执行

通兑超团 `autoPublish=false`，创建后必须审核通过才可上线。

> ✅ **已实测验证（2026-07-22，spuId=2257204683）：通兑超团审核只需调用 `auditProduct` 一步即可，不需要走 BPM 基础信息审核**：单独调用 `auditProduct`（不做 BPM）后，`superDealCouponModel.couponAuditStatus`、`superDealGiftCardModel.giftCardAuditStatus`、`superDealSieveModel.sieveAuditStatus` 均直接变为 `4`（通过），`mboxId` 正常生成，随后上线（`onlineSwitch`）成功，最终 `status=1`（上架）。此前文档记录的"BPM 必须先做"是基于早期排查得出的错误结论，已修正。**唯一残留现象**：`spuAuditModel.auditStatus` 会停留在 `8`（不会变成 4），但这**不影响上线**，属于该场景下的正常终态，无需在意。
>
> ✅ **创建脚本默认在创建成功后自动串联本步骤**，无需手动执行。
> 仅当创建时传了 `--skip-audit` 才需手动调用：

```bash
python3 factory/audit/super-deal-unified/audit.py \
  --spu-id <spuId> \
  --partner-id <partnerId> \
  --graphic-only \
  --auto-online
```

**审核流程（仅需一步）**：

**auditProduct RPC 图文信息审核**（`--graphic-only`，跳过 BPM）
   - appkey：`com.sankuai.qatool.productmanage`
   - service：`com.meituan.nibqa.tdm.api.service.ProductMakeService`
   - method：`auditProduct`
   - configKey：`spuDeal`（通兑超团）
   - 内部执行 `approvedSpuAndAddGraphicDetails`（添加默认图文并提交审核，同时完成优惠券/魔盒选单的审核流转）
   - 返回 `success:true, code:200` 即代表图文+优惠券+选单侧审核全部完成

> ⚠️ **关键约束**：
> 1. **submitSpu 创建时不能带 `spuImageInfoModel`**，否则 auditProduct 会把图文推到「审核中」
> 2. **上线存在明显异步索引延迟**：`auditProduct` 成功、`couponAuditStatus` 等已变为4后，立即调用上线可能报「套餐缺少图文详情」（已实测间隔 20-45s 重试仍报此错），需要等待更长时间才能上线成功；脚本 `--auto-online` 内置了递增重试，耐心等待即可，非必要不要脱离脚本手动短间隔轮询判断"失败"
> 3. ⚠️ **`auditProduct` 短间隔内重复调用同一 spuId 可能返回不稳定结果（已实测，2026-07-22）**：一次 `success:true/code:200`，另一次 `success:false/code:2024/message:"SPU基础信息审核失败"`。若已确认调用成功（`couponAuditStatus` 等已变为4），**不要再重复调用 `auditProduct`**，否则可能把状态打回卡死态（`couponAuditStatus` 卡在非4的中间态 `5` 且无法自愈，需放弃该 spuId 重新新建）
>
> `--action reject` 仅支持 BPM 驳回场景（通兑超团正常通过流程无需关心）。

> ✅ **已实测验证（2026-07-22，spuId=2257204835）：通兑超团上线优先直接调用 `MeResourceFacade#updateSpuStatus` RPC（Thrift 直调），无需依赖 `mtcurl` + MTA HTTP 网关的 `onlineSwitch`**：`updateSpuStatus` 与非通兑超团/套餐共用同一已注册 OCTO 的 `MeResourceFacade` 接口（方法签名 `updateSpuStatus(UpdateSpuStatusParam{spuId,partnerId,poiId,status})`），已加入 `interface/super-deal-unified/interface.py`。相比 `online_switch`（依赖浏览器 ssoid，且此前遇到过异步索引延迟需数分钟重试），本次实测 `couponAuditStatus`/`giftCardAuditStatus`/`sieveAuditStatus` 均为4、`mboxId` 已生成后，直调 `updateSpuStatus(status=1)` **一次性成功**（耗时约7秒），`status` 立即从 `0` 变为 `1`（上架），未再复现「套餐缺少图文详情」的报错。
>   - `factory/audit/super-deal-unified/audit.py` 的 `--auto-online`（`_do_online_switch`，供 `--graphic-only --auto-online` 及创建脚本默认自动串联使用）已改为**优先走 `update_spu_status` Thrift RPC，异常时才 fallback 到 `online_switch` HTTP 网关**，其余重试等待逻辑不变
>   - 新增 `--online-only` 参数：跳过审核，直接单次调用 `updateSpuStatus` RPC 上线（不重试），用于图文审核已确认通过（`couponAuditStatus` 等均为4、`mboxId` 非空）、只是显式卡在 `status=0` 中间态、需要手动触发一次上线动作的场景：
>     ```bash
>     python3 factory/audit/super-deal-unified/audit.py --spu-id <spuId> --partner-id <partnerId> --online-only
>     ```
>   - ⚠️ `updateSpuStatus` 与 `edit_spu` 的适用场景不同（详见下方非通兑超团相关说明）：仅当基本信息/关联选单/关联魔盒均已正常入库（`mboxId` 非空）时才适用；若 SPU 仍是「基本信息模块未入库」（13001）等未完全入库状态，直调本函数大概率复现同样报错，此时应改走 `edit_spu` 修复

### Step 4：上线后刷新 SPU 缓存（审核上线后自动执行）

> ✅ **创建脚本默认在审核上线成功后自动刷新 SPU 缓存**，无需手动执行。
> 仅当创建时传了 `--skip-refresh-spu-cache`，或 `--skip-audit` / 审核未成功时才需手动刷新。

超团上线后报价服务依赖 SPU 套餐产品缓存与 POI-SPU 映射缓存，若不刷新会出现 C 端查不到产品/房型售罄等问题。脚本通过 goodsoperator-cli 触发：

```bash
# 1. 刷新 SPU 套餐产品缓存（按 SPU 维度）
hthotel-ops-product --env test goodsquery query-spu --spu-id <spuId> --sync

# 2. 刷新 POI-SPU 映射缓存（按 POI 维度，通兑超团对每个 shopId 逐个刷新）
hthotel-ops-product --env test goodsquery query-poi-spu-mapping --poi-id <poiId> --sync
```

> ⚠️ 前置依赖：首次使用需安装 goodsoperator-cli：
> ```bash
> pip3 install -e /Users/baichenyu/.catpaw/skills/skills-market/goodsoperator-cli -q
> ```
> 刷新为 best-effort 后置动作：CLI 缺失或单条刷新失败仅打印告警，不会让已成功的超团创建流程报错退出。`--cache-env` 默认 `test`（与本 skill 创建商品所用测试环境一致）。

---

## 【境内通兑直连超团】创建流程

> 🎯 **场景**：用户持有 partnerId（单体酒店供应商），希望把 **直连商品**（而非预付专属全日房）包装成通兑超团。整条链路自动编排，用户无需手动调 zl-hotel-testdata skill。
>
> ✅ **已验证可行**：spuId=2257136639（partnerId=4550182）成功用两个直连 goodsId（600004435695、600004461127）创建通兑超团，说明 `submitSpu` 后端接受直连 goodsId 作为 `relatedGoodsList`。

### 前置条件

| 所需 ID | 是否必填 | 说明 |
|---------|------|------|
| `partnerId` | ✅ 必填 | 供应商ID，且主体类型 entity-type=2（单体酒店），已绑定≥2门店或允许新建门店 |
| `poiId` | 可选 | ≥2个门店ID；不传则自动新建（默认 2 个，可用 `--count N` 覆盖） |

> ⚠️ **partnerId 要求**：必须是 entity-type=2（单体酒店）供应商。通兑超团不支持酒店集团主体。
> 若 partnerId 未绑定门店，Agent 自动走 W8 路径D 新建门店。

### 编排流程（Agent 自动执行，5 步）

#### Step 1：新建 N 个门店（POI）

用户未提供 poiId 时，自动调用本 skill 的 W8 路径D 原子操作，为每个门店执行：

```bash
# 在 hotel-product-testdata 的 hotel_testdata_cli/ 目录下执行
python3 factory/infra/create-poi.py                          # 得到 poiId
python3 factory/infra/claim-poi.py --poi-id <poiId>          # 私海认领（每次新 poiId 必做）
python3 factory/infra/bind-partner-poi.py --poi-id <poiId> --partner-id <partnerId>  # 绑定门店
```

默认新建 2 个门店（通兑超团最低要求），可用 `--count N` 覆盖。每个门店独立执行三步，得到 `[(poiId1, ...), (poiId2, ...)]`。

> 📌 W8 路径D 详见 `references/workflows/w8-infra-bootstrap.md`。create-poi 默认境内 category-id=352。

#### Step 2：创建直连超团商品（调用 zl-hotel-testdata skill）

对每个 poiId，读取并调用 `zl-hotel-testdata` skill（`~/.catpaw/skills/skills-market/zl-hotel-testdata/SKILL.md`）创建直连商品，**不要自行调用接口**。

向 skill 传入以下关键参数：

- **接入模式**：`CN_NEWOPENPLATFORM_LAND`（境内新开放平台落地）
- **超团标记**：`isSuperDeal=true`（关键字段，标识可用于超团，**必须传**）
- **入离日期**：`checkInDate=今天`、`checkOutDate=今天+30天`（落地允许≤180天，30天覆盖近一个月库存价格）
- **付款方式**：预付（`paymentType=1`）
- **rateplanCode/roomCode**：不传，由 skill 处理自动生成逻辑（避免 ARI 时序问题）

> ⚠️ **必须走 skill，不要绕过**：zl-hotel-testdata skill 会完整处理 rateplanCode/roomCode 自动生成、ARI 库存价格推送、大象消息通知等细节。Agent 按 skill 流程执行即可。
> 创建是异步任务，skill 会返回 `taskId`，goodsId 需通过大象消息或轮询获取（见 Step 3）。

#### Step 3：获取 goodsId

直连商品创建是异步入库（耗时约 1-2min）。skill 执行 createProduct 后会打印 `taskId`，**等待约 90 秒**后直接调用 `queryCreateProductTaskResult` 接口查询创建结果：

```bash
curl -s "https://zl.data.test.sankuai.com/queryCreateProductTaskResult?taskId=<taskId>&operator=<mis>&sourceType=0"
```

返回中提取 `goodsId` 字段即可。若任务尚未完成，再等 30s 重试几次（通常 90s 内完成，最多 3 分钟）。

> ⚠️ **status 大小写注意**：接口实际返回 `status=success`（小写），文档写的是 `SUCCESS`，不影响手动查看。
>
> 🚫 **查到 `status=fail` 时不要在同一 POI 上重试**：换一个全新 POI（重新调 `fetchUnmatchedPoi`），同时换一批新的 rateplanCode/roomCode，重新走 Step 2 创建。

#### Step 4：创建通兑超团（复用已有流程）

拿到 N 个 poiId + 对应 goodsId 后，调用现有通兑超团创建脚本：

```bash
python3 factory/super-deal-unified/create-super-deal-unified.py \
  --partner-id <partnerId> \
  --shop-ids "<poiId1>,<poiId2>" \
  --goods-ids "<goodsId1>,<goodsId2>"
```

> 📌 `--goods-ids` 直接复用直连商品 goodsId 作为 `relatedGoodsList`（通兑超团 `relatedGoodsList` 每项仅需 `{poiIdStr, goodsId}`，模板本身 `spuActivityStockModel` 就是 `null`，无需额外参数区分直连/专属全日房）。
> 后端接受直连 goodsId 作为通兑超团关联商品（已验证：spuId=2257136639 创建成功）。

#### Step 5：后续审核 + 上线 + 缓存刷新

create-super-deal-unified.py 默认自动串联完整审核流程（与普通通兑超团一致）：

1. BPM 基础信息审核（需 BPM Cookie，详见上方【通兑超团】Step 3）
2. auditProduct 图文信息审核（code=200 或 2024 预期）
3. 自动上线 onlineSwitch（异步入库可能需重试，脚本内置 10 次重试）
4. 刷新 SPU 缓存 + POI-SPU 映射缓存（goodsoperator-cli）

> ⚠️ BPM 审核依赖 BPM Cookie，首次执行可能需要在 CatDesk 浏览器登录 BPM（测试环境 SSO 升级后需先完成生产环境 SSO 登录，详见 `scripts/bpm_utils.py` 的 `ensure_bpm_login`）。

> ⚠️ **直连商品超团特有：上线可能报"套餐缺少图文详情"，需重试 auditProduct**
>
> 直连商品作为超团关联商品时，第一次 auditProduct 虽然返回 code=200，但图文详情可能没真正落库（直连商品场景有时序问题），导致上线报"套餐缺少图文详情"或"spu魔盒修改状态失败"。
>
> **修复方式**：用 `--graphic-only --auto-online` 重试一次 auditProduct + 上线：
> ```bash
> python3 factory/audit/super-deal-unified/audit.py \
>   --spu-id <spuId> --partner-id <partnerId> \
>   --graphic-only --auto-online
> ```
> 第二次 auditProduct 返回 code=2024（图文真正提交为「编审修改后通过」），onlineSwitch 重试 1-2 次即可上线成功。
>
> ✅ **实跑验证**（2026-07-19）：spuId=2257136655 第一次上线报"套餐缺少图文详情"，重试 auditProduct 后第二次上线成功。
>
> 📌 **与预付商品超团的差异**：预付商品一次 auditProduct 就够；**直连商品需要两次**。原因推测：直连商品的图文详情入库是异步的，第一次 auditProduct 触发后还没落库，第二次调用时才真正提交。

### 关键约束

- **partnerId 必须是 entity-type=2（单体酒店）**，酒店集团主体不支持通兑超团
- **直连商品必须 isSuperDeal=true**，否则不能作为超团关联商品
- **入离日期跨度 ≤180 天**（落地产品上限），默认 30 天覆盖近一个月
- **goodsId 异步生成**（约 1-2min），等待约 90 秒后直接调用 `queryCreateProductTaskResult?taskId=<taskId>&operator=<mis>&sourceType=0` 查询，从返回中提取 `goodsId`；查到 `status=fail` 时换新 POI 重新创建，不要在同一 POI 上重试
- **直连商品超团需调两次 auditProduct**：第一次（创建脚本自动调）返回 code=200 但图文可能没落库，上线报"套餐缺少图文详情"；需用 `--graphic-only --auto-online` 重试一次，第二次返回 code=2024 图文真正提交，上线才能成功（预付商品一次即可，这是直连商品的特有差异）
- **整条链路涉及 2 个 skill**：hotel-product-testdata（新建门店 W8）+ zl-hotel-testdata（创建直连商品），Agent 需切换 skill 上下文执行

### 与普通通兑超团的关键差异

| 项目 | 普通通兑超团 | 境内通兑直连超团 |
|-----|------------|----------------|
| 关联商品来源 | 前置 A：W1 创建专属全日房（预付） | 调用 zl-hotel-testdata skill 创建直连商品 |
| 创建参数 | `--shop-ids` + `--goods-ids`（专属全日房） | `--shop-ids` + `--goods-ids`（复用直连 goodsId，无需额外参数） |
| 门店来源 | 用户提供 | 自动新建（W8 路径D）或用户提供 |
| 涉及 skill | 仅 hotel-product-testdata | hotel-product-testdata + zl-hotel-testdata |
| 超团创建+审核 | — | 一致（复用 create-super-deal-unified.py） |

---

## 完整执行链路

```
非通兑超团：
[前置 A] W1：factory/fullday/create-fullday.py（配合 --calc-fullday-price 换算价格）→ goodsId
[前置 B]（可选）W3：create-non-room.py + audit/gift/audit.py → xGoodsId（不传则脚本自动新建+审核）
[W5]     factory/super-deal/create-super-deal.py --goods-id <goodsId> [--xgoods-id <xGoodsId>] → spuId（自动上线）

通兑超团：
[前置 A] 为每个门店重复 W1：factory/fullday/create-fullday.py → goodsId1, goodsId2, ...
[W5]     factory/super-deal-unified/create-super-deal-unified.py --shop-ids "..." --goods-ids "..." → spuId
         → 自动串联 BPM 审核 + auditProduct 图文审核 + 上线 + 缓存刷新
```

---

## 非通兑 vs 通兑 关键差异对照

| 项目 | 非通兑 | 通兑 |
|-----|--------|------|
| 创建方式 | **MeResourceFacade#submitSpu RPC** | **MeResourceFacade#submitSpu RPC**（同一实现类） |
| 场景标识 | `spuExchangeType=1` | `spuExchangeType=0` |
| poiId | 真实单门店ID | **null**（不绑定单门店） |
| shop-ids 参数 | 不传 | **必传，≥2个，逗号分隔** |
| goods-id(s) | `--goods-id`（单个，必填，来自前置 A） | `--goods-ids`（逗号分隔多个，必填，来自前置 A，需按 shop-ids 顺序） |
| contractId / contract-no | 可选，不传自动查询 | 可选，不传自动查询（供应商维度，所有门店共用） |
| 价格 | `mtPrice` + `linePrice`，单位均为**分** | `mtPrice` + `linePrice`，单位均为**分** |
| 门店数要求 | 1个 | **≥2个** |
| 专属全日房 | 前置 A 为 1 个门店创建 1 条 | 前置 A **为每个门店各创建一条** |
| relatedGoodsList 每项 | `goodsId` + `goodsName` + `goodsSource` 等多字段 | 仅 `poiIdStr` + `goodsId` |
| spuId 获取 | RPC 响应同步返回 | RPC 响应同步返回 |
| autoPublish | `true`（创建即自动审核上线，含图文） | `false`（需完整审核才可上线） |
| 审核方式 | **无需额外审核**（autoPublish=true 自动发布） | **BPM 基础信息审核 + auditProduct 图文信息审核** |
| 审核脚本 | audit/super-deal/audit.py（手动诊断工具，正常不调用） | audit/super-deal-unified/audit.py |
| 审核参数 | N/A | `--spu-id` + `--partner-id` + `--action pass` |
| 前置资质 | 无 | 需工具498资质审核 |

## 关键约束

- **专属全日房必须先按前置 A（W1 流程）单独创建好**，脚本本身不再自动创建全日房；`--goods-id`（非通兑）/ `--goods-ids`（通兑）为必填参数
- 全日房售价必须满足超团价格公式：**基础卖价 = 超团价格(mtPrice) ÷ 间夜(roomNights)**；可用超团脚本的 `--calc-fullday-price` 辅助换算，减少手工拼接 JSON 出错概率
- 超团产品必须勾选美团+点评（sellChannel 含位1和位2），否则报 SUPER_DEAL_GOODS_INFO_ERROR
- 超团产品不能设置连住规则（serialCheckinMin/Max 必须均为 0）
- 超团创建成功后必须审核通过才能上线（通兑需完整审核；非通兑 autoPublish=true 自动上线）
- **通兑超团创建脚本默认自动串联完整审核**（BPM 基础信息审核 + auditProduct 图文信息审核）；加 `--skip-audit` 可跳过
- 通兑超团 `--shop-ids` 和 `--goods-ids` 为逗号分隔多值参数，数量必须一致
- 专属全日房 `goodsName` 必须包含"超级团购"字样，满足系统识别要求（`--calc-fullday-price` 输出会提示）——**已实测验证（2026-07-22）**：若全日房命名不含此字样（例如仅含"通兑超团"），`submitSpu` 会报 `(goodsId)不属于超级团购产品`（code=200014024），需重新创建全日房（改用含"超级团购"字样的 `--goods-name`）后再提交
- `submitSpu` 直接调用研发 Thrift RPC（`MeResourceFacade#submitSpu` 两参数版本，与套餐共用同一已注册 OCTO 接口），通过 `mt-qa-tool` 的 `du_thrift` 模块发起调用，不再依赖 `mtcurl` CLI
- **非通兑超团默认创建并绑定非房附加服务**：脚本默认调用 W3 流程（`factory/non-room/create-non-room.py` 创建 + `factory/audit/gift/audit.py` 审核）在门店下新建一条餐饮类非房并审核通过，再查询非房快照注入 `relateXgoodsInfoModels`；加 `--skip-xgoods` 可跳过，传 `--xgoods-id <已有xgoodsId>` 可跳过新建直接绑定已有非房（仅非通兑超团，通兑超团不关联非房）
- 通兑超团 `relatedGoodsNum` 和 `relatedPoiNum` 固定为 0（后端自行从 `relatedGoodsList` 计算）
- 非通兑超团 `autoPublish=true`，创建即自动审核上线（含图文详情），无需额外审核
- 通兑超团 `autoPublish=false`，创建后创建脚本自动串联 BPM 基础信息审核 + auditProduct 图文信息审核
- 境内通兑直连超团：关联商品改为直连商品（isSuperDeal=true），需先调 zl-hotel-testdata skill 创建直连商品拿 goodsId，再用 `--goods-ids` 复用（通兑超团脚本无需 `--direct-goods` 参数，`relatedGoodsList` 本身仅需 `{poiIdStr, goodsId}`）；门店可由 W8 路径D 自动新建；超团创建+审核流程与普通通兑一致
- **通兑超团审核顺序：BPM 先 → auditProduct 后**：BPM 通过后 auditProduct 的 `spuAuditUpdate` 返回 code=2024（预期），但 `approvedSpuAndAddGraphicDetails` 成功提交图文为「编审修改后通过」。若先调 auditProduct 再做 BPM，或只调 auditProduct 不做 BPM，图文会卡在「审核中」
- **通兑超团 submitSpu 不能带 `spuImageInfoModel`**：带了之后 auditProduct 会把图文推到「审核中」；不带时 auditProduct 添加默认图文并直接通过
- `auditProduct` 返回值含义：`code=200` 图文+基础信息均成功；`code=2024` BPM 已完成基础信息审核，spuAuditUpdate 冲突，但图文已成功提交（预期行为）；`code=2023` 图文提交失败
- **超团上线后自动刷新 SPU 缓存**（SPU 套餐产品缓存 + POI-SPU 映射缓存，通过 goodsoperator-cli），避免 C 端查不到产品/房型售罄；加 `--skip-refresh-spu-cache` 可跳过，`--cache-env` 控制环境（默认 `test`，与本 skill 创建商品环境一致）。非通兑在 autoPublish 上线后刷新单门店 POI-SPU；通兑在审核上线成功后对所有 shopIds 逐个刷新
- ⚠️ **非通兑超团 submitSpu 后异步入库延迟**：`submitSpu` 返回 `spuId` 后魔盒（商品中心）创建 SPU 实体是异步的（约 10-30s），落库前前端会显示「基本信息模块未入库」「魔盒创建失败,依赖系统异常」「110003 魔盒 thrift 连接异常」「13001提交审核失败」等报错——**多数是正常延迟，不是创建失败**。
  - ❌ **不要用 `querySpuListPage` 验证入库**：该接口对超团（spuType=1）查询不可靠，无论传不传 spuId、加不加 onLineStatus 过滤，RPC 均正常返回 success=true，但恒为 totalCount=0、list=[]，会造成误判
  - ✅ **用 `factory/super-deal/query-spu.py` 验证入库+在线状态**（`MeResourceFacade#getSpuDetail`，按 partnerId+spuId 精确查询，已实测验证可靠）：`python3 factory/super-deal/query-spu.py --partner-id <partnerId> --spu-id <spuId> --wait`（`--wait` 自动重试最多8次/每次15s）。`status=1`（上架）即代表入库+上线成功，同时可看 `mboxId` 是否非空、`relatedGoodsList` 关联全日房是否正确
  - 🔁 **`110003 魔盒 thrift 连接异常` / `13001提交审核失败` / `13013关联套餐礼包不存在` 均需调用 `editSpu` 编辑重提修复（已实测验证，2026-07-22，含2个独立成功案例），不要重新调用 `submitSpu` 新建**：此时 `spuId` 已存在，用 `get_spu_detail` 取回该 spuId 的完整 SpuModel，不修改任何字段原样传给 `edit_spu(partner_id, spu_model)`（`MeResourceFacade#editSpu`，spuId 必须保留）。这些报错本质都是异步索引/连接抖动，`edit_spu` 本身也可能立即失败复现同样报错，需间隔 30-45s 重试 3-4 次；成功后 `submitStatus` 先变 1、`auditStatus` 变 8（提交中间态），最终 `status` 自动从 0 流转为 1，**全程耗时可达 90-120s**，需耐心轮询等待，不要中途误判失败；也可能卡在 `couponAuditStatus=5`/`sieveAuditStatus=2` 等非 4 的中间态超过 2 分钟仍无法继续推动（已实测遇到过），此时不要无限重试，直接放弃该 spuId 重新走完整流程。`update_spu_status` 直接调 `status=1` 在上述任何未完全入库场景下都会复现同样的 13001 报错，只适用于基本信息/关联选单/关联魔盒均已正常入库的显式上/下线场景。详见上方 Step 2 说明
  - ⏰ **联系人工排查**：把 ME 上单系统链接发给用户手动确认 SPU 上线状态：`https://me.hotel.test.sankuai.com/ebooking/merchant/spu/gift-list?partnerId=<partnerId>&poiId=<poiId>`
- `edit_spu(partner_id, spu_model)`（`MeResourceFacade#editSpu`）与 `update_spu_status(partner_id, spu_id, poi_id, status)`（`MeResourceFacade#updateSpuStatus`）已加入 `interface/super-deal/interface.py`：前者用于针对同一 spuId 编辑重提触发重新入库（见上），后者仅用于基本信息模块已正常入库后的显式上/下线切换，两者不可互相替代

