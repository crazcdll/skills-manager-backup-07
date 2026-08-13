# 场景 3：协议诊断排错

指导 AI 从现象定位 DUO 页面协议相关问题根因并给修复建议。适用：页面白屏、渲染异常、表达式不生效、update 无响应、提交失败、物料不渲染。

## 一、先定位问题层级

```
跳链参数问题 → 检查参数是否 'null'/'undefined'/'NaN'，是否缺参数
页面白屏     → 检查 preview 接口，端到端协议结构是否完整
update 异常  → 检查 update 接口入参、updateBy 是否配置、数据是否正确传递
提交失败     → 检查 submit 接口、回调逻辑
表达式不生效 → 检查 Groovy 语法、变量、类型、是否放错节点
物料不渲染   → 检查物料引用、componentsMap、dependencies
```

## 二、快速排查表

| 现象 | 优先原因 | 排查方向 |
|------|---------|---------|
| 页面白屏 | preview 异常 / 协议结构错 / 物料加载失败 | 抓 preview + Raptor JSError |
| 物料不渲染 | 物料未引用 componentsMap/dependencies / 节点类型 | 查引用 + 描述文件 |
| 表达式不生效 | 语法错 / 变量编造 / 类型不匹配 / 放错节点 | 配置平台校验 + duo-debug-panel |
| update 无变化 | updateBy 缺失 / 事件名不匹配 / 数据未传 | 查 updateBy + on 事件 |
| 提交无响应 | submit 回调未配 / 事件未触发 | 查 logics/submit.* |
| 小程序端异常 | 安全基线 header / mrnChannel / 生命周期差异 | 区分端排查 |
| 鸿蒙端异常 | 鸿蒙依赖漂移 / oh-package | 查 ohDependencies |

## 三、协议专项排查

### 3.1 表达式不生效（最常见）

排查顺序：
1. 在 props 的 `{{ }}` 内？
2. 变量来自真实全局变量（不是编造）？
3. 类型匹配（bool/number/string/array 声明 vs 值类型）？
4. Groovy 2.4.17（没用 includes/map/filter）？
5. **是否放错了节点**（渲染表达式不能放 CommonParams/Static/Logic 等静态/逻辑节点）？
6. 用 duo-debug-panel 看求值结果

### 3.2 update 无变化

1. 该字段/节点配了 `updateBy` 吗？
2. `updateBy 'xxx'` 与触发的 `on('xxx')` 事件名一致吗？
3. updateBy 挂在正确的目标节点吗？
4. update 入参 `PAYLOAD` 是否携带正确数据？
5. update 后返回的新协议视图树是否更新？

### 3.3 页面白屏

1. preview 返回 200 且 code=0
2. struct 视图树完整
3. 涉及的物料都能加载（componentsMap/dependencies）
4. 有无表达式 preview 阶段抛异常（空值）

## 四、改协议排错注意

1. **先复现定位，再改**：确认是协议问题才改
2. **最小修复**：只改出问题的字段/节点
3. **验证**：duo-debug-panel / 真机预览确认且无副作用
4. **区分端**：MRN/H5/鸿蒙/小程序分别排查

## 五、结束条件

- [ ] 定位到根因层级
- [ ] 确认是否协议引起
- [ ] 最小修复方案
- [ ] 验证方式与预期
