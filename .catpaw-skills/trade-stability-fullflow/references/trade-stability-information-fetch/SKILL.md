---
name: trade-stability-information-fetch
description: 交易前端稳定性信号识别与信息提取专家。作为稳定性全流程第一步，负责从原始信号中提取结构化关键信息，并通过 trade-fe-stability-kb 知识库补全页面技术档案。
  支持三类信号：告警（Raptor/CIA/成功率/48h首现）、TT工单、反馈（用户投诉、客诉、C端反馈、产研反馈、测试反馈、用户反馈等统一归为「反馈」）。
  核心能力：识别信号类型 → 匹配业务线（餐/综/酒/景）→ 提取 Bundle/页面/时间/用户标识 → 通过 trade-fe-stability-kb 知识库查询补全 projectId/raptor链接/diva链接/Appkey → 指定后续排查路径。
  输入：用户原始信号文本（告警推送/TT工单内容/反馈描述/截图）。
  输出：结构化信息提取结果（信号类型、业务线、用户标识、问题时间、Bundle/页面名、projectId、raptor链接、diva链接、Appkey、排查路径指向）。
  触发词：信息提取、信号识别、提取告警信息、提取工单信息、识别业务线。
---

# 信号识别与路由规则

## 前置输入

本 skill 作为全流程第一步执行，接收以下原始输入：

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 原始信号文本 | 用户输入 | 告警推送内容 / TT工单详情 / 反馈描述 / 反馈截图 |

> ⚠️ 信息提取必须在 **1 分钟内**完成，保证真实性，不得推断或捏造字段。

---

## 餐、综、酒、景的资产（通过 trade-fe-stability-kb 知识库查询）

