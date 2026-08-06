# 酒店交易前端研发资产映射表

数据来源：aHR0cHM6Ly9rbS5zYW5rdWFpLmNvbS9jb2xsYWJwYWdlLzI3NTA5MDExNjU=

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9kdW8taG90ZWwtb3JkZXItc3VibWl0L2ZpbGUvbGlzdA== |
| **物料仓库** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oZmUvaG90ZWwtbWF0ZXJpYWwvZmlsZS9saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtb3JkZXJmaWxsLWR1by92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 37345 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM3MzQ1 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 百万级（新老合并cid） |
| **CID（Ocean配置）** | [c_hotel_createorder_unified](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MTg1ODQ0MSZjaGFubmVsSWQ9MTg=) |
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9pbmxhbmQvZmlsZS9saXN0P3BhdGg9aG90ZWxjaGFubmVsLW9yZGVyLWRldGFpbA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtb3JkZXItZGV0YWlsL3ZlcnNpb25zP2Vudj1wcm9k |
| **projectId** | 5273 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTUyNzM= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 千万级 |
| **CID（Ocean配置）** | [hotel_orderdetail](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDE2NjA4MiZjaGFubmVsSWQ9MTg=) |
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9pbmxhbmQvZmlsZS9saXN0P3BhdGg9aG90ZWxjaGFubmVsLW9yZGVyLXN1Ym9yZGVybGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtb3JkZXItc3Vib3JkZXJsaXN0L3ZlcnNpb25zP2Vudj1wcm9k |
| **projectId** | 5157 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTUxNTc= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9pbmxhbmQvZmlsZS9saXN0?path=hotelchannel-order-voucherlist |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtb3JkZXItdm91Y2hlcmxpc3QvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 3468 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM0Njg= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 万-十万级 |
| **CID（Ocean配置）** | [c_hotel_couponlist](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MTg5OTczNCZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9pbmxhbmQvZmlsZS9saXN0?path=hotelchannel-fill-order-special-hobbies |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtZmlsbC1vcmRlci1zcGVjaWFsLWhvYmJpZXMvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 3466 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM0NjY= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9pbmxhbmQvZmlsZS9saXN0?path=hotelchannel-order-reschedule |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtb3JkZXItcmVzY2hlZHVsZS92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 3504 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM1MDQ= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 万级 |
| **CID（Ocean配置）** | [hotel_modifygoods](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDU2MjU4OCZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9tYXgtaG90ZWwtZmUtZGVhbC9maWxlL2xpc3Q/cGF0aD1ob3RlbGNoYW5uZWwtb3JkZXItZ3Vlc3QtbW9kaWZ5 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9tYXgtb3JkZXItZ3Vlc3QtbW9kaWZ5L3ZlcnNpb25zP2Vudj1wcm9k |
| **projectId** | 29269 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI5MjY5 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 十万级 |
| **CID（Ocean配置）** | [c_hotel_ixncx1gn](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzExMzk0NyZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9tYXgtaG90ZWwtZmUtZGVhbC9maWxlL2xpc3Q/cGF0aD1ob3RlbGNoYW5uZWwtZ3Vlc3QtbW9kaWZ5 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9tYXgtZ3Vlc3QtbW9kaWZ5L3ZlcnNpb25zP2Vudj1wcm9k |
| **projectId** | 26712 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI2NzEy |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9tYXgtaG90ZWwtZmUtZGVhbC9maWxlL2xpc3Q/cGF0aD1ob3RlbGNoYW5uZWwtb3JkZXItY2FuY2Vs |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9tYXgtb3JkZXItY2FuY2VsL3ZlcnNpb25zP2Vudj1wcm9k |
| **projectId** | 27600 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI3NjAw |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 十万级（盲盒取消复用cid） |
| **CID（Ocean配置）** | [c_5olfzqm](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDAxMTA3NSZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9tYXgtaG90ZWwtZmUtZGVhbC9maWxlL2xpc3Q/cGF0aD1ob3RlbGNoYW5uZWwtY2VydGlmaWNhdGU= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9tYXgtY2hlY2tpbi1jZXJ0aWZpY2F0ZS92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 27025 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI3MDI1 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 万级 |
| **CID（Ocean配置）** | 入住凭证tab：[c_hotel_x0ypbh4h](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjA3MzgwOSZjaGFubmVsSWQ9MTg=)<br>权益凭证tab：[c_hotel_n8j3lltm](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjMzMzE1OCZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9tYXgtaG90ZWwtZmUtZGVhbC9maWxlL2xpc3Q/cGF0aD1ob3RlbGNoYW5uZWwtY2VydGlmaWNhdGU= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9tYXgtY2hlY2tpbi1jZXJ0aWZpY2F0ZS92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 27025 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI3MDI1 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [c_hotel_9vl8xl36](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjA3MzgxMCZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9ob3RlbC1mZS1tYXgvZmlsZS9saXN0P3BhdGg9aG90ZWxjaGFubmVsLW9yZGVyLXJlc2NoZWR1bGUtcmVmdW5k |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9tYXgtcmVzY2hlZHVsZS1yZWZ1bmQvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 18879 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE4ODc5 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9pbmxhbmQvZmlsZS9saXN0?path=hotelchannel-invoice-fill |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtaW52b2ljZS1maWxsL3ZlcnNpb25zP2Vudj1wcm9k |
| **projectId** | 3312 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTMzMTI= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [hotel_invoice_info](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDAxMjEwNiZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9pbmxhbmQvZmlsZS9saXN0?path=hotelchannel-invoice-detail |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtaW52b2ljZS1kZXRhaWwvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 3503 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM1MDM= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 万级 |
| **CID（Ocean配置）** | [c_hotel_ugfiw8v4](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjAyNTA4NyZjaGFubmVsSWQ9MTg=) |

---

## 修改发票

| 属性 | 值 |
|------|-----|
| **关键词** | 修改发票 |
| **技术栈** | H5(Vue) |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | hotel-v2/src/pages/invoiceUpdate |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS9ob3RlbC12Mi9maWxlL2xpc3Q= |
| **projectId** | - |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |

---

## 退款状态（结果）页

| 属性 | 值 |
|------|-----|
| **关键词** | 退款状态、退款结果 |
| **技术栈** | H5(Vue) |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | hotel-v2/src/pages/refundingView |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS9ob3RlbC12Mi9maWxlL2xpc3Q= |
| **projectId** | - |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 万级 |
| **CID（Ocean配置）** | [c_hotel_mytchz3w](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzE5MDgwMyZjaGFubmVsSWQ9MTg=) |

---

## 极速退填写页

| 属性 | 值 |
|------|-----|
| **关键词** | 极速退、极速退款 |
| **技术栈** | H5(Vue) |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | hotel-v2/src/pages/fastRefund |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS9ob3RlbC12Mi9maWxlL2xpc3Q= |
| **projectId** | - |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [hotel_rapidrefund](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDY3ODQyNCZjaGFubmVsSWQ9MTg=) |

---

## 极速退结果页

| 属性 | 值 |
|------|-----|
| **关键词** | 极速退结果 |
| **技术栈** | H5(Vue) |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **页面路径** | hotel-v2/src/pages/fastRefund（同极速退填写） |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS9ob3RlbC12Mi9maWxlL2xpc3Q= |
| **projectId** | - |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [hotel_rapidrefundresult](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDY3ODQzNCZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9pbmxhbmQvZmlsZS9saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtb3JkZXItcm9vbS11c2VyLW51bS1zZWxlY3QvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 3441 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM0NDE= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9zdXBlcmRlYWwvZmlsZS9saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9zdXBlcmRlYWwvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 9456 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTk0NTY= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 十万级（小程序复用cid） |
| **CID（Ocean配置）** | [c_hotel_67ewa5bk](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjAyNjkyMSZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9zaG9wcGluZ2NhcnQtb3JkZXJmaWxsL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9jYXJ0LW9yZGVyZmlsbC92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 11984 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTExOTg0 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **CID（Ocean配置）** | 酒店：[c_hotel_y06bl2hl](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjExODU4MSZjaGFubmVsSWQ9MTg=)<br>门票：[c_hotel_bltrnvv5](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjExODU4MCZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9ob3RlbF9pbmxhbmQvZmlsZS9saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9ob3RlbGNoYW5uZWwtb3JkZXItZGlzY291bnQtbGlzdC92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 3469 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM0Njk= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9vdmVyc2VhaG90ZWxfbWFpbi9maWxlL2xpc3Q= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9vdmVyc2VhaG90ZWxfb3ZlcnNlYWhvdGVsLW9yZGVyLWRldGFpbC92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 5327 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTUzMjc= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 万-十万级 |
| **CID（Ocean配置）** | [hotel_orderdetail_oversea](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDE1MjM0OCZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9vdmVyc2VhaG90ZWxfbWFpbi9maWxlL2xpc3Q= |
| **projectId** | 5263 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTUyNjM= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9vdmVyc2VhaG90ZWxfbWFpbi9maWxlL2xpc3Q= |
| **projectId** | 5327 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTUzMjc= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 千级 |
| **CID（Ocean配置）** | [c_hotel_8uyv1cx8](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjE3NDU0NCZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9vdmVyc2VhaG90ZWxfbWFpbi9maWxlL2xpc3Q= |
| **projectId** | 5327 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTUzMjc= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |
| **PV量级** | 百级 |
| **CID（Ocean配置）** | [hotel_resendmail_oversea](aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDc3MTU2OCZjaGFubmVsSWQ9MTg=) |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl9vdmVyc2VhaG90ZWxfbWFpbi9maWxlL2xpc3Q= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9vdmVyc2VhaG90ZWxfb3ZlcnNlYWhvdGVsLXN1Ym1pdC1vcmRlci92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 6541 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTY1NDE= |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oZmUvbWF4LWhvdGVsLW9yZGVyLW1vZGlmeS9maWxlL2xpc3Q= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9vcmRlci1tb2RpZnkvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 19344 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE5MzQ0 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9kdW8taG90ZWwtY29tYmluZS1vcmRlci1zdWJtaXQvZmlsZS9saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9ob3RlbF9jb21iaW5lLW9yZGVyLXN1Ym1pdC92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 39698 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM5Njk4 |
| **后端日志 Appkey** | com.sankuai.mptrade.hotel.apic |
| **后端日志链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuaG90ZWwuYXBpYw== |

---

## 通兑提单页（新）

| 属性 | 值 |
|------|-----|
| **关键词** | 通兑提单、通兑下单、通兑订单 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_daodianpingtai_ex-coupon-pay |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/trade-ex-coupon.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/trade-ex-coupon/file/list?path=ex-coupon-submit |
| **diva链接** | https://diva.sankuai.com/bundle/rn_daodianpingtai_ex-coupon-pay/versions?env=prod |
| **projectId** | 43755 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=43755 |
| **后端日志 Appkey** | com.sankuai.mptrade.api |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api?searchType=expert&searchGrammar=dsl&timeType=5m~0m&startDate=20260724193201&endDate=20260724193701&iSLimit=100&pageNum=1&pageSize=50 |
| **PV量级** | 十万级（新老合并cid） |
| **CID（Ocean配置）** | [c_tex_page_247001](https://ocean.sankuai.com/config/#/page/detail?id=42389857&channelId=510) |
| **CIA** | 0x03 监控 |

---

## 通兑单详页（新）

| 属性 | 值 |
|------|-----|
| **关键词** | 通兑卡、订单详情、通兑单详、商品兑换 |
| **技术栈** | DUO |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_daodianpingtai_ex-coupon-order |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/trade-ex-coupon.git |
| **仓库https链接** | https://dev.sankuai.com/code/repo-detail/nibfe/trade-ex-coupon/file/list?path=ex-coupon-order-detail |
| **diva链接** | https://diva.sankuai.com/bundle/rn_daodianpingtai_ex-coupon-order/versions?env=prod |
| **projectId** | 43418 |
| **raptor 异常链接** | https://raptor.mws.sankuai.com/frontend/error/list?projectId=43418 |
| **后端日志 Appkey** | com.sankuai.mptrade.api |
| **后端日志链接** | https://raptor.mws.sankuai.com/log/topic/view/com.sankuai.mptrade.api?searchType=expert&searchGrammar=dsl&timeType=5m~0m&startDate=20260724193201&endDate=20260724193701&iSLimit=100&pageNum=1&pageSize=50 |
| **PV量级** |十万级（新老合并cid） |
| **CID（Ocean配置）** | [c_special_groupon_5813gb19](https://ocean.sankuai.com/config/#/page/detail?id=42392986&channelId=557) |
| **CIA** | 0x03 监控 |

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

> 完整资产数据请查阅：aHR0cHM6Ly9rbS5zYW5rdWFpLmNvbS9jb2xsYWJwYWdlLzI3NTA5MDExNjU=
