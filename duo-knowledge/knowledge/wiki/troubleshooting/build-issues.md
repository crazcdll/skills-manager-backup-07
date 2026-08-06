# T3 · 出码与联调异常排查

> 覆盖范围：`duo-builder generate` / `duo-builder dev` 出码失败、依赖安装失败、联调服务异常等问题的定位与修复。
>
> **注意**：本文档针对的是 `duo-builder` 的**页面代码生成**流程，不涉及物料包构建（物料构建由各物料仓库自己的脚本负责）。

---

## 快速定位流程

```
出码/联调异常
  1. 协议拉取失败？ -> 检查 pageId / pageProtocolId / pageProtocolVersion 配置，以及网络/鉴权
  2. 物料拉取失败？ -> 检查 Yooz 平台物料是否已发布，以及网络/鉴权
  3. 代码生成报错？ -> 看具体报错信息，定位是哪个 generator 文件出错
  4. 依赖安装失败？ -> 检查 yarn.lock 同步状态，或尝试跳过 lock 同步
  5. dev 模式无响应？ -> 检查 WebSocket 端口是否被占用，DUO 平台是否已连接
```

---

## 1. 协议拉取失败

### 1.1 配置项缺失或错误

**现象**：`duo-builder generate` 报 `加载页面协议失败`，或提示 `pageId is required`。

**原因**：`duo.config.js` 中 `pageId`、`pageProtocolId`、`pageProtocolVersion` 未配置或配置错误。

**排查**：

```bash
# 查看 duo-builder 打印的最终配置
duo-builder generate
# 输出中会打印 "最终 duo 配置:"，检查三个必填字段是否正确
```

**修复**：在 `duo.config.js` 中补全配置：

```javascript
module.exports = {
  pageId: 'your-page-id',
  pageProtocolId: 'your-protocol-id',
  pageProtocolVersion: 'your-protocol-version',
};
```

### 1.2 鉴权失败（非 prod 环境）

**现象**：报 `加载页面协议失败`，HTTP 状态码为 401 或 403。

**原因**：访问测试环境或泳道时，需要额外的鉴权 header（`accessHttpAuthToken`）。

**排查**：检查 `_devEnv` 配置是否与实际环境匹配，以及鉴权 token 是否有效。

### 1.3 使用草稿协议跳过远程拉取

如果需要调试未保存的协议，可以在 `duo.config.js` 中传入 `draftProtocol`，`duo-builder` 会直接使用此协议字符串，不发起远程请求：

```javascript
module.exports = {
  pageId: 'your-page-id',
  pageProtocolId: 'your-protocol-id',
  pageProtocolVersion: 'your-protocol-version',
  // 传入协议 JSON 字符串，跳过远程拉取
  draftProtocol: JSON.stringify({ /* 协议内容 */ }),
};
```

---

## 2. 物料拉取失败

### 2.1 物料未在 Yooz 平台发布

**现象**：报 `拉取物料协议为空` 或 `拉取物料协议失败`。

**原因**：协议中引用的物料在 Yooz 平台上没有对应的发布版本，或发布版本已下线。

**排查**：

1. 在 DUO 配置平台上检查页面使用的物料列表
2. 在 Yooz 平台（`https://yooz.sankuai.com`）确认对应物料已发布且版本可用
3. 检查 `duo-builder` 打印的请求参数中 `ids` 字段，确认物料 ID 正确

**修复**：联系物料负责人重新发布，或在 DUO 配置平台上更换为已发布的物料版本。

### 2.2 物料 configSchema 解析失败

**现象**：报 `物料协议解析失败`，通常伴随 JSON parse 错误。

**原因**：Yooz 平台上该物料的 `configSchema` 字段内容不是合法 JSON。

**修复**：联系物料负责人在 Yooz 平台重新发版，确保 `configSchema` 格式正确。

---

## 3. 代码生成报错

### 3.1 协议版本不兼容

**现象**：出码后产物结构异常，或报 `duoVersion` 相关错误。

**原因**：协议的 `duoVersion` 不是 `'2'` 时，`duo-builder` 会降级调用 `@meishi/duo-builder-v1` 旧版逻辑。如果旧版 builder 也不支持该协议版本，则会报错。

**排查**：检查协议中的 `duoVersion` 字段，确认是否需要升级协议版本。

### 3.2 materialMap 生成失败

**现象**：报错信息包含 `materialMap` 或 `materialMapGenerator`，通常是某个物料的 `config` 字段缺失或格式异常。

**排查**：

1. 检查报错中的 `materialId`，定位是哪个物料出问题
2. 在 Yooz 平台确认该物料的 `configSchema` 格式正确
3. 检查物料的 `config.type` 是否为 `NORMAL_MODULE` 或 `HANDLER_MODULE`

### 3.3 lowCode 物料出码失败

**现象**：报 `yooz 组件出码失败，请在 yooz 平台重新发版` 或 `yooz 逻辑编排出码失败`。

**原因**：物料的 `devMode` 为 `lowCode`，但其 `dsl` 字段内容有误，导致 `@yooz/lowcode-code-generator` 出码失败。

**修复**：

1. 联系物料负责人在 Yooz 平台重新发版，确保 DSL 格式正确
2. 如果需要本地调试，可在 `duo.config.js` 中配置 `yoozComponentDebugMap`，传入本地调试用的 DSL：

