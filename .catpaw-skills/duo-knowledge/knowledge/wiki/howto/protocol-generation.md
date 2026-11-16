# H · DUO 协议生成

> 覆盖范围：物料描述协议（description.json）的生成方式、搭建协议的配置流程、事件配置原理，以及协议与代码的关联关系。

---

## 1. 两类协议概述

DUO 体系中存在两类协议，职责不同：

**物料描述协议（description.json）** 描述一个物料组件对外暴露的 props、events、slots 等接口，是搭建平台识别和配置物料的元数据。由 `duo-cli` 工具从 TypeScript 源码自动生成。

**搭建协议（页面协议）** 描述一个具体页面的完整配置，包含视图树结构、逻辑节点列表、数据源绑定、节点属性表达式等。由开发者在 DUO 配置平台上通过可视化操作生成，最终以 JSON 形式存储在 Git 仓库中。

---

## 2. 物料描述协议生成（docgen）

### 2.1 工具安装

```shell
npm install @meishi/duo-cli -g
# 检查版本，需要 >= 0.4.15
duo -V
```

### 2.2 生成命令

在物料目录下执行：

```shell
# 非 MCP 物料
duo doc-gen

# MCP 物料
duo mcp-doc-gen
```

命令会读取物料的 TypeScript 类型定义，生成 `description.json` 文件。

### 2.3 JSDoc 注解规范

`duo doc-gen` 依赖 JSDoc 注解来生成完整的描述信息。支持以下注解标签：

**`@label`** — 字段的中文显示名称（必填，否则搭建平台无法展示）

**`@default`** — 字段的默认值说明

**`@desc`** — 字段的补充描述，如取值范围、注意事项

示例：

```typescript
/**
 * @label 是否隐藏标题前的断线
 * @default false
 */
disableLineMark?: boolean;

/**
 * @label 高度相对屏高比例
 * @desc 取值范围 (0, 1]
 */
heightPercent?: number;
```

生成的 description.json 片段：

```json
{
  "name": "disableLineMark",
  "required": false,
  "styleType": null,
  "label": "是否隐藏标题前的断线",
  "desc": null,
  "defaultValue": null,
  "type": "Boolean"
}
```

### 2.4 样式字段

类型为 `CSSProperties` 的字段会被识别为样式字段，`styleType` 自动设为 `"view"`：

```typescript
/**
 * @label 顶部容器样式
 */
topStyle?: CSSProperties;
```

生成结果中 `"styleType": "view"`，搭建平台会为其渲染样式编辑器。

### 2.5 事件（函数类型）字段

函数类型的 props 会被归类到 `events.emit` 数组中，需要手动编写（`duo doc-gen` 无法自动推断函数签名的语义）：

```typescript
/**
 * 下拉刷新回调
 */
onRefresh?: (ref: RefObject<ScrollViewRefObject>) => void;
```

生成的 description.json 中 `events.emit` 结构：

```json
{
  "events": {
    "emit": [
      {
        "name": "onRefresh",
        "required": false,
        "label": "下拉刷新回调",
        "type": "Any",
        "returnValue": { "type": "void" },
        "props": [...]
      }
    ]
  }
}
```

### 2.6 buildIn 字段

`buildIn` 字段声明组件的特殊内置角色，需在 description.json 中手动配置（不由 docgen 生成）：

```json
"buildIn": "static"
// 或
"buildIn": "pageContainer"
```

`static` 表示静态节点，在 preview 接口返回前就 mount，数据不参与数据流转，**非必要禁止使用**，且必须是视图树顶层节点。

`pageContainer` 表示页面容器，同样在 preview 前 mount，DUO 会将 loading 视图和异常视图作为 `props.children` 传入，可用于自定义加载态和错误态。一个页面只能有一个 pageContainer，且必须是顶层节点。

---

## 3. 搭建协议配置流程

### 3.1 新建页面

