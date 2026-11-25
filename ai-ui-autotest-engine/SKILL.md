---
name: ai-ui-autotest-engine
version: 6.6.0
description: 移动端 UI 自动化测试。以 steps.json（业务用例）输入驱动，执行环境准备、步骤走查、证据归档与完整性报告。当前实现覆盖 Android 与 HarmonyOS 两个平台（sandbox 云模拟器 + local 本地真机）。

metadata:
  skillhub.creator: "wangshicheng05"
  skillhub.updater: "wangshicheng05"
  skillhub.version: "V209"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "93069"
  skillhub.high_sensitive: "false"
---

# AI UI Autotest Engine

> **目录（作用域分层）**：所有状态都在**机器顶层根下的 `$STATE`** = `$AI_UITEST_HOME/engine/`（缺省 `~/.local/share/ai-ui-autotest/engine/`，跨安装 / 跨项目唯一；`AI_UITEST_HOME` 改顶层根、`AI_UITEST_STATE_HOME` 直接改 `$STATE`）：`run/`（运行态：`tasks/<ws>/{config,inputs,tmp,runs/<run>}/` + 入口 `ws/<ws>/cli`）、`reports/`（历史报告 `<batch>/<run>/`，执行前按 keep-latest-N 清理，默认留 5 个批次）、`console/`（统一控制台服务，全机唯一、常驻）、`credentials/`（AppMock SSO 凭据）、`toolchain/`（adb/hdc 路径缓存）、`cache/artifacts/<platform>/<form>/<pkg>/`（制品缓存，引擎永不自动清理）、`device-pool/`（预热台账等本机辅助文件；设备租约在服务端，不落本地）。同一顶层根下并列的 `cases/`（用例资产）与 `orchestration/`（编排产物）**归编排层所有，引擎不读也不写**。**Skill 目录内不产生任何运行态**（多副本 / 自动更新都不会丢进度、缓存、登录与报告）。
> **随包分发的依赖清单**：`references/toolchain/manifest.json`（adb 离线包：按平台声明包名、大小与解压白名单）与 `references/deps/manifest.json`（Python 包版本区间 + 静态资源大小/更新时间）。两者都由 `check-deps` 统一安装/校验。依赖清单带 `updated_at`：安装成功后写进机器级 `$STATE/deps/state.json`，下次比对不一致（依赖集合被 Skill 升级改过）才重装 Python 包并复核资源大小；一致则只做 import/大小复核 —— 不算 sha256、也不比较文件 mtime。adb 离线包按「版本目录 + 大小」判定是否可用，解压出的 adb 需能执行 `adb version` 才算成功。
> **workspace 入口（每轮测试第一步）**：`python3 -B scripts/cli.py ws-init` 分配 workspace 并生成入口 `$STATE/run/ws/<ws>/cli`（**绝对路径**）；**之后所有命令都必须通过该入口执行**（写作 `<入口> <命令>`），入口把 `AI_UITEST_TASK=<ws>` 注入进程以定位工作区。未经入口执行 → 直接报错，**无默认兜底**（避免静默落到共享目录）。入口与 `cli.py` 均已带 `python3 -B` + `PYTHONDONTWRITEBYTECODE=1`（源树零字节码，不做 pyc 缓存）；手工执行其它 python 入口（如 `scripts/aitest/dev/*.py`）同样加 `-B`。
> `--input` 支持**裸文件名**（按本 workspace 的 `$STATE/run/tasks/<ws>/tmp/` 解析）
> **统一传输端口**：每个 workspace 首个命令分配唯一 `transport-port.json` / `flow-context.meta.transport_port`，所有平台统一持有；当前只有 Android ADB 适配器把它映射为 `IMEITUAN_CLOUD_ADB_PORT`，HarmonyOS（hdc）/ iOS（WDA）暂不使用。

## 一、执行原则