```javascript
module.exports = {
  // ...
  yoozComponentDebugMap: {
    'your-material-id': {
      dsl: JSON.stringify({ /* 调试用 DSL */ }),
    },
  },
};
```

### 3.4 useStaticNodes 生成失败

**现象**：报错信息包含 `useStaticNodes` 或 `displayRuleTreeShaking`。

**原因**：协议中某个节点的展示条件（`displayRule`）表达式语法有误，导致 tree shaking 分析失败。

**排查**：检查协议中各节点的 `displayRule` 字段，确认 Groovy 表达式语法正确。

---

## 4. 依赖安装失败

### 4.1 yarn.lock 同步失败

**现象**：报 `lock 文件同步失败` 或 S3 相关错误。

**原因**：`duo-builder` 会从 Yooz S3 接口同步 `yarn.lock`，如果 S3 接口不可用或 lock 文件不存在，会报此错误。

**临时修复**：设置 `_devSkipInstallDeps: true` 跳过依赖安装（仅适用于依赖未变更的情况）：

```javascript
module.exports = {
  // ...
  _devSkipInstallDeps: true,
};
```

或使用环境变量：

```bash
DUO__DEV_SKIP_INSTALL_DEPS=true duo-builder generate
```

### 4.2 依赖安装报错

**现象**：`yarn install` 阶段报 `Cannot find module` 或版本冲突错误。

**排查**：

```bash
# 进入输出目录，手动执行安装查看详细报错
cd .duo-tmp/preview-{pageId}
yarn install --verbose
```

**常见原因**：

- 协议中声明的某个依赖版本在 npm registry 中不存在
- `yarn.lock` 与 `package.json` 中的版本范围不兼容

**修复**：联系 DUO 平台团队检查协议中的依赖版本配置。

---

## 5. dev 联调模式异常

### 5.1 WebSocket 服务启动失败

**现象**：`duo-builder dev` 启动后报端口占用错误。

**排查**：

```bash
# 检查端口是否被占用（默认端口为 8899，可通过 -p 参数指定）
lsof -i :<port>

# 杀掉占用进程
kill -9 <pid>
```

### 5.2 DUO 配置平台无法连接本地服务

**现象**：在 DUO 配置平台点击"预览"后，本地没有触发出码。

**排查**：

1. 确认 `duo-builder dev` 进程正在运行
2. 确认 DUO 配置平台的本地服务地址配置正确（通常为 `ws://localhost:{port}`）
3. 检查防火墙或代理设置是否阻止了 WebSocket 连接

### 5.3 源码组件调试不生效

**现象**：`dev` 模式下修改了源码组件，但预览页面没有更新。

**原因**：源码组件调试依赖 `duo-cli` 通过 Unix Socket（`/tmp/duo.sock`）向 `duo-builder` 注册调试信息。如果 `duo-cli` 未启动或 socket 连接断开，调试信息不会传递。

**排查**：

1. 确认 `duo-cli` 已启动并正常运行
2. 检查 `/tmp/duo.sock` 文件是否存在
3. 查看 `duo-builder dev` 的日志，确认是否有 `源码组件调试启动失败` 的错误信息

### 5.4 出码后预览页面无法启动

**现象**：出码成功，但 `yarn start:main` 执行失败，预览页面无法访问。

**排查**：

```bash
# 进入输出目录，手动执行启动命令查看报错
cd .duo-tmp/preview-{pageId}
yarn start:main
```

如果不需要自动启动预览，可以关闭此行为：

```javascript
module.exports = {
  // ...
  _devYarnStart: false,
};
```

---

## 6. 出码产物异常

### 6.1 materialMap 中缺少某个物料

**现象**：出码成功，但运行时报 `componentMap 中找不到 materialId xxx`。

**原因**：该物料在协议 `componentsMap` 中有注册，但 `usedMaterialIdSet` 中没有（即协议 struct/logics 中没有实际使用），导致 `loadMaterials` 时被过滤掉。

**排查**：检查协议中该物料是否真的被使用，或联系 DUO 平台团队检查 `usedMaterialIdSet` 的计算逻辑。

### 6.2 预请求配置未生成

**现象**：`pn/` 目录下没有预请求配置文件。

**原因**：`usePn` 未开启，或协议中没有配置预请求相关信息。

**修复**：在 `duo.config.js` 中开启预请求：

```javascript
module.exports = {
  // ...
  usePn: true,
};
```

### 6.3 鸿蒙端依赖安装失败

**现象**：鸿蒙端出码后，`oh-better-install` 执行失败。

**排查**：检查 `oh-package.json` 中的依赖版本是否在鸿蒙 npm registry 中存在，以及鸿蒙开发环境是否正确配置。

---

## 附：出码前检查清单

执行 `duo-builder generate` 前确认以下内容：

- [ ] `duo.config.js` 中 `pageId`、`pageProtocolId`、`pageProtocolVersion` 已正确配置
- [ ] 网络可访问 DUO 服务端（`_devEnv` 对应的环境）
- [ ] 网络可访问 Yooz 平台（物料发布协议拉取）
- [ ] 协议中使用的所有物料已在 Yooz 平台发布
- [ ] 如有 lowCode 物料，确认其 DSL 在 Yooz 平台上格式正确
