# 日常巡检默认资产

> 提示：用于交易日常默认巡检项目统计

## ⚙️ 方向级配置

| 方向 | category 标识 | 首现异常展示阈值（`new_error_min_count`） | 过滤已忽略异常（`filter_ignored_errors`） | 暴涨阈值（`surge_threshold`） | 说明 |
|------|--------------|----------------------------------------|------------------------------------------|------------------------------|------|
| 餐（美食） | `can` | `5` | `true` | `50` | 次数 < 5 的首现异常不渲染到表格（但计入 NEW_COUNT）；自动剔除 Raptor 中已标记忽略的异常 |
| 综（综合） | `gc` | `3` | `false` | `50` | 无过滤，全部展示 |
| 酒（酒店） | `hotel` | `1` | `false` | `50` | 无过滤，全部展示 |
| 景（门票度假） | `travel` | `1` | `false` | `50` | 无过滤，全部展示 |

> 新增方向时，在此表追加一行并填写各项配置即可；阈值为 `1` 表示不过滤。  
> `filter_ignored_errors=true` 时，Step A 会额外调用 `get-summary-table` 获取 STATUS=4（完全忽略）或 STATUS=5（暂时忽略）的异常名单，并在汇总阶段从 currentErrors/previousErrors 中剔除。  
> `surge_threshold` 为环比暴涨判定阈值（百分比整数），变化率超过该值则判定为暴涨；默认 `50` 表示变化率 > 50% 时判定为暴涨。

---

## 🏞️ 景（门票度假）

| 项目 | projectName |
| --- | --- |
| 门票填单页 | rn_travel_travelcore-duo |
| 门票单详页 | rn_travel_order-detail |
| 门票景 x （填单页+单详页） | rn_travel_travelmpplus |
| 度假-跟团填单页 | rn_travel_group-tour-submit-order-base |
| 度假-跟团新订详页 | rn_travel_gty-order-detail |
| 度假-组品填单页 | rn_travel_group-tour-submit-order |
| 度假-组品订详页 | rn_travel_group-tour-order-detail |

## 🍽️ 餐（美食）

| 项目 | projectName |
| --- | --- |
| 团购提单 | rn_meishi_c-group-order-submit |
| 团购订单详情页 | rn_meishi_food-order-detail |
| 智能点餐提单 | rn_meishi_smart-order-food-submit |
| 智能点餐订详 | rn_meishi_smart-order-detail |
| 一键买单提单 | rn_meishi_coupon-pay |
| 一键买单订详 | rn_meishi_coupon-pay-result |

## 🛒 综（综合）

| 项目 | projectName |
| --- | --- |
| 团购提单页 | rn_gc_group-order-submit |
| 新订详页 | rn_gc_group-order-detail |
| 老订详页 | 美团：rn_gc_gctrademrnmodules-mt<br>点评：rn_gc_gctrademrnmodules |

## 🏨 酒（酒店）

| 项目 | projectName |
| --- | --- |
| 新提单页 | rn_hotel_hotelchannel-orderfill-duo |
| 境内单详页 | rn_hotel_hotelchannel-order-detail |
| 境外单详页 | rn_overseahotel_overseahotel-order-detail |

---

*来源：[学城文档](https://km.sankuai.com/collabpage/2758610495)*
