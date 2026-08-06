# duo-backend-sdk 目录结构快照

- 仓库地址：ssh://git@git.sankuai.com/hui/duo-backend-sdk.git
- 本地路径：/Users/liuxin/Documents/00_work/35_duo/duo-backend-sdk
- 快照时间：2026-04-15
- 对应分支：master

---

## 目录结构

```
duo-backend-sdk/
├── pom.xml
├── data-engine/                          # 核心引擎模块
│   └── src/main/java/com/sankuai/duo/backend/sdk/
│       ├── AbstractUnifiedController.java      # 框架入口：注册 HTTP 路由、拉取协议、编排解析流程
│       ├── UnifiedControllerV2.java            # 业务方继承的抽象类，定义 doBizPreview/Update/Submit/Check
│       ├── UnifiedProtocolParserV2.java        # 核心解析器：resolveRequest + resolveResponse（V2 协议）
│       ├── UnifiedProtocolParser.java          # 核心解析器（V1 协议，兼容旧版）
│       ├── UnifiedProtocolBaseParser.java      # 解析器接口
│       ├── ProxyExpressionDataResolver.java    # Groovy 表达式执行代理
│       ├── ExpressionDataResolver.java         # 表达式解析器接口
│       ├── DUOProcessContext.java              # 单次请求的进程级上下文（NodeFactory 等）
│       ├── DUOProcessContextManager.java       # 进程上下文管理器（ThreadLocal）
│       ├── annotation/
│       │   ├── DUOBaseUrlConfig.java           # 业务方注解：配置 basePostUrl 和 needRegisterApis
│       │   └── DUOInterceptor.java             # 拦截器注解：配置 includeUrls/excludeUrls
│       ├── constant/
│       │   └── ApiTypeEnum.java               # 接口类型枚举：PREVIEW/UPDATE/SUBMIT/CHECK
│       ├── groovy/
│       │   └── DUOBinding.java                # Groovy Binding 实现，支持 MissingProperty 静默处理
│       ├── model/
│       │   └── DUOInterceptorContext.java      # 拦截器上下文（含 unifiedRequest + bizReq）
│       ├── parse/
│       │   ├── PageProtocolParseContext.java   # 单次解析上下文（pageId、expressionErrorCollector 等）
│       │   ├── ParseContextManager.java        # 解析上下文工厂
│       │   ├── enums/
│       │   │   └── StageEnum.java             # 解析阶段枚举（见下方详细说明）
│       │   └── stage/
│       │       ├── DataParseStage.java         # 数据解析阶段接口（runRule 系列方法）
│       │       ├── PageNodeParseStage.java     # 节点解析阶段接口（parseProps/parseStyles/parseEvents 等）
│       │       ├── DefaultPageNodeParseStage.java  # 节点解析阶段实现（含错误收集、slot 递归）
│       │       ├── DataRuleParseStage.java     # 数据规则解析阶段实现
│       │       └── intern/                    # 解析节点内部实现（ParseNode 树）
│       │           ├── ParseNode.java
│       │           ├── RootPageNodeParseNode.java
│       │           ├── DefaultPageNodeParseNode.java
│       │           ├── SlotPageNodeParseNode.java
│       │           └── ...
│       ├── protocol/
│       │   ├── PageProtocol.java              # 协议顶层模型（对应 duo_protocol.json）
│       │   ├── PageNode.java                  # 节点模型（含 Resource/Advanced/EventConfig）
│       │   ├── EventConfig.java               # 事件配置模型（emit/on）
│       │   ├── MaterialResourceConfig.java    # 物料资源配置
│       │   ├── constant/
│       │   │   ├── NodeTypeEnum.java          # 节点类型：NORMAL_MODULE/HANDLER_MODULE/LIST_CONTAINER
│       │   │   ├── SourceTypeEnum.java        # 表达式变量枚举（DATA_SOURCE/PAGE_QUERY/CONST 等）
│       │   │   ├── ResolveTypeEnum.java       # 解析类型：BACK_END/STATIC/EXPRESSION
│       │   │   ├── DataTypeEnum.java          # 数据类型：String/Number/Boolean/Object/List
│       │   │   └── SlotsKey.java              # 插槽 key 常量（CHILDREN 等）
│       │   └── dataresolve/
│       │       ├── DataResolveRule.java       # 表达式规则模型（dataType/data/sub/__resolveType__）
│       │       └── TempDataContext.java       # 临时上下文（LIST_CONTAINER 循环变量 FOR.item/index）
│       ├── protocolpuller/
│       │   ├── ProtocolPuller.java            # 协议拉取器（本地缓存 + 远程拉取）
│       │   └── ProtocolRemotePuller.java      # 远程协议拉取（从配置平台）
│       ├── request/
│       │   ├── UnifiedRequest.java            # 统一请求体（pageId/pageQuery/commonParams/payload 等）
│       │   └── CommonParam.java               # 通参模型（userInfo/location/cityInfo/systemInfo）
│       ├── response/
│       │   ├── UnifiedResponse.java           # preview/update 响应（struct/bizRespStatus/currentData）
│       │   ├── UnifiedSubmitResponse.java     # submit 响应（submitBizRespStatus/bizRes）
│       │   ├── UnifiedCheckResponse.java      # check 响应（checkBizRespStatus/bizRes）
│       │   ├── BizRespStatus.java             # 业务响应状态（isError/errorMsg/errorToast）
│       │   ├── RenderNode.java                # 渲染节点（返回给前端的节点结构）
│       │   └── NodeData.java                  # 节点数据（props/styles/events，存入 nodeDataMap）
│       ├── extendfunc/
│       │   └── DuoUtil.java                   # Groovy 表达式中可用的 DF 工具函数实现
│       └── webresponse/
│           └── WebResponse.java               # HTTP 响应包装（code/data/error/warnInfo）
└── data-management/                           # 协议管理模块（协议版本转换工具）
    └── src/main/java/.../management/utils/
        ├── ProtocolConverter.java             # 协议格式转换
        └── ProtocolVersionConverter.java      # 协议版本转换
```

