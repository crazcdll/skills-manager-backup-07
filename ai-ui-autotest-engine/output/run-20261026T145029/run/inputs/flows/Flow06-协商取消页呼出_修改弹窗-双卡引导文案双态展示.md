# Flow06 · 协商取消页呼出/修改弹窗-双卡引导文案双态展示

<!-- caseId = 4210291 -->

> 关联 EC 用例：4210291（P1：【协商取消页】呼出/修改弹窗-双卡引导文案-双态展示）
> 执行类型：data-dependent
> 前置条件：存在协商取消场景订单（已进入协商取消流程），协商取消页联系酒店入口可用；美团App / 点评App；协商取消页经 IMModal 0.0.11 → privacy-phone 1.0.8 物料链路生效

> 测试数据参考：使用协商取消场景订单（见 workspace `testplan/testdata.md` 订单 #2：hotel-create-order 生成订单后做协商取消状态扭转）；协商取消场景由 AppMock 规则 19538157 / 19538201 开启（人工确认提供）

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-order-detail&mrn_component=hotelchannel-order-detail&order_id={negotiation_order_id}&biz_type=1
```

> {negotiation_order_id} 为协商取消场景订单；落地后经订单详情页取消入口进入协商取消页（导航路径以页面实际入口为准，数据依赖见 S1）。

## 可测性环境

| 项 | 值 |
|----|----|
| AppMock | `19538157`（协商取消场景：订单协商取消态，人工提供规则 ID） |
| AppMock | `19538201`（协商取消场景：协商取消页可达数据，人工提供规则 ID） |

> 上表规则 ID 由人工在 Issue 评论中明确提供（appmock.sankuai.com mockDetail/19538157、19538201），声明即启用。

## 执行步骤

### S1. 从订单详情页进入协商取消页

**操作**：点击「取消订单」。

**等待**：取消流程页面展示（协商取消页可达）。

**校验**：
- 协商取消页展示 — 视觉确认

> 备注：协商取消页入口与导航路径依赖订单协商状态，若「取消订单」入口不可达，由执行引擎/人工按协商取消场景订单实际路径进入。

### S2. 协商取消页点击联系酒店唤起呼出弹窗

**操作**：点击「联系酒店」。

**等待**：号码呼出弹窗展示。

**校验**：
- 「将使用该号码加密呼出」 — 渲染就绪标志
- 「双卡双待请确认，系统呼出号码和下方一致」 — 文案断言
- 「双卡双待请确认，系统呼出号码和下方一致」位于弹窗标题正下方 — 视觉确认

**接口断言**：`POST /hotelorder/v1/queryuserinfo.json`
- error.code=200，data.maskMobile 正常返回

### A1. queryuserinfo 接口返回校验

- 接口 `POST https://apihotel.meituan.com/hotelorder/v1/queryuserinfo.json` 返回 error.code=200

### S3. 进入修改号码流程查看编辑态弹窗文案

**操作**：点击「非本机号请修改」。

**等待**：编辑态弹窗展示。

**校验**：
- 「输入本机号码」 — 文案断言
- 「双卡双待请确认，系统呼出号码和下方一致」 — 文案断言
- 「请输入本机号码」 — 文案断言

**证据要求**：协商取消页展示态/编辑态弹窗各截图一张，供样式走查对照 UI 稿 https://imd.sankuai.com/goto/WXY9Zrqp

### S4. 关闭弹窗

**操作**：点击「取消」。

**等待**：弹窗关闭。

**校验**：
- 「输入本机号码」消失 — 文案消失
