# W7：房态 & 库存修改（开房/关房/设置库存余量）

## 场景覆盖

| 用户意图 | 操作 |
|---------|------|
| 开房（让房间变为可预订状态） | invSwitch=1 |
| 关房（让房间不可预订） | invSwitch=0 |
| 设置库存余量（如补库存至299） | limitChangeValue=299 |
| 新建商品上线失败："最近90天内至少30天同时有价格和库存" | 初次设库存，countType=1121 |

> 直调 `MeInventoryFacade#batchUpdateInventory`，不经过 `batchCreateGoods`。

---

## 前置条件

必须已就绪：`partnerId`、`poiId`，以及 `roomId`（全日房用 `--day-room-ids`，钟点房用 `--hour-room-ids`）。

---

## 核心命令

```bash
python3 factory/inventory/update-inventory.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --day-room-ids <roomId> \         # 全日房用此参数
  # --hour-room-ids <roomId> \      # 钟点房用此参数
  --start-date <YYYY-MM-DD> \       # 通常是今天，如 2026-05-22
  --end-date <YYYY-MM-DD> \         # 通常是两年后，如 2028-05-21（服务端限制：不超今天+2年）
  --inv-switch <-1|0|1> \           # -1=不变，0=关房，1=开房
  --limit-change-value 299 \        # 库存余量目标值（默认299）
  [--count-type 1121] \             # 仅初次设库存时需要
  [--count 1] \                     # 仅 countType=1121 时需要
  [--effect-weeks 1 2 3 4 5]        # 可选：只对指定星期几生效（1=周一...7=周日）
```

> ⚠️ `end-date` 不能超过今天起 2 年（不含当天），建议填 `今天+2年-1天`。不要用 `$(date -v+2y ...)`（macOS 语法），直接写日期字符串更可靠。

---

## countType 选择（关键！）

| 场景 | countType | 必传参数 |
|-----|-----------|---------|
| **新建商品首次设库存** | `1121` | `--count 1`（也必须传） |
| 已有库存，修改余量 | `1520`（默认，不用传） | 无 |
| 已有库存，设为不限量 | `1920` | 无 |

> ⚠️ **新建商品必须用 countType=1121**。用默认 1520 会报「初次添加库存,不能选择不变」。
> 判断方式：商品刚创建 / 从未设过库存 → 用 1121；已经有库存记录 → 用 1520。

---

## 常用场景示例

### 场景一：新建商品上线失败，补库存后重新上线

```bash
# Step 1：开房 + 初次设库存
python3 factory/inventory/update-inventory.py \
  --partner-id <partnerId> --poi-id <poiId> \
  --day-room-ids <roomId> \
  --start-date <今天日期> --end-date <今天+2年-1天> \
  --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1

# Step 2：重新上线
python3 factory/ops/online-switch.py \
  --partner-id <partnerId> --poi-id <poiId> \
  --goods-ids <goodsId> --status 2
```

### 场景二：关房（某日期区间不可预订）

```bash
python3 factory/inventory/update-inventory.py \
  --partner-id <partnerId> --poi-id <poiId> \
  --day-room-ids <roomId> \
  --start-date 2026-06-01 --end-date 2026-06-07 \
  --inv-switch 0     # 0=关房
```

### 场景三：已有库存，补余量

```bash
python3 factory/inventory/update-inventory.py \
  --partner-id <partnerId> --poi-id <poiId> \
  --day-room-ids <roomId> \
  --start-date <今天日期> --end-date <今天+2年-1天> \
  --inv-switch 1 --limit-change-value 299    # 不需要 --count-type
```

### 场景四：钟点房开房（用 --hour-room-ids）

```bash
python3 factory/inventory/update-inventory.py \
  --partner-id <partnerId> --poi-id <poiId> \
  --hour-room-ids <roomId> \
  --start-date <今天日期> --end-date <今天+2年-1天> \
  --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1
# ⚠️ 钟点房用 --hour-room-ids（全日房用 --day-room-ids）
```

---

## invSwitch 枚举

| 值 | 含义 |
|----|------|
| `-1` | 不变（保持当前房态） |
| `0` | 关房（不可预订） |
| `1` | 开房（可预订） |

---

## 关键约束

- 全日房：`--day-room-ids`；钟点房：`--hour-room-ids`，不能搞混
- 日期范围建议：`start-date=今天`，`end-date=两年后`（确保足够库存覆盖）
- 详细 countType 坑记录：`references/pitfalls/inventory.md`

