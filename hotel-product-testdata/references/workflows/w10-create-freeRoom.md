# W10：构造闲置房（子产品，依赖境内全日房母产品）

## 场景覆盖

| 用户描述 | 说明 |
|---------|------|
| 闲置房、闲置房上单、闲置房充值、batchRechargeFreeHouse | 唯一场景，**只支持境内**（闲置房不存在境外场景） |

---

## 核心概念：闲置房是"子产品"

闲置房**不能独立创建**，必须先有一个已成功上线的**母产品**（境内全日房），再通过"闲置房充值"接口把母产品的部分间夜"转生产"为闲置房子产品。

```
[前置] W1：境内全日房（母产品）→ goodsId
  ↓
[W10] 闲置房充值 batchRechargeFreeHouse（子产品）→ 以母产品 goodsId 作为 rechargeGoods[].goodsId
```

> ⚠️ 母产品**必须是境内全日房**（只有境内有闲置房场景，境外/钟点房均不适用）。

---

## 前置条件

| 所需 ID | 是否必填 | 说明 |
|---------|------|------|
| `partnerId` | ✅ 必填 | 供应商ID（境内预付） |
| `poiId` | ✅ 必填 | 门店ID，须与 partnerId 已绑定 |
| `customerId` | 可选 | 业务客户ID；不传则脚本自动用工具464（客户ID互查）由 partnerId 换算 platformCustomerId |
| `goodsId`（母产品） | ✅ 必填 | 先按 **前置 A：W1 创建境内全日房** 完成后得到，必须已成功上线 |

若 `partnerId`/`poiId` 缺失，先走 `references/workflows/w8-infra-bootstrap.md` 补齐（境内路径即可，不要加 `--overseas`）。

---

## 前置 A：W1 创建境内全日房母产品

参考 `references/workflows/w1-create-fullday.md`，按境内默认参数创建一条全日房，完成后得到 `goodsId`。

```bash
python3 factory/fullday/create-fullday.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --room-id <roomId> \
  --room-name "<roomName>" \
  --goods-name "<母产品商品名>" \
  --set goodsDetailList.0.goodsBaseInfo.contractNo=<contractNo>
```

确认 `[Step 4] 恢复上线（batchOnlineSwitch status=2）` 成功后，记录返回的 `goodsId`，作为 W10 的 `--goods-id` 传入。

> 无需带任何境外参数（`priceSameTag`/`priceFactorInfos` 等），闲置房母产品就是普通境内全日房，早餐/取消政策等按默认模板即可，除非用户明确要求特定规则。

---

## 前置 B：商家账号查询 + 免密登录（闲置房充值接口唯一额外依赖）

闲置房充值接口 **不是标准 Thrift RPC 调用**（2026-09-16 实测修正：底层 Thrift 方法 `EbPcGoodsFacade#batchRechargeFreeHouse` 在 DataUnity 网关上无法路由，报 `connection list is empty`），而是 **HTTP 直连 EB 后台网关**：

- url：`POST http://eb.hotel.test.sankuai.com/api/v1/ebooking/vacantHouse/rechargeV2`
- 鉴权：`Cookie: ebbsid=<bsid>`，bsid 用 **tdm-cli** 对商家账号免密登录换取：
  ```bash
  tdm token blogin --skip-password -u <商家账号登录名> --raw
  ```
- body：业务入参中保留 `"user"` 字段（商家账号登录名），与 EB 前端真实请求一致

### 依赖安装（首次使用）

**merchant-testdata-cli**（命令名 `merchant-testdata-cli`，用于按 partnerId 反查商家账号登录名）：
```bash
curl -fsSL https://friday.sankuai.com/open/cli/deploy/merchant-testdata-cli/install.sh | bash
```

**tdm-cli**：用于免密登录换 bsid（一般已随环境安装，`which tdm` 确认）。

### 按 partnerId 查询商家账号登录名

```bash
merchant-testdata-cli hotel account --action query-partner --partner-id <partnerId>
```

返回关联账号登录名 `loginName/login`（tdm-cli 免密登录的账号，也是 body 中 `user` 字段的值），以及商家账号ID `accountId/mid`（`mid = accountId = bizAccountId`，**开资金池时要用**）。

