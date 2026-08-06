---
name: trade-page-modal-audit
description: >-
  梳理交易前端 MRN/Max 页面中所有弹窗（Modal/Dialog/Popup/SlideModal/Sheet/Overlay/Alert/ActionSheet 等），
  输出结构化表格并保存为学城文档。当用户说梳理弹窗、弹窗审计、整理弹窗、弹窗盘点、modal audit 时触发。
  需要提供：页面目录路径、mis 号。文档固定保存到父文档 2753311082 下。
---

# 交易前端页面弹窗梳理 Skill

梳理指定交易前端 MRN/Max 页面中的所有弹窗/浮层组件，生成结构化文档并保存到学城。

## 必要参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `pageDir` | 页面根目录的相对或绝对路径 | `hotelchannel-order-detail` |
| `mis` | 学城认证用的 mis 号 | `zhangce07` |
| `docTitle` | 文档标题（可选，默认：`{页面名}-弹窗梳理`） | `境内单详-弹窗梳理` |

**`parentId` 固定为 `2753311082`**，无需用户输入，所有弹窗梳理文档统一保存到该父文档下。

缺少 `pageDir` 或 `mis` 时向用户索取，不要猜测。

## 工作流程

### Phase 1：环境准备与计时

1. 创建临时计时文件，记录 T1：
   ```bash
   TIMER_FILE="/tmp/modal-audit-timer-$(date +%s).txt"
   echo "T1=$(date '+%Y-%m-%d %H:%M:%S')" > "$TIMER_FILE"
   echo "$TIMER_FILE"
   ```
   后续所有 phase 都使用这个 `$TIMER_FILE` 路径来追加时间。
2. 确保 Node.js >= 18（oa-skills 依赖 `fetch`，Node 16 会报 `ReferenceError: fetch is not defined`）：
   ```bash
   export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use 18
   ```
3. 确保 `@it/oa-skills` 已安装且最新：
   ```bash
   npm list -g @it/oa-skills --depth=0 --registry=http://r.npm.sankuai.com 2>/dev/null | grep oa-skills
   npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com
   ```

### Phase 2：定位页面结构

1. 确认 `pageDir` 存在，读取 `package.json` 获取页面名称。
2. 找到页面入口文件（`index.tsx` / `index.ts`）和主页面组件（通常在 `src/pages/` 下）。
3. 读取 `src/App.tsx` 和路由文件（`src/routers.tsx`），确认 App 级弹窗（如 TopViewProvider、ToastManager 等基础设施组件不计入业务弹窗）。

### Phase 3：三轮搜索弹窗（使用 subagent 并行加速）

分三轮执行，**每轮尽量使用 subagent 并行处理**以提速和提升准确度。

#### 第一轮：广度搜索

主 agent 直接执行以下搜索（利用 Grep/Glob 等工具的并行调用能力）：

1. **读取主页面组件**（如 `*Page.tsx`），提取 render 方法中所有 Modal/Dialog/Popup/Sheet/Overlay 类 JSX 标签。
2. 记录 state/ref 中控制弹窗可见性的变量（`visible`、`show`、`isShow`、`open`、`modalVisible` 等）。
3. 记录命令式调用（`Dialog.open`、`Dialog.alert`、`Alert.alert`、`msi.showModal`、`msi.showActionSheet`、`Questionnaire.open`、`KNB.confirm` 等）。
4. 列出 `src/components/` 和 `src/new_components/` 下**所有子目录**（不要只看名字带 Modal 的）。
5. 在 `src/` 下搜索以下关键词（正则合并搜索提效）：
   `Modal|Dialog|Popup|SlideModal|BottomSheet|ActionSheet|Overlay|Drawer|Panel|Sheet|Alert|Toast|Confirm|Prompt|Cover|Layer|Mask`
6. 搜索外部弹窗库导入：
   - `@mrn/react-native` 的 `Modal`、`Alert`
   - `@ss/mtd-react-native` 的 `Dialog`、`SlideModal`、`Modal`、`Loading`
   - `react-native-modal`
   - `@max/leez-slide-modal`、`@max/leez-modal-base-container`
   - `@mtfe/msi-mrn`（`showModal`、`showActionSheet`）
   - `@mrn/hotel-aura`（`CouponDialog`）
   - `@mrn/hotel-questionnaire`
   - 其他项目特有的弹窗库

#### 第二轮：深度验证（subagent 并行）

