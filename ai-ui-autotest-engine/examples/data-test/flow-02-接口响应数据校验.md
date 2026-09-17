# Flow02 · 接口响应数据校验

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 页面加载确认接口响应正常

**操作**：无（通过 Scheme 进入页面）。

**等待**：页面加载完成。

**校验**：
- 「房型详情」— 渲染就绪标志

**接口断言**：
- POST /hotelorder/trade/precreate/preview — 响应状态码为 200，响应包含商品信息、价格、库存字段，字段值类型正确

### S2. 滚动到底部触发分页接口

**操作**：滚动到底部。

**等待**：动态内容加载完成。

**校验**：
- 「没有更多了」— 文案断言

**接口断言**：
- GET /api/hotel/orderfill/queryComment — 响应状态码为 200，评论列表数据格式正确，分页参数 pageSize 符合预期