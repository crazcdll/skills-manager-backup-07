# AI UI Autotest Engine — 技术架构文档

## 一、Skill 是什么

ai-ui-autotest-engine 是一个 AI 驱动的移动端 UI 自动化测试 Skill。它通过 CatPaw Agent 读取人工编写的测试 Flow（Markdown），自动完成云真机设备创建、App 安装登录、页面操作走查、截图断言、证据归档和测试报告生成的全流程。

整个系统的核心思想是**人机协作**：Python 引擎负责"机械性"工作（设备管理、SOP 推进、截图、视图树采集、步骤状态跟踪），AI 负责"智能性"工作（理解 Flow 语义、生成测试用例、视觉判断截图、处理异常决策）。

### 适用范围

当前支持 Android（Sandbox 云模拟器 + 本地 ADB 真机）与 HarmonyOS（本地 HDC 真机）双平台，覆盖美团 App 的 Native/MRN/H5 容器页面测试。测试类型包含 UI 功能走查、文案断言、弹窗交互验证、埋点数据校验和业务接口校验。

## 二、整体架构

系统分为五层，从上到下依次是：AI 协作层、Flow 引擎层、设备交互层、基础设施层和外部服务层。

```
┌─────────────────────────────────────────────────────────────────┐
│  AI 协作层 (CatPaw Agent)                                       │
│  读 Flow → 生成 steps-input.json → 视觉判断 → 异常决策         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ CLI 调用
┌──────────────────────────▼──────────────────────────────────────┐
│  Flow 引擎层                                                    │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │
│  │ flow_init│ │stage_orchest.│ │step_scheduler│ │flow_context│ │
│  │ 初始化   │ │ SOP 阶段编排 │ │ 步骤调度+Hook │ │ 状态读写   │ │
│  └──────────┘ └──────────────┘ └──────────────┘ └────────────┘ │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │ sop_defs │ │runtime_audit │ │ report/*     │               │
│  │ 阶段声明 │ │ 审计日志     │ │ 报告构建     │               │
│  └──────────┘ └──────────────┘ └──────────────┘               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 调用
┌──────────────────────────▼──────────────────────────────────────┐
│  设备交互层                                                      │
│  ┌────────────────┐ ┌────────────┐ ┌──────────────────────────┐ │
│  │ actions/*      │ │ screen_state/│ │ environment/*            │ │
│  │ 点击/滚动/截图 │ │ 探针链调度 │ │ 登录/环境切换/锁包       │ │
│  │ 断言/文本输入  │ │ 元素定位   │ │                          │ │
│  └────────────────┘ └─────┬──────┘ └──────────────────────────┘ │
│  ┌────────────────┐ ┌─────▼───────────────────────────────────┐ │
│  │ mock/*         │ │ device_platform/* 四维抽象（注册表驱动分发）    │ │
│  │ AppMock 规则   │ │ android/harmony 各自 ops+App 描述符      │ │
│  │ 录制/泳道/域名 │ │ probes: NativeProbe │ │
│  └────────────────┘ └─────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 调用
┌──────────────────────────▼──────────────────────────────────────┐
│  基础设施层                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐       │
│  │ adb.py   │ │ hdc.py   │ │ sandbox_api  │ │session.py│       │
│  │ ADB 命令 │ │ HDC 命令 │ │ 云模拟器 API │ │imeituan  │       │
│  └──────────┘ └──────────┘ └──────────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────────┐                                  │
│  │node_env  │ │ check_deps   │ │ app_installer（跨平台安装卸载）│ │
│  │Node 环境 │ │ 依赖检测     │ │                                │ │
│  └──────────┘ └──────────────┘ └────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / ADB
┌──────────────────────────▼──────────────────────────────────────┐
│  外部服务层                                                      │
│  yooz-server (代理)  ←→  CatPaw Sandbox OpenAPI                 │
│  AppMock 平台        ←→  imeituan CLI                           │
│  QAHome (验证码)     ←→  ADB (设备控制)                         │
└─────────────────────────────────────────────────────────────────┘
```

## 三、目录结构

```
ai-ui-autotest-engine/
├── SKILL.md                    # Skill 使用手册（AI 阅读的操作指南）
├── docs/                       # 技术文档
│   ├── technical-design.md     # 本文档
│   ├── duo-mock-guide.md       # DUO 协议 Mock 指南
│   └── ui-quality-checklist.md # UI 质量检查规范
├── examples/                   # Flow 文件示例
│   ├── flow-01-*.md            # 各场景 Flow
│   └── flow-01-ptype-multi-step/ # 多步骤拆分示例
├── references/                 # 静态资源
│   ├── apk_sources.json        # 可测性 APK 版本配置
│   ├── ADBKeyboard.apk         # ADB 键盘输入法
│   └── templates/              # 标准生成脚本模板
├── scripts/                    # 全部 Python 脚本（约 20,800 行）
│   ├── cli.py                  # CLI 入口（薄壳，参数分发）
│   ├── gen_report.py           # 报告生成模块（cli.py gen-report 子命令委托）
│   ├── device_lifecycle.py     # 设备生命周期 CLI
│   ├── core/                   # 引擎核心（SOP 编排 + onboarding 画像注册表）
│   ├── actions/                # 设备操作与断言
│   ├── assertions/             # 埋点与接口断言解析
│   ├── context/                # 工厂层：按注册表惰性创建并缓存四维抽象实例
│   ├── environment/            # 环境准备、登录与设备前置校验/引导
│   ├── infra/                  # 基础设施（ADB/HDC/API/Session/安装）
│   ├── mock/                   # AppMock 全功能子系统
│   ├── screen_state/             # 视图树采集、元素定位与探针链调度
│   ├── device_platform/               # 四维抽象定义（base.py）与 android/harmony 实现
│   └── report/                 # 报告构建与传输
├── .config/                    # 持久配置（MIS、SSO Cookie）
├── .run/                       # 当前运行工作区（执行后清空）
└── output/                     # 历史报告与归档产物
```

