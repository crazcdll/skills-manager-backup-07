# Flow02 · 异常流程与跳过终止

> 执行类型：data-dependent

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-orderfill-duo&mrn_component=main&goods_id=1172344601&checkinDate={T+10:%Y-%m-%d}&checkoutDate={T+11:%Y-%m-%d}&biz_type=1&room_num=1
```

## 执行步骤

### S1. 页面加载确认

**操作**：无（通过 Scheme 进入页面）。

**等待**：页面加载完成。

**校验**：
- 「房型详情」— 渲染就绪标志

### S2. 断言失败场景

**操作**：无（已在页面）。

**等待**：页面渲染完成。

**校验**：
- 「这是一个绝对不存在的文案」— 文案断言（预期失败：验证断言失败后跳过机制）

### S3. 打开弹窗

**操作**：点击「房型详情」。

**等待**：弹窗加载完成。

**校验**：
- 「房型设施详情」— 渲染就绪标志

### S4. 关闭弹窗

**操作**：关闭弹窗。

**等待**：弹窗关闭。

**校验**：
- 「房型设施详情」消失 — 文案消失