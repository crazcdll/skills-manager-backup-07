# Flow02 · 无文案图标点击与锚点定位

> 执行类型：deterministic

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 减少房间数

**操作**：点击「住客」区域减号按钮。

**等待**：房间数更新。

**校验**：
- 「住客」区域房间数减少 — 视觉确认

### S2. 增加房间数

**操作**：点击「住客」区域加号按钮。

**等待**：房间数更新。

**校验**：
- 「住客」区域房间数增加 — 视觉确认

### S3. 关闭弹窗

**操作**：点击关闭按钮。

**等待**：弹窗关闭。

**校验**：
- 弹窗已关闭，页面恢复正常 — 视觉确认