# 页面常量配置 constData.groovy

> 对应执行步骤：Step 3.3

## 定义

constData 用于定义可在 struct 组件树中复用的表达式常量。

## 基本结构

```groovy
constant {
  string('pageTitle') {{ '门票提单' }}
  number('childPrice') {{ DATA_SOURCE?.data?.dealInfo?.childPrice ?: 40 }}
  number('adultPrice') {{ DATA_SOURCE?.data?.dealInfo?.adultPrice ?: 90 }}
}
```

## 使用方式

在 struct.groovy 中通过 `CONST.xxx` 引用：

```groovy
node('TitleText', '38') {
  label '页面标题'
  props {
    string('text') {{ CONST.pageTitle }}
  }
}
```

## 强约束规则

| 规则 | 说明 |
|------|------|
| MUST_NOT 用于 reqProps | constData 中的常量**不能**在 dataSourceMap.groovy 的 requestProps 中使用 |
| MUST_NOT 互相引用 | CONST 之间不可以互相引用（如 `CONST.a` 引用 `CONST.b`） |
| MUST_NOT 在自身中引用 | 常量定义中不可以使用 `CONST` 变量 |
| MUST | constData 表达式中可以使用 `DATA_SOURCE`、`PAGE_QUERY`、`COMMON_PARAMS` |

## JSON 协议格式

```json
"constData": {
  "pageTitle": {
    "dataType": "String",
    "constant": "拼团结果页"
  }
}
```

> 注意：JSON 协议中使用 `constant` 字段表示静态值，而非 `data` 字段。

## 注意事项

1. 常量只在 struct 的组件表达式中可用，入参配置中不可用
2. 同一个表达式会在多处使用时，适合抽取为常量
3. 常量名称建议使用驼峰命名法，语义清晰

## 参考文档

https://km.sankuai.com/collabpage/1749282893