根据第一轮搜索结果，将待分析文件**按区域拆分为 2-4 组**，每组启动一个 `explore` subagent 并行处理。

**拆分策略**（根据文件数量灵活调整，每个 subagent 分配 10-20 个文件）：

- **Subagent A**：`new_components/` 下所有弹窗相关文件（Dialog 目录、OrderStatus 区域、PriceDetail 区域等）
- **Subagent B**：`components/` 下所有弹窗相关文件 + 子页面（cancel、resendMail、voucher 等路由页面）
- **Subagent C**（可选，文件多时启用）：外部 npm 组件的 props 分析 + 会员/营销等独立模块

每个 subagent 的 prompt 必须包含：
1. 完整的文件路径列表
2. 明确的分析要求：组件名、底层库来源、触发机制、功能描述、展示形式
3. 要求返回结构化表格

**subagent 调用示例：**
```
Task(subagent_type="explore", prompt="Read and analyze the following files for modal/dialog/popup components... [文件列表]. For each file, identify: 1) modal component name and library source, 2) trigger mechanism (state/ref/imperative), 3) brief function description, 4) display form. Return a structured table.")
```

**关键：多个 subagent 必须在同一条消息中发起**，确保真正并行执行。

对每个 subagent 返回的组件做递归展开：
- **容器型弹窗组件**（如 `*ModalView*`）：读取源码，列出其内嵌的所有子弹窗。
- **区域组件**（Header、Bottom、Promotion、OrderInfo、Voucher 等）：逐个检查内部是否包含弹窗，**不要只看名字**，要看实际代码。
- **外部 npm 组件**：检查其 props 是否含 `onDialogShow`、`onModalClose`、`visible`、`onShow`、`onClose` 等暗示内部有弹窗的回调。

#### 第三轮：交叉校验与下线检测

主 agent 汇总前两轮结果后执行（可并行多个 Grep 调用）：

- 用 `visible|isVisible|show|isShow|modalVisible|slideModalVisible` 在 `src/` 下搜索，确认没有遗漏的弹窗状态变量。
- 对照 `src/components/` 目录列表，确认每个子目录都已检查过。
- **下线检测**：对每个发现的弹窗组件文件，检查是否仍被页面引用链路引用。判定方式：
  1. 在 `src/` 下搜索该组件的 import 语句或 require 调用。
  2. 如果**无任何文件 import 该组件**，或者 import 它的文件本身也未被引用（孤立文件），标记为"可能已下线"。
  3. 如果组件在 JSX 中被**注释掉**或对应的渲染代码被注释，同样标记为"可能已下线"。
  4. 如果组件存在但当前页面已切换到新版本组件（如 V1 → V2），旧版标记为"可能已下线"。

### Phase 4：整理弹窗表格，记录 T2

对每个弹窗组件，收集以下信息并按区域分组：

| 列 | 说明 |
|----|------|
| 弹窗组件名 | 组件名或 API 名 |
| 弹窗含义 | 简短名称（≤6 字）；若弹窗文件无引用或已被注释，追加"**（可能已下线）**" |
| 展示形式 | 全屏 / 半屏 / 居中 / 底部 / 气泡 / 浮层 / 系统弹窗 |
| 弹窗功能 | 一句话描述功能 |
| 代码位置 | 所有相关文件的相对路径，外部组件给 npm 包名，不能省略 |
| 当前截图 | 留空 |
| 是否适配 | 留空 |
| 适配后截图 | 留空 |

**分组规则**（按实际页面结构灵活调整）：
1. 页面级弹窗（主页面 render 中直接渲染的）
2. 嵌套容器弹窗（容器组件内部的子弹窗）
3. 各区域弹窗（Header、ActionButton、Promotion、OrderInfo 等）
4. 命令式弹窗（通过 API 调用触发的，如 Dialog.open、Alert.alert）
5. 外部组件弹窗（npm 包内实现，标注"可能含弹窗"并说明判断依据）

**末尾附加两个汇总表：**

**底层弹窗库汇总表**：底层库 / 类型 / 使用的组件列表

**废弃/未挂载组件备注表**（如有）：组件名 / 文件路径 / 未挂载原因。这些组件的弹窗含义列统一标注"**（可能已下线）**"

记录 T2 到临时文件：
```bash
echo "T2=$(date '+%Y-%m-%d %H:%M:%S')" >> "$TIMER_FILE"
```

### Phase 5：保存到学城