## 四、核心模块详解

### 4.1 CLI 入口 — `cli.py`

整个 Skill 的唯一命令入口，纯粹的参数解析和分发层。所有操作通过 `python3 scripts/cli.py <command>` 调用。命令按依赖程度分三档：不依赖 active_case 的（check-deps、preflight-clean、device query）、只需 run_dir 的（flow-status、flow-next、flow-advance、ack）、需要设备已创建的（tap-text、screenshot、step）。

### 4.2 Flow 引擎 — `core/`

这是整个 Skill 的"大脑"，负责 SOP 生命周期管理。

`core/sop/` 按职责拆分为若干小模块：`stages.py`（SOP 阶段模板：Batch 头部 B0-B3、Case 循环体、Batch 尾部 T0-T2）、`hook_templates.json` + `hook_templates.py`（Hook 模板数据与加载，改文案只动 JSON）、`on_fail.py`（失败策略与默认规则）、`hook_router.py`（按步骤结果生成 Hook）、`hook_render.py`（Hook 占位符裁剪与渲染）、`actions.py`（步骤动作契约）、`constants.py`（通用常量）。修改模板或策略只需改数据或对应的小模块，即可调整整个 SOP 流程。

`flow_init.py` 负责从 A·q   I 生成的 `steps-input.json` 初始化 `flow-context.json`，校验结构完整性，为每个 Case 展开一组 Case 循环体阶段，并创建运行目录。

`stage_orchestrator.py` 是阶段编排层，负责 SOP 阶段推进（flow-advance）、条件跳过（无 mock_ids 时跳过 B0）、门禁校验（requires_ack）和失败收口（abort/skip_to_next_case/best_effort）。

`step_scheduler.py` 是步骤调度层，负责 C3 走查阶段内的步骤级调度，管理 Hook 生命周期（pre_step → 执行 → on_pass/on_warn/on_fail），处理偏移检测和步骤锁定（已执行步骤不可重跑）。

`flow_context.py` 是数据访问层，封装 `flow-context.json` 的原子读写、条件评估和完成校验。所有状态变更都经过这一层，禁止 AI 直接编辑 JSON 文件。

`runtime_audit.py` 负责运行清单（run-manifest.json）、事件流（run-events.jsonl）和证据清单（evidence-manifest.json）的写入。

`onboarding.py` 声明 `OnboardingProfile`（按 device_type 分发的设备接入策略，回答“是否需要 acquire/版本检查/安装”等能力位组合）与 `MockLifecyclePolicy`（按 device_type 分发的 mis 账号级 AppMock 状态策略）两套接口，都通过 `_DEVICE_TYPE_PROFILE_REGISTRY` 查表分发，与 `device_platform/registry.py` 的三张注册表同构但独立维护（前者管“怎么接入”，后者管“怎么交互/获取/识别 App”）。`core/sop/stages.py`/`stage_orchestrator.py` 通过 `create_onboarding_profile(device_type).needs_device_acquire()` 等能力位方法判断阶段取舍，不再直接比较 `device_type == "local"` 字符串。

`case_cli.py`/`case_utils.py` 是 Batch 内 Case 切换与 UI 扫描命令的 CLI 入口层与共享工具函数（如 `resolve_case_path`/`resolve_mis`），`json_utils.py` 提供原子写入 JSON 的通用封装，三者均为无业务状态的纯工具模块。

### 4.3 设备交互 — `actions/` + `screen_state/`

`step_executor.py` 是步骤执行引擎，将一个声明式步骤（sid + action + assert）转换为“动作 → 等待 → 截图 → 断言 → 日志”的完整流水线。

`action_handlers.py` 实现各种 UI 动作的底层逻辑（tap-text 的视图树查找 + 坐标点击 + 上溯可点击父容器、scroll-until 的循环滚动查找、back 的返回键模拟）。

`text_input.py` 封装文本输入与清空：含 CJK 字符走 ADBKeyboard broadcast，纯 ASCII 直接调 `PlatformOps.input_text`，清空用批量退格 keyevent，输入结果统一走 inspect-tree 校验。

