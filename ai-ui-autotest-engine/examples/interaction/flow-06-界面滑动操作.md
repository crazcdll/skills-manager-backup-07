# Flow06 · 界面滑动操作

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 页面加载确认

**操作**：无（通过 Scheme 进入页面）。

**等待**：页面加载完成。

**校验**：
- 「房型详情」— 渲染就绪标志

### S2. 横向滑动查看

**操作**：横向滑动。

**等待**：滑动动画完成。

**校验**：
- 内容区域发生横向滚动，布局正常 — 视觉确认

### S3. 纵向滑动查看

**操作**：纵向滑动。

**等待**：滑动动画完成。

**校验**：
- 页面内容随滑动更新 — 视觉确认