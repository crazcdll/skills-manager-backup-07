# Flow03 · 埋点事件验证

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 页面曝光埋点

**操作**：无（通过 Scheme 进入页面）。

**等待**：页面加载完成。

**校验**：
- 「房型详情」— 渲染就绪标志

**埋点断言**：
- PV 事件 c_hotel_createorder_unified — 页面曝光时触发，事件参数包含页面来源、商品 ID

### S2. 点击房型详情触发 MC 埋点

**操作**：点击「房型详情」。

**等待**：弹窗加载完成。

**校验**：
- 「房型设施详情」— 渲染就绪标志

**埋点断言**：
- MC 事件 b_hotel_wb663p9r_mc — 点击「房型详情」时触发，事件参数包含弹窗来源入口名称

### S3. 关闭弹窗

**操作**：关闭弹窗。

**等待**：弹窗关闭。

**校验**：
- 「房型设施详情」消失 — 文案消失