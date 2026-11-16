# W3：构造非房 xGoods + 审核

## 场景覆盖

| 用户描述 | 关键参数差异 |
|---------|------------|
| 普通非房（单门店） | `--partner-id <id> --poi-id <单个ID>` |
| 独立售卖（加购）非房 | `--sell-status 1` + 8 个扩展参数（见下方专节），额外需要 `contractNo` |
| 不同商品类型模板 | `--type catering(默认)\|scenic\|tour` |
| 审核通过/驳回 | `factory/audit/gift/audit.py`（无 --action 参数，见下方 Step 2） |

> ℹ️ 当前 `create-non-room.py` 实际不支持 `--tourists-info-type` / `--overseas` / 批量 `--poi-id` 逗号分隔（历史文档遗留描述，与代码不一致，已在此次修订中移除；如有这些诉求请反馈给 Skill 维护者评估排期）。

---

## 前置条件

进入本 workflow 前，必须已就绪：`partnerId`、`poiId`（门店ID）。

缺少任何一项 → 先执行 `references/workflows/w8-infra-bootstrap.md`。

> ⚠️ **普通非房不需要** contractNo 和 roomId（区别于全日房/钟点房）。
> ⚠️ **独立售卖（加购）非房例外**：需要 `contractNo`（合同编号字符串），且仅支持 **预付合同(=2)** 或 **团购合同(=0)**，**禁止包销合同(=5)**。可用 `factory/infra/create-contract.py --contract-type 2` 创建后取 `contractNo` 使用（注意此参数口径与 `MccConstants.XGOODS_CONTRACT_TYPE_RULE` 的编号一致：2=预付、0=团购）。

---

## Step 1：创建非房 xGoods

直接调用 `MeResourceFacade#submitXgoods`（同步接口，直接返回 xGoodsId）。

```bash
python3 factory/non-room/create-non-room.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  [--product-name "<非房名称>"]   # ⚠️ 不超过 20 字符
```

**指定泳道**：

```bash
python3 factory/non-room/create-non-room.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --swimlane <泳道名>
```

> ✅ 同步接口，直接返回 `xGoodsId`，无需等待大象推送。

---

## Step 1'：创建独立售卖（加购）非房（CRS-60）

> 需求方向为「非房独立售卖 / 可加购非房 / 非房商品化」时使用本节，其余场景走普通 Step 1。

sellStatus=1（普通加购）时，以下 **8 个扩展字段全部必填**，缺一会在本地提前报错（不会等到 RPC 返回 10004 才发现）：

| CLI 参数 | 落库路径 | 取值约束 |
|---------|---------|---------|
| `--promotion-text` | `basicInfoModel.promotionText` | 促销文案，长度/字符集规则待 PRD 补充 |
| `--display-order` | `basicInfoModel.displayOrder` | 整数 1-20 |
| `--contract-no` | `basicInfoModel.contractNo` | 合同编号字符串；仅支持 **预付合同(=2)** / **团购合同(=0)**，禁止 **包销合同(=5)**，否则返回 10004 |
| `--total-stock` | `stockModel.totalStock`（⚠️ 顶层新模型，非 basicInfoModel 字段） | 整数，取值范围待 PRD 确认 |
| `--market-price` | `priceModel.marketPrice` | 单位分（字符串），如 99.00 元传 `9900` |
| `--sale-price` | `priceModel.salePrice` | 单位分（字符串），本期仅卖价模式 |
| `--commission-rate` | `priceModel.commissionRate` | 万分位整数，如 12.50% 传 `1250`；本期后端不校验取值范围，只做格式校验 |
| `--max-num-per-order` | `ruleModel.useRuleModel.maxNumPerOrder` | 整数 1-10 |

```bash
python3 factory/non-room/create-non-room.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --sell-status 1 \
  --promotion-text "周末特惠立减" \
  --display-order 5 \
  --contract-no <contractNo> \
  --total-stock 100 \
  --market-price 9900 \
  --sale-price 8900 \
  --commission-rate 1250 \
  --max-num-per-order 2
```

