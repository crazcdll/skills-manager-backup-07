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
```

---

## ✅（已解决）房态管理维度："产品维度"下的开关房/库存操作已打通

### 历史现象（2026-08-18 修复前）

`update-inventory.py`（及依赖它的 `factory/goods-state/goods_inventory_ops.py` 的 `b-closed`/`b-full`）
曾经只能传 `--day-room-ids`/`--hour-room-ids`（房型ID），没有 `--goods-ids`/`--change-type` 参数，
导致门店切换为产品维度后无法用 CLI 操作开关房/库存。

### 原因

`MeInventoryFacade#batchUpdateInventory` 接口本身支持 `changeType`：
- `1` = 房型维度（ROOM），配合 `dayRoomIdList`/`hourRoomIdList`
- `2` = 产品维度（GOODS），配合 `goodsIdList`

接口层 `interface/inventory/interface.py` 的 `call_batch_update_inventory()`/`build_modify_model()`
早就支持这两种维度的参数，但场景层 `factory/inventory/update-inventory.py` 的
`open_and_set_inventory()` 曾经把 `change_type=1` 写死，函数签名也没暴露
`change_type`/`goods_ids` 形参，导致 CLI 和 `goods-state.py` 都只能走房型维度。

### 什么情况下门店会变成"产品维度"

通过 `MeGoodsFacade#changeRoomStatusDimension` 接口（HTTP 网关
`/api/gw/v1/product/vpoi/changeRoomStatusDimension`）可以把门店的房态管理从房型维度
**永久切换**为产品维度（`factory/inventory/change-room-status-dimension.py`，2026-08-18 已支持）。
该接口特点：
- **不可逆**：无法从产品维度切回房型维度。
- **门店级**：对整个 VPOI 生效，不是单个商品/房型。
- **异步**：调用成功只代表任务已提交，服务端异步迁移数据，无已知的对外查询接口可轮询最终状态。
- 切换后 B 端存在两套独立数据：房型维度的库存/房态 + 产品维度的库存/房态，两个维度可分别
  单独设置；C 端取用时做两个维度的交集判断——房型维度售罄或关房时，即使产品维度开房有库存，
  C 端也买不了，只有两个维度都"开房且有库存"才可售。

### 解决方案（2026-08-18 已落地）

已扩展场景层，两种维度均可通过 CLI 直接操作：

1. **`factory/inventory/update-inventory.py`**：新增 `--goods-ids` 参数（产品维度，
   `changeType=2`），与 `--day-room-ids`/`--hour-room-ids`（房型维度，`changeType=1`）互斥，
   传其一自动决定 `changeType`。
2. **`factory/goods-state/goods_inventory_ops.py`**：`set_b_closed`/`set_b_full`/
   `apply_inventory_state` 新增 `dimension`（`"room"`/`"goods"`）+ `goods_id` 参数。
3. **`factory/ops/goods-state.py`**：新增 `--state b-closed-goods`/`b-full-goods`
   两个产品维度状态值（与房型维度的 `b-closed`/`b-full` 并存），不需要 `--room-id`/
   `--goods-type`，直接用已有的 `--goods-id` 组装 `goodsIdList`。详见 `w10-goods-state.md`。

⚠️ 使用前提不变：`*-goods` 系列状态**仅当门店已通过 `change-room-status-dimension.py`
切换为产品维度后才生效**，未切换维度的门店传 `--goods-ids`/`b-closed-goods`/`b-full-goods`
大概率会被后端拒绝或不生效；执行前如不确定门店当前维度，应先向用户确认。

