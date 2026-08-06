# W1：构造全日房（全日房 batchCreateGoods）

## 场景覆盖

| 用户描述 | 关键参数差异 |
|---------|------------|
| 普通全日房（当天18:00前免费取消、无早餐） | 默认模板，无需额外 --set |
| 免费取消全日房 | cancelItemType=1, moveUpCancelDays=0, moveUpCancelHour=23:59:00 |
| 收费取消全日房 | cancelItemType=1 + payCancelPeriodModels |
| 含早餐（单早/双早） | rpBreakFastModel.normalRule.num=1 或 2 |
| 平日/周末不同取消/早餐规则 | weekendRule 字段 |
| 附近专享（3公里内可见） | rpDisplayModel.normalRule.distanceRange=1 |
| 现付担保 | paymentType=1, rpGuaranteeModel.normalRule.isGuarantee=1 |
| 现付非担保 | paymentType=2, rpGuaranteeModel.normalRule.isGuarantee=0, arrivalHour 必填 |
| 境外多人多价（不同入住人数不同价） | priceSameTag=0 + priceFactorInfos 各档 basePrice 不同 |
| 境外多人同价 | priceSameTag=1 + priceFactorInfos 各档 basePrice 相同 |
| 带非房/带礼包 | 先按 W3 创建并审核非房，再在 Step 1 命令中追加 `--set goodsDetailList.0.rpInfo.rpServiceModel=...`，详见下方「前置步骤（可选）」 |

---

## 前置条件

进入本 workflow 前，必须已就绪：`partnerId`、`poiId`、`roomId`、`roomName`、`contractNo`（字符串如 `ZSFW-A9-75178816`）。

缺少任何一项 → 先执行 `references/workflows/w8-infra-bootstrap.md`。

> ⚠️ **境外产品**：若需要指定价格模式（底价/卖价），必须在 W8 中通过工具928 完成 VPOI 价格模式切换后，再进入本 workflow 创建产品（详见下方「境外产品价格模式（提示）」）。

---

## 前置步骤（可选）：创建非房并关联礼包

> 仅当产品需要绑定礼包（非房）时执行。普通全日房跳过，直接进入 Step 1。

### ① 按 [W3：构造非房 xGoods + 审核](w3-create-non-room.md) 完成非房创建

```bash
python3 factory/non-room/create-non-room.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  [--product-name "<礼包名称>"]
# 输出：xGoodsId（同步返回，无需等待）
```

### ② 查询非房详情

用创建返回的 `xGoodsId` 查询非房完整信息（`MeResourceFacade#queryXgoodsListByPage`）：

```bash
# 接口：MeResourceFacade#queryXgoodsListByPage
# appKey：com.sankuai.hotel.biz.platform
# 入参：partnerId + poiId + xgoodsId
```

> 关注返回值中的以下字段，后续需映射到产品入参：
> - `basicInfoModel.xgoodsId`、`name`、`priType`、`content`、`images`
> - `ruleModel.useRuleModel`（`businessHours`、`suitableCount`、`touristsInfo`、`contactsInfo`、`ageLimit`）
> - `ruleModel.bookingRuleModel.bookingType`

### ③ 在 Step 1 创建全日房命令中追加 `--set` 参数（组装 rpServiceModel）

非房信息在创建产品接口中通过 **`rpServiceModel`** 传递（不是 `rpGiftModel`）：

```bash
--set 'goodsDetailList.0.rpInfo.rpServiceModel={
  "normalRule": {
    "serviceModels": [
      {
        "serviceTmplId": <xGoodsId>,
        "serviceName": "<非房name>",
        "serviceType": 12,
        "serviceItemType": 3,
        "remark": "<非房content>",
        "availableDate": "",
        "availableDateType": 0,
        "serviceCategory": 1,
        "serviceTemplate": <priType>,
        "servicePriceStd": "0",
        "servicePrice": 0,
        "serviceContent": {
          "bookingRule": "{\"bookingType\":<bookingType>}",
          "images": "<images JSON字符串>",
          "needVerifyIdCard": "0",
          "adultMax": "<adultMax>",
          "adultMin": "<adultMin>",
          "suitableCountType": "<countType>",
          "touristsFeatureType": "<featureType>",
          "businessHours": "<businessHours JSON字符串>",
          "ageLimitType": "<ageLimitType>",
          "contactsTypes": "<contactsInfoTypes JSON字符串>"
        }
      }
    ]
  },
  "updateType": 0
}'
```

**字段映射规则（查询结果 → 创建入参）：**

**从查询结果动态映射的字段：**

