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
- `update-inventory.py` 同时支持「房型维度」和「产品维度」两种操作：
  - 传 `--day-room-ids`/`--hour-room-ids` → 房型维度（`changeType=1`，适用于未切换维度的门店）
  - 传 `--goods-ids` → 产品维度（`changeType=2`，仅适用于已通过下方"切换房态管理维度"
    章节切换为产品维度的门店），二者互斥不可混传
  - `factory/goods-state/goods_inventory_ops.py` 对应封装为 `dimension="room"`（默认）/
    `dimension="goods"` 两种入参，`factory/ops/goods-state.py` 则对外暴露为
    `b-closed`/`b-full`（房型维度）与 `b-closed-goods`/`b-full-goods`（产品维度）四个 `--state`
    值，详见 `w10-goods-state.md`

---

## ⚠️ 切换房态管理维度（房型 → 产品，高风险不可逆，独立场景）

ME 系统支持把某个门店（VPOI）的房态管理从「房型维度」切换为「产品维度」，通过
`MeGoodsFacade#changeRoomStatusDimension` 接口触发（HTTP 网关对应
`/api/gw/v1/product/vpoi/changeRoomStatusDimension`）。**这是一个门店级、异步、不可逆的操作**，
与本 workflow 上面描述的"开关房/设库存"是完全不同的两件事，务必先完全理解以下三点再执行：

1. **不可逆**：切换后不支持从产品维度切回房型维度，没有反向接口。
2. **切换后 B 端存在两套独立数据**：在房型维度的库存/房态之外，多出一层产品维度的库存/房态，
   两个维度可以分别单独设置（B 端视角 = 房型维度库存/房态 + 产品维度库存/房态，共两套）。
3. **C 端取用时做两个维度的交集判断**：房型维度库存售罄或关房时，即使产品维度房态为开、
   有库存，C 端也买不了；只有两个维度都"开房且有库存"，C 端才可售。

调用方式：

```bash
python3 factory/inventory/change-room-status-dimension.py \
  --partner-id <partnerId> --poi-id <poiId>

# 强烈建议先 dry-run 确认门店/供应商无误
python3 factory/inventory/change-room-status-dimension.py \
  --partner-id <partnerId> --poi-id <poiId> --dry-run
```

- 只需要 `partnerId` + `poiId`，没有 `goodsId`/`roomId` 维度的入参（接口本身就是门店级操作）。
- 接口调用成功只代表"切换任务已提交"（服务端异步迁移库存/房态数据），**本脚本不轮询确认最终
  是否切换成功**，`data` 字段返回的是任务标识字符串（非 goodsId），无法复用 `wait_for_goods_id`
  轮询逻辑；如需确认最终状态，需等待片刻后在 ME/MTA 前端页面自行核实。
- ⚠️ **仅当用户明确要求"切换为产品维度房态"时才执行**，不要在普通开关房/建品需求中主动调用，
  也不要在非测试专用门店上执行（该操作对整个门店生效且不可逆）。

