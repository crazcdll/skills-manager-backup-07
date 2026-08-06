---
name: double check与重复依赖检测
description: 检查 dependencies.json 与 ohDependencies.json 的改动是否一致、完整。
---

## 🎯 执行内容

`dependencies.json`、`ohDependencies.json` 依赖处理流程

步骤1：遍历并校验现有依赖

遍历两份清单中的全部条目（按数组逐项或按 `name` 聚合）。

对每个依赖包，在鸿蒙依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableOhPackage-dep.md}}和通用依赖表${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableCommonPackage-dep.md}}中查询（要求依赖名称完全匹配）
需要保障：
1. `dependencies.json` 中包含的所有包为三端兼容版本${{inputFile:.temp/trade-duo-standard-same-npm-dependencies/file/tableCommonPackage-dep.md}}（**与 k-hub 知识库及步骤 1 对照表中的标准版本一致**）
2. `ohDependencies.json` 中所有包均为仅鸿蒙侧需保留的标准化版本（**与 k-hub 知识库及步骤 1 规则一致**）。


步骤2：补充缺失的兼容依赖
1. 遍历鸿蒙依赖表
2. 找出所有第四列显示兼容安卓/iOS 的依赖
3. 检查这些依赖是否已在 `dependencies.json` 中
4. 如果未使用 → 添加到 `dependencies.json`

步骤3：处理依赖名称修改
1. 检查 `dependencies.json` 中是否有被修改的依赖名称
2. 如有修改 → 恢复为原始名称，并修正版本号为符合要求的版本


步骤4：处理重复依赖和不一致依赖
1. 检查 `dependencies.json` 中是否出现重复 `name`（若存在多条记录），保留符合规则的一条并合并版本信息
2. 检查两份清单之间是否存在同名依赖版本不一致，如有，统一到最新合理版本

步骤5：报告更新
如果有改动，则更新到${{outputFile:.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md}}

---
*完成此步骤后，请继续执行下一步*