| 查询返回字段 | 创建入参字段 | 备注 |
|---|---|---|
| `basicInfoModel.xgoodsId` | `serviceModels[].serviceTmplId` | 非房ID |
| `basicInfoModel.name` | `serviceModels[].serviceName` | 非房名称 |
| `basicInfoModel.priType` | `serviceModels[].serviceTemplate` | 如 22（餐饮） |
| `basicInfoModel.content` | `serviceModels[].remark` | 备注描述 |
| `basicInfoModel.images` | `serviceContent.images` | 序列化为 JSON 字符串 |
| `ruleModel.useRuleModel.businessHours` | `serviceContent.businessHours` | 序列化为 JSON 字符串 |
| `ruleModel.useRuleModel.suitableCount.adultMax` | `serviceContent.adultMax` | 字符串类型 |
| `ruleModel.useRuleModel.suitableCount.adultMin` | `serviceContent.adultMin` | 字符串类型 |
| `ruleModel.useRuleModel.suitableCount.countType` | `serviceContent.suitableCountType` | 字符串类型 |
| `ruleModel.useRuleModel.touristsInfo.featureType` | `serviceContent.touristsFeatureType` | 字符串类型 |
| `ruleModel.useRuleModel.ageLimit.ageLimitType` | `serviceContent.ageLimitType` | 字符串类型 |
| `ruleModel.useRuleModel.contactsInfo.contactsInfoTypes` | `serviceContent.contactsTypes` | 序列化为 JSON 字符串 |
| `ruleModel.useRuleModel.extAttrs.needVerifyIdCard` | `serviceContent.needVerifyIdCard` | 字符串类型，如 `"0"` |
| `ruleModel.useRuleModel.quantityRule` | `serviceModels[].serviceItemType` | 整数，直接传值 |
| `priceModel.salePrice` | `serviceModels[].servicePriceStd` | 字符串类型，如 `"10000"` |
| `priceModel.salePrice` | `serviceModels[].servicePrice` | 数字类型，如 `10000` |
| `priceModel.marketPrice` | `serviceContent.marketPrice` | 字符串类型，如 `"20000"` |
| `ruleModel.bookingRuleModel.bookingType` | `serviceContent.bookingRule` | 序列化为 `{"bookingType":N}` 字符串 |

**固定值字段（无需从查询结果映射）：**

| 字段 | 固定值 | 说明 |
|---|---|---|
| `serviceModels[].serviceType` | `12` | 固定值 |
| `serviceModels[].serviceCategory` | `1` | 固定值 |
| `serviceModels[].availableDate` | `""` | 固定值 |
| `serviceModels[].availableDateType` | `0` | 固定值 |

> ⚠️ `serviceContent` 中所有嵌套对象（`businessHours`、`images`、`bookingRule`、`contactsTypes`）均需序列化为 **JSON 字符串**后传入。
> ⚠️ 优先从查询接口返回中取值，只有在查询接口明确无对应字段时才使用固定值。

---

## Step 1：组装命令

> 参数约束：`factory/fullday/schema.json` | 默认值：`factory/fullday/templates/fullday-default.json`

**基础命令结构**：

```bash
python3 factory/fullday/create-fullday.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --room-id <roomId> \
  --room-name "<roomName>" \
  --goods-name "<商品名>" \
  --set goodsDetailList.0.goodsBaseInfo.contractNo=<contractNo> \
  [--set KEY=VALUE ...]
```

> ⚠️ **`contractNo` 必须通过 `--set` 传入**，脚本没有 `--contract-no` 命令行参数。
> ⚠️ `create-fullday.py` **没有 `--mis` 参数**，脚本通过环境变量自动读取操作人。

---

## Step 2：按用户描述追加 --set 参数

### 取消政策

默认模板已设置「当天18:00前免费取消」，只有需要**变更截止时间或政策**时才需追加 `--set`：

| 场景 | --set 参数 |
|-----|-----------|
| 当天18:00前免费取消（**默认**，无需 --set） | — |
| 不可取消 | `goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=0` |
| 免费取消（当天23:59前） | `...normalRule.cancelItemType=1` `...moveUpCancelDays=0` `...moveUpCancelHour=23:59:00` |
| 免费取消（提前1天14:00前） | 同上，但 `moveUpCancelDays=1` `moveUpCancelHour=14:00:00` |
| 收费取消（前1天14:00后取消扣20%） | 同免费取消基础上加：`'...normalRule.payCancelPeriodModels=[{"advanceDays":0,"advanceHour":"14:00:00","penaltyRate":20}]'` |
| 平日不可取消 + 周末18:00前免费取消 | `normalRule.cancelItemType=0` + `'...weekendRule={"cancelItemType":1,"moveUpCancelDays":0,"moveUpCancelHour":"18:00:00"}'` |
| 平日免费取消 + 周末不可取消 | `normalRule.cancelItemType=1` + 三个 normalRule 字段 + `'...weekendRule={"cancelItemType":0}'` |

