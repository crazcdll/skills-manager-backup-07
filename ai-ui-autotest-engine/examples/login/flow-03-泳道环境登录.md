# Flow03 · 泳道环境登录

> 执行类型：deterministic

## 可测性环境

| 项 | 值 |
|----|----|
| 覆盖范围 | 泳道环境验证码登录 → 泳道切换 → 提单页正常加载 |
| AppMock | `16305525`（自动化测试：preview 接口 Mock，泳道环境下提单页必需） |
| 泳道名 | `sunhuace-bszge`（自动化测试泳道，缺省走线上环境） |
| 泳道 URL | `/*`（全量路由到泳道） |

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