1. **严格遵循 Skill 流程**：AI 必须严格按 SKILL.md 定义的阶段和子步骤顺序执行，不得跳过、合并或重排流程。
2. **禁止运行期改写已声明步骤**：steps 只依据 `steps.json`；页面不符走 hook 消歧并记 `needs_review`/finding，不得回改 `steps.json` 或重跑 `steps-generate`/`flow-init` 掩盖。
3. 测试结果必须可追溯。环境、登录、落地页、步骤、视觉扫描、动态 Mock 和报告都写入运行事件与证据清单。失败记录真实结果，不伪造成功。
4. 一次运行串行控制一台设备。`device create` 从**设备池**领取设备（复用空闲实例；**池满直接失败 `POOL_EXHAUSTED`，不会新建，也不要立即重试**）并登记本 run 的 owner 租约（服务端 `device_registry` 单表权威，无本地副本）；租约 owner 恒为 `<run>#<workspace>`，每条设备命令都会刷新心跳并校验归属——**租约被其他 workspace 持有时直接失败（`DEVICE_LEASE_LOST`）**，禁止继续操作该设备（否则两个分片会同时 tap/滚动，结论不可信）。收尾先 `device disconnect` 回收本 run 的 imeituan 会话（legacy 会话自动移入 `~/.imeituan/sessions/.stale/`，不删除），再 `device release` 归还租约（**不销毁实例**，留给池复用；release 后进入 120s 复用冷却，避免上一轮 session 未清理完就复用；`SESSION_CLEANUP_PENDING` 等单设备会话错误自动隔离旧 sandbox 并换机重试一次；`ADB_SERVER_COORDINATION_*` 仅 Android 调用 `device contract --repair-android-runtime` 修复本 workspace 独立 ADB 台账后重试一次，禁止换机）。每个 run 还会先 `mis acquire` 从**虚拟 mis 池**领取一个 AppMock 工作域（`mock_domain`，私有优先 → 公共兜底），所有 AppMock（规则 / 录制 / 环境 / 泳道）都以它为准，收尾 `mis release` 归还；它记录在 workspace 级 `intake.mock_domain`，与设备 / 报告归属的 `resource_mis` **恒定分离**。收尾阶段由 SOP 引擎自动处理，AI 只需执行 `flow-next` 返回的指令即可。共享设备（云模拟器）历次占用会在 `/data/local/tmp` 残留安装/传输中间产物（清数据不覆盖该目录），需要时可执行 `device clean-tmp`：只删白名单后缀的产物、**保留本 Skill 自己的设备侧缓存目录与临时文件**，不递归、不删目录。安装制品统一**先查 Skill 制品缓存**（`$STATE/cache/artifacts/`，唯一入口 `shared/artifact_cache.py`）：命中即免下载，未命中才下载一次，多个子 Agent 并行也只会下载一次。
5. 环境不可用时快速失败并收尾，不重试、不换数据对照、不深挖日志。
6. **先预置、后提问（硬门禁）**：用户已明确提供的值先经 `input-seed --answers` **一次性预置**（引擎按与作答同一套白名单 / 依赖校验入库，已预置的题不再下发）；剩余项才走 `input-next` → AskQuestion（原样传 `options`，每次只 1 题）→ `input-answer`（只提交刚下发的题 ID，禁止合并 / 跳答 / 未下发直接作答）；循环见 §二「阶段 0」。
7. **禁止复用历史产物**：每轮测试的判定依据必须全部来自**本次运行**的实时产物（`$STATE/run/`、`$STATE/reports/<batch>/<run>/`），不得引用历史 `$STATE/reports/` 下的截图、报告或日志作为判定依据。
8. **`steps.json` 是唯一真源**：用例只由 `ai-app-flow` 产出 `steps.json`（业务模型），引擎只接受 `<入口> steps-generate --steps <steps.json> --tag <tag>` 生成的 `steps-input`；**禁止**手写或编辑引擎内部 CASES / `steps-input.json`（生成产物只读，要改就改 `steps.json` 重跑）。
9. **统一控制台（跨会话共享；链接须转达用户）**：`ws-init` 与 `ai-auto-ui-test` 的环境准备会自动**幂等启动** Web 控制台并打印访问链接（多设备实时画面 + 结构化动态日志）——**务必把该链接原样转达给用户**便于实时分析。服务**常驻、跨会话共享**：已启动则直接复用（其他会话据此跳过，**不要重启**）；`down` 一般不需要。控制台对测试执行**零侵入**（服务未启动时埋点不启用、零开销；启动后仅非阻塞落盘）。
10. **线上支付可整体执行、但必然支付失败（属预期）**：平台下发的线上账号未实名/未绑卡，允许走完下单 → 收银台 → 支付，以下单接口、支付参数与未支付订单号为断言对象（`unpaid_expected` 即通过并记录 `orderId`，`paid` 属意外成功须立即取消/退款并记录，`unknown` 判失败），退款失败必须在报告与结论中显式列为风险并提示用户手动退款，且该账号禁止绑卡、改价、代付等真实资金操作。

## 二、运行模型

### 阶段 0：信息收集 → 流程初始化

```bash
# ① 分配 workspace + 生成入口（整轮测试只执行一次，之后 <入口> 固定不变）
python3 -B scripts/cli.py ws-init

# ② 之后所有命令都通过 <入口> 执行（<入口> = $STATE/run/ws/<ws>/cli，绝对路径）
<入口> check-deps          # 唯一的安装入口：缺什么装什么（pip/npm/解压内置 adb 离线包）
<入口> toolchain           # 只读体检：adb/hdc 从哪来、版本、内置离线包是否完好

# ③ 预置已知值：先看问题目录，再把「用户已明确提供」的值一次性 seed
#    用户没给的不写（留给 ④ 逐题问）；派生键（device_type/platform/app/auth_method/credential）不写
#    credential 默认不问：线上由平台下发、测试环境用号池；要换号才 seed credential（需带 country_code）
#    bundle_lock：题面已前置 steps.json「可测性环境」声明里的值
#    场景 AppMock 不在此采集：case 级配置（env.mock_ids），无需作答
<入口> input-schema                    # 问题目录：字段 id / 选项 / 依赖 / 派生键
<入口> input-seed --answers '{"env_type":"A","resource_mis":"<mis>","device_combo":"sandbox-android-meituan",...}'

# ④ 逐题收集剩余项（已 seed 的不再问）：一步一题循环 ——
#    input-next（下发 1 题 + next 指针）→ AskQuestion（只放这 1 题）
#    → input-answer（只提交刚下发的题 ID）→ 回 input-next，直到 done（规则见 §一.6）
<入口> input-next                     # 返回 question + progress + next 指针
<入口> input-answer --id <当前下发的ID> --value <值>

# 收集完成后：steps.json → steps-input.json → 初始化流程
# steps.json 由 ai-app-flow 产出（一个用例一个文件），落盘前先过 steps_cli check
<入口> steps-generate --steps <steps.json 绝对路径> --tag {tag}
<入口> flow-init --dir <run-name> --input 'steps-input-{tag}.json' --flow-name <Flow名> [--run-type regression]
<入口> flow-next                       # 阶段 1 入口
```

