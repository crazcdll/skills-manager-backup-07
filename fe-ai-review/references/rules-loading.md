# 规则加载策略

规则分两类，加载方式不同：

- **审查规则**（`general-rules.md` / `trade-rules.md` / `stack/*.md`）：纯审查知识，不依赖执行流程，走本节的远程同步机制
- **附加能力模块**（`dep-upgrade-rules.md` / `msi-api-review-rules.md`）：本身是一套 subagent 执行流程说明，与 Step 3 编排逻辑强耦合，固定读本 skill 自带的 `references/rules/base/`，**不参与**远程同步

Step 2「识别技术栈并加载规则」加载审查规则前，先执行完成本节的同步动作，确定这次用的是远程最新规则还是本地兜底规则。

## 同步动作（仅审查规则）

删除 `<skill_dir>/.rules-cache/`（如存在），重新执行：

```bash
git clone --depth 1 -b feature/rules-init ssh://git@git.sankuai.com/mcp/ai-cr.git <skill_dir>/.rules-cache
```

> ⚠️ 临时措施：规则内容当前维护在 `ai-cr` 仓库的 `feature/rules-init` 分支（尚未合并到默认分支 `master`）。

- **成功** → 本次审查规则读取根目录是 `<skill_dir>/.rules-cache/rules/frontend/`
- **失败**（网络、权限、仓库不可达等任何原因）→ 本次审查规则读取根目录回退为本 skill 自带的 `references/rules/`，并在会话中提示一句：`ℹ️ 规则仓库拉取失败，本次使用本地兜底规则（可能非最新版本）`

两个来源的目录结构一一对应，Step 2 后续列出的审查规则路径按「读取根目录」替换前缀即可：

| 规则用途 | 远程路径（读取根目录为 `.rules-cache/rules/frontend/`） | 本地兜底路径（读取根目录为 `references/rules/`） |
|---|---|---|
| 通用规则 | `base/general-rules.md` | `base/general-rules.md` |
| 交易规则 | `base/trade-rules.md` | `base/trade-rules.md` |
| MRN | `stack/mrn-rules.md` | `stack/mrn-rules.md` |
| Max | `stack/max-rules.md` | `stack/max-rules.md` |
| 小程序 | `stack/miniprogram-rules.md` | `stack/miniprogram-rules.md` |
| DUO | `stack/duo-rules.md` | `stack/duo-rules.md` |

## 附加能力模块（固定本地路径，不走同步）

- 依赖升级扫描：`references/rules/base/dep-upgrade-rules.md`
- MSI API 契约核对：`references/rules/base/msi-api-review-rules.md`

## 备注：已知限制（当前阶段刻意不做）

- 不校验远程规则与本 skill 版本的兼容性，规则文件结构变化可能导致本 skill 引用失效
- 本地兜底副本是 skill 发布时刻的快照，不随远程规则仓库自动保鲜，可能与远程内容存在差异
- 每次会话全量重新 clone，不做增量 pull

这些是当前明确接受的短期风险，不在本次改动范围内。
