# 第七步：上报评分数据

评估完成后，将本次评分结果通过 Supabase REST API 直接写入数据库，实现评分数据集中汇总。

---

## 第零步：获取 Supabase 配置（SUPABASE_URL + ANON_KEY）

通过远程配置接口动态获取 `SUPABASE_URL` 和 `ANON_KEY`。**anon key 不写入 skill 文件**，必须从远程接口获取。

```bash
SUPABASE_CONFIG=$(python3 - <<'EOF'
import requests, sys
CONFIG_URL = "https://mt258jsd6lpnob.sandbox.nocode.sankuai.com/config.json"
try:
    cfg = requests.get(CONFIG_URL, timeout=5).json()
    print(f"{cfg['supabase_url']}|{cfg['anon_key']}")
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)

if [ $? -eq 0 ] && [ -n "$SUPABASE_CONFIG" ]; then
  SUPABASE_URL=$(echo "$SUPABASE_CONFIG" | cut -d'|' -f1)
  ANON_KEY=$(echo "$SUPABASE_CONFIG" | cut -d'|' -f2)
  echo "✅ 远程配置获取成功"
else
  echo "⚠️ 远程配置获取失败，跳过上报。"
  echo "   请检查网络是否可访问：https://mt258jsd6lpnob.sandbox.nocode.sankuai.com/config.json"
  # 跳过后续上报步骤，直接结束
  exit 0
fi
```

---

## 第一步：获取 JWT Token（自动登录，失败时手动输入）

通过 playwright 打开浏览器，引导用户完成美团 SSO 登录后从 localStorage 提取 Supabase JWT token。

### 1a. 检测 playwright 是否可用

```bash
python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null && echo "installed" || echo "not installed"
```

**未安装时**（exit code 非 0）：

输出以下提示，跳至 1c（手动输入）：

```
⚠️ playwright 未安装，无法自动弹出浏览器获取 JWT Token。
安装命令：pip3 install playwright && playwright install chromium
```

### 1b. 自动登录获取 token

```bash
# SKILL_BASE_DIR 由 skill 执行框架注入，指向当前 skill 的根目录
SCRIPT_PATH="${SKILL_BASE_DIR}/scripts/get_nocode_token.py"
echo "正在通过美团 SSO 自动获取 JWT Token（将弹出浏览器，请完成登录）..."
JWT_TOKEN=$(python3 "$SCRIPT_PATH" 2>/tmp/ai_ready_sso_err.txt)
```

- 成功（exit 0 且 `JWT_TOKEN` 非空）→ 继续第二步
- 失败 → 输出错误原因，跳至 1c（手动输入）

### 1c. 回退：手动输入 token

使用 `AskUserQuestion` 工具询问：

> "自动获取 token 失败。请手动访问 https://agent-data-scan.mynocode.host 登录后，从浏览器控制台执行 `window.NoCode?.getUserInfo()?.token` 获取 token，粘贴至此处（留空跳过上报）。"

- 用户提供 Token → 赋值给 `JWT_TOKEN`，继续第二步
- 用户留空或跳过 → **跳过上报，流程结束**

---

**重要：所有变量仅在 shell 内存中使用，禁止写入任何本地文件。第零步至第四步必须在同一个 Bash 工具调用中完成。** 每次 Bash 工具调用都是独立的 shell 进程，变量不跨调用共享。若拆成多个 Bash 块执行，`SUPABASE_URL`、`ANON_KEY`、`JWT_TOKEN` 等变量会丢失，导致重复弹出浏览器登录。**必须将第零步至第四步的所有 shell 命令合并为一个 Bash 工具调用，禁止分块执行。**

---

## 第二步：收集 repo 信息

```bash
# 获取远程 URL
REPO_URL=$(git remote get-url origin 2>/dev/null || echo "")

# 解析 org/repo 格式（兼容 SSH 和 HTTPS 格式），去掉 .git 后缀
REPO_NAME=$(echo "$REPO_URL" | sed -E 's|.*[:/]([^/]+/[^/]+)(\.git)?$|\1|')

# 读取环境变量，缺省从 git config 推断
MIS_ID="${AI_READY_MIS_ID:-$(git config user.email 2>/dev/null | cut -d@ -f1)}"
```

---

## 第三步：插入主评分记录

> 直接使用第零步已获取的 `${SUPABASE_URL}`、`${ANON_KEY}`，第一步已获取的 `${JWT_TOKEN}`，不重新登录。

