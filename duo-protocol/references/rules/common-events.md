# 常见事件规则

DUO 页面交互通过事件系统实现。`on('event') { }` 内可用指令**只有 5 个**：`callMethod` / `transparentArg` / `props` / `condition` / `lock`。

## 一、事件机制

| 机制 | 真实写法 | 说明 |
|------|---------|------|
| 事件监听 | `on('onKeyBoardShow') { ... }` | 节点内监听交互或生命周期事件；同名事件可声明多个，按声明顺序触发 |
| 跨节点调用 | `callMethod('GuestCard', 'onKeyBoardShow')` | `callMethod(目标节点名, 目标方法名)` |
| 透传参数 | `transparentArg('y', 'y')` | 事件回调参数 → 目标方法入参；空映射会被 builder 保留为 `{from: '', to: ''}`，不配置则是不生成该项 |
| 事件附加入参 | `props { string('k') {{ 'v' }} }` | 触发时携带的静态额外参数，写法与 node 级 `props` 相同 |
| 条件 | `condition {{ ... }}` | 事件生效条件（Boolean 表达式） |
| 加锁 | `lock true` | update/submit 执行中不响应本事件，防重复触发（默认 `false`） |
| 双向绑定 | ⚠️ **不在这里** | `updateBy` 必须写在 `propConfig('field') { }` 内，见 §三 |

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

`updateBy` **不是独立声明，也不能裸写**。它必须写在 `propConfig('字段名') { }` 块内，而 `propConfig` 必须与 `props` **同级**（都是 `node` 的直接子块）：

```groovy
node('GuestCard', '706') {
  props {
    number('checkInPeriod') {{ ... }}
    number('adultNum') {{ ... }}
  }                              // ← props 先闭合
  // ✅ 每个字段一个 propConfig 块，与 props 同级
  propConfig('checkInPeriod') {
    updateBy 'onChangeHourPeriod'   // 该事件触发后重算 checkInPeriod
  }
  propConfig('adultNum') {
    updateBy 'onChangeGuestInfo'
    isRequestArg true               // update 时把当前值作为请求参数提交给后端
    lock true                       // 请求进行中不触发双向绑定
  }
}
```

> ❌ **两种禁止写法**（都会导致协议解析失败 / 绑定不生效）：
> 1. 字段声明后直接跟裸 `updateBy 'onChangeXxx'`（没有 `propConfig` 包裹）；
> 2. 把 `propConfig('xxx') { }` 块写进 `props { }` 里面。
>
> 这两种写法 **Groovy 语法都合法**，语法校验抓不到，只能靠块层级核对。

**排查 update 无变化**：
0. **先确认 `propConfig` 是否被误嵌进 `props { }` 内，或 `updateBy` 是否裸写在 node/props 里** —— 最隐蔽的一类，语法合法但解析失败
1. 是否配置了 `updateBy`（且确实在 `propConfig` 块内）
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
2. 用 `on(...)` + `updateBy` 实现联动（`on` 里 `callMethod` 跳 Lifecycle 触发 update，`propConfig.updateBy` 完成字段回写）
3. 跨节点用 `callMethod`
4. 改完确认链路未断（尤其别改掉其它字段依赖的 `updateBy`）
5. 涉及 submit 前端逻辑要确认 `logics/submit.*` 事件未受影响
6. 防重复触发（提交、连点）用**事件级** `lock true`，不要和 `propConfig.lock` 混淆：前者锁事件，后者锁字段双向绑定
