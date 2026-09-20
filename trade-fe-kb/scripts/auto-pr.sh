#!/usr/bin/env bash
# =============================================================================
# trade-kb · auto-pr.sh
#
# KB 更新流程的 git 操作 + PR 创建封装。
# source 同目录 _code_.sh 调用美团 Code 平台 API。
#
# 子命令：
#   sync_kb                           # clone（若不存在）+ fetch + checkout release/main + pull
#   resolve_mis                       # 打印 MIS（失败打印空串）
#   compute_branch <mis> <topic>      # 打印分支名 feat/kb-<topic>-<5位随机串>（topic建议≤15字符）
#   safe_checkout_new <branch>        # 检查 working tree 干净 + 创建新分支，打印最终分支名
#   commit_push <msg_body> <file...>  # git add <files> + commit + push origin HEAD
#   pr_create_wrapper <branch> <title> <desc>
#                                     # 创建 PR，返回 PR URL；失败返回 fallback URL
#   fallback_pr_url <branch>          # 打印手动提 PR 的 URL
#
# 固定配置：
#   REPO_SSH  = ssh://git@git.sankuai.com/nibfe/trade-fe-rule.git
#   KB_DIR    = $TRADE_KB_DIR 或 ~/.trade-fe-kb
#   TARGET    = release/main
#   REVIEWERS = changsusheng / it_catpaw
# =============================================================================
set -euo pipefail

# ─── 全局常量 ────────────────────────────────────────────────────────────────
readonly REPO_PROJECT="nibfe"
readonly REPO_NAME="trade-fe-rule"
readonly REPO_SSH="ssh://git@git.sankuai.com/${REPO_PROJECT}/${REPO_NAME}.git"
readonly TARGET_BRANCH="release/main"
readonly KB_DIR="${TRADE_KB_DIR:-$HOME/.trade-fe-kb}"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly CODE_API="${SCRIPT_DIR}/_code_.sh"
# 固定 reviewer；PR API 使用 hfe_stash 身份，Bitbucket 禁止 author = reviewer。
readonly REVIEWERS=("changsusheng" "it_catpaw")
readonly PR_AUTHOR="hfe_stash"

if [ ! -f "${CODE_API}" ]; then
  echo "ERROR: 找不到 Code API 脚本: ${CODE_API}" >&2
  exit 10
fi

# ─── 依赖检查 ────────────────────────────────────────────────────────────────
# Query snapshots only need Git; update/PR commands retain the full toolchain.
if [ "${1:-}" = "query_snapshot" ]; then
  _required_commands=(git)
else
  _required_commands=(git curl jq openssl)
fi
for _cmd in "${_required_commands[@]}"; do
  if ! command -v "${_cmd}" &>/dev/null; then
    echo "ERROR: 缺少依赖命令: ${_cmd}，请先安装后重试" >&2
    exit 9
  fi
done
unset _required_commands
unset _cmd

# shellcheck disable=SC1090
source "${CODE_API}"

# ─── 工具函数 ────────────────────────────────────────────────────────────────
_log() { echo "[trade-kb] $*" >&2; }
_err() { echo "[trade-kb][ERROR] $*" >&2; }

# ─── sync_kb ─────────────────────────────────────────────────────────────────
# clone（若不存在）+ fetch + checkout release/main + pull
sync_kb() {
  if [ ! -d "${KB_DIR}/.git" ]; then
    # KB_DIR 存在但不是 git 仓库（空目录或误建目录），需先清理
    if [ -e "${KB_DIR}" ]; then
      _err "目录 ${KB_DIR} 已存在但不是 git 仓库，请手动删除后重试：rm -rf ${KB_DIR}"
      exit 11
    fi
    _log "本地 KB 不存在，正在 clone..."
    if ! git clone "${REPO_SSH}" "${KB_DIR}"; then
      _err "git clone 失败，请检查 SSH Key：ssh -T git@git.sankuai.com"
      exit 11
    fi
  fi

  cd "${KB_DIR}"
  if ! git fetch origin; then
    _err "git fetch origin 失败，请检查网络/SSH 配置"
    exit 12
  fi
  git checkout "${TARGET_BRANCH}"
  if ! git pull --ff-only origin "${TARGET_BRANCH}"; then
    _err "git pull --ff-only 失败，本地存在未推送提交，请手动处理后重试"
    exit 12
  fi

  _log "✅ KB 已同步到最新 ${TARGET_BRANCH}"
  echo "${KB_DIR}"
}

# ─── query_snapshot ──────────────────────────────────────────────────────────
# Fetch release/main for queries without changing the user's branch or worktree.
query_snapshot() {
  if [ ! -d "${KB_DIR}/.git" ]; then
    if [ -e "${KB_DIR}" ]; then
      _err "目录 ${KB_DIR} 已存在但不是 git 仓库，请手动处理后重试"
      exit 11
    fi
    if ! git clone "${REPO_SSH}" "${KB_DIR}" >/dev/null; then
      _err "git clone 失败，请检查 SSH Key：ssh -T git@git.sankuai.com"
      exit 11
    fi
  fi

  if ! git -C "${KB_DIR}" fetch --no-tags origin \
    "refs/heads/${TARGET_BRANCH}:refs/remotes/origin/${TARGET_BRANCH}" >/dev/null; then
    _err "git fetch ${TARGET_BRANCH} 失败，请检查网络/SSH 配置"
    exit 12
  fi
  git -C "${KB_DIR}" rev-parse --verify "refs/remotes/origin/${TARGET_BRANCH}^{commit}"
}

