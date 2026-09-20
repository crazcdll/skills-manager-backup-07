# capability-map.md — hotel-product-testdata 能力地图

> 本文件回答一个问题：**这个 Skill 现在具不具备某项能力？**
> 查询顺序：① 能力事实源声明 → ② 已支持能力清单 → ③ 明确不支持清单 → ④ 常见说法对照表 → ⑤ 都查不到时看「能力归属判定规则」。
> 编号口径：本 Skill 无独立 `scenarios/index.md`，场景清单以 `SKILL.md`「场景路由」表 + `references/workflows/w1~w9-*.md` 为单一事实来源。地图中的「场景编号」= workflow 编号（W1～W9），与 `references/workflows/` 目录下文件一一对应。
> 最后同步时间：2026-08-28（对齐《capability-map.md 建设规范 v0.2》，km.sankuai.com/collabpage/2775962365：新增能力事实源声明、3.3 缺口分类、2.3 叶子枚举 CLI 委托；能力内容仍对齐 2026-08-03 版本的事实）。

---

## 能力事实源声明（v0.2 规范第 0 节）

```YAML
capability_map_version: "0.2"

architecture:
  primary: workflow_orchestrator   # SKILL.md 场景路由 → w1~w9 工作流 → factory/ 脚本族；W4/W5 委托 zl-hotel-testdata

resolution_modes:
  - static_map        # 工作流文档（w1~w9）中的场景覆盖表
  - cli_schema        # factory/<域>/<脚本>.py 的 --show-schema / factory/<域>/schema.json
  - delegated_skill   # zl-hotel-testdata（直连产品）、zl-hotel-room-mapping（房型映射兜底）

sources_of_truth:
  stable_boundary:
    - capability-map.md              # 本文件
    - SKILL.md（场景路由表）
    - references/workflows/w1-create-fullday.md ～ w9-create-palletize-package.md
  leaf_capability:
    - "hotel_testdata_cli/factory/<域>/<脚本>.py --show-schema（全部 factory 脚本均支持）"
    - "hotel_testdata_cli/factory/<域>/schema.json（参数约束）"
    - "testdata-cli query-testdata list-tags --query-tab 1 --biz-line 20（数据池标签全集）"
  contract_docs:
    - references/pitfalls/{infra,inventory,rpc}.md
    - references/shared/enums.md（共用枚举）
    - references/goods/model.md（RPC 字段全量）

safe_probes:            # 仅允许无写入探测，不得为判断能力真伪而发起任何写入调用
  - "factory/<域>/<脚本>.py --help"
  - "factory/<域>/<脚本>.py --show-schema"
  - "factory/<域>/<脚本>.py --dry-run（仅创建类脚本，输出约束校验，不落库）"

verification_contract:
  minimum: dry_run    # 创建类操作先 --dry-run 确认「[约束校验] ✅ 通过」再正式执行；查询/审核类直接执行后回读
```

---

## 一、已支持能力清单

### 1. 商品构造（住宿·预付自建 / 直连组装）