> **workspace 入口是硬门禁**：`ws-init` 是阶段 0 第一步，它输出的 `<入口>` 是整轮测试唯一的命令入口；漏用入口会被引擎直接拒绝（报“未指定 workspace”）。
> **预置优先（避免重复提问）**：先 `input-schema` 看字段与选项，把用户请求里**已明确给出**的值（设备组合 / 环境类型（A/P/B/C/D/E）/ MIS / 凭证（`credential`）/ 锁包等）用 `input-seed` 一次性入库；`input-seed` 返回 `remaining`（仍需问的题）与 `rejected`（非法 / 不适用的值），随后只需对 `remaining` 跑逐题循环。已给过的值绝不再问。`resource_mis` 能由当前身份（`HOTEL_UI_MIS` / 缓存 SSO 身份 / `git config user.email`）自动派生，此时会以 `source=derived` 出现、**不会下发提问**；只有当这些来源都拿不到时才是必答题，需指定其他 MIS 时仍可用 `input-seed` 覆盖。**场景 AppMock 不入采集**：它是 case 级配置（steps.json `env.mock_ids`），`steps-generate` 直接透传到该 case 的 `mock_ids`，无需作答。
> **强指针**：`input-next` 输出 `progress` + `next` 指针（`ask` 带可直接执行的 `cmd`），逐条照抄直到 `done`；结果落 workspace 级 `intake.json`。**`flow-init` 是阶段 0/1 分界线**：它只做协议载入与 run 目录创建；其后的 B0（`mis acquire`）、B1（`device create/setup`）、B2（`env-prepare` 登录）均由 `flow-next`/`flow-advance` 逐条驱动，AI 按返回值执行，**不会在 flow-init 内自动执行**。

### 阶段 1：引擎驱动

AI 不再手动决定下一步，按 `flow-next` 返回的命令执行，确认用 `ack --key`。「推进阶段」只做两件事：① 仅当 `flow-next` 明确输出「执行 python3 scripts/cli.py flow-advance 推进到下一阶段」时才调用 `flow-advance`；② 其余情况（含条件不满足被自动跳过的阶段）一律继续执行 `flow-next` 给出的命令。

**关键规则**：
- 逐条执行 `flow-next` 返回的指令，禁止批量自动化
- **长任务命令**（引擎标注「长任务·后台执行」）：**后台启动并轮询日志**；超时/失败后先确认旧实例已终止再重跑，**禁止前台阻塞、或并发/重跑已在进行的长任务**
- **条件不满足的阶段由 `flow-next` 自动跳过**（如无场景 Mock 时跳过 `B0_mock_preflight` / `T0_mock_restore`），输出只陈述「已跳过」；此时**不要**再调 `flow-advance`，否则会对已跳过的阶段重复推进，误伤下一阶段（无 `completion_check` 的阶段会被直接标完成）
- 截图自动生成（统一归档于每个 Case 的 `frames/`），按 `[REVIEW]` 指示读图确认
- 步骤失败时按引擎输出 hooks 优先修复，确认无法修复再用 `skip-case` 跳过；禁止以"时间成本"等理由跳过低成本修复
- **落地步骤失败属另一类结论**：`role=landing` 的首步 `open-url` 没把页面打开（商品下架 / 环境 URL 失效 / 登录态失效）时，后续断言已无意义 → 先按 hooks 重试/修复；确认入口不可达后把终态写成 `override-step-result --fail`（必须带 `--assert-verdict` 判定内建视觉断言），引擎会**自动**把 case 记 blocked 并进入报告阶段，**无需手工 `skip-case`**，更**禁止** `flow-fail`（会误判为用例业务失败并中断整批）
- 环境不可恢复时 `flow-fail --cleanup` 终止

## 三、用例输入：steps.json → 引擎

### 流程

用例的唯一真源是 **`steps.json`**（业务模型：用户看到什么、做了什么、期望什么）。
写它的是 `ai-app-flow`，读它的是本引擎，中间没有任何手写环节：

