#!/usr/bin/env bash
# =============================================================================
# trade-kb · _code_.sh
#
# 美团 Code 平台（Bitbucket Server）REST API 封装。
# 供 auto-pr.sh source 调用，也可单独执行：bash _code_.sh <func> [args...]
#
# API 文档: https://yapi.sankuai.com/project/20899/interface/api
# =============================================================================
set -euo pipefail

# ─── 全局配置 ────────────────────────────────────────────────────────────────
_CODE_BASE="http://git.sankuai.com"
# hfe_stash 服务账号（已是 base64(user:pass) 格式，直接使用，不再 decode→re-encode）
_AH="Authorization: Basic aGZlX3N0YXNoOkVWYXp0cEA5Mzg="
_CT="Content-Type: application/json"

# ─── 通用请求函数 ────────────────────────────────────────────────────────────
_post() {
  local url="$1" data="${2:-{}}"
  local _body_file _http_code
  _body_file="$(mktemp)"
  # 使用 printf + stdin (-d @-) 传请求体，避免 shell 变量 "${data}" 在多层函数传参时
  # 破坏含换行符或中文的 JSON（直接 -d "${data}" 会导致 400 空响应）
  _http_code=$(printf '%s' "${data}" | curl -s \
    --connect-timeout 5 \
    --max-time 30 \
    -o "${_body_file}" \
    -w "%{http_code}" \
    -X POST "${_CODE_BASE}${url}" \
    -H "${_AH}" -H "${_CT}" -H "Accept: application/json" \
    -d @-)
  if [[ "${_http_code}" != 2* ]]; then
    echo "[_code_][ERROR] HTTP ${_http_code}: $(cat "${_body_file}")" >&2
    rm -f "${_body_file}"
    return 1
  fi
  cat "${_body_file}"
  rm -f "${_body_file}"
}

# ─── Pull Request ─────────────────────────────────────────────────────────────
# pr_create <project> <repo> <json_body>
# json_body 示例见 auto-pr.sh pr_create_wrapper
pr_create() {
  local project="$1" repo="$2" body="$3"
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests" "${body}"
}

# ─── 主入口 ───────────────────────────────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  if [ $# -lt 1 ]; then
    echo "用法: bash _code_.sh <func> [args...]"
    echo "可用函数: pr_create <project> <repo> <json_body>"
    exit 1
  fi
  func="$1"; shift
  "${func}" "$@"
fi
