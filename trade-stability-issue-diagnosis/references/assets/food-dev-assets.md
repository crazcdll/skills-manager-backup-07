# 到餐交易前端研发资产映射表

数据来源：https://km.sankuai.com/collabpage/2756656397
特殊说明
1、DUO页面特有DUO页面ID、DUO页面链接
2、I版特有pageId
3、i版和小程序技术栈特有页面路径，无Bundle信息和diva地址。DUO、MRN和MAX无业务路径，独有Bundle信息和diva地址
---

## 页面索引

| 页面 | 技术栈 |
|------|--------|
| [团购提单（DUO）](#团购提单duo) | DUO |
| [团购提单（MAX）](#团购提单max) | MAX |
| [支付结果页（MRN）](#支付结果页mrn) | MRN |
| [支付结果页（小程序-美小）](#支付结果页小程序-美小) | 小程序 |
| [支付结果页（直播）](#支付结果页直播) | MRN |
| [订单详情页（DUO）](#订单详情页duo) | DUO |
| [订单详情页（i版）](#订单详情页i版) | i版 |
| [申请退款（DUO）](#申请退款duo) | DUO |
| [申请退款（i版）](#申请退款i版) | i版 |
| [券码详情](#券码详情) | MRN |
| [赠礼发送](#赠礼发送) | MRN |
| [赠礼接受](#赠礼接受) | DUO |
| [取消订单弹窗](#取消订单弹窗) | MAX |
| [交易快照（MRN）](#交易快照mrn) | MRN |
| [交易快照（DUO）](#交易快照duo) | DUO |
| [订单列表](#订单列表) | MAX |
| [已消费退申请](#已消费退申请) | MRN |
| [已消费退详情](#已消费退详情) | MRN |
| [配送/自提提单](#配送自提提单) | MAX |
| [配送订单详情](#配送订单详情) | MAX |
| [物流详情](#物流详情) | DUO |
| [物流详情B端](#物流详情b端) | DUO |
| [配送退款](#配送退款) | MAX |
| [秒提购物车](#秒提购物车) | MRN |
| [智能点餐货架+点餐购物车](#智能点餐货架_点餐购物车) | DUO |
| [智能点餐货架底部bar+服务员](#智能点餐货架底部bar_服务员) | DUO |
| [智能点餐提单](#智能点餐提单) | DUO |
| [智能点餐订详](#智能点餐订详) | DUO |
| [智能点餐退款](#智能点餐退款) | DUO |
| [团购购物车](#团购购物车) | MRN |
| [购物车提单](#购物车提单) | MRN |
| [一键买单提单](#一键买单提单) | DUO |
| [一键买单订详](#一键买单订详) | DUO |
| [一键买单申请退款](#一键买单申请退款) | DUO |
| [优惠买单提单（MRN）](#优惠买单提单mrn) | MRN |
| [优惠买单提单（美小）](#优惠买单提单美小) | 小程序 |
| [优惠买单提单（点小）](#优惠买单提单点小) | 小程序 |
| [优惠买单订单详情（MRN）](#优惠买单订单详情mrn) | MRN |
| [优惠买单订单详情（美小）](#优惠买单订单详情美小) | 小程序 |
| [优惠买单订单详情（点小）](#优惠买单订单详情点小) | 小程序 |
| [优惠买单订单结果（点小）](#优惠买单订单结果点小) | 小程序 |
| [抵用券列表](#抵用券列表) | MRN |
| [C扫B提单](#c扫b提单) | i版 |
| [C扫B支付结果页](#c扫b支付结果页) | i版 |
| [选择优惠页](#选择优惠页) | i版 |
| [拼团结果页](#拼团结果页) | DUO |

---

## 团购提单（DUO）

| 属性 | 值 |
|------|-----|
| **关键词** | 团购提单、提单页、下单页、确认订单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小/圈小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_c-group-order-submit |
| **DUO页面ID** | DUO-12413 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12413?branch=master |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/duo-food-order-submit.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/duo-food-order-submit/file/list?branch=master |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_c-group-order-submit/versions?env=prod |
| **projectId** | 10749 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=10749 | 
| **后端日志（precreate）Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志（precreate）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.grouptrade.precreate.apic |
| **后端日志（query）Appkey** | com.sankuai.web.order.front |
| **后端日志（query）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.front |

**CID（Ocean配置）**：
- 美团：c_meishi_rao5v99i（https://ocean.sankuai.com/config/#/page/detail?id=42054242&channelId=28）
- 点评：c_sfcp07i（https://ocean.sankuai.com/config/#/page/detail?id=40000835&channelId=28）
- 美小：c_90v1nrbr（https://ocean.sankuai.com/config/#/page/detail?id=40701006&channelId=28）
- 点小：c_7tcab35u（https://ocean.sankuai.com/config/#/page/detail?id=40308344&channelId=28）
- 美团鸿蒙：c_meishi_xkxr9rrq（https://ocean.sankuai.com/config/#/page/detail?id=43107590&channelId=28）
- 点评鸿蒙：c_meishi_m1kk37gm（https://ocean.sankuai.com/config/#/page/detail?id=43107639&channelId=28）

**CIA**：
- 美团：https://cia.sankuai.com/page/detail?id=136764667&tab=module
- 点评：https://cia.sankuai.com/page/detail?id=134456340
- 美小：https://cia.sankuai.com/page/detail?id=134456016
- 点小：https://cia.sankuai.com/page/detail?id=134456052
- 百度：https://cia.sankuai.com/page/detail?id=757226788
- 美团鸿蒙：https://cia.sankuai.com/page/detail?id=609969361
- 点评鸿蒙：https://cia.sankuai.com/page/detail?id=623154659

---

## 团购提单（MAX）

| 属性 | 值 |
|------|-----|
| **关键词** | 团购提单旧版、MAX提单、圈圈站外提单、商企通提单、百度提单 |
| **技术栈** | MAX（旧版） |
| **覆盖端** | 圈圈站外/商企通/百度/支付宝/惠省/其他 |
| **覆盖系统** | iOS/Android |
| **bundle** | rn_meishi_c-group-order-submit-max |
| **H5路径** | https://awp.meituan.com/meis/biz-cross-food-transaction/group-order-submit/web/index.html?dealId= |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/biz-cross-food-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/biz-cross-food-transaction/file/list?path=group-order-submit |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_c-group-order-submit-max/versions |
| **projectId** | 14930 |
| **raptor客户端异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=14930 |
| **raptor小程序异常链接** | https://raptor.mws.sankuai.com/mp/error/list?projectId=14930 |
| **后端日志（precreate）Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志（precreate）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.grouptrade.precreate.apic |
| **后端日志（query）Appkey** | com.sankuai.web.order.front |
| **后端日志（query）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.front |

**CID（Ocean配置）**：
- c_meishi_onqxln25（https://ocean.sankuai.com/config/#/page/detail?id=43240625&channelId=28）

**CIA**：
- 美团：https://cia.sankuai.com/page/detail?id=136764667&tab=module
- 点评：https://cia.sankuai.com/page/detail?id=134456340
- 美小：https://cia.sankuai.com/page/detail?id=134456016
- 点小：https://cia.sankuai.com/page/detail?id=134456052
- 百度：https://cia.sankuai.com/page/detail?id=757226788
- 美团鸿蒙：https://cia.sankuai.com/page/detail?id=609969361
- 点评鸿蒙：https://cia.sankuai.com/page/detail?id=623154659

---

## 支付结果页（MRN）

| 属性 | 值 |
|------|-----|
| **关键词** | 支付结果、支付成功、支付完成、付款结果 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android |
| **bundle** | rn_meishi_food-pay-result |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi-transaction/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_food-pay-result/versions |
| **projectId** | 9907 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=9907 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- 美团：c_yh70r8a（https://ocean.sankuai.com/config/#/page/detail?id=40000933&channelId=28）
- 点评：c_itr20uu（https://ocean.sankuai.com/config/#/page/detail?id=40000836&channelId=28）

**CIA**：
- 美团：https://cia.sankuai.com/page/detail?id=134456021&tab=module
- 点评：https://cia.sankuai.com/page/detail?id=134456028

---

## 支付结果页（小程序-美小）

| 属性 | 值 |
|------|-----|
| **关键词** | 美小支付结果、小程序支付结果 |
| **技术栈** | 小程序 |
| **覆盖端** | 美小 |
| **覆盖系统** | iOS/Android |
| **页面路径** | food/pages/mt/pay-result/index |
| **仓库SSH** | ssh://git@git.sankuai.com/dfe/biz-miniapp-food-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/dfe/biz-miniapp-food-transaction/file/list?path=packages%2Fpay-result |
| **projectId** | 11699 |
| **raptor 异常** | https://raptor.mws.sankuai.com/mp/error/list?projectId=11699 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- 美小：c_meishi_muloxd4i

**CIA**：
- 美小：https://cia.sankuai.com/page/detail?id=134456087

---

## 支付结果页（直播MRN）

| 属性 | 值 |
|------|-----|
| **关键词** | 直播支付结果、直播间弹窗 |
| **技术栈** | MRN |
| **覆盖端** | 美团 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_group-pay-result-slide-modal |
| **仓库SSH** | ssh://git@git.sankuai.com/dfe/biz-cross-food-transaction-group.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/dfe/biz-cross-food-transaction-group/file/list?path=group-pay-result-slide-modal |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_group-pay-result-slide-modal/versions |
| **projectId** | 27179 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=27179 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- 美团：c_meishi_1b73khe6（https://ocean.sankuai.com/config/#/page/detail?id=42959047&channelId=28&tabName=page&source_click=21）

**CIA**：
- 美团：https://cia.sankuai.com/page/detail?id=482142409

---

## 订单详情页（DUO）

| 属性 | 值 |
|------|-----|
| **关键词** | 订单详情、订单信息、查看订单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小/圈小/圈圈站外/商企通/惠省 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_food-order-detail |
| **DUO页面ID** | DUO-12299 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12299?branch=master |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi-transaction/file/list?path=food-order-detail-duo&branch=master |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_food-order-detail/versions?env=prod |
| **projectId** | 8699 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=8699 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.foodtrade.groupbuy.apic |

**CID（Ocean配置）**：
- c_8f91rdb

**CIA**：
- https://cia.sankuai.com/page/detail?id=134456021

---

## 订单详情页（i版）

| 属性 | 值 |
|------|-----|
| **关键词** | i版订单详情、百度订单详情、支付宝订单详情 |
| **技术栈** | i版 |
| **覆盖端** | 百度/支付宝/其他 |
| **覆盖系统** | iOS/Android |
| **页面路径** | https://meishi.meituan.com/i/order/detail/{{orderId}} |
| **raptor项目名** | com.sankuai.meishi.fe.iorderdetail |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi.mobile.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi.mobile/file/list |
| **projectId** | 2714 |
| **pageId** | 12278 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=2714&pageId=12278 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.foodtrade.groupbuy.apic |

---

## 申请退款（DUO）

| 属性 | 值 |
|------|-----|
| **关键词** | 申请退款、退款、取消订单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小/圈小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_group-cancel-order-new |
| **DUO页面ID** | DUO-12453 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12453?branch=master |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi-transaction/file/list?path=group-cancel-order-new&branch=master |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_group-cancel-order-new/versions?env=prod |
| **projectId** | 38912 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=38912 |
| **后端日志Appkey** | com.sankuai.web.refund.applyproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.refund.applyproxy |

**CID（Ocean配置）**：
- c_meishi_xhks37n3

**CIA**：
- https://cia.sankuai.com/page/detail?id=134456021

---

## 申请退款（i版）

| 属性 | 值 |
|------|-----|
| **关键词** | i版退款、百度退款、支付宝退款 |
| **技术栈** | i版 |
| **覆盖端** | 商企通/百度/支付宝/其他 |
| **覆盖系统** | iOS/Android |
| **页面路径** | https://meishi.meituan.com/i/refund/{{orderId}} |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi.mobile.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi.mobile/file/list |
| **projectId** | 2714（同 i版订单详情） |
| **pageId** | 12277 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=2714&pageId=12277 |
| **后端日志Appkey** | com.sankuai.web.refund.applyproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.refund.applyproxy |

**CID（Ocean配置）**：
- 美团：c_gphEA
- 点评：c_mIVcz
- 微信：c_mIVcz

**CIA**：
- 美团：https://cia.sankuai.com/page/detail?id=134456021
- 点评：https://cia.sankuai.com/page/detail?id=134456028
- 微信：https://cia.sankuai.com/page/detail?id=134456028

---

## 券码详情

| 属性 | 值 |
|------|-----|
| **关键词** | 券码、优惠券、券码详情、去用券 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_coupon-detail |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi-transaction/file/list?path=group-coupon-detail |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_coupon-detail/versions |
| **projectId** | 9963 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=9963 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- 美团：c_6eo1z1hf（https://ocean.sankuai.com/config/#/page/detail?id=40678450&channelId=28）
- 点评：c_sz2kxrk2（https://ocean.sankuai.com/config/#/page/detail?id=40748359&channelId=28）

**CIA**：
- 美团：https://cia.sankuai.com/page/detail?id=134456142
- 点评：https://cia.sankuai.com/page/detail?id=134456072

---

## 赠礼发送

| 属性 | 值 |
|------|-----|
| **关键词** | 赠礼、送礼 |
| **技术栈** | MRN |
| **覆盖端** | 美团 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_gift-giving |
| **入口** | 支付结果页 / 订单详情 / 券码详情 |
| **仓库SSH** | ssh://git@git.sankuai.com/MEIS/meishi-mrn.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/MEIS/meishi-mrn/file/list?codeArea=bj&branch=refs%2Fheads%2Fmaster&path=gift-giving |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_gift-giving/versions |
| **projectId** | 11563 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=11563 |
| **后端日志（foodtrade apic）Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志（foodtrade apic）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.foodtrade.groupbuy.apic |

**CID（Ocean配置）**：
- 美团：c_meishi_m4hfiti9（https://ocean.sankuai.com/config/#/page/detail?id=43319681&channelId=28）

**CIA**：
- 美团：https://cia.sankuai.com/page/detail?id=866261759

---

## 赠礼接受

| 属性 | 值 |
|------|-----|
| **关键词** | 赠礼接受、收礼、美食礼品卡 |
| **技术栈** | DUO |
| **覆盖端** | 美小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_gift-receipt |
| **DUO页面ID** | DUO-12431 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12431?protocolId=0006&protocolVersion=0001 |
| **H5路径** | https://awp.meituan.com/dfe/duo-page/gift-receipt/web/index.html |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/food-duo/file/list?path=gift-receipt |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_gift-receipt/versions |
| **projectId** | 34117 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=34117 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.foodtrade.groupbuy.apic |

**CID（Ocean配置）**：
- 美小：c_meishi_urvhx3zl（https://ocean.sankuai.com/config/#/page/detail?id=43319682&channelId=28）

**CIA**：
- 美小：https://cia.sankuai.com/page/detail?id=866326978

---

## 取消订单弹窗

| 属性 | 值 |
|------|-----|
| **关键词** | 取消订单弹窗、取消订单 |
| **技术栈** | MAX |
| **覆盖端** | 美团 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_food-cancel-order |
| **入口** | 订单详情-取消订单 |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/biz-cross-food-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/biz-cross-food-transaction/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_food-cancel-order/versions |
| **projectId** | 13843 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=13843 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- 美团：c_meishi_6ugsewk9（https://ocean.sankuai.com/config/#/page/detail?id=42217967&channelId=28）

**CIA**：
- 美团：https://cia.sankuai.com/page/detail?id=143251306

---

## 交易快照（MRN）

| 属性 | 值 |
|------|-----|
| **关键词** | 交易快照 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_transaction-snapshot |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi-transaction/file/list?branch=refs%2Fheads%2Fmaster&path=transaction-snapshot |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_transaction-snapshot/versions?env=prod |
| **projectId** | 11010 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=11010 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- c_meishi_am3i50v9（https://ocean.sankuai.com/config/#/page/detail?id=42065963&channelId=28）

---

## 交易快照（DUO）

| 属性 | 值 |
|------|-----|
| **关键词** | 交易快照（DUO版） |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_transaction-snapshot-duo |
| **DUO页面ID** | DUO-12422 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12422?branch=master |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/transaction-snapshot/file/list?path=&branch=master |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_transaction-snapshot-duo/versions |
| **projectId** | 31637 |
| **raptor 异常** | http://raptor.mws.sankuai.com/frontend/error/list?projectId=31637 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

---

## 团购购物车

| 属性 | 值 |
|------|-----|
| **关键词** | 购物车、团购购物车、购物车页 |
| **技术栈** | MRN |
| **覆盖端** | 美团 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_food-shopping-cart-list |
| **仓库SSH** | ssh://git@git.sankuai.com/dcan/food-mrn.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/dcan/food-mrn/file/list?path=food-shopping-cart-list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_food-shopping-cart-list/versions |
| **projectId** | 9522 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=9522 |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/food_cart_order（⚠️ topic 为下划线格式，logcenter 查询时直接用 `-l food_cart_order`） |

**CID（Ocean配置）**：
- 美团：c_meishi_mvt1vdli

**CIA**：
- https://cia.sankuai.com/page/detail?id=134456021

---

## 购物车提单

| 属性 | 值 |
|------|-----|
| **关键词** | 购物车提单、秒提提单 |
| **技术栈** | MRN |
| **覆盖端** | 美团 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_c-group-order-submit-old |
| **仓库SSH** | 待填写 |
| **仓库https链接** | 待填写 |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_c-group-order-submit-old/versions?env=prod |
| **projectId** | 14801 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=14801 |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/food_cart_order |

**CID（Ocean配置）**：
- 综：c_gc_031k2o7b
- 餐：c_meishi_rao5v99i（与团购提单一致）

**CIA**：
- https://cia.sankuai.com/page/detail?id=134456021

---

## 秒提购物车

| 属性 | 值 |
|------|-----|
| **关键词** | 秒提购物车、秒提门店购物车、秒提 |
| **技术栈** | DUO |
| **覆盖端** | 美团 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_food-mop-cart-list |
| **DUO页面ID** | DUO-12443 |
| **仓库SSH** | ssh://git@git.sankuai.com/dfe/biz-cross-intelligent-order.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/dfe/biz-cross-intelligent-order/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_food-mop-cart-list/versions |
| **projectId** | 35193 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=35193 |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/food_cart_order |

**CID（Ocean配置）**：
- c_meishi_p99f86kx

---

## 配送/自提提单

| 属性 | 值 |
|------|-----|
| **关键词** | 配送自提、自提提单、配送提单、预约配送 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_group-order-submit-delivery |
| **入口** | 订单列表-预约配送 / 订单详情-预约配送 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/order-submit-delivery.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/order-submit-delivery/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_group-order-submit-delivery/versions |
| **projectId** | 32227 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=32227 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- c_meishi_5cq45lir（https://ocean.sankuai.com/config/#/page/detail?id=43298750&channelId=28）

---

## 配送订单详情

| 属性 | 值 |
|------|-----|
| **关键词** | 配送订单详情、配送详情 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_delivery-food-order-detail |
| **入口** | 配送提单 / 订单列表 |
| **仓库SSH** | ssh://git@git.sankuai.com/dfe/biz-cross-food-transaction-group.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/dfe/biz-cross-food-transaction-group/file/list?path=delivery-food-order-detail |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_delivery-food-order-detail/versions |
| **projectId** | 15913 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=15913 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- c_meishi_tgje1vqu

---

## 物流详情

| 属性 | 值 |
|------|-----|
| **关键词** | 物流详情、配送状态、配送轨迹 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android |
| **bundle** | rn_meishi_delivery-logistic-detail |
| **DUO页面ID** | DUO-12305 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12305?protocolId=0001&protocolVersion=0001 |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/food-duo/file/list?path=delivery-logistic-detail |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_delivery-logistic-detail/versions |
| **projectId** | 29056 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=29056 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.booking |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.foodtrade.groupbuy.booking |
| **APP跳链** | imeituan://www.meituan.com/mrn?mrn_biz=meishi&mrn_entry=delivery-logistic-detail&mrn_component=main |
| **H5跳链** | https://awp.meituan.com/dfe/duo-page/delivery-logistic-detail/web/index.html |

---

## 配送退款

| 属性 | 值 |
|------|-----|
| **关键词** | 配送退款、配送取消 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_delivery-food-cancel-order |
| **入口** | 配送订单详情 |
| **仓库SSH** | ssh://git@git.sankuai.com/dfe/biz-cross-food-transaction-group.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/dfe/biz-cross-food-transaction-group/file/list?path=delivery-food-order-detail |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_delivery-food-cancel-order/versions |
| **projectId** | 15915 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=15915 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- c_meishi_dqpnbg2w

---

## 智能点餐货架_点餐购物车

| 属性 | 值 |
|------|-----|
| **关键词** | 智能点餐购物车、点餐购物车、智能点餐货架 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_intelli-order-home |
| **仓库SSH** | ssh://git@git.sankuai.com/dfe/biz-cross-intelligent-order.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/dfe/biz-cross-intelligent-order/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_intelli-order-home/versions |
| **projectId** | 34467 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=34467 |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/food_cart_order |

---

## 智能点餐货架底部bar_服务员

| 属性 | 值 |
|------|-----|
| **关键词** | 点餐货架底部bar、服务员、点餐底部价格区域 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_intelli-order-home |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/smart-waiter-unified.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/smart-waiter-unified/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_intelli-order-home/versions |
| **projectId** | 34467 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=34467 |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/food_cart_order |

---

## 智能点餐提单

| 属性 | 值 |
|------|-----|
| **关键词** | 智能点餐提单、点餐提单、点餐下单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_smart-order-food-submit |
| **DUO页面ID** | DUO-12436 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12436?branch=master |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/smart-ordering.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/smart-ordering/file/list?path=order-submit |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_smart-order-food-submit/versions |
| **projectId** | 34867 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=34867 |
| **后端日志Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.grouptrade.precreate.apic |

**CID（Ocean配置）**：
- c_meishi_pc2p5yfu（https://ocean.sankuai.com/config/#/page/detail?id=43368983&channelId=28）

**CIA**：
- https://cia.sankuai.com/page/detail?id=946659215

---

## 智能点餐订详

| 属性 | 值 |
|------|-----|
| **关键词** | 智能点餐订单详情、点餐订单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_smart-order-detail |
| **DUO页面ID** | DUO-12437 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12437?branch=master |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/smart-ordering.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/smart-ordering/file/list?path=smart-order-detail |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_smart-order-detail/versions |
| **projectId** | 34765 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=34765 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.foodtrade.groupbuy.apic |

**CID（Ocean配置）**：
- c_meishi_y0frjxgd（https://ocean.sankuai.com/config/#/page/detail?id=43367405&channelId=28）

**CIA**：
- https://cia.sankuai.com/page/detail?id=962819692

---

## 智能点餐退款

| 属性 | 值 |
|------|-----|
| **关键词** | 智能点餐退款、点餐退款 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_smart-refund-detail |
| **DUO页面ID** | DUO-12451 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12451?branch=master |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/smart-ordering.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/smart-ordering/file/list?path=smart-refund-detail |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_smart-refund-detail/versions |
| **projectId** | 36876 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=36876 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.foodtrade.groupbuy.apic |

**CID（Ocean配置）**：
- c_meishi_nc0w2m5z（https://ocean.sankuai.com/config/#/page/detail?id=43446722&channelId=28）

**CIA**：
- https://cia.sankuai.com/page/detail?id=1078093110

---

## 一键买单提单

| 属性 | 值 |
|------|-----|
| **关键词** | 一键买单、一键买单提单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_coupon-pay |
| **DUO页面ID** | DUO-12416 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12416?protocolId=0023&protocolVersion=0001 |
| **入口** | 支持一键买单的 POI / 券码详情页-去买单 |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/food-duo/file/list?path=coupon-pay |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_coupon-pay/versions |
| **projectId** | 30176 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=30176 |
| **后端日志Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.grouptrade.precreate.apic |

**CID（Ocean配置）**：
- c_meishi_p1pyv5zo（https://ocean.sankuai.com/config/#/page/detail?id=43142284&channelId=28）

**CIA**：
- https://cia.sankuai.com/page/detail?id=661510158

---

## 一键买单订详

| 属性 | 值 |
|------|-----|
| **关键词** | 一键买单订单详情、一键买单订详 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_coupon-pay-result |
| **DUO页面ID** | DUO-12420 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12420 |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/food-duo/file/list?path=coupon-pay-result |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_coupon-pay-result/versions |
| **projectId** | 33636 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=33636 |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

**CID（Ocean配置）**：
- c_mewpv96（https://ocean.sankuai.com/config/#/page/detail?id=40000934&channelId=28）

**CIA**：
- https://cia.sankuai.com/page/detail?id=134456101

---

## 一键买单申请退款

| 属性 | 值 |
|------|-----|
| **关键词** | 一键买单退款、一键买单申请退款 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_coupon-pay-cancel |
| **DUO页面ID** | DUO-12417 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12417?protocolId=0008&protocolVersion=0001 |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/food-duo/file/list?path=coupon-pay-cancel |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_coupon-pay-cancel/versions |
| **projectId** | 30359 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=30359 |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

**CID（Ocean配置）**：
- c_meishi_txu19v2c（https://ocean.sankuai.com/config/#/page/detail?id=43142336&channelId=28）

**CIA**：
- https://cia.sankuai.com/page/detail?id=649319003

---

## 优惠买单提单（MRN）

| 属性 | 值 |
|------|-----|
| **关键词** | 优惠买单、优惠买单提单 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_pay |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi-transaction/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_pay/versions |
| **projectId** | 6709 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=6709 |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

**CID（Ocean配置）**：
- c_7eby4oi

---

## 优惠买单提单（美小）

| 属性 | 值 |
|------|-----|
| **关键词** | 美小优惠买单提单 |
| **技术栈** | 小程序 |
| **覆盖端** | 美小 |
| **仓库** | biz-miniapp-food-transaction |
| **页面路径** | food/pages/maiton/order/order |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/biz-miniapp-food-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/biz-miniapp-food-transaction/file/list |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

**CID（Ocean配置）**：
- c_c33mwasl

---

## 优惠买单提单（点小）

| 属性 | 值 |
|------|-----|
| **关键词** | 点小优惠买单提单 |
| **技术栈** | 小程序 |
| **覆盖端** | 点小 |
| **仓库** | meishi.wxapp |
| **页面路径** | packages/msdeal/pages/maiton-order/maiton-order |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi.wxapp.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi.wxapp/file/list |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

---

## 优惠买单订单详情（MRN）

| 属性 | 值 |
|------|-----|
| **关键词** | 优惠买单订单详情、买单订单详情 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_pay-result |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi-transaction/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_pay-result/versions |
| **projectId** | 6871 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=6871 |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

**CID（Ocean配置）**：
- c_mewpv96

---

## 优惠买单订单详情（美小）

| 属性 | 值 |
|------|-----|
| **关键词** | 美小优惠买单订单详情 |
| **技术栈** | 小程序 |
| **覆盖端** | 美小 |
| **仓库** | biz-miniapp-food-transaction |
| **页面路径** | /food/pages/maiton/order-detail/order-detail |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/biz-miniapp-food-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/biz-miniapp-food-transaction/file/list |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

**CID（Ocean配置）**：
- c_2oke2hvy

---

## 优惠买单订单详情（点小）

| 属性 | 值 |
|------|-----|
| **关键词** | 点小优惠买单订单详情 |
| **技术栈** | 小程序 |
| **覆盖端** | 点小 |
| **仓库** | meishi.wxapp |
| **页面路径** | packages/msdeal/pages/maiton-order-detail/maiton-order-detail |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi.wxapp.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi.wxapp/file/list |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

**CID（Ocean配置）**：
- c_tfls11k1

---

## 优惠买单订单结果（点小）

| 属性 | 值 |
|------|-----|
| **关键词** | 点小优惠买单订单结果 |
| **技术栈** | 小程序 |
| **覆盖端** | 点小 |
| **仓库** | meishi.wxapp |
| **页面路径** | packages/msdeal/pages/maiton-order-succ/maiton-order-succ |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi.wxapp.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi.wxapp/file/list |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

**CID（Ocean配置）**：
- c_s6z2ibg9

---

## 抵用券列表

| 属性 | 值 |
|------|-----|
| **关键词** | 抵用券列表、优惠买单抵用券 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **bundle** | rn_meishi_pay-voucher-list |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/meishi-transaction/file/list?path=maiton-voucher-list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_pay-voucher-list/versions |
| **projectId** | 6707 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=6707 |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/dianping_dc_hui_huibusiness |

**CID（Ocean配置）**：
- c_meishi_pns3mouv（https://ocean.sankuai.com/config/#/page/detail?id=43240625&channelId=28）

---

## C扫B提单

| 属性 | 值 |
|------|-----|
| **关键词** | C扫B、扫码、C扫B提单 |
| **技术栈** | i版 |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **仓库SSH** | ssh://git@git.dianpingoa.com/ed-f2e/app-menuorder-flashpay.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/ed-f2e/app-menuorder-flashpay/file/list |
| **projectId** | 7991 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=7991 |
| **后端日志Appkey** | ka-mixpay-web |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/ka-mixpay-web |

---

## C扫B支付结果页

| 属性 | 值 |
|------|-----|
| **关键词** | C扫B支付结果 |
| **技术栈** | i版 |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **仓库** | app-menuorder-flashpay |
| **仓库SSH** | ssh://git@git.dianpingoa.com/ed-f2e/app-menuorder-flashpay.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/ed-f2e/app-menuorder-flashpay/file/list |
| **后端日志Appkey** | ka-mixpay-web |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/ka-mixpay-web |

---

## 选择优惠页

| 属性 | 值 |
|------|-----|
| **关键词** | 选择优惠页、优惠选择 |
| **技术栈** | i版 |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **仓库** | app-menuorder-flashpay |
| **仓库SSH** | ssh://git@git.dianpingoa.com/ed-f2e/app-menuorder-flashpay.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/ed-f2e/app-menuorder-flashpay/file/list |
| **后端日志Appkey** | ka-mixpay-web |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/ka-mixpay-web |

---

## 拼团结果页

| 属性 | 值 |
|------|-----|
| **关键词** | 拼团结果、特团拼团结果 |
| **技术栈** | DUO |
| **覆盖端** | 美团 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_group-pintuan-result |
| **DUO页面ID** | DUO-12319 |
| **DUO页面链接** | https://duo.sankuai.com/portal/page/detail2/12319 |
| **备注** | 区分餐综 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/duo-pintuan-result.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/duo-pintuan-result/file/list?path=&branch=master |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_group-pintuan-result/versions |
| **projectId** | 26582 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=26582 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.order.groupapiqueryproxy |

**CID（Ocean配置）**：
- c_special_groupon_mtf9otu7（https://ocean.sankuai.com/config/#/page/detail?id=43240625&channelId=28）

---

## 订单列表

| 属性 | 值 |
|------|-----|
| **关键词** | 订单列表、我的订单 |
| **技术栈** | MAX |
| **覆盖端** | 美团 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_food-order-list |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/biz-cross-food-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/biz-cross-food-transaction/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_food-order-list/versions |
| **projectId** | 13842 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=13842 |
| **后端日志Appkey** | com.sankuai.foodtrade.food.trade |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.foodtrade.food.trade |

**CID（Ocean配置）**：
- c_meishi_6ugsewk9

**CIA**：
- 美团：https://cia.sankuai.com/page/detail?id=143251306

---

## 已消费退申请

| 属性 | 值 |
|------|-----|
| **关键词** | 已消费退申请、已消费退款申请 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_self-refund-submit |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/biz-cross-food-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/biz-cross-food-transaction/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_self-refund-submit/versions |
| **projectId** | 16178 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=16178 |
| **后端日志Appkey** | com.sankuai.web.refund.applyproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.refund.applyproxy |

**CID（Ocean配置）**：
- c_meishi_5jevcqwp

---

## 已消费退详情

| 属性 | 值 |
|------|-----|
| **关键词** | 已消费退详情、已消费退款详情 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_self-refund-detail |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/biz-cross-food-transaction.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/biz-cross-food-transaction/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_self-refund-detail/versions |
| **projectId** | 16179 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=16179 |
| **后端日志Appkey** | com.sankuai.web.refund.applyproxy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.web.refund.applyproxy |

**CID（Ocean配置）**：
- c_meishi_w7mz4j1f

---

## 物流详情B端

| 属性 | 值 |
|------|-----|
| **关键词** | 物流详情B端、开店宝物流详情 |
| **技术栈** | DUO |
| **覆盖端** | 开店宝 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_meishi_logistic-detail-tob |
| **DUO页面ID** | DUO-12454 |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/meis/food-duo/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_meishi_logistic-detail-tob/versions |
| **projectId** | 37268 |
| **raptor 异常** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=37268 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.booking |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.foodtrade.groupbuy.booking |

---
