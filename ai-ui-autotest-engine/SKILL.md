---
name: ai-ui-autotest-engine
version: 6.4.0
description: 移动端 UI 自动化测试。以 Flow 输入驱动，执行环境准备、步骤走查、证据归档与完整性报告。基于 PlatformOps / DeviceLifecycle / AppDescriptor / RendererProbe 四维度抽象（RendererProbe 通过 probe_name 属性标识探针类型），当前实现覆盖 Android 与 HarmonyOS 两个平台（sandbox 云模拟器 + local 本地真机）。

metadata:
  skillhub.creator: "wangshicheng05"
  skillhub.updater: "wangshicheng05"
  skillhub.version: "V159"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "93069"
  skillhub.high_sensitive: "false"
---

# AI UI Autotest Engine

> **目录**：`scripts/` 下；`steps-input.json` → `.run/tmp/`；运行产物 → `.run/cases/<run-name>/`；Flow 输入 → `.run-input/flows/

## 一、执行原则

1. **严格遵循 Skill 流程**：AI 必须严格按 SKILL.md 定义的阶段和子步骤顺序执行，不得跳过、合并或重排流程。
2. 测试结果必须可追溯。环境、登录、落地页、步骤、视觉扫描、动态 Mock 和报告都写入运行事件与证据清单。失败记录真实结果，不伪造成功。
3. 一次运行串行控制一台设备。`device create` 自动清理该用户名下所有遗留实例后创建新设备。收尾阶段由 SOP 引擎自动处理，AI 只需执行 `flow-next` 返回的指令即可。
4. 环境不可用时快速失败并收尾，不重试、不换数据对照、不深挖日志。
5. **AI 不得预填环境选项**：先跑 `*-required` 看输出再问用户，禁止在 `save-answers` 中预填未选择的值。提取的 `options` 必须原样传给 AskQuestion，禁止自行构造、合并、删减或改标签。
6. **禁止复用历史产物**：每轮测试的判定依据必须全部来自**本次运行**的实时产物（`.run/`、`output/run-<ts>/`），不得引用历史 `output/` 下的截图、报告或日志作为判定依据。
7. **CASES 文件强制约定**：先 `cases-create --tag <tag>` 创建空文件，AI 再写入内容；写完 `wc -c` 确认非空后再 `steps-generate`。禁止用编辑器直接新建该文件。

## 二、运行模型

### 阶段 0：人工准备

严格按以下顺序执行：

```bash
python3 scripts/cli.py preflight-clean
python3 scripts/cli.py check-deps
python3 scripts/cli.py flow-create --name <Flow名>  # 多 Flow 场景：每个 Flow 执行一次
# AI 写入完整 Flow 内容
python3 scripts/cli.py device-required
# 第1步：先跑 env-required（不带 --type），查看输出中的 options
python3 scripts/cli.py env-required --app <app>
# 第2步：将输出的 options 原样提取传给 AskQuestion（禁止自行构造/简化）
# 第3步：用户选择后，按选择的值存入 save-answers
python3 scripts/cli.py save-answers --answers '{"env_type":"<用户所选value>","mis":"<mis>"}'
python3 scripts/cli.py env-required --app <app> --device-type <device_type>
python3 scripts/cli.py config-required --flow-source <flow-文件路径>
# 录入测试身份（替换下方占位）
python3 scripts/cli.py save-answers --answers '{"account":"<测试身份>","password":"<对应凭据>"}'
python3 scripts/cli.py flow-convert --tag {tag}  # 多 Flow 场景：一次 --tag all 转换所有 Flow
# 强制约定：先用 cases-create 创建空 CASES 文件，AI 再写入 steps（写完 wc -c 确认非空）
python3 scripts/cli.py cases-create --tag {tag}
python3 scripts/cli.py steps-generate --input '.run/tmp/cases-{tag}.json' --tag {tag}
python3 scripts/cli.py flow-init --dir <run-name> --input '.run/tmp/steps-input-{tag}.json' --flow-name <Flow名> --mis <mis>  # ⚠️ 多 Flow 场景：只执行一次，所有 Flow 合入一个 cases 数组
python3 scripts/cli.py flow-next  # 阶段 1 入口，获取引擎第一条指令
```

**`flow-init` 是阶段 0/1 分界线**：创建 `flow-context.json`，此后依赖 active_case。`env-prepare` 在 `device create/setup` 之后执行，不是阶段 0 入口。

### 阶段 1：引擎驱动

AI 不再手动决定下一步，按 `flow-next` 返回的命令执行，阶段间用 `flow-advance` 推进，确认用 `ack --key`。SOP 顺序：B0-B3 批次头 → C0-C5 Case 循环 → T0-T2 批次尾。

**关键规则**：
- 逐条执行 `flow-next` 返回的指令，禁止批量自动化
- 截图自动生成（统一归档于每个 Case 的 `frames/`），按 `[REVIEW]` 指示读图确认
- 步骤失败时按引擎输出 hooks 优先修复，确认无法修复再用 `skip-case` 跳过；禁止以"时间成本"等理由跳过低成本修复
- 环境不可恢复时 `flow-fail --cleanup` 终止

## 三、Flow 转换

### 流程

1. `flow-convert --tag <tag>` → 解析元数据，输出 `metadata-<TAG>.json`
2. `cases-create --tag <tag>` → 创建空 CASES 文件占位（强制约定，写内容前必须先执行）
3. AI 写入 steps 内容（含 device/env/cases/steps），写完 `wc -c` 确认非空
4. `steps-generate --input '.run/tmp/cases-<tag>.json' --tag <tag>` → 输出 `steps-input-<TAG>.json`
5. `flow-init` → 载入引擎

### steps-input.json 结构

```json
{
  "batch_name": "{批次名称}",
  "device": { "type": "sandbox", "platform": "android", "app": "meituan", "auto_install": false },
  "env": {
    "type": "A",
    "auth_method": "password",
    "account": "<测试身份>",
    "password": "<对应凭据>",
    "mock_ids": [],
    "bundle_lock": [],
    "ptest": false
    // 当 type=B（泳道环境）时需额外提供：
    // "swimline": { "lane_name": "{泳道名}", "url_pattern": "/*" },
    // "url_mappings": [{ "url": "{域名}", "title": "{描述}", "betaUrl": "{映射地址}" }]
  },
  "cases": [{
    "case_id": "{case标识}", "case_name": "{case描述}",
    "landing_scheme": "imeituan://...mrn_biz={biz}&mrn_entry={entry}&mrn_component={component}",
    "params": {"<占位符名>": "<真实值>"},  // 键=占位符名（不带宽括号）；日期 {T+N:format} 自动解析，无需写入
    "steps": [
      {"sid":"S1","kind":"ui","desc":"开：点击目标","action":"tap-text","action_arg":"目标","step-type":"interaction","page_ready":true,"asserts":[
        {"kind":"text","match":"present","expect":"就绪文案"}
      ]},
      {"sid":"S2","kind":"ui","desc":"向右滚动到目标","action":"scroll-until","action_arg":"目标","direction":"right","step-type":"interaction","asserts":[
        {"kind":"text","match":"present","expect":"就绪文案"}
      ]},
      {"sid":"S3","kind":"ui","desc":"看：断言内容","action":"assert-text","step-type":"assert","asserts":[
        {"kind":"text","match":"present","expect":"预期1"},
        {"kind":"text","match":"present","expect":"预期2"}
      ]},
      {"sid":"S4","kind":"ui","desc":"关：关闭","action":"back","step-type":"interaction","asserts":[
        {"kind":"text","match":"gone","expect":"原文案"}
      ]},
      {"sid":"S5","kind":"ui","desc":"操作：点击锚点","action":"tap","action_anchor":"锚点","step-type":"interaction","asserts":[
        {"kind":"visual","expect":"AI 读截图确认预期效果呈现"}
      ]},
      {"sid":"A1","kind":"api","desc":"接口验证","api_assert":{
        "path":"/path/to/api",
        "expected_fields":[
          {"source":"request","field":"字段名","expected":"预期值"},
          {"source":"response","field":"字段名","expected":"预期值"}
        ]
      }},
      {"sid":"T1","kind":"track","desc":"埋点验证","track_assert":{"match":"事件名"}},
      {"sid":"T2","kind":"track","desc":"埋点参数校验","track_assert":{"match":"事件名","expected_fields":{"page_type":"全日房","button_name":"房型详情"}}}
    ]
  }]
}
```
`landing_scheme` 必须完整，日期占位符 `{T+N}` 执行时替换。支持 `{T+N:format}` 语法指定格式（如 `{T+4:%Y%m%d}` 输出 yyyyMMdd，`{T+4:%Y-%m-%d}` 输出 YYYY-MM-DD），不指定 format 时默认 `%Y-%m-%d`。`flow-init` 自动追加 debug 浮窗关闭参数，无需手动填写。UI / API / Track 步骤执行后均自动截图（命名 `case_NN_{sid}.png`），统一归档到当前 Case 的 `frames/` 目录；步骤记录以 `screenshots` 数组承载（每项含 `file`/`label`/`kind`），报告层跨同一 SID 的多条记录合并截图，任一记录有图即不丢图。API/Track 步骤匹配成功后自动 PASS；**埋点 `match` 用 `val_cid`/`nm`（分类级标识）命中多条时转 PENDING**，生成 `verify_track_fields` hook（携带候选清单），需 AI 按 `nm`/`val_lab` 语义选定后用 `assert-fields --picked <序号>` 消歧；配了 `expected_fields` 也生成该 hook。`val_bid`（精确事件 ID）命中永不歧义。响应体不进 `extracted_fields`，结构落 `diagnostics/response_skeleton_<SID>.md`，取值用 `response-search`。

**顶层字段**：

| 字段 | 说明 |
|---|---|
| `batch_name` | 批次名称，报告中展示 |
| `device` | 设备配置（可选，缺省走 sandbox-android-meituan 默认值，见下） |
| `env` | 环境配置（type/auth_method/account/password/mock_ids/bundle_lock/ptest）。**account/password 使用已录入的测试身份**（与 save-answers 一致） |
| `cases` | Case 数组，一个 Flow 文件 = 一个 Case。**多 Flow 场景**：将所有 Flow 的 Case 合并到同一个数组，`flow-init` 只执行一次 |
| `cases[].params` | AI 手动填充的占位符映射。`{name: value}`，value 取值：`null`（需用户提供）、`"__date__"`（`{T+N}` 或 `{T+N:format}` 日期，引擎自动解析）、具体值字符串（从「测试数据参考」填入） |

**`device` 块字段**（可选，缺省时全部走默认值）：

| 字段 | 可选值 | 默认值 | 说明 |
|---|---|---|---|
| `type` | `sandbox` / `local` / `cloud_device` | `sandbox` | 云模拟器（自动创建，复用现有 running 实例）；本地真机（跳过创建/销毁）；云真机（待完善） |
| `platform` | `android` / `harmony` | `android` | 决定 AndroidOps（imeituan-cli）或 HarmonyOps（hdc） |
| `app` | `meituan` / `dianping` | `meituan` | `dianping` 暂不支持 |
| `auto_install` | `true` / `false` | `false` | 仅 `local` 生效：版本不符时自动卸载重装。`sandbox` 恒为 `true` |

`type`/`platform`/`app` 组合必须命中 `SUPPORTED_DEVICE_COMBINATIONS`（sandbox-android-meituan / local-harmony-meituan / local-android-meituan），`flow-init` 硬校验。`local` 只允许 `auth_method=noop`。

**Kind 字段白名单与互斥校验**（flow-init 自动校验，混合字段会直接报错）：

| kind | 必需字段 | 禁止字段 | 说明 |
|---|---|---|---|
| `ui` | `action` | — | UI 交互与断言步骤 |
| `api` | `api_assert`（含 `path` + 可选 `expected_fields`） | `action` / `step-type` / `screenshot` / `asserts` | 接口字段验证（从录制数据匹配，逐字段断言） |
| `track` | `track_assert`（含 `match` + 可选 `expected_fields`） | `action` / `step-type` / `screenshot` | 埋点事件验证。`match` 用 `val_bid`（精确，命中即 PASS）或 `val_cid`/`nm`（分类级，命中多条→转 PENDING，AI 用 `assert-fields --picked` 消歧） |

**`api_assert` 语义规范**：

| 字段 | 必填 | 语义 |
|---|---|---|
| `path` | ✅ | Flow 原文路径，不补 `https://`；**后缀段匹配**（至少末尾一段一致即命中） |
| `expected_fields` | ❌ | **缺省 = 不校验字段**（匹配成功即自动 PASS）；配了才有字段级判定 |
| `[].source` | ❌ | `request` / `response` / `meta`（仅展示）；状态码固定写 `{"source":"meta","field":"http_code","expected":"200"}` |
| `[].field` | ✅ | **生成期可写语义名**（如「价格字段」）；真实路径 `response.<点号路径>` 由 `assert-fields` 解析后回写 |
| `[].expected` | ❌ | 允许直接引用 Flow 原文（含自然语言） |