---

## StageEnum 解析阶段说明

```java
PARSE_CONST            // 解析 constData（常量，注入 CONST 变量）
PARSE_DATA_SOURCE      // 解析 dataSourceMap.reqProps（接口入参）
PARSE_BIZ_RESP_STATUS  // 解析 bizRespStatus（preview/update 业务响应状态）
PARSE_SUBMIT_BIZ_RESP_STATUS // 解析 submitBizRespStatus / checkBizRespStatus
PARSE_STRUCT           // 解析 struct（组件树，递归）
PARSE_LOGICS           // 解析 logics（逻辑节点事件配置）
PARSE_CURRENT_DATA     // 解析 currentData（供下次请求 PREV_DATA 使用）
```

---

## SourceTypeEnum 可用变量

```java
PAGE_QUERY      // URL 参数（前端传入）
COMMON_PARAMS   // 通参（userId/location/cityInfo 等）
SYSTEM_INFO     // 系统信息（UA/IP，后端在入口填充，前端无法获取）
DATA_SOURCE     // 业务接口响应（bizResponse 转 Map 后注入）
NODE            // 节点保存的状态（nodeDataMap，对应 NODE.xxx.props.yyy）
CONST           // constData 常量（PARSE_CONST 阶段注入）
PREV_DATA       // 上次数据源结果（仅 reqProps 阶段可用，响应阶段已 remove）
PAYLOAD         // 事件临时参数（前端 update/submit 时携带）
UPDATE          // 双向绑定更新的 props（updatePropMap）
FOR             // LIST_CONTAINER 循环变量（item/index，仅后端解析，不传前端）
```

---

## 更新记录

| 日期 | 变更内容 |
| --- | --- |
| 2026-04-15 | 初始化：基于本地代码生成目录结构快照 |
