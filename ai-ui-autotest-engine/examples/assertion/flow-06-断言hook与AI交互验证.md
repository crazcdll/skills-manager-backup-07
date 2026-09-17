# Flow06 · 断言 Hook 与 AI 交互验证

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. visual 断言 hook 流程

**操作**：点击「房型详情」，打开弹窗。

**等待**：弹窗动画完成。

**校验**：
- 「房型详情」弹窗从底部滑入，内容完整展示 — 视觉确认

### S2. 文本断言匹配结果确认 hook

**操作**：无（已在弹窗中）。

**等待**：内容渲染完成。

**校验**：
- 「房型设施详情」— 文案断言

### S3. 关闭弹窗

**操作**：关闭弹窗。

**等待**：弹窗关闭。

**校验**：
- 弹窗已关闭 — 视觉确认

### S4. 滚动到底部

**操作**：滚动到底部。

**等待**：动态内容加载完成。

**校验**：
- 「没有更多了」— 文案断言
- 「购买须知」— 文案断言