### Action 选择映射表

AI 根据以下映射表选择 Flow 操作描述 → action + asserts。推定步骤按下方「模糊推定」规则走 `kind: "visual"`。

| Flow 描述关键词 | action | page_ready | asserts | 附加参数 |
|---|---|---|---|---|
| 进入页面 / 打开 Scheme / 跳转 | `open-url` | `false` | `[{"kind":"text","match":"present","expect":"就绪文案"}]` | |
| 点击有文案按钮（打开新页面） | `tap-text` | `true` | `[{"kind":"text","match":"present","expect":"轻量就绪标志"}]` | |
| 点击有文案按钮（当前页操作） | `tap-text` | `false` | `[{"kind":"text","match":"present","expect":"新内容"}]` | |
| 点击无文案图标 | `tap`（配 `action_anchor`） | `false` | `[{"kind":"visual","expect":"预期效果呈现"}]` | |
| 关闭弹窗 / 返回 | `back` | `false` | `[{"kind":"text","match":"gone","expect":"原文案"}]` | |
| 滚动到「xxx」 | `scroll-until` | `false` | `[{"kind":"text","match":"present","expect":"目标"}]` | `--direction`（可选，默认自动推断） |
| 滚动到底部 | `scroll-edge` | `false` | `[{"kind":"text","match":"present","expect":"底部标志"}]` | `--direction down` |
| 向右/左滚动到「xxx」 | `scroll-until` | `false` | `[{"kind":"text","match":"present","expect":"目标"}]` | `--direction right/left` |
| 快速滚动到 xxx 区域边界 | `scroll-edge` | `false` | `[{"kind":"visual","expect":"边界内容"}]` | `--direction up/down/left/right` |