```bash
# SUPABASE_URL 和 ANON_KEY 已在第零步从远程配置接口获取
# KM_URL 来自第六步：若用户选择保存到学城且成功，则为学城文档链接；否则为空字符串
# 示例：KM_URL="https://km.sankuai.com/collabpage/2748397739" 或 KM_URL=""

# 插入主表，获取 score_id
SCORE_RESP=$(curl -s -X POST \
  "${SUPABASE_URL}/rest/v1/ai_ready_scores" \
  -H "apikey: ${ANON_KEY}" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H 'Content-Type: application/json' \
  -H 'Prefer: return=representation' \
  -d "{
    \"repo_name\": \"${REPO_NAME}\",
    \"repo_url\": \"${REPO_URL}\",
    \"mis_id\": \"${MIS_ID}\",
    \"skill_version\": \"ai-ready-repo@3.7.0\",
    \"repo_type\": \"${REPO_TYPE}\",
    \"total_score\": ${TOTAL_SCORE},
    \"suggestions\": \"${SUGGESTIONS}\",
    \"km_url\": \"${KM_URL}\"
  }")

SCORE_ID=$(echo "$SCORE_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])" 2>/dev/null)
```

若 `SCORE_ID` 为空，提示：
```
⚠️ 主表插入失败，跳过维度明细上报。
```
并跳过第四步，直接输出失败结果。

**mono-repo 上报规则**：`${REPO_TYPE}` 填 `mono-repo`，`${TOTAL_SCORE}` 填全部成员综合分的
等权平均值，成员明细以第六步报告为准。主表写入成功后跳过第四步的维度明细写入，因为成员
可能使用不同权重档案，当前明细表无法忠实表达一组统一的 `dim_weight`；禁止虚构父仓权重。
若主表拒绝 `mono-repo` 类型，按真实响应报告上报失败，不得回退伪装成单仓类型。

---

## 第四步：构造 Payload 并插入维度明细

> 直接使用第零步已获取的 `${SUPABASE_URL}`、`${ANON_KEY}`，第一步已获取的 `${JWT_TOKEN}`，不重新登录。

本步骤仅用于单仓。mono-repo 已在第三步写入父仓平均分后结束上报。

基于前六步的评估结果，构造以下 JSON 数组（11 条记录），每条对应一个维度：

```json
[
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim1a",
    "dim_name": "仓库定位准确性",
    "dim_weight": 6,
    "dim_score": <S1>,
    "pass_rules": "<✅ 优势项1>;<✅ 优势项2>",
    "deduct_rules": "<⚠️ 扣分项1>;<⚠️ 扣分项2>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim1b",
    "dim_name": "仓库导航完整性",
    "dim_weight": 6,
    "dim_score": <S2>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim2",
    "dim_name": "架构文档完整性",
    "dim_weight": 12,
    "dim_score": <S3>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim3",
    "dim_name": "代码可读性",
    "dim_weight": 8,
    "dim_score": <S4>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim4",
    "dim_name": "代码可维护性",
    "dim_weight": 7,
    "dim_score": <S5>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim5",
    "dim_name": "代码可扩展性",
    "dim_weight": 5,
    "dim_score": <S6>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim6",
    "dim_name": "业务领域建模",
    "dim_weight": 14,
    "dim_score": <S7>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim7",
    "dim_name": "编码规范遵守度",
    "dim_weight": 12,
    "dim_score": <S8>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim8",
    "dim_name": "AI 协作友好度",
    "dim_weight": 8,
    "dim_score": <S9>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim9",
    "dim_name": "测试验证",
    "dim_weight": 12,
    "dim_score": <S10>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  },
  {
    "score_id": <SCORE_ID>,
    "repo_name": "<REPO_NAME>",
    "dim_key": "dim10",
    "dim_name": "反馈回路",
    "dim_weight": 10,
    "dim_score": <S11>,
    "pass_rules": "<✅ 优势项>",
    "deduct_rules": "<⚠️ 扣分项>",
    "suggestions": "<该维度改进建议>"
  }
]
```

**填充规则**：
- `pass_rules`：从该维度"得分依据"的 ✅ 项提取，多条用 `;` 分隔，无则填 `""`
- `deduct_rules`：从该维度"得分依据"的 ⚠️ 项提取，多条用 `;` 分隔，无则填 `""`
- `suggestions`：该维度的改进建议，无则填 `""`

执行插入：

```bash
ITEMS_RESP=$(curl -s -X POST \
  "${SUPABASE_URL}/rest/v1/ai_ready_score_items" \
  -H "apikey: ${ANON_KEY}" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H 'Content-Type: application/json' \
  -H 'Prefer: return=representation' \
  -d "${ITEMS_JSON}")
```

---

## 第五步：输出结果

- 主表插入成功（`SCORE_ID` 非空）且维度明细插入成功：输出 `✅ 评分数据已上报，score_id=${SCORE_ID}`
- 任意步骤失败：输出 `⚠️ 上报失败，本次评分数据未能同步`

**上报失败不影响本次评估结果，流程正常结束。**

---

## 环境变量

| 变量名 | 必填 | 说明 | 缺省值 |
|--------|------|------|--------|
| `AI_READY_MIS_ID` | 否 | 评估人工号/用户名 | `git config user.email` 的 `@` 前部分 |

**注**：`SUPABASE_URL` 和 `ANON_KEY` 从远程配置接口 `https://mt258jsd6lpnob.sandbox.nocode.sankuai.com/config.json` 动态获取，不写入 skill 文件。接口不可达时跳过上报，不影响评估结果。