# ─── resolve_mis ─────────────────────────────────────────────────────────────
resolve_mis() {
  local mis=""
  # 1) 环境变量
  if [ -n "${MIS:-}" ]; then
    mis="${MIS}"
  elif [ -n "${USER_MIS:-}" ]; then
    mis="${USER_MIS}"
  fi
  # 2) git config user.email @ 前
  if [ -z "${mis}" ]; then
    local email
    email="$(git config user.email 2>/dev/null || true)"
    if [[ "${email}" =~ ^([a-z0-9._-]+)@ ]]; then
      mis="${BASH_REMATCH[1]}"
    fi
  fi
  # 3) git config user.name（4-12 位小写英数才认为是 mis）
  if [ -z "${mis}" ]; then
    local name
    name="$(git config user.name 2>/dev/null || true)"
    if [[ "${name}" =~ ^[a-z][a-z0-9]{3,11}$ ]]; then
      mis="${name}"
    fi
  fi
  if [ -z "${mis}" ]; then
    _err "WARN: 无法解析 MIS（已尝试 \$MIS / git email / git name），分支名将省略 MIS 段"
    _err "WARN: 如需带 MIS，请设置环境变量：export MIS=<你的MIS> 后重试"
  fi
  echo "${mis//./_}"
}

# ─── compute_branch ──────────────────────────────────────────────────────────
# 参数: mis（保留参数位，不写入分支名）topic（kebab-case 英文）
# 输出: feat/kb-<topic>-<5位随机串>
# 唯一性由随机串保证；topic 由调用方（AI）控制长度，建议 ≤ 15 字符
compute_branch() {
  local mis="${1:-}" topic="${2:?need topic}"

  # 5位十六进制随机串，保证分支唯一
  # 用 openssl rand -hex（无 locale 依赖，macOS/Linux 均兼容）
  # 不用 tr + /dev/urandom，避免 macOS 下 "Illegal byte sequence" + SIGPIPE 导致函数提前退出
  local rand
  rand="$(openssl rand -hex 3 | head -c5)"

  echo "feat/kb-${topic}-${rand}"
}

# ─── safe_checkout_new ───────────────────────────────────────────────────────
safe_checkout_new() {
  local base="${1:?need base branch name}"

  cd "${KB_DIR}"

  # 前置校验 1：working tree 必须干净
  if [ -n "$(git status --porcelain)" ]; then
    _err "working tree 存在未提交改动，请先 git stash 后重试"
    git status --short >&2
    exit 14
  fi

  # 前置校验 2：必须在 release/main 上才允许切分支
  local current_branch
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  if [ "${current_branch}" != "${TARGET_BRANCH}" ]; then
    _err "当前分支为 ${current_branch}，必须在 ${TARGET_BRANCH} 上创建新分支"
    _err "请先执行：bash auto-pr.sh sync_kb"
    exit 14
  fi

  # 同名冲突则追加 -r2 / -r3（同时检查本地和远程）
  local branch="${base}" i=2
  while git show-ref --verify --quiet "refs/heads/${branch}" || \
        git show-ref --verify --quiet "refs/remotes/origin/${branch}"; do
    branch="${base}-r${i}"
    i=$((i + 1))
    if [ "${i}" -gt 20 ]; then
      _err "同名分支冲突超过 20 次，放弃"
      exit 15
    fi
  done

  git checkout -b "${branch}"
  _log "已切到新分支: ${branch}"
  echo "${branch}"
}

