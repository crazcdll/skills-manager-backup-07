# Flow03 · visual 视觉效果验证

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 弹窗打开动画效果

**操作**：点击「房型详情」。

**等待**：弹窗动画完成。

**校验**：
- 「房型详情」弹窗从底部滑入，内容完整展示，背景有遮罩层 — 视觉确认

### S2. 弹窗关闭动画效果

**操作**：关闭弹窗。

**等待**：弹窗关闭动画完成。

**校验**：
- 弹窗已完全关闭，遮罩消失，页面恢复正常展示 — 视觉确认

### S3. 按钮状态

**操作**：无（已在页面）。

**等待**：页面渲染完成。

**校验**：
- 页面按钮文案和样式展示正常，无异常重叠或错位 — 视觉确认