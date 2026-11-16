#!/usr/bin/env bash
# =============================================================================
# trade-fe-knowledge-editor · auto-pr.sh
#
# [auto-only] 自动模式下的 workspace 校验 / git 流程 / pr_create 封装。
# 引用同目录 _code_.sh 调用美团 Code 平台 REST API。
#
# 使用前提：
#   - 需要 bash 4+、git、curl、jq、node
#   - 底层 Code API 通过 _code_.sh 中的 hfe_stash 服务账号鉴权
#
# 子命令：
#   ensure_workspace  [auto|local]              # 校验/切换工作区，auto 时不合法自动 clone
#                                                # clone 落地目录按以下优先级动态决定（不再写死 /tmp）：
#                                                #   1) $TRADE_FE_CLONE_ROOT（显式指定）
#                                                #   2) $CATPAW_WORKSPACE_ROOT / $WORKSPACE_FOLDER（IDE 上下文）
#                                                #   3) $PWD 命中 */projects/ 或 */workspace/ → 取其父目录作为 root
#                                                #   4) $HOME/projects（若可写）
#                                                #   5) $(mktemp -d) 系统临时目录（最终兜底）
#   sync_master                                 # git fetch + checkout master + pull --ff-only
#   resolve_mis                                 # 打印 mis 号（失败打印空串）
#   compute_branch <mis?>                       # 打印分支名 chore/update-knowledge-{mis?}-{ts}
#   safe_checkout_new <branch>                  # 检测未提交改动 + 处理同名冲突 (-r2/-r3/…)
#   commit_scoped <group> <kinds> <mis> <msg_body_file>  # git add 指定文件 + commit
#   push_current_branch                         # git push origin HEAD
#   pr_create_wrapper <group> <kinds> <mis> <branch> <title_file> <desc_file>
#                                              # 调用 _code_.sh pr_create 并返回 PR URL
#   fallback_pr_url <branch>                   # 打印手动提 PR 的 URL
#
# 约定：
#   - REPO_SSH = ssh://git@git.sankuai.com/nibfe/trade-fe-rule.git
#   - PROJECT  = nibfe / REPO = trade-fe-rule / TARGET = master
# =============================================================================
set -euo pipefail

# ─── 全局常量 ────────────────────────────────────────────────────────────────
readonly REPO_PROJECT="nibfe"
readonly REPO_NAME="trade-fe-rule"
readonly REPO_SSH="ssh://git@git.sankuai.com/${REPO_PROJECT}/${REPO_NAME}.git"
readonly DEFAULT_BRANCH="master"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly CODE_API="${SCRIPT_DIR}/_code_.sh"
readonly CODE_BASE_URL="https://dev.sankuai.com"

if [ ! -f "${CODE_API}" ]; then
  echo "ERROR: 找不到 Code API 脚本: ${CODE_API}" >&2
  exit 10
fi

# source 以便复用函数（而不是每次 fork）
# shellcheck disable=SC1090
source "${CODE_API}"

# ─── 通用工具 ────────────────────────────────────────────────────────────────
_now_ts() { date +"%Y%m%d%H%M%S"; }

_log() { echo "[auto-pr] $*"; }
_err() { echo "[auto-pr][ERROR] $*" >&2; }

# 向上查找 trade-fe-rule 仓库根（AGENTS.md + context-docs/ + spec/ 同时存在）
_find_repo_root_upward() {
  local dir="${1:-$PWD}"
  dir="$(cd "${dir}" && pwd)"
  while :; do
    if [ -f "${dir}/AGENTS.md" ] && [ -d "${dir}/context-docs" ] && [ -d "${dir}/spec" ]; then
      echo "${dir}"
      return 0
    fi
    local parent
    parent="$(dirname "${dir}")"
    [ "${parent}" = "${dir}" ] && return 1
    dir="${parent}"
  done
}

# 判定 git remote 是否指向 trade-fe-rule
_remote_matches_repo() {
  local dir="${1:-$PWD}"
  local url
  url="$(git -C "${dir}" remote get-url origin 2>/dev/null || true)"
  [ -z "${url}" ] && return 1
  echo "${url}" | grep -q "${REPO_PROJECT}/${REPO_NAME}"
}