`api_step_executor.py`/`track_step_executor.py` 是接口断言与埋点断言的独立执行器：拉取 AppMock 录制快照 → 最新记录匹配（埋点额外做 lx0 解析 + 顶层/tag 递归匹配）→ 提取关键字段写入 `extracted_fields`（接口侧仅 query/request/meta/headers；响应体不入索引，浅骨架单独落 `diagnostics/response_skeleton_<sid>.md`，字段定位与取值走 `response-search --query/--path`），不执行程序化断言，字段级判定由 AI 通过 `assert-fields` 写入——判定结果以 `fa.field_results` 落盘（报告层唯一读取契约，经 `report/schema.build_evidence` → `report/steps._expand_field_results_to_fields` 展开为步骤 evidence 的 `api_assert.<真实路径>`），并把解析出的真实路径回写步骤 `api_assert.expected_fields`（原声明存 `declared_fields`）。

`standalone_commands.py` 提供独立的 UI 交互原语（截图、滚动、断言），供引擎和 AI 直接调用。

`screen_state/` 按职责拆分（原单文件 `inspect_tree.py`，1014 行）：`tree_source.py`（imeituan CLI 采集 + 缓存）、`tree_parse.py`（原始树 → UiNode + 几何 + 滚动裁剪）、`tree_match.py`（多级匹配 + 最佳点击目标）、`tree_neighborhood.py`（邻域结构树）、`tree_hit.py`（坐标命中 / 遮挡规避）、`tree_query.py`（对外的 find-text / find-icon / find-input / 滚动 / 文本列表查询 API）。`inspect_tree.py` 作为统一入口 facade 保持不变，对外 API 零改动。

采集走 ADB 广播 `com.mrn.VIEW_TREE_DUMP`，接收器由 App 端按页面注入，因此覆盖范围取决于页面是否注入而非渲染技术栈——业务容器页（MRN 新老架构、Recce、Mach、动态布局）及其内部原生控件均可采集；首页（MainActivity）未注入，广播 `result=0` 且不产出文件，CLI 报 `INSPECT_TREE_TIMEOUT`，需改用截图或 Activity 焦点判断。

`tree_query.py` 同时是探针链的调度入口：对外的 `inspect_tree_has_text` / `inspect_tree_find_center` 不再直接查询视图树，而是依次询问 `context.get_probes()` 返回的探针链，任一渲染层命中即返回。native 层的原始实现保留为 `native_has_text` / `native_find_center`，由 NativeProbe 调用。

`screen_state/screen_layout.py` 提供屏幕布局分析，辅助坐标计算。

### 4.4 环境管理 — `environment/`

`env_prepare.py` 是一键环境准备命令，串联 set-mis → reset-env → 登录 → 环境切换 → MRN 锁包的完整链路。

`login_strategy.py` 根据环境类型（A/B/C/D）选择登录策略：A 使用凭证登录（推送合并 Scheme），B/C 使用 QAHome 验证码登录，D 免登录（假定已登录，仅校验登录态）。

`env_validator.py` 在 flow-init 时校验环境配置的完整性（认证维度：环境类型 A-D、账号密码、MIS、ptest 开关），并在 env-required 阶段生成前置信息收集清单。

`mock/ptest_mock.py` 管理 ptest partMock 生命周期：ptest 不是环境类型，而是独立开关 `env.ptest`（线上环境 + partMock 注入 isPtest 等参数），由 `env-prepare` 在登录前独立开启，与登录方式解耦（可与 A/B/C/D 任意组合）。

`device_validator.py` 与 `env_validator.py` 职责对称且正交，校验设备维度（device_type × platform × app 组合是否已经过业务验证允许选择）。`SUPPORTED_DEVICE_COMBINATIONS` 与 `device_platform/registry.py` 三张底层注册表是“业务白名单”与“能力声明”的关系（非同一份数据的重复拷贝），两者都在 flow-init 阶段完成硬校验，报错时机提前到设备创建之前，避免非法组合跑到 device create 才失败、浪费设备资源。

`device_guidance.py` 是设备连接异常场景→用户可执行分步指引的纯数据注册表（`GUIDANCE_REGISTRY`），与 `device_validator`（组合是否受支持）、`env_validator`（认证信息是否齐备）职责正交，专注于“组合合法但设备当前不可达”时如何指导用户现场修复（如本地鸿蒙真机未连接），不包含交互/等待逻辑。

`question_utils.py` 抽取 `env_validator.py` 与 `device_validator.py` 共用的 AskQuestion 契约构造工具（known_values 预填规则），避免两处重复实现。

### 4.5 设备与渲染层抽象 — `device_platform/` + `context/`

系统使用四维抽象来解耦设备、获取方式、App 与渲染差异，四个维度相互正交，任一维度新增取值不影响其余三维与引擎逻辑：

| 维度 | 回答什么问题 | 取值 | 当前实现 |
|------|------------|------|---------|
| `PlatformOps` | 怎么与设备交互 | **android** / **harmony** / ios | AndroidOps、HarmonyOps |
| `DeviceLifecycle` | 怎么获取释放设备 | **sandbox**（仅 android）/ **local**（android+harmony）/ cloud_device | SandboxDeviceLifecycle、LocalDeviceLifecycle |
| `AppDescriptor` | 目标 App 是什么 | **meituan@android** / **meituan@harmony** / dianping | MeituanAppDescriptor、MeituanHarmonyAppDescriptor |
| `RendererProbe` | 探针名称标识 | **native** | NativeProbe |

