# H4 · 如何构建与发布 DUO 页面

> 覆盖范围：页面工程的本地构建命令、多端产物说明、FEDO 流水线发布流程、灰度放量与回滚操作。

---

## 1. 页面工程结构

DUO 页面工程以 `duo-page` 仓库为基础，每个页面对应一个独立的工程目录（通常由 FEDO 模板自动创建）。核心文件如下：

```
page-latest/                      ← 页面工程根目录
├── duo.config.js                 ← DUO 构建配置（pageId、环境变量等）
├── package.json                  ← 依赖和脚本
├── scripts/
│   └── installDuo.js             ← 自动安装/更新 duo-builder
└── node_modules/
    └── @meishi/duo-builder/      ← DUO 构建工具（stable 版本）
```

`duo.config.js` 关键配置项：

```javascript
const config = {
  pageId: process.env.DUO_PAGE_ID,                    // 页面 ID（必填）
  pageProtocolId: process.env.DUO_PAGE_PROTOCOL_ID,   // 协议 ID
  pageProtocolVersion: process.env.DUO_PAGE_PROTOCOL_VERSION,
  webAppmockConfig: false,                            // 是否生成 AppMock 配置入口
  usePn: false,                                       // 是否开启预请求
  isDevBundle: false,                                 // 是否测试包
  h5guard: true,                                      // 是否开启 H5 验签
};
module.exports = config;
```

---

## 2. 本地开发命令

### 2.1 启动本地开发服务

```shell
# 默认（MRN + Web 双端）
yarn dev

# 仅 Web 端
yarn dev:web
# 等价于：git pull && yarn installDuo && MAX_TARGET_ENV=web duo-builder dev

# 仅 MRN 端
yarn dev:mrn
# 等价于：git pull && yarn installDuo && MAX_TARGET_ENV=mrn duo-builder dev

# 鸿蒙端
yarn dev:oh
# 等价于：git pull && yarn installDuo && MRN_HARMONY=true duo-builder dev
```

`yarn dev` 会自动执行：
1. `git pull`：拉取最新代码
2. `yarn installDuo`：检查并更新 `@meishi/duo-builder` 到 stable 版本
3. `duo-builder dev`：启动构建 + 本地 Dev Server

### 2.2 重新生成代码

当协议文件（`constData.groovy`、`struct.groovy` 等）有变更，或需要从平台拉取最新协议时：

```shell
yarn generate
# 等价于：duo-builder generate
```

`generate` 命令会：
1. 根据 `duo.config.js` 中的 `pageId` 从 DUO 平台拉取最新 `PageProtocol`
2. 调用 `toGroovy` 将 JSON 协议转换为 Groovy 文件
3. 生成前端代码（componentMap、logicMap、页面入口等）

### 2.3 环境变量控制

```shell
# 使用测试环境协议（而非生产环境）
DUO_PROTOCOL_ENV=test yarn dev

# 跳过自动安装依赖（加速启动）
DUO__DEV_SKIP_INSTALL_DEPS=true yarn dev

# 跳过 lint 检查
DUO__DEV_SKIP_LINT=true yarn dev

# 使用测试包（isDevBundle=true）
DUO_DEVBUNDLE=true yarn dev
```

---

## 3. 多端产物说明

DUO 页面支持三类产物，由 `duo-builder` 统一构建：

| 产物 | 环境变量 | 说明 |
|------|---------|------|
| **MRN**（React Native） | `MAX_TARGET_ENV=mrn` | 美团/点评 App 内的 RN 页面 |
| **Web/H5** | `MAX_TARGET_ENV=web` | 浏览器 H5 页面 |
| **微信小程序** | `MAX_TARGET_ENV=wechat-miniprogram` | 微信小程序页面 |
| **鸿蒙** | `MRN_HARMONY=true` | 鸿蒙 App 内的 RN 页面 |

构建产物目录：

```
build/
├── mrn/                    ← MRN 产物（jsbundle）
├── web/                    ← Web 产物（HTML + JS + CSS）
├── wechat-miniprogram/     ← 小程序产物（wxml + js + wxss）
└── harmony/                ← 鸿蒙产物
```

**Web 产物特殊说明**：Web 端通过 S3 CDN 加载物料的 `web-bundle`（UMD 格式），物料的 S3 URL 来自 `dependencies.json`。MRN 端通过 npm 包静态打包，不依赖 S3。

---

## 4. FEDO 流水线发布

### 4.1 发布模板选择

DUO 页面必须使用官方 FEDO 模板，不得手动部署：

| 模板名称 | 用途 |
|---------|------|
| **DUO 开发模板(分支版2.0)** | 日常需求开发，含完整 CI/CD 流程 |
| **DUO Bugfix 模板(分支版2.0)** | 线上 Bug 修复，流程更精简 |
| **DUO Web部署Talos2.0（分支版2.0）** | 单独部署 Web 产物 |

