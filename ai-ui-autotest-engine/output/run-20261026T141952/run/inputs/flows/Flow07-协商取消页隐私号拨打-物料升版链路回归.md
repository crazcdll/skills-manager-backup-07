# Flow07 · 协商取消页隐私号拨打-物料升版链路回归

<!-- caseId = 4210292 -->

> 关联 EC 用例：4210292（P0：【协商取消页】隐私号拨打-物料升版链路-拨打正常）
> 执行类型：data-dependent
> 前置条件：协商取消场景订单；IMModal 0.0.11 → privacy-phone 1.0.8 物料链路已部署至测试环境（锁包：协商取消页接入分支）；美团App / 点评App

> 测试数据参考：使用协商取消场景订单（见 workspace `testplan/testdata.md` 订单 #2）；协商取消场景由 AppMock 规则 19538157 / 19538201 开启（人工确认提供）

## 落地入口

```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-order-detail&mrn_component=hotelchannel-order-detail&order_id={negotiation_order_id}&biz_type=1
```

> {negotiation_order_id} 为协商取消场景订单；落地后经订单详情页取消入口进入协商取消页（导航路径以页面实际入口为准）。

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

### S2. IM 联系入口唤起隐私号弹窗

**操作**：点击「联系酒店」。

**等待**：IM 联系入口/隐私号弹窗展示。

**校验**：
- 弹窗正常唤起（验证 IMModal 0.0.11 → privacy-phone 1.0.8 升版链路生效） — 视觉确认
- 「双卡双待请确认，系统呼出号码和下方一致」 — 文案断言

**接口断言**：`POST /hotelorder/v1/queryuserinfo.json`
- error.code=200，data.maskMobile 正常返回

### A1. queryuserinfo 接口返回校验

- 接口 `POST https://apihotel.meituan.com/hotelorder/v1/queryuserinfo.json` 返回 error.code=200

### S3. 点击立即呼叫验证拨打链路

**操作**：点击「立即呼叫」。

**等待**：系统拨号呼出。

**校验**：
- 隐私号呼叫正常发起 — 视觉确认

**接口断言**：`POST /hotelorder/v1/bindvirtualnumber.json`
- 绑定虚拟号成功后发起呼出

### A2. bindvirtualnumber 接口返回校验

- 接口 `POST https://apihotel.meituan.com/hotelorder/v1/bindvirtualnumber.json` 调用成功（error.code=200）

**证据要求**：截图或录屏记录呼叫发起

### S4. 再次唤起弹窗点击取消

**操作**：点击「联系酒店」。

**等待**：弹窗展示。

**校验**：
- 「将使用该号码加密呼出」 — 渲染就绪标志

### S5. 点击取消关闭弹窗

**操作**：点击「取消」。

**等待**：弹窗关闭。

**校验**：
- 「将使用该号码加密呼出」消失 — 文案消失
- 无因升版引入的回归异常（报错/布局错乱） — 视觉确认

> 备注：取号失败降级直拨真实号场景依赖取号失败 Mock 环境（无明确规则 ID，不启用 Mock），在执行报告中标注人工验证或按 Flow04 场景 C 环境复用结果。
