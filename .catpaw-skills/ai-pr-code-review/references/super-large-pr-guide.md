# 超大 PR 模式（Step 2D）详细指南

> **触发条件**：Step 2B 检测到文件数恰好为 500（Code 平台截断限制）。
> **目标**：用 MCode REST API 分页拉取完整文件列表，替换截断列表，再做智能三层分层。

---

## 2D-1. 用 MCode API 拉完整文件列表

MCode（内部 Bitbucket）`/changes` 接口支持分页，无 500 文件限制：

```bash
# 获取浏览器 Cookie（复用 Step 0C 已校验的登录状态）
MCODE_COOKIE=$(python3 /root/.openclaw/workspace/.claude/skills/code-cli/code-cli/scripts/get_cookie.py 2>/dev/null)

# 分页拉取完整文件列表（循环直到 isLastPage=true）
python3 - <<'PYEOF'
import json, urllib.request, os

org = "{org}"
repo = "{repo}"
pr_id = "{prId}"
cookie = os.environ.get("MCODE_COOKIE", "")

start = 0
limit = 500
all_files = []

while True:
    url = (f"https://dev.sankuai.com/code/api/1.0/projects/{org}/repos/{repo}"
           f"/pull-requests/{pr_id}/changes?start={start}&limit={limit}")
    req = urllib.request.Request(url, headers={"Cookie": cookie})
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    values = resp.get("values", [])
    all_files.extend(v["path"]["toString"] for v in values if "path" in v)
    if resp.get("isLastPage", True):
        break
    start = resp.get("nextPageStart", start + limit)

print(f"TOTAL_FILES={len(all_files)}")
for f in all_files:
    print(f)
PYEOF
```

输出 `TOTAL_FILES={N}` + 完整文件列表，赋值给 `$ALL_FILES`，替换 2B 中的截断列表。

> ⚠️ **Cookie 获取失败时 — 优先尝试扫码重新登录**：
>
> **Step 1：检测沙箱是否有 Chromium（9222 端口）**
> ```bash
> curl -s http://localhost:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print('HAS_BROWSER')" 2>/dev/null || echo "NO_BROWSER"
> ```
>
> **Step 2A：有 Chromium → 扫码引导**
> 1. 用 agent-browser 打开大象网页版（`https://im.daxiang.com`）登录页
> 2. 截图含二维码的页面，通过大象消息发给用户：「Cookie 已失效，请扫码重新登录（有效期约 2 分钟）」
> 3. 轮询检测登录状态（最多等 120 秒，每 3 秒检查一次页面是否跳转到主界面）
> 4. 登录成功 → 重新执行 `get_cookie.py` 拿 Cookie → 继续 2D 流程
> 5. 超时未扫 → 降级到 Step 2B
>
> **Step 2B：无 Chromium / 扫码超时 → 降级提示**
> - 提示用户：「超大 PR 需要浏览器登录以拉取完整文件列表，当前登录状态不可用。请在浏览器登录 dev.sankuai.com 后，将 Cookie 文件放到 `~/.openclaw/workspace/.claude/skills/code-cli/code-cli/scripts/cookie.txt`，然后重新触发 CR」
> - CR 降级为基于前 500 个文件继续（可能存在漏报）
> - 记录降级状态到 Step 11 完成报告中

> ⚠️ **API 路径说明**：内部使用 `/code/api/1.0/...`（非 `/rest/api/2.0/...`），已通过 PR #3141（1853文件）验证。

---

## 2D-2. 智能文件三层分层

拿到完整文件列表后，按以下规则分层：

### 分层规则