粗体取值为已实现，其余为接口已预留、待补实现。每个维度均由 `device_platform/registry.py` 中的注册表驱动分发，不存在任何 `if/elif platform` 或 `if/elif device_type` 的散落分支：

- `_PLATFORM_MODULES`：platform → ops 模块路径。`get_platform_module(platform)` 惰性加载并在首次加载时用 `_verify_module_contract` 强制校验模块契约（`_REQUIRED_MODULE_ATTRS` 声明的类/函数签名），缺失即在导入阶段报 `PlatformModuleContractError`（早失败），不会拖到运行时某个深层调用点才报 `AttributeError`。
- `_DEVICE_TYPE_REGISTRY`：device_type → (DeviceLifecycle 实现类路径, 支持的 platform 集合)。`get_supported_platforms()`/`is_device_platform_supported()` 供 `device_validator` 派生合法组合表；`get_device_lifecycle_class()` 供 `context.create_device_lifecycle` 分发实例化。
- `_APP_REGISTRY`：(app, platform) 二元组 → AppDescriptor 实现类路径。App 与 Platform 不正交（同一个 App 在不同 OS 上是完全独立安装包），因此用二元组做键；未注册的组合直接报错，不静默回退。

`PlatformOps`（`device_platform/interfaces/platform_ops.py` 抽象基类）定义设备操作接口（截图、点击、滚动、inspect-tree、屏幕电源状态等），当前实现为 `AndroidOps`（`device_platform/android/ops.py`，交互操作全部委托 `infra/imeituan_cli.py` 执行 imeituan CLI 命令）和 `HarmonyOps`（`device_platform/harmony/ops.py`，交互操作直接拼接 `hdc shell` 命令执行，仅 session 注册走 `infra/imeituan_cli.py::imeituan_connect_local_device`）。`infra/imeituan_cli.py` 是三端（Android/iOS/Harmony）通用的 CLI 封装层（内部通过 Session 机制路由到 AdbAdapter/XcrunAdapter/HdcAdapter），因此归属 `infra/` 而非某个平台目录；`device_platform/harmony/hdc.py` 则是 hdc 二进制探测与 PATH 准备的平台专属工具。

`DeviceLifecycle`（`device_platform/interfaces/lifecycle.py` 抽象基类）定义设备生命周期接口（acquire/release/install_app/query_user_devices），当前实现为 `SandboxDeviceLifecycle`（`device_platform/lifecycle/sandbox.py`，云模拟器，依赖 yooz-server API，目前仅 Android 镜像）和 `LocalDeviceLifecycle`（`device_platform/lifecycle/local.py`，本地真机，跨平台通用，内部按 `get_platform_module(platform)` 分发 `probe_local_devices`）。

`AppDescriptor`（`device_platform/interfaces/app_descriptor.py` 抽象基类）封装宿主 App 的包名、Activity/Ability、testability scheme 前缀、调试控件类名等元数据，同时承载 app 和 platform 两个维度信息。当前实现为 `device_platform/android/apps/meituan.py::MeituanAppDescriptor` 和 `device_platform/harmony/apps/meituan.py::MeituanHarmonyAppDescriptor`。新增 App 时需在 `device_platform/<platform>/apps/` 下补实现并注册到 `_APP_REGISTRY`，同时同步补齐 `login_strategy.py`/`env_validator.py`/`device_validator.py` 三处（各自独立维护但语义对齐："未注册即不可用"），规则已内置于各 `*-required` 命令的 AI 引导提示中。

`RendererProbe`（`device_platform/interfaces/renderer_probe.py` 抽象基类）定义渲染层感知探针接口（find_text/find_center/list_texts/probe_name），通过 `probe_name` 属性标识当前使用的探针类型，用于日志与证据标注。`NativeProbe` 覆盖各平台原生视图树（Android View 体系含 MRN、Recce；HarmonyOS ArkUI 组件树），其 `probe_name` 恒为 `"native"`。

`context/__init__.py` 是工厂层，根据 flow-context.json 中的 device_type/platform/app 字段，通过上述三张注册表分发创建对应实例，并做惰性初始化与缓存。`get_probes()` 返回探针链：native 恒在链首。

### 4.6 AppMock 子系统 — `mock/`

AppMock 是美团客户端测试的核心基础设施，本 Skill 对其进行了全功能封装：

