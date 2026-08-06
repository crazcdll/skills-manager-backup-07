---
name: double check与重复依赖检测
description: 检查一遍package.json的改动
---

## 🎯 执行内容

package.json、oh-pageckage.json依赖处理流程

步骤1：遍历并校验现有依赖

遍历`package.json`,`oh-pageckage.json`中的三个字段：dependencies、devDependencies、resolutions

对每个依赖包，在鸿蒙依赖表${{inputFile:.spec/file/tabelOhPackage-dep.md}}和通用依赖表${{inputFile:.spec/file/tabelCommonPackage-dep.md}}中查询（要求依赖名称完全匹配）
需要保障：
1. `package.json`中包含的所有包为三端兼容版本${{inputFile:.spec/file/tabelCommonPackage-dep.md}}
2. `oh-pageckage.json`中所有包均为不支持Android/IOS版本。


步骤2：补充缺失的兼容依赖
1. 遍历鸿蒙依赖表
2. 找出所有第四列显示兼容安卓/ios的依赖
3. 检查这些依赖是否已在package.json中使用
4. 如果未使用 → 添加到package.json中


步骤3：处理依赖名称修改
1. 检查package.json中是否有被修改的依赖名称
2. 如有修改 → 恢复为原始名称，并修正版本号为符合要求的版本


步骤4：处理重复依赖和不一致依赖
1. 检查package.json中相同字段下是否有重复依赖（例如，resolutions字段下有两个@mrn/mrn-owl）如果有，则删除掉一个版本较低的
2. 检查dependencies、devDependencies、resolutions中是否有不一致的依赖，如果有，统一到最新版本

步骤5：metro.config.js解析Max组件/基础库
1. 检查用户工程中是否有metro.config.js，且其中配置了resolverMainFields，如果没有配置，帮用户配置上
```
module.exports = function (metroConf) {
    ··· // 其他配置
    metroConf.resolver.resolverMainFields = ['main:mrn', ...metroConf.resolver.resolverMainFields]; //解析Max组件/基础库
    ··· // 其他配置
    return metroConf;
};
```

步骤5：报告更新
如果有改动，则更新到${{outputFile:.spec/result/changelist.md}}

---
*完成此步骤后，请继续执行下一步*
