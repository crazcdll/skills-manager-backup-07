#!/usr/bin/env bash
# =============================================================================
# Code 平台 Git HTTP API 封装脚本
# 基于 dev.sankuai.com Code 平台 REST API
# 所有操作使用 hfe_stash 服务账号
# API 文档: https://yapi.sankuai.com/project/20899/interface/api
# =============================================================================
set -euo pipefail
# ─── 全局配置 ────────────────────────────────────────────────────────────────
_U="http://git.sankuai.com"
_AH="Authorization: Basic $(echo -n "$(echo -n "aGZlX3N0YXNoOkVWYXp0cEA5Mzg=" | base64 -d)" | base64)"
CONTENT_TYPE="Content-Type: application/json"
# ─── 通用请求函数 ────────────────────────────────────────────────────────────
# 通用 GET 请求
_get() {
  local url="$1"
  curl -s -X GET "${_U}${url}" \
    -H "${_AH}" \
    -H "Accept: application/json"
}
# 通用 POST 请求
_post() {
  local url="$1"
  local empty_json='{}'
  local data="${2:-$empty_json}"
  curl -s -X POST "${_U}${url}" \
    -H "${_AH}" \
    -H "${CONTENT_TYPE}" \
    -H "Accept: application/json" \
    -d "${data}"
}
# 通用 PUT 请求
_put() {
  local url="$1"
  local empty_json='{}'
  local data="${2:-$empty_json}"
  curl -s -X PUT "${_U}${url}" \
    -H "${_AH}" \
    -H "${CONTENT_TYPE}" \
    -H "Accept: application/json" \
    -d "${data}"
}
# 通用 DELETE 请求
_delete() {
  local url="$1"
  local data="${2:-}"
  if [ -n "${data}" ]; then
    curl -s -X DELETE "${_U}${url}" \
      -H "${_AH}" \
      -H "${CONTENT_TYPE}" \
      -H "Accept: application/json" \
      -d "${data}"
  else
    curl -s -X DELETE "${_U}${url}" \
      -H "${_AH}" \
      -H "Accept: application/json"
  fi
}
# =============================================================================
# Pull Request 相关接口
# =============================================================================
# 获取仓库 PullRequest 详情
# 用法: pr_get_detail <project> <repo> <pr_id>
pr_get_detail() {
  local project="$1" repo="$2" pr_id="$3"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}"
}
# 获取仓库 PullRequest 列表
# 用法: pr_list <project> <repo> [state] [limit] [start]
# state: OPEN | MERGED | DECLINED (默认 OPEN)
pr_list() {
  local project="$1" repo="$2"
  local state="${3:-OPEN}" limit="${4:-25}" start="${5:-0}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests?state=${state}&limit=${limit}&start=${start}"
}
# 搜索仓库 PullRequest 列表
# 用法: pr_search <project> <repo> [author] [state] [source] [target] [filterTitle] [limit] [start]
pr_search() {
  local project="$1" repo="$2"
  local author="${3:-}" state="${4:-}" source="${5:-}" target="${6:-}"
  local filterTitle="${7:-}" limit="${8:-25}" start="${9:-0}"
  local query="limit=${limit}&start=${start}"
  [ -n "${author}" ] && query="${query}&author=${author}"
  [ -n "${state}" ] && query="${query}&state=${state}"
  [ -n "${source}" ] && query="${query}&source=${source}"
  [ -n "${target}" ] && query="${query}&target=${target}"
  [ -n "${filterTitle}" ] && query="${query}&filterTitle=${filterTitle}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/search?${query}"
}
# 创建 PullRequest
# 用法: pr_create <project> <repo> <json_body>
# json_body 示例:
# {
#   "title": "PR标题",
#   "description": "PR描述",
#   "fromRef": {
#     "id": "refs/heads/feature-branch",
#     "displayId": "feature-branch",
#     "repository": { "slug": "repo-name", "project": { "key": "PROJECT" } }
#   },
#   "toRef": {
#     "id": "refs/heads/master",
#     "displayId": "master",
#     "repository": { "slug": "repo-name", "project": { "key": "PROJECT" } }
#   },
#   "deleteSourceRefAfterMerge": false,
#   "reviewers": [{"user": {"name": "reviewer_mis"}}]
# }
pr_create() {
  local project="$1" repo="$2" body="$3"
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests" "${body}"
}
# 更新 PullRequest (v2.0)
# 用法: pr_update <project> <repo> <pr_id> <json_body>
pr_update() {
  local project="$1" repo="$2" pr_id="$3" body="$4"
  _put "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}" "${body}"
}
# 更新 PullRequest (latest 版本，支持 mergableState)
# 用法: pr_update_latest <project> <repo> <pr_id> <json_body>
pr_update_latest() {
  local project="$1" repo="$2" pr_id="$3" body="$4"
  _put "/rest/api/latest/projects/${project}/repos/${repo}/pull-requests/${pr_id}" "${body}"
}
# Approve PullRequest
# 用法: pr_approve <project> <repo> <pr_id>
pr_approve() {
  local project="$1" repo="$2" pr_id="$3"
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/approve" "{}"
}
# 合并 PullRequest
# 用法: pr_merge <project> <repo> <pr_id>
pr_merge() {
  local project="$1" repo="$2" pr_id="$3"
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/merge" "{}"
}
# 关闭(Decline) PullRequest
# 用法: pr_decline <project> <repo> <pr_id> [version]
pr_decline() {
  local project="$1" repo="$2" pr_id="$3"
  local version="${4:-}"
  local query=""
  [ -n "${version}" ] && query="?version=${version}"
  _post "/rest/api/latest/projects/${project}/repos/${repo}/pull-requests/${pr_id}/decline${query}" "{}"
}
# 重新打开 PullRequest
# 用法: pr_reopen <project> <repo> <pr_id> [version]
pr_reopen() {
  local project="$1" repo="$2" pr_id="$3"
  local version="${4:-}"
  local query=""
  [ -n "${version}" ] && query="?version=${version}"
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/reopen${query}" "{}"
}
# 将 draft PullRequest 转成 normal
# 用法: pr_draft_to_normal <project> <repo> <pr_id>
pr_draft_to_normal() {
  local project="$1" repo="$2" pr_id="$3"
  _put "/rest/api/latest/projects/${project}/repos/${repo}/pull-requests/${pr_id}/toPullrequest" "{}"
}
# 获取 PullRequest 的变更文件列表
# 用法: pr_get_changes <project> <repo> <pr_id> [limit] [start]
pr_get_changes() {
  local project="$1" repo="$2" pr_id="$3"
  local limit="${4:-500}" start="${5:-0}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/changes?limit=${limit}&start=${start}"
}
# 获取 PR 文件 diff 内容
# 用法: pr_get_file_diff <project> <repo> <pr_id> <file_path>
# 注意: pr_id 是 PR 在仓库下的 ID（数字较小），不是全局 ID
pr_get_file_diff() {
  local project="$1" repo="$2" pr_id="$3" file_path="$4"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/diff/${file_path}"
}
# 获取 PullRequest merge 状态
# 用法: pr_get_merge_status <project> <repo> <pr_id>
pr_get_merge_status() {
  local project="$1" repo="$2" pr_id="$3"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/merge"
}
# 获取 PullRequest 的 merge-status (latest 版本)
# 用法: pr_get_merge_status_latest <project> <repo> <pr_id>
pr_get_merge_status_latest() {
  local project="$1" repo="$2" pr_id="$3"
  _get "/rest/api/latest/projects/${project}/repos/${repo}/pull-requests/${pr_id}/merge-status"
}
# 获取 PullRequest 的 commit 列表
# 用法: pr_get_commits <project> <repo> <pr_id> [limit] [start]
pr_get_commits() {
  local project="$1" repo="$2" pr_id="$3"
  local limit="${4:-25}" start="${5:-0}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/commits?limit=${limit}&start=${start}"
}
# 获取 PullRequest 动态列表
# 用法: pr_get_activities <project> <repo> <pr_id> [limit] [start]
pr_get_activities() {
  local project="$1" repo="$2" pr_id="$3"
  local limit="${4:-25}" start="${5:-0}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/activities?limit=${limit}&start=${start}"
}
# 获取 PR 评审意见
# 用法: pr_get_assignments <project> <repo> <pr_id> [path] [states]
# states: open | resolved
pr_get_assignments() {
  local project="$1" repo="$2" pr_id="$3"
  local path="${4:-}" states="${5:-}"
  local query=""
  [ -n "${path}" ] && query="path=${path}"
  [ -n "${states}" ] && query="${query:+${query}&}states=${states}"
  [ -n "${query}" ] && query="?${query}"
  _get "/rest/api/5.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/assignments${query}"
}
# 新增 PR 评论（普通评论）
# 用法: pr_add_comment <project> <repo> <pr_id> <text>
pr_add_comment() {
  local project="$1" repo="$2" pr_id="$3" text="$4"
  local body
  body=$(jq -n --arg text "${text}" '{"text": $text}')
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/comments" "${body}"
}
# 新增 PR 行内评论（关联到具体文件和行号）
#
# ⚠️ 重要提示 ⚠️
# 本函数必须使用 bash 执行，不能用 sh 执行！
# 正确用法: bash references/code-api.sh pr_add_inline_comment ...
#
# 用法: pr_add_inline_comment <project> <repo> <pr_id> <text> <file_path> <line> <since_commit> <until_commit> [line_type] [file_type]
#
# 必需参数 (8个):
#   project      - 仓库组名 (如 "nibfe")
#   repo         - 仓库名 (如 "gc-group-order-submit")
#   pr_id        - PR ID (仓库内 ID，如 "822")
#   text         - 评论内容 (支持 Markdown)
#   file_path    - 文件路径 (与 diff 中的路径一致，如 "packages/pages/submit/constData.groovy")
#   line         - 行号 (新文件中的行号，即 destination 行号)
#   since_commit - diff 接口返回的 fromHash (目标分支 commit SHA)
#   until_commit - diff 接口返回的 toHash (PR 有效合并 commit SHA)
#
# 可选参数 (2个):
#   line_type    - 行类型: ADDED (默认) | REMOVED | CONTEXT
#   file_type    - 文件类型: TO (默认，新文件) | FROM (旧文件)
#
# ⚠️ API 参数值固定，不可更改:
#   type 必须为 "assignment" (不能是 "INLINE")
#   fileType 必须为 "TO" 或 "FROM" (不能是 "ADDED")
#
# 示例:
#   bash references/code-api.sh pr_add_inline_comment \
#     "nibfe" "gc-group-order-submit" "822" \
#     "[P1] 建议使用安全导航操作符" \
#     "packages/pages/submit/constData.groovy" 107 \
#
pr_add_inline_comment() {
  # 参数校验
  if [ $# -lt 8 ]; then
    echo "错误: pr_add_inline_comment 需要至少 8 个参数，当前传入 $# 个" >&2
    echo "用法: pr_add_inline_comment <project> <repo> <pr_id> <text> <file_path> <line> <since_commit> <until_commit> [line_type] [file_type]" >&2
    echo "" >&2
    echo "必需参数:" >&2
    echo "  project      - 仓库组名" >&2
    echo "  repo         - 仓库名" >&2
    echo "  pr_id        - PR ID (仓库内 ID)" >&2
    echo "  text         - 评论内容" >&2
    echo "  file_path    - 文件路径" >&2
    echo "  line         - 行号" >&2
    echo "  since_commit - fromHash (目标分支 commit SHA)" >&2
    echo "  until_commit - toHash (PR 有效合并 commit SHA)" >&2
    echo "" >&2
    echo "可选参数:" >&2
    echo "  line_type    - ADDED (默认) | REMOVED | CONTEXT" >&2
    echo "  file_type    - TO (默认) | FROM" >&2
    return 1
  fi
  local project="$1" repo="$2" pr_id="$3" text="$4"
  local file_path="$5" line="$6"
  local since_commit="$7" until_commit="$8"
  local line_type="${9:-ADDED}" file_type="${10:-TO}"
  # 参数值校验
  if [[ ! "${line_type}" =~ ^(ADDED|REMOVED|CONTEXT)$ ]]; then
    echo "错误: line_type 必须是 ADDED、REMOVED 或 CONTEXT，当前值: ${line_type}" >&2
    return 1
  fi
  if [[ ! "${file_type}" =~ ^(TO|FROM)$ ]]; then
    echo "错误: file_type 必须是 TO 或 FROM，当前值: ${file_type}" >&2
    echo "提示: TO 表示新文件，FROM 表示旧文件。不能使用 ADDED 等其他值！" >&2
    return 1
  fi
  local body
  body=$(jq -n \
    --arg text "${text}" \
    --arg path "${file_path}" \
    --argjson line "${line}" \
    --arg lineType "${line_type}" \
    --arg fileType "${file_type}" \
    --arg prId "${pr_id}" \
    --arg sinceRev "${since_commit}" \
    --arg untilRev "${until_commit}" \
    '{
      "anchor": {
        "path": $path,
        "line": $line,
        "fileType": $fileType,
        "lineType": $lineType,
        "ignoreWhiteSpace": false,
        "commitRange": {
          "id": $prId,
          "sinceRevision": {"id": $sinceRev},
          "untilRevision": {"id": $untilRev}
        }
      },
      "mentions": [],
      "text": $text,
      "labels": [],
      "type": "assignment",
      "isTrusted": true
    }')
  local response
  response=$(_post "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/comments" "${body}")
  # 检查是否成功
  local comment_id
  comment_id=$(echo "${response}" | jq -r '.id // empty')
  if [ -n "${comment_id}" ]; then
    echo "✅ 行内评论添加成功，评论 ID: ${comment_id}"
  else
    local error_msg
    error_msg=$(echo "${response}" | jq -r '.errors[0].message // .message // "未知错误"')
    echo "❌ 行内评论添加失败: ${error_msg}" >&2
    echo "请求体: ${body}" >&2
  fi
  echo "${response}"
}
# 删除 PR 评论
# 用法: pr_delete_comment <project> <repo> <pr_id> <comment_id>
pr_delete_comment() {
  local project="$1" repo="$2" pr_id="$3" comment_id="$4"
  _delete "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${pr_id}/comments/${comment_id}"
}
# 获取 PR 的 commit 范围（用于行内评论的 commitRange）
# 用法: pr_get_commit_range <project> <repo> <pr_id>
# 返回: since_commit until_commit (空格分隔)
# since_commit = diff 接口的 fromHash（目标分支 commit）
# until_commit = diff 接口的 toHash（PR 的有效合并 commit）
pr_get_commit_range() {
  local project="$1" repo="$2" pr_id="$3"
  local changes
  changes=$(pr_get_changes "${project}" "${repo}" "${pr_id}" 1)
  local first_file
  first_file=$(echo "${changes}" | jq -r '.values[0].path.toString // (.values[0].path.components | join("/")) // empty')
  if [ -z "${first_file}" ]; then
    echo "ERROR: PR 没有变更文件，无法获取 commit 范围" >&2
    return 1
  fi
  local diff_result
  diff_result=$(pr_get_file_diff "${project}" "${repo}" "${pr_id}" "${first_file}")
  local since_commit until_commit
  since_commit=$(echo "${diff_result}" | jq -r '.fromHash // empty')
  until_commit=$(echo "${diff_result}" | jq -r '.toHash // empty')
  if [ -z "${since_commit}" ] || [ -z "${until_commit}" ]; then
    echo "ERROR: 无法从 diff 接口获取 commit 范围" >&2
    return 1
  fi
  echo "${since_commit} ${until_commit}"
}
# =============================================================================
# Commit Build 状态相关接口
# =============================================================================
# 获取 commit build 结果信息
# 用法: build_get_stats <commit_id> [includeUnique]
build_get_stats() {
  local commit_id="$1"
  local includeUnique="${2:-}"
  local query=""
  [ -n "${includeUnique}" ] && query="?includeUnique=${includeUnique}"
  _get "/rest/build-status/2.0/commits/stats/${commit_id}${query}"
}
# 获取 commit build 结果列表
# 用法: build_get_list <commit_id>
build_get_list() {
  local commit_id="$1"
  _get "/rest/build-status/2.0/commits/${commit_id}"
}
# 获取多个 commits 的 build 结果信息
# 用法: build_get_multi_stats
build_get_multi_stats() {
  _get "/rest/build-status/2.0/commits/stats"
}
# 回调 commit build 结果
# 用法: build_callback <commit_id> <json_body>
# json_body 示例:
# {
#   "state": "SUCCESSFUL",
#   "key": "build-key",
#   "name": "Build Name",
#   "url": "https://ci.example.com/build/123",
#   "description": "Build passed"
# }
build_callback() {
  local commit_id="$1" body="$2"
  _post "/rest/build-status/2.0/commits/${commit_id}" "${body}"
}
# =============================================================================
# Repository 仓库相关接口
# =============================================================================
# 获取仓库详细信息
# 用法: repo_get_detail <project> <repo>
repo_get_detail() {
  local project="$1" repo="$2"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}"
}
# 获取仓库详细信息 (branch-utils 版本)
# 用法: repo_get_detail_v2 <project> <repo>
repo_get_detail_v2() {
  local project="$1" repo="$2"
  _get "/rest/branch-utils/2.0/projects/${project}/repos/${repo}"
}
# 获取仓库组下用户有权限的仓库列表
# 用法: repo_list <project> [limit] [start]
repo_list() {
  local project="$1"
  local limit="${2:-25}" start="${3:-0}"
  _get "/rest/api/2.0/projects/${project}/repos?limit=${limit}&start=${start}"
}
# 创建仓库
# 用法: repo_create <project> <json_body>
repo_create() {
  local project="$1" body="$2"
  _post "/rest/api/2.0/projects/${project}/repos" "${body}"
}
# 模糊搜索仓库
# 用法: repo_search <keyword> [limit] [start]
repo_search() {
  local keyword="$1"
  local limit="${2:-10}" start="${3:-0}"
  _get "/rest/api/2.0/search/REPOSITORY/open-fast-search?keyword=${keyword}&limit=${limit}&start=${start}"
}
# 获取仓库的分支列表
# 用法: repo_get_branches <project> <repo> [filterText] [limit] [start]
repo_get_branches() {
  local project="$1" repo="$2"
  local filterText="${3:-}" limit="${4:-25}" start="${5:-0}"
  local query="limit=${limit}&start=${start}"
  [ -n "${filterText}" ] && query="${query}&filterText=${filterText}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/branches?${query}"
}
# 获取仓库的默认分支
# 用法: repo_get_default_branch <project> <repo>
repo_get_default_branch() {
  local project="$1" repo="$2"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/branches/default"
}
# 创建仓库分支
# 用法: repo_create_branch <project> <repo> <branch_name> <start_point>
repo_create_branch() {
  local project="$1" repo="$2" name="$3" startPoint="$4"
  local body
  body=$(jq -n --arg name "${name}" --arg startPoint "${startPoint}" \
    '{"name": $name, "startPoint": $startPoint}')
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/branches" "${body}"
}
# 创建仓库分支 (branch-utils 版本)
# 用法: repo_create_branch_v2 <project> <repo> <branch_name> <start_point>
repo_create_branch_v2() {
  local project="$1" repo="$2" name="$3" startPoint="$4"
  local body
  body=$(jq -n --arg name "${name}" --arg startPoint "${startPoint}" \
    '{"name": $name, "startPoint": $startPoint}')
  _post "/rest/branch-utils/2.0/projects/${project}/repos/${repo}/branches" "${body}"
}
# 删除仓库分支
# 用法: repo_delete_branch <project> <repo> <branch_name>
repo_delete_branch() {
  local project="$1" repo="$2" name="$3"
  local body
  body=$(jq -n --arg name "${name}" '{"name": $name}')
  _delete "/rest/api/2.0/projects/${project}/repos/${repo}/branches" "${body}"
}
# 获取仓库 tag 列表
# 用法: repo_get_tags <project> <repo> [filterText] [limit] [start] [orderBy]
repo_get_tags() {
  local project="$1" repo="$2"
  local filterText="${3:-}" limit="${4:-25}" start="${5:-0}" orderBy="${6:-}"
  local query="limit=${limit}&start=${start}"
  [ -n "${filterText}" ] && query="${query}&filterText=${filterText}"
  [ -n "${orderBy}" ] && query="${query}&orderBy=${orderBy}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/tags?${query}"
}
# 创建仓库 tag
# 用法: repo_create_tag <project> <repo> <tag_name> <start_point> <type> [message] [force]
# type: ANNOTATED | LIGHTWEIGHT
repo_create_tag() {
  local project="$1" repo="$2" name="$3" startPoint="$4" type="$5"
  local message="${6:-}" force="${7:-false}"
  local body
  body=$(jq -n \
    --arg name "${name}" \
    --arg startPoint "${startPoint}" \
    --arg type "${type}" \
    --arg message "${message}" \
    --arg force "${force}" \
    '{
      "name": $name,
      "startPoint": $startPoint,
      "type": $type,
      "message": $message,
      "force": $force
    }')
  _post "/rest/git/2.0/projects/${project}/repos/${repo}/tags" "${body}"
}
# 获取仓库文件列表
# 用法: repo_get_files <project> <repo> [at] [limit] [start]
# at: 分支名、commitHash、tag名
repo_get_files() {
  local project="$1" repo="$2"
  local at="${3:-}" limit="${4:-500}" start="${5:-0}"
  local query="limit=${limit}&start=${start}"
  [ -n "${at}" ] && query="${query}&at=${at}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/files?${query}"
}
# 获取仓库文件列表 (branch-utils 版本)
# 用法: repo_get_files_v2 <project> <repo> [at] [limit] [start]
repo_get_files_v2() {
  local project="$1" repo="$2"
  local at="${3:-}" limit="${4:-500}" start="${5:-0}"
  local query="limit=${limit}&start=${start}"
  [ -n "${at}" ] && query="${query}&at=${at}"
  _get "/rest/branch-utils/2.0/projects/${project}/repos/${repo}/files?${query}"
}
# 浏览目录/文件内容
# 用法: repo_browse <project> <repo> <file_path> [at] [limit] [start]
# at: 指定分支或 commit
repo_browse() {
  local project="$1" repo="$2" file_path="$3"
  local at="${4:-}" limit="${5:-500}" start="${6:-0}"
  local query="limit=${limit}&start=${start}"
  [ -n "${at}" ] && query="${query}&at=${at}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/browse/${file_path}?${query}"
}
# 获取 commit 详细信息
# 用法: repo_get_commit <project> <repo> <commit_hash> [withIssues]
repo_get_commit() {
  local project="$1" repo="$2" commit="$3"
  local withIssues="${4:-}"
  local query=""
  [ -n "${withIssues}" ] && query="?withIssues=${withIssues}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/commits/${commit}${query}"
}
# 获取两个 ref 之间的 commit 列表
# 用法: repo_get_commits <project> <repo> [since] [until] [limit] [start]
repo_get_commits() {
  local project="$1" repo="$2"
  local since="${3:-}" until="${4:-}" limit="${5:-25}" start="${6:-0}"
  local query="limit=${limit}&start=${start}"
  [ -n "${since}" ] && query="${query}&since=${since}"
  [ -n "${until}" ] && query="${query}&until=${until}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/commits?${query}"
}
# 获取仓库两个版本之间的变更文件列表
# 用法: repo_get_changes <project> <repo> <since> <until> [limit] [start]
repo_get_changes() {
  local project="$1" repo="$2" since="$3" until="$4"
  local limit="${5:-500}" start="${6:-0}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/changes?since=${since}&until=${until}&limit=${limit}&start=${start}"
}
# 比较两个分支
# 用法: repo_compare_branches <project> <repo> [since] [until] [doubleDot]
repo_compare_branches() {
  local project="$1" repo="$2"
  local since="${3:-}" until="${4:-}" doubleDot="${5:-}"
  local query=""
  [ -n "${since}" ] && query="since=${since}"
  [ -n "${until}" ] && query="${query:+${query}&}until=${until}"
  [ -n "${doubleDot}" ] && query="${query:+${query}&}doubleDot=${doubleDot}"
  [ -n "${query}" ] && query="?${query}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/compare/between${query}"
}
# 获取两个 ref diff 文件列表
# 用法: repo_compare_changes <project> <repo> [from] [to] [limit] [start] [doubleDot] [numStats]
repo_compare_changes() {
  local project="$1" repo="$2"
  local from="${3:-}" to="${4:-}" limit="${5:-500}" start="${6:-0}"
  local doubleDot="${7:-}" numStats="${8:-}"
  local query="limit=${limit}&start=${start}"
  [ -n "${from}" ] && query="${query}&from=${from}"
  [ -n "${to}" ] && query="${query}&to=${to}"
  [ -n "${doubleDot}" ] && query="${query}&doubleDot=${doubleDot}"
  [ -n "${numStats}" ] && query="${query}&numStats=${numStats}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/compare/changes?${query}"
}
# 获取仓库归属关系
# 用法: repo_get_belonging <project> <repo>
repo_get_belonging() {
  local project="$1" repo="$2"
  _get "/rest/api/5.0/projects/${project}/repos/${repo}/belonging"
}
# 查看用户是否具有仓库某种权限
# 用法: repo_has_permission <project> <repo>
repo_has_permission() {
  local project="$1" repo="$2"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/hasPermissionSpec"
}
# 查询分支或 Tag 是否存在
# 用法: repo_ref_exists <project> <repo> <ref>
repo_ref_exists() {
  local project="$1" repo="$2" ref="$3"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/ref-exists?ref=${ref}"
}
# =============================================================================
# Project 仓库组相关接口
# =============================================================================
# 获取仓库组列表
# 用法: project_list [name] [permission] [limit] [start]
project_list() {
  local name="${1:-}" permission="${2:-}" limit="${3:-25}" start="${4:-0}"
  local query="limit=${limit}&start=${start}"
  [ -n "${name}" ] && query="${query}&name=${name}"
  [ -n "${permission}" ] && query="${query}&permission=${permission}"
  _get "/rest/api/2.0/projects?${query}"
}
# =============================================================================
# User 用户相关接口
# =============================================================================
# 获取当前请求用户具有某种权限的仓库列表
# 用法: user_get_repos [permission] [limit] [start]
# permission: REPO_READ | REPO_WRITE | REPO_ADMIN (默认 REPO_ADMIN)
user_get_repos() {
  local permission="${1:-REPO_ADMIN}" limit="${2:-25}" start="${3:-0}"
  _get "/rest/api/2.0/repos?permission=${permission}&limit=${limit}&start=${start}"
}
# 获取 SSH Key 列表
# 用法: user_get_ssh_keys [user]
user_get_ssh_keys() {
  local user="${1:-}"
  local query=""
  [ -n "${user}" ] && query="?user=${user}"
  _get "/rest/ssh/2.0/keys${query}"
}
# 添加 SSH Key
# 用法: user_add_ssh_key <ssh_key_text> [user]
user_add_ssh_key() {
  local text="$1" user="${2:-}"
  local body
  if [ -n "${user}" ]; then
    body=$(jq -n --arg text "${text}" --arg user "${user}" '{"text": $text, "user": $user}')
  else
    body=$(jq -n --arg text "${text}" '{"text": $text}')
  fi
  _post "/rest/ssh/2.0/keys" "${body}"
}
# 删除 SSH Key
# 用法: user_delete_ssh_key <key_id> [user]
user_delete_ssh_key() {
  local key_id="$1" user="${2:-}"
  local query=""
  [ -n "${user}" ] && query="?user=${user}"
  _delete "/rest/ssh/2.0/keys/${key_id}${query}"
}
# =============================================================================
# Repo Setting 仓库设置相关接口
# =============================================================================
# 获取仓库 webhook 列表
# 用法: setting_get_webhooks <project> <repo>
setting_get_webhooks() {
  local project="$1" repo="$2"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/integrations/webhooks"
}
# 增加仓库 webhook
# 用法: setting_add_webhook <project> <repo> <json_body>
setting_add_webhook() {
  local project="$1" repo="$2" body="$3"
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/integrations/webhooks" "${body}"
}
# 删除仓库 webhook
# 用法: setting_delete_webhook <project> <repo> <json_body>
setting_delete_webhook() {
  local project="$1" repo="$2" body="$3"
  _delete "/rest/api/2.0/projects/${project}/repos/${repo}/integrations/webhooks" "${body}"
}
# 获取仓库用户权限列表
# 用法: setting_get_user_permissions <project> <repo>
setting_get_user_permissions() {
  local project="$1" repo="$2"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/permissions/users"
}
# 增加仓库用户权限
# 用法: setting_add_user_permission <project> <repo> <user_mis> <permission>
# permission: REPO_READ | REPO_WRITE | REPO_ADMIN
setting_add_user_permission() {
  local project="$1" repo="$2" name="$3" permission="$4"
  _put "/rest/api/2.0/projects/${project}/repos/${repo}/permissions/users?name=${name}&permission=${permission}" "{}"
}
# 删除仓库用户权限
# 用法: setting_delete_user_permission <project> <repo> <user_mis>
setting_delete_user_permission() {
  local project="$1" repo="$2" name="$3"
  _delete "/rest/api/2.0/projects/${project}/repos/${repo}/permissions/users?name=${name}"
}
# 获取 Pull Request 设置
# 用法: setting_get_pr_settings <project> <repo>
setting_get_pr_settings() {
  local project="$1" repo="$2"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pr-settings"
}
# 更新 Pull Request 设置
# 用法: setting_update_pr_settings <project> <repo> <json_body>
setting_update_pr_settings() {
  local project="$1" repo="$2" body="$3"
  _put "/rest/api/2.0/projects/${project}/repos/${repo}/pr-settings" "${body}"
}
# 获取仓库最少通过数
# 用法: setting_get_min_approvers <project> <repo>
setting_get_min_approvers() {
  local project="$1" repo="$2"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pr-settings/approvers"
}
# 更新仓库最少通过数
# 用法: setting_update_min_approvers <project> <repo> <count>
setting_update_min_approvers() {
  local project="$1" repo="$2" count="$3"
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/pr-settings/approvers?count=${count}" "{}"
}
# 获取仓库 Pull Request 的默认评审人列表
# 用法: setting_get_default_reviewers <project> <repo>
setting_get_default_reviewers() {
  local project="$1" repo="$2"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/defaultReviewer"
}
# 获取仓库的保护分支列表
# 用法: setting_get_protected_branches <project> <repo>
setting_get_protected_branches() {
  local project="$1" repo="$2"
  _get "/rest/branch-permissions/2.0/projects/${project}/repos/${repo}/restricted"
}
# 增加仓库的保护分支设置
# 用法: setting_add_protected_branch <project> <repo> <json_body>
setting_add_protected_branch() {
  local project="$1" repo="$2" body="$3"
  _post "/rest/api/2.0/projects/${project}/repos/${repo}/restricted" "${body}"
}
# 更新仓库的保护分支设置
# 用法: setting_update_protected_branch <project> <repo> <setting_id> <json_body>
setting_update_protected_branch() {
  local project="$1" repo="$2" setting_id="$3" body="$4"
  _put "/rest/api/2.0/projects/${project}/repos/${repo}/restricted/${setting_id}" "${body}"
}
# 获取仓库管理员列表
# 用法: setting_get_admins <project> <repo> [limit] [start]
setting_get_admins() {
  local project="$1" repo="$2"
  local limit="${3:-25}" start="${4:-0}"
  _get "/rest/api/2.0/projects/${project}/repos/${repo}/admin?limit=${limit}&start=${start}"
}
# =============================================================================
# Ref Permission 分支权限相关接口
# =============================================================================
# 分支鉴权
# 用法: ref_has_permission <project> <repo> <user> <ref> <permission>
# permission: REF_PUSH | REF_MERGE
ref_has_permission() {
  local project="$1" repo="$2" user="$3" ref="$4" permission="$5"
  _get "/rest/ref-permissions/2.0/projects/${project}/repos/${repo}/restrictions/hasPermission?user=${user}&ref=${ref}&permission=${permission}"
}
# 获取仓库的分支权限列表
# 用法: ref_get_restrictions <project> <repo>
ref_get_restrictions() {
  local project="$1" repo="$2"
  _get "/rest/ref-permissions/2.0/projects/${project}/repos/${repo}/restrictions"
}
# 获取单个分支权限详情
# 用法: ref_get_restriction_detail <project> <repo> <restriction_id>
ref_get_restriction_detail() {
  local project="$1" repo="$2" restriction_id="$3"
  _get "/rest/ref-permissions/2.0/projects/${project}/repos/${repo}/restrictions/${restriction_id}"
}
# 新增分支权限
# 用法: ref_add_restriction <project> <repo> <json_body>
ref_add_restriction() {
  local project="$1" repo="$2" body="$3"
  _post "/rest/ref-permissions/2.0/projects/${project}/repos/${repo}/restrictions" "${body}"
}
# 更新分支权限
# 用法: ref_update_restriction <project> <repo> <restriction_id> <json_body>
ref_update_restriction() {
  local project="$1" repo="$2" restriction_id="$3" body="$4"
  _put "/rest/ref-permissions/2.0/projects/${project}/repos/${repo}/restrictions/${restriction_id}" "${body}"
}
# 删除分支权限
# 用法: ref_delete_restriction <project> <repo> <restriction_id>
ref_delete_restriction() {
  local project="$1" repo="$2" restriction_id="$3"
  _delete "/rest/ref-permissions/2.0/projects/${project}/repos/${repo}/restrictions/${restriction_id}"
}
# =============================================================================
# Repo Event 仓库事件相关接口
# =============================================================================
# 获取 Push 事件列表
# 用法: event_list_push <project> <repo> <branch> [startTime] [endTime] [limit] [start]
event_list_push() {
  local project="$1" repo="$2" branch="$3"
  local startTime="${4:-}" endTime="${5:-}" limit="${6:-25}" start="${7:-0}"
  local query="branch=${branch}&limit=${limit}&start=${start}"
  [ -n "${startTime}" ] && query="${query}&startTime=${startTime}"
  [ -n "${endTime}" ] && query="${query}&endTime=${endTime}"
  _get "/rest/api/2.0/CodeEvents/projects/${project}/repos/${repo}/events/push?${query}"
}
# =============================================================================
# 辅助工具函数
# =============================================================================
# 从 PR 链接中解析 project、repo、pr_id
# 用法: parse_pr_url <pr_url>
# 返回: project repo pr_id (空格分隔)
# 支持的链接格式:
#   https://dev.sankuai.com/code/repo-detail/{project}/{repo}/pr/detail/{pr_id}
#   https://dev.sankuai.com/code/repo-detail/{project}/{repo}/pr/detail/{pr_id}/diff
#   https://dev.sankuai.com/code/repo-detail/{project}/{repo}/pr/{pr_id}/diff
#   https://dev.sankuai.com/code/repo-detail/{project}/{repo}/pr/{pr_id}
parse_pr_url() {
  local url="$1"
  local project repo pr_id
  # 格式1: /code/repo-detail/{project}/{repo}/pr/detail/{pr_id}[/diff]
  if [[ "${url}" =~ /code/repo-detail/([^/]+)/([^/]+)/pr/detail/([0-9]+) ]]; then
    project="${BASH_REMATCH[1]}"
    repo="${BASH_REMATCH[2]}"
    pr_id="${BASH_REMATCH[3]}"
    echo "${project} ${repo} ${pr_id}"
  # 格式2: /code/repo-detail/{project}/{repo}/pr/{pr_id}[/diff]
  elif [[ "${url}" =~ /code/repo-detail/([^/]+)/([^/]+)/pr/([0-9]+) ]]; then
    project="${BASH_REMATCH[1]}"
    repo="${BASH_REMATCH[2]}"
    pr_id="${BASH_REMATCH[3]}"
    echo "${project} ${repo} ${pr_id}"
  else
    echo "ERROR: 无法解析 PR 链接: ${url}" >&2
    return 1
  fi
}
# 从 PR 页面 URL 中的全局 ID 获取仓库内 PR ID
# Code 平台的 PR 详情页使用全局 ID，但 API 需要仓库内 ID
# 用法: get_repo_pr_id <project> <repo> <global_pr_id>
get_repo_pr_id() {
  local project="$1" repo="$2" global_pr_id="$3"
  # 先尝试直接用这个 ID 获取 PR 详情
  local result
  result=$(_get "/rest/api/2.0/projects/${project}/repos/${repo}/pull-requests/${global_pr_id}")
  local code
  code=$(echo "${result}" | jq -r '.code // empty')
  if [ -z "${code}" ] || [ "${code}" = "null" ]; then
    # 如果返回中有 id 字段，说明这就是仓库内 ID
    echo "${global_pr_id}"
  else
    # 否则需要搜索
    echo "ERROR: 无法找到 PR ID: ${global_pr_id}" >&2
    return 1
  fi
}
# 批量获取 PR 所有变更文件的 diff 内容
# 用法: pr_get_all_diffs <project> <repo> <pr_id>
# 输出: JSON 数组，每个元素包含 filePath 和 diff 内容
pr_get_all_diffs() {
  local project="$1" repo="$2" pr_id="$3"
  # 1. 获取变更文件列表
  local changes
  changes=$(pr_get_changes "${project}" "${repo}" "${pr_id}" 500)
  # 2. 提取文件路径列表
  local file_paths
  file_paths=$(echo "${changes}" | jq -r '.values[]? | .path.toString // (.path.components | join("/"))')
  # 3. 逐文件获取 diff
  local results="[]"
  while IFS= read -r file_path; do
    [ -z "${file_path}" ] && continue
    local diff
    diff=$(pr_get_file_diff "${project}" "${repo}" "${pr_id}" "${file_path}")
    results=$(echo "${results}" | jq --arg path "${file_path}" --argjson diff "${diff}" \
      '. + [{"filePath": $path, "diff": $diff}]')
  done <<< "${file_paths}"
  echo "${results}"
}
# =============================================================================
# 主入口 - 支持命令行直接调用
# =============================================================================
# 用法: bash code-api.sh <function_name> [args...]
# 示例:
#   bash code-api.sh pr_get_detail my-project my-repo 123
#   bash code-api.sh pr_approve my-project my-repo 123
#   bash code-api.sh repo_get_branches my-project my-repo
#   bash code-api.sh parse_pr_url "https://dev.sankuai.com/code/repo-detail/group/repo/pr/detail/123"
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  if [ $# -lt 1 ]; then
    echo "用法: bash code-api.sh <function_name> [args...]"
    echo ""
    echo "可用函数列表:"
    echo ""
    echo "=== Pull Request ==="
    echo "  pr_get_detail <project> <repo> <pr_id>"
    echo "  pr_list <project> <repo> [state] [limit] [start]"
    echo "  pr_search <project> <repo> [author] [state] [source] [target] [filterTitle] [limit] [start]"
    echo "  pr_create <project> <repo> <json_body>"
    echo "  pr_update <project> <repo> <pr_id> <json_body>"
    echo "  pr_approve <project> <repo> <pr_id>"
    echo "  pr_merge <project> <repo> <pr_id>"
    echo "  pr_decline <project> <repo> <pr_id> [version]"
    echo "  pr_reopen <project> <repo> <pr_id> [version]"
    echo "  pr_draft_to_normal <project> <repo> <pr_id>"
    echo "  pr_get_changes <project> <repo> <pr_id> [limit] [start]"
    echo "  pr_get_file_diff <project> <repo> <pr_id> <file_path>"
    echo "  pr_get_merge_status <project> <repo> <pr_id>"
    echo "  pr_get_commits <project> <repo> <pr_id> [limit] [start]"
    echo "  pr_get_activities <project> <repo> <pr_id> [limit] [start]"
    echo "  pr_get_assignments <project> <repo> <pr_id> [path] [states]"
    echo "  pr_add_comment <project> <repo> <pr_id> <text>"
    echo "  pr_add_inline_comment <project> <repo> <pr_id> <text> <file_path> <line> <since_commit> <until_commit> [line_type] [file_type]"
    echo "  pr_delete_comment <project> <repo> <pr_id> <comment_id>"
    echo "  pr_get_commit_range <project> <repo> <pr_id>"
    echo "  pr_get_all_diffs <project> <repo> <pr_id>"
    echo ""
    echo "=== Build Status ==="
    echo "  build_get_stats <commit_id> [includeUnique]"
    echo "  build_get_list <commit_id>"
    echo "  build_callback <commit_id> <json_body>"
    echo ""
    echo "=== Repository ==="
    echo "  repo_get_detail <project> <repo>"
    echo "  repo_list <project> [limit] [start]"
    echo "  repo_create <project> <json_body>"
    echo "  repo_search <keyword> [limit] [start]"
    echo "  repo_get_branches <project> <repo> [filterText] [limit] [start]"
    echo "  repo_get_default_branch <project> <repo>"
    echo "  repo_create_branch <project> <repo> <branch_name> <start_point>"
    echo "  repo_delete_branch <project> <repo> <branch_name>"
    echo "  repo_get_tags <project> <repo> [filterText] [limit] [start] [orderBy]"
    echo "  repo_create_tag <project> <repo> <tag_name> <start_point> <type> [message] [force]"
    echo "  repo_get_files <project> <repo> [at] [limit] [start]"
    echo "  repo_browse <project> <repo> <file_path> [at] [limit] [start]"
    echo "  repo_get_commit <project> <repo> <commit_hash> [withIssues]"
    echo "  repo_get_commits <project> <repo> [since] [until] [limit] [start]"
    echo "  repo_get_changes <project> <repo> <since> <until> [limit] [start]"
    echo "  repo_compare_branches <project> <repo> [since] [until] [doubleDot]"
    echo "  repo_compare_changes <project> <repo> [from] [to] [limit] [start] [doubleDot] [numStats]"
    echo "  repo_ref_exists <project> <repo> <ref>"
    echo ""
    echo "=== Project ==="
    echo "  project_list [name] [permission] [limit] [start]"
    echo ""
    echo "=== User ==="
    echo "  user_get_repos [permission] [limit] [start]"
    echo "  user_get_ssh_keys [user]"
    echo "  user_add_ssh_key <ssh_key_text> [user]"
    echo "  user_delete_ssh_key <key_id> [user]"
    echo ""
    echo "=== Repo Setting ==="
    echo "  setting_get_webhooks <project> <repo>"
    echo "  setting_add_webhook <project> <repo> <json_body>"
    echo "  setting_delete_webhook <project> <repo> <json_body>"
    echo "  setting_get_user_permissions <project> <repo>"
    echo "  setting_add_user_permission <project> <repo> <user_mis> <permission>"
    echo "  setting_delete_user_permission <project> <repo> <user_mis>"
    echo "  setting_get_pr_settings <project> <repo>"
    echo "  setting_update_pr_settings <project> <repo> <json_body>"
    echo "  setting_get_min_approvers <project> <repo>"
    echo "  setting_update_min_approvers <project> <repo> <count>"
    echo "  setting_get_default_reviewers <project> <repo>"
    echo "  setting_get_protected_branches <project> <repo>"
    echo "  setting_get_admins <project> <repo> [limit] [start]"
    echo ""
    echo "=== Ref Permission ==="
    echo "  ref_has_permission <project> <repo> <user> <ref> <permission>"
    echo "  ref_get_restrictions <project> <repo>"
    echo "  ref_get_restriction_detail <project> <repo> <restriction_id>"
    echo "  ref_add_restriction <project> <repo> <json_body>"
    echo "  ref_update_restriction <project> <repo> <restriction_id> <json_body>"
    echo "  ref_delete_restriction <project> <repo> <restriction_id>"
    echo ""
    echo "=== Repo Event ==="
    echo "  event_list_push <project> <repo> <branch> [startTime] [endTime] [limit] [start]"
    echo ""
    echo "=== 辅助工具 ==="
    echo "  parse_pr_url <pr_url>"
    exit 1
  fi
  func_name="$1"
  shift
  "${func_name}" "$@"
fi