# ─── commit_push ─────────────────────────────────────────────────────────────
# 参数: msg_body（commit message 正文）file1 [file2 ...]
commit_push() {
  if [ $# -lt 2 ]; then
    _err "commit_push 需要至少 2 个参数: msg_body file1 [file2...]"
    exit 2
  fi
  local msg="$1"; shift

  cd "${KB_DIR}"
  _log "git add: $*"
  git add -- "$@"

  if git diff --cached --quiet; then
    _err "staged 区为空，没有需要提交的变更"
    exit 16
  fi

  git commit -m "${msg}"

  local branch
  branch="$(git rev-parse --abbrev-ref HEAD)"
  _log "git push origin ${branch}"
  if ! git push --set-upstream origin "${branch}"; then
    _err "git push 失败。本地 commit 已保留，恢复命令：cd ${KB_DIR} && git push origin ${branch}"
    exit 17
  fi
  _log "✅ push 成功: ${branch}"
  # remote 可能在 stderr 输出指向 master 的 "建 PR" 提示 URL，但该 URL 目标分支有误。
  # 本脚本固定以 TARGET_BRANCH=${TARGET_BRANCH} 为 PR 目标，请忽略 remote hint。
  _log "PR 目标分支：${TARGET_BRANCH}（忽略 remote 输出的其他 URL）"
  echo "${branch}"
}

# ─── pr_create_wrapper ───────────────────────────────────────────────────────
# 参数: branch title desc
# 认证、HTTPS 请求和响应体清理由 _code_.sh 统一处理，避免凭据散落到多个脚本。
pr_create_wrapper() {
  local branch="${1:?need branch}" title="${2:?need title}" desc="${3:?need desc}"

  # ── reviewers：固定列表 + 动态当前用户，排除 PR 创建者 ──
  local reviewers_json='[]'
  for mis in "${REVIEWERS[@]}"; do
    reviewers_json="$(echo "${reviewers_json}" | jq --arg mis "${mis}" '. + [{"user": {"name": $mis}}]')"
  done
  local cur_mis
  cur_mis="$(resolve_mis)"
  if [ -n "${cur_mis}" ] && [ "${cur_mis}" != "${PR_AUTHOR}" ]; then
    local already
    already="$(echo "${reviewers_json}" | jq --arg mis "${cur_mis}" 'map(select(.user.name == $mis)) | length')"
    if [ "${already}" = "0" ]; then
      reviewers_json="$(echo "${reviewers_json}" | jq --arg mis "${cur_mis}" '. + [{"user": {"name": $mis}}]')"
      _log "追加当前用户 ${cur_mis} 为 reviewer"
    fi
  fi

  local body resp
  body="$(jq -cn \
    --arg title "${title}" \
    --arg desc "${desc}" \
    --arg branch "${branch}" \
    --arg repo "${REPO_NAME}" \
    --arg project "${REPO_PROJECT}" \
    --arg target "${TARGET_BRANCH}" \
    --argjson reviewers "${reviewers_json}" \
    '{
      title: $title,
      description: $desc,
      fromRef: {
        id: ("refs/heads/" + $branch),
        displayId: $branch,
        repository: { slug: $repo, project: { key: $project } }
      },
      toRef: {
        id: ("refs/heads/" + $target),
        displayId: $target,
        repository: { slug: $repo, project: { key: $project } }
      },
      deleteSourceRefAfterMerge: true,
      reviewers: $reviewers
    }')"

  _log "创建 PR: ${REPO_PROJECT}/${REPO_NAME} ${branch} → ${TARGET_BRANCH}"
  if ! resp="$(pr_create "${REPO_PROJECT}" "${REPO_NAME}" "${body}")"; then
    _err "pr_create 请求失败。"
    local fallback_url
    fallback_url="$(fallback_pr_url "${branch}")"
    _err "代码已 push，请手动建 PR: ${fallback_url}"
    echo "${fallback_url}"
    return 0
  fi

  local pr_id
  pr_id="$(echo "${resp}" | jq -r '.id // empty' 2>/dev/null || true)"
  if [ -z "${pr_id}" ] || [ "${pr_id}" = "null" ]; then
    _err "PR 创建响应缺少 id。"
    local fallback_url
    fallback_url="$(fallback_pr_url "${branch}")"
    echo "${fallback_url}"
    return 0
  fi

  local pr_url="${CODE_API_BASE}/code/repo-detail/${REPO_PROJECT}/${REPO_NAME}/pr/detail/${pr_id}"
  _log "✅ PR 创建成功: ${pr_url}"
  echo "${pr_url}"
}

# ─── fallback_pr_url ─────────────────────────────────────────────────────────
fallback_pr_url() {
  local branch="${1:?need branch}"
  echo "${CODE_API_BASE}/code/repo-detail/${REPO_PROJECT}/${REPO_NAME}/pr/create?sourceBranch=${branch}&targetBranch=${TARGET_BRANCH}"
}

# ─── 主入口 ───────────────────────────────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  if [ $# -lt 1 ]; then
    cat >&2 <<'EOF'
用法: bash auto-pr.sh <subcommand> [args...]

子命令:
  sync_kb
  query_snapshot
  resolve_mis
  compute_branch <mis> <topic>
  safe_checkout_new <base_branch>
  commit_push <commit_msg> <file1> [file2...]
  pr_create_wrapper <branch> <title> <desc>
  fallback_pr_url <branch>

典型 update 流程串联:
  1) bash auto-pr.sh sync_kb
  2) mis=$(bash auto-pr.sh resolve_mis)
  3) branch=$(bash auto-pr.sh compute_branch "$mis" "food-refund")   # topic ≤ 15 字符
  4) bash auto-pr.sh safe_checkout_new "$branch"
  5) [Agent 写文件]
  6) bash auto-pr.sh commit_push "docs: food 新增退款规则" biz/food/L2-spec/business-rules.md
  7) desc="food business-rules.md 新增次卡退款规则说明"              # 纯文字，禁止URL/Markdown/斜杠/换行
     pr_url=$(bash auto-pr.sh pr_create_wrapper "$branch" "docs: food 新增退款规则" "$desc")
EOF
    exit 1
  fi
  sub="$1"; shift
  "${sub}" "$@"
fi