### 早餐规则

| 场景 | --set 参数 |
|-----|-----------|
| 无早餐（默认） | 无需额外设置 |
| 含单早 | `goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=1` |
| 含双早 | `goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=2` |
| 平日单早 + 周末双早 | `normalRule.num=1` + `'...weekendRule={"effectiveTimes":null,"num":2}'` |

### 附近专享

```bash
--set goodsDetailList.0.rpInfo.rpDisplayModel.normalRule.distanceRange=1
```

### 现付担保

```bash
--set goodsDetailList.0.goodsBaseInfo.paymentType=1 \
--set 'goodsDetailList.0.rpInfo.rpGuaranteeModel={"normalRule":{"isGuarantee":1,"guaranteeType":2},"updateType":0}'
```
> ⚠️ paymentType=1/2 时 rpGuaranteeModel 必填；paymentType=0（预付）时必须为 null。

### 售价

```bash
--set goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos.0.priceInfo.salePrice=20000
# 单位：分，20000=200元
```

### 境外多人多价（priceFactorInfos）

境外商品支持按入住人数设置不同价格，需要同时设置两处：

**① goodsBaseInfo.priceSameTag + maxAdultAdmissibility**

| 字段 | 类型 | 说明 |
|------|------|------|
| `priceSameTag` | Integer | `0`=多人多价（各档 basePrice 不同），`1`=多人同价（各档 basePrice 相同）；境内不传 |
| `maxAdultAdmissibility` | Integer | 最大可住成人人数（1~6），值为 N 则 priceFactorInfos 必须覆盖 1~N 全部档位；境内不传 |

```bash
# 多人多价（各档 basePrice 不同）
--set goodsDetailList.0.goodsBaseInfo.priceSameTag=0 \
--set goodsDetailList.0.goodsBaseInfo.maxAdultAdmissibility=5   # 最多 5 人，priceFactorInfos 需 5 个档位

# 多人同价（各档 basePrice 相同）
--set goodsDetailList.0.goodsBaseInfo.priceSameTag=1 \
--set goodsDetailList.0.goodsBaseInfo.maxAdultAdmissibility=5   # 最多 5 人，priceFactorInfos 需 5 个档位
```

**② priceInfo 整体替换**（因 priceFactorInfos 为数组，通过 `--set` 难以逐项覆盖，建议整块传 JSON）：
```bash
# 多人多价示例：1~3人梯度价（分），priceInfo 传 null，ratioType=2（加价率）
--set 'goodsDetailList.0.priceInfo={"priceRecordWay":3,"ratioConfig":{"ratioChange":true,"newRatio":"11000","ratioType":2},"unifiedDatePriceInfos":{"dates":[{"startDate":"2026-05-22","endDate":"2028-05-21"}],"weekPriceInfos":[{"inWeek":[1,2,3,4,5,6,7],"priceInfo":null,"priceFactorInfos":[{"salePrice":"","basePrice":"10000","subPrice":"","baseAddRatio":"11000","priceFactors":{"guestFactor":{"adultCount":1,"childAges":null,"childCount":0}}},{"salePrice":"","basePrice":"12000","subPrice":"","baseAddRatio":"11000","priceFactors":{"guestFactor":{"adultCount":2,"childAges":null,"childCount":0}}},{"salePrice":"","basePrice":"15000","subPrice":"","baseAddRatio":"11000","priceFactors":{"guestFactor":{"adultCount":3,"childAges":null,"childCount":0}}}]}]},"priceInfos":null}'
```

> ⚠️ 境外多人多价关键约束：
> - `priceFactorInfos` 必须覆盖 1~`maxAdultAdmissibility` 所有档位（少一档会报错）
> - `priceInfo` 必须传 `null`（与 `priceFactorInfos` 互斥，不能同时有值）
> - `baseAddRatio` 与 `ratioConfig.newRatio` 保持一致
> - 完整示例见 `factory/fullday/schema.json` 的 `scenario_8` / `scenario_9`
> - 境内商品**不需要**传 `priceSameTag`，也不传 `priceFactorInfos`（保持 null）

### 境外产品价格模式（提示）