```bash
# ① 产出（ai-app-flow）：<case-dir>/steps.json
#    Schema：ai-app-flow/scripts/steps/model.py
#    模板：ai-app-flow/references/templates/steps-json-template.json

# ② 自检：结构校验 + 文本级 lint + 渲染只读视图（md 不参与执行）
python3 <ai-app-flow>/scripts/steps_cli.py check --in steps.json

# ③ 生成引擎步骤：业务模型 → CASES 映射 + sid 编号 + blur 注入 + intake 合成 device/env + 两级校验
#    （同时把业务真源 steps.json 与刚生成的 steps-input 冻结进 workspace `inputs/<tag>/`，
#     之后报告阶段只读这份副本，不再回读上游 .docs / .orchestration 目录）
<入口> steps-generate --steps <steps.json 绝对路径> --tag {tag}

# ④ 载入引擎
<入口> flow-init --dir <run-name> --input 'steps-input-{tag}.json' --flow-name <Flow名> [--run-type regression]
```

> **一个 run 可承载多个 Case（=一条报告行）**：`flow-init`（首个）→ `flow-add-case --dir <run> --input 'steps-input-<tag>.json'`（其余，可带 `--case-index`；`--dir` 可省略，缺省沿用当前活跃 run）→ 重跑 `flow-init` 重建上下文（**沿用同一批次/报告行**，不会另起空行）→ 每 Case 一次 `gen-report` Append → `flow-finalize` Close。`--flow-name` 优先级最高，多 Case 批次必须显式传，否则行标题退化为首个 `steps.json` 的 title。
> **运行类型**：输入声明 `runType=regression`（或 `【运行类型】...回归`）时，`flow-init` 必须追加 `--run-type regression`（或先 `export AI_UITEST_RUN_TYPE=regression`）；报告行 `run_type` 据此入库，工作台可按类型筛选。未声明时不传，默认 `adhoc`。
> `steps-input-<tag>.json` 是**生成产物**：只读，不回写、不手改。要改用例就改 `steps.json` 再跑 ③。
> 编排层的用例快照（`shard.cases[].steps_path`）直接用绝对路径传给 ③，无需先拷进 workspace。

### steps.json 结构

```json
{
  "caseId": "EC-100234",
  "title": "预付房型下单：选房 → 优惠明细 → 提交订单",
  "priority": "P0",
  "executionType": "deterministic",
  "env": {
    "scheme": "imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=order-submit&goods_id={goods_id}&checkinDate={checkinDate}",
    "type": "A",
    "mock_ids": [],
    "vars": {
      "goods_id": {"value": "12345678", "desc": "EC 用例提供的测试商品 ID"},
      "checkinDate": {"date": 4, "format": "%Y-%m-%d", "desc": "入住日期（今天 +4 天）"}
    }
  },
  "steps": [
    {
      "kind": "ui",
      "id": "open-landing",
      "name": "进入填写订单页",
      "action": {"kind": "open-url", "text": "<与 env.scheme 完全一致>"},
      "wait": {"type": "page_ready"},
      "checks": [{"type": "render_ready", "text": "填写订单"}]
    },
    {
      "kind": "ui",
      "id": "open-coupon",
      "name": "展开优惠明细弹层",
      "action": {"kind": "tap-text", "text": "优惠明细"},
      "checks": [{"type": "text", "text": "优惠合计"}]
    },
    {
      "kind": "ui",
      "id": "verify-coupon",
      "name": "核对优惠明细内容",
      "action": {"kind": "none"},
      "checks": [
        {"type": "text", "text": "优惠明细"},
        {"type": "vision", "text": "底部弹层展示优惠条目与合计金额，背景出现半透明遮罩"}
      ]
    },
    {
      "kind": "api",
      "id": "api-submit",
      "name": "校验提交订单接口",
      "api": {
        "method": "POST",
        "path": "/api/hotel/order/submit",
        "expectedFields": [
          {"source": "request", "field": "goodsId", "expected": "{goods_id}"},
          {"source": "response", "field": "orderId"}
        ]
      }
    },
    {
      "kind": "track",
      "id": "track-submit",
      "name": "校验提交订单埋点",
      "track": {"match": "hotel_order_submit", "expectedFields": {"page_type": "全日房"}}
    }
  ]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `caseId` / `title` | ✅ | 用例标识与名称（报告与平台引用） |
| `priority` / `executionType` | — | `P0~P3` / `deterministic`·`data-dependent`·`manual-review` |
| `env.scheme` | ✅ | 落地深链，**唯一事实源**（`imeituan://` 开头） |
| `env.vars` | — | `{value}` / `{ask, desc}` / `{date, format}` 三选一；steps 里出现的 `{xxx}` 必须在此声明 |
| `env.type`·`swimline`·`url_mappings`·`bundle_lock`·`testability`·`mock_ids` | — | 与引擎 / AppMock 同一套字段名（snake_case），同形状直传；`swimline` 内部为 `{lane_name, url_pattern}`，`bundle_lock` 内部为 `{name, version?}`（省略 `version` = 仅声明目标不锁包）；未声明的字段直接报错；`testability` 即 Pillow action 列表，`flow-init` 前置强校验 |
| `steps[].kind` | ✅ | `ui` / `api` / `track`；三者字段互斥（`ui` 只带 action/wait/checks，`api` 只带 `api`，`track` 只带 `track`） |
| `steps[].id` / `name` | ✅ | `id` 是稳定 slug（平台引用用）；执行序由引擎按数组下发，与 id 无关 |
| `steps[].action` | ui ✅ | `{kind, text?, value?}`：`open-url`/`tap-text`/`input-text`/`scroll-until` 必须给 `text`，`scroll-bottom`/`back`/`none` 不接受；`value` 仅 `input-text` 必填（要输入的文本，`text` 是锚点） |
| `steps[].wait` | — | `page_ready` / `text`（配 `text`）/ 省略 |
| `steps[].checks` | ui ✅ | ≥1 条：`render_ready`·`text`·`text_gone`·`vision`（`vision` 截图后由 AI 读本次运行截图判定） |
| `steps[].api` | api ✅ | `path`（必填，**后缀段匹配**）、`method`（缺省 GET）、`expectedFields[]`（`source`=request/response，`field` 可写语义名，`expected` 可选） |
| `steps[].track` | track ✅ | `match`（必填，空匹配会轮询到超时）、`expectedFields`（`{字段: 期望值}`） |