> ⚠️ **仅支持 TEST 测试环境**；`query-partner` 能查到的是供应商关联的登录名，但不一定代表该账号已录入"测试账号管理平台"。若查不到记录，说明未被录入，此时执行：
> ```bash
> merchant-testdata-cli hotel account --action add --partner-id <partnerId>
> ```
> 录入后再重新查询。

**以上步骤已封装进 `factory/freeRoom/create-freeRoom.py` 脚本内部**，正常使用无需手动执行，脚本会自动查账号 → tdm-cli 换 bsid → curl 直连 rechargeV2；本节仅供排查账号问题时参考。

---

## 前置 C：商家资金池（假成功根因，2026-09-16 实测踩坑）

充值流程第一步是资金池检查（`containsCoinPool_check`）。**若商家账号未开通资金池，接口会静默跳过充值，但外层仍返回 `{"status":0,"message":"成功","data":null}`（假成功）**——不查置换记录根本发现不了。

执行 W10 前，先确认商家已开资金池（hotel-merchant-data skill 的 coinpool 命令）：

```bash
# 查询（应能看到 coinTypeId=5 大资金池）
mt-testdata hotel coinpool --action query --merchant-type hotel-yf --biz-account-id <bizAccountId>

# 未开通则开户（境内预付）
mt-testdata hotel coinpool --action open --merchant-type hotel-yf \
  --biz-account-id <bizAccountId> --partner-id <partnerId>
# 若 Step 2 绑定报 402 系统异常，等待 10s 后用 --bind-only 单独重试绑定；
# 实测即使绑定 402，资金池已创建（query 可见），不影响闲置房充值
```

**真假成功判别**：真实成功返回 `data:true`；`data:null` 即资金池检查未通过（脚本已内置此检测，会直接报错并提示开户命令）。

## 前置 D：rechargeScheme（充值方案）选择

| rechargeScheme | 模式 | 依赖 |
|---|---|---|
| `0` | 先充值 | 需要 Moka 平台配置「免费房估值信息」mock，否则报"查不到免费房估值信息"（SOP 见前置 E） |
| `1`（默认） | **先售卖** | **不需要估值 mock**，推荐默认使用 |

脚本 `--recharge-scheme` 默认已改为 `1`（先售卖）。

---

## 前置 E：先充值（rechargeScheme=0）估值 mock SOP（泳道隔离方案，2026-09-16 实测踩通）

先充值链路会调 mcoin `getFreeRoomValue` → dpd `IDpdVacantRoomService.queryValueAndNum` 查「免费房估值信息」，查不到报 `400 查不到免费房估值信息`。需在 Moka 给 mcoin 配置该接口的**泳道级** mock（⚠️ **严禁动主干 BACK_BONE 共享配置/共享规则集数据**，那是危险操作）。

- 调用方 appkey：`com.sankuai.mpht.mcoin.biz`；下游：`com.sankuai.rocs.dpd`
- uri：`com.sankuai.rocs.dpd.thrift.service.IDpdVacantRoomService.queryValueAndNum(com.sankuai.rocs.dpd.thrift.dto.request.VacantValueAndNumQueryReq)`
- mock response 模板（字段替换为自己的数据）：
  ```json
  {"code":200,"msg":"成功","data":{"pageNo":1,"pageSize":200,"total":1,"list":[{"partnerId":4581625,"poiId":1090269458185024,"bizActId":150200959,"goodsId":600007122756,"roomId":78035390,"valuationAmount":10000,"exchangeNum":10}]}}
  ```
  字段：`partnerId` / `poiId` / `bizActId`（=商家账号ID mid，`merchant-testdata-cli ... query-partner` 可查）/ `goodsId`（**当次要充值的母产品**——先充值同样要求母产品下无未履约子产品，需新母产品）/ `roomId` / `valuationAmount`（=simpleValue，单位分）/ `exchangeNum`（=freeRoomNum）

### 泳道选择三条件（必须同时满足）

