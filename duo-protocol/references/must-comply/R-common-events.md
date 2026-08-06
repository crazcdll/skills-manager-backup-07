# DUO 事件配置

[参考示例 struct](../../examples/duo-page-demo/struct.groovy)
[参考示例 logic](../../examples/duo-page-demo/logics.groovy)

## 一、功能说明

组件 B 需要对外暴露方法供其他组件（以组件 A 为例）调用时，可以通过 DUO 进行配置。

## 二、事件配置步骤

### 2.1 组件 B 实现方法

1. **proCode 函数式组件**：需要使用 `forwardRef` + `useImperativeHandle()` hooks 对外主动暴露方法
2. **proCode 类组件** 或 **lowCode 组件**：正常编写 method 即可

### 2.2 声明对外暴露方法

#### lowCode 组件

选择组件根节点 → 高级 → 勾选要暴露的方法名。这会在生成的组件描述协议 For DUO 中生成该方法的描述。

#### proCode 组件

在 DUO 组件描述协议（description.json）中增加：

```json
{
  "events": {
    "on": ["onTest"]
  }
}
```

### 2.3 组件 A 配置回调

1. 组件 A 的入参中增加 `onTestCb`
2. 在组件 A 中通过 `this.props.onTestCb()` 的方式调用

### 2.4 DUO 平台配置

在 DUO 配置平台上修改「触发事件」Tab 进行配置。

## 三、参数传递说明

### 3.1 配置事件数据方式

在 `onTest` 方法中收到的参数为：

非 MRN 侧：

```json
{"props": "test"}
```

MRN 侧（都会注入 rootTag）：

```json
{"props": "test", "rootTag": 21}
```

### 3.2 透传参数方式

#### 展开形式传参

组件 A 调用时传参方式为展开形式：
```javascript
this.props.onTestCb(1, 2, 3)
```

组件 B 的 `onTest` 收到的参数为：

MRN 侧：

```json
{"c": 3, "obj": {"a": 1, "b": 2}, "props": "test", "rootTag": 21}
```

非 MRN 侧：

```json
{"c": 3, "obj": {"a": 1, "b": 2}, "props": "test"}
```

#### 对象形式传参

组件 A 调用时传参方式为对象形式：
```javascript
this.props.onTestCb({ title: 'a', name: 'b' })
```

组件 B 的 `onTest` 收到的参数为：

MRN 侧：

```json
{"obj": {"title": "a"}, "props": "test", "rootTag": 41}
```

非 MRN 侧：

```json
{"obj": {"title": "a"}, "props": "test"}
```

#### 透传整个对象参数

组件 B 的 `onTest` 收到的参数为：

MRN 侧：

```json
{"name": "b", "title": "a", "props": "test", "rootTag": 41}
```

非 MRN 侧：

```json
{"name": "b", "title": "a", "props": "test"}
```

## 四、参数传递原理

DUO 配置「来源」、「目标」支持 JSONPath 格式，调用方可以合并传参或分开传参，接收方只能合并收到参数。

```javascript
// from: 来源，to: 目标，args 为入参 ...args
const value = !from ? args : /^\d/.test(from) ? get(args, from) : get(args, from);
if (!to) {
  props = {
    ...props,
    ...value
  };
} else {
  props = set(props, to, value);
}
```

## 五、struct.groovy 中的事件配置

### 5.1 基本语法

> `on` 块内通过 `callMethod` 调用其他节点的方法，`props` 为附加入参（可选）

```groovy
node('ButtonNode', '37') {
  label '按钮'
  props {
    string('text') {{ '点击' }}
  }
  on('onPress') {
    callMethod('TargetNode', 'methodName')
    props {
      string('param1') {{ 'value1' }}
      number('param2') {{ 123 }}
    }
  }
}
```

### 5.2 调用生命周期方法

```groovy
node('SubmitButton', '37') {
  label '提交按钮'
  on('onPress') {
    callMethod('LifecycleLogic', 'submit')
  }
}
```

### 5.3 调用导航方法

```groovy
node('BackButton', '37') {
  label '返回按钮'
  on('onPress') {
    callMethod('EventNav', 'navigateBack')
  }
}
```

### 5.4 带参数调用

```groovy
node('ActionBtn', '37') {
  label '操作按钮'
  on('onPress') {
    callMethod('TargetNode', 'handleAction')
    props {
      string('action') {{ 'click' }}
      number('value') {{ DATA_SOURCE?.data?.count ?: 0 }}
    }
  }
}
```

## 六、常见事件类型

### 6.1 按钮事件

| 事件名　　　　| 说明　　 |
| ---------------| ----------|
| `onPress`　　 | 点击事件 |
| `onLongPress` | 长按事件 |

### 6.2 输入事件

| 事件名 | 说明 |
|-------|------|
| `onChange` | 值变化事件 |
| `onFocus` | 获得焦点 |
| `onBlur` | 失去焦点 |

### 6.3 列表事件

| 事件名 | 说明 |
|-------|------|
| `onItemClick` | 列表项点击 |
| `onLoadMore` | 加载更多 |

### 6.4 Stepper 计数器事件

| 事件名 | 说明 | 参数 |
|-------|------|------|
| `onMinusPress` | 减少按钮点击 | `disabled: Boolean` |
| `onPlusPress` | 增加按钮点击 | `disabled: Boolean` |
| `onInputValueChange` | 输入值变化 | `value: Number`, `isValid: Boolean` |

## 七、注意事项

1. **MRN 侧会自动注入 `rootTag`**：在处理参数时需要注意这个额外字段。

2. **参数合并**：调用方可以分开传参，但接收方只能合并收到参数。

3. **方法必须先声明**：proCode 组件需要在 `description.json` 中声明 `events.on`，lowCode 组件需要在根节点勾选暴露的方法。

4. **双向绑定**：使用 `propConfig` 配合事件实现双向绑定：

5. **参数锁定**：使用 `lock` 属性可以锁定参数的更新。


```groovy
node('StepperNode', '265') {
  propConfig('value') {
    updateBy 'onInputValueChange'
    isRequestArg true
    lock true 
  }
}
```

## 参考文档

https://km.sankuai.com/collabpage/2592258233
