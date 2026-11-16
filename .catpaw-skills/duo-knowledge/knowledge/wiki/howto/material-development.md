# H2 · 如何开发一个 DUO 物料

> 覆盖范围：从零创建 proCode 物料包、编写组件代码、注册到 yooz 平台、在页面工程中引用，以及物料升级发布的完整流程。

---

## 1. 物料工程结构

DUO 物料以 **monorepo** 形式组织，使用 pnpm + lerna 管理多包。典型目录结构如下：

```
biz-cross-transaction-material/   ← 物料仓库根目录
├── duo.config.json               ← DUO 物料工程配置
├── lerna.json                    ← lerna 配置（version: independent）
├── package.json                  ← 根 package（含 build/publish 脚本）
├── build.json / build-umd.js     ← max-app 构建配置
├── packages/                     ← 各物料包
│   ├── common-custom-view/
│   │   ├── src/
│   │   │   ├── index.tsx         ← 组件入口
│   │   │   └── types.ts          ← Props 类型定义
│   │   └── package.json
│   ├── common-duo-lifecycle/
│   │   ├── src/
│   │   │   └── index.ts          ← 逻辑物料入口
│   │   └── package.json
│   └── ...
└── preview/                      ← 本地预览工程
```

`duo.config.json` 关键字段：

```json
{
  "packageScope": "@meishi",      // npm scope
  "packagePath": "packages",      // 物料包目录
  "npmPrefix": "common-",         // 包名前缀（可选）
  "scopeId": "15"                 // yooz 平台的 scope ID
}
```

---

## 2. 创建新物料包

在仓库根目录执行：

```shell
pnpm duo new-pkg
```

按提示输入物料名称（kebab-case），工具会在 `packages/` 下生成标准目录结构，包含 `src/index.tsx`、`src/types.ts`、`package.json` 等模板文件。

生成的 `package.json` 关键字段：

```json
{
  "name": "@meishi/common-my-material",
  "version": "1.0.0",
  "scripts": {
    "_build0": "../../node_modules/.bin/max-app build --config ../../build-no-weapp.json --skip-demo",
    "_build1": "../../node_modules/.bin/max-app build --config ../../build-umd.js --skip-demo && pnpm run mv:web-bundle",
    "mv:web-bundle": "mkdir -p web-bundle && mv lib/react-umd-bundle/index.js web-bundle/",
    "_build": "pnpm run _build1 && pnpm run _build0",
    "build": "pnpm run _build && pnpm run _clean",
    "clean": "pnpm run _clean && rm -rf es lib",
    "prepublishOnly": "pnpm build"
  },
  "peerDependencies": {
    "@max/max": "^1.0.0"
  }
}
```

---

## 3. 编写视图物料（NORMAL_MODULE）

### 3.1 types.ts — Props 类型定义

使用 JSDoc 注释描述每个 prop，yooz 平台会解析这些注释生成配置面板：

```typescript
// src/types.ts
import type { CSSProperties, MaxNode } from '@max/max';
import type { StyleProp } from '@max/leez-style-util';

export interface MyMaterialProps {
  /**
   * @label 标题文本
   * @desc 显示在卡片顶部的标题
   */
  title?: string;

  /**
   * @label 是否显示
   * @default true
   */
  visible?: boolean;

  /**
   * @label 点击回调
   */
  onClick?: () => void;

  // 样式（DUO 引擎通过 styles 字段传入）
  style?: StyleProp<CSSProperties>;
  children?: MaxNode;
}
```

### 3.2 index.tsx — 组件实现

```typescript
// src/index.tsx
import { createElement, memo } from '@max/max';
import View from '@hfe/max-view';
import type { MyMaterialProps } from './types';

export type { MyMaterialProps };

function MyMaterial(props: MyMaterialProps) {
  const { title, visible = true, onClick, style, children } = props;

  if (!visible) return null;

  return (
    <View style={style} onClick={onClick}>
      {title && <View>{title}</View>}
      {children}
    </View>
  );
}

export default memo(MyMaterial) as typeof MyMaterial;
```

**注意**：不要在组件内直接使用 `props.__duo__`，除非该组件只在 DUO 页面中使用。如需触发生命周期，通过 `onClick` 等回调 prop 向上传递，由协议层的 `on` 事件绑定处理。

### 3.3 逻辑物料（HANDLER_MODULE）

逻辑物料不渲染 UI，通常暴露若干方法供其他节点通过 `callMethod` 调用：

```typescript
// src/index.ts（注意是 .ts 不是 .tsx）
import type {
  UpdateOptions,
  SubmitOptions,
  LifecycleCallbacks,
} from '@meishi/duo-protocol';

interface DuoInjectProps {
  __duo__: {
    emit: (key: string, opts: any, ...rest: any[]) => void;
  };
}

// 暴露 update 方法，供 logics.groovy 中 callMethod 调用
export function update(options: UpdateOptions & LifecycleCallbacks & DuoInjectProps) {
  options.__duo__.emit('update', options, options);
}

// 暴露 submit 方法
export function submit(options: SubmitOptions & LifecycleCallbacks & DuoInjectProps) {
  options.__duo__.emit('submit', options, options);
}
```

---

## 4. 物料注册到 yooz 平台

### 4.1 本地构建

