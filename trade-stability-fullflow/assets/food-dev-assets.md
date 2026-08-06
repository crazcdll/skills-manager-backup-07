# 到餐交易前端研发资产映射表

数据来源：aHR0cHM6Ly9rbS5zYW5rdWFpLmNvbS9jb2xsYWJwYWdlLzI3NTY2NTYzOTc=
特殊说明
1、DUO页面特有DUO页面ID、DUO页面链接
2、I版特有pageId
3、i版和小程序技术栈特有页面路径，无Bundle信息和diva地址。DUO、MRN和MAX无业务路径，独有Bundle信息和diva地址
---

## 页面索引

| 页面 | 技术栈 |
|------|--------|
| [团购提单（DUO）](#团购提单duo) | DUO |
| [团购提单（MRN-旧提单）](#团购提单mrn-旧提单) | MRN |
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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQxMz9icmFuY2g9bWFzdGVy |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/duo-food-order-submit.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9kdW8tZm9vZC1vcmRlci1zdWJtaXQvZmlsZS9saXN0P2JyYW5jaD1tYXN0ZXI= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfYy1ncm91cC1vcmRlci1zdWJtaXQvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 10749 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTEwNzQ5 | 
| **后端日志（precreate）Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志（precreate）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmdyb3VwdHJhZGUucHJlY3JlYXRlLmFwaWM= |
| **后端日志（query）Appkey** | com.sankuai.web.order.front |
| **后端日志（query）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5mcm9udA== |

**CID（Ocean配置）**：
- 美团：c_meishi_rao5v99i（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjA1NDI0MiZjaGFubmVsSWQ9Mjg=）
- 点评：c_sfcp07i（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDAwMDgzNSZjaGFubmVsSWQ9Mjg=）
- 美小：c_90v1nrbr（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDcwMTAwNiZjaGFubmVsSWQ9Mjg=）
- 点小：c_7tcab35u（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDMwODM0NCZjaGFubmVsSWQ9Mjg=）
- 美团鸿蒙：c_meishi_xkxr9rrq（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzEwNzU5MCZjaGFubmVsSWQ9Mjg=）
- 点评鸿蒙：c_meishi_m1kk37gm（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzEwNzYzOSZjaGFubmVsSWQ9Mjg=）

**CIA**：
- 美团：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM2NzY0NjY3JnRhYj1tb2R1bGU=
- 点评：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MzQw
- 美小：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDE2
- 点小：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDUy
- 百度：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9NzU3MjI2Nzg4
- 美团鸿蒙：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9NjA5OTY5MzYx
- 点评鸿蒙：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9NjIzMTU0NjU5

---

## 团购提单（MRN-旧提单）

| 属性 | 值 |
|------|-----|
| **关键词** | 团购提单、提单页、下单页、确认订单（MRN旧架构） |
| **技术栈** | MRN（old架构） |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android |
| **bundle** | rn_meishi_food-order-submit |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZm9vZC1vcmRlci1zdWJtaXQvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 29883 |
| **raptor 异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI5ODgz |
| **后端日志（precreate）Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志（precreate）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmdyb3VwdHJhZGUucHJlY3JlYXRlLmFwaWM= |
| **后端日志（query）Appkey** | com.sankuai.web.order.front |
| **后端日志（query）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5mcm9udA== |

---

## 团购提单（MAX）

| 属性 | 值 |
|------|-----|
| **关键词** | 团购提单旧版、MAX提单、圈圈站外提单、商企通提单、百度提单 |
| **技术栈** | MAX（旧版） |
| **覆盖端** | 圈圈站外/商企通/百度/支付宝/惠省/其他 |
| **覆盖系统** | iOS/Android |
| **bundle** | rn_meishi_c-group-order-submit-max |
| **H5路径** | aHR0cHM6Ly9hd3AubWVpdHVhbi5jb20vbWVpcy9iaXotY3Jvc3MtZm9vZC10cmFuc2FjdGlvbi9ncm91cC1vcmRlci1zdWJtaXQvd2ViL2luZGV4Lmh0bWw/ZGVhbElkPQ== |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/biz-cross-food-transaction.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Jpei1jcm9zcy1mb29kLXRyYW5zYWN0aW9uL2ZpbGUvbGlzdD9wYXRoPWdyb3VwLW9yZGVyLXN1Ym1pdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfYy1ncm91cC1vcmRlci1zdWJtaXQtbWF4L3ZlcnNpb25z |
| **projectId** | 14930 |
| **raptor客户端异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE0OTMw |
| **raptor小程序异常链接** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL21wL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE0OTMw |
| **后端日志（precreate）Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志（precreate）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmdyb3VwdHJhZGUucHJlY3JlYXRlLmFwaWM= |
| **后端日志（query）Appkey** | com.sankuai.web.order.front |
| **后端日志（query）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5mcm9udA== |

**CID（Ocean配置）**：
- c_meishi_onqxln25（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzI0MDYyNSZjaGFubmVsSWQ9Mjg=）

**CIA**：
- 美团：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM2NzY0NjY3JnRhYj1tb2R1bGU=
- 点评：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MzQw
- 美小：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDE2
- 点小：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDUy
- 百度：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9NzU3MjI2Nzg4
- 美团鸿蒙：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9NjA5OTY5MzYx
- 点评鸿蒙：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9NjIzMTU0NjU5

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS10cmFuc2FjdGlvbi9maWxlL2xpc3Q= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZm9vZC1wYXktcmVzdWx0L3ZlcnNpb25z |
| **projectId** | 9907 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTk5MDc= |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

**CID（Ocean配置）**：
- 美团：c_yh70r8a（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDAwMDkzMyZjaGFubmVsSWQ9Mjg=）
- 点评：c_itr20uu（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDAwMDgzNiZjaGFubmVsSWQ9Mjg=）

**CIA**：
- 美团：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDIxJnRhYj1tb2R1bGU=
- 点评：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDI4

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9kZmUvYml6LW1pbmlhcHAtZm9vZC10cmFuc2FjdGlvbi9maWxlL2xpc3Q/cGF0aD1wYWNrYWdlcyUyRnBheS1yZXN1bHQ= |
| **projectId** | 11699 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL21wL2Vycm9yL2xpc3Q/cHJvamVjdElkPTExNjk5 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

**CID（Ocean配置）**：
- 美小：c_meishi_muloxd4i

**CIA**：
- 美小：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDg3

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9kZmUvYml6LWNyb3NzLWZvb2QtdHJhbnNhY3Rpb24tZ3JvdXAvZmlsZS9saXN0P3BhdGg9Z3JvdXAtcGF5LXJlc3VsdC1zbGlkZS1tb2RhbA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZ3JvdXAtcGF5LXJlc3VsdC1zbGlkZS1tb2RhbC92ZXJzaW9ucw== |
| **projectId** | 27179 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI3MTc5 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

**CID（Ocean配置）**：
- 美团：c_meishi_1b73khe6（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00Mjk1OTA0NyZjaGFubmVsSWQ9MjgmdGFiTmFtZT1wYWdlJnNvdXJjZV9jbGljaz0yMQ==）

**CIA**：
- 美团：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9NDgyMTQyNDA5

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjI5OT9icmFuY2g9bWFzdGVy |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS10cmFuc2FjdGlvbi9maWxlL2xpc3Q/cGF0aD1mb29kLW9yZGVyLWRldGFpbC1kdW8mYnJhbmNoPW1hc3Rlcg== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZm9vZC1vcmRlci1kZXRhaWwvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 8699 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTg2OTk= |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmZvb2R0cmFkZS5ncm91cGJ1eS5hcGlj |

**CID（Ocean配置）**：
- c_8f91rdb

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDIx

---

## 订单详情页（i版）

| 属性 | 值 |
|------|-----|
| **关键词** | i版订单详情、百度订单详情、支付宝订单详情 |
| **技术栈** | i版 |
| **覆盖端** | 百度/支付宝/其他 |
| **覆盖系统** | iOS/Android |
| **页面路径** | aHR0cHM6Ly9tZWlzaGkubWVpdHVhbi5jb20vaS9vcmRlci9kZXRhaWwve3tvcmRlcklkfX0= |
| **raptor项目名** | com.sankuai.meishi.fe.iorderdetail |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi.mobile.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS5tb2JpbGUvZmlsZS9saXN0 |
| **projectId** | 2714 |
| **pageId** | 12278 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI3MTQmcGFnZUlkPTEyMjc4 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmZvb2R0cmFkZS5ncm91cGJ1eS5hcGlj |

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQ1Mz9icmFuY2g9bWFzdGVy |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi-transaction.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS10cmFuc2FjdGlvbi9maWxlL2xpc3Q/cGF0aD1ncm91cC1jYW5jZWwtb3JkZXItbmV3JmJyYW5jaD1tYXN0ZXI= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZ3JvdXAtY2FuY2VsLW9yZGVyLW5ldy92ZXJzaW9ucz9lbnY9cHJvZA== |
| **projectId** | 38912 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM4OTEy |
| **后端日志Appkey** | com.sankuai.web.refund.applyproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5yZWZ1bmQuYXBwbHlwcm94eQ== |

**CID（Ocean配置）**：
- c_meishi_xhks37n3

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDIx

---

## 申请退款（i版）

| 属性 | 值 |
|------|-----|
| **关键词** | i版退款、百度退款、支付宝退款 |
| **技术栈** | i版 |
| **覆盖端** | 商企通/百度/支付宝/其他 |
| **覆盖系统** | iOS/Android |
| **页面路径** | aHR0cHM6Ly9tZWlzaGkubWVpdHVhbi5jb20vaS9yZWZ1bmQve3tvcmRlcklkfX0= |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/meishi.mobile.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS5tb2JpbGUvZmlsZS9saXN0 |
| **projectId** | 2714（同 i版订单详情） |
| **pageId** | 12277 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI3MTQmcGFnZUlkPTEyMjc3 |
| **后端日志Appkey** | com.sankuai.web.refund.applyproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5yZWZ1bmQuYXBwbHlwcm94eQ== |

**CID（Ocean配置）**：
- 美团：c_gphEA
- 点评：c_mIVcz
- 微信：c_mIVcz

**CIA**：
- 美团：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDIx
- 点评：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDI4
- 微信：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDI4

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS10cmFuc2FjdGlvbi9maWxlL2xpc3Q=?path=group-coupon-detail |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfY291cG9uLWRldGFpbC92ZXJzaW9ucw== |
| **projectId** | 9963 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTk5NjM= |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

**CID（Ocean配置）**：
- 美团：c_6eo1z1hf（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDY3ODQ1MCZjaGFubmVsSWQ9Mjg=）
- 点评：c_sz2kxrk2（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDc0ODM1OSZjaGFubmVsSWQ9Mjg=）

**CIA**：
- 美团：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MTQy
- 点评：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDcy

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9NRUlTL21laXNoaS1tcm4vZmlsZS9saXN0P2NvZGVBcmVhPWJqJmJyYW5jaD1yZWZzJTJGaGVhZHMlMkZtYXN0ZXImcGF0aD1naWZ0LWdpdmluZw== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZ2lmdC1naXZpbmcvdmVyc2lvbnM= |
| **projectId** | 11563 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTExNTYz |
| **后端日志（foodtrade apic）Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志（foodtrade apic）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmZvb2R0cmFkZS5ncm91cGJ1eS5hcGlj |

**CID（Ocean配置）**：
- 美团：c_meishi_m4hfiti9（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzMxOTY4MSZjaGFubmVsSWQ9Mjg=）

**CIA**：
- 美团：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9ODY2MjYxNzU5

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQzMT9wcm90b2NvbElkPTAwMDYmcHJvdG9jb2xWZXJzaW9uPTAwMDE= |
| **H5路径** | aHR0cHM6Ly9hd3AubWVpdHVhbi5jb20vZGZlL2R1by1wYWdlL2dpZnQtcmVjZWlwdC93ZWIvaW5kZXguaHRtbA== |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Zvb2QtZHVvL2ZpbGUvbGlzdD9wYXRoPWdpZnQtcmVjZWlwdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZ2lmdC1yZWNlaXB0L3ZlcnNpb25z |
| **projectId** | 34117 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM0MTE3 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmZvb2R0cmFkZS5ncm91cGJ1eS5hcGlj |

**CID（Ocean配置）**：
- 美小：c_meishi_urvhx3zl（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzMxOTY4MiZjaGFubmVsSWQ9Mjg=）

**CIA**：
- 美小：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9ODY2MzI2OTc4

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Jpei1jcm9zcy1mb29kLXRyYW5zYWN0aW9uL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZm9vZC1jYW5jZWwtb3JkZXIvdmVyc2lvbnM= |
| **projectId** | 13843 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTEzODQz |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

**CID（Ocean配置）**：
- 美团：c_meishi_6ugsewk9（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjIxNzk2NyZjaGFubmVsSWQ9Mjg=）

**CIA**：
- 美团：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTQzMjUxMzA2

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS10cmFuc2FjdGlvbi9maWxlL2xpc3Q=?branch=refs%2Fheads%2Fmaster&path=transaction-snapshot |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfdHJhbnNhY3Rpb24tc25hcHNob3QvdmVyc2lvbnM/ZW52PXByb2Q= |
| **projectId** | 11010 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTExMDEw |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

**CID（Ocean配置）**：
- c_meishi_am3i50v9（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MjA2NTk2MyZjaGFubmVsSWQ9Mjg=）

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQyMj9icmFuY2g9bWFzdGVy |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmFuc2FjdGlvbi1zbmFwc2hvdC9maWxlL2xpc3Q/cGF0aD0mYnJhbmNoPW1hc3Rlcg== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfdHJhbnNhY3Rpb24tc25hcHNob3QtZHVvL3ZlcnNpb25z |
| **projectId** | 31637 |
| **raptor 异常** | aHR0cDovL3JhcHRvci5td3Muc2Fua3VhaS5jb20vZnJvbnRlbmQvZXJyb3IvbGlzdD9wcm9qZWN0SWQ9MzE2Mzc= |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9kY2FuL2Zvb2QtbXJuL2ZpbGUvbGlzdD9wYXRoPWZvb2Qtc2hvcHBpbmctY2FydC1saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZm9vZC1zaG9wcGluZy1jYXJ0LWxpc3QvdmVyc2lvbnM= |
| **projectId** | 9522 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTk1MjI= |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2Zvb2RfY2FydF9vcmRlcg==（⚠️ topic 为下划线格式，logcenter 查询时直接用 `-l food_cart_order`） |

**CID（Ocean配置）**：
- 美团：c_meishi_mvt1vdli

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDIx

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
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfYy1ncm91cC1vcmRlci1zdWJtaXQtb2xkL3ZlcnNpb25zP2Vudj1wcm9k |
| **projectId** | 14801 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE0ODAx |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2Zvb2RfY2FydF9vcmRlcg== |

**CID（Ocean配置）**：
- 综：c_gc_031k2o7b
- 餐：c_meishi_rao5v99i（与团购提单一致）

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MDIx

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9kZmUvYml6LWNyb3NzLWludGVsbGlnZW50LW9yZGVyL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZm9vZC1tb3AtY2FydC1saXN0L3ZlcnNpb25z |
| **projectId** | 35193 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM1MTkz |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2Zvb2RfY2FydF9vcmRlcg== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9vcmRlci1zdWJtaXQtZGVsaXZlcnkvZmlsZS9saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZ3JvdXAtb3JkZXItc3VibWl0LWRlbGl2ZXJ5L3ZlcnNpb25z |
| **projectId** | 32227 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTMyMjI3 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

**CID（Ocean配置）**：
- c_meishi_5cq45lir（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzI5ODc1MCZjaGFubmVsSWQ9Mjg=）

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9kZmUvYml6LWNyb3NzLWZvb2QtdHJhbnNhY3Rpb24tZ3JvdXAvZmlsZS9saXN0P3BhdGg9ZGVsaXZlcnktZm9vZC1vcmRlci1kZXRhaWw= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZGVsaXZlcnktZm9vZC1vcmRlci1kZXRhaWwvdmVyc2lvbnM= |
| **projectId** | 15913 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE1OTEz |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjMwNT9wcm90b2NvbElkPTAwMDEmcHJvdG9jb2xWZXJzaW9uPTAwMDE= |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Zvb2QtZHVvL2ZpbGUvbGlzdD9wYXRoPWRlbGl2ZXJ5LWxvZ2lzdGljLWRldGFpbA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZGVsaXZlcnktbG9naXN0aWMtZGV0YWlsL3ZlcnNpb25z |
| **projectId** | 29056 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI5MDU2 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.booking |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmZvb2R0cmFkZS5ncm91cGJ1eS5ib29raW5n |
| **APP跳链** | imeituan://www.meituan.com/mrn?mrn_biz=meishi&mrn_entry=delivery-logistic-detail&mrn_component=main |
| **H5跳链** | aHR0cHM6Ly9hd3AubWVpdHVhbi5jb20vZGZlL2R1by1wYWdlL2RlbGl2ZXJ5LWxvZ2lzdGljLWRldGFpbC93ZWIvaW5kZXguaHRtbA== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9kZmUvYml6LWNyb3NzLWZvb2QtdHJhbnNhY3Rpb24tZ3JvdXAvZmlsZS9saXN0P3BhdGg9ZGVsaXZlcnktZm9vZC1vcmRlci1kZXRhaWw= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZGVsaXZlcnktZm9vZC1jYW5jZWwtb3JkZXIvdmVyc2lvbnM= |
| **projectId** | 15915 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE1OTE1 |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9kZmUvYml6LWNyb3NzLWludGVsbGlnZW50LW9yZGVyL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfaW50ZWxsaS1vcmRlci1ob21lL3ZlcnNpb25z |
| **projectId** | 34467 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM0NDY3 |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2Zvb2RfY2FydF9vcmRlcg== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9zbWFydC13YWl0ZXItdW5pZmllZC9maWxlL2xpc3Q= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfaW50ZWxsaS1vcmRlci1ob21lL3ZlcnNpb25z |
| **projectId** | 34467 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM0NDY3 |
| **后端日志Appkey** | food_cart_order |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2Zvb2RfY2FydF9vcmRlcg== |

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQzNj9icmFuY2g9bWFzdGVy |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/smart-ordering.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL3NtYXJ0LW9yZGVyaW5nL2ZpbGUvbGlzdD9wYXRoPW9yZGVyLXN1Ym1pdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfc21hcnQtb3JkZXItZm9vZC1zdWJtaXQvdmVyc2lvbnM= |
| **projectId** | 34867 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM0ODY3 |
| **后端日志Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmdyb3VwdHJhZGUucHJlY3JlYXRlLmFwaWM= |

**CID（Ocean配置）**：
- c_meishi_pc2p5yfu（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzM2ODk4MyZjaGFubmVsSWQ9Mjg=）

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9OTQ2NjU5MjE1

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQzNz9icmFuY2g9bWFzdGVy |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/smart-ordering.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL3NtYXJ0LW9yZGVyaW5nL2ZpbGUvbGlzdD9wYXRoPXNtYXJ0LW9yZGVyLWRldGFpbA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfc21hcnQtb3JkZXItZGV0YWlsL3ZlcnNpb25z |
| **projectId** | 34765 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM0NzY1 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmZvb2R0cmFkZS5ncm91cGJ1eS5hcGlj |

**CID（Ocean配置）**：
- c_meishi_y0frjxgd（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzM2NzQwNSZjaGFubmVsSWQ9Mjg=）

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9OTYyODE5Njky

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQ1MT9icmFuY2g9bWFzdGVy |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/smart-ordering.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL3NtYXJ0LW9yZGVyaW5nL2ZpbGUvbGlzdD9wYXRoPXNtYXJ0LXJlZnVuZC1kZXRhaWw= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfc21hcnQtcmVmdW5kLWRldGFpbC92ZXJzaW9ucw== |
| **projectId** | 36876 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM2ODc2 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.apic |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmZvb2R0cmFkZS5ncm91cGJ1eS5hcGlj |

**CID（Ocean配置）**：
- c_meishi_nc0w2m5z（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzQ0NjcyMiZjaGFubmVsSWQ9Mjg=）

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTA3ODA5MzExMA==

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQxNj9wcm90b2NvbElkPTAwMjMmcHJvdG9jb2xWZXJzaW9uPTAwMDE= |
| **入口** | 支持一键买单的 POI / 券码详情页-去买单 |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Zvb2QtZHVvL2ZpbGUvbGlzdD9wYXRoPWNvdXBvbi1wYXk= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfY291cG9uLXBheS92ZXJzaW9ucw== |
| **projectId** | 30176 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTMwMTc2 |
| **后端日志Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmdyb3VwdHJhZGUucHJlY3JlYXRlLmFwaWM= |

**CID（Ocean配置）**：
- c_meishi_p1pyv5zo（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzE0MjI4NCZjaGFubmVsSWQ9Mjg=）

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9NjYxNTEwMTU4

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQyMA== |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Zvb2QtZHVvL2ZpbGUvbGlzdD9wYXRoPWNvdXBvbi1wYXk=-result |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfY291cG9uLXBheS1yZXN1bHQvdmVyc2lvbnM= |
| **projectId** | 33636 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTMzNjM2 |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

**CID（Ocean配置）**：
- c_mewpv96（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MDAwMDkzNCZjaGFubmVsSWQ9Mjg=）

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM0NDU2MTAx

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQxNz9wcm90b2NvbElkPTAwMDgmcHJvdG9jb2xWZXJzaW9uPTAwMDE= |
| **仓库SSH** | ssh://git@git.sankuai.com/meis/food-duo.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Zvb2QtZHVvL2ZpbGUvbGlzdD9wYXRoPWNvdXBvbi1wYXk=-cancel |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfY291cG9uLXBheS1jYW5jZWwvdmVyc2lvbnM= |
| **projectId** | 30359 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTMwMzU5 |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

**CID（Ocean配置）**：
- c_meishi_txu19v2c（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzE0MjMzNiZjaGFubmVsSWQ9Mjg=）

**CIA**：
- aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9NjQ5MzE5MDAz

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS10cmFuc2FjdGlvbi9maWxlL2xpc3Q= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfcGF5L3ZlcnNpb25z |
| **projectId** | 6709 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTY3MDk= |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Jpei1taW5pYXBwLWZvb2QtdHJhbnNhY3Rpb24vZmlsZS9saXN0 |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS53eGFwcC9maWxlL2xpc3Q= |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS10cmFuc2FjdGlvbi9maWxlL2xpc3Q= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfcGF5LXJlc3VsdC92ZXJzaW9ucw== |
| **projectId** | 6871 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTY4NzE= |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Jpei1taW5pYXBwLWZvb2QtdHJhbnNhY3Rpb24vZmlsZS9saXN0 |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS53eGFwcC9maWxlL2xpc3Q= |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS53eGFwcC9maWxlL2xpc3Q= |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL21laXNoaS10cmFuc2FjdGlvbi9maWxlL2xpc3Q/cGF0aD1tYWl0b24tdm91Y2hlci1saXN0 |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfcGF5LXZvdWNoZXItbGlzdC92ZXJzaW9ucw== |
| **projectId** | 6707 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTY3MDc= |
| **后端日志Appkey** | dianping_dc_hui_huibusiness |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2RpYW5waW5nX2RjX2h1aV9odWlidXNpbmVzcw== |

**CID（Ocean配置）**：
- c_meishi_pns3mouv（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzI0MDYyNSZjaGFubmVsSWQ9Mjg=）

---

## C扫B提单

| 属性 | 值 |
|------|-----|
| **关键词** | C扫B、扫码、C扫B提单 |
| **技术栈** | i版 |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **仓库SSH** | ssh://git@git.dianpingoa.com/ed-f2e/app-menuorder-flashpay.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9lZC1mMmUvYXBwLW1lbnVvcmRlci1mbGFzaHBheS9maWxlL2xpc3Q= |
| **projectId** | 7991 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTc5OTE= |
| **后端日志Appkey** | ka-mixpay-web |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2thLW1peHBheS13ZWI= |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9lZC1mMmUvYXBwLW1lbnVvcmRlci1mbGFzaHBheS9maWxlL2xpc3Q= |
| **后端日志Appkey** | ka-mixpay-web |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2thLW1peHBheS13ZWI= |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9lZC1mMmUvYXBwLW1lbnVvcmRlci1mbGFzaHBheS9maWxlL2xpc3Q= |
| **后端日志Appkey** | ka-mixpay-web |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2thLW1peHBheS13ZWI= |

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
| **DUO页面链接** | aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjMxOQ== |
| **备注** | 区分餐综 |
| **仓库SSH** | ssh://git@git.sankuai.com/nibfe/duo-pintuan-result.git |
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9kdW8tcGludHVhbi1yZXN1bHQvZmlsZS9saXN0P3BhdGg9JmJyYW5jaD1tYXN0ZXI= |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZ3JvdXAtcGludHVhbi1yZXN1bHQvdmVyc2lvbnM= |
| **projectId** | 26582 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI2NTgy |
| **后端日志Appkey** | com.sankuai.web.order.groupapiqueryproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5vcmRlci5ncm91cGFwaXF1ZXJ5cHJveHk= |

**CID（Ocean配置）**：
- c_special_groupon_mtf9otu7（aHR0cHM6Ly9vY2Vhbi5zYW5rdWFpLmNvbS9jb25maWcvIy9wYWdlL2RldGFpbD9pZD00MzI0MDYyNSZjaGFubmVsSWQ9Mjg=）

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Jpei1jcm9zcy1mb29kLXRyYW5zYWN0aW9uL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfZm9vZC1vcmRlci1saXN0L3ZlcnNpb25z |
| **projectId** | 13842 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTEzODQy |
| **后端日志Appkey** | com.sankuai.foodtrade.food.trade |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmZvb2R0cmFkZS5mb29kLnRyYWRl |

**CID（Ocean配置）**：
- c_meishi_6ugsewk9

**CIA**：
- 美团：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTQzMjUxMzA2

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Jpei1jcm9zcy1mb29kLXRyYW5zYWN0aW9uL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfc2VsZi1yZWZ1bmQtc3VibWl0L3ZlcnNpb25z |
| **projectId** | 16178 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE2MTc4 |
| **后端日志Appkey** | com.sankuai.web.refund.applyproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5yZWZ1bmQuYXBwbHlwcm94eQ== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Jpei1jcm9zcy1mb29kLXRyYW5zYWN0aW9uL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfc2VsZi1yZWZ1bmQtZGV0YWlsL3ZlcnNpb25z |
| **projectId** | 16179 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE2MTc5 |
| **后端日志Appkey** | com.sankuai.web.refund.applyproxy |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLndlYi5yZWZ1bmQuYXBwbHlwcm94eQ== |

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
| **仓库https链接** | aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tZWlzL2Zvb2QtZHVvL2ZpbGUvbGlzdA== |
| **diva链接** | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9tZWlzaGlfbG9naXN0aWMtZGV0YWlsLXRvYi92ZXJzaW9ucw== |
| **projectId** | 37268 |
| **raptor 异常** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM3MjY4 |
| **后端日志Appkey** | com.sankuai.foodtrade.groupbuy.booking |
| **后端日志** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmZvb2R0cmFkZS5ncm91cGJ1eS5ib29raW5n |

---