# ─── _resolve_clone_root ─────────────────────────────────────────────────────
# 按优先级返回一个"适合存放克隆仓库"的根目录（可写、已存在或可创建）。
# 不再写死 /tmp，让 clone 贴近用户真实工作区。
#
# 优先级（自上而下，第一个可用者胜出）：
#   1) $TRADE_FE_CLONE_ROOT               # 用户显式指定（最高优先级）
#   2) $CATPAW_WORKSPACE_ROOT             # CatPaw / IDE 注入
#   3) $WORKSPACE_FOLDER                  # VSCode 约定
#   4) $PWD 向上最近的 */projects/ 或 */workspace/ 父节点
#   5) $HOME/projects（若可写，不存在则尝试创建）
#   6) $(mktemp -d -t "${REPO_NAME}-XXXXXXXX") 系统临时目录（最终兜底）
#
# 返回：可写的绝对路径；失败退出 17
_resolve_clone_root() {
  local candidate=""

  # 1/2/3：环境变量
  for env_name in TRADE_FE_CLONE_ROOT CATPAW_WORKSPACE_ROOT WORKSPACE_FOLDER; do
    local val
    val="$(printenv "${env_name}" 2>/dev/null || true)"
    if [ -n "${val}" ] && [ -d "${val}" ] && [ -w "${val}" ]; then
      candidate="${val}"
      _log "clone root 解析命中 \$${env_name}: ${candidate}"
      echo "${candidate}"
      return 0
    fi
  done

  # 4：从 $PWD 向上找 /projects/ 或 /workspace/ 结构
  #     例：/root/projects/trade-fe-rule/... → /root/projects
  local dir="${PWD}"
  while [ "${dir}" != "/" ] && [ -n "${dir}" ]; do
    local base
    base="$(basename "${dir}")"
    if [[ "${base}" == "projects" || "${base}" == "workspace" || "${base}" == "workspaces" || "${base}" == "repos" ]]; then
      if [ -w "${dir}" ]; then
        _log "clone root 从 \$PWD 继承: ${dir}"
        echo "${dir}"
        return 0
      fi
    fi
    dir="$(dirname "${dir}")"
  done

  # 5：$HOME/projects
  if [ -n "${HOME:-}" ]; then
    local home_proj="${HOME}/projects"
    if [ -d "${home_proj}" ] && [ -w "${home_proj}" ]; then
      _log "clone root 使用 \$HOME/projects: ${home_proj}"
      echo "${home_proj}"
      return 0
    fi
    if [ -w "${HOME}" ] && mkdir -p "${home_proj}" 2>/dev/null; then
      _log "clone root 新建 \$HOME/projects: ${home_proj}"
      echo "${home_proj}"
      return 0
    fi
  fi

  # 6：最终兜底 mktemp -d
  local tmproot
  if tmproot="$(mktemp -d -t "${REPO_NAME}-XXXXXXXX" 2>/dev/null)"; then
    _log "clone root 兜底使用系统临时目录: ${tmproot}"
    # mktemp 直接创建了目标目录（已可作为 clone target 的父 + 子），
    # 但我们只需要"父目录"；所以取其 dirname
    echo "$(dirname "${tmproot}")"
    rmdir "${tmproot}" 2>/dev/null || true
    return 0
  fi

  _err "无法找到可写的 clone 根目录（TRADE_FE_CLONE_ROOT / CATPAW_WORKSPACE_ROOT / WORKSPACE_FOLDER / \$PWD 路径扫描 / \$HOME/projects / mktemp 均失败）"
  exit 17
}

# ─── ensure_workspace ────────────────────────────────────────────────────────
# 参数: mode = auto | local
# 行为:
#   - local + 合法  → 打印仓库根，退出 0
#   - local + 非法  → 打印错误，退出 11
#   - auto  + 合法  → 打印仓库根，退出 0
#   - auto  + 非法  → git clone 到 <clone_root>/trade-fe-rule-{ts}，打印路径，退出 0
#                    clone_root 由 _resolve_clone_root 动态决定（见上），不再写死 /tmp。
ensure_workspace() {
  local mode="${1:-local}"
  if [[ "${mode}" != "auto" && "${mode}" != "local" ]]; then
    _err "ensure_workspace: mode 必须为 auto|local，收到 '${mode}'"
    exit 2
  fi

  local root
  if root="$(_find_repo_root_upward "${PWD}")" && _remote_matches_repo "${root}"; then
    echo "${root}"
    return 0
  fi

  if [ "${mode}" = "local" ]; then
    _err "当前目录不在 ${REPO_PROJECT}/${REPO_NAME} 仓库内。请 cd 到仓库后重试；如需远程自动更新，请改说'自动更新…并提 PR'"
    exit 11
  fi

  # auto + 非法：动态选 clone 根目录
  local clone_root ts target
  clone_root="$(_resolve_clone_root)"
  ts="$(_now_ts)"
  target="${clone_root%/}/${REPO_NAME}-${ts}"

  # 避免极小概率的秒级冲突
  local i=2
  while [ -e "${target}" ]; do
    target="${clone_root%/}/${REPO_NAME}-${ts}-r${i}"
    i=$((i + 1))
    if [ "${i}" -gt 20 ]; then
      _err "clone 目标目录反复冲突（${clone_root}/${REPO_NAME}-${ts}-r*），放弃"
      exit 18
    fi
  done

  _log "workspace 不合法，auto 模式自动 clone 到 ${target}"
  if ! git clone "${REPO_SSH}" "${target}" >&2; then
    _err "git clone 失败：${REPO_SSH} → ${target}"
    exit 12
  fi
  echo "${target}"
}

