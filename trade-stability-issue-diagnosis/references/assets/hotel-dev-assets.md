# 酒店交易前端研发资产映射表

数据来源：https://km.sankuai.com/collabpage/2750901165

---

## 页面索引

| 页面 | 技术栈 | projectId |
|------|--------|-----------|
| [主链路提单页（新）](#主链路提单页新) | DUO | 37345 |
| [主链路单详页](#主链路单详页) | MRN | 5273 |
| [子订单页](#子订单页) | MRN | 5157 |
| [抵用券列表页](#抵用券列表页) | MRN | 3468 |
| [国内住宿偏好](#国内住宿偏好) | MRN | 3466 |
| [自助改签页面（大改签）](#自助改签页面大改签) | MRN | 3504 |
| [修改订单（小改签）](#修改订单小改签) | MAX | 29269 |
| [常旅客修改页](#常旅客修改页) | MAX | 26712 |
| [取消订单页面](#取消订单页面) | MAX | 27600 |
| [入住凭证页](#入住凭证页) | MAX | 27025 |
| [发确认信息页](#发确认信息页) | MAX | 27025 |
| [已入住部分间夜退](#已入住部分间夜退) | MAX | 18879 |
| [发票填写页面](#发票填写页面) | MRN | 3312 |
| [发票详情页面](#发票详情页面) | MRN | 3503 |
| [修改发票](#修改发票) | H5(Vue) | - |
| [退款状态（结果）页](#退款状态结果页) | H5(Vue) | - |
| [极速退填写页](#极速退填写页) | H5(Vue) | - |
| [极速退结果页](#极速退结果页) | H5(Vue) | - |
| [境内直连儿童选择页](#境内直连儿童选择页) | MRN | 3441 |
| [超团提单页](#超团提单页) | MRN | 9456 |
| [活包购物车提单页](#活包购物车提单页) | MRN | 11984 |
| [活包购物车-促销活动列表](#活包购物车-促销活动列表) | MRN | 3469 |
| [境外订单详情页](#境外订单详情页) | MRN | 5327 |
| [境外直连儿童选择页](#境外直连儿童选择页) | MRN | 5263 |
| [境外取消订单](#境外取消订单) | MRN | 5327 |
| [境外重发确认邮件](#境外重发确认邮件) | MRN | 5327 |
| [境外住宿偏好页](#境外住宿偏好页) | MRN | 6541 |
| [境外改签](#境外改签) | MAX | 19344 |
| [境外组合预定提单页](#境外组合预定提单页) | DUO | 39698 |

---

## 主链路提单页（新）

| 属性 | 值 |
|------|-----|
| **关键词** | 酒店提单、酒店下单、填写订单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-orderfill-duo |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/duo-hotel-order-submit.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/duo-hotel-order-submit/file/list |
| **物料仓库** | https://dev.sankuai.com/code/repo-detail/hfe/hotel-material/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-orderfill-duo/versions?env=prod |
| **projectId** | 37345 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=37345 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 百万级（新老合并cid） |
| **CID（Ocean配置）** | [c_hotel_createorder_unified](https://ocean.sankuai.com/config/#/page/detail?id=41858441&channelId=18) |
| **CIA** | 待完善 |

---

## 主链路单详页

| 属性 | 值 |
|------|-----|
| **关键词** | 酒店订单详情、酒店订单 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-order-detail |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_inland/file/list?path=hotelchannel-order-detail |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-order-detail/versions?env=prod |
| **projectId** | 5273 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=5273 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 千万级 |
| **CID（Ocean配置）** | [hotel_orderdetail](https://ocean.sankuai.com/config/#/page/detail?id=40166082&channelId=18) |
| **CIA** | 待完善 |

---

## 子订单页

| 属性 | 值 |
|------|-----|
| **关键词** | 子订单、酒店子订单 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-order-suborderlist |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_inland/file/list?path=hotelchannel-order-suborderlist |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-order-suborderlist/versions?env=prod |
| **projectId** | 5157 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=5157 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **备注** | 数据从单详页通过跳链传过来 |

---

## 抵用券列表页

| 属性 | 值 |
|------|-----|
| **关键词** | 抵用券、酒店抵用券 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-order-voucherlist |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_inland/file/list?path=hotelchannel-order-voucherlist |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-order-voucherlist/versions?env=prod |
| **projectId** | 3468 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=3468 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 万-十万级 |
| **CID（Ocean配置）** | [c_hotel_couponlist](https://ocean.sankuai.com/config/#/page/detail?id=41899734&channelId=18) |

---

## 国内住宿偏好

| 属性 | 值 |
|------|-----|
| **关键词** | 住宿偏好、入住偏好 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-fill-order-special-hobbies |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_inland/file/list?path=hotelchannel-fill-order-special-hobbies |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-fill-order-special-hobbies/versions?env=prod |
| **projectId** | 3466 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=3466 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **备注** | 仍有少量场景使用 |

---

## 自助改签页面（大改签）

| 属性 | 值 |
|------|-----|
| **关键词** | 改签、自助改签、大改签 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-order-reschedule |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_inland/file/list?path=hotelchannel-order-reschedule |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-order-reschedule/versions?env=prod |
| **projectId** | 3504 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=3504 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 万级 |
| **CID（Ocean配置）** | [hotel_modifygoods](https://ocean.sankuai.com/config/#/page/detail?id=40562588&channelId=18) |

---

## 修改订单（小改签）

| 属性 | 值 |
|------|-----|
| **关键词** | 小改签、修改订单 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_max-order-guest-modify |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/max-hotel-fe-deal.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/max-hotel-fe-deal/file/list?path=hotelchannel-order-guest-modify |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_max-order-guest-modify/versions?env=prod |
| **projectId** | 29269 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=29269 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 十万级 |
| **CID（Ocean配置）** | [c_hotel_ixncx1gn](https://ocean.sankuai.com/config/#/page/detail?id=43113947&channelId=18) |

---

## 常旅客修改页

| 属性 | 值 |
|------|-----|
| **关键词** | 常旅客修改、入住人修改 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_max-guest-modify |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/max-hotel-fe-deal.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/max-hotel-fe-deal/file/list?path=hotelchannel-guest-modify |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_max-guest-modify/versions?env=prod |
| **projectId** | 26712 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=26712 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |

---

## 取消订单页面

| 属性 | 值 |
|------|-----|
| **关键词** | 取消订单、酒店退款 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_max-order-cancel |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/max-hotel-fe-deal.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/max-hotel-fe-deal/file/list?path=hotelchannel-order-cancel |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_max-order-cancel/versions?env=prod |
| **projectId** | 27600 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=27600 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 十万级（盲盒取消复用cid） |
| **CID（Ocean配置）** | [c_5olfzqm](https://ocean.sankuai.com/config/#/page/detail?id=40011075&channelId=18) |

---

## 入住凭证页

| 属性 | 值 |
|------|-----|
| **关键词** | 入住凭证、入住码 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_max-checkin-certificate |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/max-hotel-fe-deal.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/max-hotel-fe-deal/file/list?path=hotelchannel-certificate |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_max-checkin-certificate/versions?env=prod |
| **projectId** | 27025 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=27025 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 万级 |
| **CID（Ocean配置）** | 入住凭证tab：[c_hotel_x0ypbh4h](https://ocean.sankuai.com/config/#/page/detail?id=42073809&channelId=18)<br>权益凭证tab：[c_hotel_n8j3lltm](https://ocean.sankuai.com/config/#/page/detail?id=42333158&channelId=18) |

---

## 发确认信息页

| 属性 | 值 |
|------|-----|
| **关键词** | 发确认信息、确认邮件 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_max-checkin-certificate（同入住凭证） |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/max-hotel-fe-deal.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/max-hotel-fe-deal/file/list?path=hotelchannel-certificate |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_max-checkin-certificate/versions?env=prod |
| **projectId** | 27025 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=27025 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [c_hotel_9vl8xl36](https://ocean.sankuai.com/config/#/page/detail?id=42073810&channelId=18) |

---

## 已入住部分间夜退

| 属性 | 值 |
|------|-----|
| **关键词** | 部分间夜退、间夜退款 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_max-reschedule-refund |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/hotel-fe-max.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/hotel-fe-max/file/list?path=hotelchannel-order-reschedule-refund |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_max-reschedule-refund/versions?env=prod |
| **projectId** | 18879 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=18879 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |

---

## 发票填写页面

| 属性 | 值 |
|------|-----|
| **关键词** | 发票填写、开发票 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-invoice-fill |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_inland/file/list?path=hotelchannel-invoice-fill |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-invoice-fill/versions?env=prod |
| **projectId** | 3312 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=3312 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [hotel_invoice_info](https://ocean.sankuai.com/config/#/page/detail?id=40012106&channelId=18) |

---

## 发票详情页面

| 属性 | 值 |
|------|-----|
| **关键词** | 发票详情、查看发票 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-invoice-detail |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_inland/file/list?path=hotelchannel-invoice-detail |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-invoice-detail/versions?env=prod |
| **projectId** | 3503 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=3503 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 万级 |
| **CID（Ocean配置）** | [c_hotel_ugfiw8v4](https://ocean.sankuai.com/config/#/page/detail?id=42025087&channelId=18) |

---

## 修改发票

| 属性 | 值 |
|------|-----|
| **关键词** | 修改发票 |
| **技术栈** | H5(Vue) |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | hotel-v2/src/pages/invoiceUpdate |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/hotel-v2/file/list |
| **projectId** | - |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |

---

## 退款状态（结果）页

| 属性 | 值 |
|------|-----|
| **关键词** | 退款状态、退款结果 |
| **技术栈** | H5(Vue) |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | hotel-v2/src/pages/refundingView |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/hotel-v2/file/list |
| **projectId** | - |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 万级 |
| **CID（Ocean配置）** | [c_hotel_mytchz3w](https://ocean.sankuai.com/config/#/page/detail?id=43190803&channelId=18) |

---

## 极速退填写页

| 属性 | 值 |
|------|-----|
| **关键词** | 极速退、极速退款 |
| **技术栈** | H5(Vue) |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | hotel-v2/src/pages/fastRefund |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/hotel-v2/file/list |
| **projectId** | - |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [hotel_rapidrefund](https://ocean.sankuai.com/config/#/page/detail?id=40678424&channelId=18) |

---

## 极速退结果页

| 属性 | 值 |
|------|-----|
| **关键词** | 极速退结果 |
| **技术栈** | H5(Vue) |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | hotel-v2/src/pages/fastRefund（同极速退填写） |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/h5/hotel-v2/file/list |
| **projectId** | - |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [hotel_rapidrefundresult](https://ocean.sankuai.com/config/#/page/detail?id=40678434&channelId=18) |

---

## 境内直连儿童选择页

| 属性 | 值 |
|------|-----|
| **关键词** | 儿童选择、入住人数选择 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-order-room-user-num-select |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_inland/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-order-room-user-num-select/versions?env=prod |
| **projectId** | 3441 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=3441 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | - |

---

## 超团提单页

| 属性 | 值 |
|------|-----|
| **关键词** | 超团提单、超级团购 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_superdeal |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_superdeal.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_superdeal/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_superdeal/versions?env=prod |
| **projectId** | 9456 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=9456 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 十万级（小程序复用cid） |
| **CID（Ocean配置）** | [c_hotel_67ewa5bk](https://ocean.sankuai.com/config/#/page/detail?id=42026921&channelId=18) |

---

## 活包购物车提单页

| 属性 | 值 |
|------|-----|
| **关键词** | 活包购物车、套餐提单 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_cart-orderfill |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_shoppingcart-orderfill.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_shoppingcart-orderfill/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_cart-orderfill/versions?env=prod |
| **projectId** | 11984 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=11984 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **CID（Ocean配置）** | 酒店：[c_hotel_y06bl2hl](https://ocean.sankuai.com/config/#/page/detail?id=42118581&channelId=18)<br>门票：[c_hotel_bltrnvv5](https://ocean.sankuai.com/config/#/page/detail?id=42118580&channelId=18) |

---

## 活包购物车-促销活动列表

| 属性 | 值 |
|------|-----|
| **关键词** | 促销活动列表、活包促销 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_hotelchannel-order-discount-list |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_hotel_inland/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-order-discount-list/versions?env=prod |
| **projectId** | 3469 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=3469 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |

---

## 境外订单详情页

| 属性 | 值 |
|------|-----|
| **关键词** | 境外酒店订单详情、境外订单 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_overseahotel_overseahotel-order-detail |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_overseahotel_main.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_overseahotel_main/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_overseahotel_overseahotel-order-detail/versions?env=prod |
| **projectId** | 5327 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=5327 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 万-十万级 |
| **CID（Ocean配置）** | [hotel_orderdetail_oversea](https://ocean.sankuai.com/config/#/page/detail?id=40152348&channelId=18) |

---

## 境外直连儿童选择页

| 属性 | 值 |
|------|-----|
| **关键词** | 境外儿童选择 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_overseahotel_overseahotel-usernumber-select |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_overseahotel_main.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_overseahotel_main/file/list |
| **projectId** | 5263 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=5263 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |

---

## 境外取消订单

| 属性 | 值 |
|------|-----|
| **关键词** | 境外取消、境外退款 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_overseahotel_overseahotel-order-detail（同境外订单详情） |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_overseahotel_main.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_overseahotel_main/file/list |
| **projectId** | 5327 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=5327 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [c_hotel_8uyv1cx8](https://ocean.sankuai.com/config/#/page/detail?id=42174544&channelId=18) |

---

## 境外重发确认邮件

| 属性 | 值 |
|------|-----|
| **关键词** | 境外确认邮件、重发邮件 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_overseahotel_overseahotel-order-detail（同境外订单详情） |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_overseahotel_main.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_overseahotel_main/file/list |
| **projectId** | 5327 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=5327 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |
| **PV量级** | 百级 |
| **CID（Ocean配置）** | [hotel_resendmail_oversea](https://ocean.sankuai.com/config/#/page/detail?id=40771568&channelId=18) |

---

## 境外住宿偏好页

| 属性 | 值 |
|------|-----|
| **关键词** | 境外住宿偏好 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_overseahotel_overseahotel-submit-order |
| **仓库SSH** | ssh://git@git.sankuai.com/htmrn/rn_overseahotel_main.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/htmrn/rn_overseahotel_main/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_overseahotel_overseahotel-submit-order/versions?env=prod |
| **projectId** | 6541 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=6541 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |

---

## 境外改签

| 属性 | 值 |
|------|-----|
| **关键词** | 境外改签、境外修改订单 |
| **技术栈** | MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_order-modify |
| **仓库SSH** | ssh://git@git.sankuai.com/hfe/max-hotel-order-modify.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/hfe/max-hotel-order-modify/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_order-modify/versions?env=prod |
| **projectId** | 19344 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=19344 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |

---

## 境外组合预定提单页

| 属性 | 值 |
|------|-----|
| **关键词** | 境外组合预定、境外combo提单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_hotel_combine-order-submit |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/duo-hotel-combine-order-submit.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/duo-hotel-combine-order-submit/file/list |
| **diva链接** | https://diva.sankuai.com/bundle/rn_hotel_combine-order-submit/versions?env=prod |
| **projectId** | 39698 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=39698 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.hotel.apic |

---

## 仓库速查

| 业务 | 仓库 | 技术栈 | gitSSH |
|------|------|--------|--------|
| 国内酒店主链路提单（新） | nibfe/duo-hotel-order-submit | DUO | ssh://git@git.sankuai.com/nibfe/duo-hotel-order-submit.git |
| 国内酒店物料 | hfe/hotel-material | DUO | ssh://git@git.sankuai.com/hfe/hotel-material.git |
| 国内酒店主链路（MRN） | htmrn/rn_hotel_inland | MRN | ssh://git@git.sankuai.com/htmrn/rn_hotel_inland.git |
| 国内酒店MAX页面 | nibfe/max-hotel-fe-deal | MAX | ssh://git@git.sankuai.com/nibfe/max-hotel-fe-deal.git |
| 国内酒店MAX退款 | nibfe/hotel-fe-max | MAX | ssh://git@git.sankuai.com/nibfe/hotel-fe-max.git |
| 国内酒店H5 | h5/hotel-v2 | H5(Vue) | 待完善 |
| 境外酒店主链路 | htmrn/rn_overseahotel_main | MRN | ssh://git@git.sankuai.com/htmrn/rn_overseahotel_main.git |
| 境外酒店改签 | hfe/max-hotel-order-modify | MAX | ssh://git@git.sankuai.com/hfe/max-hotel-order-modify.git |
| 境外组合预定 | nibfe/duo-hotel-combine-order-submit | DUO | ssh://git@git.sankuai.com/nibfe/duo-hotel-combine-order-submit.git |
| 超团 | htmrn/rn_hotel_superdeal | MRN | ssh://git@git.sankuai.com/htmrn/rn_hotel_superdeal.git |
| 活包购物车 | htmrn/rn_hotel_shoppingcart-orderfill | MRN | ssh://git@git.sankuai.com/htmrn/rn_hotel_shoppingcart-orderfill.git |

---

> 完整资产数据请查阅：https://km.sankuai.com/collabpage/2750901165
