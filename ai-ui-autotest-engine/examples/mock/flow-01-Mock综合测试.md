# Flow01 · Mock 综合测试

> 执行类型：data-dependent

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. Mock 数据下页面加载

**操作**：无（通过 Scheme 进入页面，AppMock 已生效）。

**等待**：页面加载完成。

**校验**：
- 「房型详情」— 渲染就绪标志

**接口断言**：
- POST /api/hotel/orderfill/preview — 接口返回 Mock 数据，响应中的商品价格与 Mock 配置的预期值一致

### S2. Mock 环境下弹窗内容验证

**操作**：点击「房型详情」。

**等待**：弹窗加载完成。

**校验**：
- 「房型设施详情」— 渲染就绪标志

**接口断言**：
- POST /api/hotel/orderfill/queryGoodsDetail — 接口返回 Mock 数据，房型列表和价格与 Mock 配置一致

### S3. 关闭弹窗验证 Mock 数据一致性

**操作**：关闭弹窗。

**等待**：弹窗关闭。

**校验**：
- 「房型设施详情」消失 — 文案消失

**接口断言**：
- POST /api/hotel/orderfill/preview — 再次请求该接口，确认 Mock 数据稳定，未因弹窗操作而变更