> **方向统一约定**：所有 `--direction` 参数均采用 **用户语义**（想看的目标方向）：
> - `down` = 想看下方 → 引擎自动翻译为物理上滑（内容上移）
> - `up` = 想看上方 → 引擎自动翻译为物理下滑（内容下移）
> - `right` = 想看右侧 → 引擎自动翻译为物理左滑
> - `left` = 想看左侧 → 引擎自动翻译为物理右滑
> AI / SOP 只需表达「想看哪个方向」，物理手势由引擎内部处理。

| 输入「xxx」 | `input-text`（配 `action_anchor`） | `false` | `[{"kind":"text","match":"present","expect":"回显文案"}]` | |
| 断言出现 / 校验包含 | `assert-text` | `false` | `[{"kind":"text","match":"present","expect":"..."}]` | |
| 断言消失 | `assert-text` | `false` | `[{"kind":"text","match":"gone","expect":"..."}]` | |

**`page_ready` 布尔字段**：设为 `true` 时引擎在操作后先等待视图树稳定再截图（适用于导航到新页面的操作）。

**「开 → 看 → 关」拆分原则**（AI 手动执行）：

| 段 | 适用 action | step-type | asserts |
|---|---|---|---|
| 开 | `tap-text`（打开新页面） | `interaction` | `page_ready: true` + `[{"kind":"text","match":"present","expect":"轻量就绪标志"}]` |
| 开 | `tap-text`（当前页操作）等 | `interaction` | `[{"kind":"text","match":"present","expect":"轻量标志"}]`（**非深层内容**） |
| 看（**总是独立**） | `assert-text` | `assert` | Flow 声明的**全部**预期字段 |
| 关（仅弹窗类） | `back` | `interaction` | `[{"kind":"text","match":"gone","expect":"上一段标志文案"}]` |

