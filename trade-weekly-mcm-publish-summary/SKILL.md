---
name: trade-weekly-mcm-publish-summary
description: "统计交易前端团队本周 MCM 上线发布情况。按团队成员 MIS 列表查询指定时间范围内（默认上周五到本周四）的 MCM 变更计划，输出带链接的汇总表格和按人统计，并提取每条变更的 PRD 和 ONES 链接。当用户需要查团队本周上线、MCM 发布汇总、谁有发布、上线统计时使用。触发词：MCM 统计、上线统计、本周发布、团队发布汇总、查本周上线、MCM 发布情况、谁有发布、发布汇总。"
---

# 交易前端团队 MCM 上线发布统计

查询团队成员在指定时间范围内的 MCM 变更计划，输出带链接的发布汇总表，并提取每条变更的 PRD 和 ONES 链接。

## 前置依赖

- `mcm-cli` 命令行工具（`mcm --version` 检查，需 >= 0.1.33）
- 已登录（`mcm whoami` 确认认证状态）

### 参考文档

- **mcm-cli 官方 Skill 文档**：https://friday.sankuai.com/skills/skill-detail?activeTab=overview&id=3708
  - 遇到命令参数、输出格式、认证等问题时，优先参考此文档

## 使用方式

用户提供以下信息（均可通过对话上下文获取）：
- **团队成员 MIS 列表**：直接列出 MIS ID，或使用下方默认列表
- **时间范围**：默认为「上周五 00:00:00 ~ 本周四 23:59:59」

### 默认团队成员 MIS 列表

```text
baolilei      鲍立磊
liuxin62      刘欣
liulichao     刘立超
zhangce07     张策
wangyu193     王宇
wb_xuweixin   许未鑫
duanshuhuai   段舒怀
hwhm_mamenglong  华为-马孟龙
wangwenting09 王文婷
yanyi22       颜怡
liyanyan25    李炎炎
zhangyanbing  张艳兵
```

## 执行流程

### Step 1: 确定时间范围

默认时间范围为「上周周五 00:00:00 ~ 本周四 23:59:59」。用户可指定其他时间范围。

使用 `date` 命令计算具体日期：
```bash
# 示例：计算上周五和本周四
date -v-thu -v-fri "+%Y-%m-%d" 2>/dev/null || date -d "last friday" "+%Y-%m-%d"
```

### Step 2: 查询每人的发布

对列表中每个 MIS 执行：

```bash
mcm plan list --creator <mis> --start "<startTime>" --end "<endTime>" -s 50 -f json
```

- `--creator`：按创建人筛选（仅返回该人发起的计划）
- `--start` / `--end`：计划开始时间范围
- `-s 50`：每页 50 条
- `-f json`：JSON 格式输出

### Step 3: 查询每条变更的详情，提取 PRD 和 ONES 链接

对每条变更计划，调用详情接口获取 PRD 和 ONES 链接：

```bash
mcm plan detail <planId> -f json
```

从返回的 JSON 中提取：

1. **ONES 链接**：`planContent.onesLink`（直接 URL）或 `planContent.onesIssue`（Issue ID，需拼链接）
2. **PRD 链接**：从 `planContent.description` HTML 中提取，按以下优先级：
   - **优先**：查找表格行 `需求PRD/Ones`，提取同行下一个 `<td>` 中的链接
     - 正则：`需求PRD.*?</td>.*?<td[^>]*>(.*?)</td>`，再从匹配到的 cell 中提取 `href`
     - 这是最可靠的方式，大部分前端上线模板使用此格式
   - **备选**：若无上述表格行或行内无链接，使用以下启发式规则：
     - 使用正则匹配 `href="(https?://km\.sankuai\.com/(collabpage|page)/\d+)"`
     - 过滤掉模板通用链接（出现在几乎所有计划中的链接）：
       - `2719653030`（交易紧急止损SOP）
       - `2730541093`（上线规范/酒）
       - `2753993729`（餐）
       - `2569577290`（综）
       - `2730136094`（景）
       - `1247807532`（模板链接）
       - `1215929361`（模板链接）
     - 剩余唯一链接中，锚点文字包含「PRD」或链接裸挂在正文中的即为 PRD 链接
     - 若无法确认标题，可用 citadel CLI 查询文档标题辅助判断（需 Node >= 18）：
       ```bash
       oa-skills citadel getSimpleMarkdown --contentId <id> 2>&1 | head -3
       ```

3. **ONES 链接格式**：
   - `onesLink` 有值时直接使用
   - 仅有 `onesIssue` 时拼接为 `https://ones.sankuai.com/ones/product/18762/testdetail/<onesIssue>`
   - 也需在 description HTML 中搜索 `ones.sankuai.com` 链接作为补充

> **注意**：mcm-cli 的 `plan detail` 输出可能较大（几十KB），可重定向到临时文件后用脚本提取关键字段。

### Step 4: 汇总输出

将所有查询结果汇总为以下格式：

#### 汇总表

| # | 同学 | 发布名称 | 状态 | 计划时间 | PRD | ONES | MCM |
|---|------|---------|------|---------|-----|------|-----|
| 1 | 张策 | 【酒店】xxx 上线 | ✅ 成功 | 7/29 | [PRD](km链接) | [ONES](ones链接) | [1049847](https://mcm.mws.sankuai.com/#/mine/plan/detail/1049847) |

#### 按人统计

- 刘立超：2 条
- 李炎炎：4 条
- ...

#### 状态映射

| MCM 状态 | 显示 | Emoji |
|---------|------|-------|
| SUCCEED | 成功 | ✅ |
| RUNNING | 执行中 | 🔄 |
| WAIT_RUNNING | 待执行 | ⏳ |
| AUDITING | 审核中 | 🔍 |
| PLANNING | 计划中 | 📝 |
| STOPPED | 已停止 | ⛔ |
| REJECTED | 已驳回 | ❌ |

## 注意事项

1. **无发布记录的同学**：在按人统计中标注「本周无创建发布」
2. **MCM 链接格式**：`https://mcm.mws.sankuai.com/#/mine/plan/detail/<planId>`
3. **时间格式**：`yyyy-MM-dd HH:mm:ss`，北京时间 (UTC+8)
4. **每页条数**：默认 50 条，若团队成员发布较多可适当调大
5. **PRD/ONES 缺失**：若某条变更未找到 PRD 或 ONES 链接，该单元格显示「—」
6. **无权限文档**：部分学城文档可能因权限或高密级无法访问，标注「（无权限）」即可
