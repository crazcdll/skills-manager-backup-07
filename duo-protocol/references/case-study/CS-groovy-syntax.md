# Groovy DSL 语法错误总结

> **🔴 核心铁律（2026-04-20 更新）**：
> `{{ }}` 内是 Groovy 脚本代码，Groovy 原生支持 `//` 注释，因此注释**只能写在 `{{ }}` 内部**。`{{ }}` 之外是 DUO DSL 语法层，不支持任何注释，写了会直接报 `Unexpected char "/"`。
>
> 注释规则适用范围：
> - ✅ `.groovy` 文件的 `{{ }}` 内部 → **允许 `//` 单行注释和 `/* */` 块注释**（Groovy 脚本代码）
> - ❌ `.groovy` 文件的 `{{ }}` 外部 → **禁止任何注释**（DUO DSL 语法层）
> - ❌ `.json` 文件（componentsMap/dependencies/pageBuildConfig）→ **禁止任何注释**（标准 JSON 不支持注释）
>
> 违反后果：平台解析直接报错 `Unexpected char "/"`，协议无法加载。

以下错误是在实际生成协议过程中遇到的，请避免类似问题：

## 目录

- [1. ❌ 错误：使用 `//` 注释](#1--错误使用--注释) — Unexpected char "/"
- [2. ❌ 错误：events 使用 JSON 数组语法](#2--错误events-使用-json-数组语法) — Unexpected token "["
- [3. ❌ 错误：使用 `advanced { bool('displayRule') ... }`](#3--错误使用-advanced--booldisplayrule--) — 应使用 xIf 语法
- [4. ❌ 错误：使用 `styles { object('style') ... }`](#4--错误使用-styles--objectstyle--) — 应使用 style('styleName') 语法
- [5. ❌ 错误：使用 `lock false`](#5--错误使用-lock-false) — lock 默认 false，不需显式声明
- [6. ❌ 错误：`constData.groovy` 使用 `constData` 关键字](#6--错误constdatagroovy-使用-constdata-关键字) — 应使用 `constant` 关键字
- [7. ❌ 错误：`submitBizRespStatus`/`checkBizRespStatus` 中使用 `errorNoReturnStruct`](#7--错误submitbizrespstatuscheckbizrespstatus-中使用-errornoreturnstruct) — 该字段只在 bizRespStatus 中有效
- [完整正确示例](#完整的正确示例) — struct.groovy + logics.groovy 完整示例

## 1. ❌ 错误：使用 `//` 注释

**错误信息**：`Unexpected char "/" at xxx`

**错误写法**：

```groovy
// 这是注释
node('MeishiCommonLayoutTopBottom', '7') {
  // 这也是注释
  label '页面布局'
}
```

**正确写法**：`{{ }}` 外部（DSL 语法层）不能有注释，必须移除

```groovy
node('MeishiCommonLayoutTopBottom', '7') {
  label '页面布局'
}
```

**✅ 允许写注释的正确示例**：注释写在 `{{ }}` 内部的 Groovy 脚本代码中

```groovy
string('title') {{
  // 兜底空字符串
  DATA_SOURCE.data?.title ?: ''
}}

bool('isOversea') {{
  def bizType = PAGE_QUERY.biz_type
    ? (int) DF.toNumber(PAGE_QUERY.biz_type)
    : 1
  // bizType == 2 表示境外
  return bizType == 2
}}
```

## 2. ❌ 错误：events 使用 JSON 数组语法

**错误信息**：`Unexpected token "[" at xxx`

**错误写法**：

```groovy
events {
  emit {
    'onSubmit'([
      {
        notifyNodeName 'xxx'
        notifyEventName 'submit'
      }
    ])
  }
}
```

**正确写法**：使用 `on('eventName')` 和 `callMethod()` 语法

```groovy
on('onSubmit') {
  callMethod('TargetNodeName', 'targetMethodName')
}
```

## 3. ❌ 错误：使用 `advanced { bool('displayRule') ... }`

**错误信息**：`Unexpected token "}" at xxx`

**错误写法**：

```groovy
node('SomeComponent', '123') {
  advanced {
    bool('displayRule') {{ DATA_SOURCE.loading == true }}
  }
}
```

**正确写法**：使用 `xIf` 语法

```groovy
node('SomeComponent', '123') {
  xIf {{ DATA_SOURCE.loading == true }}
}
```

## 4. ❌ 错误：使用 `styles { object('style') ... }`

**错误信息**：`Unexpected token "}" at xxx`

**错误写法**：

```groovy
node('SomeComponent', '123') {
  styles {
    object('style') {{
      string('backgroundColor') {{ '#FFFFFF' }}
    }}
  }
}
```

**正确写法**：使用 `style('styleName')` 语法

```groovy
node('SomeComponent', '123') {
  style('style') {
    string('backgroundColor') {{ '#FFFFFF' }}
  }
}
```

## 5. ❌ 错误：使用 `lock false`

**错误写法**：

```groovy
on('onSubmit') {
  callMethod('TargetNodeName', 'targetMethodName')
  lock false
}
```

**正确写法**：`lock` 默认就是 false，不需要显式声明；如果需要 `lock true`，可以写

```groovy
on('onSubmit') {
  callMethod('TargetNodeName', 'targetMethodName')
  lock true
}
```

## 6. ❌ 错误：`constData.groovy` 使用 `constData` 关键字

**错误信息**：`Unknown identifier, constData is not defined`

**错误写法**：

```groovy
constData {
  string('pageTitle') {{ '填单页' }}
}
```

**正确写法**：使用 `constant` 关键字

```groovy
constant {
  string('pageTitle') {{ '填单页' }}
}
```

## 7. ❌ 错误：`submitBizRespStatus`/`checkBizRespStatus` 中使用 `errorNoReturnStruct`

**错误信息**：`Unknown identifier, errorNoReturnStruct is not defined`

**错误原因**：`errorNoReturnStruct` 字段只在 `bizRespStatus` 块中有效，不能用于 `submitBizRespStatus` 和 `checkBizRespStatus` 块。

**错误写法**：

```groovy
submitBizRespStatus {
  bool('isError') {{ DATA_SOURCE.code != 0 }}
  string('errorMsg') {{ DATA_SOURCE.message ?: '' }}
  errorToast true
  errorNoReturnStruct false
}

checkBizRespStatus {
  bool('isError') {{ DATA_SOURCE.code != 0 }}
  string('errorMsg') {{ DATA_SOURCE.message ?: '' }}
  errorToast true
  errorNoReturnStruct false
}
```

**正确写法**：`submitBizRespStatus` 和 `checkBizRespStatus` 只需要 `isError`、`errorMsg` 和 `errorToast`，不需要 `errorNoReturnStruct`

```groovy
bizRespStatus {
  bool('isError') {{ DATA_SOURCE.code != 0 }}
  string('errorMsg') {{ DATA_SOURCE.message ?: '' }}
  errorToast true
  errorNoReturnStruct true
}

submitBizRespStatus {
  bool('isError') {{ DATA_SOURCE.code != 0 }}
  string('errorMsg') {{ DATA_SOURCE.message ?: '' }}
  errorToast true
}

checkBizRespStatus {
  bool('isError') {{ DATA_SOURCE.code != 0 }}
  string('errorMsg') {{ DATA_SOURCE.message ?: '' }}
  errorToast true
}
```

## 完整的正确示例

**struct.groovy**：

```groovy
node('MeishiCommonLayoutTopBottom', '7') {
  label '页面布局（上中下）'
  props {
    bool('statusBarTranslucent') {{ false }}
    string('safeAreaBottom') {{ 'normal' }}
  }
  style('style') {
    string('backgroundColor') {{ '#F5F5F5' }}
  }
  slot('renderTop') {
    node('NavBar', '6073') {
      label '导航栏'
      props {
        string('title') {{ '页面标题' }}
      }
    }
  }
  slot('renderContent') {
    node('LoadingFill', '1204') {
      label '加载骨架屏'
      xIf {{ DATA_SOURCE.loading == true }}
    }
    node('ContentCard', '1052') {
      label '内容卡片'
      xIf {{ DATA_SOURCE.loading != true }}
      props {
        string('data') {{ DATA_SOURCE.data?.content ?: '' }}
      }
      on('onItemClick') {
        callMethod('EventHandler', 'handleClick')
      }
    }
  }
  slot('renderBottom') {
    node('BottomBar', '1076') {
      label '底部栏'
      props {
        string('price') {{ DATA_SOURCE.data?.price ?: '0' }}
      }
      on('onSubmit') {
        callMethod('LifecycleLogic', 'submit')
      }
    }
  }
}
```

**logics.groovy**：

```groovy
node('MeishiCommonEventNav', '90') {
  label '导航API'
}

node('MeishiCommonDuoLifecycle', '13') {
  label '内置物料-页面生命周期'
  on('preview.onResponse') {
    callMethod('MeishiCommonEventNav', 'setWebDocumentTitle')
    props {
      string('title') {{ '页面标题' }}
    }
  }
}
```
