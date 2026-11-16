# W10：已有商品特殊状态变更（废除/审核/关房/满房）

## 场景覆盖

| 用户描述 | `--state` | 行为 |
|---------|-----------|------|
| 不在线 / 未上线的商品 | `offline` | 对**已上线**商品调用 `batchOnlineSwitch(status=3)` 下线，最终 `goodsStatus=3`。**可逆**（之后可通过 `online-switch.py --status 2` 重新上线），与 `abolish` 的区别是不会调用 `destroyGoods` |
| 废除 / 已废除的商品 | `abolish` | 自动先下线（`batchOnlineSwitch status=3`）再调用 `destroyGoods`，最终 `goodsStatus=8`。**不可逆操作**，若下线触发人工审批（PrepayGoodsOfflineAuditProcess）会失败并提示手动命令，不做重试 |
| 审核中 / 待审核的商品（商家改价） | `merchant-auditing` | 对**已上线**商品调用 `PlatformMeGoodsFacade#updatePriceV2` 大幅提价（涨到当前售价的5倍，需传 `--current-price-yuan`）触发涨跌幅审核，商品进入「待审核」状态。**按 `--start-date`/`--end-date` 指定的日期段进入审核**（非整商品，不传默认仅当天）。不做任何审核动作，就此停住 |
| 审核驳回 / 被驳回的商品（商家改价） | `merchant-audit-rejected` | 在 `merchant-auditing` 基础上，改价触发待审核后，额外主动调用商家改价审核驳回（`operationType=3, auditStatus=2`） |
| 审核中 / 待审核的商品（BD改价） | `BD-auditing` | 对**已上线**商品以 **BD 身份**（真实 SSO 登录换票，默认使用全局固定测试账号 `crstest`，已实测验证通过，无需手动传参）调用 `PlatformMeGoodsFacade#updatePriceV2` 大幅提价（涨到当前售价的5倍，需传 `--current-price-yuan`）触发 BD 改价审核，商品进入「待审核」状态。⚠️ 是否也像商家一样按日期段进审、还是整商品进审待重新验证（旧结论基于已证伪的方案）。不做任何审核动作，就此停住 |
| 审核驳回 / 被驳回的商品（BD改价） | `BD-audit-rejected` | 在 `BD-auditing` 基础上，改价触发待审核后，额外主动调用 BD 改价审核驳回（`operationType=2, auditStatus=2`） |
| B端关房（房型维度） | `b-closed` | 对已上线商品调用 `batchUpdateInventory`（`changeType=1`）将指定日期范围设置为关房（`invSwitch=0`），**同时保留非零库存余量**（`limitChangeValue` 默认 299，可用 `--limit-change-value` 自定义），体现「有库存但关房不可订」，需传 `--room-id --goods-type` |
| B端满房（房型维度） | `b-full` | 对已上线商品调用 `batchUpdateInventory`（`changeType=1`）将指定日期范围**开房**（`invSwitch=1`）且库存余量置0（`limitChangeValue=0`），体现「开房可订但库存耗尽」，需传 `--room-id --goods-type` |
| B端关房（产品维度） | `b-closed-goods` | 与 `b-closed` 效果相同，但通过 `batchUpdateInventory`（`changeType=2` + `goodsIdList`）**直接按 `goodsId` 操作**，不需要 `--room-id`/`--goods-type`。⚠️ **仅当门店已通过 `factory/inventory/change-room-status-dimension.py` 切换为「产品维度」后才可用**，未切换维度的门店调用大概率会被后端拒绝或不生效 |
| B端满房（产品维度） | `b-full-goods` | 与 `b-full` 效果相同，但通过 `batchUpdateInventory`（`changeType=2` + `goodsIdList`）**直接按 `goodsId` 操作**，不需要 `--room-id`/`--goods-type`。⚠️ 同上，仅门店已切换为产品维度后可用 |

> ⚠️ **仅当用户明确要求**构造"不在线""废除""审核中""审核驳回""关房""满房"等特定状态的商品时才使用本 workflow；普通建品需求走 W1（全日房）/ W2（钟点房）的默认流程即可，不要主动做这一步。

---

## 与建品流程的关系（完全解耦）

`create-fullday.py` / `create-hourly.py` 只负责**建品 + 正常上线**，不感知任何特殊状态（旧的 `--goods-state` 参数已废弃并移除）。特殊状态统一通过本 workflow 描述的独立脚本 `factory/ops/goods-state.py` 对**已有商品**操作，分两步：

