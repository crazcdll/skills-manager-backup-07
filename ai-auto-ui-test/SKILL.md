---
name: ai-auto-ui-test
version: 5.0.0
description: 自动化 UI 测试编排入口。识别用户意图，委托下游 Skill 完成 Flow 生成或测试执行。触发词：UI 自动化测试、端到端测试、回归测试、测试用例生成、Flow 用例、测试报告、ai-app-flow、ai-ui-autotest-engine。场景：需要生成测试用例时委托 ai-app-flow，需要执行测试时委托 ai-ui-autotest-engine。

metadata:
  skillhub.creator: "huangshuiqing"
  skillhub.updater: "wangshicheng05"
  skillhub.version: "V22"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "112900"
  skillhub.high_sensitive: "false"
---

## 前置

```bash
# 1. 全自动环境准备（自身更新 + 依赖 Skill 安装 + 运行时环境配置）
python3 scripts/env_setup.py

# 2. 使用上报
python3 scripts/report_usage.py --stage start --mis "<mis_id>" --input "<输入摘要>" --desc "<意图>"
```

# 编排入口

本 Skill 是一个编排壳子，不做具体业务逻辑。根据用户意图委托给下游 Skill：

| 场景 | 委托 Skill | 说明 |
|------|-----------|------|
| 生成 Flow 用例 | `ai-app-flow` | 生成可执行的 Flow 测试文件 |
| 执行测试 | `ai-ui-autotest-engine` | 端到端执行，产出报告 |

## 执行规则

1. **全局依赖就绪**：进入执行前先运行 `python3 scripts/env_setup.py`，自动完成：
   - 当前 Skill 自身更新
   - 安装缺失的依赖 Skill（`ai-app-flow`、`ai-ui-autotest-engine`）
   - 触发下游 Skill 的运行时环境自动配置（Python 包、Node、CLI 工具等）
   - 输出环境就绪报告
2. 委托前先读取并严格遵循下游 Skill 的 SKILL.md。
3. Flow 文件已存在时不得重新生成，除非用户明确要求更新。
4. 不重写下游 Skill 的流程，下游 Skill 的输出即最终结果。
5. **委托执行方式**：委托 ai-app-flow 后，**由当前 AI 在本地直接执行** `ec-toolkit`、`citadel` 等 CLI 命令。禁止创建子 Agent 去执行。