`appmock_core.py` 实现核心 HTTP 调用（经 yooz-server 代理），所有 Mock 操作走统一的请求层。`appmock_rules.py` 封装规则 CRUD 和字段级补丁（patch-field），支持 DUO 协议的 nodeDataMap 精准修改。`appmock_record.py` 拉取接口录制数据并做噪音过滤（排除 lx0 埋点、CDN 等非业务域名）。`appmock_swimlane.py` 管理泳道代理。`appmock_session.py` 管理 SSO Cookie 和域名映射。`appmock_device.py` 管理设备端 Mock SDK 开关。`appmock_ops.py` 承载被 CLI 层与业务层共同复用的编排操作（可测性 Scheme 推送、环境重置、ptest mockId 持久化），使 `appmock_env_cli.py`、`ptest_mock.py`、`env_prepare.py`、`login_password.py` 无需反向依赖 CLI 模块，从根源上避免 `appmock_cli ↔ appmock_env_cli` 的模块级循环依赖。`appmock_env_cli.py` 从 `appmock_cli.py` 拆出，专注泳道管理、域名映射、MRN 锁包等环境配置类子命令；`appmock_cli.py` 本身保留规则 CRUD、录制和 CLI 分发入口。`mock_baseline.py` 负责 Mock 基线快照和回滚（B0 拍快照 → C5 Case 间回滚 → T0 Batch 级回滚）。

### 4.7 报告子系统 — `report/`

`data_collector.py` 从 Case workspace 的 `steps.jsonl` 读取原始执行事实。`model.py` 将同 SID 的多条记录归一化为 conclusion/executions 模型：`conclusion` 按 `followup > retry > step` 优先级选取终态记录（`retry` 是重试步骤如 `S2b` 写入父 SID `S2` 的记录，优先于原始 `step` 但低于显式 `followup`），`executions` 包含全部执行记录（step + followup + retry）供 `coalesce_evidence` 取值（取第一个非空值）。报告构建按职责拆为纯函数模块：`steps.py`（步骤级投影）/ `timeline.py`（时间线）/ `case_report.py`（单 Case）/ `run_report.py`（批次）/ `timefmt.py`（时间工具），文件读取统一走 `data_collector.py`。基于 conclusion 投影 Case 与 Batch 报告，`coalesce_evidence(executions, field, default)` 从所有 executions 中按优先级提取证据字段。`finalizer.py` 负责最终归档和落盘。`transport.py` 负责截图上传 S3（扫描 `frames/`）和平台入库。`schema.py` 定义报告数据结构；`core/util/records.py` 定义 `StepRecord` 单一写入契约（所有写入端统一构造，截图以 `screenshots` 数组承载）。截图由 `merge_screenshots(executions)` 跨同一 SID 的全部执行记录合并，conclusion 缺图时自动补齐。

统计口径的核心不变量：携带判定（ok 非空）的记录一律进入统计。findings 中存在 fail 时 Case 不得判为 completed。

### 4.8 基础设施 — `infra/`

`sandbox_api.py` 封装所有 Sandbox 云模拟器 API 调用（经 yooz-server 代理，API Key 由服务端持有）。设备创建采用异步模式：POST create 立即返回 taskId，Skill 自行轮询 GET status 直到 state=running。

`session.py` 管理 imeituan CLI 的设备会话（注册/断开），内部通过 `get_platform_module(platform).register_device()` 分发到各平台的注册入口（云真机走 `device register`，本地真机走 `device connect --target local-device`），跨 Android/HarmonyOS 通用，不感知平台细节。`imeituan_cli.py`（三端通用封装层，见 4.5 节）也位于本目录。`app_installer.py` 负责 App 的版本检测、卸载、安装和验证，内部通过 `PlatformOps`/`DeviceLifecycle` 调用，跨 Android/HarmonyOS 通用。`adb.py` 封装 ADB 命令执行（Android），`hdc.py`（位于 `device_platform/harmony/`）封装 hdc 二进制探测与 PATH 准备（HarmonyOS）。`check_deps.py` 检测运行时依赖（Python、Node、imeituan CLI、adb/hdc、SSO Cookie，按当前 platform 按需检测对应工具链）。`node_env.py` 管理 Node.js 环境和 imeituan CLI 执行器。

## 五、SOP 生命周期

一次完整的测试执行分为 Batch 头部、Case 循环体和 Batch 尾部三段，共 16+ 个阶段。

### Batch 头部（B0-B3）— 执行一次

B0 是 Mock 基线快照，仅在 steps-input.json 声明了 mock_ids 时执行，在所有修改前捕获预设 Mock 规则的真实状态，用于后续回滚。

B2 是设备获取，执行 device create（异步创建云模拟器） + device setup（注册 session、安装可测性 APK、处理隐私弹窗、配置 ADB Keyboard）。

B3 是环境登录，执行 env-prepare 一键完成 set-mis → reset-env → ptest mock（可选）→ 登录 → 泳道/域名映射切换 → MRN 锁包。凭证登录需 AI 读截图确认结果。

B4 是启用预设 Mock 规则，在 B3 的 reset-env 之后执行（避免被 stop-all 覆盖）。

### Case 循环体（C0/C1/C2/C3/C4/C5）— 每个 Case 重复

C0 切换到目标 Case。C1 启动接口录制。C2 通过 Scheme 跳转到目标落地页，AI 读截图确认（如 Recce 浮层遮挡可手动调 dismiss-recce）。C3 是统一多步走查，引擎按 steps 顺序逐步执行 step 命令，通过 `kind` 字段区分步骤类型：`ui`（UI 交互，动作 → 截图 → 断言，tap-text 遇 Recce 遮挡会自动处理）、`api`（接口字段验证，从录制数据中匹配并断言）、`track`（埋点字段验证，从录制数据中匹配并断言）。三种步骤的结果统一写入 steps.jsonl，不再需要独立的批量断言阶段。C4 生成 Case 报告。C5 回滚 Case 级 Mock 响应体。

