# workflow-context.json 权威 Schema

> **⚠️ 本文件是 `workflow-context.json` 的唯一权威定义。**
> **所有读写 `workflow-context.json` 的阶段和 Skill，必须严格遵循本 schema。**
> **字段命名、类型、枚举值以本文件为准，禁止自行扩展未定义字段。**

---

## 文件路径

```
{project_root}/.duo/{demand_description}/workflow-context.json
```

- `project_root`：Git 仓库根目录（`pwd` 确认）
- `demand_description`：需求英文名，由 Stage 1 从 PRD/ONES/学城文档中提炼，一旦确定全程不变

---

## 完整 Schema

```json
{
  "meta": {
    "skill": "fe-rd-workflow",
    "version": "V2",
    "mode": "<'single_agent' | 'multi_agent': 执行模式，由用户在流程启动时通过 AskQuestion 确认，默认 single_agent>",
    "started_at": "<ISO8601>",
    "project_root": "<string: 仓库根目录绝对路径>"
  },

  "input": {
    "mis": "<string: 用户 MIS 号，必填>",
    "prd_link": "<string: PRD 文档链接，必填>",
    "km_parent_id": "<string: 学城需求记录文档 contentId，必填>",
    "api_link": "<string | null: 接口文档链接，可选>",
    "ux_link": "<string | null: Ingee 视觉稿链接，可选>",
    "user_description": "<string: 用户原始需求描述>",
    "fedo_info": {
      "ones_link": "<string | null>",
      "iteration_name": "<string | null>",
      "task_name": "<string | null>",
      "project_name": "<string | null>",
      "tech_stack": "<string | null>",
      "assignee": "<string | null>",
      "qa": "<string | null>",
      "pm": "<string | null>"
    }
  },

  "runtime": {
    "complexity": "<'L' | 'M' | 'H': 由 Stage 3 需求分析与技术设计评估后写入>",
    "doc_write_strategy": "<'local_only' | 'km_only' | 'dual_write': 由 Stage 1 确认>",
    "current_stage": "<string: 当前正在执行的阶段 key，如 'stage3'>",
    "session_links": [
      {
        "conversation_id": "<string: CatPaw 会话 ID>",
        "share_url": "<string: 会话分享链接 URL>",
        "created_at": "<ISO8601: 链接生成时间>",
        "source": "<'catpaw_desk' | 'catpaw_ide' | 'other': 会话来源环境>"
      }
    ],
    "post_stage_hooks": {
      "_agent_instruction": "⚠️ 每个主阶段(stage1~stage7)标记 completed 后、进入下一阶段之前，MUST 按顺序执行以下 actions，全部成功后才可推进",
      "actions": [
        {
          "id": "report_stage",
          "description": "执行日志上报脚本，确保 reported_at 被脚本自动回写",
          "command": "node {skill_root}/scripts/report-stage.js --stage {completed_stage_key} --context {this_file_absolute_path}",
          "success_criteria": "终端输出 '✅ [report-stage] 已上报' 且对应 stage 的 reported_at 不为 null",
          "failure_action": "重试一次，仍失败则记录到 errors[] 并继续"
        }
      ],
      "skill_root": "<string: fe-rd-workflow skill 的绝对路径，Stage 1 写入>"
    },
    "stages": {
      "stage1": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null: 阶段开始时间>",
        "completed_at": "<ISO8601 | null: 阶段完成时间>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage2": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage2.0": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage2.1": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage2.2": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage3": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage3.1": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage3.2": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage3.3": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage4": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage4.1": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage4.2": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage4.3": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage5": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage6": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      },
      "stage7": {
        "status": "<'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'>",
        "started_at": "<ISO8601 | null>",
        "completed_at": "<ISO8601 | null>",
        "reported_at": "<ISO8601 | null: ⚠️ 为 null 时禁止进入下一阶段，status 变为 completed 后必须立即执行 post_stage_hooks 直到此字段被回写>"
      }
    }
  },

  "current_work_ask": {
    "stage1": "<'resolved' | 'pending' | 'rejected'>",
    "stage2": "<'resolved' | 'pending' | 'rejected'>",
    "stage2.0": "<'resolved' | 'pending' | 'rejected'>",
    "stage2.1": "<'resolved' | 'pending' | 'rejected'>",
    "stage2.2": "<'resolved' | 'pending' | 'rejected'>",
    "stage3": "<'resolved' | 'pending' | 'rejected'>",
    "stage3.1": "<'resolved' | 'pending' | 'rejected'>",
    "stage3.2": "<'resolved' | 'pending' | 'rejected'>",
    "stage3.3": "<'resolved' | 'pending' | 'rejected'>",
    "stage4": "<'resolved' | 'pending' | 'rejected'>",
    "stage4.1": "<'resolved' | 'pending' | 'rejected'>",
    "stage4.2": "<'resolved' | 'pending' | 'rejected'>",
    "stage4.3": "<'resolved' | 'pending' | 'rejected'>",
    "stage5": "<'resolved' | 'pending' | 'rejected'>",
    "stage6": "<'resolved' | 'pending' | 'rejected'>",
    "stage7": "<'resolved' | 'pending' | 'rejected'>"
  },

  "documents": {
    "implementation_checklist": {
      "status": "<'pending' | 'in_progress' | 'completed' | 'skipped'>",
      "local_path": "<string | null>",
      "km_content_id": "<string | null>"
    },
    "delivery_report": {
      "status": "<'pending' | 'in_progress' | 'completed' | 'skipped'>",
      "local_path": "<string | null>",
      "km_content_id": "<string | null>"
    }
  },

  "local_docs": {
    "demand-spec": {
      "status": "<'pending' | 'completed' | 'skipped'>",
      "path": "<string | null: .duo/xxx/docs/demand-spec.md>"
    },
    "tech-design": {
      "status": "<'pending' | 'completed' | 'skipped'>",
      "path": "<string | null: .duo/xxx/docs/tech-design.md>"
    },
    "dev-tasks": {
      "status": "<'pending' | 'completed' | 'skipped'>",
      "path": "<string | null: .duo/xxx/docs/dev-tasks.md>"
    }
  },

  "outputs": {
    "branch": {
      "feature": "<string | null: feature 分支名>",
      "release": "<string | null: release 分支名>",
      "repo_ssh": "<string | null: 仓库 SSH 地址>"
    },
    "fedo": {
      "task_id": "<number | null>",
      "workflow_id": "<number | null>",
      "task_url": "<string | null>",
      "workflow_url": "<string | null>"
    },
    "pr": {
      "url": "<string | null>",
      "status": "<'pending' | 'open' | 'merged' | null>"
    },
    "deploy": {
      "env": "<'test' | 'staging' | 'production' | null>",
      "url": "<string | null>",
      "status": "<'pending' | 'success' | 'failed' | null>"
    }
  },

  "skip_decisions": {
    "<stage_key>": "<string: 跳过原因>"
  },

  "user_confirmation": {
    "<stage_key>": {
      "confirmed_at": "<ISO8601>",
      "note": "<string | null>"
    }
  },

  "errors": [
    {
      "stage": "<string>",
      "timestamp": "<ISO8601>",
      "message": "<string>",
      "resolved": "<boolean>"
    }
  ]
}
```

