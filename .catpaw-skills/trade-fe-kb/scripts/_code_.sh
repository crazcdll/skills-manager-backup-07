#!/usr/bin/env bash
# =============================================================================
# trade-kb · _code_.sh
#
# 美团 Code 平台（Bitbucket Server）REST API 封装。
# 供 auto-pr.sh source 调用，也可单独执行：bash _code_.sh <func> [args...]
#
# API 文档: xxx
# =============================================================================
set -euo pipefail

# ─── 全局配置 ────────────────────────────────────────────────────────────────
# hfe_stash 服务账号：现成的 base64(user:pass)，直接使用，不再解码或重新编码。
readonly _AH="Authorization: Basic aGZlX3N0YXNoOkVWYXp0cEA5Mzg="
readonly CODE_API_BASE="https://git.sankuai.com"
readonly REGISTRY_URL="https://dev.sankuai.com/rest/api/1.0/projects/nibfe/repos/trade-fe-rule/raw/_governance/kb-routers/index.yaml"
readonly CONTENT_TYPE="Content-Type: application/json"

_code_error() { printf '[_code_][ERROR] %s\n' "$*" >&2; }

_curl_auth_config() {
  local config
  config="$(mktemp)" || {
    _code_error 'Cannot create curl authentication file.'
    return 1
  }
  chmod 600 "$config" || {
    rm -f "$config"
    _code_error 'Cannot protect curl authentication file.'
    return 1
  }
  # 两种 HTTP 请求共用原认证值；临时配置避免凭据出现在 curl 进程参数中。
  printf 'header = "%s"\n' "$_AH" > "$config" || {
    rm -f "$config"
    _code_error 'Cannot write curl authentication file.'
    return 1
  }
  printf '%s' "$config"
}

# ─── 通用请求函数 ────────────────────────────────────────────────────────────
_post() (
  local url="$1" data="${2:-}" auth_config='' body_file='' http_code
  [ -n "$data" ] || data='{}'
  trap 'rm -f -- "$auth_config" "$body_file"' EXIT
  auth_config="$(_curl_auth_config)" || return 1
  body_file="$(mktemp)" || {
    _code_error 'Cannot create response file.'
    return 1
  }
  # 使用 printf + stdin (-d @-) 传请求体，避免 shell 变量 "${data}" 在多层函数传参时
  # 破坏含换行符或中文的 JSON（直接 -d "${data}" 会导致 400 空响应）
  if ! http_code=$(printf '%s' "${data}" | curl -s \
    --config "$auth_config" \
    --connect-timeout 5 \
    --max-time 30 \
    -o "${body_file}" \
    -w "%{http_code}" \
    -X POST "${CODE_API_BASE}${url}" \
    -H "${CONTENT_TYPE}" -H "Accept: application/json" \
    -d @-); then
    _code_error 'Code API transport failed.'
    return 1
  fi
  if [[ "${http_code}" != 2* ]]; then
    _code_error "Code API HTTP ${http_code}."
    return 1
  fi
  cat "${body_file}"
)

# registry_get: output the published YAML unchanged; diagnostics never include the response or credentials.
registry_get() (
  local body='' auth_config='' status curl_status=0
  trap 'rm -f -- "$auth_config" "$body"' EXIT
  auth_config="$(_curl_auth_config)" || return 1
  body="$(mktemp)" || return 1
  status=$(curl -s --connect-timeout 5 --max-time 30 \
    --config "$auth_config" \
    -G --data-urlencode 'at=refs/heads/release/main' \
    -H 'Accept: text/plain' \
    -o "$body" -w '%{http_code}' \
    "${REGISTRY_URL}") || curl_status=$?
  if [ "$curl_status" -ne 0 ]; then
    printf '[_code_][ERROR] registry transport failed (curl %s)\n' "$curl_status" >&2
    return 1
  fi
  if [ "$status" != 200 ]; then
    printf '[_code_][ERROR] registry HTTP %s\n' "$status" >&2
    return 1
  fi
  if ! LC_ALL=C grep -q '[^[:space:]]' "$body"; then
    printf '[_code_][ERROR] registry response is empty\n' >&2
    return 1
  fi
  if LC_ALL=C grep -Eiq '<!doctype[[:space:]]+html|<html([[:space:]>])|<form([[:space:]>])' "$body"; then
    printf '[_code_][ERROR] registry response is HTML\n' >&2
    return 1
  fi
  cat "$body"
)

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
    echo "可用函数: registry_get | pr_create <project> <repo> <json_body>"
    exit 1
  fi
  func="$1"; shift
  "${func}" "$@"
fi
