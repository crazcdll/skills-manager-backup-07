# 协议规则文件索引（must-comply）

> 文件命名规则：`R{N}-协议文件名.md` 对应 6 步执行顺序，`R-common-*.md` 为跨文件通用规则。
> ⚠️ 本文件为纯索引，各规则文件的详细内容由 SKILL.md 资源索引表统一引用，此处仅做目录概览（不设超链接避免嵌套引用）。

## 按执行顺序（R1-R6）

| 文件 | 对应步骤 | 对应协议文件 | 说明 |
|------|---------|------------|------|
| R1-pageBuildConfig.md | Step 3.1 | pageBuildConfig.json | 页面配置规则：baseUrl、pageUrl、pageQuery、commonParams |
| R2-dataSourceMap.md | Step 3.2 | dataSourceMap.groovy | 数据源配置规则：reqProps、currentData、bizRespStatus、submitBizRespStatus |
| R3-constData.md | Step 3.3 | constData.groovy | 页面常量规则：constant 定义、CONST 引用限制 |
| R4-struct.md | Step 3.4 | struct.groovy | 组件树结构规则：node/props/style/slot/xIf/propConfig/events |
| R5-logics.md | Step 3.5 | logics.groovy | 生命周期规则：preview/update/submit 回调、事件链路 |
| R6-dependencies.md | Step 3.6 | dependencies.json + componentsMap.json | 依赖声明与物料注册表：materialId 获取、URL 路径规则 |

## 跨文件通用规则（R-common）

| 文件 | 适用步骤 | 说明 |
|------|---------|------|
| R-common-expression.md | Step 3.2/3.3/3.4/3.5 | Groovy 表达式规则：变量类型、安全访问、兜底运算 |
| R-common-events.md | Step 3.4/3.5 | 事件配置规则：组件间通信、参数透传、双向绑定 |