所有模板在 [DUO 研发组](https://fedo.sankuai.com/group/255) 下选取。业务页面的 FEDO 项目必须建立在各自业务方向的研发组里，DUO 研发组仅供 RD 测试使用。

### 4.2 标准发布流程

```
1. 创建迭代（FEDO）
   ↓
2. 创建开发任务，关联 ONES 需求
   ↓
3. 从 develop 创建 feature/* 分支开发
   ↓
4. 提 PR → 至少 2 人 approve → 合并到 develop
   ↓
5. 触发 FEDO 构建流水线（develop 分支）
   ↓
6. 测试环境验证（Web + MRN 双端）
   ↓
7. develop → release/* 分支
   ↓
8. 触发 FEDO 发布流水线（release 分支）
   ↓
9. 灰度放量（从 1% 逐步扩大）
   ↓
10. 全量发布
```

### 4.3 五端齐发

建议使用**五端齐发流水线**统一发布 Web、MRN、小程序等多端产物，避免多端版本不一致：

```
五端齐发流水线
├── Web 产物部署（Talos）
├── MRN 产物发布（jsbundle 上传）
├── 微信小程序发布
├── 鸿蒙产物发布
└── 版本号同步
```

---

## 5. 灰度放量

### 5.1 灰度策略

DUO 页面支持按以下维度灰度：
- **用户比例**：按 userId 哈希，从 1% 逐步扩大到 100%
- **城市**：指定城市先行放量
- **设备**：指定 App 版本或设备类型

### 5.2 放量步骤

1. 在 FEDO 流水线中找到「灰度放量」节点
2. 配置灰度规则（比例/城市/设备）
3. 点击「开始灰度」
4. 观察监控指标（错误率、成功率、响应时间）
5. 无异常后逐步扩大比例，直到 100% 全量

### 5.3 监控指标

灰度期间重点关注：
- **JSError 错误率**：在 Raptor 平台查看，异常升高需立即回滚
- **接口成功率**：DUO 端到端接口（`duo_csdk_v` 标识）的成功率
- **页面加载时长**：FFP（First Frame Paint）指标

---

## 6. 回滚操作

### 6.1 快速回滚

在 FEDO 流水线中找到上一个成功的发布记录，点击「回滚」按钮，系统会自动将产物回滚到上一版本。

**Web 产物回滚**：Talos 部署支持一键回滚，回滚后 CDN 缓存会在 5 分钟内刷新。

**MRN 产物回滚**：jsbundle 回滚后，App 内的 RN 页面会在下次启动时加载旧版本（热更新机制）。

### 6.2 紧急回滚

如果 FEDO 流水线不可用，可以通过以下方式紧急回滚：

```shell
# 1. 切换到上一个稳定的 release 分支
git checkout release/stable-version

# 2. 手动触发构建（需要有 FEDO 权限）
# 在 FEDO 平台手动触发对应分支的构建流水线

# 3. 或者直接在 Talos 平台回滚 Web 产物
# Talos 控制台 → 应用 → 版本历史 → 选择稳定版本 → 回滚
```

---

## 7. 常见构建问题

**Q: `yarn dev` 启动后页面空白？**
检查 `duo.config.js` 中的 `pageId` 是否正确，以及网络是否能访问 DUO 平台接口。执行 `yarn generate` 重新拉取协议后再启动。

**Q: 构建报错 `Cannot resolve module '@meishi/xxx'`？**
物料包未安装。检查 `dependencies.json` 中的版本号，执行 `yarn installDuo` 更新 duo-builder，再执行 `yarn generate` 重新安装依赖。

**Q: Web 端物料加载失败（404）？**
`dependencies.json` 中的 S3 URL 不可访问。确认物料已发布到 S3（执行 `pnpm duo-publish` 后等待 1-2 分钟），或检查 URL 中的版本号是否与 `npmVersion` 一致。

**Q: MRN 端正常但 Web 端样式异常？**
MRN 和 Web 使用不同的样式系统。检查是否使用了 MRN 专有的样式属性，Web 端需要使用标准 CSS 属性。

**Q: 小程序端构建失败？**
检查是否使用了 MRN/Web 专有的 API，小程序端需要使用 MSI 跨端 API。参考 `msi-coding` skill 查询兼容性。

**Q: 灰度后发现问题，如何快速定位？**
在 Raptor 平台搜索 `duo_csdk_v` 接口的错误日志，查看 `bizReq`（接口入参）和错误信息。结合 AppMock 复现问题，修改 Groovy 表达式后重新发布。

---

## 附：duo-builder 版本管理

`duo-builder` 使用 `stable` tag 追踪最新稳定版本，`installDuo.js` 脚本会在每次 `yarn dev` 时自动检查并更新：

```javascript
// 检查逻辑（简化）
const installedVersion = require('@meishi/duo-builder/package.json').version;
const stableVersion = getLatestStableVersion();  // 从 npm registry 查询

if (installedVersion !== stableVersion) {
  execSync(`yarn add @meishi/duo-builder@${stableVersion}`);
}
```

如果需要固定版本（如调试特定 bug），可以在 `package.json` 中将 `"@meishi/duo-builder": "stable"` 改为具体版本号，并在 `installDuo.js` 中传入 `--no-stable` 参数跳过自动更新：

```shell
DUO_NO_STABLE=1 yarn dev
```
