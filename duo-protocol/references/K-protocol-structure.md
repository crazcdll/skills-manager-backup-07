# Duo 页面协议生成指南

Duo 是美团内部的低代码页面搭建平台，页面以 JSON 协议描述。协议规范来源：<https://km.sankuai.com/collabpage/1749282893>

## 目录

- [协议整体结构（PageProtocol）](#协议整体结构pageprotocol) — 顶层字段概览：duoVersion、dependencies、componentsMap、struct、logics 等
- [一、dependencies（依赖声明）](#一dependencies依赖声明) — npm 物料列表，component/logic/util 的 CDN URL 规律
- [二、componentsMap（物料注册表）](#二componentsmap物料注册表) — materialId 获取方式、proCode 组件/逻辑库、lowCode 组件
  - [proCode 组件（type: component）](#procode-组件type-component)
  - [proCode 逻辑库（type: logic）](#procode-逻辑库type-logic)
  - [lowCode 组件（平台内编排）](#lowcode-组件平台内编排)
- [三、pageBuildConfig（页面构建配置）](#三pagebuildconfig页面构建配置) — baseUrl、pageUrl、commonParams 字段说明
- [四、dynamicDataConfig（数据源配置）](#四dynamicdataconfig数据源配置) — dataSourceMap、constData、数据绑定 DSL
  - [dataSourceMap（接口数据源）](#datasourcemap接口数据源) — reqProps、bizRespStatus、submitBizRespStatus
  - [constData（页面常量）](#constdata页面常量) — 仅可用于 struct，不可用于 reqProps
  - [数据绑定 DSL（DataExpression）](#数据绑定-dsldataexpression) — Groovy 表达式写法、常用数据路径前缀、Object sub 嵌套
- [五、struct（组件树结构）](#五struct组件树结构) — PageNode 数组、slots 嵌套、styles 写法、nodeType 取值
  - [5.1 节点高级配置（advanced）](#51-节点高级配置advanced) — displayRule、items、iterateKey
  - [5.2 双向绑定（propConfig）](#52-双向绑定propconfig) — isRequestArg、updateBy、lock
  - [5.3 事件配置（events.emit）](#53-事件配置eventsemit) — notifyNodeName、notifyEventName、props 透传
  - [5.4 buildConfig](#54-buildconfig) — 默认 null，标准字段
- [六、logics（页面逻辑）](#六logics页面逻辑) — HANDLER_MODULE 逻辑节点、lifecycle、event-nav 常用组合
- [七、scripts（页面脚本）](#七scripts页面脚本) — 页面 JS 代码

## 协议整体结构（PageProtocol）

```bash
顶层字段
├── duoVersion          协议引擎版本（固定 "2"）
├── pageId              页面全局唯一 ID
├── pageProtocolId      协议模板 ID（如 "0002"）
├── pageProtocolVersion 协议版本（如 "0001"）
├── dependencies        依赖的 npm 列表，运行前预加载
├── componentsMap       物料映射表（key 为 materialId）
├── pageBuildConfig     页面编译时的静态配置信息
├── dynamicDataConfig   动态配置数据
│   ├── dataSourceMap   数据源配置
│   └── constData       常量（只能在 struct 中使用，不可用于 reqProps）
├── struct              页面的树形结构（UI 组件树）
└── logics              页面逻辑列表
```

---

## 一、dependencies（依赖声明）

列出页面用到的所有 npm 物料，运行前预加载。**组件和逻辑库 URL 路径不同**：

```json
[
  {
    "name": "@hfe/max-button",
    "version": "4.0.4",
    "type": "component",
    "url": "https://s3plus-bj02.sankuai.com/yooz-assets/material/@hfe/max-button/4.0.4/index.js"
  },
  {
    "name": "@meishi/common-duo-lifecycle",
    "version": "1.1.0",
    "type": "logic",
    "url": "https://s3plus-bj02.sankuai.com/yooz-assets/logic/@meishi/common-duo-lifecycle/1.1.0/index.js"
  }
]
```

**URL 规律**：

| type        | CDN 路径                                                                         |
| ----------- | -------------------------------------------------------------------------------- |
| `component` | `https://s3plus-bj02.sankuai.com/yooz-assets/material/{name}/{version}/index.js` |
| `logic`     | `https://s3plus-bj02.sankuai.com/yooz-assets/logic/{name}/{version}/index.js`    |
| `util`      | `https://s3plus-bj02.sankuai.com/yooz-assets/material/{name}/{version}/index.js` |

> **注意**：lowCode 组件不需要在 dependencies 中声明。

---

## 二、componentsMap（物料注册表）

key 为页面内 materialId（字符串数字），每种组件只注册一次（多实例共用同一 materialId）。

> ⚠️ **重要**：materialId 和 版本`id` 字段**不能随意编造**，必须从以下途径获取：
>
> - **key（`materialId`）**：物料在 DUO 资产平台的唯一标识 ID
> - **版本`id` 字段**：物料**对应版本**的 ID（同一物料不同版本的 id 不同，必须与 npmVersion 匹配）
> - **版本`npmVersion`字段**物料**对应版本**的版本号（同一物料npmVersion必须与版本id一一对应）
>
> **获取方式（按优先级）**：
>
> 1. **`duo yooz-*` CLI 工具（首选）**：`duo yooz-read-detail -n "<包名>"` 或 `duo yooz-getby-packagename -p "<包名>"`
> 2. **MCP 工具（降级）**：`mcp_tool_duo_ai_mcp_server_read_yooz_material_detail` 或 `get_material_by_package_name`
> 2. **从现有文件复制**：若平台查询不到，从已有的[materials.json](./materials.json)文件中找到该物料，直接复制 materialId、id、npmVersion 等字段。

> 3.⚠️ **重要**：若平台查询不到，且没有其他途径获取到该物料的 materialId 和 id 字段，不要使用该物料。

### proCode 组件（type: component）

```json
"{{materialId，通过CLI/MCP查询}}": {
  "id": "{{该版本的id，通过CLI/MCP查询，与npmVersion对应}}",
  "materialType": "proCode",
  "type": "component",
  "npm": "@meishi/common-layout-top-bottom",
  "npmVersion": "{{版本号，通过CLI/MCP查询}}",
  "web": [
    "https://s3plus-bj02.sankuai.com/yooz-assets/material/@meishi/common-layout-top-bottom/{{VERSION}}/index.js"
  ]
}
```

### proCode 逻辑库（type: logic）

逻辑库的 web URL 路径使用 `/logic/` 而非 `/material/`：

```json
"{{materialId，通过CLI/MCP查询}}": {
  "id": "{{该版本的id，通过CLI/MCP查询，与npmVersion对应}}",
  "materialType": "proCode",
  "type": "logic",
  "npm": "@meishi/common-duo-lifecycle",
  "npmVersion": "{{版本号，通过CLI/MCP查询}}",
  "web": [
    "https://s3plus-bj02.sankuai.com/yooz-assets/logic/@meishi/common-duo-lifecycle/{{VERSION}}/index.js"
  ]
}
```

### lowCode 组件（平台内编排）

```json
"{{materialId，通过CLI/MCP查询}}": {
  "id": "{{该版本的id，通过CLI/MCP查询}}",
  "materialType": "lowCode",
  "type": "component",
  "name": "nav-bar"
}
```

lowCode 组件没有 `web` URL，由平台内部渲染，无需在 dependencies 中声明。

---

## 三、pageBuildConfig（页面构建配置）

```json
{
  "baseUrl": "https://cart.sankuai.com/foodtrade/internal/snapshot",
  "pageUrl": {
    "mrn": "rn_meishi_snapshot-pacific&main",
    "h5": "snapshot-pacific"
  },
  "pageQuery": {},
  "commonParams": {
    "usePn": true,
    "systemInfo": {},
    "location": {
      "type": "GCJ02",
      "sceneToken": "dd-6c2101d70b06b779",
      "useSync": true,
      "useQuery": true,
      "useAll": true
    },
    "userInfo": {
      "forceLogin": true,
      "useQuery": true,
      "useSync": true
    },
    "city": {
      "useSync": true,
      "useQuery": true,
      "useAll": false
    },
    "fingerprint": {}
  }
}
```

**commonParams 字段说明**：

| 字段                  | 说明                                               |
| --------------------- | -------------------------------------------------- |
| `usePn`               | 是否开启预请求                                     |
| `systemInfo`          | 环境信息配置（通常为 `{}`）                        |
| `fingerprint`         | fingerprint 配置（通常为 `{}`）                    |
| `location.type`       | 定位坐标系：`GCJ02` 或 `WGS84`                     |
| `location.sceneToken` | 定位场景 token（useSync=false 时必填）             |
| `location.useSync`    | 使用同步桥缓存定位（更快）                         |
| `location.useQuery`   | 优先使用跳链参数（与 useAll 互斥）                 |
| `location.useAll`     | 获取完整精度信息（与 useQuery 互斥）               |
| `userInfo.forceLogin` | 是否强制登录（默认 true）                          |
| `userInfo.useQuery`   | 优先使用跳链参数（与 forceLogin 互斥）             |
| `userInfo.useSync`    | 使用同步桥                                         |
| `city.useSync`        | 使用同步桥（默认 true）                            |
| `city.useQuery`       | 优先使用跳链参数                                   |
| `city.useAll`         | 获取定位城市 locCityId（与 useSync/useQuery 互斥） |

---

## 四、dynamicDataConfig（数据源配置）

### dataSourceMap（接口数据源）

每个数据源用数字 ID 作为 key（无需从 10 开始，可用任意数字）：

```json
"91": {
  "currentData": {},
  "reqProps": {
    "snapshotBusinessParam": {
      "dataType": "Object",
      "__resolveType__": "BACK_END",
      "sub": {
        "orderId": {
          "dataType": "String",
          "__resolveType__": "BACK_END",
          "data": "PAGE_QUERY?.orderId ?: ''"
        },
        "querySource": {
          "dataType": "String",
          "__resolveType__": "BACK_END",
          "data": "PAGE_QUERY?.querySource ?: 'main'"
        }
      }
    }
  },
  "bizRespStatus": {
    "isError": {
      "dataType": "Boolean",
      "__resolveType__": "BACK_END",
      "data": "DATA_SOURCE.code != 0"
    },
    "errorToast": true,
    "errorNoReturnStruct": true
  },
  "submitBizRespStatus": {
    "isError": {
      "dataType": "Boolean",
      "__resolveType__": "BACK_END",
      "data": "DATA_SOURCE.code != 0"
    },
    "errorToast": true,
    "errorNoReturnStruct": false
  },
  "checkBizRespStatus": {
    "errorToast": true,
    "errorNoReturnStruct": false
  }
}
```

**字段说明**：

| 字段                  | 说明                               |
| --------------------- | ---------------------------------- |
| `currentData`         | 入参中引用上次数据源结果           |
| `reqProps`            | 数据源请求入参（后端解析）         |
| `bizRespStatus`       | preview/update 请求的业务响应状态  |
| `submitBizRespStatus` | submit 请求的业务响应状态          |
| `checkBizRespStatus`  | check 请求的业务响应状态           |
| `errorNoReturnStruct` | true = 发生错误时不渲染页面 struct |

### constData（页面常量）

```json
"constData": {
  "pageTitle": {
    "dataType": "String",
    "constant": "拼团结果页"
  }
}
```

> **限制**：constData 只能在 struct 视图树中使用，**不能**在 reqProps（入参）中使用。

---

### 数据绑定 DSL（DataExpression）

> ⚠️ **重要**：`data` 字段的表达式是 **Groovy** 语法（后端执行），不是 JavaScript！

**完整格式**：

```json
{
  "dataType": "String | Number | Boolean | Object | List",
  "constant": "静态值（与 data 二选一）",
  "data": "Groovy 表达式（与 constant 二选一）",
  "__resolveType__": "BACK_END | STATIC | EXPRESSION",
  "sub": {
    "field1": { "dataType": "String", "data": "..." }
  }
}
```

**常用数据路径前缀**：

| 前缀                            | 含义                   |
| ------------------------------- | ---------------------- |
| `DATA_SOURCE.data?.xxx`         | 数据源返回的 data 字段 |
| `DATA_SOURCE.code`              | 数据源返回的 code 字段 |
| `PAGE_QUERY?.xxx`               | 页面 URL 参数          |
| `CONST.xxx`                     | constData 中定义的常量 |
| `COMMON_PARAMS.systemInfo?.xxx` | 通参中的环境信息       |

**Groovy 表达式写法规则**：

| 场景               | 写法                    | 示例                                           |
| ------------------ | ----------------------- | ---------------------------------------------- |
| 字符串字面量       | 外层双引号 + 内层单引号 | `"data": "'交易快照'"`                         |
| 数字字面量         | 直接写数字字符串        | `"data": "10"`                                 |
| 颜色/字符串常量    | 单引号包裹              | `"data": "'#F9F9F9'"`                          |
| null 兜底（Elvis） | `?:` 运算符             | `"data": "PAGE_QUERY?.orderId ?: ''"`          |
| 带默认值           | `?: 'defaultValue'`     | `"data": "PAGE_QUERY?.source ?: 'main'"`       |
| 列表判断           | `.size() > 0`           | `"data": "DATA_SOURCE.data?.list?.size() > 0"` |
| 取反条件           | `!( ... )`              | `"data": "!(PAGE_QUERY?.hiddenNav == '1')"`    |
| 比较判断           | `!= / == / > / <`       | `"data": "DATA_SOURCE.code != 0"`              |

**Object 类型 sub 嵌套写法**（用于复杂入参对象）：

```json
"params": {
  "dataType": "Object",
  "__resolveType__": "BACK_END",
  "sub": {
    "orderId": {
      "dataType": "String",
      "__resolveType__": "BACK_END",
      "data": "PAGE_QUERY?.orderId ?: ''"
    },
    "count": {
      "dataType": "Number",
      "__resolveType__": "BACK_END",
      "data": "PAGE_QUERY?.count ?: 1"
    }
  }
}
```

---

## 五、struct（组件树结构）

对使用的物料，使用 `duo yooz-*` CLI（优先）或 MCP 工具来查询物料的配置信息，包括入参和方法调用，插槽slots等信息，用于组件树的使用。

struct 是 PageNode 数组，通过 slots 嵌套子节点：

```json
{
  "nodeType": "NORMAL_MODULE",
  "materialType": "proCode",
  "materialId": "7",
  "nodeId": "5456099",
  "slots": {
    "renderTop": [
      {
        "nodeType": "NORMAL_MODULE",
        "materialType": "lowCode",
        "materialId": "12",
        "nodeId": "5456102",
        "resource": {
          "nodeName": "NavBar",
          "label": "导航栏",
          "props": {
            "title": {
              "dataType": "String",
              "__resolveType__": "BACK_END",
              "data": "'交易快照'"
            }
          },
          "styles": {},
          "events": {},
          "advanced": {
            "displayRule": {
              "dataType": "Boolean",
              "__resolveType__": "BACK_END",
              "data": "!(PAGE_QUERY?.hiddenNav == '1')"
            }
          },
          "buildConfig": null
        }
      }
    ],
    "renderContent": [...]
  },
  "resource": {
    "nodeName": "MeishiCommonLayoutTopBottom",
    "label": "页面布局（上中下）",
    "props": {
      "statusBarTranslucent": {
        "dataType": "Boolean",
        "__resolveType__": "BACK_END",
        "data": "false"
      },
      "safeAreaBottom": {
        "dataType": "String",
        "__resolveType__": "BACK_END",
        "data": "'normal'"
      }
    },
    "styles": {
      "style": {
        "dataType": "Object",
        "__resolveType__": "BACK_END",
        "sub": {
          "backgroundColor": {
            "dataType": "String",
            "__resolveType__": "BACK_END",
            "data": "'#F9F9F9'"
          }
        }
      }
    },
    "events": {},
    "advanced": {},
    "buildConfig": null
  }
}
```

**styles 写法说明**：styles 通常使用 `"style"` key，值为 Object 类型的 DataExpression，通过 `sub` 定义各个样式属性：

```json
"styles": {
  "style": {
    "dataType": "Object",
    "__resolveType__": "BACK_END",
    "sub": {
      "marginBottom": {
        "dataType": "Number",
        "__resolveType__": "BACK_END",
        "data": "10"
      },
      "backgroundColor": {
        "dataType": "String",
        "__resolveType__": "BACK_END",
        "data": "'#FFFFFF'"
      }
    }
  }
}
```

### nodeType 取值

| 值               | 说明               | 用于   |
| ---------------- | ------------------ | ------ |
| `NORMAL_MODULE`  | 普通组件（最常用） | struct |
| `HANDLER_MODULE` | 事件处理/逻辑组件  | logics |
| `LIST_CONTAINER` | 列表容器           | struct |

**常见插槽名**：`renderTop`、`renderContent`、`renderBottom`、`renderHeader`、`renderFooter`、`default`

### 5.1 节点高级配置（advanced）

```json
"advanced": {
  "displayRule": {
    "dataType": "Boolean",
    "__resolveType__": "BACK_END",
    "data": "DATA_SOURCE.data?.menuArea?.menus?.size() > 0"
  },
  "items": {
    "dataType": "List",
    "__resolveType__": "BACK_END",
    "data": "DATA_SOURCE.data?.list"
  },
  "iterateKey": {
    "dataType": "String",
    "__resolveType__": "BACK_END",
    "data": "item.id"
  }
}
```

| 字段          | 说明                             |
| ------------- | -------------------------------- |
| `displayRule` | Boolean 表达式，控制节点是否展示 |
| `items`       | List 表达式，列表容器时绑定数据  |
| `iterateKey`  | 列表中每个元素的唯一 key         |

### 5.2 双向绑定（propConfig）

```json
"propConfig": {
  "value": {
    "isRequestArg": true,
    "updateBy": "onChange",
    "lock": true
  }
}
```

### 5.3 事件配置（events.emit）

```json
"events": {
  "emit": {
    "preview.onResponse": [
      {
        "notifyNodeName": "MeishiCommonEventNav",
        "notifyEventName": "setWebDocumentTitle",
        "lock": false,
        "props": {
          "title": {
            "dataType": "String",
            "__resolveType__": "BACK_END",
            "data": "'交易快照'"
          }
        },
        "transparentArg": []
      }
    ]
  }
}
```

事件名格式：`"事件类型.事件阶段"`，如 `"preview.onResponse"`（数据源 preview 请求响应时触发）。

### 5.4 buildConfig

所有节点的 `resource` 中均包含 `"buildConfig": null`，这是标准字段，默认值为 null。

---

## 六、logics（页面逻辑）

存放全局逻辑节点，nodeType 通常为 `HANDLER_MODULE`。

真实示例（导航 API + 页面生命周期）：

```json
"logics": [
  {
    "nodeType": "HANDLER_MODULE",
    "materialType": "proCode",
    "materialId": "90",
    "nodeId": "5456100",
    "resource": {
      "nodeName": "MeishiCommonEventNav",
      "label": "导航API",
      "events": {},
      "buildConfig": null
    }
  },
  {
    "nodeType": "HANDLER_MODULE",
    "materialType": "proCode",
    "materialId": "13",
    "nodeId": "5456101",
    "resource": {
      "nodeName": "MeishiCommonDuoLifecycle",
      "label": "内置物料-页面生命周期",
      "events": {
        "emit": {
          "preview.onResponse": [
            {
              "notifyNodeName": "MeishiCommonEventNav",
              "notifyEventName": "setWebDocumentTitle",
              "lock": false,
              "props": {
                "title": {
                  "dataType": "String",
                  "__resolveType__": "BACK_END",
                  "data": "'页面标题'"
                }
              },
              "transparentArg": []
            }
          ]
        }
      },
      "buildConfig": null
    }
  }
]
```

**常用 logics 组合**（大多数页面都需要）：

- `@meishi/common-duo-lifecycle`：页面生命周期（处理 preview/submit 事件）
- `@meishi/common-event-nav`：导航 API（路由跳转、设置标题等）

---


## 七、scripts（页面脚本）

7.1 buildCustom.js  (可选)
构建配置，对应 `pageBuildConfig.commonParams.buildFunction`:
```javascript
module.exports = (config) => {
  const { targets, define } = config;
  // 修改 config...
  return config;
};
```

7.2 mrnConfigCustom.js (可选)
MRN 配置，对应 `pageBuildConfig.commonParams.mrnConfigFunction`:
```javascript
module.exports = (config) => {
  // 修改 MRN 配置...
  return config;
};
```

7.3 firstScreenModulePaths.json (可选)
首屏加载模块路径。
```json
[
  "node_modules/@analytics/mrn-sdk/dist/index.js"
]
```

