# Flow08 · 语义化文本输入与锚点定位

> 执行类型：deterministic

测试 `input-text` 语义模式（`{"anchor":"...","text":"..."}`），覆盖锚点在视口内、视口外、未命中三种场景下的 Hook 路由流程。

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 锚点在视口内 → 直接输入

**操作**：在入住人姓名输入框中输入中文姓名。

**等待**：输入完成。

**校验**：
- 输入框回显输入的姓名 — 视觉确认

**数据**：`{"anchor":"姓名","text":"张三"}`

**说明**：锚点「姓名」在视口内可点击，`inspect_tree_find_center` 精确命中 → 清空 → 聚焦 → 输入，全程无 Hook 介入。

### S2. 锚点在视口外 → resolve_target_viewport Hook

**操作**：在页面底部的备注输入框中输入文字（锚点初始在视口外）。

**等待**：滚动完成，输入框可见并输入完成。

**校验**：
- 输入框回显输入的文字 — 视觉确认

**数据**：`{"anchor":"备注","text":"请安排高楼层"}`

**Hook 路径**：`input-text` → `TEXT_OUT_OF_VIEWPORT` → `resolve_target_viewport` Hook
→ AI 读截图确认目标位置 → 执行 `scroll-until` 或手动滚动 → 重试 input-text → 输入成功

### S3. 锚点文案不匹配 → resolve_missing_target Hook

**操作**：在手机号输入框中输入号码（锚点文案与页面不完全一致）。

**等待**：经 AI 语义匹配后定位成功，输入完成。

**校验**：
- 输入框回显输入的号码 — 视觉确认

**数据**：`{"anchor":"手机号码","text":"13800138000"}`（页面实际文案为"手机号"）

**Hook 路径**：`input-text` → `TEXT_NOT_FOUND` → `resolve_missing_target` Hook
→ AI 读截图 + sidecar → 发现"手机号"是匹配锚点 → 使用 `find-text` 确认坐标 → 重试 input-text → 输入成功

### S4. 输入框失焦后重聚焦

**操作**：输入完成后使用 `blur-input` 使输入框失焦，再重新点击聚焦。

**等待**：失焦完成，键盘收起。再次聚焦，键盘弹出。

**校验**：
- 输入框内容保留，光标重新出现 — 视觉确认