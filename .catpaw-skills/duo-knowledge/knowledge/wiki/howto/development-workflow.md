# G · DUO 开发工作流

> 覆盖范围：从创建分支到发布上线的完整流程，包含本地调试、Mock 测试、多端自测规范。

---

## 1. 工程规范

DUO 项目必须使用官方 FEDO 模板创建，不得手工搭建工程结构。

日常需求使用 **DUO 开发模板(分支版2.0)**，Bug 修复使用 **DUO Bugfix 模板(分支版2.0)**，两者均在 [DUO 研发组](https://fedo.sankuai.com/group/255) 下选取。页面的 FEDO 项目必须建立在各自业务方向的研发组里，DUO 研发组仅供 RD 测试使用。

## 2. 分支规范

分支管理遵循 Git Flow 变体：

```
develop（开发主分支，RD 可推送）
  └── feature/*（功能分支，RD 可创建）
        └── PR → 至少 2 人 approve → 合并回 develop
develop → release/*（发布分支，RD 可推送）
release/* → hotfix/*（热修复分支，RD 可创建）
master（只读，禁止任何人直接 push）
```

强制规则：禁止往 `release` 和 `master` 分支直接 push 代码；PR 至少 2 人 approve 后才可合并，approve 后若人工更新代码需重新 review。建议同时创建关联 Draft PR 并在评论中说明意图。

## 3. 配置规范

开发阶段有三条强制配置规范：

**PAYLOAD 仅用于需要后端校验的 update 场景。** preview 时 PAYLOAD 为空，submit 时可能已清空，两者均不应依赖 PAYLOAD。正确用法是在 update 入参中读取 `PAYLOAD.xxx`，并提供 `PREV_DATA` 兜底：

```groovy
// ✅ 正确：update 场景，有兜底
def count = PAYLOAD.quantity ?: PREV_DATA?.quantity ?: 1
[quantity: count, skuId: PAYLOAD.skuId ?: PAGE_QUERY.skuid]

// ❌ 错误：preview 场景使用 PAYLOAD（此时为空）
def count = PAYLOAD.quantity
```

**NODE.X.PROPS 仅在入参时使用，出参用 PREV_DATA。** `NODE.X.PROPS` 读取的是当前渲染帧的前端状态，不稳定；出参应使用 `PREV_DATA` 获取服务端返回的稳定数据：

```groovy
// ✅ 入参：读取其他节点的 props
def epc = NODE.MeishiGcGroupOrderLogic1?.props?.epc ?: CONST.queryEpc

// ✅ 出参：使用 PREV_DATA
{ productList: PREV_DATA?.productList }

// ❌ 出参不应使用 NODE.X.PROPS
{ productList: NODE.ProductListModule?.props?.items }
```

**static 类型组件非必要禁止使用。** static 节点在 preview 接口返回前就 mount，数据在页面生命周期内不会更新，且必须是顶层节点。仅适用于静态配置信息、不响应用户操作的展示内容、与业务逻辑解耦的常量数据。

建议在配置 `displayRule`、`emitConditions` 时使用 `!!` 保证表达式结果是 boolean 类型。

## 4. 本地调试

### 4.1 Web 端调试

在工程根目录执行 `yarn start`（或 `yarn dev`），启动本地 Dev Server，通过浏览器直接访问调试页面。

### 4.2 MRN 端调试

MRN 端通过 Metro Bundler 热更新调试，具体启动命令参见各业务工程的 README。

### 4.3 小程序端调试

小程序端调试分四步：

**第一步：启动 DUO 构建**

```shell
# 方式一：进入 duo-tmp 预览目录
cd .duo-tmp/preview-{pageId}
yarn start:wx

# 方式二：在 page-latest 目录添加命令后执行
# package.json 中增加：
# "dev:wx": "yarn && MAX_TARGET_ENV=wechat-miniprogram duo-builder dev"
yarn dev:wx
```

**第二步：修改宿主壳 app.json（仅本地调试）**

在小程序壳的 `app.json` 中 `subPackages` 新增子包：

```json
{
  "root": "food",
  "pages": ["duo/max/src/index"],
  "lazyCodeLoading": "requiredComponents",
  "rendererOptions": {
    "skyline": { "defaultDisplayBlock": true }
  }
}
```

**第三步：软链接构建产物到宿主壳**

```shell
cd build/wechat-miniprogram   # 前目录是 .duo-tmp/preview-{pageId}
pwd                            # 记录绝对路径，记为"路径1"
cd "小程序壳项目"
mkdir -p duo && cd duo
ln -s "路径1" max
```

> 注意：`mtpt-wxmp` 主干分支 master 使用 `ln -s` 构建会有问题，需手动 copy 构建产物到目标路径。

**第四步：启动宿主壳编译**

不同小程序壳调试方式不统一，以餐侧为例：使用 `mtpt-wxmp` 仓库 `feature/foodWrapper` 分支，执行 `yarn start` 启动 saber 构建。

## 5. Mock 调试

DUO 页面的 Mock 通过拦截端到端接口（`duo_csdk_v` 标识的请求）实现，核心是在请求中注入 `lyrebirdMockResp` 字段。

### 5.1 查看原始入参/出参

连接 AppMock 后，response 中会包含 `bizReq`（实际业务接口入参）和 `bizRes`（实际业务接口出参）字段。不连 AppMock 则不会有这两个字段。使用其他抓包工具时，需在 request header 中添加 `from-appmock=true`。

### 5.2 使用 AppMock 设置 Mock

在 AppMock 中创建 Mock 规则，配置如下：

**Form data（请求体）：**
```json
{"lyrebirdMockResp": "<bizRes 的内容>"}
```

**请求头：**
```json
{"lyrebird": "mock", "mockRespV2": 1}
```

添加 `mockRespV2: 1` 可跳过后端模型校验，直接返回全部响应数据（需后端 DUO SDK ≥ 3.0.23-SNAPSHOT）。

**重要：** 必须清空"响应头"和"响应内容"字段，否则 Mock 不生效。

> 如果后端 DUO SDK 未升级到最新版，`lyrebirdMockResp` 需要设置为 JSON string 格式（即对对象再做一次 `JSON.stringify`）。

### 5.3 使用 Lyrebird / Charles 等抓包工具

1. 拦截含 `duo_csdk_v={string}` 参数的请求（此标识表明是 DUO 端到端接口）
2. 修改 request body，增加字段 `lyrebirdMockResp`，值为 mock 数据
3. 在 request header 添加 `lyrebird: mock` 和 `mockRespV2: 1`

## 6. 测试规范

自测必须覆盖 **Web 和 MRN** 两种产物，并覆盖所有投放场景（不同入口、不同参数组合）。建议在需求上线前针对固有核心功能进行回归测试。

## 7. 发布规范

Web 产物部署必须使用 **「DUO Web部署Talos2.0（分支版2.0）」** 工作流，不得手动部署。建议使用五端齐发流水线统一发布 Web、MRN、小程序等多端产物。

| 模板 | 用途 |
|------|------|
| DUO 开发模板(分支版2.0) | 日常需求开发 |
| DUO Bugfix 模板(分支版2.0) | Bug 修复 |
| DUO Web部署Talos2.0（分支版2.0） | Web 产物部署 |

---

## 附：常见问题

**Q: PAYLOAD 和 PREV_DATA 分别在什么场景用？**
PAYLOAD 仅用于需要后端校验的 update 场景，携带前端临时信息（如用户点击的商品 ID）发给后端校验。PREV_DATA 用于出参取值，引用上一节点（通常是业务接口）返回的稳定数据。preview 和 submit 场景均应使用 PREV_DATA，不应依赖 PAYLOAD。

**Q: 为什么禁止直接 push 到 release/master？**
绕过 PR 流程会破坏代码审查机制，未经验证的代码可能破坏构建稳定性，且无法追溯变更意图。

**Q: 为什么 PR 需要 2 人 approve？**
降低单一 Reviewer 主观盲区，提升发现缺陷概率，同时实现知识共享和责任共担。