### 映射（引擎侧 `flow_json`，只做机械翻译）

| steps.json | 引擎 |
|---|---|
| `action.kind` | 同名 action；`none` → `assert-text`（纯断言、无副作用）；`scroll-bottom` → `scroll-edge` |
| `wait.type=page_ready` 或任一 `checks[].type=render_ready` | 步骤 `page_ready`（截图前等页面稳定） |
| `checks[].type=text` / `render_ready` | 文本断言 present（附带元素目录 vs 渲染一致性复核） |
| `checks[].type=text_gone` | 文本断言 gone |
| `checks[].type=vision` | 视觉断言：本步截图后生成 `verify_visual_assertion` hook，AI 读**本次运行截图**判定 |
| `env.vars` | case `vars`（占位符替换 + 执行前提问） |
| `env.type` / `swimline` / `url_mappings` / `bundle_lock` / `testability` | case `env`（同名字段直接带入；与 intake 合成时场景声明优先） |
| `env.mock_ids` | case `mock_ids`（case 级，`B0_mock_preflight` 做同 case 冲突检测） |

生成期由引擎补齐、AI **不要写**的东西：
- `steps[0]` 缺失时按 `env.scheme` 注入落地步骤；首步在装载层补 `role=landing` + `page_ready` + 一条内建落地校验（运行期截图自证）；sid 编号 S/A/T；`input-text` 后自动补 `blur-input`（锚点同名）；`device` 缺省由 intake 合成。

### 写步骤的口径

- **落地页由首步 `open-url` 表达（唯一事实源）**：`steps[0]` 必须是 `open-url` 且 `action.text` 与 `env.scheme` 完全一致；漏写时引擎会用 `env.scheme` 自动注入，写了两份不一致的 URL 直接报错。首步落地步恒为 PENDING，必须完成 `verify_landing_page`（AI 读**本次运行截图**判定「是否真的进入目标页」，非登录页/报错页/白屏兜底页）后才能推进；判 fail 时引擎自动把 case 记 blocked 并进入报告阶段。纯 api/track 用例不注入落地步。
- **操作文案口径**：`tap-text` / `scroll-until` 优先精确匹配；页面文案与 `action.text` 存在**唯一子串/重叠关系**时（页面「已优惠¥175」vs `action.text`「已优惠」），运行期唯一子串兜底直接命中并记 `action_hit`（verdict=semantic）→ 该步标记 `needs_review`、evidence 记 `text_mismatch`，不额外产生 hook；多形态候选不兜底，转 `resolve_text_not_found`（tap）/ `SUBSTRING_AMBIGUOUS`（scroll）hook 交 AI 消歧。
- **input-text 的锚点语义**：`action.text` 只是「输入框附近的锚点」或一句语义描述，引擎在锚点所在**同一视觉行**内自行定位 `role=input` 目标；定位不到（行内无输入框 / 需先点击展开 / 是选择器）转专用 hook `resolve_input_box`，由 AI 用截图 + 锚点行成员（含宽度）推断坐标后以坐标形态重跑（输入动作禁止用坐标点击替代）。
- **「开 → 看 → 关」拆分**：交互步骤（`tap-text` / `back` / `scroll-until`）的 `checks` 只放页面标题等**轻量标志**，用例声明的全部预期内容拆到独立步骤（`action.kind=none` + 多条 `checks`）。弹窗类按「开（`tap-text` + 等待就绪）→ 看（`none` + 内容断言）→ 关（`back` + `text_gone`）」三段拆。
- **场景 Mock 是 case 级（`env.mock_ids`）**：Mock 对同一请求「命中即短路」，同一 case 内不允许两个 mockId 命中同一接口（`B0_mock_preflight` fail-fast）；跳 case 由 `C1_mock_apply` 差量开关隔离，绝不共存。
- **自检**：`steps_cli check` 必须通过（结构 + 文本级 lint：禁时长 / 坐标 / 像素 / 凭证 / 方位词），再按 `references/review-rules.md` 逐条审校（R-STR → R-ACT → R-AST → R-SEM → R-PAR → R-CFL），**P0 全通过后**才执行 ③。

