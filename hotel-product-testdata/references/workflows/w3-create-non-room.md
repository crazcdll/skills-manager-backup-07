# W3：构造非房 xGoods + 审核

## 场景覆盖

| 用户描述 | 关键参数差异 |
|---------|------------|
| 普通非房（单门店） | `--poi-id <单个ID>` |
| 需要游客信息的非房 | `--tourists-info-type 2` |
| 境外非房 | `--overseas` |
| 批量门店非房 | `--poi-id "<id1>,<id2>,<id3>"` （逗号分隔，单参数） |
| 审核通过/驳回 | `--action pass / reject` |

---

## 前置条件

进入本 workflow 前，必须已就绪：`partnerId`、`poiId`（门店ID）。

缺少任何一项 → 先执行 `references/workflows/w8-infra-bootstrap.md`。

> ⚠️ 非房**不需要** contractNo 和 roomId（区别于全日房/钟点房）。

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

