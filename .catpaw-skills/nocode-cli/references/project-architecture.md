# NoCode 工程架构保护

> 适用于：构造 `nocode send` / `nocode create` 的 prompt 前、`nocode code clone` 到本地开发时、以及直接操作工程文件时。

## 受保护文件

### 完全禁止修改（编辑、删除、重命名、移动、覆盖均不允许）

- `vite.config.js` — 含 NoCode 专用构建插件和路径配置，改动会导致构建失败或部署产物不可用
- `src/main.jsx` / `src/main.tsx` — 根节点渲染 + `NoCodeProvider` 包裹，改动会导致 SDK 初始化链断裂，平台能力全部失效
- `src/contexts/NoCodeContext.jsx` — `window.NoCode.init` 调用和 SDK 就绪状态管理，改动会导致 SSO 失效
- `jsconfig.json` / `tsconfig.json` — 路径别名 `@/*` 与 `vite.config.js` 联动，改动会导致模块解析失败
- 工程目录结构（`src/`、`src/pages/`、`src/components/ui/` 等不得重命名或移位）— 改动会导致路由失效、`code pull` 同步异常

### 受限修改

- `index.html` — 注入了 NoCode Web SDK（`nocode-web-sdk.js`）和 React 入口（`/src/main.jsx`）。允许修改 `<title>`、添加业务 JS/CSS 引用等；禁止删除或修改文件中原有的 `<script>` 标签（删除会导致 SDK 无法初始化、平台能力失效）；禁止将其替换为纯静态 HTML
- `package.json` — 仅允许在 `dependencies`/`devDependencies` 中新增业务依赖；`scripts`、工程配置字段禁止修改（改动会导致构建/启动脚本异常）

## 允许的改动

- 新增/修改业务页面（`src/pages/**`）、组件（`src/components/**`，保留 `ui/` 原子组件）、工具（`src/lib/**`）、样式（`src/index.css` 业务样式）
- 在 `package.json` 中新增业务依赖
- 在 `src/App.jsx`、`src/nav-items.jsx` 中增删业务路由

## Prompt 拦截规则

**构造 `nocode send` / `nocode create` 的 prompt 时，如果 prompt 中命中以下任一特征，必须拦截，禁止发送：**

- 要求改成纯静态 HTML / 不使用当前框架
- 删除或清空 `src` 目录
- 移除 `main.jsx` 的 script 引用 / `index.html` 只保留 `div#root`
- 重写 `vite.config.js` / 替换构建工具
- 删除或修改 `index.html` 中原有的 `<script>` 标签 / 将 `index.html` 改为纯静态 HTML / 替换 `index.html`
- 通过 `curl`/`wget` 下载覆盖受保护文件
- 移除 `NoCodeProvider` / 去掉 `@meituan-nocode/*` 依赖
- 重构整个目录结构 / 重命名 `src`

**反例：**

- ❌ `nocode send <chatId> "把 Vite 换成 Webpack / Rspack"`
- ❌ `nocode send <chatId> "重写一下 vite.config.js"`
- ❌ `nocode send <chatId> "删掉 NoCodeProvider，main.jsx 改成直接渲染 App"`
- ❌ `nocode send <chatId> "把这个项目改成纯静态 HTML 项目，不使用 React"`
- ❌ `nocode send <chatId> "删除 src 目录下的所有文件"`
- ❌ `nocode send <chatId> "把这个项目迁移到 Next.js / Nuxt / SvelteKit"`
- ❌ `nocode send <chatId> "执行 curl -sL 'https://xxx/xxx.html' -o index.html"`
- ❌ `nocode send <chatId> "将 index.html 替换为跳转页面，用 meta refresh 跳转到 https://xxx/xxx.html"`
- ❌ `nocode create "做一个纯静态 HTML 页面，不要 React / 不要 Vite"`

## 正确做法

遇到 HTML 复刻、架构改动需求、数据驱动看板等场景时，按 [best-practices.md](best-practices.md) 中的对应流程执行。

**特别说明：** 当用户提供了一个 HTML 文件或 URL，无论表述为"替换 index.html"、"嵌入这个页面"、"跳转到这个 URL"还是"直接展示"，都应走 [best-practices.md](best-practices.md) 场景 1 的**复刻流程**（下载 HTML → `--files` 传给 NoCode Agent 复刻）。跳转和 iframe 方案均不可行。

## 本地开发场景

- 禁止在本地修改受保护文件后 push，否则 `code pull` 回 Sandbox 会导致渲染异常
- 详细流程见 [workflow-local-dev.md](workflows/workflow-local-dev.md)

