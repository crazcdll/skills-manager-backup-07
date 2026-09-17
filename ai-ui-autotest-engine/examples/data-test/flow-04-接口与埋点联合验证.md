# Flow04 · 接口与埋点联合验证

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 页面加载 → 接口 + 曝光埋点

**操作**：无（通过 Scheme 进入页面）。

**等待**：页面加载完成。

**校验**：
- 「房型详情」— 渲染就绪标志

**接口断言**：
- POST /hotelorder/trade/precreate/preview — 页面加载时触发，响应状态码为 200，商品信息完整

**埋点断言**：
- PV 事件 c_hotel_createorder_unified — 页面曝光时触发，事件参数包含页面来源

### S2. 点击房型详情 → 接口 + 点击埋点

**操作**：点击「房型详情」。

**等待**：弹窗加载完成。

**校验**：
- 「房型设施详情」— 渲染就绪标志

**接口断言**：
- GET /productapi/v3/prepayGoodDetail — 弹窗加载时触发，响应包含房型列表和设施信息

**埋点断言**：
- MC 事件 b_hotel_wb663p9r_mc — 点击「房型详情」时触发，事件参数包含弹窗来源入口名称

### S3. 点击费用明细 → 接口 + 曝光埋点

**操作**：点击「已优惠」。

**等待**：弹窗加载完成。

**校验**：
- 「费用明细」— 渲染就绪标志

**接口断言**：
- POST /api/hotel/orderfill/queryPriceDetail — 弹窗加载时触发，响应包含房费、优惠明细

**埋点断言**：
- PV 事件 c_hotel_price_detail_popup — 费用明细弹窗曝光时触发，事件参数包含优惠金额