### 模糊推定

Flow 含 `pending`/`待审校`/`以实际为准` 时：操作推定最合理文案（上下文优先→美团常识回退），标注 `"inferred": true`，能用文案描述的写 `{"type": "text"}`，只剩形态/排版无法用单一文案表达的写 `{"type": "vision"}`。推定不违反 R-SEM-001。

## 四、命令一览

`step` 命令的 `--help` 会列出每个 action 子命令及其必填参数（缺失会直接报错并给出标准用法）。本节只做命令分类导航，不重复列参数。**阶段 1 中 AI 不应手动构造命令，直接执行 `flow-next` 返回的指令即可。**

- **用例输入与审校**：`steps-generate`（`steps.json` → `steps-input.json`：业务模型→CASES 映射、sid 编号、blur 注入、intake 合成 device/env、占位符登记、两级校验）`validate`（dry-run 校验已生成的 steps-input）
- **交互与断言**：`screenshot`（`--out` 为纯文件名时归档到当前 Case 的 `frames/`；为路径时按原路径） `open-url` `tap-text` `tap` `scroll-until` `scroll-edge` `input-text` `blur-input` `assert-multi` `swipe` `dismiss-recce`（`assert-text` 合并至 `step assert-text`）
- **元素定位**：`find-text --text <文案>` `find-icon --anchor <邻近文案>` `find-input --anchor <邻近文案>` `probe-status` `inspect-tree`
- **Flow 引擎驱动**：`step` `log-record` `override-step-result` `assert-fields`（API/Track 字段判定；埋点多候选用 `--picked <序号>` 消歧） `response-search`（API 响应按需视图：`--skeleton` 结构总览 / `--query` 关键字定位 / `--path` 精确取值） `flow-init` `flow-add-case`（把另一个 case 追加进同一 run：`--dir <run>`（**可省略**，缺省沿用当前活跃 run）+ `--input`，可直接传 `steps-input-<tag>.json`，取 `cases[--case-index]`；追加后重跑 `flow-init` 会沿用同一批次与报告行）`flow-status`（`--sid <SID>` 查单步精简详情）`flow-case-status` `flow-next` `flow-advance` `hook-info`（`--hook-id <ID> [--sid <SID>]` 按需查询单个 hook 的完整操作指引）`ack` `skip-case` `case-post-scan`（Case 收尾补扫：无失败/待判定项自动跳过、零设备成本；有则**先快速回顶**（纯手势不截图，`--no-reset-top` 可关闭）、再自上而下补看 ≤5 屏截图并列出待复核项，帧序即页面顺序，AI 一次性读图后改判）`flow-fail` `flow-finalize` `gen-report`（生成当前 Case 报告并**立即追加**到平台报告；每 Case 一次）
- **异常终止**：`report-error`（异常终止收尾前调用，上报 AI 分析结论和解决方案）
- **workspace / 环境与设备**：`ws-init`（分配 workspace + 生成入口） `check-deps`（缺什么装什么） `toolchain`（adb/hdc 来源与内置离线包体检，只读） `prune`（清理旧报告归档，keep-latest-N） `preflight-clean` `post-clean` `device disconnect`（收尾回收本 run 会话，legacy 自动隔离到 `sessions/.stale/`） `install-app` `force-stop` `launch` `set-location` `mock`（含 `mock effective`：聚合 ptest + 场景 Mock 的生效集并判定是否仍被 ptest 全量规则遮蔽） `mock-preflight`（场景 Mock 预检：快照 union + 冲突检测 + 清场） `mock-apply --case-index <i>`（把场景 Mock 收敛到指定 case） `mock-restore`（恢复 union 到执行前状态） `mis`（虚拟 mis 池：`mis acquire` 领虚拟 mis / `mis status` 查看 / `mis release` 释放 / `mis release-stale --hours N`） `input-schema` `input-seed` `input-next` `input-answer` `input-status` `env-prepare` `validate` `case-init`