---

## 字段写入时机

| 字段路径 | 写入时机 | 写入方 |
|---------|---------|--------|
| `meta.*` | Stage 2（仓库初始化）首次创建时 | Stage 2 |
| `meta.mode` | 流程启动时用户确认后 | 启动 subagent 判断步骤 |
| `input.*` | Stage 1（前置准备与环境检查）提取参数后 | Stage 1 |
| `runtime.complexity` | Stage 3（需求分析与技术设计）完成后 | design-spec skill |
| `runtime.doc_write_strategy` | Stage 1（前置准备与环境检查）确认后 | Stage 1 |
| `runtime.current_stage` | 每次进入新阶段时实时更新 | 各阶段 |
| `runtime.post_stage_hooks` | Stage 1 初始化时写入（含 skill_root 绝对路径） | Stage 1 |
| `runtime.session_links[]` | 每次日志上报时由 report-stage.js 内部触发 generate-session-link.js 异步写入（去重 by conversation_id） | generate-session-link.js |
| `runtime.stages.*.status` | 阶段状态变化时 | 各阶段 |
| `runtime.stages.*.started_at` | 阶段状态变为 `in_progress` 时 | 各阶段 |
| `runtime.stages.*.completed_at` | 阶段状态变为 `completed` / `skipped` / `failed` 时 | 各阶段 |
| `runtime.stages.*.reported_at` | 阶段日志上报成功后由自动写入 | 各阶段 |
| `current_work_ask.*` | 各阶段完成/跳过/失败时；恢复检查后 | check.md 逻辑 |
| `local_docs.spec.*` | Stage 3.1 完成后 | design-spec skill |
| `local_docs.design.*` | Stage 3.2 完成后 | design-spec skill |
| `local_docs.tasks.*` | Stage 3.3 完成后 | design-spec skill |
| `outputs.branch.*` | Stage 2 分支创建后； | Stage 2 / duo-fedo |
| `outputs.fedo.*` | Stage 2 FEDO 任务/流水线创建后 | duo-fedo skill |
| `outputs.pr.*` | Stage 6 PR 创建后 | Stage 6 |
| `outputs.deploy.*` | Stage 6 部署完成后 | Stage 6 |
| `skip_decisions.*` | 用户选择跳过某阶段时 | 各阶段 |
| `user_confirmation.*` | 用户确认某阶段产物时 | 各阶段 |
| `errors[]` | 任意阶段发生错误时 | 各阶段 |