### Batch 尾部（T0-T2）— 执行一次

T0 回滚 Batch 级 Mock。T2 是收尾清理：导出录制数据 → 停止录制 → 重置环境 → 销毁设备 → flow-finalize（归档 + 入库 + 生成最终报告）→ post-clean 清空 .run 目录。

### 阶段推进机制

AI 通过 `flow-next` 获取当前应执行的命令，执行后再 `flow-next` 获取下一步。阶段间通过 `flow-advance` 推进。需要人工确认的节点（登录截图、落地页截图）通过 `ack --key <key>` 写入证据后才能继续。失败策略有四种：abort（终止流程）、skip_to_next_case（跳到下一个 Case）、log_and_continue（记录后继续）、best_effort（尽力执行）。

## 六、数据流

### 输入

Flow 文件（Markdown）→ AI 理解并生成 → steps-input.json（结构化测试用例）→ flow-init 校验并展开 → flow-context.json（运行时状态）。

### 运行时

flow-context.json 是唯一的状态控制面，分为 meta（运行元数据）、env（环境配置）、sop（SOP 阶段状态）、runtime（门禁 ack）、steps（当前 Case 步骤定义与执行状态）、cases_manifest（Case 注册表）等职责域。断言结论直接写入 steps.jsonl 的步骤记录中，不再单独维护 evidence 职责域。

steps.jsonl 是不可变的执行事实流，每个 Case workspace 一个，记录每步的动作、结果、耗时和截图资产（`screenshots` 数组，`file` 为 `frames/` 下的纯文件名）。全部写入端统一经 `StepRecord` 构造，杜绝字段漂移。

### 输出

每次运行归档到 `output/run-<timestamp>/`，包含 report.json（聚合报告）、各 Case 的 report.json 和 frames/（截图 S3 URL），以及 run/（完整原始执行产物备份）。报告同时入库到平台，可通过 URL 在线查看。

## 七、设备管理架构

### 云模拟器（Sandbox）

设备通过 CatPaw Sandbox OpenAPI 创建，经 yooz-server 代理转发。创建采用异步架构：Skill 调用 yooz-server 的 POST /sandbox/create（yooz-server 转发到 Sandbox API 后立即返回 taskId），然后 Skill 自行轮询 GET /sandbox/status（yooz-server 转发到 Sandbox API 查询任务状态），直到 state 变为 running。这种设计将轮询控制权交给调用方，避免了 yooz-server 函数超时（60s）与创建耗时（60-120s）的冲突。

设备就绪后通过 ADB（remote connect）进行操作控制，通过 imeituan CLI 进行视图树采集和 Scheme 推送。

### 本地真机

Android 通过 USB 或 WiFi ADB 连接，HarmonyOS 通过 USB HDC 连接，设备生命周期统一由 `LocalDeviceLifecycle`（`device_platform/lifecycle/local.py`，跨平台通用）管理：acquire 内部按 `get_platform_module(platform).probe_local_devices()` 分发探测唯一在线设备（探测失败抛 `LocalDeviceProbeError`，命中 `device_guidance.GUIDANCE_REGISTRY` 时输出结构化分步引导），release 为空操作。

### 四维抽象设计

PlatformOps（怎么操作设备）、DeviceLifecycle（怎么获取和释放设备）、AppDescriptor（操作什么 App）、RendererProbe（探针名称标识）四个维度相互独立，均由 `device_platform/registry.py` 的注册表（`_PLATFORM_MODULES`/`_DEVICE_TYPE_REGISTRY`/`_APP_REGISTRY`）驱动分发，`context/__init__.py` 仅作为查表后的实例化与缓存层。新增平台（如 iOS）只需：实现 `device_platform/ios/ops.py`（满足 `_REQUIRED_MODULE_ATTRS` 契约）与对应 `AppDescriptor`，在三张注册表中各追加一行，不需要改动 `context/__init__.py`/`device_lifecycle.py`/`screen_state/`/`environment/` 任何调用方代码，也不会引入新的 if/elif 分支。

渲染层维度与前三维正交：同一台 Android 设备、同一个 App 内，既可能是 MRN 页面，也可能内嵌 H5 页面；iOS 上同样存在这种分化。

## 八、当前能力与后续规划

### 已支持