以下是 `--help` 之外仍需要说明的行为语义（不属于参数，`--help` 不会体现）：
- `back` 是 Flow action，单独执行用 `step back`。
- `step` 的独立操作（不绑定声明步骤）若未提供 `--desc`，引擎按 action + 参数自动派生描述，不会写入 desc 为空的孤立记录。
- `dismiss-recce` 检测并拖离 Recce 调试浮层（`tap-text` 遇遮挡时自动调用，也可手动使用）。
- `log-record / override-step-result --img` 可指定已有截图（`frames/` 下的文件名；不传时自动截当前画面并归档到 `frames/`）。
- `log-record` 是唯一能写「无判定备注」的入口：传 `--note` 且不带 `--pass/--fail/--ok` → 记录 `ok=None`，带 `--sid` 归步骤 `annotations`、不带则归 Case `notes`，均不计入通过/失败统计。
- **兜底操作必须归属父步骤**：`step --for-sid <SID> tap --action-x … --action-y …` 把坐标兜底等补救动作绑到已声明步骤 —— 记录进该步证据/attempts，**不改其结论**（结论权在断言与 AI override）；禁止裸写 `step tap`（会落成脱离步骤的孤立 finding 并覆盖证据截图）。`--for-sid` 与 `--sid` 互斥。
- **不可原地重跑的动作**：`back` / `input-text` 有不可撤销副作用（back 多退一页、input 重复叠加），**已执行过的步骤禁止原地重跑**（引擎直接 `STEP ABORT`）；确需再执行请换新 sid（`step --sid S3b back …`，记为父步骤 retry），页面已偏离时用 `open-url` 恢复。
- **hook 指引按需查询**：`flow-next` / `[AI_CHECKLIST]` 只给 hook id + 一行摘要 + 查询/标记命令；需要完整操作指引时执行 `hook-info --hook-id <ID> --sid <SID>`。

## 五、异常处理

0. **异常终止闭环**：运行时异常已由引擎自动写入时间线，随报告入库，无需手动处理。**平台级归因诊断的唯一上报入口是 `report-error`**，由 AI 在异常终止收尾前调用。异常终止时按 3 步闭环：
   **第 1 步 — 分析原因**：结合日志、执行产物、Skill 实现代码，定位失败根因。
   **第 2 步 — 给出方案**：向用户说明失败原因和解决方案。
   **第 3 步 — 上报诊断**：收尾前调用 `<入口> report-error --help` 查看参数并上报。

1. **断言**：`kind: "text"` 断言先由引擎做程序化判定 —— 精确匹配 → `pass/exact`；`expect` 与页面节点文案互为子串且**形态唯一** → `pass/semantic`（如 `expect`「没有更多了」/ 页面「- 没有更多了 -」）。**待复核唯一口径**：`needs_review = 通过且判定方式非字面精确（verdict ≠ exact）` —— `semantic`（引擎唯一子串推断 / AI 语义确认）与 `visual` 均标记待人工复核，仅 `exact` 属确定性结论；实现见 `assertions.engine.compute_needs_review`，动作层同口径（唯一子串兜底记 `action_hit.verdict=semantic`），报告在步骤（`steps[].needs_review`）与批次（`step_needs_review` / `assert_needs_review`）打标。两者都不成立才构建元素目录交 AI 语义确认，逐条按 **断言 id（A1/A2…）** 判定；`kind: "visual"` 用于纯视觉判断，可配 `targets` 拆开多条硬性验收点；`match: "gone"` 用于排除异常值（如 `{"kind":"text","match":"gone","expect":"https"}`），引擎会同时确认文本未以子串形态残留。判定口径与写回命令由 hook 提示给出（`hook-info`）。`step-type=assert` 步骤必须提供至少一项断言，否则 `flow-init` 报错。
   - action 文案口径差异（TEXT_NOT_FOUND）只记备注，既不判失败也不额外记一条 PASS：`log-record --desc "<摘要>" --note "<口径差异说明>"`（不带 `--pass/--fail/--ok` → 写一条无判定 note，归入 Case `notes` 或步骤 `annotations`，不计入统计）。
   - 一个步骤只写一次 `--assert-verdict`（同时覆盖文本断言与视觉复核）。

2. **设备创建失败**：云模拟器失败=基础设施不可用，**直接终止**（不重试不换参数），按第 0 条 3 步闭环。本地真机异常若带 `guidance` 则按步骤引导重试。

3. **本地真机安装/信任弹窗**：`local` 未安装 App 时自动补装（鸿蒙约 2-3 分钟），`important_notices` **原样转述给用户**。鸿蒙首次启动被"企业应用未受信任"拦截时，`device setup` 会暂停并携带 `guidance`：引导用户手动信任后重试，不要判为不可恢复。

4. **测试数据变更**：先用 steps.json 原始参数完成首次落地验证，确认链路健康后再切换用户指定数据。

5. **感知通道适用范围**：文本断言与元素定位走探针链。视图树由 App 端按页面注入 dump 能力，业务容器页（MRN / Recce / Mach / 动态布局）可用；首页（MainActivity）未注入，`inspect-tree` 必然超时，须改用截图或 Activity 焦点判断。

6. **元素定位按目标选命令**：有文案用 `find-text --text <文案>`（直接返回坐标）；**无文案图标（箭头、图标按钮）在 steps.json 里用 `action.kind=tap` + `action_anchor`（锚点行唯一可点击目标 → 引擎自动点击；多/无 → 走视觉通道消歧）**；`find-icon --anchor <邻近文案>` 用于复核与坐标兜底（返回**锚点祖先链 + 该行候选**，结合周边文案判断点哪个 `clickable`，其 `tap` 字段即坐标）；输入框用 `find-input --anchor <邻近文案>`（同上，按 `role=input` 过滤）。`tap --action-x/--action-y` 坐标必须来自以上命令或截图取证。`inspect_tree.json` **禁止自行写脚本解析**（直读顶层字段全为空，会得「页面无节点」假象）。