1. **先建品**：按 W1（全日房）或 W2（钟点房）走完整建品+上线流程，拿到 `goodsId`
2. **再变更状态**：用 `factory/ops/goods-state.py --goods-id <goodsId> --state <目标状态>` 对该商品设置目标状态

内部实现位于 `factory/goods-state/`，按状态类型拆分为三个子模块，互不干扰、独立维护：
- `goods_product_ops.py` — 产品状态（`offline` / `abolish`）
- `goods_price_ops.py` — 价格状态（`merchant-auditing` / `merchant-audit-rejected` / `BD-*`）
- `goods_inventory_ops.py` — 库存/房态状态（`b-closed` / `b-full` 房型维度，`b-closed-goods` / `b-full-goods` 产品维度）

无需了解上述实现细节，直接调用 `factory/ops/goods-state.py` 即可；该脚本会根据 `--state` 自动分发到对应子模块。

---

## 前置条件

必须已有一个**已上线**的商品（全日房或钟点房均可），并知道其 `goodsId`。若还没有商品，先按 W1/W2 建品。

---

## 核心命令

```bash
python3 factory/ops/goods-state.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-id <goodsId> \
  --state <目标状态> \
  [--current-price-yuan <元>] \    # merchant-auditing / merchant-audit-rejected / BD-auditing / BD-audit-rejected 用，不传则按 --goods-type 取默认值
  [--bd-sso-user <BD员工SSO账号>] \      # BD-auditing / BD-audit-rejected 可选，不传默认用全局固定测试账号 crstest（已实测）
  [--bd-sso-password <BD员工SSO密码>] \  # 可选，不传默认 Ceshi123
  [--bd-client-id <SSO客户端ID>] \        # 可选，不传默认 hotel_sc
  [--bd-client-secret <SSO客户端密钥>] \  # 可选，不传用默认值
  [--audit-reason <审核理由>] \    # BD-auditing / BD-audit-rejected 可选，不传默认"测试数据构造"
  [--room-id <roomId>] \           # b-closed / b-full 必填（b-closed-goods / b-full-goods 不需要，直接用 --goods-id）
  [--goods-type 1|2] \             # 1=全日房（默认） 2=钟点房；影响默认售价 & 房态接口选择（仅房型维度状态生效）
  [--start-date <YYYY-MM-DD>] \    # b-closed/b-full/b-closed-goods/b-full-goods：库存/房态起始日期，默认今天
                                   # merchant-*/BD-*：改价生效起始日期，默认今天
                                   # （⚠️ 商家审核已实测按此日期段进入审核，BD 审核范围待重新验证）
  [--end-date <YYYY-MM-DD>] \      # b-closed系/b-full系：默认两年后；merchant-*/BD-*：默认=--start-date
  [--limit-change-value <int>] \  # 仅 b-closed/b-closed-goods 生效，关房期间保留的库存余量，默认299（必须>0）；
                                   # b-full系 库存固定为0，不受此参数影响
  [--swimlane <泳道名>]
```

> 查看完整参数说明：`python3 factory/ops/goods-state.py --show-schema`

---

## 常用场景示例

### 场景一：下线（不在线，可逆）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550589 --poi-id 1085927256096396 \
  --goods-id <goodsId> --state offline
```

### 场景二：废除商品（不可逆）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550589 --poi-id 1085927256096396 \
  --goods-id <goodsId> --state abolish
```

### 场景三：触发商家价格审核（全日房，当前售价200元，仅当天进入审核）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550589 --poi-id 1085927256096396 \
  --goods-id <goodsId> --state merchant-auditing \
  --current-price-yuan 200.0
```

### 场景四：指定日期段触发商家价格审核（仅 2026-09-01~2026-09-05 这段日期进入审核）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550589 --poi-id 1085927256096396 \
  --goods-id <goodsId> --state merchant-auditing \
  --current-price-yuan 200.0 --start-date 2026-09-01 --end-date 2026-09-05
```

> 商家改价审核是按日期段进入审核的（非整商品），不传 `--start-date`/`--end-date` 时默认仅当天。

### 场景五：触发商家价格审核后驳回（钟点房，当前售价80元）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550100 --poi-id 1090235108219575 \
  --goods-id <goodsId> --state merchant-audit-rejected \
  --current-price-yuan 80.0 --goods-type 2
```

### 场景六：触发 BD 价格审核（全日房，当前售价200元，默认 BD 测试账号）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550589 --poi-id 1085927256096396 \
  --goods-id <goodsId> --state BD-auditing \
  --current-price-yuan 200.0 --audit-reason "测试数据构造"
```