**核心规则**：`step-type=interaction` 的 `asserts` 仅用页面标题等轻量标志，禁止用深层内容。深层内容放到独立的 `step-type=assert` 步骤。
### 注意事项

- **`landing_scheme` 禁止重复**：不要为第一步写 `open-url`，引擎 C2 已通过 scheme 自动跳转
- **自检**：按 `references/review-rules.md` 逐条审校 steps（R-STR → R-ACT → R-AST → R-SEM → R-PAR → R-CFL），**P0 全部通过后再执行 steps-generate**

### 模糊推定

Flow 含 `pending`/`待审校`/`以实际为准` 时：操作推定最合理文案（上下文优先→美团常识回退），标注 `"inferred": true`，asserts 全走 `kind: "visual"`。推定不违反 R-SEM-001。

## 四、命令一览

`step` 命令的 `--help` 会列出每个 action 子命令及其必填参数（数据源 `ACTION_SPECS`，与运行时前置校验规则强一致，参数缺失会在写入任何状态前直接报错并给出标准用法，不占用 SID）。本节只做命令分类导航，不重复列参数。**阶段 1 中 AI 不应手动构造命令，直接执行 `flow-next` 返回的指令即可。**

- **Flow 转换与审校**：`flow-convert`（轻量模式：解析 Flow .md 元数据，供 AI 写步骤参考） `cases-create`（创建空 CASES 文件，写内容前必须先执行） `steps-generate`（接收 AI 编写的 CASES JSON，完成 sid 编号/校验/占位符替换，输出 steps-input.json）
- **交互与断言**：`screenshot`（`--out` 为纯文件名时归档到当前 Case 的 `frames/`；为路径时按原路径） `open-url` `tap-text` `tap` `scroll-until` `scroll-edge` `input-text` `blur-input` `assert-multi` `swipe` `dismiss-recce`（`assert-text` 合并至 `step assert-text`）
- **元素定位**：`find-text --text <文案>` `find-icon --anchor <邻近文案>` `find-input --anchor <邻近文案>` `probe-status` `inspect-tree`
- **Flow 引擎驱动**：`step` `log-record` `override-step-result` `assert-fields`（API/Track 字段判定；埋点多候选用 `--picked <序号>` 消歧） `response-search`（API 响应按需视图：`--skeleton` 结构总览 / `--query` 关键字定位 / `--path` 精确取值） `flow-init` `flow-status`（`--sid <SID>` 查单步精简详情）`flow-case-status` `flow-next` `flow-advance` `hook-info`（`--hook-id <ID> [--sid <SID>]` 按需查询单个 hook 的完整操作指引）`ack` `skip-case` `flow-fail` `flow-finalize` `gen-report`
- **异常终止**：`report-error`（异常终止收尾前调用，上报 AI 分析结论和解决方案）
- **环境与设备**：`check-deps` `preflight-clean` `post-clean` `install-app` `force-stop` `launch` `set-location` `mock` `mock-snapshot` `mock-restore` `device-required` `env-required` `env-prepare` `validate` `case-init`

