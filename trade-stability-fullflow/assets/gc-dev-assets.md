# 服务零售交易前端研发资产映射表

数据来源：aHR0cHM6Ly9rbS5zYW5rdWFpLmNvbS9jb2xsYWJwYWdlLzIwMjIyODk0NzY=

---

## 页面索引

| 页面 | 技术栈 | projectId |
|------|--------|-----------|
| [新团购提单/一品多态提单页](#新团购提单一品多态提单页) | DUO+MAX | 28372 |
| [团购提单（MRN）](#团购提单mrn) | MRN | 15675 |
| [新订单详情](#新订单详情) | DUO+MAX | 32943 |
| [订单详情（老订详）](#订单详情老订详) | MRN | 8072 |
| [预订提单页](#预订提单页) | DUO+MAX | 30325 |
| [预订订详](#预订订详) | DUO+MAX | 31959 |
| [预付提单页](#预付提单页) | DUO+MAX | 27703 |
| [多品提单页](#多品提单页) | DUO+MAX | 38157 |
| [申请退款页](#申请退款页) | DUO+MAX | 33671 |
| [退款规则浮层](#退款规则浮层) | DUO+MAX | 33871 |
| [价保服务页](#价保服务页) | MRN | 19207 |
| [泛商品（MRN）](#泛商品mrn) | MRN | 16907 |
| [泛商品（H5）](#泛商品h5) | H5 | 9497 |
| [Fuse](#fuse) | H5 | 9930 |
| [I站](#i站) | H5 | - |

---

## 新团购提单/一品多态提单页

| 属性 | 值 |
|------|-----|
| **关键词** | 团购提单、提单页、下单页、确认订单、一品多态 |
| **技术栈** | DUO+MAX |
| **覆盖端** | 美团/点评/美小/点小/圈小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_gc_gc-group-order-submit |
| **projectId** | 28372 |
| **后端日志（precreate）Appkey** | com.sankuai.grouptrade.precreate.apic |
| **后端日志（precreate）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2NvbS5zYW5rdWFpLmdyb3VwdHJhZGUucHJlY3JlYXRlLmFwaWM= |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/gc-group-order-submit.git |
| **本地目录** | All_gc_project/gc-group-order-submit |
| **备注** | 团购新提单页，主力版本 |

**链接**：
- diva：aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9nY19nYy1ncm91cC1vcmRlci1zdWJtaXQvdmVyc2lvbnM/ZW52PXByb2Q=
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9nYy1ncm91cC1vcmRlci1zdWJtaXQvZmlsZS9saXN0P3BhdGg9cGFja2FnZXM=
- raptor 异常：aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTI4Mzcy
- CIA：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM2NzY5NjU5JnRhYj1vcmc=


**CID（Ocean配置）**：
- c_0evvuz5

---

## 团购提单（MRN）

| 属性 | 值 |
|------|-----|
| **关键词** | 团购提单MRN版、MRN提单 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_gc_gcsubmitordermrnmodules |
| **projectId** | 15675 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/gcsubmitordermrnmodules.git |
| **备注** | 团购提单MRN版本，流量较低，逐步被DUO版替代 |

**链接**：
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9nY3N1Ym1pdG9yZGVybXJubW9kdWxlcy9maWxlL2xpc3Q=
- raptor 异常：aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE1Njc1
- CIA：aHR0cHM6Ly9jaWEuc2Fua3VhaS5jb20vcGFnZS9kZXRhaWw/aWQ9MTM2NzY5NzUzJnRhYj1vcmc=

**CID（Ocean配置）**：
- createtuanorder

---

## 新订单详情

| 属性 | 值 |
|------|-----|
| **关键词** | 订单详情、订单信息、查看订单 |
| **技术栈** | DUO+MAX |
| **覆盖端** | 美团/点评/美小/点小/圈小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_gc_group-order-detail |
| **DUO页面ID** | DUO-12428 |
| **projectId** | 32943 |
| **后端日志（precreate）Appkey** | dztrade-mapi-web |
| **后端日志（precreate）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L2R6dHJhZGUtbWFwaS13ZWI= |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/gc-group-order-detail.git |
| **本地目录** | All_gc_project/gc-group-order-detail |

**链接**：
- diva：aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9nY19ncm91cC1vcmRlci1kZXRhaWwvdmVyc2lvbnM/ZW52PXByb2Q=
- DUO页面：aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQyOD9icmFuY2g9bWFzdGVy
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9nYy1ncm91cC1vcmRlci1kZXRhaWwvZmlsZS9saXN0
- raptor 异常：aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTMyOTQz

---

## 订单详情（老订详）

| 属性 | 值 |
|------|-----|
| **关键词** | 老版订单详情、MRN订单详情 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_gc_gctrademrnmodules-mt、rn_gc_gctrademrnmodules |
| **projectId** | 8072 |
| **后端日志（precreate）Appkey** | mapi-mtusercenter-web |
| **后端日志（precreate）** | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L21hcGktbXR1c2VyY2VudGVyLXdlYg== |
| **gitSSH** | ssh://git@git.dianpingoa.com/mobile/gctrademrnmodules.git |
| **备注** | 老版本，逐步被新订详替代 |

**链接**：
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9tb2JpbGUvZ2N0cmFkZW1ybm1vZHVsZXMvZmlsZS9saXN0
- raptor 异常：aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTgwNzI=

---

## 预订提单页

| 属性 | 值 |
|------|-----|
| **关键词** | 预订提单、预约提单 |
| **技术栈** | DUO+MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **DUO页面ID** | DUO-12381 |
| **projectId** | 30325 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/gc-duo-dztrade-general.git |

**链接**：
- DUO页面：aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjM4MQ==
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9nYy1kdW8tZHp0cmFkZS1nZW5lcmFsL2ZpbGUvbGlzdA==

---

## 预订订详

| 属性 | 值 |
|------|-----|
| **关键词** | 预订订单详情 |
| **技术栈** | DUO+MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **DUO页面ID** | DUO-12421 |
| **projectId** | 31959 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/gc-duo-dztrade-general.git |

**链接**：
- DUO页面：aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjQyMQ==
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9nYy1kdW8tZHp0cmFkZS1nZW5lcmFsL2ZpbGUvbGlzdA==

---

## 预付提单页

| 属性 | 值 |
|------|-----|
| **关键词** | 预付提单 |
| **技术栈** | DUO+MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **DUO页面ID** | DUO-12381 |
| **projectId** | 27703 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/gc-duo-dztrade-general.git |

**链接**：
- DUO页面：aHR0cHM6Ly9kdW8uc2Fua3VhaS5jb20vcG9ydGFsL3BhZ2UvZGV0YWlsMi8xMjM4MQ==
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9nYy1kdW8tZHp0cmFkZS1nZW5lcmFsL2ZpbGUvbGlzdA==

---

## 多品提单页

| 属性 | 值 |
|------|-----|
| **关键词** | 多品提单、combo提单 |
| **技术栈** | DUO+MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_gc_combo-order-submit |
| **projectId** | 38157 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/combo-order-submit.git |

**链接**：
- diva：aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9nY19jb21iby1vcmRlci1zdWJtaXQvdmVyc2lvbnM/ZW52PXByb2Q=
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9jb21iby1vcmRlci1zdWJtaXQvZmlsZS9saXN0
- raptor 异常：aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTM4MTU3

---

## 申请退款页

| 属性 | 值 |
|------|-----|
| **关键词** | 申请退款、退款、取消订单 |
| **技术栈** | DUO+MAX |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_gc_max-gc-duo-refund |
| **projectId** | 33671 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/gc-duo-refund.git |

**链接**：
- diva：aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9nY19tYXgtZ2MtZHVvLXJlZnVuZC92ZXJzaW9ucz9lbnY9cHJvZA==
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9nYy1kdW8tcmVmdW5kL2ZpbGUvbGlzdA==
- raptor 异常：aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTMzNjcx

---

## 退款规则浮层

| 属性 | 值 |
|------|-----|
| **关键词** | 退款规则、退款说明浮层 |
| **技术栈** | DUO+MAX |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_gc_refund-rules-modal |
| **projectId** | 33871 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/refund-rules-modal.git |

**链接**：
- diva：aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS9ybl9nY19yZWZ1bmQtcnVsZXMtbW9kYWwvdmVyc2lvbnM/ZW52PXByb2Q=
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9yZWZ1bmQtcnVsZXMtbW9kYWwvZmlsZS9saXN0
- raptor 异常：aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTMzODcx

---

## 价保服务页

| 属性 | 值 |
|------|-----|
| **关键词** | 价保、价格保障、买贵必赔 |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **bundle** | rn_gc_gctradesubpagemrnmodules |
| **projectId** | 19207 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/gctradesubpagemrnmodules.git |

**链接**：
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS9nY3RyYWRlc3VicGFnZW1ybm1vZHVsZXMvZmlsZS9saXN0
- raptor 异常：aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPTE5MjA3

**CID（Ocean配置）**：
- 价保：c_gc_1dcahset
- 买贵必赔：c_gc_bly7txkx

---

## 泛商品（MRN）

| 属性 | 值 |
|------|-----|
| **关键词** | 泛商品MRN |
| **技术栈** | MRN |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **projectId** | 16907 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/tra-app-platform-mrn.git |
| **主分支** | release/canary |

**链接**：
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmEtYXBwLXBsYXRmb3JtLW1ybi9maWxlL2xpc3Q=

---

## 泛商品（H5）

| 属性 | 值 |
|------|-----|
| **关键词** | 泛商品H5 |
| **技术栈** | H5 |
| **覆盖端** | 美团/点评/美小/点小 |
| **覆盖系统** | iOS/Android/Harmony |
| **projectId** | 9497 |
| **gitSSH** | ssh://git@git.sankuai.com/nibfe/tra-app-platform-web.git |

**链接**：
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS90cmEtYXBwLXBsYXRmb3JtLXdlYi9maWxlL2xpc3Q=

---

## Fuse

| 属性 | 值 |
|------|-----|
| **关键词** | Fuse、综合交易H5 |
| **技术栈** | H5 |
| **覆盖端** | 美团/点评 |
| **覆盖系统** | iOS/Android/Harmony |
| **projectId** | 9930 |

**链接**：
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9uaWJmZS93aWRlbHktdHJhbnNhY3Rpb24vZmlsZS9saXN0

---

## I站

| 属性 | 值 |
|------|-----|
| **关键词** | I站、综合交易I版 |
| **技术栈** | H5 |
| **覆盖端** | 百度/支付宝/其他 |
| **覆盖系统** | iOS/Android |
| **projectId** | 无 |

**链接**：
- 仓库：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9nZmUvYXBwLXBhZ2UtdHVhbi9maWxlL2xpc3Q=

---

## 仓库速查

| 业务 | 仓库 | 技术栈 | gitSSH |
|------|------|--------|--------|
| 新团购提单/一品多态 | nibfe/gc-group-order-submit | DUO+MAX | ssh://git@git.sankuai.com/nibfe/gc-group-order-submit.git |
| 团购提单（MRN） | nibfe/gcsubmitordermrnmodules | MRN | ssh://git@git.sankuai.com/nibfe/gcsubmitordermrnmodules.git |
| 新订单详情 | nibfe/gc-group-order-detail | DUO+MAX | ssh://git@git.sankuai.com/nibfe/gc-group-order-detail.git |
| 老订详（MRN） | mobile/gctrademrnmodules | MRN | ssh://git@git.dianpingoa.com/mobile/gctrademrnmodules.git |
| 预订/预付提单+订详 | nibfe/gc-duo-dztrade-general | DUO+MAX | ssh://git@git.sankuai.com/nibfe/gc-duo-dztrade-general.git |
| 多品提单 | nibfe/combo-order-submit | DUO+MAX | ssh://git@git.sankuai.com/nibfe/combo-order-submit.git |
| 申请退款 | nibfe/gc-duo-refund | DUO+MAX | ssh://git@git.sankuai.com/nibfe/gc-duo-refund.git |
| 退款规则浮层 | nibfe/refund-rules-modal | DUO+MAX | ssh://git@git.sankuai.com/nibfe/refund-rules-modal.git |
| 页面组件 | nibfe/gc-trade-materials | - | ssh://git@git.sankuai.com/nibfe/gc-trade-materials.git |
| 价保/买贵必赔 | nibfe/gctradesubpagemrnmodules | MRN | ssh://git@git.sankuai.com/nibfe/gctradesubpagemrnmodules.git |
| 泛商品（MRN） | nibfe/tra-app-platform-mrn | MRN | ssh://git@git.sankuai.com/nibfe/tra-app-platform-mrn.git |
| 泛商品（H5） | nibfe/tra-app-platform-web | H5 | ssh://git@git.sankuai.com/nibfe/tra-app-platform-web.git |
| 泛商品组件 | nibfe/tra-app-platform-component | - | ssh://git@git.sankuai.com/nibfe/tra-app-platform-component.git |
| Fuse | nibfe/widely-transaction | H5 | - |
| I站 | gfe/app-page-tuan | H5 | - |
| 运营后台 | nibfe/spt-tp-manage | - | - |
| 预付通用（点评） | gfe/universal-prepayment-new-order | - | ssh://git@git.dianpingoa.com/gfe/universal-prepayment-new-order.git |
| 通用交易流程（点评） | gfe/general-transactions-process | - | ssh://git@git.dianpingoa.com/gfe/general-transactions-process.git |
| 通用预订（点评） | gfe/general-transactions-preorder | - | ssh://git@git.dianpingoa.com/gfe/general-transactions-preorder.git |

---

> 完整资产数据请查阅：aHR0cHM6Ly9rbS5zYW5rdWFpLmNvbS9jb2xsYWJwYWdlLzIwMjIyODk0NzY=
