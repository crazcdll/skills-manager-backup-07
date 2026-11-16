# 场景 2：从零生成 / 搭建协议

指导 AI 从需求出发构建 DUO 页面协议。适用：生成协议 / 从零搭建页面 / 重组视图树 + 数据源 + 逻辑。

## 一、目标

构建一份结构完整、逻辑自洽、可被 duo-builder / duo-engine 渲染的 DUO 页面协议。

## 二、修改目标

生成的协议写入仓库 `protocol/` 目录下的 `.groovy` 与 `.json` **拆分文件**：
- `struct.groovy`：视图树
- `logics.groovy`：逻辑
- `dataSourceMap.groovy`：数据源
- `constData.groovy`：页面常量
- `pageBuildConfig.json`：编译配置
- `dependencies.json`：依赖物料
- `componentsMap.json`：物料映射

并同步 `duo-builder/duo.config.js`（pageId）、`duo-version.json`（protocolId/version）。

> 参考已有页面骨架：到餐 `nibfe/duo-food-order-submit`（pageId=12413，protocolId=0401）、酒店 `nibfe/duo-hotel-order-submit`（pageId=12450，protocolId=0238）。**模仿它们的真实 node 命名与 props 写法**。

## 三、流程

### Step 1：确认页面语义（🔴 阻塞）
明确：提单页 / 详情页 / 卡片 / 列表；核心模块；数据来源。输入来源 spec/plan 或用户描述。

### Step 2：规划结构树（🔴 阻塞）
从骨架由外向内：
1. 根布局（`LayoutTopBottom` 上中下 或 到餐 `TopBottomSlide`）
2. 静态/逻辑节点（`CommonParams` 公共参数、`LifecycleLogic` 生命周期）
3. 内容卡片（商品、价格、优惠）
4. 底部操作（`BottomBar` 提交）

参考到餐/酒店真实节点命名（Product、PriceCard、BottomBar 等）。

### Step 3：选物料（🔴 阻塞）
- 物料 npm 名来自 package.json（如 `@max/leez-card`、`@max/leez-button`、`@meishi/common-layout-top-bottom`）
- **materialId（物料平台注册的物料 ID）/ 节点 resource 从现有协议、componentsMap、物料平台查询，禁止编造**

### Step 4：构建 struct 视图树
```groovy
node('LayoutTopBottom', '7') {
  node('CommonParams', '757') {
    props {
      object('lxCommonParams') {{ [ cid: CONST.cid ] }}
    }
  }
  node('Product', '1056') {
    props {
      number('price') {{ DATA_SOURCE?.data?.priceVO?.price }}
    }
  }
  node('BottomBar', '798') {
    props {
      number('totalPay') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
    }
  }
}
```

### Step 5：绑定数据源
- `dataSourceMap.groovy` 定义 `dataSource { ... }`
- struct 里用表达式绑定 `DATA_SOURCE.data.xxx`

### Step 6：写逻辑
- `logics.groovy`：`node('MeishiCommonDuoLifecycle1','13')` 生命周期 + `on('...')` 事件
- 交互用 `updateBy` / `callMethod`
- 提交用 `submit.*` 事件

### Step 7：校验（🟡 半阻塞）
1. Groovy 2.4.17
2. materialId / 编号真实且不重复
3. componentsMap / dependencies 覆盖所用物料
4. updateBy / 事件引用目标存在
5. protocolId / version 在 duo-version.json 一致

## 四、生成骨架示例（真实语法）

到餐提单页骨架：
```groovy
node('TopBottomSlide', '136') {
  node('MeishiCommonDuoParams', '757') { ... }   // 公共参数
  node('NavBar', '1523') { ... }                 // 导航
  node('Product', '1056') { ... }                // 商品卡
  node('MeishiGroupSubmitCoupons', '1650') { ... }  // 团购券
  node('SubmitRisk', '192') { ... }              // 风险
  node('BottomBar', '402') { ... }               // 底部提单栏
}
```

## 五、常见坑

| 坑 | 避免 |
|----|------|
| 编造 materialId / 物料 ID | 从物料平台/componentsMap/现有协议查询 |
| 结构层级错 | 先规划容器/子节点 |
| 数据源未定义就引用 | 先 dataSourceMap 后 struct |
| 变量编造 | 用真实全局变量 |
| 漏 componentsMap/dependencies | 校验引用 |
| 编号撞车 | 物料 ID 从物料平台查询真实值，不套用其它物料 |

## 六、结束条件

- [ ] 视图树结构完整、层级清晰
- [ ] 节点物料 ID / materialId 真实（从物料平台查询）
- [ ] 数据源绑定正确
- [ ] 逻辑完整（生命周期 + updateBy + 提交）
- [ ] componentsMap/dependencies 覆盖
- [ ] 表达式 2.4.17 兼容
