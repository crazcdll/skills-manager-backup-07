# MeGoodsFacade#batchCreateGoods 完整参数模型

> 来源：前端仓库 `/packages/shared/src/types/goods/api-goods-model.ts`
> 对应后端接口：`com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade#batchCreateGoods`
> HTTP路由：`POST /api/gw/v1/product/goods/batchCreateGoods`
>
> ⚠️ **隐性必填**：标注为"⚠️ 隐性必填"的字段文档标注为"否"，但实测不传会报错。interface 层已自动兜底，AI/用户无需手动传递。

---

## 顶层参数（CreateOrUpdateGoodsParam）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `poiId` | Long/String | ✅ | 门店ID（逻辑门店，mtPoiId） |
| `partnerId` | Long | ✅ | 供应商ID |
| `createFlag` | Boolean | ✅ | `true`=真实创建，`false`=预创建校验 |
| `goodsDetailList` | List | ✅ | 产品详情列表，见 GoodsCreateDetailModel |
| `priceAuditInfos` | null | 否 | 创建时传 null |
| `superDealGoodsFlag` | Boolean | 否 | 是否超团（EB/代理商才传） |
| `sellChannelCreateFlag` | Boolean | 否 | 代理商才传 true |

---

## GoodsCreateDetailModel（goodsDetailList 单项）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `goodsBaseInfo` | GoodsBaseInfoModel | ✅ | 产品基本信息 |
| `roomInfo` | RoomInfoModel | ✅ | 上单房型信息 |
| `rpInfo` | RpInfoModel | ✅ | 规则信息（取消/早餐等） |
| `priceInfo` | GoodsPriceUpdateModel | ✅ | 价格信息 |
| `inventoryInfoModel` | InventoryInfoModel | 否 | 库存信息（可选） |

---

## GoodsBaseInfoModel（产品基本信息）

| 字段 | 类型 | 必填 | 说明 | 枚举值 |
|------|------|------|------|--------|
| `goodsId` | Long/null | 否 | 创建时传 null | - |
| `goodsName` | String | ✅ | 商品名称，**不能含"测试"字样** | - |
| `goodsType` | Integer | ✅ | 房型类型 | `1`=全日房 `2`=钟点房 |
| `goodsStatus` | Integer | 否 | 商品状态 | `2`=在线 `3`=暂停 `8`=废除 |
| `partnerId` | Long | ⚠️ 隐性必填 | 必传，interface 层自动填充 | - |
| `poiId` | String | ⚠️ 隐性必填 | 必传，interface 层自动填充 | - |
| `paymentType` | Integer | 否 | 支付类型 | `0`=预付(默认) `1`=现付担保 `2`=现付非担保 |
| `contractNo` | String | ✅ | 合同编号（前置必填，缺少时询问用户） | - |
| `sellChannel` | Integer | 否 | 售卖平台 | `null`=全平台(默认) `9`=仅美团 `10`=仅点评 `15`=全平台（前端真实抓包值，与null等效） |
| `channelNos` | Map | ⚠️ 隐性必填 | **不传报"参数错误"**。默认传 `{"8":["001","002"]}` | `key:4`=差旅 `key:8`=分销 |
| `singleChannelReason` | String | 否 | 单渠道售卖原因，默认传空字符串 | - |
| `priceSameTag` | Integer | 否 | 境外多人多价 | `0`=多价 `1`=同价 |
| `typeLimitValue` | Integer | 否 | 可住时长（**钟点房必填**，单位小时） | `1`~`23` |
| `priceChangeMode` | Integer | ⚠️ 隐性必填 | 必传，默认 `8`=预付，interface 层自动填充 | - |
| `pricingPower` | Integer | ⚠️ 隐性必填 | 必传，默认 `0`，interface 层自动填充 | - |
| `priceRecodeWay` | Integer | ⚠️ 隐性必填 | 必传，默认 `1`，interface 层自动填充 | - |
| `switchStatus` | Integer | ⚠️ 隐性必填 | 必传，默认 `0`，interface 层自动填充 | - |
| `expectPriceChangeMode` | Integer | ⚠️ 隐性必填 | 必传，默认 `8`，interface 层自动填充 | - |
| `deductionAudit` | Boolean | ⚠️ 隐性必填 | **需传 false**，interface 层自动填充 | - |
| `superDealReSale` | Boolean | ⚠️ 隐性必填 | **需传 false**，interface 层自动填充 | - |
| `canAdjustPrice` | Boolean | ⚠️ 隐性必填 | **需传 false**，interface 层自动填充 | - |
| `maxAdultAdmissibility` | Integer | 否 | 最大可入住人数 | - |
| `superDealReSaleStatus` | Integer | 否 | 是否转售 | `0`=不转售 `1`=转售 |

