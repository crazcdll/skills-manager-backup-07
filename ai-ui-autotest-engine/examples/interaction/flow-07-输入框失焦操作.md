# Flow07 · 输入框失焦操作

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 页面加载完成

**操作**：无（通过 Scheme 进入页面）。

**等待**：页面加载完成。

**校验**：
- 「房型详情」— 渲染就绪标志

### S2. 输入入住人姓名

**操作**：点击姓名输入框，输入中文姓名。

**等待**：输入完成。

**校验**：
- 输入框回显输入的姓名 — 视觉确认

### S3. 点击其他区域失焦

**操作**：点击非输入框区域。

**等待**：输入框失焦，键盘收起。

**校验**：
- 输入框光标消失，键盘已收起 — 视觉确认

### S4. 再次聚焦输入框

**操作**：点击姓名输入框。

**等待**：输入框重新聚焦。

**校验**：
- 输入框内容仍保留，光标重新出现 — 视觉确认