1. **EB 网关认该泳道**：带 `swimlane: <泳道>` header 调 rechargeV2 不报 `302 权限验证失败`（2026-09-16 实测：EB 只放行部分泳道，`1942-nrsfj`/`weijiawei05-zppiy`/`zhuxin17-dvwvx` 可用；`1938-bgrdf`/`yanwenjing-hhbuu`/`lvzonglin-zrryh`/`sunxiaoting03-rzmdl` 报 302）
2. **mcoin 在该泳道有部署且 Agent 已装**：`moka-cli scope --appkey com.sankuai.mpht.mcoin.biz --type swimlane` 看 agentStatus，未装则 `moka-cli install-agent --appkey com.sankuai.mpht.mcoin.biz --swimlane <泳道>`（约 5 分钟）
3. **该接口在该泳道无既有 mock 配置**：`moka-cli list --appkey com.sankuai.mpht.mcoin.biz` 查 queryValueAndNum 的 scope 占用；已占用时 create 会报"当前配置已存在"

> 2026-09-16 实测唯一交集：`weijiawei05-zppiy`（泳道归属会随时间变化，按三条件重新探测；探测方法：带 header 调 rechargeV2，用旧母产品看返回是业务错误还是 302）

### 操作步骤

1. 按三条件选定泳道（必要时先装 Agent）
2. **创建泳道级 mock**（moka-cli，登录已内置 catdesk 兑底换票，免浏览器）：
   ```bash
   python3 ~/.catpaw/skills/skills-market/moka-cli/scripts/moka-cli.py create \
     --appkey com.sankuai.mpht.mcoin.biz \
     --remote-appkey com.sankuai.rocs.dpd \
     --uri "com.sankuai.rocs.dpd.thrift.service.IDpdVacantRoomService.queryValueAndNum(com.sankuai.rocs.dpd.thrift.dto.request.VacantValueAndNumQueryReq)" \
     --invoke-type THRIFT \
     --scope <泳道> \
     --remark "闲置房先充值验证（临时，用完即删）" \
     --response '<上方模板替换后的 JSON>'
   ```
3. **带泳道执行先充值**：`create-freeRoom.py --recharge-scheme 0 --swimlane <泳道>`（脚本已支持给 rechargeV2 请求加 `swimlane` header，泳道上下文沿 EB→platform→mcoin 透传）
4. **用完立即删除 mock**：`moka-cli delete --id <MockID>`

---

## Step 1：dry-run 校验（可选）

```bash
python3 factory/freeRoom/create-freeRoom.py \
  --poi-id <poiId> \
  --partner-id <partnerId> \
  [--customer-id <customerId>] \
  --goods-id <母产品goodsId> \
  --goods-name "<母产品商品名>" \
  [--login-name <已知商家账号，跳过自动查询>] \
  [--min 3] [--max 20] [--free-room-num 10] \
  [--simple-value 10000] [--total-value 100000] \
  [--start-days 0] [--end-days 365] \
  [--swimlane <泳道>] \
  --dry-run
```

`--goods-id` 为**必填参数**，必须是**前置 A**中已成功上线的母产品 `goodsId`；`--dry-run` 只打印将要发送的 Thrift 请求（含自动注入的 `user` 字段），不实际调用。

> `--customer-id` 不传时，脚本自动调用工具464（`transform-customer-id`，按 `originCustomerIdStr=partnerId` 查 `platformCustomerId`）换算得到，无需手动查询。

---

## Step 2：正式提交

去掉 `--dry-run` 执行同一命令。脚本按顺序执行：

1. （若未传 `--customer-id`）调用工具464由 `partnerId` 换算 `platformCustomerId` 作为 `customerId`
2. 组装 `rechargeGoods` 请求体（含 `goodsId`/`goodsName`/`min`/`max`/`freeRoomNum`/`simpleValue`/`totalValue` 等）
3. （若未传 `--login-name`）调用 `merchant-testdata-cli` 按 `partnerId` 查询商家账号登录名，注入 `user` 字段
4. 通过 `scripts/runner.py` 的 `invoke()` 直接发起 Thrift RPC 调用 `EbPcGoodsFacade#batchRechargeFreeHouse`

```bash
python3 factory/freeRoom/create-freeRoom.py \
  --poi-id <poiId> \
  --partner-id <partnerId> \
  --goods-id <母产品goodsId> \
  --goods-name "<母产品商品名>"
```

