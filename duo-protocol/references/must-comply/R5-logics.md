# 逻辑配置文档 logics.groovy

[示例参考](../../examples/duo-page-demo/logics.groovy)

## 目录

- [一、生命周期概述](#一生命周期概述) — preview/update/submit 三个阶段
- [二、生命周期物料](#二生命周期物料) — @meishi/common-duo-lifecycle（materialId: 13）
- [三、生命周期回调事件](#三生命周期回调事件) — 完整回调列表、回调参数类型
- [四、logics.groovy 编写规范](#四logicsgroovy-编写规范) — 基本结构、触发 update、触发 submit
- [五、数据源异常处理配置](#五数据源异常处理配置) — preview/update 异常处理、submit 异常处理
- [六、常用场景示例](#六常用场景示例) — 设置标题、跳转结果页、update 失败提示、完整提单页配置
- [七、注意事项](#七注意事项) — 回调参数获取、锁机制、取消原因、数据源使用

## 一、生命周期概述

DUO 页面有三个生命周期阶段：

| 生命周期 | 说明 |
|---------|------|
| `preview` | 用户打开页面，触发加载接口 |
| `update` | 用户交互（点选操作），触发更新 |
| `submit` | 用户确认提交，触发提交接口 |

> update、submit 为可选，纯展示页面可以没有更新或提交。

## 二、生命周期物料

使用 `@meishi/common-duo-lifecycle` 物料（materialId: 13）：

`dependencies.json`：

```json
{
  "name": "@meishi/common-duo-lifecycle",
  "version": "1.1.0",
  "type": "logic",
  "url": "https://s3plus-bj02.sankuai.com/yooz-assets/logic/@meishi/common-duo-lifecycle/1.1.0/index.js"
}
```

`componentsMap.json`：

```json
"13": {
  "id": "19422",
  "materialType": "proCode",
  "type": "logic",
  "npm": "@meishi/common-duo-lifecycle",
  "npmVersion": "1.1.0",
  "web": ["https://s3plus-bj02.sankuai.com/yooz-assets/logic/@meishi/common-duo-lifecycle/1.1.0/index.js"]
}
```

## 三、生命周期回调事件

### 3.1 完整回调列表

| 生命周期 | 回调事件 | 说明 |
|---------|---------|------|
| preview | `preview.onResponse` | preview 回调，业务成功或失败都会执行 |
| preview | `preview.onSuccess` | preview 业务成功回调 |
| preview | `preview.onFail` | preview 业务失败回调 |
| preview | `preview.onCancel` | preview 取消回调 |
| update | `update.onEngineFail` | update 引擎失败回调 |
| update | `update.onResponse` | update 回调，业务成功或失败都会执行 |
| update | `update.onSuccess` | update 业务成功回调 |
| update | `update.onFail` | update 业务失败回调 |
| submit | `submit.onEngineFail` | submit 引擎失败回调 |
| submit | `submit.onResponse` | submit 回调，业务成功或失败都会执行 |
| submit | `submit.onSuccess` | submit 业务成功回调 |
| submit | `submit.onFail` | submit 业务失败回调 |

### 3.2 回调参数类型

```typescript
interface CallbackArg {
  // 是否业务失败
  isError?: boolean;
  // 业务错误信息
  errorMsg?: string;
  // 额外信息
  extra?: any;
  // submit 成功时的数据（仅 submit 回调有）
  data?: any;
}
```

## 四、logics.groovy 编写规范

### 4.1 基本结构

> 导入生命周期物料（materialId: 13）

```groovy
node('LifecycleLogic', '13') {
  label '页面生命周期逻辑'

  props {
    string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
    string('activityId') {{ PAGE_QUERY?.activityId ?: '' }}
    string('userId') {{ COMMON_PARAMS.userInfo?.userId ?: '' }}
    string('token') {{ COMMON_PARAMS.userInfo?.token ?: '' }}
  }

  on('preview.onResponse') {
    callMethod('EventNavLogic', 'setWebDocumentTitle')
    props {
      string('title') {{ '页面标题' }}
    }
  }

  on('submit.onSuccess') {
    callMethod('EventNavLogic', 'navigateTo')
    props {
      string('url') {{ "/result?orderId=${DATA_SOURCE?.data?.orderId ?: ''}" }}
    }
  }
}
```

### 4.2 触发 update

在组件上配置按钮点击时触发 update：

```groovy
node('SubmitButton', '37') {
  label '提交按钮'
  props {
    string('type') {{ 'primary' }}
    string('text') {{ '确认提交' }}
  }
  on('onPress') {
    callMethod('LifecycleLogic', 'submit')
  }
}
```

### 4.3 触发 submit

```groovy
node('SubmitButton', '37') {
  label '提交按钮'
  on('onPress') {
    callMethod('LifecycleLogic', 'submit')
  }
}
```

## 五、数据源异常处理配置

### 5.1 preview/update 异常处理

在 `dataSourceMap.groovy` 中配置：

```groovy
dataSource {
  dataSourceId '10'

  bizRespStatus {
    bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '请求失败' }}
  }
}
```

### 5.2 submit 异常处理

```groovy
dataSource {
  dataSourceId '10'

  submitBizRespStatus {
    bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '提交失败' }}
  }
}
```

## 六、常用场景示例

### 6.1 页面加载设置标题

```groovy
node('PageLifecycle', '13') {
  label '页面生命周期'
  props {
    string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
  }
  on('preview.onResponse') {
    callMethod('EventNav', 'setWebDocumentTitle')
    props {
      string('title') {{ DATA_SOURCE?.data?.dealInfo?.title ?: '默认标题' }}
    }
  }
}
```

### 6.2 提交成功跳转结果页

```groovy
node('PageLifecycle', '13') {
  label '页面生命周期'
  on('submit.onSuccess') {
    callMethod('EventNav', 'navigateTo')
    props {
      string('url') {{ "/order/result?orderId=${DATA_SOURCE?.data?.orderId ?: ''}" }}
    }
  }
}
```

### 6.3 update 失败提示

```groovy
node('PageLifecycle', '13') {
  label '页面生命周期'
  on('update.onFail') {
    callMethod('EventNav', 'showToast')
    props {
      string('message') {{ '更新失败，请重试' }}
      string('type') {{ 'error' }}
    }
  }
}
```

### 6.4 完整的提单页生命周期配置

```groovy
node('TicketSubmitEventNav', '90') {
  label '导航API'
}

node('TicketSubmitLifecycle', '13') {
  label '页面生命周期逻辑'
  props {
    string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
    string('activityId') {{ PAGE_QUERY?.activityId ?: '' }}
    string('userId') {{ COMMON_PARAMS.userInfo?.userId ?: '' }}
    string('token') {{ COMMON_PARAMS.userInfo?.token ?: '' }}
  }

  on('preview.onResponse') {
    callMethod('TicketSubmitEventNav', 'setWebDocumentTitle')
    props {
      string('title') {{ '门票提单' }}
    }
  }

  on('submit.onSuccess') {
    callMethod('TicketSubmitEventNav', 'navigateTo')
    props {
      string('url') {{ "/ticket/order/result?orderId=${DATA_SOURCE?.data?.orderId ?: ''}" }}
    }
  }
}
```

## 七、注意事项

1. **回调参数获取**：在 `on` 回调中，可以使用回调参数中的 `isError`、`errorMsg`、`extra`、`data` 等字段。

2. **锁机制**：默认开启锁，如果有待处理请求，新请求会被阻止。

3. **取消原因**：`onCancel` 回调参数 `cancelReasonType` 可能的值：
   - `DebouncePending`：debounce 等待中被取消
   - `Locked`：被锁机制阻止
   - `Invalid`：响应过期被舍弃
   - `PageClosed`：页面已关闭

4. **数据源使用**：
   - `preview.onSuccess`/`preview.onFail` 无法直接获取业务数据源数据
   - `submit.onSuccess` 可以通过 `data` 字段获取业务数据

## 参考文档
https://km.sankuai.com/collabpage/1735774570
