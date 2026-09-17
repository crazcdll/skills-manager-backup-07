# Flow03 · 滚动操作与页面加载

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 滚动到底部

**操作**：滚动到底部。

**等待**：滚动动画完成。

**校验**：
- 「没有更多了」— 文案断言
- 「购买须知」— 文案断言

### S2. 滚动到入住人模块

**操作**：滚动到「入住人」。

**等待**：目标区域可见。

**校验**：
- 「入住人」— 文案断言