# ─── sync_master ─────────────────────────────────────────────────────────────
# 在 $PWD 下执行 git fetch + checkout master + pull --ff-only
sync_master() {
  _log "同步 master 分支..."
  if ! git fetch origin >&2; then
    _err "git fetch origin 失败"
    exit 13
  fi
  if ! git checkout "${DEFAULT_BRANCH}" >&2; then
    _err "git checkout ${DEFAULT_BRANCH} 失败"
    exit 13
  fi
  if ! git pull --ff-only origin "${DEFAULT_BRANCH}" >&2; then
    _err "git pull --ff-only 失败（可能非 ff-only，存在本地提交，请清理后重试）"
    exit 13
  fi
}

# ─── resolve_mis ─────────────────────────────────────────────────────────────
# 按优先级取 mis；全部取不到则打印空字符串
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
  # email 中的点号转下划线（mis 通常不含点）
  mis="${mis//./_}"
  echo "${mis}"
}

# ─── compute_branch ──────────────────────────────────────────────────────────
# 参数: mis (可为空)
# 打印: chore/update-knowledge-<mis>-<ts> 或 chore/update-knowledge-<ts>
compute_branch() {
  local mis="${1:-}"
  local ts
  ts="$(_now_ts)"
  if [ -n "${mis}" ]; then
    echo "chore/update-knowledge-${mis}-${ts}"
  else
    echo "chore/update-knowledge-${ts}"
  fi
}

# ─── safe_checkout_new ───────────────────────────────────────────────────────
# 参数: base_branch
# 行为：
#   - 检测 working tree 是否干净；脏则退出 14
#   - 若目标分支本地已存在 → 尝试 -r2 / -r3 / … 直到不冲突
#   - git checkout -b 新分支，打印最终分支名
safe_checkout_new() {
  local base="${1:?need base branch name}"
  if [ -n "$(git status --porcelain)" ]; then
    _err "working tree 存在未提交改动，请先 git stash 或手动处理后重试"
    git status --short >&2
    exit 14
  fi

  local branch="${base}"
  local i=2
  while git show-ref --verify --quiet "refs/heads/${branch}"; do
    branch="${base}-r${i}"
    i=$((i + 1))
    if [ "${i}" -gt 20 ]; then
      _err "同名分支重试 20 次仍冲突，放弃"
      exit 15
    fi
  done

  if ! git checkout -b "${branch}" >&2; then
    _err "git checkout -b ${branch} 失败"
    exit 15
  fi
  echo "${branch}"
}

