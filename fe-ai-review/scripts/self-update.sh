#!/usr/bin/env bash
# self-update.sh — 自动检查并更新 fe-ai-review skill
#
# 行为：
#   - 检测到有更新 → 自动执行 mtskills pull，输出一行结论
#   - 已是最新     → 输出一行结论
#   - mtskills 未安装 → 内网环境下自动安装（Node 版本达标时），再继续检查更新
#   - 任何异常情况 → 输出一行结论
#   - 始终 exit 0，不阻塞后续流程
#
# 版本判断策略：
#   1. 优先比对本地 SKILL.md frontmatter 的 version 字段与远端版本（需维护者手动在 frontmatter 写 version: x.x.x）
#   2. 无 version 字段时（当前默认路径），回退到本地 SKILL.md 文件 mtime vs 远端 updated 时间戳

set -uo pipefail

SKILL_NAME="fe-ai-review"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_MD="$SKILL_DIR/SKILL.md"
MIN_NODE_MAJOR=20
MTSKILLS_REGISTRY="http://r.npm.sankuai.com"

# ── 工具函数 ──────────────────────────────────────────────────────────────────

node_major_version() {
  # 输出形如 "20"；拿不到版本号时输出空
  local ver
  ver=$(node -v 2>/dev/null) || { echo ""; return; }
  echo "${ver#v}" | cut -d. -f1
}

# 确保当前 PATH 下有满足 MIN_NODE_MAJOR 的 node 可用：
#   1. 先看当前 `node -v` 是否达标，达标直接返回
#   2. 不达标或没有 node → 尝试 nvm，找一个达标版本 `nvm use`
#   3. 都没有 → 返回非 0，调用方负责跳过后续安装
ensure_node_ready() {
  local major
  major=$(node_major_version)
  if [[ -n "$major" && "$major" -ge "$MIN_NODE_MAJOR" ]]; then
    return 0
  fi

  [[ -s "$HOME/.nvm/nvm.sh" ]] || return 1
  # shellcheck disable=SC1091
  source "$HOME/.nvm/nvm.sh" &>/dev/null || return 1

  # 只取已安装版本（行尾带 `*` 标记），排除 lts/* 等未安装的别名映射行
  local candidate
  candidate=$(nvm ls --no-colors 2>/dev/null \
    | grep -E '^\s*(->)?\s*v[0-9]+\.[0-9]+\.[0-9]+\s*\*\s*$' \
    | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' \
    | sed 's/^v//' \
    | awk -F. -v min="$MIN_NODE_MAJOR" '$1 >= min' \
    | sort -t. -k1,1n -k2,2n -k3,3n \
    | tail -1)
  [[ -n "$candidate" ]] || return 1

  nvm use "$candidate" &>/dev/null || return 1
  major=$(node_major_version)
  [[ -n "$major" && "$major" -ge "$MIN_NODE_MAJOR" ]]
}

# mtskills 是否真的可用：命令不存在，或存在但因 Node 版本不兼容执行报错，都算不可用
mtskills_healthy() {
  mtskills --version &>/dev/null
}

# 优先用 GNU timeout/gtimeout；macOS 默认都没有时直接跑（npm 自身有网络超时兜底）
run_with_timeout() {
  local seconds="$1"; shift
  if command -v timeout &>/dev/null; then
    timeout "$seconds" "$@"
  elif command -v gtimeout &>/dev/null; then
    gtimeout "$seconds" "$@"
  else
    "$@"
  fi
}

# mtskills 不可用时的内网自动安装；成功返回 0，任何一步失败返回非 0
install_mtskills() {
  ensure_node_ready || return 1
  command -v npm &>/dev/null || return 1
  run_with_timeout 60 npm i -g @mtfe/mtskills --registry="$MTSKILLS_REGISTRY" &>/dev/null
}

get_local_version() {
  [[ -f "$SKILL_MD" ]] || { echo ""; return; }
  awk '/^---/{found++; next} found==1' "$SKILL_MD" \
    | grep -E '^version:' | head -1 \
    | sed -E "s/^version:[[:space:]]*['\"]?([^'\"[:space:]]+)['\"]?/\1/"
}

