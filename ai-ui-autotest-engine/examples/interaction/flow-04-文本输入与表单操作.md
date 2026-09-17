# Flow04 · 文本输入与表单操作

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 滚动到入住人模块

**操作**：滚动到「入住人」。

**等待**：目标区域可见。

**校验**：
- 「入住人」— 文案断言

### S2. 输入入住人姓名

**操作**：点击姓名输入框，输入中文姓名。

**等待**：输入完成。

**校验**：
- 输入框回显输入的姓名 — 视觉确认

### S3. 输入手机号

**操作**：点击手机号输入框，输入 11 位手机号。

**等待**：输入完成。

**校验**：
- 输入框回显输入的手机号 — 视觉确认