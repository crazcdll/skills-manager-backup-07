---
scope: mt-coding-standards
authority: execution-contract
owner: unknown
---

# AGENTS.md

## npm 版本管理

- `@nibfe/mt-code-standards` 的 npm 发布版本由 Talos 流水线自动递增和回写，Talos 是 npm 版本号的管理方。
- 日常开发、修复和 npm 发布准备时，不在本地手动升版，不执行 `npm version`，不为了发包修改 `package.json` 或 `package-lock.json` 中包自身的版本号。
- 合并或同步 Talos 的自动升版提交时保留其版本结果，不用本地旧版本覆盖或回退；依赖版本调整不属于此限制。
- npm 包与 Friday Skill 分别发布。不得为了匹配 Talos 生成的 npm 版本而修改 `SKILL.md` 的版本；Skill 版本仅在明确要求更新 Skill 版本时单独处理。
- 校验脚本或旧文档若仍要求 npm 与 Skill 版本相等，应报告该冲突，不通过手工改版本号绕过检查。
- 发布验收以 Talos 发布回执和公司 npm 源中的实际版本为准，不将某次发布版本固化为长期规则；提交源码不代表已发布。