```shell
# 在物料仓库根目录下，构建单个包
cd packages/common-my-material  # 进入对应包目录
pnpm build

# 构建所有包（在物料仓库根目录执行）
pnpm build  # 等价于 lerna run build
```

构建产物：
- `es/`：ESM 格式，供 MRN/小程序使用
- `lib/`：CJS 格式
- `web-bundle/index.js`：UMD 格式，供 Web/H5 使用（上传到 S3）

### 4.2 发布到 npm

发布前检查（`prepublishOnly` 脚本自动执行）：
1. 确认当前分支是 `release`（测试版）或 `master`（正式版）
2. 确认 git 工作区无未提交修改

```shell
# 在仓库根目录执行
pnpm duo-pre-publish   # 生成文档 + 更新版本号（lerna version）
pnpm duo-publish       # 发布到 npm + 上传 web-bundle 到 S3
```

`duo-publish` 等价于：

```shell
pnpm lerna-publish from-package   # 发布所有版本号有变化的包
pnpm duo publish-pkg              # 上传 web-bundle 到 S3，更新 yooz 平台物料记录
```

### 4.3 在 yooz 平台确认物料

发布成功后，在 [yooz 物料平台](https://yooz.sankuai.com/client-platform/material/component) 搜索包名，确认新版本已出现在版本列表中，并检查 `configSchema`（props/slots/events 定义）是否正确解析。

---

## 5. 在页面工程中引用物料

### 5.1 更新 dependencies.json

在页面协议的 `dependencies.json` 中添加新物料的 npm 包和 S3 地址：

```json
[
  {
    "name": "@meishi/common-my-material",
    "version": "1.0.0",
    "type": "component",
    "url": "https://s3plus-bj02.sankuai.com/yooz-assets/material/@meishi/common-my-material/1.0.0/index.js"
  }
]
```

### 5.2 更新 componentsMap.json

在 `componentsMap.json` 中为新节点分配 ID 并关联物料：

```json
{
  "42": {
    "id": "物料在yooz平台的ID",
    "materialType": "proCode",
    "type": "component",
    "npm": "@meishi/common-my-material",
    "npmVersion": "1.0.0",
    "web": [
      "https://s3plus-bj02.sankuai.com/yooz-assets/material/@meishi/common-my-material/1.0.0/index.js"
    ]
  }
}
```

`componentsMap.json` 的 key（如 `"42"`）是节点 ID，与 `struct.groovy` 中 `node('NodeName', '42')` 的第二个参数对应。

### 5.3 在 struct.groovy 中使用

```groovy
node('MyMaterial1', '42') {
  label '我的物料'
  props {
    string('title') {{ DATA_SOURCE.data?.title }}
    bool('visible') {{ DATA_SOURCE.data?.showModule == true }}
  }
  style('style') {
    number('marginBottom') {{ 9 }}
  }
  on('onClick') {
    callMethod('MeishiCommonDuoLifecycle1', 'update')
  }
}
```

### 5.4 重新生成页面代码

修改协议文件后，在页面工程根目录执行：

```shell
yarn generate   # 或 duo-builder generate
```

这会根据 `duo.config.js` 中的 `pageId` 从平台拉取最新协议，重新生成 componentMap、logicMap 等前端代码。

---

## 6. 物料升级

### 6.1 升级步骤

1. 在物料仓库修改代码，执行 `pnpm build` 验证构建通过
2. 执行 `pnpm duo-pre-publish` 更新版本号（遵循 semver）
3. 执行 `pnpm duo-publish` 发布
4. 在页面工程的 `dependencies.json` 和 `componentsMap.json` 中更新版本号和 S3 URL
5. 执行 `yarn generate` 重新生成代码
6. 本地验证后提 PR

### 6.2 版本号规范

遵循 semver：
- **patch**（`1.0.x`）：Bug 修复，向后兼容
- **minor**（`1.x.0`）：新增功能，向后兼容
- **major**（`x.0.0`）：破坏性变更，需通知所有使用方

测试版本使用 prerelease 标签，如 `1.0.1-beta.1`，发布到 `release` 分支。

### 6.3 注意事项

升级物料时，如果修改了 `MaterialConfig`（props/slots/events 定义），需要同步更新 yooz 平台的物料配置，否则搭建平台的配置面板会与实际组件不一致。

删除或重命名 prop 属于破坏性变更，需要 major 版本号，并提前通知所有使用该物料的页面工程负责人。

---

## 附：常见问题

**Q: 构建报错 `Cannot find module '@max/max'`？**
检查 `peerDependencies` 是否正确声明，并确认物料仓库根目录已执行 `pnpm install`（pnpm workspace 会将 peerDependencies 提升到根目录）。

**Q: web-bundle 上传失败？**
确认已登录 npm（`npm whoami`），且有对应 scope 的发布权限。S3 上传由 `duo publish-pkg` 命令处理，失败时检查网络和权限。

**Q: yooz 平台看不到新版本？**
`duo publish-pkg` 执行后需要等待约 1-2 分钟同步。如果超时仍未出现，检查 `duo.config.json` 中的 `scopeId` 是否正确。

**Q: 物料在 MRN 正常但 Web 白屏？**
检查 `web-bundle/index.js` 是否正确生成（UMD 格式），以及 `dependencies.json` 中的 S3 URL 是否可访问。Web 端通过 S3 URL 动态加载物料，MRN 端通过 npm 包静态引入。