境外产品价格模式定义在 VPOI 上，**需在进入本 workflow 前**，于 `references/workflows/w8-infra-bootstrap.md` 的基础实体准备阶段通过工具928 完成切换（`switch-price-mode.py --overseas`）。`create-fullday.py` 本身不负责价格模式切换，仅负责创建产品。

若 VPOI 已切换为底价模式，创建产品时需注意：

- **价格字段必须用 `basePrice`**（而非 `salePrice`），否则报"参数错误"：
  ```bash
  --set goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos.0.priceInfo.basePrice=20000
  --set goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos.0.priceInfo.salePrice=
  ```
- 需自行通过 `--set` 传入底价相关字段：
  ```bash
  --set goodsDetailList.0.goodsBaseInfo.priceChangeMode=9 \
  --set goodsDetailList.0.goodsBaseInfo.priceRecodeWay=2 \
  --set goodsDetailList.0.goodsBaseInfo.expectPriceChangeMode=9 \
  --set goodsDetailList.0.priceInfo.priceRecordWay=2
  ```
  （卖价模式为模板默认值，无需额外设置）

> ⚠️ 钟点房无境外场景，不适用本节内容。

---

## Step 3：dry-run 确认（必做）

```bash
python3 factory/fullday/create-fullday.py [全部参数] --dry-run
```

确认输出中 `[约束校验] ✅ 通过` 且最终参数结构符合预期，再去掉 `--dry-run` 正式执行。

---

## Step 4：执行创建

```bash
python3 factory/fullday/create-fullday.py [全部参数]
```

脚本内部处理异步轮询，直接等待输出。成功后脚本**自动**依次执行：

1. **恢复上线**（batchOnlineSwitch status=2）
2. **开房设库存**（若上线失败且原因含"最近90天内至少30天同时有价格和库存"）：自动调用 batchUpdateInventory（invSwitch=1，countType=1520，limitChangeValue=299），再重新上线
   > ⚠️ 自动步骤用 countType=1520（设置余量）。**全新商品首次添加库存**时可能因"不能选择不变"再次失败 → 走下方手动步骤，改用 `--count-type 1121`
3. **缓存刷新**（operationType=1）

自动步骤失败时脚本打印完整手动命令，直接复制执行即可。

---

## Step 5：手动补操作（自动步骤失败时）

**手动开房+设库存**（全新商品首次添加库存用 `--count-type 1121`；已有库存记录用 `1520`）：
```bash
python3 factory/inventory/update-inventory.py --partner-id <partnerId> --poi-id <poiId> --day-room-ids <roomId> --start-date <今天日期> --end-date <今天+2年-1天> --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1
```

**手动上线**：
```bash
python3 factory/ops/online-switch.py --partner-id <partnerId> --poi-id <poiId> --goods-ids <goodsId> --status 2
```

**手动缓存刷新**：
```bash
python3 factory/ops/cache-refresh-audit.py --op 1 --product-id <goodsId>
```

### 改价审核（如商品触发审核流程）

全日房在某些情况下（如调价幅度超出系统阈值）会进入审核状态，需手动审核通过后商品才能正常展示。使用 `factory/ops/cache-refresh-audit.py`：

| 场景 | 命令 |
|------|------|
| BD改价审核 - 通过 | `python3 factory/ops/cache-refresh-audit.py --op 2 --product-id <goodsId> --audit-status 3` |
| BD改价审核 - 驳回 | `python3 factory/ops/cache-refresh-audit.py --op 2 --product-id <goodsId> --audit-status 2` |
| 商家改价审核 - 通过 | `python3 factory/ops/cache-refresh-audit.py --op 3 --product-id <goodsId>` |
| 境外商品缓存刷新 | `python3 factory/ops/cache-refresh-audit.py --op 1 --product-id <goodsId> --overseas` |

> ⚠️ `--audit-status`：`3`=通过（默认），`2`=驳回。BD改价（`--op 2`）需手动指定；商家改价（`--op 3`）默认通过，无需传。
> `--product-id` 即创建返回的 `goodsId`（即 productId）。

---

## 关键约束速查

- `weekendRule` 是 rpCancelModel/rpBreakFastModel 的**直接子字段**（与 normalRule 平级），不是 normalRule 的嵌套字段
- 收费取消的扣费时间点必须**晚于**免费取消截止时间（advanceDays 更小，或天数相等时 advanceHour 更晚）
- 全日房 `rpHourlyRoomUseModel` 必须传 null
- `start-date` = 今天，`end-date` = 今天 + 2 年 - 1 天（batchUpdateInventory 服务端限制）