以下是 `--help` 之外仍需要说明的行为语义（不属于参数，`--help` 不会体现）：
- `back` 是 Flow action，单独执行用 `step back`。
- `step` 的独立操作（不绑定声明步骤）若未提供 `--desc`，引擎按 action + 参数自动派生描述，不会写入 desc 为空的孤立记录。
- `dismiss-recce` 检测并拖离 Recce 调试浮层（`tap-text` 遇遮挡时自动调用，也可手动使用）。
- `log-record / override-step-result --img` 可指定已有截图（`frames/` 下的文件名；不传时自动截当前画面并归档到 `frames/`）。同一 SID 的多条记录截图会在报告层自动合并，任一记录有图即不丢图。
- `log-record` 是唯一能写「无判定备注」的入口：传 `--note` 且不带 `--pass/--fail/--ok` → 记录 `ok=None`，带 `--sid` 归步骤 `annotations`、不带则归 Case `notes`，均不计入通过/失败统计。
- **hook 指引按需查询**：hook 的完整操作指引（cli_hint）不再随 `step` / `flow-next` 输出全量打印，flow-context 中只存 `id/hint_params`。AI 需要完整指引时执行 `hook-info --hook-id <ID> --sid <SID>` 现场渲染；`flow-next` 和步骤执行完成后的 `[AI_CHECKLIST]` 输出只给 hook id + 一行摘要 + 查询/标记命令。

## 五、异常处理

0. **异常终止闭环**：运行时异常已由引擎自动写入时间线，随报告入库，无需手动处理。**平台级归因诊断的唯一上报入口是 `report-error`**，由 AI 在异常终止收尾前调用。异常终止时按 3 步闭环：
   **第 1 步 — 分析原因**：结合日志、执行产物、Skill 实现代码，定位失败根因。
   **第 2 步 — 给出方案**：向用户说明失败原因和解决方案。
   **第 3 步 — 上报诊断**：收尾前调用 `python3 scripts/cli.py report-error --help` 查看参数并上报。