---

## RoomInfoModel（上单房型信息）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `roomId` | Long | ✅ | 上单房型ID（逻辑房型ID） |
| `roomName` | String | ✅ | 上单房型名称 |
| `capacity` | Integer | ✅ | **固定传 0**（后端从房型继承，不要传前端看到的值） |

---

## RpInfoModel（规则信息）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `rpBaseModel` | RpBaseModel | ✅ | 基本规则（自动延期等） |
| `rpBreakFastModel` | RpModel\<RpFoodModel\> | ⚠️ 全日房隐性必填 | **全日房必传**，不传报"系统内部错误"；无早餐传 `num=0` |
| `rpCancelModel` | RpModel\<RpCancelModel\> | ⚠️ 隐性必填 | **必传**，不传报"参数错误"；不可取消传 `cancelItemType=0` |
| `rpHourlyRoomUseModel` | RpModel\<RpHourlyRoomUseModel\> | 否 | **钟点房入住规则（钟点房必填）** |
| `rpEarlyBookingModel` | RpModel\<RpEarlyBookingModel\> | ⚠️ 隐性必填 | **必传**，不限制时传 `latestBookingDays=-1, earliestBookingDays=-1` |
| `rpGuaranteeModel` | RpModel\<RpGuaranteeModel\> | 否 | 担保规则（现付必填） |
| `rpSerialModel` | RpModel\<RpSerialModel\> | ⚠️ 隐性必填 | **必传**，不限制时传 `serialCheckinMin=0, serialCheckinMax=0` |
| `rpServiceModel` | RpModel\<RpServiceModel\> | 否 | 礼包规则 |
| `rpTimeLimitSaleModel` | RpModel\<RpTimeLimitSaleModel\> | 否 | 限时售卖规则 |
| `rpBookingModel` | RpModel\<RpBookingModel\> | 否 | 入住规则（境外BD/商家传） |
| `rpDisplayModel` | RpModel\<RpDisplayModel\> | ⚠️ 隐性必填 | **必传**，不限制时所有字段为 0 |

### RpBaseModel（基本规则）

| 字段 | 类型 | 说明 |
|------|------|------|
| `isAutoRelay` | Integer | `0`=自动延期（默认） `1`=不自动延期 |
| `autoRelayDays` | Integer | 自动延期天数，默认 30 |
| `rpName` | String/null | 产品规则名称，显示在产品列表中（如「含单早-不可取消」）。不传时后端自动生成 |
| `rpCustomName` | String/null | 产品备注文字，追加在 rpName 之后（如「标准价」），用于区分同房型下多个产品，不传时 interface 层自动用时间戳填充 |
| `customNameType` | Integer | `0`=未自定义（默认，后端自动生成 rpName） `1`=自定义（使用传入的 rpCustomName） |
| `saleStrategyInfo` | Object | **必传**，默认 `{"blackWhiteStatus":0,"saleStrategy":[0,1]}`（全日房+套餐均可售） |

### RpFoodModel（早餐规则，通过 RpModel 包装）

> ⚠️ **全日房必传**，不传报「系统内部错误」；无早餐也必须传 `num=0`

| 字段 | 说明 |
|------|------|
| `num` | 早餐份数：`0`=无早餐 `1`=单份 `2`=双份 |
| `effectiveTimes` | 生效时间，通常传 `null` |

**包装结构（RpModel）：**
- `normalRule` = 平日早餐规则
- `weekendRule` = 周末（周六日）早餐规则，不区分时传 `null`；结构与 `normalRule` 相同，直接放在 `rpBreakFastModel` 顶层（与 `normalRule` 平级）
- `updateType` = 固定传 `0`

```json
// 无早餐
{"normalRule": {"effectiveTimes": null, "num": 0}, "weekendRule": null, "updateType": 0}

// 含单早（平日/周末相同）
{"normalRule": {"effectiveTimes": null, "num": 1}, "weekendRule": null, "updateType": 0}

// 平日单早 + 周末双早
{"normalRule": {"effectiveTimes": null, "num": 1}, "weekendRule": {"effectiveTimes": null, "num": 2}, "updateType": 0}
```