| 能力 | 说明 |
|------|------|
| Android 云模拟器 | 通过 CatPaw Sandbox 自动创建/销毁（仅 Android 镜像） |
| Android 本地真机 | 通过 ADB 连接，`LocalDeviceLifecycle` 自动探测并校验唯一在线设备 |
| HarmonyOS 本地真机 | 通过 HDC 连接，同一套 `LocalDeviceLifecycle` 按 platform 分发探测，接入方式与 Android 对齐 |
| Native/MRN/H5 页面测试 | 基于 Native 视图树（Android View / HarmonyOS ArkUI）的精确元素定位 |
| 四种环境类型 | 线上(A)、泳道(B)、alpha(C)、免登录(D)；ptest 为独立开关（`env.ptest`） |
| 凭证登录 + 验证码登录 + 免登录 | A 凭证，B/C QAHome 验证码，D 免登录 |
| AppMock 全功能 | 规则 CRUD、录制、泳道、域名映射、MRN 锁包 |
| DUO 协议 Mock | nodeDataMap 组件级字段精准修改 |
| 埋点验证 | lx0 录制数据解析 + 事件匹配 + 字段提取（extracted_fields），AI 分析判定 |
| 接口验证 | 业务接口录制数据匹配 + 字段提取（query/request/meta/headers）+ 响应浅骨架文件 + `response-search` 按需检索；字段判定经 `fa.field_results` 并入步骤 evidence（`api_assert.<真实路径>`），真实路径回写声明 |
| UI 质量扫描 | 占位符/乱码、入口缺失、区域遮挡检测 |
| 多 Case 批量执行 | 一个 Flow 拆分多个 Case，循环执行 |
| Mock 基线快照与回滚 | Case 间/Batch 级精确回滚 |
| 报告入库 | 自动上传平台，可在线查看 |
| 审计追溯 | run-manifest + events + evidence 完整记录 |
| UI 质量扫描 | 占位符/乱码、入口缺失、区域遮挡检测 |

### 架构已预留但尚未实现

| 能力 | 预留方式 |
|------|----------|
| iOS 平台 | PlatformOps/DeviceLifecycle/AppDescriptor 接口已抽象，`_PLATFORM_MODULES` 等三张注册表已预留分发结构，需新增 `device_platform/ios/` 实现并注册 |
| HarmonyOS 云真机/云模拟器 | `_DEVICE_TYPE_REGISTRY`/`_APP_REGISTRY` 已声明 harmony 可用性，`sandbox` 目前仅 Android 镜像、`cloud_device` 尚未接入 lifecycle 实现，非架构限制 |
| dianping（点评）App | `_APP_REGISTRY` 尚未注册任何 (dianping, platform) 组合，登录方式/可测性通道待调研，接入流程见 `*-required` 命令内置 AI 引导提示 |
| 多设备并行 | 当前一次运行串行控制一台设备，引擎层已按 Case 隔离，可扩展为并行 |

## 九、快速上手

### 一次测试执行的最小路径

```
# 0. 保存 Flow 文件到 .run-input/flows/ 并执行依赖检测
python3 scripts/cli.py check-deps

# 1. 预检清理（清空 .run/、.config/、.run-input/ 工作区）
python3 scripts/cli.py preflight-clean

# 2. 收集设备信息（选择云模拟器/本地真机/云真机）
python3 scripts/cli.py device-required

# 3. 收集环境范围 + 认证凭证（env_type 确定后才能推断 auth_method，需分两步）
#    第1轮：收集 env_type + mis
python3 scripts/cli.py env-required --app meituan
python3 scripts/cli.py save-answers --answers '{"env_type":"<所选>","mis":"<mis>"}'
#    第2轮：env_type 已确定 → 自动推断 auth_method → 收集 credential 字段
python3 scripts/cli.py env-required --app meituan --device-type <device_type>
python3 scripts/cli.py save-answers --answers '{"account":"<手机号>","password":"<密码>"}'

# 4. 收集可选配置（ptest、锁包等）
python3 scripts/cli.py config-required --flow-source <flow-文件路径>

# 5. 解析 Flow 元数据（供 AI 写步骤参考）
python3 scripts/cli.py flow-convert --flow-source .run-input/flows/flow-{NN}-{场景简称}.md --tag {tag}

# 6. CASES 文件（强制约定）：先创建空文件 → AI 写入 → 落盘校验 → 生成 steps-input
python3 scripts/cli.py cases-create --tag {tag}
#    AI 写入完整 CASES（device/env/cases/steps），wc -c 确认非空后：
python3 scripts/cli.py steps-generate --input '.run/tmp/cases-{tag}.json' --tag {tag}

# 7. 初始化 flow-context（占位符在此解析，并固化 steps-input 为唯一事实来源；原文另存 steps-input.raw.json）
python3 scripts/cli.py flow-init --dir <run-name> --input '.run/tmp/steps-input-<tag>.json' --flow-name <name> --mis <mis>

# 8. 进入引擎驱动，按 flow-next 返回的命令逐步执行
python3 scripts/cli.py flow-next   # 获取下一步
# ... 按 flow-next 返回的指令逐条执行 ...

# 9. 收尾（flow-finalize → post-clean，由引擎 T2 阶段自动完成）
```

### 开发者扩展指南

