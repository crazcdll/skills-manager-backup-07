# DUO 接口动态 Mock 指南

> 适用于 DUO 协议驱动的页面接口（preview、update、check 等），这类接口的 response 采用 nodeDataMap 组件化数据结构。

## 核心原则

DUO 协议接口的 response 中存在**两套数据体系**，Mock 时必须修改正确的那套：

| 数据位置 | 用途 | Mock 是否生效 |
|---------|------|-------------|
| `data.totalPrice`、`data.salePrice` 等顶层字段 | 元数据/业务逻辑参考值，不直接驱动 UI 渲染 | ❌ 改了 UI 不变 |
| `data.nodeDataMap.<组件名>.p.<字段>` | 各组件的渲染 props，UI 直接读取 | ✅ 改了 UI 立即生效 |
| `data.currentData.<字段>` | 当前数据快照，部分组件会读取 | ⚠️ 建议同步修改 |

## 价格相关字段速查（以酒店提单页 preview 接口为例）

### 底部支付栏（BottomBar 组件）

```
data.nodeDataMap.BottomBar.p.totalPayAmount → 底部栏总价（单位：分，如 15375 = ¥153.75）
data.nodeDataMap.BottomBar.p.roomFeeAmount → 房费金额（单位：分）
data.nodeDataMap.BottomBar.p.cashRoomFeeAmount → 现金房费（单位：分）
data.nodeDataMap.BottomBar.p.priceItemList[].amountText → 费用明细显示文本（如 "¥153.75"）
```

### 当前数据快照（建议同步修改）

```
data.currentData.totalPayAmount → 单位：分
data.currentData.roomFeeAmount → 单位：分
data.currentData.cashRoomFeeAmount → 单位：分
```

### 其他组件

```
data.nodeDataMap.PromotionDiscountCard.p.priceVO.totalPayAmount → 优惠卡片中的总价
data.nodeDataMap.PromotionDiscountCard.p.priceVO.roomFeeAmount → 优惠卡片中的房费
data.nodeDataMap.InsuranceTying.p.forwardedParams.salePrice → 保险组件的售价
data.nodeDataMap.HfeHotelSubmitPrePay.p.orderAmount → 预付组件的订单金额
```

## 操作示例

```bash
# 修改底部栏总价为 ¥0.01（1 分）
python3 scripts/cli.py mock patch-field --mock-id <mockId> --field "data.nodeDataMap.BottomBar.p.totalPayAmount" --value "1"
python3 scripts/cli.py mock patch-field --mock-id <mockId> --field "data.nodeDataMap.BottomBar.p.roomFeeAmount" --value "1"
python3 scripts/cli.py mock patch-field --mock-id <mockId> --field "data.nodeDataMap.BottomBar.p.cashRoomFeeAmount" --value "1"

# 同步修改 currentData
python3 scripts/cli.py mock patch-field --mock-id <mockId> --field "data.currentData.totalPayAmount" --value "1"
python3 scripts/cli.py mock patch-field --mock-id <mockId> --field "data.currentData.roomFeeAmount" --value "1"
python3 scripts/cli.py mock patch-field --mock-id <mockId> --field "data.currentData.cashRoomFeeAmount" --value "1"

# 修改后必须重新加载页面（scheme 跳转）才能看到变化
python3 scripts/cli.py open-url --url "<目标scheme>"
```

## 如何定位其他组件的字段

当需要 Mock 其他组件的数据时，可以通过以下方式定位字段路径：

```bash
# 获取当前 Mock 的完整 response
python3 scripts/cli.py mock get --mock-id <mockId>

# 用 Python 搜索关键词（如价格、文案等）
python3 -c "
import json
with open('response.json') as f:
 data = json.load(f)
resp = json.loads(data['data']['response'])
def find(obj, keyword, path=''):
 if isinstance(obj, str) and keyword in obj:
 print(f'{path} = {obj}')
 elif isinstance(obj, dict):
 for k, v in obj.items():
 find(v, keyword, f'{path}.{k}')
 elif isinstance(obj, list):
 for i, v in enumerate(obj):
 find(v, keyword, f'{path}[{i}]')
find(resp, '关键词')
"
```

## 注意事项

1. **单位是分不是元**：nodeDataMap 中的金额字段（如 `totalPayAmount`）单位为**分**（整数），1 = ¥0.01，15375 = ¥153.75。而顶层 `data.totalPrice` 单位为**元**（浮点数）。
2. **显示文本字段**：`priceItemList[].amountText` 等带 `Text` 后缀的字段是前端直接显示的字符串（如 `"¥153.75"`），修改它不会联动其他计算逻辑，仅影响展示。
3. **修改后必须刷新页面**：`patch-field` 修改的是服务端 Mock 规则的 response 模板，已加载的页面不会自动更新，需要通过 scheme 重新跳转触发接口重新请求。
4. **组件名来源**：nodeDataMap 的 key（如 `BottomBar`、`PromotionDiscountCard`）对应 DUO 协议 `struct` 中定义的组件节点 `n` 字段，不同页面的组件名不同，需从 response 中确认。