| 能力名称 | 对应场景编号 | 关键入参 | 关键输出 | 备注 |
|---------|------------|---------|---------|------|
| 全日房构造（普通/免费取消/收费取消/不可取消） | W1 | partnerId+poiId+roomId+contractNo，cancelItemType/moveUpCancelDays/payCancelPeriodModels | goodsId（异步，等大象推送/轮询）；rpCancelModel 含对应取值；脚本自动串联上线(batchOnlineSwitch status=2)/开房设库存/缓存刷新 | 默认「当天18:00前免费取消、无早餐」 |
| 全日房-早餐规则（单早/双早/平日周末差异化） | W1 | rpBreakFastModel.normalRule.num（1/2）+ weekendRule | goodsId | — |
| 全日房-附近专享（3公里可见） | W1 | rpDisplayModel.normalRule.distanceRange=1 | goodsId | — |
| 全日房-现付担保/非担保 | W1 | paymentType=1/2，rpGuaranteeModel | goodsId | paymentType=0（预付，默认）不传 rpGuaranteeModel |
| 全日房-境外多人多价/多人同价 | W1 | priceSameTag（0/1）+ maxAdultAdmissibility + priceFactorInfos | goodsId | 境外专属；priceInfo 须传 null；需 W8 先切换 VPOI 价格模式 |
| 全日房-底价/卖价模式产品创建 | W1 | basePrice/salePrice + priceChangeMode 等 | goodsId | 价格模式需先在 W8 用工具928/合同侧切换 |
| 全日房绑定非房/礼包（rpServiceModel） | W1（依赖 W3） | 非房查询结果字段映射至 serviceModels | goodsId | 非房须先按 W3 创建+审核通过 |
| 钟点房构造（普通/自定义时长/不可取消/自定义接待时间） | W2 | typeLimitValue（1~23h）、receiveTimeStart/End、cancelItemType | goodsId（goodsType=2，typeLimitValue 生效）；rpBreakFastModel/rpSerialModel 固定 null | 仅支持境内，不支持境外钟点房、不支持收费取消、paymentType 固定0（预付） |
| 钟点房绑定非房/礼包 | W2（依赖 W3） | 同 W1 rpServiceModel 机制 | goodsId | 字段映射规则与 W1 一致 |
| 非房 xGoods 构造（单门店，餐饮/景点门票/玩乐一日游模板） | W3 | partnerId+poiId、--type catering\|scenic\|tour | xGoodsId（**同步**返回）；商品名≤20字符 | 不需要 contractNo/roomId（普通非房）；**不支持**批量门店逗号分隔/游客信息类型/境外（历史文档误标，代码从未支持，2026-08-03 已修正）；--type 枚举以 create-non-room.py --show-schema 实时探测为准 |
| 非房独立售卖（加购）构造（CRS-60） | W3 | `--sell-status 1` + 8 扩展字段：promotionText/displayOrder/contractNo/totalStock/marketPrice/salePrice/commissionRate/maxNumPerOrder | xGoodsId（basicInfoModel.sellStatus=1） | contractNo 仅支持预付(=2)/团购(=0)合同，禁止包销(=5)；stockModel 为顶层新模型（非 basicInfoModel 字段）；commissionRate 万分位整数；创建后不可绑定 goods/套餐/超团；vpoi 需在 metaId=1074 白名单内；已自动补齐价值凭证联动校验所需的 priceProofUrls；2026-08-03 已用 partnerId=4570381/poiId=1090269468135297 实测创建+审核通过（xGoodsId=2257281540） |
| 非房审核（通过/驳回） | W3 | xGoodsId+partnerId+shopId | 审核结果 | 直接 RPC `auditProduct`，无需 BPM/浏览器；无 --action 参数（历史文档误标，脚本本身不区分 pass/reject 参数） |
| 套餐构造-预付自建模式 | W4 | 关联 W1 全日房 goodsId + W3 审核通过的 xGoodsId | spuId（同步接口，创建即上线，无需额外审核） | — |
| 套餐构造-境外套餐 | W4 | 同上 + `--overseas` | spuId | — |
| 套餐构造-直连产品包装（落地/不落地） | W4（依赖 zl-hotel-testdata skill） | `--goods-source direct-land/direct-noland`，直连 goodsId | spuId | 直连产品需先由 zl-hotel-testdata skill 创建；`200013028` 报错需补调 zl-hotel-room-mapping（mode2） |
| 房转套餐（货盘规则上单，系统自动生成套餐） | W9 | 全日房(带非房)goodsId → CSV → S3 → 货盘规则 strategyId | spuId（由 queryGoods2SpuRecordByPage 查得） | 不需要 contractId，不走 create-package.py，无需手动审核 |
| 超团构造-非通兑（单店） | W5 | partnerId+单 poiId+专属全日房 goodsId | spuId（spuExchangeType=1）；autoPublish=true 自动上线 | 默认自动创建+审核绑定一条非房（可 --skip-xgoods / --xgoods-id 复用） |
| 超团构造-通兑（多店，≥2门店） | W5 | partnerId(entity-type=2)+≥2个 poiId+对应 goodsIds | spuId（spuExchangeType=0，poiId=null）；创建脚本自动串联 BPM+auditProduct 审核+上线+缓存刷新 | autoPublish=false |
| 超团构造-境外变体（非通兑/通兑） | W5 | 同上 + `--overseas` [--max-adult N] | spuId | 专属全日房走境外多人同价模式 |
| 超团构造-境内通兑直连超团 | W5（依赖 zl-hotel-testdata skill，编排5步） | partnerId(entity-type=2) + 直连商品 isSuperDeal=true | spuId | 全流程 Agent 自动编排：新建门店(W8路径D)→创建直连商品→查goodsId→建通兑超团→审核上线；直连商品超团需调两次 auditProduct |
| 超团加价日历（周末/节假日加价） | W5 | `--base-add-price`（数组，含 startDate/endDate/weekPrices） | spuId | 写入 SPU 顶层，不影响全日房价格；日期须落在入离日期范围内 |

