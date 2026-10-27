# Probe · 隐私号浮层唤起探针

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-order-detail&mrn_component=hotelchannel-order-detail&order_id=5035036077836749951&biz_type=1
```

## 执行步骤

### S1. 落地订单详情

**操作**：无（通过 Scheme 进入页面）。

**等待**：页面加载完成。

**校验**：
- 「联系酒店」— 文案断言（部分匹配）
