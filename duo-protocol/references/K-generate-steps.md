# 生成协议的步骤

## 1. 分析页面需求

- 明确有哪些组件（布局、业务组件）及嵌套关系
- 明确数据来源（入参从 PAGE_QUERY 还是其他来源）
- 明确是否需要：条件渲染（displayRule）、列表渲染（items）、事件通信（events.emit）

## 2. 查询物料 ID（重要）

**materialId 和 componentsMap.id 必须从平台获取，不能自己编造！**

**首选：使用 `duo yooz-*` CLI（优先）或 MCP 工具查询**

- 搜索物料包名（如 `@meishi/common-layout-top-bottom`）
- 获取返回的 materialId、版本对应的 `id` 和版本号
- 填入 `componentsMap` 对应位置

**备选：从现有协议文件中复制** 若物料在 CLI 和 MCP 中均查询不到，从已有的协议 JSON 文件`references/materials.json`中查找该物料的配置，直接复制其 materialId、id、version 等字段。

`nodeId`：每个节点实例全局唯一，推荐用 7 位数字，可自行生成。数据源 ID：任意数字字符串，自行规划。

## 3. 收集 dependencies

所有 proCode 组件/逻辑库都必须在 dependencies 中声明（lowCode 不需要）。注意 logic 类型使用 `/logic/` CDN 路径。

## 4. 填写 componentsMap

每种组件/逻辑库填写一次，注意 logic 类型的 web URL 也使用 `/logic/` 路径。

## 5. 配置 dynamicDataConfig

- reqProps：用 `sub` 构造复杂对象入参，用 `?: ''` 做空值兜底
- bizRespStatus：通常用 `DATA_SOURCE.code != 0` 判断错误
- 如有 check 接口，补充 checkBizRespStatus

## 6. 构建 struct 树

从外层布局组件开始嵌套，styles 使用 `style` key + `sub` 结构，字符串字面量要用单引号包裹。

## 7. 配置 logics

标准配置：添加 common-duo-lifecycle + common-event-nav，在 lifecycle 的 `preview.onResponse` 事件中设置页面标题。

## 完整协议模板

> ⚠️ **使用前必读**：模板中所有 `{{...}}` 占位符必须替换为真实值。特别注意：`componentsMap` 的 **key（materialId）** 和 **`id` 字段** 必须通过 `duo yooz-*` CLI（优先）或 MCP 工具查询获得，**不能自行编造任何数字**，使用的groovy表达式必须是合法的groovy语法。groovy 的版本是 2.4.17，一些较新的语法不支持，可以参考 `case-study/CS-groovy-syntax.md`，禁止非法语法。

```json
{
  "duoVersion": "2",
  "pageId": "{{PAGE_ID}}",
  "pageProtocolId": "0002",
  "pageProtocolVersion": "0001",
  "dependencies": [
    {
      "name": "{{NPM_NAME}}",
      "version": "{{VERSION}}",
      "type": "component",
      "url": "https://s3plus-bj02.sankuai.com/yooz-assets/material/{{NPM_NAME}}/{{VERSION}}/index.js"
    },
    {
      "name": "{{LOGIC_NPM_NAME}}",
      "version": "{{LOGIC_VERSION}}",
      "type": "logic",
      "url": "https://s3plus-bj02.sankuai.com/yooz-assets/logic/{{LOGIC_NPM_NAME}}/{{LOGIC_VERSION}}/index.js"
    }
  ],
  "componentsMap": {
    "{{MATERIAL_ID_1，通过CLI/MCP查询}}": {
      "id": "{{PLATFORM_ID_1，通过CLI/MCP查询}}",
      "materialType": "proCode",
      "type": "component",
      "npm": "{{NPM_NAME}}",
      "npmVersion": "{{VERSION}}",
      "web": [
        "https://s3plus-bj02.sankuai.com/yooz-assets/material/{{NPM_NAME}}/{{VERSION}}/index.js"
      ]
    },
    "{{MATERIAL_ID_2，通过CLI/MCP查询}}": {
      "id": "{{PLATFORM_ID_2，通过CLI/MCP查询}}",
      "materialType": "proCode",
      "type": "logic",
      "npm": "{{LOGIC_NPM_NAME}}",
      "npmVersion": "{{LOGIC_VERSION}}",
      "web": [
        "https://s3plus-bj02.sankuai.com/yooz-assets/logic/{{LOGIC_NPM_NAME}}/{{LOGIC_VERSION}}/index.js"
      ]
    }
  },
  "pageBuildConfig": {
    "baseUrl": "https://{{API_HOST}}/{{API_PATH}}",
    "pageUrl": {
      "mrn": "rn_meishi_{{PAGE_NAME}}&main",
      "h5": "{{PAGE_NAME}}"
    },
    "pageQuery": {},
    "commonParams": {
      "usePn": true,
      "systemInfo": {},
      "userInfo": {
        "forceLogin": true,
        "useQuery": true
      },
      "fingerprint": {}
    }
  },
  "dynamicDataConfig": {
    "dataSourceMap": {
      "{{DS_ID}}": {
        "currentData": {},
        "reqProps": {},
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
          "errorToast": true
        }
      }
    },
    "constData": {}
  },
  "struct": [
    {
      "nodeType": "NORMAL_MODULE",
      "materialType": "proCode",
      "materialId": "{{MATERIAL_ID_1，与componentsMap的key一致}}",
      "nodeId": "{{自行生成的7位唯一数字}}",
      "slots": {
        "renderContent": []
      },
      "resource": {
        "nodeName": "{{COMPONENT_CLASS_NAME}}",
        "label": "{{COMPONENT_LABEL}}",
        "props": {},
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
  ],
  "logics": [
    {
      "nodeType": "HANDLER_MODULE",
      "materialType": "proCode",
      "materialId": "{{MATERIAL_ID_2，与componentsMap的key一致}}",
      "nodeId": "{{自行生成的7位唯一数字}}",
      "resource": {
        "nodeName": "{{LOGIC_CLASS_NAME}}",
        "label": "导航API",
        "events": {},
        "buildConfig": null
      }
    },
    {
      "nodeType": "HANDLER_MODULE",
      "materialType": "proCode",
      "materialId": "{{LIFECYCLE_MATERIAL_ID，通过CLI/MCP查询}}",
      "nodeId": "{{自行生成的7位唯一数字}}",
      "resource": {
        "nodeName": "{{LIFECYCLE_CLASS_NAME}}",
        "label": "内置物料-页面生命周期",
        "events": {
          "emit": {
            "preview.onResponse": [
              {
                "notifyNodeName": "{{导航API的nodeName}}",
                "notifyEventName": "setWebDocumentTitle",
                "lock": false,
                "props": {
                  "title": {
                    "dataType": "String",
                    "__resolveType__": "BACK_END",
                    "data": "'{{PAGE_TITLE}}'"
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
}
```

- [完整示例参考](../examples/duo-protocol-demo.json)