get_local_mtime_ms() {
  [[ -f "$SKILL_MD" ]] || { echo "0"; return; }
  if stat --version &>/dev/null 2>&1; then
    echo $(( $(stat -c %Y "$SKILL_MD") * 1000 ))
  else
    echo $(( $(stat -f %m "$SKILL_MD") * 1000 ))
  fi
}

compare_versions() {
  local v1="${1#v}" v2="${2#v}"
  IFS='.' read -ra p1 <<< "$v1"
  IFS='.' read -ra p2 <<< "$v2"
  local max_len=$(( ${#p1[@]} > ${#p2[@]} ? ${#p1[@]} : ${#p2[@]} ))
  for (( i=0; i<max_len; i++ )); do
    local a="${p1[$i]:-0}" b="${p2[$i]:-0}"
    (( a < b )) && echo "lt" && return
    (( a > b )) && echo "gt" && return
  done
  echo "eq"
}

# ── 主流程（任何异常直接 exit 0） ─────────────────────────────────────────────

{
  # 0. 开发目录检测：存在 _authoring.md 说明是维护者本地开发环境，跳过更新（避免覆盖源码）
  if [[ -f "$SKILL_DIR/_authoring.md" ]]; then
    echo "[fe-ai-review] 开发目录，跳过自动更新"
    exit 0
  fi

  # 1. mtskills 健康检查；不可用（未安装 / 存在但 Node 版本不兼容）时尝试内网自动安装
  #    Node < 20 或安装失败则跳过，不阻塞
  if ! mtskills_healthy; then
    if install_mtskills && mtskills_healthy; then
      echo "[fe-ai-review] mtskills 不可用，已自动安装/修复完成，继续检查版本"
    else
      echo "[fe-ai-review] 版本检查跳过（mtskills 不可用，自动安装未完成，可手动执行：npm i -g @mtfe/mtskills --registry=$MTSKILLS_REGISTRY）"
      exit 0
    fi
  fi

  # 2. 获取远端信息
  SEARCH_OUTPUT=$(mtskills search "$SKILL_NAME" 2>/dev/null || true)
  if [[ -z "$SEARCH_OUTPUT" ]]; then
    echo "[fe-ai-review] 版本检查跳过（无法获取远端信息）"
    exit 0
  fi

  REMOTE_UPDATED_MS=$(echo "$SEARCH_OUTPUT" | grep -E '^updated:' | head -1 | grep -oE '[0-9]+' || echo "")
  REMOTE_VERSION=$(echo "$SEARCH_OUTPUT" | grep -E '^version:' | head -1 \
    | sed -E "s/^version:[[:space:]]*['\"]?([^'\"[:space:]]+)['\"]?/\1/" || echo "")

  # 3. 判断是否需要更新
  HAS_UPDATE=false
  LOCAL_VERSION=$(get_local_version)

  if [[ -n "$LOCAL_VERSION" && -n "$REMOTE_VERSION" ]]; then
    CMP=$(compare_versions "$LOCAL_VERSION" "$REMOTE_VERSION")
    [[ "$CMP" == "lt" ]] && HAS_UPDATE=true
  elif [[ -n "$REMOTE_UPDATED_MS" ]]; then
    LOCAL_MTIME_MS=$(get_local_mtime_ms)
    (( REMOTE_UPDATED_MS > LOCAL_MTIME_MS )) && HAS_UPDATE=true
  else
    echo "[fe-ai-review] 版本检查跳过（版本信息不足）"
    exit 0
  fi

  # 4. 执行更新或输出已最新
  if [[ "$HAS_UPDATE" == "true" ]]; then
    if mtskills pull "$SKILL_NAME" >/dev/null 2>&1; then
      echo "[fe-ai-review] ✅ 已自动更新到最新版本，继续执行"
    else
      echo "[fe-ai-review] ⚠️ 自动更新失败，继续使用当前版本（可手动执行：mtskills pull fe-ai-review）"
    fi
  else
    echo "[fe-ai-review] ✅ 已是最新版本"
  fi

} || {
  # 任何未捕获异常
  echo "[fe-ai-review] 版本检查异常，跳过"
}

exit 0
