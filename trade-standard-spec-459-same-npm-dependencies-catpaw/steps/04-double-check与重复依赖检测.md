---
name: double check 与重复依赖检测
description: 校验 package.json 与 oh-package.json 的改动完整性，检测重复依赖，验证 metro.config.js 配置
---

## 🎯 执行内容

对步骤 2 和步骤 3 的改动进行全面校验，确保依赖迁移和版本更新的正确性，同时补充遗漏的三端兼容依赖，并处理 `metro.config.js` 配置。

<sop>
## 检查工作流程

### 步骤 1: 遍历校验现有依赖

遍历 `package.json` 和 `oh-package.json` 中的 `dependencies`、`devDependencies`、`resolutions` 三个字段，对每个依赖包在对照表中进行完全匹配查询。

**校验目标：**
1. `package.json` 中包含的所有包使用三端兼容版本（`.spec/file/tabelCommonPackage-dep.md`）。
2. `oh-package.json` 中所有包均为「不支持 Android/iOS」的版本。

**发现违规时：**
- `package.json` 中出现应当已删除但仍残留的非三端兼容依赖 → 按步骤 2/3 规则补正。
- `oh-package.json` 中出现支持 Android/iOS 的依赖（漏迁移）→ 补充迁出操作。

### 步骤 2: 补充缺失的三端兼容依赖

遍历鸿蒙依赖对照表（`.spec/file/tabelOhPackage-dep.md`）中「是否支持 Android/iOS」列为「是✅」的所有依赖：
1. 检查这些依赖是否已在 `package.json` 中使用。
2. 若**未使用**且该包是项目实际需要的（存在于 `oh-package.json` 的原始版本中）→ 添加到 `package.json` 的对应字段，使用知识库标准版本。
3. 若该包并非项目依赖（知识库中有、但项目从未引用过）→ 跳过，不强制新增。

> 💡 只补充在步骤 2 中「应被迁出但因某种原因未处理」的依赖，不凭空新增项目未用到的包。

### 步骤 3: 处理依赖名称修改（防止意外重命名）

检查 `package.json` 中是否存在被意外修改名称的依赖：
1. 若发现依赖名称与原始不符 → 恢复为原始名称，并确保版本号为符合要求的版本。
2. 记录到 changelist。

### 步骤 4: 处理重复依赖和不一致依赖

1. **重复依赖检测**：检查 `package.json` 同一字段下是否有重复依赖名称（如 `resolutions` 下出现两个 `@mrn/mrn-owl`）。
   - 若有重复 → 保留版本较高的，删除版本较低的，changelist 注明。
2. **版本不一致检测**：检查 `dependencies`、`devDependencies`、`resolutions` 中是否存在相同包名但版本不一致的情况。
   - 若有 → 统一为最新版本（semver 最高），changelist 注明。

### 步骤 5: metro.config.js 解析 Max 组件/基础库

检查工程中是否存在 `metro.config.js`，且其中是否已配置 `resolverMainFields`：

**若已有 `resolverMainFields` 配置** → 确认包含 `'main:mrn'`，若没有则补充。

**若无 `metro.config.js` 或无 `resolverMainFields` 配置** → 帮用户补充配置：

```javascript
module.exports = function (metroConf) {
    // ... 其他配置
    metroConf.resolver.resolverMainFields = ['main:mrn', ...metroConf.resolver.resolverMainFields]; // 解析 Max 组件/基础库
    // ... 其他配置
    return metroConf;
};
```

注意：若 `metro.config.js` 使用的是不同的导出方式（如 `module.exports = { ... }` 对象形式），需适配其实际结构添加该配置，避免破坏原有配置。

### 步骤 6: 报告更新

如有改动，将本步骤所有补正内容追加到 `.spec/result/changelist.md`。

changelist 格式示例：
```markdown
## 步骤 4：double check 与重复依赖检测

### 补正操作
- `@max/meituan-uni-xxx`：在 oh-package.json 中仍存在（漏迁移），已补充迁出至 package.json。

### 重复依赖处理
- `@mrn/mrn-owl`：resolutions 中存在重复，保留 1.2.3，删除 1.1.0。

### 版本不一致处理
- `react`：dependencies 为 18.2.0，resolutions 为 17.0.2，统一为 18.2.0。

### metro.config.js
- 已添加 resolverMainFields 配置（解析 Max 组件/基础库）。
```
</sop>

<boundary>
## 工作边界

**工作范围：**
- 对步骤 2/3 的改动做完整性校验。
- 补充遗漏的三端兼容依赖迁出（仅限项目已有的依赖，不新增项目未使用的包）。
- 处理字段内重复依赖和跨字段版本不一致问题。
- 检查并补充 `metro.config.js` 的 `resolverMainFields` 配置。

**不应该做的事情：**
- 不引入知识库之外的版本。
- 不修改依赖包名称。
- 不新增项目从未使用过的依赖。
</boundary>

---
*完成此步骤后，继续执行第 5 步（yarn.lock 重复依赖过滤）*
