# Flow01 · 接口请求参数校验

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 页面加载确认参数传递

**操作**：无（通过 Scheme 进入页面）。

**等待**：页面加载完成。

**校验**：
- 「房型详情」— 渲染就绪标志

**接口断言**：
- POST /hotelorder/trade/precreate/preview — 请求参数包含 goods_id、checkinDate、checkoutDate，bizType 为 1，roomNum 为 1

### S2. 点击弹窗触发详情接口

**操作**：点击「房型详情」。

**等待**：弹窗加载完成。

**校验**：
- 「房型设施详情」— 渲染就绪标志

**接口断言**：
- GET /productapi/v3/prepayGoodDetail — 请求参数包含 goodsId，与 S1 中 preview 接口的 goods_id 一致