---

## 初始化模板

> Stage 2（仓库初始化）首次创建 `workflow-context.json` 时使用此模板：

```json
{
  "meta": {
    "skill": "fe-rd-workflow",
    "version": "V2",
    "mode": "single_agent",  // 用户确认后写入：single_agent 或 multi_agent
    "started_at": "",
    "project_root": ""
  },
  "input": {
    "mis": "",
    "prd_link": "",
    "km_parent_id": "",
    "api_link": null,
    "ux_link": null,
    "user_description": "",
    "fedo_info": {
      "ones_link": null,
      "iteration_name": null,
      "task_name": null,
      "project_name": null,
      "tech_stack": null,
      "assignee": null,
      "qa": null,
      "pm": null
    }
  },
  "runtime": {
    "complexity": null,
    "doc_write_strategy": "local_only",
    "current_stage": "stage2",
    "session_links": [],
    "post_stage_hooks": {
      "_agent_instruction": "⚠️ 每个主阶段(stage1~stage7)标记 completed 后、进入下一阶段之前，MUST 按顺序执行以下 actions，全部成功后才可推进",
      "actions": [
        {
          "id": "report_stage",
          "description": "执行日志上报脚本，确保 reported_at 被脚本自动回写",
          "command": "node {skill_root}/scripts/report-stage.js --stage {completed_stage_key} --context {this_file_absolute_path}",
          "success_criteria": "终端输出 '✅ [report-stage] 已上报' 且对应 stage 的 reported_at 不为 null",
          "failure_action": "重试一次，仍失败则记录到 errors[] 并继续"
        }
      ],
      "skill_root": ""
    },
    "stages": {
      "stage1": { "status": "completed", "started_at": null, "completed_at": null, "reported_at": null },
      "stage2": { "status": "in_progress", "started_at": null, "completed_at": null, "reported_at": null },
      "stage2.0": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage2.1": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage2.2": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage3": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage3.1": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage3.2": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage3.3": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage4": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage4.1": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage4.2": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage4.3": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage5": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage6": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null },
      "stage7": { "status": "pending", "started_at": null, "completed_at": null, "reported_at": null }
    }
  },
  "current_work_ask": {
    "stage1": "pending",
    "stage2": "pending",
    "stage2.0": "pending",
    "stage2.1": "pending",
    "stage2.2": "pending",
    "stage3": "pending",
    "stage3.1": "pending",
    "stage3.2": "pending",
    "stage3.3": "pending",
    "stage4": "pending",
    "stage4.1": "pending",
    "stage4.2": "pending",
    "stage4.3": "pending",
    "stage5": "pending",
    "stage6": "pending",
    "stage7": "pending"
  },
  "documents": {
    "implementation_checklist": { "status": "pending", "local_path": null, "km_content_id": null },
    "delivery_report": { "status": "pending", "local_path": null, "km_content_id": null }
  },
  "local_docs": {
    "demand-spec": { "status": "pending", "path": null },
    "tech-design": { "status": "pending", "path": null },
    "dev-tasks": { "status": "pending", "path": null }
  },
  "outputs": {
    "branch": { "feature": null, "release": null, "repo_ssh": null },
    "fedo": { "task_id": null, "workflow_id": null, "task_url": null, "workflow_url": null },
    "pr": { "url": null, "status": null },
    "deploy": { "env": null, "url": null, "status": null }
  },
  "skip_decisions": {},
  "user_confirmation": {},
  "errors": []
}
```
