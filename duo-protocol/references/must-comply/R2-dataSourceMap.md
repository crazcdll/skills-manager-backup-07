# 数据源配置 dataSourceMap.groovy

## 目录

- [一、DataSourceConfig 结构](#一datasourceconfig-结构) — currentData/reqProps/bizRespStatus/submitBizRespStatus
- [二、字段说明](#二字段说明) — currentData/reqProps/bizRespStatus/submitBizRespStatus 详细定义
- [三、dataSourceMap.groovy 编写规范](#三datasourcemapgroovy-编写规范) — 基本结构、requestProps/currentData/bizRespStatus/submitBizRespStatus 配置
- [四、常用场景示例](#四常用场景示例) — 简单提单页、额外信息上报、使用 PREV_DATA
- [五、与 1.0 版本差异](#五与-10-版本差异)
- [六、注意事项](#六注意事项)

## 一、DataSourceConfig 结构

```typescript
interface DataSourceConfig {
  // 入参中可能会使用上次的数据源结果，需要在这里定义
  currentData: { [key: string]: DataExpression };
  // 数据源请求入参。只有后端关心，前端不需要解析
  reqProps: { [key: string]: DataExpression };
  // preview/update 数据源响应的业务状态
  bizRespStatus?: DataSourceConfigBizRespStatus;
  // submit 数据源响应的业务状态
  submitBizRespStatus?: DataSourceConfigSubmitBizRespStatus;
}
```

## 二、字段说明

### 2.1 currentData

入参中可能会使用上次的数据源结果，需要在这里定义。用于在入参表达式中引用 `PREV_DATA`。

### 2.2 reqProps / requestProps

数据源请求入参，只有后端关心，前端不需要解析。

> **命名说明**：TypeScript 接口和 JSON 协议中字段名为 `reqProps`；Groovy DSL 代码中对应的关键字为 `requestProps`。两者表示同一概念，只是在不同层面的写法不同。

### 2.3 bizRespStatus

preview/update 数据源响应的业务状态配置：

```typescript
interface DataSourceConfigBizRespStatus {
  // 是否业务失败
  isError?: DataExpression;
  // 业务错误信息
  errorMsg?: DataExpression;
  // preview 失败是否显示 toast
  errorToast?: boolean;
  // 额外信息
  extra?: DataExpression;
  // 异常时，是否不返回 struct
  errorNoReturnStruct?: boolean;
}
```

### 2.4 submitBizRespStatus

submit 数据源响应的业务状态配置：

```typescript
interface DataSourceConfigSubmitBizRespStatus {
  // 是否业务失败
  isError?: DataExpression;
  // 业务错误信息
  errorMsg?: DataExpression;
  // submit 失败是否显示 toast
  errorToast?: boolean;
  // 额外信息
  extra?: DataExpression;
}
```

## 三、dataSourceMap.groovy 编写规范

### 3.1 基本结构

```groovy
dataSource {
  dataSourceId '10'

  requestProps {
    objectWithSub('previewParam') {
      string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
      string('activityId') {{ PAGE_QUERY?.activityId ?: '' }}
      string('userId') {{ COMMON_PARAMS.userInfo?.userId ?: '' }}
      string('token') {{ COMMON_PARAMS.userInfo?.token ?: '' }}
    }
  }

  currentData {
    string('orderId') {{ DATA_SOURCE?.data?.orderId ?: '' }}
    string('dealTitle') {{ DATA_SOURCE?.data?.dealInfo?.title ?: '' }}
  }

  bizRespStatus {
    bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '请求失败' }}
    bool('errorToast') {{ true }}
  }

  submitBizRespStatus {
    bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '提交失败' }}
    bool('errorToast') {{ true }}
  }
}
```

### 3.2 requestProps 入参配置

```groovy
requestProps {
  string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
  number('count') {{ 1 }}

  objectWithSub('userInfo') {
    string('userId') {{ COMMON_PARAMS.userInfo?.userId ?: '' }}
    string('token') {{ COMMON_PARAMS.userInfo?.token ?: '' }}
  }

  list('itemIds') {{ [] }}
}
```

### 3.3 currentData 当前数据定义

```groovy
currentData {
  string('orderId') {{ DATA_SOURCE?.data?.orderId ?: '' }}
  string('dealTitle') {{ DATA_SOURCE?.data?.dealInfo?.title ?: '' }}
  string('poiName') {{ DATA_SOURCE?.data?.poiInfo?.name ?: '' }}
  number('price') {{ DATA_SOURCE?.data?.dealInfo?.price ?: 0 }}
}
```

### 3.4 bizRespStatus 业务状态配置

```groovy
bizRespStatus {
  bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}

  string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '请求失败' }}

  bool('errorToast') {{ true }}

  objectWithSub('extra') {
    string('code') {{ DATA_SOURCE.errorInfo?.code ?: '' }}
    string('data') {{ DATA_SOURCE?.data ?: '' }}
  }

  bool('errorNoReturnStruct') {{ true }}
}
```

### 3.5 submitBizRespStatus 提交业务状态配置

```groovy
submitBizRespStatus {
  bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}
  string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '提交失败' }}
  bool('errorToast') {{ true }}
  objectWithSub('extra') {
    string('orderId') {{ DATA_SOURCE?.data?.orderId ?: '' }}
  }
}
```

## 四、常用场景示例

### 4.1 简单提单页数据源

```groovy
dataSource {
  dataSourceId '10'

  requestProps {
    objectWithSub('previewParam') {
      string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
      string('userId') {{ COMMON_PARAMS.userInfo?.userId ?: '' }}
      string('token') {{ COMMON_PARAMS.userInfo?.token ?: '' }}
    }
  }

  currentData {
    string('dealTitle') {{ DATA_SOURCE?.data?.dealInfo?.title ?: '' }}
    string('dealImage') {{ DATA_SOURCE?.data?.dealInfo?.imageUrl ?: '' }}
    number('price') {{ DATA_SOURCE?.data?.dealInfo?.price ?: 0 }}
  }

  bizRespStatus {
    bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '' }}
  }

  submitBizRespStatus {
    bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '提交失败' }}
    bool('errorToast') {{ true }}
  }
}
```

### 4.2 带额外信息上报的数据源

```groovy
dataSource {
  dataSourceId '10'

  requestProps {
    objectWithSub('previewParam') {
      string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
    }
  }

  currentData {
    string('orderId') {{ DATA_SOURCE?.data?.orderId ?: '' }}
  }

  bizRespStatus {
    bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '' }}

    objectWithSub('extra') {
      string('reportMsg') {{ 'code:' + (DATA_SOURCE.errorInfo?.code ?: '') }}
      string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
    }
  }
}
```

### 4.3 使用 PREV_DATA 的数据源

```groovy
dataSource {
  dataSourceId '10'

  currentData {
    string('selectedCouponId') {{ DATA_SOURCE?.data?.selectedCoupon?.id ?: '' }}
  }

  requestProps {
    objectWithSub('previewParam') {
      string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
      string('couponId') {{ PREV_DATA?.selectedCouponId ?: '' }}
    }
  }

  bizRespStatus {
    bool('isError') {{ DATA_SOURCE.errorInfo?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE.errorInfo?.message ?: '' }}
  }
}
```

## 五、与 1.0 版本差异

- **新增 currentData**：入参中可能会使用上次的数据源结果，需要在这里定义
- **新增 bizRespStatus.errorToast**：preview 失败是否显示 toast，大部分页面需要默认 toast
- **新增 bizRespStatus.errorNoReturnStruct**：preview/update 失败时是否返回 struct
- **新增 submitBizRespStatus.errorToast**：submit 失败是否显示 toast

## 六、注意事项

1. **requestProps**：只有后端关心，前端不需要解析
2. **currentData**：用于在入参表达式中引用 `PREV_DATA`，只能在入参配置中使用
3. **bizRespStatus**：用于 preview 和 update 请求的业务状态判断
4. **submitBizRespStatus**：用于 submit 请求的业务状态判断
5. **errorToast**：大部分页面需要默认 toast，以前需要单独配置事件回调处理
6. **errorNoReturnStruct**：以前引擎默认如果有 struct 就渲染，现在可以通过此字段控制

## 参考文档

https://km.sankuai.com/collabpage/1749282893
