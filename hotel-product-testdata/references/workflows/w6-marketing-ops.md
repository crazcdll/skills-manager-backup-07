# W6：营销报名 / 缓存刷新 / 改价审核 / 上线下线

## 场景覆盖

| 用户意图 | 操作 |
|---------|------|
| 生意助手报名 / 全域通报名 | 营销报名（工具1037） |
| 刷新商品/SPU/门店/货盘缓存 | 缓存刷新（--op 1） |
| BD 改价审核（通过/驳回） | --op 2 |
| 商家改价审核（通过/驳回） | --op 3 |
| 商品上线 | batchOnlineSwitch status=2 |
| 商品下线 | batchOnlineSwitch status=3 |
| 查询商品详情 | queryGoodsInfo |

---

## 营销报名（工具1037）

参数约束参考：`factory/marketing/schema.json`

两种报名方式（通过 `--mode` 区分）：

### 方式一：供应商+门店报名（新建 Goods 报名）

```bash
python3 factory/marketing/enroll-marketing.py \
  --mode 1 \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --config-key <configKey>
```

### 方式二：对已有产品报名

```bash
python3 factory/marketing/enroll-marketing.py \
  --mode 2 \
  --product-id <goodsId> \
  --config-key <configKey>
```

### configKey 枚举

| configKey | 含义 |
|-----------|------|
| `notUpscale` | 生意助手（仅生意助手，不含全域通） |
| `upscaleFixed` | 全域通一口价（**最常用**） |
| `upscaleDiscount` | 全域通折扣 |
| `upscaleFixedDiscountMixed` | 全域通一口价折扣混合 |

> 工具1037 是异步接口，code=2027 表示提交成功，结果由大象推送。

---

## 缓存刷新 / 改价审核（工具1031）

参数约束参考：`factory/ops/schema.json`

> ⚠️ 参数名是 `--op`（不是 `--operation-type`）

### 缓存刷新

```bash
python3 factory/ops/cache-refresh-audit.py \
  --op 1 \
  --product-id <goodsId>    # 商品级别
  # 或 --spu-id <spuId>      # SPU 级别（超团/套餐）
  # 或 --poi-id <poiId>      # 门店级别
  # 或 --rp-id <rpId>        # 货盘级别
```

> 四个 ID 参数（product-id / spu-id / poi-id / rp-id）传其中一项即可，对应刷新的粒度不同。

### BD 改价审核

```bash
python3 factory/ops/cache-refresh-audit.py \
  --op 2 \
  --product-id <goodsId> \
  --audit-status 3          # 3=通过（默认），2=驳回
```

### 商家改价审核

```bash
python3 factory/ops/cache-refresh-audit.py \
  --op 3 \
  --product-id <goodsId> \
  --audit-status 3
```

---

## 商品上线 / 下线（batchOnlineSwitch）

> ⚠️ `--goods-ids` 可传多个（空格分隔）；`--partner-id` 和 `--poi-id` 必填

```bash
# 上线（恢复上线）
python3 factory/ops/online-switch.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-ids <goodsId> \
  --status 2                # 2=上线

# 下线
python3 factory/ops/online-switch.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-ids <goodsId> \
  --status 3                # 3=下线（注意：不是1！）

# 批量上线多个商品
python3 factory/ops/online-switch.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-ids <goodsId1> <goodsId2> \
  --status 2
```

> 上线失败且报"最近90天内至少30天同时有价格和库存"时，先执行 `references/workflows/w7-inventory-ops.md` 开房设库存，再重新上线。

---

## 查询商品详情（queryGoodsInfo）

```bash
python3 factory/ops/query-goods.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-ids <goodsId>
  # 支持多个 goodsId（空格分隔）
  # 可选：--field rpCancelModel   只打印特定字段
```

---

## 关键约束

- `--op` 是 cache-refresh-audit.py 的参数名（不是 `--operation-type`）
- 商品**下线** status=`3`，**上线** status=`2`（不是 1！1 在内部枚举中有其他含义）
- online-switch.py 必须传 `--partner-id`、`--poi-id`、`--goods-ids`，三者缺一不可
- 营销报名必须先指定 `--mode 1`（供应商+门店）或 `--mode 2`（productId），两者互斥
- 改价审核必须传 `--audit-status`（2=驳回 / 3=通过），--op=3（商家改价）默认通过

