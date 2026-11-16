# 门票&度假交易前端研发资产映射表

数据来源：https://km.sankuai.com/collabpage/2753660657
特殊说明
1、DUO页面特有DUO页面ID、DUO页面链接
2、H5/Vue技术栈特有页面路径，无Bundle信息和diva地址
3、Tex技术栈（度假-团购）共用同一个bundle和projectId

---

## 页面索引

| 页面 | 技术栈 |
|------|--------|
| [普通门票 - 门票提单](#普通门票---门票提单) | DUO |
| [普通门票 - 单详页](#普通门票---单详页) | MAX |
| [普通门票 - 支付结果页](#普通门票---支付结果页) | MRN |
| [普通门票 - 退款页](#普通门票---退款页) | DUO |
| [普通门票 - 入园凭证页](#普通门票---入园凭证页) | H5 |
| [普通门票 - 学生认证页](#普通门票---学生认证页) | MRN |
| [普通门票 - 邀请好友填写页面](#普通门票---邀请好友填写页面) | MAX |
| [景x - 填单页](#景x---填单页) | MAX |
| [景x - 单详页](#景x---单详页) | H5 |
| [景x - 退款申请页](#景x---退款申请页) | H5 |
| [景x - 退款详情页](#景x---退款详情页) | H5 |
| [度假-团购 - 提单页](#度假-团购---提单页) | Tex |
| [度假-团购 - 订详页](#度假-团购---订详页) | Tex |
| [度假-团购 - 申请退款页](#度假-团购---申请退款页) | Tex |
| [度假-团购 - 退款详情页](#度假-团购---退款详情页) | Tex |
| [度假-跟团 - 新填单页](#度假-跟团---新填单页) | DUO |
| [度假-跟团 - 老订单详情页](#度假-跟团---老订单详情页) | Vue |
| [度假-跟团 - 新订详页](#度假-跟团---新订详页) | DUO |
| [度假-跟团 - 支付结果页](#度假-跟团---支付结果页) | Vue |
| [度假-跟团 - 退款申请页](#度假-跟团---退款申请页) | Vue |
| [度假-组品 - 填单页](#度假-组品---填单页) | DUO |
| [度假-组品 - 订详页](#度假-组品---订详页) | DUO |
| [度假-组品 - 退款申请页](#度假-组品---退款申请页) | DUO |
| [度假-组品 - 退款详情页](#度假-组品---退款详情页) | DUO |

---

## 普通门票 - 门票提单

| 属性 | 值 |
|------|-----|
| **关键词** | 门票提单、提单页、下单页、确认订单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小/门小/银行 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_travelcore-duo |
| **DUO页面ID** | 待补充 |
| **DUO页面链接** | 待补充 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/travel-transaction-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/travel-transaction-duo/file/list?path=ticket-submit-order |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_travelcore-duo/versions |
| **projectId** | 31960 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=31960 |
| **后端日志Appkey** | com.sankuai.triptrade.buy |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.triptrade.buy |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 普通门票 - 单详页

| 属性 | 值 |
|------|-----|
| **关键词** | 订单详情、单详页 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评/美小/点小/门小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_order-detail |
| **仓库SSH** | ssh://git@git.sankuai.com/hfe/travel-ticket-max.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/hfe/travel-ticket-max/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_order-detail/versions |
| **projectId** | 12255 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=12255 |
| **后端日志Appkey** | com.sankuai.triptrade.order.manager |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.triptrade.order.manager |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 普通门票 - 支付结果页

| 属性 | 值 |
|------|-----|
| **关键词** | 支付结果、支付成功、支付结果页 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_travelticket |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_travel_ticket.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_travel_ticket/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_travelticket/versions |
| **projectId** | 8445 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=8445&pageId=1800456 |
| **后端日志（trade.order）Appkey** | com.sankuai.trip.trade.order |
| **后端日志（trade.order）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.trip.trade.order |
| **后端日志（order.manager）Appkey** | com.sankuai.triptrade.order.manager |
| **后端日志（order.manager）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.triptrade.order.manager |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 普通门票 - 退款页

| 属性 | 值 |
|------|-----|
| **关键词** | 退款、申请退款、退款页 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/门小/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_ticket-request-refund |
| **DUO页面ID** | 待补充 |
| **DUO页面链接** | 待补充 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/travel-transaction-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/travel-transaction-duo/file/list?path=ticket-request-refund |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_ticket-request-refund/versions |
| **projectId** | 37761 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=37761 |
| **后端日志Appkey** | com.sankuai.mptrade.api |
| **后端日志** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 普通门票 - 入园凭证页

| 属性 | 值 |
|------|-----|
| **关键词** | 入园凭证、二维码、凭证页 |
| **技术栈** | H5 |
| **覆盖端** | 美团/点评/门小 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | src/apps/qrcode-list |
| **仓库SSH** | ssh://git@git.sankuai.com/h5/lvyou.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/lvyou/file/list?path=src%2Fapps%2Fqrcode-list |
| **projectId** | 2224 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=2224&pageId=2066257 |
| **后端日志（order.manager）Appkey** | com.sankuai.triptrade.order.manager |
| **后端日志（order.manager）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.triptrade.order.manager |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 普通门票 - 学生认证页

| 属性 | 值 |
|------|-----|
| **关键词** | 学生认证、学生验证 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_travelticket |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_travel_ticket.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_travel_ticket/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_travelticket/versions |
| **projectId** | 8445 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=8445&pageId=7346421 |
| **后端日志（trade.order）Appkey** | com.sankuai.trip.trade.order |
| **后端日志（trade.order）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.trip.trade.order |
| **后端日志（meilv.rhone）Appkey** | com.sankuai.meilv.rhone |
| **后端日志（meilv.rhone）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.meilv.rhone |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 普通门票 - 邀请好友填写页面

| 属性 | 值 |
|------|-----|
| **关键词** | 邀请好友、好友填写 |
| **技术栈** | MAX |
| **覆盖端** | 门小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | 待补充 |
| **仓库SSH** | ssh://git@git.sankuai.com/hfe/share-travel-max.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/hfe/share-travel-max/file/list |
| **diva链接** | 待补充 |
| **projectId** | 待补充 |
| **raptor 异常链接** | 待补充 |
| **后端日志（precreate）Appkey** | 待补充 |
| **后端日志（precreate）** | 待补充 |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 景x - 填单页

| 属性 | 值 |
|------|-----|
| **关键词** | 景x填单、景加X提单、mpplussubmitorder |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评/美小/点小/门小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_travelmpplus |
| **仓库SSH** | ssh://git@git.sankuai.com/hfe/max-travel-ticket-submitorder.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/hfe/max-travel-ticket-submitorder/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_travelmpplus/versions |
| **projectId** | 8602 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=8602&pageId=1866685 |
| **后端日志（tp.dpack.api）Appkey** | com.sankuai.tp.dpack.api |
| **后端日志（tp.dpack.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.tp.dpack.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 景x - 单详页

| 属性 | 值 |
|------|-----|
| **关键词** | 景x订单详情、景加X单详页 |
| **技术栈** | H5 |
| **覆盖端** | 美团/点评/美小/点小/门小 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | src/pages/order/package |
| **仓库SSH** | ssh://git@git.sankuai.com/h5/lvyou.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/lvyou/file/list?path=src%2Fpages%2Forder%2Fpackage |
| **projectId** | 2224 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=2224&pageId=25794 |
| **后端日志（tp.dpack.api）Appkey** | com.sankuai.tp.dpack.api |
| **后端日志（tp.dpack.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.tp.dpack.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 景x - 退款申请页

| 属性 | 值 |
|------|-----|
| **关键词** | 景x退款申请、景加X退款 |
| **技术栈** | H5 |
| **覆盖端** | 美团/点评/美小/点小/门小 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | src/pages/refund/apply/package |
| **仓库SSH** | ssh://git@git.sankuai.com/h5/lvyou.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/lvyou/file/list?path=src%2Fpages%2Frefund%2Fapply%2Fpackage |
| **projectId** | 2224 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=2224&pageId=25796 |
| **后端日志（tp.dpack.api）Appkey** | com.sankuai.tp.dpack.api |
| **后端日志（tp.dpack.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.tp.dpack.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 景x - 退款详情页

| 属性 | 值 |
|------|-----|
| **关键词** | 景x退款详情、景加X退款详情 |
| **技术栈** | H5 |
| **覆盖端** | 美团/点评/美小/点小/门小 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | src/pages/refund/detail/package |
| **仓库SSH** | ssh://git@git.sankuai.com/h5/lvyou.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/lvyou/file/list?path=src%2Fpages%2Frefund%2Fdetail |
| **projectId** | 2224 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=2224&pageId=25773 |
| **后端日志（precreate）Appkey** | 待补充 |
| **后端日志（precreate）** | 待补充 |
| **后端日志（tp.dpack.api）Appkey** | com.sankuai.tp.dpack.api |
| **后端日志（tp.dpack.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.tp.dpack.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-团购 - 提单页

| 属性 | 值 |
|------|-----|
| **关键词** | 旅行社提单、团购填单、order-preview |
| **技术栈** | Tex |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP/美团微信小程序/小红书小程序 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_travel-agency-container |
| **仓库SSH** | 待补充 |
| **仓库https链接** | 待补充 |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_travel-agency-container/versions |
| **projectId** | 6108 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/brief?projectId=6108 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-团购 - 订详页

| 属性 | 值 |
|------|-----|
| **关键词** | 旅行社订单详情、团购订详页、order-detail |
| **技术栈** | Tex |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP/美团微信小程序 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_travel-agency-container |
| **仓库SSH** | 待补充 |
| **仓库https链接** | 待补充 |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_travel-agency-container/versions |
| **projectId** | 6108 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/brief?projectId=6108 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-团购 - 申请退款页

| 属性 | 值 |
|------|-----|
| **关键词** | 旅行社退款申请、团购退款、refund-preview |
| **技术栈** | Tex |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP/美团微信小程序 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_travel-agency-container |
| **仓库SSH** | 待补充 |
| **仓库https链接** | 待补充 |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_travel-agency-container/versions |
| **projectId** | 6108 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/brief?projectId=6108 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-团购 - 退款详情页

| 属性 | 值 |
|------|-----|
| **关键词** | 旅行社退款详情、团购退款详情、refund-detail |
| **技术栈** | Tex |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP/美团微信小程序 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_travel-agency-container |
| **仓库SSH** | 待补充 |
| **仓库https链接** | 待补充 |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_travel-agency-container/versions |
| **projectId** | 6108 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/brief?projectId=6108 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-跟团 - 新填单页

| 属性 | 值 |
|------|-----|
| **关键词** | 跟团游填单、跟团提单、group-tour-submit-order-base |
| **技术栈** | DUO |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP/美团小程序/点评小程序/门票小程序 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_group-tour-submit-order-base |
| **DUO页面ID** | 待补充 |
| **DUO页面链接** | 待补充 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/travel-transaction-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/travel-transaction-duo/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_group-tour-submit-order-base/versions |
| **projectId** | 36431 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=36431 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-跟团 - 老订单详情页

| 属性 | 值 |
|------|-----|
| **关键词** | 跟团游订单详情、老订详页、gty订单 |
| **技术栈** | Vue |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP/美团小程序/点评小程序/门票小程序 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | trip/src/apps/order/gty |
| **仓库SSH** | ssh://git@git.sankuai.com/h5/trip.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/trip/file/list?path=src%2Fapps%2Forder%2Fgty |
| **projectId** | 2224 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/request/trend?projectId=2224&pageId=25808 |
| **后端日志（precreate）Appkey** | 待补充 |
| **后端日志（precreate）** | 待补充 |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-跟团 - 新订详页

| 属性 | 值 |
|------|-----|
| **关键词** | 跟团游新订单详情、gty-order-detail |
| **技术栈** | DUO |
| **覆盖端** | 美团APP |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_gty-order-detail |
| **DUO页面ID** | 待补充 |
| **DUO页面链接** | 待补充 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/travel-transaction-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/travel-transaction-duo/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_gty-order-detail/versions |
| **projectId** | 41398 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/custom_key/?projectId=41398 |
| **后端日志（grouptour.api）Appkey** | com.sankuai.triptrade.grouptour.api |
| **后端日志（grouptour.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.triptrade.grouptour.api_all |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-跟团 - 支付结果页

| 属性 | 值 |
|------|-----|
| **关键词** | 跟团游支付结果、gty支付成功 |
| **技术栈** | Vue |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP/美团小程序/点评小程序/门票小程序 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | src/apps/result/group |
| **仓库SSH** | ssh://git@git.sankuai.com/h5/lvyou.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/lvyou/file/list |
| **projectId** | 2224 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/request/trend?projectId=2224&pageId=25828 |
| **后端日志（precreate）Appkey** | 待补充 |
| **后端日志（precreate）** | 待补充 |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-跟团 - 退款申请页

| 属性 | 值 |
|------|-----|
| **关键词** | 跟团游退款申请、gty退款 |
| **技术栈** | Vue |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP/美团小程序/点评小程序/门票小程序 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | src/apps/refund/gty |
| **仓库SSH** | ssh://git@git.sankuai.com/h5/trip.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/trip/file/list?path=src%2Fapps%2Frefund%2Fgty |
| **projectId** | 2224 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/request/trend?projectId=2224&pageId=25809 |
| **后端日志（precreate）Appkey** | 待补充 |
| **后端日志（precreate）** | 待补充 |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-组品 - 填单页

| 属性 | 值 |
|------|-----|
| **关键词** | 组品填单、组品提单、group-tour-submit-order |
| **技术栈** | DUO |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_group-tour-submit-order |
| **DUO页面ID** | 待补充 |
| **DUO页面链接** | 待补充 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/travel-transaction-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/travel-transaction-duo/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_group-tour-submit-order/versions |
| **projectId** | 35047 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=35047 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-组品 - 订详页

| 属性 | 值 |
|------|-----|
| **关键词** | 组品订单详情、group-tour-order-detail |
| **技术栈** | DUO |
| **覆盖端** | 美团APP |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_group-tour-order-detail |
| **DUO页面ID** | 待补充 |
| **DUO页面链接** | 待补充 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/travel-transaction-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/travel-transaction-duo/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_group-tour-order-detail/versions |
| **projectId** | 35062 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=35062 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-组品 - 退款申请页

| 属性 | 值 |
|------|-----|
| **关键词** | 组品退款申请、group-tour-refund |
| **技术栈** | DUO |
| **覆盖端** | 美团APP |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_group-tour-refund |
| **DUO页面ID** | 待补充 |
| **DUO页面链接** | 待补充 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/travel-transaction-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/travel-transaction-duo/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_group-tour-refund/versions |
| **projectId** | 35066 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=35066 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充

---

## 度假-组品 - 退款详情页

| 属性 | 值 |
|------|-----|
| **关键词** | 组品退款详情、退款详情页 |
| **技术栈** | DUO |
| **覆盖端** | 美团APP/点评APP/鸿蒙APP |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_travel_group-tour-refund-detail |
| **DUO页面ID** | 待补充 |
| **DUO页面链接** | 待补充 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/travel-transaction-duo.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/travel-transaction-duo/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_travel_group-tour-refund-detail/versions |
| **projectId** | 35069 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=35069 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充
