# 环境依赖说明

> 本 skill 运行在统一沙箱环境,工具路径写死、依赖预置。

## 工具路径(写死)

```bash
SKILL_DIR="${ai_skill_directory}/ai-quality-cr-agent"
CODE_CLI="$SKILL_DIR/scripts/code_cli.py"          # 内置,随 skill 分发
REPO_SEARCH="$SKILL_DIR/scripts/repo_search.py"    # 内置,随 skill 分发
REPO_SEARCH_AVAILABLE=true
```

- `ai_skill_directory` 为沙箱注入的环境变量(skill 根目录)
- `code_cli.py` / `repo_search.py` 内置于 `scripts/`,无需 `find`/`mtskills path` 搜索
- 路径不存在 = 沙箱异常,直接报错终止

## 沙箱浏览器鉴权

> **沙箱内 Chromium 已运行在 localhost:9222(CDP 端口)**,且已通过 SSO 登录内网。
> `code_cli.py` 自动通过 CDP 获取 dev.sankuai.com 的 Cookie,**无需用户手动提供 Cookie**。

鉴权方式(由 `code_cli.py` 内部处理,AI 无需关心):
1. MOA 无感换票(SSO Token,沙箱下自动探测,缓存 30 分钟)
2. CDP 浏览器 Cookie(连接 localhost:9222 → Network.getCookies)

### 常见误区

- ❌ 不要自己写 `curl` 去 SSO 登录页
- ❌ 不要让用户从浏览器复制 Cookie
- ❌ 不要认为"沙箱无浏览器"——沙箱内 Chromium 已预装运行
- ✅ 直接用 `$CODE_CLI` 即可,鉴权全自动

### 快速验证鉴权可用

```bash
python3 "$SKILL_DIR/scripts/get_dev_cookie.py" --check
```

## 外部 CLI 依赖(沙箱预置)

| CLI | 用途 | 缺失处理 |
|-----|------|---------|
| `oa-skills` | citadel(Step 6 学城文档) | 自动安装(Step 0B),安装失败则终止 |
| `ones` | ee-ones(Step 1 ONES 上下文,可选) | 无 ONES ID 时不影响 |

## 行内评论命令示例

```bash
$CODE_CLI comment-add \
  --url "$PR_URL" \
  --file "完整文件路径（与 pr-changes 返回的 path 完全一致）" \
  --line 23 \
  --line-type ADDED \
  --text "评论内容" 2>&1
```

成功返回:`{"ok": true, "id": 50319159, "text": "..."}`
