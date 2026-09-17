# Flow01 · 批量执行与 Mock 录制

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

**接口断言**：
- POST /api/hotel/orderfill/preview — 接口请求被录制，录制数据包含请求参数和响应

### S2. 打开弹窗验证录制数据

**操作**：点击「房型详情」。

**等待**：弹窗加载完成。

**校验**：
- 「房型设施详情」— 渲染就绪标志

**接口断言**：
- POST /api/hotel/orderfill/queryGoodsDetail — 接口请求被录制，录制数据包含请求参数和响应

### S3. 关闭弹窗

**操作**：关闭弹窗。

**等待**：弹窗关闭。

**校验**：
- 「房型设施详情」消失 — 文案消失