### RpCancelModel（取消规则，通过 RpModel 包装）

| 字段 | 类型 | 说明 |
|------|------|------|
| `cancelItemType` | Integer | `0`=不可取消 `1`=可取消 |
| `moveUpCancelDays` | Integer/null | 免费取消提前天数（当天=0，前一天=1） |
| `moveUpCancelHour` | String/null | 免费取消提前时间，格式 `18:00:00` |
| `payCancelPeriodModels` | Array/null | 付费取消模型列表 |
| `effectiveTimes` | Array/null | 特殊日期生效时间（仅 specialRules 用） |

**PrePayCancelPeriodModel（付费取消）：**
| 字段 | 说明 |
|------|------|
| `advanceDays` | 提前天数（当天=0） |
| `advanceHour` | 提前时间，格式 `18:00:00` |
| `penaltyRate` | 罚金率（%），如 `20`=扣20% |

**包装结构（RpModel）：**
- `normalRule` = 平日取消规则
- `weekendRule` = 周末（周六日）取消规则，不区分时传 `null`；结构与 `normalRule` 完全相同，直接放在 `rpCancelModel` 顶层（与 `normalRule` 平级）
- `updateType` = 固定传 `0`

**常用取消政策模板：**
```json
// 不可取消（平日/周末相同，默认）
{"normalRule": {"cancelItemType": 0}, "weekendRule": null, "updateType": 0}

// 免费取消（平日/周末相同，入住当天23:59前可免费取消）
{"normalRule": {"cancelItemType": 1, "moveUpCancelDays": 0, "moveUpCancelHour": "23:59:00"}, "weekendRule": null, "updateType": 0}

// 收费取消（前1天14:00后取消扣20%）
{"normalRule": {"cancelItemType": 1, "moveUpCancelDays": 1, "moveUpCancelHour": "14:00:00",
  "payCancelPeriodModels": [{"advanceDays": 0, "advanceHour": "14:00:00", "penaltyRate": 20}]}, "weekendRule": null, "updateType": 0}

// 平日不可取消 + 周末入住前18:00免费取消（已验证）
{"normalRule": {"cancelItemType": 0}, "weekendRule": {"cancelItemType": 1, "moveUpCancelDays": 0, "moveUpCancelHour": "18:00:00"}, "updateType": 0}
```

### RpHourlyRoomUseModel（钟点房入住规则，通过 RpModel 包装）

| 字段 | 说明 |
|------|------|
| `receiveTimeStart` | 开始接待时间，格式 `08:00`；24小时传 `00:00` |
| `receiveTimeEnd` | 结束接待时间，格式 `22:00`；24小时传 `23:59` |

```json
{"normalRule": {"receiveTimeStart": "08:00", "receiveTimeEnd": "22:00"}, "updateType": 0}
```

### RpEarlyBookingModel（预订规则，通过 RpModel 包装）

| 字段 | 说明 |
|------|------|
| `latestBookingDays` | 最晚预订天数（最少提前N天，不限制=-1） |
| `earliestBookingDays` | 最早预订天数（最多提前N天，不限制=-1） |
| `isDaybreakBooking` | **固定传 1**（支持0点后预订当天） |

### RpGuaranteeModel（担保规则，通过 RpModel 包装）

| 字段 | 说明 |
|------|------|
| `isGuarantee` | `0`=非担保 `1`=担保（现付担保传1） |
| `guaranteeType` | `1`=首晚担保 `2`=整单担保（现付担保必填） |
| `arrivalHour` | 到店时间，格式 `14:00:00`（现付非担保必填） |

### RpSerialModel（连住规则，通过 RpModel 包装）

| 字段 | 说明 |
|------|------|
| `serialCheckinMin` | 最小连住天数（不限制=0） |
| `serialCheckinMax` | 最大连住天数（不限制=0） |

### RpDisplayModel（专客专享，通过 RpModel 包装）

| 字段 | 说明 |
|------|------|
| `hotelMember` | `0`=全用户 `1`=一档会员 `2`=二档会员 |
| `totalGmv` | `0`=全用户 `1`=一档gmv `2`=二档gmv |
| `city` | `0`=全城市 `1`=下单城市在poi城市 `2`=下单城市不在poi城市 |
| `stuSpecial` | `0`=全用户 `1`=仅学生 |
| `distanceRange` | `0`=全用户 `1`=酒店3公里内（附近专享） |
| `riskControl` | `0`=全用户 `1`=风控黑名单不可见 |
| `flagshipNewUser` | `0`=全用户（默认）；固定传 0 |
| `businessTravel` | `0`=全用户（默认）；固定传 0 |
| `employeeExclusive` | `0`=全用户 `1`=仅美团在职员工 |
| `lengthOfStay` | 连住规则可见性（`lengthOfStayType: 0不限 1限制`，`minSerialDays`, `maxSerialDays`） |
| `addressMultiRestriction` | 地址规则（`addressMultiRestrictionType: 0不限 1异地 2特殊`，`addressModelList`） |