> 不传 `--bd-sso-user`/`--bd-sso-password` 时默认使用全局固定测试账号 `crstest`（密码 `Ceshi123`，client-id `hotel_sc`），2026-08-19 已对 `partnerId=4576342` 实测验证通过（`updatePriceV2` 返回 `code=10000`）。

### 场景七：触发 BD 价格审核后驳回（钟点房，当前售价80元）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550100 --poi-id 1090235108219575 \
  --goods-id <goodsId> --state BD-audit-rejected \
  --current-price-yuan 80.0 --goods-type 2 --audit-reason "测试数据构造"
```

> ✅ **BD 身份已内置全局固定测试账号 `crstest`**（参考 hotel-crs 自动化仓库 `LoginUtils.getBDHeaderMap()` + `env.properties`），与商家身份不同——**BD 不按 `partnerId` 绑定权限，是全局通用测试身份**，无需手动传 `--bd-sso-user`/`--bd-sso-password`。若需换用其他 BD 账号可显式传这两个参数覆盖，可选传 `--bd-client-id`/`--bd-client-secret`（SSO 客户端参数，不传用默认值）。**2026-08-19 之前的旧实现曾提供过编造的默认 BD 账号（id=2111140/login="hotel_bd_qa"），已实测证伪不生效，已彻底移除**。
>
> ⚠️ `BD-auditing`/`BD-audit-rejected` 也支持传 `--start-date`/`--end-date`，但是否像商家审核一样按日期段进审、还是旧方案下观察到的“整商品进审”，待重新验证（旧结论基于已证伪的 Thrift 伪造身份方案，不一定仍然成立）。

### 场景八：B端关房（全日房用 `--goods-type 1`，库存余量默认保留299）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550589 --poi-id 1085927256096396 \
  --goods-id <goodsId> --state b-closed \
  --room-id 77671480 --goods-type 1
```

> 需自定义保留的库存余量，可额外传 `--limit-change-value 100` 等非零值。

### 场景九：B端满房（钟点房用 `--goods-type 2`，库存固定为0）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550100 --poi-id 1090235108219575 \
  --goods-id <goodsId> --state b-full \
  --room-id 12345 --goods-type 2
```

### 场景十一：产品维度 B端关房（需门店已切换为产品维度）

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4576342 --poi-id 1090269458133536 \
  --goods-id <goodsId> --state b-closed-goods
```

> 不需要 `--room-id`/`--goods-type`，直接按 `--goods-id` 操作。需先确认该门店已通过
> `factory/inventory/change-room-status-dimension.py` 切换为产品维度，否则调用大概率会被后端拒绝或不生效。

### 场景十二：产品维度 B端满房

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4576342 --poi-id 1090269458133536 \
  --goods-id <goodsId> --state b-full-goods
```

### 场景十三：泳道支持

```bash
python3 factory/ops/goods-state.py \
  --partner-id 4550589 --poi-id 1085927256096396 \
  --goods-id <goodsId> --state abolish \
  --swimlane user-zhangsan