### 2. 营销 / 缓存 / 审核 / 上下线运营操作

| 能力名称 | 对应场景编号 | 关键入参 | 关键输出 | 备注 |
|---------|------------|---------|---------|------|
| 营销报名-生意助手/全域通（一口价/折扣/混合） | W6 | mode（1新建报名/2已有产品）、configKey（notUpscale/upscaleFixed/upscaleDiscount/upscaleFixedDiscountMixed） | 报名结果（异步，大象推送） | 工具1037 |
| 缓存刷新（商品/SPU/门店/货盘级） | W6 | --op 1，product-id/spu-id/poi-id/rp-id 之一 | 刷新结果 | 工具1031 |
| BD 改价审核（通过/驳回） | W6 | --op 2，audit-status（2驳回/3通过） | 审核结果 | — |
| 商家改价审核（通过/驳回） | W6 | --op 3，audit-status | 审核结果 | 默认通过 |
| 商品上线/下线（batchOnlineSwitch） | W6 | partnerId+poiId+goodsIds+status（2上线/3下线） | 上下线结果 | 可批量传多个 goodsId |
| 商品详情查询（queryGoodsInfo） | W6 | partnerId+poiId+goodsIds，可选 --field | 商品详情 JSON | 支持多 goodsId、按字段过滤 |
| 非房/套餐/超团审核 | W3/W4/W9/W5 | 见各自 workflow | 审核结果 | 套餐/房转套餐无需额外审核；非通兑超团 autoPublish 自动审核；通兑超团需 BPM+auditProduct 两步 |

### 3. 房态 & 库存

| 能力名称 | 对应场景编号 | 关键入参 | 关键输出 | 备注 |
|---------|------------|---------|---------|------|
| 开房（可预订） | W7 | invSwitch=1 | 库存更新结果 | 全日房用 --day-room-ids，钟点房用 --hour-room-ids |
| 关房（不可预订） | W7 | invSwitch=0 | 库存更新结果 | — |
| 设置/修改库存余量（补库存） | W7 | limitChangeValue（默认299）、countType（1121首次/1520修改/1920不限量） | 库存更新结果 | 新建商品首次设库存必须 countType=1121 |
| 商品上线失败（缺库存）修复 | W1/W2 Step5 联动 W7 | 同上 | 重新上线成功 | 全日房/钟点房创建脚本失败时自动触发，也可手动执行 |

### 4. 基础实体构造与前置数据编排（W8）

| 能力名称 | 对应场景编号 | 关键入参 | 关键输出 | 备注 |
|---------|------------|---------|---------|------|
| 创建 POI（境内/境外） | W8 | city、overseas、category-id | poiId | 境外默认 category-id=387 |
| 门店私海认领 | W8 | poiId | 认领结果（empId=2196240） | 每个新 poiId 必做，且须在绑定门店前完成 |
| 供应商绑定门店 | W8 | poiId+partnerId | 绑定结果 | — |
| 创建供应商（境内自采/境外/境内女娲） | W8 | poiId、partner-type（2/3/9）、entity-type（0集团/2单体）、currency | partnerId+platformContractId | 异步约1分钟就绪；通兑超团要求 entity-type=2 |
| 数据池查询供应商/门店/合同 | W8 | query-tab=1、biz-line=20、tags（107境内外/117单体酒店/108财务类型/115合同类型/105币种/226价格模式） | 候选 partnerId/poiId/contractNo 列表 | 两阶段查询（先查自己再查全量）；结果必须先展示等待用户确认 |
| 数据池写入（新建供应商后登记复用） | W8 | origin-customer-id+contract-id+poi-id+occupier | 写入结果 | 商品创建成功或失败后均需执行 |
| 查询合同（按 partnerId / platformContractId） | W8 | partnerId 或 platformContractId | contractNo（字符串） | 两种查询方式，新建后推荐用 platformContractId 方式更精准 |
| 新建合同 | W8 | partnerId | contractNo+platformContractId | 数据池/已有供应商查无合同时执行 |
| 创建房型（逻辑房型） | W8 | partnerId+poiId、room-type、overseas、capacity、room-area、window-type | roomInfoId+realRoomId | 全日房/钟点房必做 |
| 住宿门店资质添加（工具476） | W8 | poiId | 资质写入结果 | 商品上线需资质时执行，与工具498独立 |
| 供应商门店资质审核（工具498） | W8 | poiId | 审核通过结果 | 与工具476独立 |
| 价格模式切换（境内底价/卖价、境外底价/卖价） | W8 | contract-id 或 (overseas+partnerId+poiId)、mode | 切换结果 | 境内定义在合同，境外定义在 VPOI；须在创建产品前完成 |
| ID 互查（partnerId↔platformCustomerId、platformContractId↔contractNumber） | W8 | 对应 ID | 转换结果 | 排查辅助工具 |
| 四种前置数据路径自动编排（完全空白/仅poiId/仅partnerId/两者都有） | W8 路径A/B/C/D | 用户已持有的 ID 情况 | 补齐后的完整 ID 集合 | 境外场景额外要求两端均为境外实体/新建时加 --overseas |