| 层级 | 识别规则（文件路径 glob 匹配） | 处理策略 |
|------|-------------------------------|---------|
| **P0 核心层** | `*Service*.java` / `*Manager*.java` / `*Controller*.java` / `*Converter*.java` / `*Assembler*.java` / `*Checker*.java` / `*Validator*.java` / `*Filter*.java` / `*Dao*.java` / `*Repository*.java` / `*Processor*.java` | **全量精读 diff，不设上限** |
| **P1 接口层** | `*DTO*.java` / `*Request*.java` / `*Response*.java` / `*VO*.java` / `*Enum*.java` / `*Config*.java` / `*Configuration*.java` / `*.xml` / `*.yml` / `*.yaml` / `*.properties` / `*Client*.java` / `*Facade*.java` | **读 diff，扫触发器；软上限 200 个文件** |
| **P2 边缘层** | `*Test*.java` / `*test*.java` / `*.md`（**例外见下方注**）/ `*.txt` / `*.json`（非配置）/ `*.png` / `*.jpg` / 静态资源 / 所有不匹配 P0/P1 的文件 | **直接跳过，仅统计数量** |

> ⚠️ **`*.md` 文件例外规则**：以下路径的 `.md` 文件**不归入 P2，归入 P1 接口层**，Step 3C Layer 3 会单独读取：
> - `specs/**/*.md`（需求规范 + 技术方案）
> - `.mdp/context/*.md`（领域知识、业务概念）
> - `.mdp/rules/team/*.md` / `.mdp/rules/project/*.md`（团队/项目规则）
>
> 其余 `*.md`（如 `README.md`、`CHANGELOG.md`）保持 P2 跳过。

### P1 软上限处理（超过 200 时）

超出 200 文件时，按以下优先级排序后截断：

```
优先级（从高到低）：
1. Enum 文件             ← 枚举变更影响最广
2. DTO/Request/Response  ← 接口契约变更
3. Config/xml/yml        ← 配置变更
4. Client/Facade         ← 外部调用层
5. 其余 P1 文件          ← 按目录深度升序（越浅越优先）

取前 200 个，超出部分标记为「P1 截断」，在 Step 2 播报中告知。
```

### 分层结果播报（Step 2 完成时必须输出）

```
🔀 超大 PR 模式：共 {N} 个文件
   ✅ P0 核心层：{p0} 个文件（全量精读）
   📋 P1 接口层：{p1_read} 个文件（扫描）{p1_truncated > 0 ? "，另有 {p1_truncated} 个因超出软上限(200)被跳过" : ""}
   ⏭ P2 边缘层：{p2} 个文件（已跳过，含 {test_count} 个测试文件）
   {p1_truncated > 0 ? "⚠️ 建议提交人将 PR 拆分为多个小 PR，以获得完整 CR 覆盖。" : ""}
```

---

## 2D-3. 后续步骤衔接

### Step 3A（Layer 1 文件读取）
- 仅读 P0 + P1 层文件，P2 层直接跳过
- P0 层：全量精读每个文件的 diff（无上限）
- P1 层：扫描 diff，重点看接口签名变更和触发器

### Step 3B（Layer 2 反查）
- 仅从 P0 + P1 层触发器中提取搜索关键词
- P2 层文件不产生反查搜索词

### 分批策略（超大 PR 模式下必然触发分批）
超大 PR 模式下**无需再判断文件数阈值，必然分批**：

| Batch | 内容 | 关注点 |
|-------|------|-------|
| Batch1 | P0 高危层（Service/Manager/Converter 等） | 核心业务逻辑、空指针、并发 |
| Batch2 | P0 其他核心层 + P1 Enum/DTO/接口层 | 接口变更兼容性、枚举扩展影响 |
| Batch3 | P1 Config/Client 层 | 配置变更风险、外部依赖变化 |
| Batch4 | 汇总去重，生成最终结论 | 跨 Batch 问题合并、重复去重 |

### 批次超时降级
- 单个 Batch 超时（5min）时，主 Agent 不等待，标记该批次为「超时未完成」
- 超时批次的文件纳入 Step 11 报告的「未覆盖文件列表」
- 主 Agent 基于已完成 Batch 的结论输出最终结果，结论有效

---

## 实战记录

| PR | 总文件 | P0 | P1 | P2 | 结果 |
|----|--------|-----|-----|-----|------|
| technician-vc-service #3141 | 1853 | 61 | 200/287 | 1505 | 🟠 P0×4/P1×4 |

> 📅 2026-04-07 验证：MCode API 路径 `/code/api/1.0/...` 可用，分页分批均正常。
