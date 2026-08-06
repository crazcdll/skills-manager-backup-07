# 门票&度假交易前端研发资产映射表

数据来源：aHR0cHM6Ly9rbS5zYW5rdWFpLmNvbS9jb2xsYWJwYWdlLzI3NTM2NjA2NTc=
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmF2ZWwtdHJhbnNhY3Rpb24tZHVvL2ZpbGUvbGlzdA==?path=ticket-submit-order |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfdHJhdmVsY29yZS1kdW8vdmVyc2lvbnM= |
| **projectId** | 31960 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTMxOTYw |
| **后端日志Appkey** | com.sankuai.triptrade.buy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRyaXB0cmFkZS5idXk= |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oZmUvdHJhdmVsLXRpY2tldC1tYXgvZmlsZS9saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfb3JkZXItZGV0YWlsL3ZlcnNpb25z |
| **projectId** | 12255 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTEyMjU1 |
| **后端日志Appkey** | com.sankuai.triptrade.order.manager |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRyaXB0cmFkZS5vcmRlci5tYW5hZ2Vy |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl90cmF2ZWxfdGlja2V0L2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfdHJhdmVsdGlja2V0L3ZlcnNpb25z |
| **projectId** | 8445 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTg0NDUmcGFnZUlkPTE4MDA0NTY= |
| **后端日志（trade.order）Appkey** | com.sankuai.trip.trade.order |
| **后端日志（trade.order）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRyaXAudHJhZGUub3JkZXI= |
| **后端日志（order.manager）Appkey** | com.sankuai.triptrade.order.manager |
| **后端日志（order.manager）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRyaXB0cmFkZS5vcmRlci5tYW5hZ2Vy |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmF2ZWwtdHJhbnNhY3Rpb24tZHVvL2ZpbGUvbGlzdA==?path=ticket-request-refund |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfdGlja2V0LXJlcXVlc3QtcmVmdW5kL3ZlcnNpb25z |
| **projectId** | 37761 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM3NzYx |
| **后端日志Appkey** | com.sankuai.mptrade.api |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS9sdnlvdS9maWxlL2xpc3Q=?path=src%2Fapps%2Fqrcode-list |
| **projectId** | 2224 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTIyMjQmcGFnZUlkPTIwNjYyNTc= |
| **后端日志（order.manager）Appkey** | com.sankuai.triptrade.order.manager |
| **后端日志（order.manager）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRyaXB0cmFkZS5vcmRlci5tYW5hZ2Vy |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9odG1ybi9ybl90cmF2ZWxfdGlja2V0L2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfdHJhdmVsdGlja2V0L3ZlcnNpb25z |
| **projectId** | 8445 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTg0NDUmcGFnZUlkPTczNDY0MjE= |
| **后端日志（trade.order）Appkey** | com.sankuai.trip.trade.order |
| **后端日志（trade.order）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRyaXAudHJhZGUub3JkZXI= |
| **后端日志（meilv.rhone）Appkey** | com.sankuai.meilv.rhone |
| **后端日志（meilv.rhone）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1laWx2LnJob25l |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oZmUvc2hhcmUtdHJhdmVsLW1heC9maWxlL2xpc3Q= |
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oZmUvbWF4LXRyYXZlbC10aWNrZXQtc3VibWl0b3JkZXIvZmlsZS9saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfdHJhdmVsbXBwbHVzL3ZlcnNpb25z |
| **projectId** | 8602 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTg2MDImcGFnZUlkPTE4NjY2ODU= |
| **后端日志（tp.dpack.api）Appkey** | com.sankuai.tp.dpack.api |
| **后端日志（tp.dpack.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRwLmRwYWNrLmFwaQ== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS9sdnlvdS9maWxlL2xpc3Q/cGF0aD1zcmMlMkZwYWdlcyUyRm9yZGVyJTJGcGFja2FnZQ== |
| **projectId** | 2224 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTIyMjQmcGFnZUlkPTI1Nzk0 |
| **后端日志（tp.dpack.api）Appkey** | com.sankuai.tp.dpack.api |
| **后端日志（tp.dpack.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRwLmRwYWNrLmFwaQ== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS9sdnlvdS9maWxlL2xpc3Q=?path=src%2Fpages%2Frefund%2Fapply%2Fpackage |
| **projectId** | 2224 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTIyMjQmcGFnZUlkPTI1Nzk2 |
| **后端日志（tp.dpack.api）Appkey** | com.sankuai.tp.dpack.api |
| **后端日志（tp.dpack.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRwLmRwYWNrLmFwaQ== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS9sdnlvdS9maWxlL2xpc3Q=?path=src%2Fpages%2Frefund%2Fdetail |
| **projectId** | 2224 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTIyMjQmcGFnZUlkPTI1Nzcz |
| **后端日志（precreate）Appkey** | 待补充 |
| **后端日志（precreate）** | 待补充 |
| **后端日志（tp.dpack.api）Appkey** | com.sankuai.tp.dpack.api |
| **后端日志（tp.dpack.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRwLmRwYWNrLmFwaQ== |

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
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfdHJhdmVsLWFnZW5jeS1jb250YWluZXIvdmVyc2lvbnM= |
| **projectId** | 6108 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2JyaWVmP3Byb2plY3RJZD02MTA4 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

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
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfdHJhdmVsLWFnZW5jeS1jb250YWluZXIvdmVyc2lvbnM= |
| **projectId** | 6108 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2JyaWVmP3Byb2plY3RJZD02MTA4 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

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
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfdHJhdmVsLWFnZW5jeS1jb250YWluZXIvdmVyc2lvbnM= |
| **projectId** | 6108 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2JyaWVmP3Byb2plY3RJZD02MTA4 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

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
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfdHJhdmVsLWFnZW5jeS1jb250YWluZXIvdmVyc2lvbnM= |
| **projectId** | 6108 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2JyaWVmP3Byb2plY3RJZD02MTA4 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmF2ZWwtdHJhbnNhY3Rpb24tZHVvL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfZ3JvdXAtdG91ci1zdWJtaXQtb3JkZXItYmFzZS92ZXJzaW9ucw== |
| **projectId** | 36431 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM2NDMx |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS90cmlwL2ZpbGUvbGlzdD9wYXRoPXNyYyUyRmFwcHMlMkZvcmRlciUyRmd0eQ== |
| **projectId** | 2224 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL3JlcXVlc3QvdHJlbmQ/cHJvamVjdElkPTIyMjQmcGFnZUlkPTI1ODA4 |
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmF2ZWwtdHJhbnNhY3Rpb24tZHVvL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfZ3R5LW9yZGVyLWRldGFpbC92ZXJzaW9ucw== |
| **projectId** | 41398 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2N1c3RvbV9rZXkvP3Byb2plY3RJZD00MTM5OA== |
| **后端日志（grouptour.api）Appkey** | com.sankuai.triptrade.grouptour.api |
| **后端日志（grouptour.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLnRyaXB0cmFkZS5ncm91cHRvdXIuYXBpX2FsbA== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS9sdnlvdS9maWxlL2xpc3Q= |
| **projectId** | 2224 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL3JlcXVlc3QvdHJlbmQ/cHJvamVjdElkPTIyMjQmcGFnZUlkPTI1ODI4 |
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oNS90cmlwL2ZpbGUvbGlzdD9wYXRoPXNyYyUyRmFwcHMlMkZyZWZ1bmQlMkZndHk= |
| **projectId** | 2224 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL3JlcXVlc3QvdHJlbmQ/cHJvamVjdElkPTIyMjQmcGFnZUlkPTI1ODA5 |
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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmF2ZWwtdHJhbnNhY3Rpb24tZHVvL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfZ3JvdXAtdG91ci1zdWJtaXQtb3JkZXIvdmVyc2lvbnM= |
| **projectId** | 35047 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM1MDQ3 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmF2ZWwtdHJhbnNhY3Rpb24tZHVvL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfZ3JvdXAtdG91ci1vcmRlci1kZXRhaWwvdmVyc2lvbnM= |
| **projectId** | 35062 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM1MDYy |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmF2ZWwtdHJhbnNhY3Rpb24tZHVvL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfZ3JvdXAtdG91ci1yZWZ1bmQvdmVyc2lvbnM= |
| **projectId** | 35066 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM1MDY2 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmF2ZWwtdHJhbnNhY3Rpb24tZHVvL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl90cmF2ZWxfZ3JvdXAtdG91ci1yZWZ1bmQtZGV0YWlsL3ZlcnNpb25z |
| **projectId** | 35069 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM1MDY5 |
| **后端日志（mptrade.api）Appkey** | com.sankuai.mptrade.api |
| **后端日志（mptrade.api）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLm1wdHJhZGUuYXBp |

**CID（Ocean配置）**：
- 待补充

**CIA**：
- 待补充