---

## 二、明确不支持清单

| 能力 | 不支持原因 | 反馈路径 |
|------|-----------|---------|
| 非酒店类商品构造（到综团购/预订/代金券等） | 业务上不该由本方向承接，核心实体是到综商品，不是酒店住宿商品 | 转介 general-product-testdata skill |
| 直连产品的创建/保鲜/查询/POI-房型映射本身 | 本 Skill 仅"消费"直连产品 goodsId（在套餐 W4/超团 W5 中组装），不负责直连产品全生命周期构造 | 转介 zl-hotel-testdata skill |
| 境外钟点房 | 业务上不存在此场景（钟点房仅境内售卖），非技术限制 | 无需反馈，属正常业务边界 |
| 钟点房收费取消（payCancelPeriodModels） | 钟点房接口约束：传入即报错，仅全日房支持收费取消 | 反馈给 Skill 维护者评估是否有业务诉求 |
| 钟点房现付（担保/非担保） | 钟点房 paymentType 固定为0（预付），接口层面不支持 1/2 | 反馈给 Skill 维护者评估是否有业务诉求 |
| 通兑超团绑定酒店集团主体（entity-type=0） | 接口约束：通兑超团 partnerId 必须是 entity-type=2（单体酒店） | 反馈给 Skill 维护者评估排期 |
| 跨门店库存联动 / 跨供应商批量操作 | 现有原子工具均按单 partnerId+单 poiId（或超团通兑的多 poiId 白名单模式）设计，未做跨供应商联动编排 | 反馈给 Skill 维护者评估排期 |
| 商家账号/合同资质/结算配置等商家侧对象的独立管理（非本 Skill 上单前置） | 核心实体是商家侧账号/资金/协议对象，不是商品；本 Skill 仅做上单必需的最小前置（POI/供应商/合同/房型） | 转介 hotel-merchant-data skill |
| 会员等级/积分/权益券等用户维度数据初始化 | 核心实体是用户会员体系，不是商品 | 转介 hotel-member-points-setup skill |
| 营销活动配置本身的创建（活动规则/立减/满减等） | 核心实体是营销活动配置对象，本 Skill 仅做"报名"（把商品挂到已有活动/工具1037），不创建活动规则本身 | 转介对应营销方向 Skill |
| 报价服务查询链路验证（queryGoods/queryPoi/queryPhysicalRoom/tradeQueryGoods 等 C 端接口调用与断言） | 核心职责是"造数据"，不是"验证 C 端可见性/断言报价结果"，两者边界不同 | 转介 hotel-goodsquery-autotest 或 hotel-product-visibility-troubleshoot skill |
| ptest 环境数据构造 | 当前实现固定面向线下测试环境（test），未适配 ptest 环境专属数据源/接口地址 | 反馈给 Skill 维护者评估排期 |

---

## 三、技术概念 / 接口映射表