**资产不再从本地 assets/ 文件读取，统一通过 Skill [trade-fe-stability-kb](https://friday.sankuai.com/skills/skill-detail?activeTab=overview&activeTestTab=cases&id=132756) 查询知识库 `~/.trade-fe-stability-knowledge` 获取。**

| 业务线 | 知识库资产文件 |
|--------|---------------|
| 餐 | `~/.trade-fe-stability-knowledge/assets/food-assets.md` |
| 综 | `~/.trade-fe-stability-knowledge/assets/gc-assets.md` |
| 酒 | `~/.trade-fe-stability-knowledge/assets/hotel-assets.md` |
| 景 | `~/.trade-fe-stability-knowledge/assets/travel-assets.md` |

**查询步骤（遵循 trade-fe-stability-kb 查询模式）**：

```bash
# 1. 同步知识库（不存在则自动 clone，存在则 fetch）
KB_DIR="$HOME/.trade-fe-stability-knowledge"
[ -d "$KB_DIR/.git" ] || git clone ssh://git@git.sankuai.com/nibfe/trade-fe-stability-knowledge.git "$KB_DIR"
git -C "$KB_DIR" fetch origin --quiet

# 2. 按业务线 Grep 精确匹配页面名/Bundle名/关键词（禁止整读）
grep -n "<页面名 或 Bundle名 或 关键词>" ~/.trade-fe-stability-knowledge/assets/<domain>-assets.md
# domain 取值：餐=food 综=gc 酒=hotel 景=travel
```

3. 命中后读取该条目 YAML 块上下文（条目标题 + 块内容），获取 `project_id`、`bundles`、`raptor_error_url`、`diva_url`、`server_log_appkey`、`repository_ssh_url` 等字段
4. 若未安装 trade-fe-stability-kb skill，先执行 `mtskills i trade-fe-stability-kb`

> ⚠️ **查询约束**：禁止整读资产文件、禁止跨业务线文件猜测资产归属；未命中时按 trade-fe-stability-kb 未命中模板输出，不得编造参数。知识库同步失败（SSH Key 未配置 / 不在内网）时输出诊断提示后停止。

---

## 🚨 业务线判断规则（必须遵守，不得凭 TT 目录名称推断）

业务线只能是**餐 / 综 / 酒 / 景**之一，必须通过以下规则判断，**不得仅凭 TT 目录名称（如「到店交易」「结算」等）推断**：

| 关键词 / 场景 | 业务线 | 说明 |
|---|---|---|
| 餐饮、food、秒提、美食、外卖、团购 | 餐 ||
| 服务零售、娱乐、美发、美业、亲子、运动、丽人 | 综 | |
| 酒店、民宿、住宿、hotel | 酒 | |
| 门票、景区、度假、跟团、组品、旅行社、travel | 景 | 门票/度假 均属景 |

**判断步骤**：
1. 直接从用户输入（页面名、Bundle名、问题描述关键词）与上表关键词匹配，判断业务线
2. 能明确匹配 → 确认业务线，继续通过 trade-fe-stability-kb 知识库查询对应资产补全技术档案
3. 无法从用户输入判断 → **立即提问，禁止继续流程**

> 🛑 **强制卡点：业务线不明确时必须提问，禁止继续流程**
>
> 若用户输入中无法直接判断业务线，**必须立即停止，向用户提问**，不得猜测、不得遍历资产文件、不得继续进入第二步。
>
> 提问模板：
>
> ```
> 请问这个问题属于哪条业务线？（餐 / 综 / 酒 / 景）
> ```
>
> ⚠️ **只有用户明确回答业务线后，才能继续执行后续步骤。**

---

## 信息提取清单的规则

- 保证信息提取清单的真实性
- 保证信息提取的速度，1分钟内必须完成
- **提取完后必须按照下方「输出格式」输出结果**，用于下一步的指示
- TT工单信号、反馈信号中的页面或者Bundle信息可以匹配餐综酒景的资产获得（通过 trade-fe-stability-kb 知识库查询，见上方「餐、综、酒、景的资产」章节）

---
开始执行第一步前，**必须**先执行以下命令，记录开始时间：
```bash
startTime=$(date "+%Y-%m-%d %H:%M:%S") && echo $startTime
```

## 第一步：信号类型识别&提取

### 告警信号

**识别特征**（满足任一）：
- 文本含「Raptor告警」「CIA告警」「成功率告警」「JS异常告警」「48小时首现」「前端异常」「js异常」
- 来源于监控平台推送（Radar / Raptor）
- 含[规则配置] [告警详情] [告警看板] [点击查看数据] [智能分析] [告警记录] [查看数据] [查看数据 | 规则配置 | 大盘链接] [查看数据 | 规则配置] [异常指标: xxxx]


**信息提取清单**：
- 告警级别
- 告警类型
- 所属项目（Bundle）
- 告警名称
- 告警时间
- 告警内容
- 查看数据(详细数据的链接)

---

### TT工单信号

**识别特征**（满足任一）：
- 文本含 `TT#` 或 `TT号` 或纯数字工单编号
- 含「工单」「客服工单」「TT处理」「处理一下这个TT」
- 来源于 TT 系统推送

**信息提取清单**：
- TT编号
- 问题类型（提单失败/支付异常/页面白屏/功能不可用/其他）
- userId / 手机号/ 订单号（必须有一个）
- 问题发生时间
- 客户端版本和系统（iOS/Android/harmony）
- 复现步骤

---

### 反馈信号

用户投诉、客诉、C端反馈、产研反馈、测试反馈、用户反馈等统一归为「反馈」类型。

**识别特征**（满足任一）：
- 含「客诉」「用户投诉」「C端反馈」「用户反馈」「有用户说」「同学反馈」「测试反馈」「产研反馈」
- 附有用户截图 + userId/手机号/订单号（必须有一个）
- 来自客服系统转发，或开发同学直接描述线上问题
- 含问题截图但没有 TT 编号

**信息提取清单**：
- userId / 手机号/ 订单号（必须有一个）
- 截图描述（推断问题页面）
- 发生时间
- 问题描述文字

---

## 第二步：通过 trade-fe-stability-kb 知识库补全技术档案

完成信号提取、确认业务线和页面/Bundle后，**必须**按上方「餐、综、酒、景的资产」章节查询知识库对应资产条目，补全以下字段：

| 字段 | 知识库资产条目中的字段名 | 说明 |
|------|------------------------|------|
| 技术栈 | `stack` | DUO / MRN / MAX / 小程序 / i版 / H5 |
| projectId | `project_id` | Raptor 项目 ID，用于构造异常链接 |
| SSH链接 | `repository_ssh_url` | 页面对应代码仓库 SSH 地址 |
| raptor链接 | `raptor_error_url` | 前端异常查询直链 |
| diva链接 | `diva_url` | Bundle 发布记录直链（小程序/i版无此字段则填「无」） |
| Appkey | `server_log_appkey` | 后端日志查询所用 Appkey，可能有多个 |

> ⚠️ **补全规则**：
> - 若条目存在多个 Appkey（如 `server_log_appkey` 加 `notes` 中注明的 query Appkey，如 precreate + query），**全部列出**，用 `/` 分隔
> - 小程序、i版页面无 bundle 和 diva链接，对应字段填「无」
> - 若 project_id 不存在（如部分 i版页面），填「无」
> - **不得凭猜测填写，字段值必须来自知识库资产条目（引用带 `文件:行号`），不得从其他来源拼接**

---

## 第三步：输出信息提取报告

输出报告前，**必须**先执行以下命令，获取结束时间：

```bash
endTime=$(date "+%Y-%m-%d %H:%M:%S") && echo $endTime
```
> 💡 **耗时计算**：用 endTime 减去开始时记录的 startTime，精确到分钟，格式如「约 X 分钟」。

✅ **第一步：信息提取报告**（开始时间：{startTime}  耗时：{约 X 分钟}）

| 字段 | 内容 |
|------|------|
| 信号类型 | 告警 / TT工单 / 反馈 |
| 业务线 | 餐 / 综 / 酒 / 景（匹配依据：{Bundle名 或 关键词}） |
| 用户标识 | userId={xxx} / 手机号={xxx} / 订单号={xxx} / 无 |
| 问题时间 | YYYY-MM-DD HH:mm |
| 页面名称 | {页面名} |
| Bundle名 / 页面路径 | {bundle名 或 页面名} |
| 技术栈 |{DUO/MRN/MAX/小程序/i版}|
| projectId | {xxx 或 无} |
| SSH链接 | 仓库ssh链接 |
| raptor链接 | {aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPXh4eA== 或 无} |
| diva链接 | {aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29tL2J1bmRsZS94eHgvdmVyc2lvbnM/ZW52PXByb2Q= 或 无} |
| Appkey | {com.sankuai.xxx / com.sankuai.yyy（多个用 / 分隔）} |

➡️ **进入第二步：变更查询**
---
