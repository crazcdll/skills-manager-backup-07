# Flow01 · 线上环境登录

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 提单页加载确认

**操作**：无（已在页面）。

**等待**：页面加载完成。

**校验**：
- 「房型详情」— 渲染就绪标志
- 「订房必读」— 文案断言