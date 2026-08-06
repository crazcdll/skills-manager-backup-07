# 踩坑记录：房态 & 库存（batchUpdateInventory）

---

## ⚠️ 初次添加库存报错「初次添加库存,不能选择不变」

### 现象

新建商品后调用 `update-inventory.py` 开房设库存，报错：

```
初次添加库存,不能选择不变
```

用 `countType=1520 / 1920 / 1120`（个位=0，含"预留房不变"语义）均会触发。

### 原因

后端对 countType 个位的含义：
- 个位 `0` = 预留房「不变」→ 要求该房型**已有**库存记录才能"不变"
- 个位 `1` = 预留房「设置绝对量」→ 初次和已有均可

默认值 `1520` 个位是 0，所以新建商品第一次设库存会报错。

### 解决

| 场景 | countType | 命令示例 |
|------|-----------|---------|
| **初次**设库存（新建商品/从未设过） | `1121` | `--count-type 1121 --limit-change-value 299 --count 1` |
| **已有**库存记录后修改余量 | `1520`（默认） | `--limit-change-value 299`（无需传 count-type） |

### countType 完整枚举

| 值 | 含义 | 适用场景 |
|----|------|---------|
| `1121` | 设置库存总量 + 设置预留房绝对量 | **初次/已有均可**（推荐兜底用） |
| `1520` | 设置库存剩余量，预留房不变 | 已有库存记录后（最常用） |
| `1920` | 库存不限量，预留房不变 | 已有库存记录后 |
| `1120` | 设置库存总量，预留房不变 | 已有库存记录后 |
| `1021` | 库存总量不变，设置预留房绝对量 | 已有库存记录后 |

### 快速判断

```
新建商品 / 上线报"最近90天内至少30天同时有价格和库存"
  → python3 factory/inventory/update-inventory.py \
      --partner-id <partnerId> --poi-id <poiId> \
      --day-room-ids <roomId> \
      --start-date 2026-05-22 --end-date 2028-05-21 \
      --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1
  # 钟点房改用 --hour-room-ids

已有库存、只是补量
  → python3 factory/inventory/update-inventory.py \
      --partner-id <partnerId> --poi-id <poiId> \
      --day-room-ids <roomId> \
      --start-date 2026-05-22 --end-date 2028-05-21 \
      --inv-switch 1 --limit-change-value 299