| 常见业务表述 | 对应本 Skill 内部叫法 | 对应场景编号 |
|-------------|---------------------|------------|
| 全参数产品 / 酒店RPC上单 / MeGoodsFacade / batchCreateGoods | 全日房构造 或 钟点房构造 | W1 / W2 |
| 全日房RPC | 全日房构造 | W1 |
| 钟点房RPC | 钟点房构造 | W2 |
| xGoods / 礼包（作为独立产品创建时） | 非房构造 | W3 |
| xGoods审核 / 礼包审核 | 非房审核 | W3 |
| 非房商品化 / 非房独立售卖 / 可加购非房 / 非房加购 / sellStatus | 非房独立售卖（加购）构造 | W3 |
| 房转套餐 / 货盘规则上单 | 房转套餐（货盘规则上单） | W9 |
| 通兑 / 多店超团 | 超团构造-通兑 | W5 |
| 非通兑 / 单店超团 | 超团构造-非通兑 | W5 |
| 直连通兑超团 / 直连商品做通兑 | 超团构造-境内通兑直连超团 | W5 |
| 工具1037 | 营销报名 | W6 |
| 工具1031 | 缓存刷新/改价审核 | W6 |
| batchOnlineSwitch / 发布上线 / 恢复上线 | 商品上线/下线 | W6 |
| 库存不足上线失败 | 商品上线失败（缺库存）修复 | W7（联动 W1/W2） |
| batchUpdateInventory / 补库存 / 设置库存余量 / 修改房态 | 开房/关房/设置库存余量 | W7 |
| 私海认领 / claim poi | 门店私海认领 | W8 |
| bind partner poi / 绑定门店 | 供应商绑定门店 | W8 |
| 工具49 | 创建供应商 | W8 |
| 工具476 | 住宿门店资质添加 | W8 |
| 工具498 / audit poi qualification / 资质审核通过 | 供应商门店资质审核 | W8 |
| 工具906 | 需人工确认具体指向（历史触发词保留，当前 workflow 文件未见对应脚本编号说明） | 待确认 |
| 工具928 / 切换底价 / 切换卖价 / 底价模式 / 卖价模式 / switch price mode | 价格模式切换 | W8 |
| priceSameTag / priceFactorInfos / 多人多价 / 多人同价 | 境外全日房多人多价能力 | W1 |
| 在指定客户下构造商品 / 指定partnerId构造 / 指定门店构造商品 | W8 路径B/C/D（已有 partnerId/poiId 场景） | W8 |

> 💡 **说法对照表补录说明**：本表仅覆盖 SKILL.md 触发词与 workflow 内容能明确对应的条目。表中"工具906"因目前 workflow 文件全文未出现该编号的脚本映射说明，暂标记为待确认，不代表不支持——按下方「能力归属判定规则」第 2 条处理，不能直接判否，需先向 Skill 维护者确认后回填此表。

---

## 四、能力归属判定规则

### 4.1 静态归属标准（这事归不归本 Skill 管）

判定为**「归本 Skill 管，只是场景还没写」**的标准（满足任一即可）：
- 需求的最终产出物核心实体是**酒店住宿商品**（goodsId/xGoodsId/spuId 为主键），且商品来源是**预付自建**或**直连产品的组装消费**（非直连产品本身的创建）
- 需求围绕该商品的**上单必需前置实体**（POI、供应商、合同、逻辑房型）本身的构造/绑定/资质
- 需求围绕已创建商品的**运营态操作**：营销报名、缓存刷新、改价审核、上下线、房态库存
- 需求描述中出现的字段/枚举明显是 `MeGoodsFacade` / `MeResourceFacade` / `MeInventoryFacade` / `HubStrategyFacade`（`com.sankuai.hotel.biz.platform` / `com.sankuai.hotelcrs.supply.hub`）家族接口的参数

判定为**「不归本 Skill 管，应转介其他团队」**的标准：
- 产出物核心实体是**到综/零售类商品**（非住宿）→ 转介 general-product-testdata
- 产出物核心实体是**直连产品自身的创建/保鲜/映射**（而非在套餐/超团中复用直连 goodsId）→ 转介 zl-hotel-testdata
- 产出物核心实体是**商家账号/资金/合同签约流程本身**（非上单最小前置）→ 转介 hotel-merchant-data
- 产出物核心实体是**用户会员等级/积分/权益**→ 转介 hotel-member-points-setup
- 产出物核心实体是**营销活动规则配置本身**（非报名动作）→ 转介对应营销方向 Skill
- 需求诉求是**验证/断言 C 端报价可见性结果**而非构造数据 → 转介 hotel-goodsquery-autotest / hotel-product-visibility-troubleshoot