如需新增平台支持（如 iOS），需要：新建 `device_platform/ios/ops.py`，继承 `PlatformOps` 实现设备操作接口（截图、点击等），并暴露 `device_platform/registry.py::_REQUIRED_MODULE_ATTRS` 声明的模块级契约成员（`PlatformOpsClass`/`probe_local_devices`/`ensure_toolchain`/`register_device`/`build_probes`/`parse_tree`/`FRESH_INSTALL_GUIDANCE_ID`/`INSTALL_VERIFY_RETRIES`）；在 `device_platform/ios/apps/` 下创建 `AppDescriptor` 描述目标 App 元数据；然后在 `device_platform/registry.py` 的 `_PLATFORM_MODULES`、`_DEVICE_TYPE_REGISTRY`（追加 `"ios"` 到相应 device_type 的 `platforms` 元组）、`_APP_REGISTRY` 三张注册表中各追加一行即可，`context/__init__.py`、`device_lifecycle.py`、`screen_state/`、`environment/` 等调用方均通过查表分发，无需改动，也不会引入新的 if/elif 分支。契约缺失会在 `get_platform_module()` 首次加载时以 `PlatformModuleContractError` 早失败报出。

如需新增设备获取方式（如云真机 `cloud_device` 正式接入），只需实现对应 `DeviceLifecycle`（放在 `device_platform/lifecycle/` 跨平台通用位置，或确有平台专属逻辑时放 `device_platform/<platform>/lifecycle/`），在 `_DEVICE_TYPE_REGISTRY` 补齐 `module`/`class_name`，`context.create_device_lifecycle` 会自动分发。

如需新增 App（如点评），需在 `device_platform/<platform>/apps/` 下实现 `AppDescriptor` 并注册到 `_APP_REGISTRY`，同时同步补齐 `login_strategy.py`（登录策略）、`env_validator.py`（认证信息校验）、`device_validator.py`（组合合法性）三处——三张表各自独立维护但语义对齐："未注册即不可用"，规则已内置于各 `*-required` 命令的 AI 引导提示中。

如需新增 Mock 能力（如新的代理平台），在 `mock/` 目录下新增实现模块，并在 `appmock_cli.py`（规则/录制类）或 `appmock_env_cli.py`（环境配置类）的分发表中注册子命令；被多方复用的业务编排逻辑下沉到 `appmock_ops.py`，避免两个 CLI 模块互相依赖。

如需新增步骤动作（如 long-press），在 `core/sop/actions.py` 的 `STEP_ACTIONS` 中注册，在 `action_handlers.py` 中实现处理逻辑，在 `cli.py` 中添加 CLI 参数。

## 附录：多 App 支持下的架构演进

### 当前架构（仅美团）

三层分治，每层一个注册表作为扩展点：

| 层 | 文件 | 注册表 | 职责 |
|---|---|---|---|
| 设备 | `device_validator.py` | `SUPPORTED_DEVICE_COMBINATIONS` | 设备×平台×App 组合校验 |
| 环境类型 | `env_validator.py` | `APP_ENV_TYPE_RULES[app]` | 各 App 的 ABCD 环境类型定义 |
| 认证规则 | `auth_validator.py` | `AUTH_METHOD_RULES[app]` | 各 App 的认证方式定义、字段规则 |
| 登录策略 | `login_strategy.py` | `APP_LOGIN_STRATEGY_BUILDERS[app]` | 各 App 的登录策略实现 |

新增 App 时，上述四处注册表各追加一条，框架逻辑不改。

### 未来演进方向（第二个 App 出现时）

当支持第二个 App（如 dianping）时，`environment/` 目录会面临职责密度上升：

```
environment/
├── env_validator.py      ← 框架逻辑 + 美团规则 + 点评规则 混在一起
├── login_strategy.py     ← 策略基类 + 美团策略 + 点评策略 混在一起
```

建议按 **App 维度**拆分，将认证规则与登录策略从 `env_validator.py`/`login_strategy.py` 中独立出去：

```
environment/
├── __init__.py
├── question_utils.py          ← 共享：known_values 工具
├── device_validator.py        ← 共享：设备组合校验
├── device_guidance.py         ← 共享：设备引导
├── env_prepare.py             ← 共享：环境准备编排
├── env_validator.py           ← 共享：框架逻辑（问题构建、配置校验、摘要）
├── rules/                     ← 按 App 分派的认证规则
│   ├── __init__.py
│   ├── _meituan.py            ← 美团认证规则
│   └── _dianping.py           ← 点评认证规则
├── strategies/                ← 按 App 分派的登录策略
│   ├── __init__.py
│   ├── _meituan.py            ← 美团登录策略
│   └── _dianping.py           ← 点评登录策略
└── login_*.py                 ← 共享：登录原语（已按职责拆分）
                                  app_lifecycle / sdk_enable / login_sms / login_qahome
                                  login_password / login_state / location
```

`env_validator.py` 保留框架逻辑（`get_required_fields`、`validate_env_config`、`get_env_summary`），`APP_ENV_TYPE_RULES` 注册表改为从 `rules/` 目录自动发现。`auth_validator.py` 保留框架逻辑（`get_auth_required_fields`、`validate_auth_config`），`AUTH_METHOD_RULES` 注册表改为从 `auth_rules/` 目录自动发现。`login_strategy.py` 保留框架逻辑（`build_login_strategy`），`APP_LOGIN_STRATEGY_BUILDERS` 改为从 `strategies/` 目录自动发现。

**拆分原则**：不提前拆分，等第二个 App 确实出现时再重构，避免过度设计。