### RpTimeLimitSaleModel（限时售卖，通过 RpModel 包装）

| 字段 | 说明 |
|------|------|
| `enableBookingType` | `0`=未设置日期全天售卖 `1`=未设置日期全天不售卖 |
| `timeLimitSaleModels` | 限时售卖规则列表 |

**timeLimitSaleModels 单项：**
| 字段 | 说明 |
|------|------|
| `date.startDate` | 生效开始日期，格式 `2024-04-25` |
| `date.endDate` | 生效结束日期 |
| `normalRule` | 平日时间段列表 `[{"enableBookingTimeStart":"06:00","enableBookingTimeEnd":"23:59"}]` |
| `weekendRule` | 周末时间段列表（可选） |

### RpBookingModel（入住规则，通过 RpModel 包装）

| 字段 | 说明 |
|------|------|
| `maxAdultAdmissibility` | 最大可入住成人数 |
| `targetUser` | 适用人群（`targetUserRule`: `0`不限 `1`适用 `2`不适用；`targetUserRestrictionList`） |

### RpServiceModel（礼包规则，通过 RpModel 包装）

```json
{"normalRule": {"serviceModels": [{"serviceTmplId": 12345}]}, "updateType": 0}
```

---

## GoodsPriceUpdateModel（价格信息）

| 字段 | 类型 | 说明 |
|------|------|------|
| `priceRecordWay` | Integer | 价格录入方式，`1`=卖价 `2`=底价（BP链路） |
| `ratioConfig` | Object | 佣金率配置 |
| `priceInfos` | null | 创建时传 null |
| `unifiedDatePriceInfos` | Object | 统一价格信息（必用此结构） |

**统一价格（实际传参格式）：**
```json
{
  "priceRecordWay": 1,
  "ratioConfig": {"newRatio": "1100", "ratioChange": true, "ratioType": 1},
  "priceInfos": null,
  "unifiedDatePriceInfos": {
    "dates": [{"startDate": "2026-05-20", "endDate": "2028-05-20"}],
    "weekPriceInfos": [{
      "inWeek": [1,2,3,4,5,6,7],
      "priceInfo": {"salePrice": "20000", "basePrice": "", "subPrice": "", "subRatio": "1100"},
      "priceFactorInfos": null
    }]
  }
}
```
> 注意：`salePrice` 单位为**分**（元×100）；`dates` 不能为 null，必须传具体日期范围；`ratioChange` 必须为 `true`；`newRatio` 单位千分比（1100=11%）

---

## RpModel\<T\> 通用包装结构

所有规则均通过 RpModel 包装：
```json
{
  "normalRule": { ... },     // 平日规则（必填）
  "weekendRule": null,       // 周末规则（不区分周末传 null）
  "specialRules": null,      // 特殊日期规则
  "updateType": 0            // 必传 0，不传报参数错误
}
```

---

## 接口返回

- **正常返回**：`{"success": true, "data": "uuid-xxxxx"}` → uuid 为异步任务ID
- **轮询进度**：`MeGoodsFacade#getProcessRate(partnerId, poiId, uuid)`
- **查询结果**：等待 10~30 秒后调用 `queryGoodsInfo`

---

## 关键枚举速查

| 枚举 | 值 | 说明 |
|------|-----|------|
| goodsType | 1 | 全日房 |
| goodsType | 2 | 钟点房 |
| paymentType | 0 | 预付（默认） |
| paymentType | 1 | 现付担保 |
| paymentType | 2 | 现付非担保 |
| sellChannel | null | 全平台（默认，不传即可） |
| sellChannel | 15 | 全平台（前端真实抓包值，与null等效） |
| sellChannel | 9 | 仅美团 |
| sellChannel | 10 | 仅点评 |
| cancelItemType | 0 | 不可取消（默认） |
| cancelItemType | 1 | 可取消 |
| ratioNew | "1100" | 佣金率 11%（千分比，默认值） |