```

---

## ⚠️ 执行完 b-closed / b-full 后，必须向用户小结「价格 / 库存 / 房态」三个维度的最终状态

`b-closed`/`b-full` 传给 `batchUpdateInventory` 的参数（`--room-id`/`--goods-type`/`--start-date`/`--end-date`/`--limit-change-value`）就是这次写入的权威结果——接口调用成功即代表服务端已按这些入参生效，**不需要额外发起查询接口去"验证"**，脚本执行时打印的 `✅ ... 成功` 信息已经包含了全部关键字段。

但脚本的 print 输出只是原始日志，**不能直接甩给用户就完事**，agent 必须提炼成结构化小结，逐一说清楚三个维度，尤其是不要漏掉「价格」这一条（因为 `b-closed`/`b-full` 本身完全不涉及改价，很容易被遗漏）：

| 维度 | 该说明什么 | 从哪里来 |
|------|-----------|---------|
| **价格** | 售价维持商品原有售价不变（`b-closed`/`b-full` 只操作库存/房态接口，不调用 `updatePriceV2`，不会改价） | 若商品此前处于 `merchant-auditing` 等价格状态，需一并提醒用户价格状态未受影响 |
| **库存** | 库存余量的具体数值（`b-closed`→`--limit-change-value` 的值，默认299；`b-full`→固定0）+ 生效的日期范围 | 命令行入参 `--limit-change-value`、`--start-date`/`--end-date`（脚本内部会补全默认值，回复用户时用补全后的实际值，不要用户传的空值） |
| **房态** | `invSwitch` 的最终值（`b-closed`→0关房；`b-full`→1开房）+ 房型ID + 全日房/钟点房类型 | 命令行入参 `--room-id`/`--goods-type`，及 `--state` 本身 |

回复用户的小结建议采用如下结构（可直接套用）：

```
商品 <goodsId> 已完成「B端关房/满房」状态构造：
- 价格：维持原售价不变（未触发改价）
- 库存：日期范围 <start_date>~<end_date> 内，库存余量=<limit_change_value>
- 房态：<invSwitch=0关房 / invSwitch=1开房>，房型ID=<room_id>（<全日房/钟点房>）
```

> 若脚本执行失败（`❌`），要如实告诉用户失败原因和打印出的手动补救命令，不要编造"已成功"的状态小结。

> ⚠️ **`b-closed`/`b-full`（房型维度）与 `b-closed-goods`/`b-full-goods`（产品维度）必须与门店
> 当前的房态管理维度匹配**：
> - 门店默认是"房型维度"，应使用 `b-closed`/`b-full`（传 `--room-id --goods-type`）。
> - 门店若已通过 `factory/inventory/change-room-status-dimension.py` 切换为"产品维度"
>   （`ROOM_DIMENSION_CHANGE_SUCCESS`），则**必须**改用 `b-closed-goods`/`b-full-goods`
>   （只传 `--goods-id`，不传 `--room-id`），继续用房型维度状态会被后端拒绝或不生效。
> - 执行前如不确定门店当前维度，建议先向用户确认，避免选错 state（详见
>   `w7-inventory-ops.md` 的"切换房态管理维度"一节）。

---

## 关键约束与方案依据

> **审核方案依据（2026-08-06 真实抓包 + 实测）**：审核只能通过**"对已上线商品大幅改价"**触发（`updatePriceV2`），而不是"创建时设置极高售价再尝试上线"（旧方案，已废弃，未经验证过能触发）。全日房与钟点房均已实测验证 `merchant-auditing`/`merchant-audit-rejected` 全流程可用。

> ⚠️⚠️⚠️ **重要教训（2026-08-19 修复，务必知悉）**：`updatePriceV2` 的身份判断实际由**网关根据登录 Cookie 在服务端内部构造**。早期版本曾直调 Thrift 接口、手工拼一个 `PlatformOrigin` 参数来冒充商家/BD 身份，但真实调用链路是「前端 → HTTP 网关 → 网关解析登录 Cookie → 内部转换为 `PlatformOrigin` → 转发给 Thrift 方法」，Thrift 直调完全绕开了网关的身份解析逻辑，服务端收到的伪造 `PlatformOrigin` 不完整、不真实，导致身份判断落入错误分支——**商家身份被误判走了 BD/整商品审核逻辑，编造的 BD 测试账号又因未在权限系统登记而完全不生效**（用户实测反馈：`merchant-auditing` 触发出的商品进了"BD审核+整商品"，`BD-auditing` 完全没生效，两个分支现象恰好对调）。
>
> 现已改为**「`tdm-cli` 真实登录换票 + HTTP 网关直连调用」**，不再直调 Thrift、不再传 `PlatformOrigin`（网关会忽略甚至拒绝该字段，身份完全依据登录 Cookie）：
> - **商家身份**：`tdm token blogin -u <partnerId> -p Ceshi123 -s lvyou` 换取 `bsid`，拼 `Cookie: mebsid=<bsid>` + `logintype: Epassport`，POST 到 `https://me.hotel.test.sankuai.com/api/gw/v1/product/price/updatePriceV2`。**已用真实供应商 4574857/门店 1090269458119393 实测通过（`code=10000`）**。
> - **BD 身份**：同样改走 HTTP 网关 + `tdm token sso` 换取 `messoid`。⚠️ 与商家身份不同，**BD 是全局固定测试账号，不按 `partnerId` 绑定权限**（参考 hotel-crs 自动化仓库 `LoginUtils.getBDHeaderMap()` + `SSOUtil.getSSOId("ME","ME")` + `env.properties`：`ME_SSO_USER=crstest` / `ME_SSO_PASSWORD=Ceshi123` / `ME_SSO_CLIENT_ID=hotel_sc` / `ME_SSO_CLIENT_SECRET=7d53c92b32a0fc914c30e1740b3fc774`）。**已设为脚本默认值，调用方无需再手动传 `--bd-sso-user`/`--bd-sso-password`**，2026-08-19 已对 partnerId=4576342/goodsId=600005953325 实测验证通过（`code=10000`）。旧版编造的默认 BD 账号（`id=2111140`/`login="hotel_bd_qa"`）已被证伪并彻底移除。

