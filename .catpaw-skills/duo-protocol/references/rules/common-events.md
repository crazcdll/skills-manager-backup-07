# 常见事件规则

DUO 页面交互通过事件系统实现。核心：`on(...)` 事件监听、`updateBy` 双向绑定、`callMethod` 跨节点调用、`condition` 条件、`props` 参数传递。

## 一、事件机制

| 机制 | 真实写法 | 说明 |
|------|---------|------|
| 事件监听 | `on('onKeyBoardShow') { ... }` | 节点内监听交互或生命周期事件 |
| 跨节点调用 | `callMethod('GuestCard', 'onKeyBoardShow')` | 调用其它节点的实例方法 |
| 双向绑定 | `updateBy 'onChangeHourPeriod'` | 某事件触发后重算绑定字段 |
| 条件 | `condition {{ ... }}` | 事件生效条件 |
| 透传参数 | `transparentArg('key','key')` | 透传事件参数 |

## 二、生命周期事件（logics.groovy）

```groovy
node('MeishiCommonDuoLifecycle1', '13') {
  label '内置物料-页面生命周期'
  on('preview.onResponse') {
    callMethod('Static', 'onPreviewResponse')
    condition {{ !!COMMON_PARAMS.systemInfo.isMRN }}
  }
  on('preview.onSuccess') {
    callMethod('MeishiCommonEventNav1', 'setWebDocumentTitle')
    props {
      string('title') {{ '提交订单' }}
    }
  }
  on('preview.onEngineFail') { ... }
  on('submit.onFail') { ... }
  on('submit.onSuccess') { ... }
}
```

| 生命周期事件 | 说明 |
|-------------|------|
| `preview.onResponse` | preview 响应 |
| `preview.onSuccess` | preview 成功 |
| `preview.onEngineFail` | preview 引擎失败 |
| `submit.onFail` / `submit.onSuccess` | 提交结果 |

## 三、updateBy 双向绑定（struct.groovy）

真实写法（酒店提单页）：
```groovy
// 某字段
number('checkInPeriod') {{ ... }}
updateBy 'onChangeHourPeriod'    // 监听房型变更事件重算

// GuestCard 入住人
updateBy 'onChangePhoneNum'
updateBy 'onChangeGuestInfo'
updateBy 'onChangeCountryCode'
```

**排查 update 无变化**：
1. 是否配置了 `updateBy`
2. 绑定的 `on('xxx')` 事件是否真实触发
3. updateBy 监听的事件名与触发的 `on` 是否一致
4. `PAYLOAD` 入参是否正确传递

## 四、callMethod 跨节点

```groovy
on('onKeyBoardShow') {
  callMethod('GuestCard', 'onKeyBoardShow')
  transparentArg('', '')
}
```
- 第一个参数是目标**节点名**
- 第二个参数是目标节点的**实例方法名**
- 跨节点需确认目标节点存在且实现了该方法

## 五、静态/逻辑节点

- `CommonParams`（酒店757）/ `MeishiCommonDuoParams`（到餐757）：静态公共参数
- `Static` / `Logic` / `LifecycleLogic`：逻辑节点
- 它们**不渲染 UI**，通常承载初始化和逻辑处理

## 六、改事件/交互建议

1. 明确触发源和目标节点
2. 用 `on(...)` + `updateBy` 实现联动
3. 跨节点用 `callMethod`
4. 改完确认链路未断（尤其别改掉其它字段依赖的 `updateBy`）
5. 涉及 submit 前端逻辑要确认 `logics/submit.*` 事件未受影响