7. **WebView（H5）页面元素定位**：WebView DOM 由 Chromium 绘制，不向 Android View 树注册子节点，`inspect-tree` 采不到其内部节点（正常现象）。**但 H5 已被统一目标模型覆盖**：webview 探针经 CDP 导出 DOM 节点（`dump_nodes`），`get_current_nodes` 会把 native 与各渲染层的节点合并去重（H5 节点在目录/候选中标注 `(webview)`），因此 **目录（sidecar）、候选清单、邻域查询、`find-icon`/`find-input` 都能看到 H5 元素**；`find-text` 走探针链（native 未命中回退 DOM，命中标注 `[webview]`）。前提是 App 已开启 WebView 调试开关，未开启时探针不可用并自动退化为纯 native（此时才需要 `find-text` + 截图目测）。排查首选 `probe-status` 确认探针链与目标页面。

8. **滚动未命中（SCROLL_TARGET_NOT_FOUND）**：引擎先精确/子串定位，均未命中才盲滑搜索；一旦滑动后页面内容无变化（已到边界/加载完）立即停止，不再跑满 5 次。hook 会同时给出截图与元素目录 —— **重试必须用目录里匹配到的真实节点文案**，拿原目标文案原样重试必然再失败。

## 六、产物

报告按 **Open → Append → Close** 增量写入同一行：Open（编排层预置；独立运行由 `flow-init` 预置）只写行级元信息与空 `cases`，**托管运行时引擎不得重复 Open**；每个 Case 的 `C5_report`（`gen-report`）只追加**这一个** Case（平台按 `case_id` 幂等合并并重算汇总）；`flow-finalize` 只做 Close（补传失败 Case + 回写 `cases[0].run_status` 与行级 `duration`）。单次请求体积恒等于一个 Case，与批次大小无关，**禁止改回一次性全量上传**（多 Case 必 413）。`flow-finalize` 将本 workspace 归档到 `$STATE/reports/<batch>/<run>/run/`，随后 `post-clean` **删除本 workspace 与其入口**。同一编排的多个分片默认各自独立（各自 `<batch>`/`<run>`/报告行）；仅当编排层显式注入 `AI_UITEST_BATCH_ID`（共享批次目录）与 `AI_UITEST_REPORT_ID`（共享报告行，引擎据此跳过 Open）时，各分片才 Append 到同一行——此时 Open 与最终 Close（行级 `run_status` / `duration`）必须归编排层统一执行，分片只 Append。`<run>` 重试落 `-r2/-r3`，不覆盖上一轮。目录内保留 `meta.json`（批次/run/状态的稳定索引）、`report.json`（批次报告）、`report-upload.json`（增量上报台账）、`case_NN/report.json` + `frames/`（Case 报告与截图 S3 URL）、`case_NN/inputs/`（**输入原文**：业务真源 `steps.json` + 执行输入 `steps-input.json`，与 `frames/` 同级，报告包自包含）和 `run/`（全部原始执行产物，含 inspect_tree / dumps 等过程信息）供数据分析。归档与报告统一脱敏，运行态原值不外泄。批量报告必须包含全部声明的 Case，缺失则 `run_status: incomplete`。报告归档在**执行前**（`flow-init`）自动滚动清理：保留最近 `AI_UITEST_KEEP_REPORTS` 个批次（缺省 5，0=关闭），60 分钟内写入的批次受保护不删；也可 `python3 scripts/cli.py prune [--keep N] [--dry-run]` 手动预览/清理。

**补测 / 重测（只重跑报告内部分 Case）**：注入 `AI_UITEST_REPORT_ID` + `AI_UITEST_BATCH_ID`（复用原报告行，引擎跳过 Open、按 `case_id` 覆盖目标 Case，行级汇总由平台重算），并额外 `export AI_UITEST_PARTIAL_RERUN=1` —— 此时 `flow-finalize` **不回写报告级 `duration`**（保留首轮全量口径），也不会把未重跑的 Case 置为缺失。注意报告行 `run_status` 的语义是「本轮声明的 Case 是否全部产出报告」，不是通过率（全部 Case blocked 也可能是 `complete`），补测失败与否以 Case 状态和调用方 verdict 为准。

Case 报告的 `steps` 是已声明步骤结论，`findings` 是独立判定，`notes` 是无判定备注。任何 fail 都会使 Case 状态为 failed，不存在"有失败但显示全绿"的情况。

## 七、时间线记录

`record-event` 用于向 `audit/run-events.jsonl` 记录 AI 分析过程（读图、重试、环境诊断等）。传 `--evidence-type` 即按证据格式记录，详情见 `--help`。