1. **断言**：`kind: "text"` 断言先由引擎做程序化判定 —— 精确匹配 → `pass/exact`；`expect` 与页面节点文案互为子串且**形态唯一** → `pass/semantic`（如 `expect`「没有更多了」/ 页面「- 没有更多了 -」）。两者都不成立才构建元素目录交 AI 语义确认，逐条按 **断言 id（A1/A2…）** 判定；`kind: "visual"` 用于纯视觉判断，可配 `targets` 拆开多条硬性验收点；`match: "gone"` 用于排除异常值（如 `{"kind":"text","match":"gone","expect":"https"}`），引擎会同时确认文本未以子串形态残留。判定口径与写回命令由 hook 提示给出（`hook-info`）。`step-type=assert` 步骤必须提供至少一项断言，否则 `flow-init` 报错。
   - action 文案口径差异（TEXT_NOT_FOUND）只记备注，既不判失败也不额外记一条 PASS：`log-record --desc "<摘要>" --note "<口径差异说明>"`（不带 `--pass/--fail/--ok` → 写一条无判定 note，归入 Case `notes` 或步骤 `annotations`，不计入统计）。
   - 一个步骤只写一次 `--assert-verdict`，同时覆盖 `verify_text_assertion` 与 `verify_text_visual_recheck`。

3. **设备创建失败**：云模拟器失败=基础设施不可用，**直接终止**（不重试不换参数），按第 0 条 3 步闭环。本地真机异常若带 `guidance` 则按步骤引导重试。

4. **本地真机安装/信任弹窗**：`local` 未安装 App 时自动补装（鸿蒙约 2-3 分钟），`important_notices` **原样转述给用户**。鸿蒙首次启动被"企业应用未受信任"拦截时，`device setup` 会暂停并携带 `guidance`：引导用户手动信任后重试，不要判为不可恢复。

5. **测试数据变更**：先用 Flow 原始参数完成首次落地验证，确认链路健康后再切换用户指定数据。

6. **感知通道适用范围**：文本断言与元素定位走探针链。视图树由 App 端按页面注入 dump 能力，业务容器页（MRN / Recce / Mach / 动态布局）可用；首页（MainActivity）未注入，`inspect-tree` 必然超时，须改用截图或 Activity 焦点判断。

7. **元素定位按目标选命令**：有文案用 `find-text --text <文案>`（直接返回坐标）；无文案图标（箭头、小人、步进器）用 `find-icon --anchor <邻近文案>`（返回结构邻域树，结合兄弟节点文案判断点哪个 `clickable`，其 `tap` 字段即坐标）；输入框用 `find-input --anchor <邻近文案>`（挑出 EditText 的 `tap` 坐标与 `text`）。`tap` 坐标必须来自以上命令或截图取证。`inspect_tree.json` 是嵌套 `exportedProperties` 结构，**禁止自行写脚本解析**（直读顶层字段全为空，得「页面无节点」假象）。

8. **WebView（H5）页面元素定位**：WebView DOM 由 Chromium 绘制，不向 Android View 树注册子节点，`inspect-tree`/`find-icon`/`find-input` 读不到其内部元素（正常现象）。规律：`find-text` 已接入探针链，native 未命中自动回退查 WebView DOM（命中标注 `[webview]`）；`find-icon`/`find-input` 依赖 native 树，WebView 不可用（提示改用 `find-text` + `tap --x --y`）；排查首选 `probe-status` 确认探针选中的页面。

9. **滚动未命中（SCROLL_TARGET_NOT_FOUND）**：引擎先精确/子串定位，均未命中才盲滑搜索；一旦滑动后页面内容无变化（已到边界/加载完）立即停止，不再跑满 5 次。hook 会同时给出截图与元素目录 —— **重试必须用目录里匹配到的真实节点文案**，拿原目标文案原样重试必然再失败。

## 六、产物

T2 阶段 `flow-finalize` 将 `.run/` 整目录归档到 `output/run-<ts>/run/`，随后 `post-clean` 清空 `.run/`。`output/` 保留 report.json（批次/Case 报告）、frames/（截图 S3 URL）和 run/（全部原始执行产物）供数据分析。批量报告必须包含全部声明的 Case，缺失则 `run_status: incomplete`。

Case 报告中 `steps` 是已声明步骤结论，`findings` 是未绑定步骤的独立判定（同权计入 `summary`），`notes` 是无判定的备注。任何 fail 都会使 Case 状态为 failed、批次 `batch_summary.failed_cases` 计数，不存在"有失败但显示全绿"的情况。

## 七、时间线记录

`record-event` 用于向 `audit/run-events.jsonl` 记录 AI 分析过程（读图、重试、环境诊断等）。传 `--evidence-type` 即按证据格式记录，详情见 `--help`。