### 4.2 新增信号识别标准（这次变化算不算需要迭代）

当需求字面出现以下表述时，先定位该表述对应的具体接口字段/枚举/状态机取值，再对照「一、已支持能力清单」核对是否已在覆盖范围内，不能仅因为"实体归本方向管"就直接判定为已支持：

| 字面信号 | 需要核对的颗粒度 | 核对方法 |
|---------|----------------|---------|
| "新增取消政策类型" / "新增早餐规则" | `rpCancelModel`/`rpBreakFastModel` 的字段取值是否超出 W1 已列举的 cancelItemType/payCancelPeriodModels/weekendRule 组合范围 | 查 W1 workflow 表格 + `factory/fullday/schema.json` |
| "新增商品类型"（如新的酒店品类） | 是否超出 goodsType∈{1全日房,2钟点房} 或超出 W3非房/W4套餐/W5超团/W9房转套餐 已覆盖的产品形态 | 查 `references/shared/enums.md` goodsType 枚举 |
| "新增境外场景" / "新增多人价格档位" | 是否超出 priceSameTag∈{0,1} + maxAdultAdmissibility 已支持的 1~6 档范围，或涉及境内从未支持的字段 | 查 W1「境外多人多价」章节 |
| "新增审核类型" / "审核流程变化" | 是否超出 W3(非房)/W4(套餐)/W5(超团非通兑autoPublish/通兑BPM+auditProduct)/W9(房转套餐无需审核) 已覆盖的审核路径 | 查各 workflow 审核章节 |
| "新增供应商主体类型" / "新增合同类型" | 是否超出 partner-type∈{2,3,9}、entity-type∈{0,2} 已支持范围 | 查 W8 create-partner.py 参数说明 |
| "新增营销报名玩法" | 是否超出 configKey∈{notUpscale, upscaleFixed, upscaleDiscount, upscaleFixedDiscountMixed} 枚举 | 查 W6「营销报名」章节 |
| "新增库存操作类型" | 是否超出 countType∈{1121,1520,1920}、invSwitch∈{-1,0,1} 已支持范围 | 查 W7「countType 选择」章节 |
| "新增价格模式" | 是否超出境内底价/卖价（合同维度）、境外底价/卖价（VPOI维度）四种组合 | 查 W8「价格模式切换」章节 |

若该取值/字段**不在**已支持场景的枚举范围内，且**不属于**「二、明确不支持清单」中已列出的项，则视为**潜在缺口，标记为待评估**，反馈给 Skill 维护者（不能直接归为"已支持"或"不支持"）。

### 4.3 缺口分类规则（v0.2 规范 3.3：发现入口 ≠ 已支持）

本 Skill 的事实源包含 CLI schema（--show-schema / schema.json）和 `--set` 任意字段透传。**仅能发现命令、接口或可透传字段，不得直接判定为"已支持"**，必须继续核实参数契约、前置资源、状态流转、后置回读是否都已覆盖。缺口分五类，前四类优先补文档契约与编排，不要重复建设底层能力：

| 缺口类型 | 判定特征 | 处置方式 |
|---------|---------|--------|
| 能力发现文档缺口 | 叶子命令/API 已存在，但 workflow/地图未写明如何发现或正确使用 | 补 workflow/地图条目，当天同步本地图 |
| 参数契约缺口 | 入口存在，但字段枚举、联动约束、默认值或参数模型不清楚 | 用 safe_probes 探测 schema 后补契约文档 |
| 工作流编排缺口 | 原子操作存在，但前后置步骤或委托 Skill 编排缺失 | 补 workflow 编排步骤 |
| 验证契约缺口 | 能发起操作但无法可靠回读核心状态（如造完商品无法确认 spuId/goodsId 状态） | 补回读手段（queryGoodsInfo / queryGoods2SpuRecordByPage 等） |
| 真实能力缺口 | 底层命令、接口、模板或依赖本身不存在 | 反馈 Skill 维护者评估排期，不得自行硬编码参数绕过（见 SKILL.md IRON LAW） |

