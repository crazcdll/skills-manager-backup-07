# DUO 核心术语

本页统一 DUO 页面协议相关术语，方便在文档、代码、对话中使用一致的表述。

## 平台与架构

| 术语 | 说明 |
|------|------|
| **DUO** | Dynamic Unified Open platform，到店平台交易前后端一体化方案，Server Driven UI 页面配置化平台 |
| **DUO 配置平台** | https://duo.sankuai.com，页面可视化配置搭建、后端数据 API 管理、调试 |
| **DUO 资产平台** | https://yooz.sankuai.com，lowCode 物料生产、proCode 物料托管 |
| **Server Driven UI** | 服务端驱动 UI，核心逻辑收敛后端，通过协议动态化即时触达 |

## 协议术语

| 术语 | 说明 |
|------|------|
| **PageProtocol** | 页面搭建协议，描述页面搭建配置信息 |
| **RenderRequest / RenderResponseData** | 端到端协议，运行时前后端通信的统一入参出参格式 |
| **MaterialConfig** | 物料协议，描述物料可配置的属性、事件、插槽等 |
| **DataExpression** | 数据表达式，支持 String / Number / Boolean / List / Object |
| **struct** | 视图树，页面的树形结构 |
| **logics** | 逻辑列表，页面的交互逻辑 |
| **dataSourceMap** | 数据源定义，后端业务数据源如何绑定 |
| **constData** | 页面级常量数据 |
| **componentsMap** | 物料接口配置映射 |
| **pageProtocolId** | 协议唯一 id |
| **pageProtocolVersion** | 协议版本号（稳定版 `0003` / 快照版 `0003-SNAPSHOT-0001`） |

## 页面生命周期接口

| 接口 | 触发时机 | 后端行为 |
|------|----------|----------|
| **preview** | 打开页面 | 解析数据源入参 → 调业务数据源 → 生成端到端协议 |
| **update** | 用户点选/交互 | 重新解析 → 生成新协议 → 前端更新渲染 |
| **submit** | 用户提交 | 直接返回数据源出参，前端执行提交回调 |

## 节点与物料

| 术语 | 说明 |
|------|------|
| **NORMAL_MODULE** | 普通渲染节点 |
| **HANDLER_MODULE** | 只执行逻辑、不渲染 UI 的节点 |
| **LIST_CONTAINER** | 列表容器节点 |
| **STATIC / static** | 编译时静态处理，不参与渲染树（`MaterialConfig.buildIn='static'`） |
| **lowCode** | 低代码物料（yooz 拖拽） |
| **proCode** | 源码物料（npm 包托管） |
| **materialId** | 物料唯一 id（绝对禁止编造） |
| **description.json** | DUO 配置平台用的物料描述文件 |

## 交互机制

| 术语 | 说明 |
|------|------|
| **updateBy** | 双向绑定机制，update 后重新计算 |
| **emit / on** | 事件系统 |
| **notifyNodeName** | 跨节点通信 |
| **groovy 表达式** | 兼容 Groovy 2.4.17，`{{ }}` 包裹 |
