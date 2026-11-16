# 场景 1：日常迭代改协议

指导 AI 在**不破坏现有页面**的前提下安全地修改 DUO 页面协议。适用于"加模块 / 加字段 / 改展示条件 / 改交互"等增量需求。

## 一、修改目标（协议源文件）

修改的是仓库 **`protocol/`** 目录下的 `.groovy` 与 `.json` **拆分文件**（都要理解怎么改）：

```
protocol/
├── struct.groovy          # 视图树 ★ 最常改
├── logics.groovy          # 逻辑（生命周期、updateBy、事件）
├── dataSourceMap.groovy   # 数据源定义
├── constData.groovy       # 页面常量
├── pageBuildConfig.json   # 编译静态配置（路由、pageQuery、公共参数）
├── dependencies.json      # 依赖物料
└── componentsMap.json     # 物料映射（key=物料ID）
```

参考仓库：到餐 `nibfe/duo-food-order-submit`（pageId=12413，protocolId=0401）、酒店 `nibfe/duo-hotel-order-submit`（pageId=12450，protocolId=0238）。

## 二、流程

### Step 1：读取并理解现状（🔴 阻塞）

1. 读取 `protocol/struct.groovy` / `logics.groovy` / `dataSourceMap.groovy`
2. 提取目标节点（用 grep 找 `node('Name','编号')`）
3. 理解目标节点的 props、updateBy、on 事件、xIf 条件
4. 理解它绑定哪个数据源（`DATA_SOURCE.data.xxx`）

> **未读懂现状禁止动手。**

### Step 2：定位改动点 + 影响面（🔴 阻塞）

1. 定位目标节点（nodeName + 编号）
2. 映射到具体文件（struct / logics / dataSourceMap）
3. 检查依赖：
   - 表达式引用哪些全局变量（CONST/DATA_SOURCE/NODE 等）
   - 是否有其它字段 `updateBy` 依赖正在改的字段
   - 新增节点的物料是否在 componentsMap/dependencies 有引用
4. 输出"改动清单 + 影响面"

### Step 3：执行改动并验证（🟡 半阻塞）

1. 增量修改（类型化声明 + Groovy 表达式）
2. 自检：
   - Groovy 2.4.17 语法（不用 includes/map/filter）
   - 字段用 `bool/number/string/object/array`
   - 变量来自真实全局变量，不编造
   - 物料 ID 从物料平台/现有协议查询（不编造、不套用其它物料）
   - updateBy/事件链路未破坏
   - 新增物料在 componentsMap/dependencies
3. 说明验证（duo dev 协议同步 / 配置平台预览）

## 三、典型改动

### 3.1 加一个字段（不改视图结构）

在现有节点（如酒店 BottomBar）props 里新增字段：

```groovy
node('BottomBar', '798') {
  props {
    // 保留原有字段 …
    number('totalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
    // 新增字段，不覆盖原有
    number('newDiscount') {{ DATA_SOURCE?.data?.priceVO?.xxx ?: 0 }}
  }
}
```

### 3.2 加一个视图节点

在目标容器下新增节点，物料需已有引用：

```groovy
node('LayoutTopBottom', '7') {
  // …
  node('NewTipNode', '1xxx') {   // 物料ID 从物料平台查询对应 tip 物料的真实 ID（示例勿直接用 1xxx）
    label '新提示'
    xIf {{ !CONST.isXXX }}
    props {
      string('content') {{ '提示文案' }}
    }
  }
}
```
> 若 `NewTipNode` 的物料（如 leez-tip）未在 componentsMap，先补引用。

### 3.3 改展示条件

```groovy
// 改 xIf 条件
node('Product', '1056') {
  xIf {{ !CONST.baseInfo.isXXX }}   // 用真实变量，先确认存在
}
```

## 四、常见坑

| 坑 | 避免 |
|----|------|
| 编造全局变量名 | 用 CONST/DATA_SOURCE/NODE/PAYLOAD/PREV_DATA/COMMON_PARAMS/PAGE_QUERY/PROPS，先确认 |
| JS 语法 | 用 Groovy 2.4.17（contains 非 includes，def 非 const） |
| 覆盖已有字段 | 增量新增，不覆盖 |
| 物料 ID 用错/编造 | 从物料平台/现有协议查询真实物料 ID，不套用其它物料 |
| 物料未引用 | 新增节点物料在 componentsMap/dependencies |
| 破坏 updateBy | 改动前梳理依赖该字段的 updateBy |
| 误改静态节点 | CommonParams/Static/Lifecycle 只放逻辑 |

## 五、结束条件

- [ ] 需求落实到协议
- [ ] Groovy 合法（2.4.17）
- [ ] 变量/编号非编造
- [ ] 物料引用完整
- [ ] updateBy/事件链路未破坏
- [ ] 验证方式已说明