> ⚠️ 特别提醒：`--set` 可透传任意 RPC 字段 ≠ 该字段对应的业务场景已支持。用 `--set` 透传后必须按 verification_contract 回读验证产出物核心字段/状态，否则只能判为"参数契约缺口/需人工确认"。

### 4.4 叶子枚举 CLI 委托（v0.2 规范 2.3）

对以下叶子枚举，本地图不硬编码维护枚举个数清单，**委托给 CLI 作为事实源**：CLI choices 级枚举新增/下线视为事实源自更新，**不触发本地图同步**：

- 非房 `--type` 模板枚举（catering/scenic/tour…）→ 以 `create-non-room.py --show-schema` 实时探测为准
- 营销报名 `--config-key` 枚举 → 以 `enroll-marketing.py --show-schema` 实时探测为准
- 库存 `--count-type` / `--inv-switch` 枚举 → 以 `update-inventory.py --show-schema` 实时探测为准
- 数据池 tags 枚举 → 以 `testdata-cli query-testdata list-tags` 实时探测为准

**委托前提（均满足）**：①顶部 `sources_of_truth.leaf_capability` 已声明对应 CLI 探测入口；②本地图对应能力行/4.2 表格中的枚举描述为动态表述（已标注"以 --show-schema 实时探测为准"），未硬编码具体枚举清单；③CLI 未收录枚举时的兜底通道为 `--set` 直传（须有后端已支持的代码级证据）+ 构造后按 verification_contract 回读验证，CLI 收录后兜底通道自动作废。

**边界**：本委托只豁免枚举级小迭代的地图同步。命令族级（新增 factory 脚本）、场景级（新增业务场景行）、依赖级（新增前置依赖或回读方式）变更，仍按下方「附：一致性校验规则」当天同步地图。CLI 能发现枚举入口，不等于该业务场景的前置数据、参数契约、编排、验证都已覆盖（4.3 仍适用），首次执行仍需走完整核对。

---

## 附：一致性校验规则（v0.2 规范 2.1/2.2）

本 Skill 无独立 `check_capability_map.py` 校验脚本，按顶部声明的架构（workflow_orchestrator）执行人工/CI 校验。**新增/下线 workflow、factory 脚本、schema、委托关系时，当次提交内同步更新本文件对应条目**（不要攒着以后补），并逐项检查：

1. **static_map（场景编号一致性）**：`references/workflows/` 下每个 `w*.md` 文件在「一、已支持能力清单」中有对应条目；「一」中引用的每个 W 编号在 `references/workflows/` 下真实存在对应文件
2. **cli_schema（命令族/schema 存在性）**：「一」中引用的每个 `factory/<域>/<脚本>.py` 真实存在于 `hotel_testdata_cli/factory/`，且 `--help` 可探测到；引用的 schema.json 真实存在
3. **delegated_skill（委托关系一致性）**：引用的委托 Skill（zl-hotel-testdata、zl-hotel-room-mapping）在当前环境可被定位
4. **contract_docs（契约文档存在性）**：顶部 `sources_of_truth` 声明的 pitfalls/enums/model 文档真实存在
5. 任一不一致 → 阻断提交，先修事实源或本地图

> 建议后续将上述检查固化为 pre-commit hook 或 PR checklist（规范 2.2）。

---

## 附录：开发者自查清单（v0.2 规范附录 A）

P0 必查：

- [x] 地图分三段：已支持 / 不支持 / 常见说法对照（不是场景清单摘要版）
- [x] 顶部有能力事实源声明：架构类型、解析方式、事实源、安全探测、验证契约
- [x] 已支持清单里的能力定位符（W 编号 / 命令 / 委托）能和声明的事实源对上，按架构跑了对应校验（见「附：一致性校验规则」）
- [x] 归属判定规则里除静态实体归属标准外，还有"新增信号识别标准"（4.2）与"缺口分类规则"（4.3）
- [x] 发现入口、字段透传不直接写成已支持，已按发现/参数/编排/验证/真实缺口五类分类核实
- [x] 用真实需求手动测过一遍，不翻完整原文、只靠地图和声明的 safe_probes 就能给出结论

P1 建议：

- [x] 不支持清单每条都有原因和反馈路径
- [x] 改场景/命令/接口/工作流和改地图在同一次提交里完成

P2 加分：

- [x] 常见说法对照表跟着真实看漏的案例持续补（如"工具906"待确认条目）