脚本打印完整请求体和响应体，并按以下规则自动校验：

1. `data == null`（假成功）→ 直接报错退出，提示先开资金池（见前置 C）
2. `data == true` → 自动调用 mcoin `IFreeRoomRecordService.countByParam`（appkey `com.sankuai.mpht.mcoin.biz`，Thrift）按 `partnerId + poiId` 统计置换记录数，**记录数 > 0 才最终判定成功**
3. 常见业务报错：`充值母产品下面子产品尚未履约完成，不能再次进行充值` —— 同一母产品下有未履约完成的闲置房子产品时不能再次充值，需等子产品履约完成（或换一个母产品）

---

## 完整执行链路

```
[前置A] W1：factory/fullday/create-fullday.py（境内，无需境外参数）→ goodsId（母产品）
[前置B] merchant-testdata-cli 查商家账号登录名（已封装进脚本，无需手动执行）
[前置C] mt-testdata hotel coinpool 确认商家资金池已开通（未开通→假成功）
[前置D] rechargeScheme 默认 1=先售卖；0=先充值需先按前置E配置估值 mock
[前置E]（仅先充值）Moka 泳道级估值 mock（三条件选泳道，严禁动主干共享配置）
[W10]   factory/freeRoom/create-freeRoom.py --goods-id <goodsId> [--swimlane <泳道>]
        → tdm-cli 免密登录换 bsid → HTTP POST rechargeV2（带 swimlane header）→ countByParam 验证置换记录 → 闲置房子产品
```

---

## 关键约束

- **闲置房只支持境内**，母产品必须是境内全日房（W1，不加 `--overseas`）
- 母产品必须**已成功上线**（`batchOnlineSwitch status=2`）才能作为 `rechargeGoods[].goodsId` 传入，未上线直接调用大概率报错
- `customerId` ≠ `partnerId`：`customerId` 是业务客户ID（`platformCustomerId`），需通过工具464由 `partnerId` 换算，不能直接把 `partnerId` 值填进 `customerId`
- 闲置房充值走 **HTTP 直连 EB 网关** `POST http://eb.hotel.test.sankuai.com/api/v1/ebooking/vacantHouse/rechargeV2`（2026-09-16 实测：底层 Thrift 方法在 DataUnity 网关无法路由，报 `connection list is empty`）；鉴权用 **tdm-cli 免密登录**换 bsid 拼 `Cookie: ebbsid=<bsid>`，body 保留 `"user"` 字段（商家账号登录名）
- **商家必须先开通资金池**：未开通时接口静默跳过充值并返回 `{"status":0,"data":null}` 假成功；用 `mt-testdata hotel coinpool --action open --merchant-type hotel-yf --biz-account-id <bizAccountId> --partner-id <partnerId>` 开户
- **`rechargeScheme` 默认 1（先售卖，无需估值 mock）**；0=先充值需按**前置 E**在 Moka 配置**泳道级**估值 mock（三条件选泳道，请求带 `swimlane` header；**严禁动主干 BACK_BONE 共享配置**），用完必须删除 mock
- **同一母产品下有未履约完成的闲置房子产品时不能再次充值**（报"子产品尚未履约完成"），需换母产品或等履约完成
- 充值成功后务必用 mcoin `IFreeRoomRecordService.countByParam`（partnerId+poiId）验证置换记录数 > 0（脚本已内置）
- HTTP 直连通过 `swimlane` 请求头支持泳道路由（脚本 `--swimlane` 已实现）；⚠️ EB 网关只放行部分泳道，不认的泳道报 `302 权限验证失败`（详见前置 E）
- 商家账号登录名依赖 `merchant-testdata-cli`（按 partnerId 查询），首次使用需按 SKILL.md 初始化章节安装
- `startTime`/`endTime` 为毫秒时间戳，脚本用 `--start-days`/`--end-days`（相对今天的天数偏移）自动换算，无需手动拼接 `"$+N day"` 占位符
- `merchant-testdata-cli hotel account --action query-partner` 仅支持 **TEST 测试环境**；若查不到账号记录，说明未录入测试账号管理平台，需先执行 `--action add --partner-id <partnerId>` 录入