> ✅ `sellStatus=0`（默认，不传 `--sell-status`）时行为与原非房上单逻辑完全一致，不受本扩展影响。
> ⚠️ `contractNo` 需先备好：数据池中已有的预付/团购合同可直接用；没有则先用 `factory/infra/create-contract.py --contract-type 2` 新建。**不要用包销合同（`--contract-type 5`）**，会被后端卡控拒绝。
> ⚠️ **vpoi 白名单限制**：测试环境仅名单库 metaId=1074 白名单内的 vpoi 才允许 sellStatus=1，不在名单返回 10004。若命中此错误，需先确认 poiId 是否在白名单试点范围内（当前仅试点约10家POI）。
> ℹ️ 编辑已有独立售卖非房 / 回查详情字段（`queryXgoodsDetail`）当前 Skill 暂无对应原子工具，如有需求请反馈给 Skill 维护者评估排期。
> ✅ **已验证可行**（2026-08-03 实测）：`partnerId=4570381 poiId=1090269468135297 contractNo=ZSFW-A9-22787529` 成功创建 `xGoodsId=2257281540` 并审核通过。

---

## Step 2：审核非房

非房审核直接调用 RPC 接口，**无需 BPM Cookie，无需浏览器**，一步完成。

```bash
python3 factory/audit/gift/audit.py \
  --xgoods-id <xGoodsId> \
  --partner-id <partnerId> \
  --shop-id <shopId>
```

> 调用接口：`com.sankuai.qatool.productmanage` → `ProductMakeService#auditProduct`

---

## 完整执行链路

```
1. create-non-room.py → 同步返回 xGoodsId
2. gift/audit.py --xgoods-id <xGoodsId> --partner-id <partnerId> --shop-id <shopId> → 直接 RPC 审核通过
```

---

## 关键约束

- 非房创建使用 `MeResourceFacade#submitXgoods`（直接 Thrift RPC，**不走** MeGoodsFacade）
- 非房 ID 叫 `xGoodsId`，审核时用 `--xgoods-id` 传入（不是 goodsId）
- 创建后必须审核通过才能上线（与全日房直接上线不同）
- 商品名称不能超过 20 字符（接口硬限制，超长自动截断并告警）
- **独立售卖（加购，CRS-60）专属约束**：
  - `sellStatus=1` 时 8 个扩展字段全部必填，本地提前校验报错（CLI 层拦截，不依赖 RPC 返回 10004）
  - `stockModel` 是与 `basicInfoModel`/`priceModel` 同级的**顶层新模型**，不要塞进 `basicInfoModel`（历史上曾有过基于仓库自行推断字段归属导致的错误，已按前后端接口文档 contentId=2769956950 纠正）
  - `contractNo` 仅支持预付合同(=2)/团购合同(=0)，包销合同(=5) 会被拒绝
  - `commissionRate` 为万分位整数（1250=12.50%），不是百分比或小数
  - 独立售卖非房创建后**不可绑定 goods/套餐/超团**（后端 6 处卡控），本 Skill 的 W1/W4/W5 绑定非房场景不适用于 `sellStatus=1` 的非房，仅普通非房（`sellStatus=0`）可继续按原方式绑定
  - ⚠️ **价值凭证联动踩坑**（实测发现）：`sellStatus=1` 时 `marketPrice`/`salePrice` 从可空变必填，会联动触发 `priceModel` 门市价价值凭证必填校验（报 `200002000 请上传价值凭证`），普通非房因 `marketPrice` 为空不触发此校验。`create-non-room.py` 已在独立售卖分支自动补齐 `priceProofType=0` + `priceProofUrls`（复用模板测试图床地址），无需用户额外处理
  - vpoi 若不在 metaId=1074 白名单会报 10004；若 RPC 返回 `200001005 依赖系统异常`，大概率是下游通用商品发布服务瞬时抖动（技术方案已知有异步重试机制），可直接重试，非脚本参数问题