在 [DUO 配置平台](https://duo.sankuai.com/portal/page/list/duo-test-test-test) 中，选择业务线后新增页面，需填写：

- **后端 appKey**：用于服务端登记，向后端 RD 确认
- **研发组**：选择 FEDO 中对应的业务研发组（非 DUO 研发组）
- **MRN 路径**：格式为 `rn_{biz}_{name}&{component}`，例如 `rn_meishi_food-order-submit&Submit`
- **H5 路径**：页面唯一标识，最终生成地址为 `https://awp.meituan.com/dfe/duo-page/{path}/web/index.html`
- **仓库**：存储页面代码的 Git 仓库路径，填写后不可修改；仓库需添加 `hfestash/hfe_stash`、`FEDO小助手/it_fedo`、`MCD/git_cd` 三个成员权限

提交后平台会自动创建初始化 commit，合并 PR 即完成创建。

### 3.2 静态配置

页面创建后，在配置平台的静态配置区域设置：

- **接口前缀**：preview / update / submit 三个接口的 URL 前缀
- **页面跳链参数**：声明页面入参（仅用于校验和上报 Raptor 指标）
- **系统环境参数**：勾选需要的 COMMON_PARAMS 字段，不需要的不勾选以提升秒开速度

### 3.3 配置数据源

在"数据"Tab 下选择业务线，新增数据源（需后端先创建对应的数据返回模型）。数据源对应后端的一个业务接口，配置其入参表达式（Groovy）。

### 3.4 配置视图和逻辑

从物料列表拖拽视图物料到视图树，从逻辑物料列表拖拽逻辑物料到逻辑列表。每个节点可配置：

- **props**：属性值，支持 Groovy 表达式
- **styles**：样式值
- **displayRule**：显示/隐藏条件，Groovy 表达式，建议用 `!!` 保证结果为 boolean
- **events**：事件绑定，触发 update/submit 或调用其他节点方法

### 3.5 平台调试

本地启动 duo-page 工程后，在配置平台开启调试模式，可实时预览配置效果。

仓库地址：`ssh://git@git.sankuai.com/dfe/duo-page.git`，克隆后进入 `page-latest/` 目录执行：

```shell
yarn dev          # 同时启动 Web 和 MRN
yarn dev:mrn      # 仅 MRN
yarn dev:web      # 仅 Web
```

启动后在配置平台打开调试开关，本地服务与平台联动。可用手机扫码预览 MRN 页面，用浏览器预览 H5 页面。

---

## 4. 事件配置

### 4.1 组件间方法调用

当组件 B 需要暴露方法供组件 A 调用时，通过 DUO 事件配置实现：

**第一步：组件 B 实现方法**

- proCode 函数式组件：使用 `forwardRef` + `useImperativeHandle()` 主动暴露方法
- proCode 类组件 / lowCode 组件：正常编写 method 即可

**第二步：声明对外暴露**

- lowCode 组件：在搭建平台"组件根节点 → 高级"中勾选要暴露的方法名，平台自动生成描述协议
- proCode 组件：在 description.json 的 `events.on` 中手动声明：

```json
{
  "events": {
    "on": [
      {
        "name": "onTest",
        "label": "onTest",
        "type": "",
        "desc": "描述"
      }
    ]
  }
}
```

**第三步：组件 A 配置调用**

组件 A 的入参中增加 `onTestCb`，在组件 A 内通过 `this.props.onTestCb()` 调用。在 DUO 配置平台的"触发事件"Tab 中配置事件绑定关系。

### 4.2 参数传递

事件调用时支持两种传参方式：

**配置事件数据方式**：在平台上直接配置静态参数对象，组件 B 的 `onTest` 收到的参数为配置的对象（MRN 侧会额外注入 `rootTag`）。

**透传参数方式**：将组件 A 调用时的实参透传给组件 B。支持展开形式（`this.props.onTestCb(1, 2, 3)`）和对象形式（`this.props.onTestCb({ title: 'a' })`）。

参数传递的底层原理是 JSONPath 映射：`from` 指定来源路径，`to` 指定目标路径，接收方合并收到所有参数：

```javascript
const value = !from ? args[0] : /^\d/.test(from) ? get(args, from) : get(args[0], from);
if (!to) {
  props = { ...props, ...value };
} else {
  props = set(props, to, value);
}
```

---

## 5. props.__duo__ 注入

DUO 引擎会自动向每个组件注入 `props.__duo__`，提供以下能力：

```typescript
interface DuoInjectHandler {
  emit: (key: string, opts: any, ...rest: any[]) => void;  // 触发 preview/update/submit
  renderNode: (node: RenderNode) => any;                    // 渲染子节点
  getPageQuery: () => PageQuery | undefined;                // 获取页面跳链参数
  getCommonParams: () => CommonParams | undefined;          // 获取通参（同步）
  getCommonParamsAsync: () => Promise<CommonParams>;        // 获取通参（异步）
  getRequestInfo: () => DuoEngineRequestInfo | undefined;   // 获取请求基本信息
  getPageState: () => DuoPageState & { updatePropMap };     // 获取页面状态
  setPageState: (state) => void;                            // 更新页面状态
  forceRender: () => void;                                  // 强制重新渲染
  getNodeKey: (node: RenderNode) => string;                 // 获取节点唯一 key
  getNodeData: (node: RenderNode) => RenderNodeData;        // 获取节点数据
  dangerouslyRefreshCommonParams: (params) => void;         // 刷新通参（慎用）
}
```

**注意**：如果组件强依赖 `this.props.__duo__`，该组件就只能在 DUO 页面中使用，无法独立复用。

`getPageState()` 返回的 `ready` 字段可用于判断页面状态：`ready=false` 表示加载中，`ready=true` 表示加载完成，`isError=true` 表示接口返回异常。

---

## 6. 协议文件结构

搭建协议最终以 JSON 文件形式存储在 Git 仓库中，核心字段结构如下：

```json
{
  "pageId": "xxx",
  "pageProtocolId": "xxx",
  "pageProtocolVersion": "xxx",
  "struct": [
    {
      "nodeName": "ProductListModule",
      "slots": {
        "default": [...]
      }
    }
  ],
  "logics": [
    {
      "nodeName": "MeishiGcGroupOrderLogic1"
    }
  ],
  "nodeDataMap": {
    "ProductListModule": {
      "materialId": "xxx",
      "props": { "title": "CONST.pageTitle" },
      "styles": {},
      "events": {
        "emit": {
          "onItemPress": [...]
        }
      }
    }
  }
}
```

`struct` 是视图树，`logics` 是逻辑节点列表，`nodeDataMap` 存储每个节点的完整配置（props 表达式、样式、事件绑定）。

---

## 附：常见问题

**Q: `duo doc-gen` 生成的 description.json 中 label 为空怎么办？**
检查 TypeScript 注释是否使用了 `/** */` 格式（JSDoc），并添加 `@label` 标签。普通的 `//` 注释不会被解析。

**Q: static 节点和 pageContainer 节点的区别？**
两者都在 preview 接口返回前 mount。区别在于：一个页面可以有多个 static 节点，但只能有一个 pageContainer；pageContainer 会接收 DUO 注入的 `props.children`（loading/error 视图），static 节点不会。两者都必须是视图树顶层节点。

**Q: 如何在 pageContainer 中自定义 loading 态？**
通过 `props.__duo__.getPageState()` 判断 `ready` 状态，当 `ready=false` 时渲染自定义 loading 视图，或直接渲染 DUO 注入的 `props.children`。

**Q: 事件配置中 MRN 侧为什么会多一个 rootTag 参数？**
MRN 侧所有事件调用都会自动注入 `rootTag`（React Native 的根节点标识），这是 MRN 容器的固有行为，无法关闭。接收方需要注意兼容。
