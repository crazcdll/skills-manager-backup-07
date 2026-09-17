# Flow05 · 断言边界条件与异常场景

> 执行类型：data-dependent

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 价格数字展示验证

**操作**：无（已在页面）。

**等待**：页面加载完成。

**校验**：
- 「¥」价格数字展示正常，数字格式正确 — 视觉确认

### S2. 特殊字符展示验证

**操作**：无（已在页面）。

**等待**：页面渲染完成。

**校验**：
- 页面特殊字符展示正常，无乱码 — 视觉确认

### S3. 日期格式展示验证

**操作**：无（已在页面）。

**等待**：页面渲染完成。

**校验**：
- 页面日期格式数据展示正常，符合预期格式 — 视觉确认