- `updatePriceV2` 调用时的身份完全由**登录 Cookie**（而非请求体字段）决定走哪条审核链路：
  - **商家身份**（`merchant-auditing`/`merchant-audit-rejected`）：`Cookie: mebsid=<真实商家登录换票>`，`logintype: Epassport`，走 `EBOriginStrategy`（已实测验证）。
  - **BD 身份**（`BD-auditing`/`BD-audit-rejected`）：`Cookie: messoid=<真实BD SSO登录换票>`，`logintype: SSO`，默认使用全局固定测试账号 `crstest`（已实测验证通过）。
- **审核范围差异（商家 vs BD）**：`updatePriceV2` 的 `calcPriceUnifiedDateModel.dates` 字段控制本次改价生效的日期范围，可通过 `--start-date`/`--end-date` 自由指定（不传默认仅当天）：
  - **商家改价审核**：服务端按此日期段判断并进入审核（非整商品），因此可用来构造"部分日期审核中"的测试数据。
  - **BD 改价审核**：是否也按日期段进审、还是旧方案时期观察到的"整商品进审"，待用本次修复后的真实 BD 账号重新验证（旧结论基于已证伪的 Thrift 伪造身份方案，不一定仍然成立）。
- 请求体关键参数按身份区分（已在 `interface/ops/interface.py#call_update_price_v2` 的 `identity` 分支中固定好，无需手动传）：
  - 商家身份：`goodsList[].priceRecordWay=8`，`priceRecordWayList=[8,9]`，`ratioConfig.ratioType=2`，`extendParam={}`。
  - BD 身份：`goodsList[].priceRecordWay=1`，`priceRecordWayList=[1,2,5,7]`，`ratioConfig.ratioType=1`，`extendParam.priceAuditInfoModels` 携带审核理由（`--audit-reason`）。
- `queryGoodsInfo`（`MeGoodsFacade`）经实测确认**不返回** `priceInfo` 和价格审核状态字段，因此脚本内部的"当前售价"需调用方通过 `--current-price-yuan` 显式传入（不做反查），改价后也**不做轮询确认审核状态**（没有可靠字段可判断）。改价请求提交成功后即视为已完成触发动作，如需确认商品是否真的进入「待审核」，需在前端页面或用 RD 提供的查询工具自行核实。
- `offline` / `abolish` 都依赖下线接口 `batchOnlineSwitch(status=3)`：服务端强约束仅"暂停/下线"状态（`goodsStatus=3`）的商品才能废除，因此 `abolish` 会自动先下线再废除；若下线触发人工审批流程（PrepayGoodsOfflineAuditProcess）会失败并提示原因，不做重试。
- `b-closed` / `b-full`（房型维度）：必须传 `--room-id`（逻辑房型ID）和正确的 `--goods-type`（1=全日房走 `--day-room-ids`，2=钟点房走 `--hour-room-ids`）。
- `b-closed-goods` / `b-full-goods`（产品维度）：不传 `--room-id`/`--goods-type`，直接用 `--goods-id` 组装 `goodsIdList` 并传 `changeType=2`；接口层/场景层实现见 `interface/inventory/interface.py#build_modify_model`（`goods_ids` 参数）和 `factory/inventory/update-inventory.py#open_and_set_inventory`（`goods_ids` 参数，传了即自动切到 `changeType=2`）。⚠️ 前置依赖：该门店必须已通过 `MeGoodsFacade#changeRoomStatusDimension`（`factory/inventory/change-room-status-dimension.py`）成功切换为产品维度，否则后端大概率拒绝或不生效；该切换本身是**门店级、异步、不可逆**操作，不要在未确认门店维度状态时随意选用 `*-goods` 系状态。
- **`b-closed`（关房）vs `b-full`（满房）的核心区别在于库存余量是否为0，两者都调用同一个 `batchUpdateInventory` 接口，但参数组合相反**（房型维度、产品维度同理，仅 `changeType`/`modifyInventorySubjectsModel` 不同）：
  - `b-closed`/`b-closed-goods`：`invSwitch=0`（关房）+ `countType=1520` + `limitChangeValue` 默认 **299**（非零，保留库存）→ 「有库存但关房不可订」
  - `b-full`/`b-full-goods`：`invSwitch=1`（开房）+ `countType=1520` + `limitChangeValue=0` → 「开房可订但库存耗尽」
  - ⚠️ **`countType` 的个位（最后一位）只控制“预留房”是否变化（0=不变，1=设置绝对量），与“库存余量”无关**；只要 `countType` 的百/十位选了“设置库存剩余量”语义（如 `1520`），`limitChangeValue` 就一定会真实生效覆盖库存，**不存在“库存完全不下发变化”的 countType 取值**。因此“关房但有库存”必须靠显式传一个非零的 `limitChangeValue` 实现，而不能寄希望于“不传就不生效”（早期实现过固定传 `limit_change_value=0` 导致 `b-closed` 实际变成了“关房+库存0”的 bug，已于本次修复）。