# ─── commit_scoped ───────────────────────────────────────────────────────────
# 参数:
#   $1 group
#   $2 kinds (逗号分隔, 如 "glossary,business-rules" 或 "all")
#   $3 mis (可空)
#   $4 msg_body_file (commit message 正文，来自调用方拼好)
#   $5..$N 变更文件相对路径列表（scope 内才允许 add）
#
# 行为: git add <files...> + git commit -m "<title>" -m "$(cat msg_body_file)"
commit_scoped() {
  if [ $# -lt 5 ]; then
    _err "commit_scoped 需要至少 5 个参数: group kinds mis msg_body_file file1 [file2...]"
    exit 2
  fi
  local group="$1"; shift
  local kinds="$1"; shift
  local mis="$1"; shift
  local msg_file="$1"; shift

  if [ ! -f "${msg_file}" ]; then
    _err "msg_body_file 不存在: ${msg_file}"
    exit 2
  fi

  local today
  today="$(date +"%Y%m%d")"
  local tag="${mis:+${mis}@}${today}"
  local title="chore(knowledge): 更新 ${group} ${kinds} [${tag}]"

  _log "git add（仅 scope 内文件，严禁全量 add）: $*"
  # shellcheck disable=SC2068
  git add -- $@ >&2

  if git diff --cached --quiet; then
    _err "staged 区为空，没有需要提交的变更"
    exit 16
  fi

  _log "git commit: ${title}"
  git commit -m "${title}" -F "${msg_file}" >&2
  echo "${title}"
}

# ─── push_current_branch ─────────────────────────────────────────────────────
push_current_branch() {
  local branch
  branch="$(git rev-parse --abbrev-ref HEAD)"
  _log "git push origin ${branch}"
  if ! git push --set-upstream origin "${branch}" >&2; then
    _err "git push 失败（网络/权限）。已保留本地 commit，恢复命令：cd $(pwd) && git push origin ${branch}"
    exit 17
  fi
  echo "${branch}"
}

# ─── pr_create_wrapper ───────────────────────────────────────────────────────
# 参数:
#   $1 group
#   $2 kinds
#   $3 mis (可空)
#   $4 branch (源分支)
#   $5 title_file (PR 标题，一行)
#   $6 desc_file  (PR description，四段式 markdown 文件)
#
# 行为：调用 _code_.sh 中的 pr_create，成功打印 PR URL；失败打印 fallback URL
pr_create_wrapper() {
  if [ $# -lt 6 ]; then
    _err "pr_create_wrapper 需要 6 个参数: group kinds mis branch title_file desc_file"
    exit 2
  fi
  local group="$1" kinds="$2" mis="$3" branch="$4" title_file="$5" desc_file="$6"

  local title desc
  title="$(head -n 1 "${title_file}")"
  desc="$(cat "${desc_file}")"

  local body
  body=$(jq -n \
    --arg title "${title}" \
    --arg desc "${desc}" \
    --arg branch "${branch}" \
    --arg repo "${REPO_NAME}" \
    --arg project "${REPO_PROJECT}" \
    --arg target "${DEFAULT_BRANCH}" \
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
      deleteSourceRefAfterMerge: false,
      reviewers: []
    }')

  _log "pr_create: ${REPO_PROJECT}/${REPO_NAME} ${branch} → ${DEFAULT_BRANCH}"
  local resp pr_id
  # pr_create 由 _code_.sh 提供
  resp="$(pr_create "${REPO_PROJECT}" "${REPO_NAME}" "${body}" || true)"
  pr_id="$(echo "${resp}" | jq -r '.id // empty' 2>/dev/null || true)"

  if [ -z "${pr_id}" ] || [ "${pr_id}" = "null" ]; then
    _err "pr_create API 失败，返回: ${resp}"
    _err "fallback：请手动在浏览器中创建 PR"
    fallback_pr_url "${branch}"
    exit 18
  fi

  local pr_url="${CODE_BASE_URL}/code/repo-detail/${REPO_PROJECT}/${REPO_NAME}/pr/detail/${pr_id}"
  _log "✅ PR 创建成功: ${pr_url}"
  echo "${pr_url}"
}

# ─── fallback_pr_url ─────────────────────────────────────────────────────────
# 提供手动提 PR 的 URL（push 成功但 pr_create API 失败时使用）
fallback_pr_url() {
  local branch="${1:?need branch}"
  echo "${CODE_BASE_URL}/code/repo-detail/${REPO_PROJECT}/${REPO_NAME}/pr/create?sourceBranch=${branch}&targetBranch=${DEFAULT_BRANCH}"
}

# ─── 主入口 ───────────────────────────────────────────────────────────────────
# 用法: bash auto-pr.sh <subcommand> [args...]
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  if [ $# -lt 1 ]; then
    cat >&2 <<EOF
用法: bash auto-pr.sh <subcommand> [args...]

子命令:
  ensure_workspace <auto|local>
  sync_master
  resolve_mis
  compute_branch [mis]
  safe_checkout_new <base_branch>
  commit_scoped <group> <kinds> <mis> <msg_body_file> <file1> [file2...]
  push_current_branch
  pr_create_wrapper <group> <kinds> <mis> <branch> <title_file> <desc_file>
  fallback_pr_url <branch>

示例（典型 auto 模式完整串联由 agent 按阶段分步调用）:
  1) root=\$(bash auto-pr.sh ensure_workspace auto); cd "\${root}"
  2) bash auto-pr.sh sync_master
  3) mis=\$(bash auto-pr.sh resolve_mis)
  4) base=\$(bash auto-pr.sh compute_branch "\${mis}")
  5) branch=\$(bash auto-pr.sh safe_checkout_new "\${base}")
  6) [Agent 写盘 + validate]
  7) bash auto-pr.sh commit_scoped gc "glossary,business-rules" "\${mis}" msg.txt \\
         context-docs/glossary/gc.md context-docs/business-rules/gc.md
  8) bash auto-pr.sh push_current_branch
  9) pr_url=\$(bash auto-pr.sh pr_create_wrapper gc "glossary,business-rules" "\${mis}" \\
         "\${branch}" title.txt desc.md)
EOF
    exit 1
  fi
  sub="$1"; shift
  "${sub}" "$@"
fi