1. 从临时文件读取 T1、T2，计算 T2-T1。
2. 将表格内容写入临时 `.md` 文件，时间统计中 T3 及相关耗时写为"待填写"占位。
3. 创建学城文档（所有 oa-skills 命令需要 nvm use 18 前缀）：
   ```bash
   export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use 18 && \
   oa-skills citadel createDocument --title "<docTitle>" --file <tmp-file> --parentId 2753311082 --mis <mis>
   ```
4. 记录 T3：
   ```bash
   echo "T3=$(date '+%Y-%m-%d %H:%M:%S')" >> "$TIMER_FILE"
   ```
5. 从临时文件读取全部时间，计算 T3-T2 和 T3-T1。
6. 用 CitadelMD 安全更新流程回填时间：
   ```bash
   oa-skills citadel getDocumentCitadelMd --contentId <id> --output <file> --mis <mis>
   # 替换 "待填写" 为实际时间
   oa-skills citadel updateDocumentByMd --contentId <id> --file <file> --mis <mis>
   ```

### Phase 6：输出结果

向用户汇报：
- 学城文档链接
- 弹窗总数及分类统计
- T1 / T2 / T3 及耗时明细
- 临时计时文件路径（供用户核实）

## 弹窗分类参考

| 展示形式 | 典型底层实现 |
|----------|-------------|
| 全屏 | RN `Modal`、MTD `Modal` |
| 居中 | MTD `Dialog`、`Dialog.alert`、`Alert.alert` |
| 半屏/底部 | MTD `SlideModal`、Leez `SlideModal`、`react-native-modal`、`BottomSheet` |
| 系统弹窗 | `msi.showModal`、`msi.showActionSheet`、`KNB.confirm` |
| 气泡/浮层 | 绝对定位 + 蒙层（引导气泡、客服引导等） |
| 全屏覆盖 | 动效覆盖层、欢迎动画等 |
| 加载态 | `Loading`、`SkeletonDrawer`（可视实际需要决定是否计入） |
| 命令式 | `Dialog.open`、`Questionnaire.open`、`Toast.open` |

## 注意事项

- 搜索必须覆盖 `src/` 下所有 `.tsx` / `.ts` 文件，每个 `src/components/` 子目录都要检查。
- **不要只看组件名**：名字不含 Modal 的组件（如 Voucher、Promotion 子组件）也可能内含弹窗。
- 外部 npm 组件：若回调名含 `Dialog`/`Modal`/`Popup`，或 props 含 `onShow`/`onClose`/`visible`，标注"可能含弹窗"并附判断依据。
- 代码位置列**不能省略**，给出完整相对路径，外部组件给包名。
- 已废弃/未挂载的组件不纳入主表格，单独列在备注表中。
- 所有 oa-skills 命令必须在 Node >= 18 环境下执行，且带 `--mis <mis>` 参数。

## Subagent 并行策略

本 Skill 涉及大量文件读取和分析（典型页面 30-80 个文件），**必须使用 subagent 并行加速**。

### 何时使用 subagent

| 阶段 | 方式 | 原因 |
|------|------|------|
| Phase 2 定位结构 | 主 agent 直接并行调用 Read/Glob | 文件少（3-5 个），无需 subagent |
| Phase 3 第一轮广度搜索 | 主 agent 直接并行调用 Grep/Glob/Shell | 搜索操作天然可并行，无需 subagent |
| **Phase 3 第二轮深度验证** | **启动 2-4 个 explore subagent** | 核心瓶颈，需读取 20-50 个文件并逐个分析内容 |
| Phase 3 第三轮交叉校验 | 主 agent 直接并行调用 Grep | 搜索操作，无需 subagent |

### subagent 拆分原则

1. **按页面区域拆分**，每个 subagent 负责一个独立区域的全部文件，保持上下文连贯
2. 每个 subagent 分配 **10-20 个文件**，不宜过多（上下文过长影响分析质量）也不宜过少（启动开销不划算）
3. **所有 subagent 必须在同一条消息中发起**（一个 message 包含多个 Task tool call），确保并行执行
4. subagent 使用 `subagent_type="explore"`，适合快速文件读取和代码分析
5. 每个 subagent prompt 中需列出**完整的文件绝对路径**和**明确的分析输出格式要求**

### 性能参考

| 指标 | 不用 subagent | 用 2-4 个 subagent |
|------|-------------|-------------------|
| 深度验证 30+ 文件 | 串行 3-5 分钟 | 并行 ~30 秒 |
| 总梳理耗时 | 7-10 分钟 | 3-5 分钟 |