- 全日房默认售价 200 元，钟点房默认售价 80 元（`--current-price-yuan` 不传时使用）。

> ⚠️⚠️⚠️ **`b-full`/`b-closed`（含产品维度 `*-goods`）预留房冲突（2026-08-18/08-19 实测踩坑，已内置自动兜底，AI 无需再手动排查）**：
> 凡是走过"新建商品自动补库存"分支（建品上线失败提示"最近90天内至少30天同时有价格和库存"，脚本自动调用 `batchUpdateInventory` 用 `countType=1121` 补货）的房型/商品，预留房量会被同时设为非零值（默认 `count=1`）。此后若直接对同一房型/商品执行 `b-full`（`limitChangeValue=0`）或 `b-closed`（关房），服务端会强约束"库存余量 ≥ 预留房余量"，报错：
> - 房型维度 `b-full`：`errCode=53007`，"房型剩余房量不能小于预留房量剩余房量，房型余量0，预留房余量1"
> - 产品维度 `b-full-goods`：`errCode=200012038`，"更新失败！更新后房型下所有产品的可售总量之和小于预留房量"
> - 产品维度 `b-closed-goods`：`errCode=200012039`，"关房失败！关房后房型下所有产品的可售总量之和小于预留房量"
>
> ⚠️⚠️⚠️ **关键教训：预留房量是"房型级共享"数据，不是挂在单个商品上的**（服务端报错原文明确写着"房型下**所有产品**的可售总量之和小于预留房量"）。因此清零预留房**必须走房型维度**（`day_room_ids`/`hour_room_ids` + `changeType=1`）调用，若直接对**产品维度**（`goods_ids` + `changeType=2`）传 `count=0` 清零，RPC 会返回成功（`code=10000`）但预留房实际**不受任何影响**，后续操作会反复报同样的冲突错误——这是一个"假成功"陷阱，容易误判为"已清零但接口逻辑有 bug"，实际是清零维度选错了。
>
> **该约束现已在 `factory/goods-state/goods_inventory_ops.py` 内部统一自动兜底**（`set_b_closed`/`set_b_full` 共用 `_clear_reserved_room`/`_is_reserved_room_conflict` 逻辑）：捕获到上述特定错误（匹配"预留房量"/"预留房余量"/"53007"/"200012038"/"200012039"关键字）后：
> 1. 若当前是房型维度（`dimension="room"`），直接用传入的 `room_id` 走房型维度清零；
> 2. 若当前是产品维度（`dimension="goods"`），**自动反查该 `goods_id` 对应的 `roomId`**（`MeGoodsFacade#queryGoodsInfo` 的 `roomInfo.roomId` 字段），再改用房型维度清零（反查失败才退化为产品维度尝试，此时大概率仍不生效）；
> 3. 清零成功后自动重新执行一次原始请求（`b-closed`/`b-full`）。
>
> **调用方（含 AI）无需手动识别、无需手动查 roomId、无需手动清零**，命令报这几个错时不代表状态构造失败，脚本会自动重试并在输出中打印「🔄 自动清零预留房（房型维度，roomId=xxx...）」「📋 提示：本次触发了「预留房自动清零」兜底逻辑」，看到这些日志即代表已自动修复成功。仅当兜底重试后仍失败才需要人工介入排查。

---

## 手动补操作（自动步骤失败时）

若 `abolish` 因下线触发人工审批而失败，脚本会打印手动命令，可单独排查/等待审批通过后手动执行：

```bash
python3 factory/ops/destroy-goods.py --partner-id <partnerId> --poi-id <poiId> --goods-id <goodsId>

