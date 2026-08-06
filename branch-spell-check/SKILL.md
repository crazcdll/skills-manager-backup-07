---
name: branch-spell-check
description: 检查当前分支改动中的英文拼写与大小写问题，可按需自动修复。适用于 PR 前自查、验证或修复拼写，以及用户提到「拼写」「拼错」「typo」「spell check」「大小写」「直接修改」「修复」等场景。

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V1"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "1744"
---

# 分支拼写检查

仅针对**当前分支的改动**（相对基准分支的 diff）检查英文拼写与大小写。默认只生成报告；仅在用户明确要求时才**自动修复**（如：直接修改 / 修复 / apply fixes）。

---

## 使用说明

### 检查 vs 检查并修复

| 模式 | 说明 | 触发方式 |
|------|------|----------|
| **仅检查** | 只扫描当前分支改动，输出拼写/大小写问题报告，不修改文件 | 默认。用户说「检查拼写」「spell check」「看看有没有拼错」等 |
| **检查并修复** | 先出报告，再按建议自动修改代码（标识符、文件名、注释/字符串等） | 用户明确说「修复」「直接改」「apply fixes」「把拼写错误修掉」等 |

### 脚本参数

在仓库根目录执行（可从任意子目录调用，脚本会切到根目录）：

```bash
.cursor/skills/branch-spell-check/scripts/check-diff-spell.sh [base_branch]
```

| 参数 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `base_branch` | 否 | 对比的基准分支（与当前分支 diff 的范围） | `origin/main`，若无则 `origin/master` |

脚本目前只支持上述一个可选参数；「只检查拼写」「只检查某类文件」等由 Agent 在报告或执行层面处理（例如只输出拼写表、或手动用 `git diff --name-only base...HEAD \| xargs npx cspell` 并指定文件类型）。

### 使用示例

**1. 仅检查（默认基准 main）**

- 用户：「帮我检查一下当前分支的拼写」
- 用户：「spell check 一下」
- 执行：`check-diff-spell.sh` 或 `check-diff-spell.sh origin/main`
- 结果：输出报告，不改文件

**2. 指定基准分支再检查**

- 用户：「对比 develop 分支检查拼写」
- 执行：`check-diff-spell.sh origin/develop`
- 结果：只检查 `origin/develop...HEAD` 的改动，出报告

**3. 检查并修复**

- 用户：「检查拼写并直接修复」
- 用户：「把报告里的拼写错误都修掉」
- 流程：先跑脚本 + 人工/规则做大小写审查 → 出报告 → 再按报告逐条改代码（标识符全量替换、文件名重命名+引用更新、注释/字符串单行修改）

**4. 只关心拼写、不关心大小写**

- 技能仍会跑完整流程；若用户说「只检查拼写」，报告里可只列出「拼写」部分，省略或简化「大小写」部分。

**5. 上线前 / PR 前快速扫一遍**

- 用户：「PR 前帮我看看有没有拼写和大小写问题」
- 执行：默认基准分支检查 → 出完整报告（拼写 + 大小写），不自动修复

## 执行流程

1. **获取 diff**
   - 优先使用：`git diff origin/main...HEAD` 或 `git diff main...HEAD`（若默认分支为 `master` 则相应调整）。
   - 可选：需要包含已暂存与未暂存改动时，用 `git diff origin/main...HEAD` 与 `git diff --staged` 合并。
   - 若用户指定了基准分支，则使用该分支（如 `git diff origin/develop...HEAD`）。

2. **拼写检查**
   - 推荐执行内置脚本：
     ```bash
     .cursor/skills/branch-spell-check/scripts/check-diff-spell.sh [base_branch]
     ```
     `base_branch` 默认为 `origin/main`（不存在时回退到 `origin/master`）。
   - 或手动对变更文件执行 cspell：
     ```bash
     git diff --name-only origin/main...HEAD | grep -E '\.(tsx?|jsx?|md|json|yml|yaml)$' | xargs npx cspell --no-progress
     ```
   - 脚本通过 `npx cspell` 运行，无需项目依赖。仅检查**有改动的文件**。

3. **大小写审查**
   - 对同一份 diff 检查：
     - **专有名词/产品术语**：如 `React`、`TypeScript`、`MRN`、`API`、`ID`、`URL`、`iOS`、`Android`。
     - **项目约定**：组件名 PascalCase、常量 UPPER_SNAKE、hooks `useXxx`。
     - **注释与面向用户的文案**：按需使用句首大写或标题式大写；非缩写不在句中全大写。
   - 将不一致或错误的大小写写入报告，并注明文件、行号及建议写法。

4. **报告**
   - **拼写**：列出文件、行号、错误词、建议更正（来自 cspell 或人工）。
   - **大小写**：列出文件、行号、当前内容、建议写法。
   - 排除：压缩/打包文件、lock 文件、哈希值、明显非英文内容。过滤误报（代码符号、环境变量、URL 等）。

5. **应用修复（仅在用户要求修复时）**
   - 当用户提出 直接修改 / 修复 等要求时，在出报告后按建议编辑文件并修正。
   - **标识符重命名**（如 `IS_HORMANY` → `IS_HARMONY`）：在仓库内对该标识符做全文搜索替换，更新定义及所有引用。
   - **名称中的单词修正**（如组件/文件名中 `Corss` → `Cross`）：先重命名文件，再更新组件名及所有 import/引用（路由、index、父组件等）。
   - **行内拼写错误**（注释、字符串）：在对应行用建议词替换。
   - 只改报告中的问题，不碰无关代码。每次编辑尽量对应一个逻辑修改（如一次标识符重命名，或一次文件重命名及其引用）。

## 报告格式

按以下模板输出：

```markdown
# 分支拼写检查报告

**基准：** origin/main...HEAD（或用户指定的基准分支）

## 拼写
| 文件 | 行号 | 错误 | 建议 |
|------|------|------|------|
| path/to/file.ts | 42 | occured | occurred |

（或无拼写问题。）

## 大小写
| 文件 | 行号 | 当前 | 建议 |
|------|------|------|------|
| path/to/file.tsx | 10 | "react" | "React" |

（或无大小写问题。）
```

## 脚本说明

- **scripts/check-diff-spell.sh**：从 `git diff base...HEAD` 获取变更文件，对其执行 `npx cspell`。需在仓库根目录执行；第一个参数为可选基准分支（默认 `origin/main`，不存在时用 `origin/master`）。

## 范围

- **在范围内**：注释、字符串字面量、JSX 文本、diff 中的变量/函数名、Markdown、配置项键名。
- **不在范围内**：二进制文件、生成文件、第三方路径、提交哈希、以及已知缩写/本地术语（项目专有词可加入 cspell 配置或在技能中说明）。
