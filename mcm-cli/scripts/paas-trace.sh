#!/bin/bash
# =============================================================================
# paas-trace.sh — Squirrel/Mafka/RDS/Eagle 变更追溯的资源标识补全脚本
#
# 定位：`mcm cloudtrail list` 追溯链路的前置编排环节，非独立工具。标准查询方式
# 始终是 `mcm cloudtrail list --appkey <业务appkey> --account-name <系统名>`，但
# Squirrel/Mafka/RDS/Eagle 这 4 个系统的变更事件不上报业务 appkey，直查会漏数据，
# 必须先换成该系统自身的资源标识（paasAppkey/Topic 短名/clusterAppkey）再查询。
# 本脚本自动完成「换标识 → 调用 cloudtrail list → 合并展示」全流程。其余常规
# 系统（Lion、Plus、Crane、Rocket、HULK、OCTO 等）不受影响，直接用标准命令查询。
#
# 支持范围：--account-name 仅接受以下 4 个值，大小写不敏感，逗号分隔可多选。
#   Squirrel（缓存）｜Mafka（消息队列）｜RDS（数据库）｜Eagle（搜索/ES）
#
# 内部两步（对调用方透明，一次调用完成）：
#   步骤一 换标识：查各系统自身管理平台 API，把业务 appkey 换成该系统的资源标识。
#     - Squirrel/RDS：Avatar appkeyPaasCapacity → 各自 paasAppkey
#     - Mafka：Avatar appkeyPaasCapacity + Mafka API → Topic 短名
#     - Eagle：Avatar appkeyMetric/middleware + Eagle OpenAPI → clusterAppkey
#   步骤二 查变更：拿换到的资源标识调用 mcm cloudtrail list。
#     - Squirrel/RDS/Eagle：--appkey <换到的资源标识> --account-name <系统名>
#     - Mafka 路径A（appkey 直查）：--appkey <业务appkey> --account-name Mafka
#     - Mafka 路径B（Topic 精确过滤，需与路径A合并才完整）：--custom-resource-type + --custom-resource-names
#
# 认证：步骤一需要 yun_portal_ssoid（由 mcm login 的 CIBA token 自动换取，换到的
# 票据会连同过期时间缓存进 ~/.mcm-cli/config.json，未过期前复用、避免重复换票，
# 万一被服务端提前吊销也会在请求时按 401/403/3xx 正确识别为认证失败，不产生假阴性）；
# 步骤二的认证由 mcm CLI 自身处理。
#
# 用法：
#   bash paas-trace.sh --appkey <业务appkey> [--account-name <Squirrel|Mafka|RDS|Eagle>]
#                       [--begin <yyyy-MM-dd HH:mm:ss>] [--end <yyyy-MM-dd HH:mm:ss>]
#                       [--env <prod|test>] [--username <mis>] [--user-type <user|api>]
#                       [--event-name <名称，逗号分隔>] [-f <json|table|md>]
#                       [-p <页码> -s <每页条数>]
#
# --begin/--end 缺省默认查近 7 天。md/table 格式不按系统分组，而是把所有命中系统
# 的结果合并为单一列表，按开始时间倒序展示（每行保留「系统」列区分来源）；-p/-s
# 语义与 `mcm cloudtrail list` 对齐，对整个合并列表整体生效。不区分默认态/分页态，
# 统一展示行为（与 `mcm cloudtrail list -f md` 模板 A/B 完全对齐）：
#   - 结果超过每页条数（默认 20）时，标题下方提示「当前展示前 N 条」；
#   - 结尾始终固定输出一行「共 N 条，第 P 页，每页 S 条」（未显式传 -p/-s 时等价于
#     第 1 页、每页 20 条，同样展示该行，不因是否显式传参而省略）。
#
# 标题下方固定输出一行 ⚠️ 提示（始终展示，AI 不得省略/改写/挪动位置），用于让
# 用户第一时间感知这张表和上方按业务 appkey 直查的表在查询口径上的差异。
#
# 环境变量：
#   MCM_DEBUG=1          启用调试日志（输出到 stderr）
#   MCM_MWS_SSOID=<tok>  直接注入 MWS 票据，跳过换票逻辑
#
# 依赖：jq、curl、mcm（需先 mcm login）、node（换票用，可选）、python3（URL 编码用，可选）
#
# 退出码：0 全部成功，1 参数错误/票据失败/子查询失败（详见 stderr）
# =============================================================================

set -euo pipefail

# ── 参数解析 ──────────────────────────────────────────────────

APPKEY=""
ACCOUNT_NAME=""
BEGIN=""
END=""
ENV=""
USERNAME=""
USER_TYPE=""
EVENT_NAME=""
FORMAT="md"
DISPLAY_PAGE=""
DISPLAY_PAGE_SIZE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --appkey) APPKEY="$2"; shift 2 ;;
    --account-name) ACCOUNT_NAME="$2"; shift 2 ;;
    --begin) BEGIN="$2"; shift 2 ;;
    --end) END="$2"; shift 2 ;;
    --env) ENV="$2"; shift 2 ;;
    --username) USERNAME="$2"; shift 2 ;;
    --user-type) USER_TYPE="$2"; shift 2 ;;
    --event-name) EVENT_NAME="$2"; shift 2 ;;
    -f|--format) FORMAT="$2"; shift 2 ;;
    -p|--page) DISPLAY_PAGE="$2"; shift 2 ;;
    -s|--page-size) DISPLAY_PAGE_SIZE="$2"; shift 2 ;;
    *) echo "[paas-trace] 未知参数: $1" >&2; exit 1 ;;
  esac
done

# -p/-s 对整个「合并去重后的单一结果列表」做展示分页（与 _mcm_list_merge_paged 内部向
# cloudtrail list 请求的拉取分页是两回事，互不影响）。_PAGE_EXPLICIT 记录用户是否
# 显式传参：未传→「仅展示前 N 条」提示（无页码概念，兼容旧行为）；显式传（哪怕只传
# 其一）→「第 X/Y 页」提示。两种文案共用同一套切片逻辑，默认态等价于隐式 -p 1。
_PAGE_EXPLICIT=0
if [ -n "$DISPLAY_PAGE" ] || [ -n "$DISPLAY_PAGE_SIZE" ]; then
  _PAGE_EXPLICIT=1
fi
[ -z "$DISPLAY_PAGE" ] && DISPLAY_PAGE=1
[ -z "$DISPLAY_PAGE_SIZE" ] && DISPLAY_PAGE_SIZE=20
if ! [[ "$DISPLAY_PAGE" =~ ^[0-9]+$ ]] || [ "$DISPLAY_PAGE" -lt 1 ]; then
  echo "[paas-trace] ✗ -p/--page 必须是正整数，当前传入：${DISPLAY_PAGE}" >&2
  exit 1
fi
if ! [[ "$DISPLAY_PAGE_SIZE" =~ ^[0-9]+$ ]] || [ "$DISPLAY_PAGE_SIZE" -lt 1 ]; then
  echo "[paas-trace] ✗ -s/--page-size 必须是正整数，当前传入：${DISPLAY_PAGE_SIZE}" >&2
  exit 1
fi

if [ -z "$APPKEY" ]; then
  echo "[paas-trace] ✗ 缺少必填参数 --appkey" >&2
  exit 1
fi

# 脚本默认查近 7 天（追溯/排查场景 24h 偏短，且只影响本脚本，不改动 mcm cloudtrail list 默认值）
if [ -z "$BEGIN" ]; then
  BEGIN=$(date -v-7d '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -d '7 days ago' '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "")
  if [ -n "$BEGIN" ]; then
    echo "[paas-trace] ℹ 未指定 --begin，默认查近 7 天（起点：${BEGIN}），如需其他范围请显式传入 --begin/--end" >&2
  fi
fi

# 提前钉死 END（默认当前时刻），确保前置校验与所有子查询使用同一时间基准，避免
# 步骤一耗时数十秒导致 end 滑动，在 --begin 靠近 180 天边界时出现「校验放行但
# 子查询报超限」的不一致。
if [ -z "$END" ]; then
  END=$(date '+%Y-%m-%d %H:%M:%S')
fi

# 前置校验 180 天上限（早于所有子查询，避免跑完 4 个系统才报错）。按天数向下取整
# 判断而非按秒精确比较：例如「查近 180 天」的 begin=今天-180d 00:00、end=当前 20:00，
# 精确差值超 180 天会被误拦截，但天数才符合用户直觉，因此仅在天数明显超限（>180）
# 时才提前拦截，天数边界内的场景交给后端校验真实报错。
if [ -n "$BEGIN" ]; then
  _PT_BEGIN_EPOCH=$(date -j -f '%Y-%m-%d %H:%M:%S' "$BEGIN" '+%s' 2>/dev/null || date -d "$BEGIN" '+%s' 2>/dev/null || echo "")
  _PT_END_EPOCH=$(date -j -f '%Y-%m-%d %H:%M:%S' "$END" '+%s' 2>/dev/null || date -d "$END" '+%s' 2>/dev/null || echo "")
  if [ -n "$_PT_BEGIN_EPOCH" ] && [ -n "$_PT_END_EPOCH" ]; then
    _PT_RANGE_DAYS=$(( (_PT_END_EPOCH - _PT_BEGIN_EPOCH) / 86400 ))
    if [ "$_PT_RANGE_DAYS" -gt 180 ]; then
      echo "[paas-trace] ✗ 查询的时间跨度超过限制（最大 180 天，当前约 ${_PT_RANGE_DAYS} 天），请缩小 --begin/--end 范围后重试" >&2
      exit 1
    fi
  fi
fi

_pt_debug() {
  if [ "${MCM_DEBUG:-}" = "1" ] || [ "${MCM_DEBUG:-}" = "true" ]; then
    echo "[PAAS-TRACE-DEBUG] $*" >&2
  fi
}

_urlencode() {
  python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$1" 2>/dev/null || echo "$1"
}

# ── 前置依赖检查：jq、curl、mcm ──────────────────────────────────

if ! command -v jq >/dev/null 2>&1; then
  echo "[paas-trace] jq 未安装，正在尝试自动安装..." >&2
  if command -v brew >/dev/null 2>&1; then
    brew install jq >/dev/null 2>&1 || true
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq jq >/dev/null 2>&1 || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y -q jq >/dev/null 2>&1 || true
  fi
  if ! command -v jq >/dev/null 2>&1; then
    echo "[paas-trace] ✗ jq 安装失败，请手动安装后重试（macOS: brew install jq）" >&2
    exit 1
  fi
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[paas-trace] ✗ 未找到 curl，请先安装后重试" >&2
  exit 1
fi

if ! command -v mcm >/dev/null 2>&1; then
  echo "[paas-trace] ✗ 未找到 mcm 命令，请先安装 mcm-cli（步骤二依赖 mcm cloudtrail list 查询）" >&2
  exit 1
fi

# ⚠️ 环境自检：检测 PATH 中的 mcm 命令是否是 Node.js 实现（防止同名工具冲突导致静默查询失败）。
# 若检测到非 Node.js 版（如 Python 版），自动从 nvm/npm 全局路径中找到正确版本并修正 PATH。
_MCM_RESOLVED_PATH=$(command -v mcm 2>/dev/null || echo "")
_mcm_is_nodejs() {
  local p="$1"
  [ -f "$p" ] && head -c 200 "$p" 2>/dev/null | grep -qi "node"
}
if [ -n "$_MCM_RESOLVED_PATH" ] && ! _mcm_is_nodejs "$_MCM_RESOLVED_PATH"; then
  echo "[paas-trace] ⚠ 检测到 mcm 命令（${_MCM_RESOLVED_PATH}）不是 mcm-cli（Node.js 实现），尝试自动修正 PATH..." >&2
  _fixed=0
  # 1. 搜索 nvm 各版本下的 mcm
  if [ -d "${HOME}/.nvm/versions/node" ]; then
    for _nvm_bin in "${HOME}"/.nvm/versions/node/*/bin/mcm; do
      if _mcm_is_nodejs "$_nvm_bin"; then
        export PATH="$(dirname "$_nvm_bin"):${PATH}"
        echo "[paas-trace] ✔ 已自动切换到 Node.js 版 mcm：${_nvm_bin}" >&2
        _fixed=1; break
      fi
    done
  fi
  # 2. 搜索 npm 全局安装目录
  if [ "$_fixed" = "0" ]; then
    _npm_bin_dir=$(npm bin -g 2>/dev/null || echo "")
    if [ -n "$_npm_bin_dir" ] && _mcm_is_nodejs "${_npm_bin_dir}/mcm"; then
      export PATH="${_npm_bin_dir}:${PATH}"
      echo "[paas-trace] ✔ 已自动切换到 Node.js 版 mcm：${_npm_bin_dir}/mcm" >&2
      _fixed=1
    fi
  fi
  if [ "$_fixed" = "0" ]; then
    echo "[paas-trace] ✗ 无法自动找到 Node.js 版 mcm-cli，请手动执行：npm install -g @dp/mcm-cli，或检查 PATH 优先级" >&2
    exit 1
  fi
fi

# ── 获取 MWS SSO 票据（步骤一查 Avatar/Mafka/Eagle 等平台 API 用） ──
#
# 优先级：0. 环境变量 MCM_MWS_SSOID；1. Token Exchange 换票（仅 authMode=ciba 时可用）；
#         2. 直接读浏览器 Cookie（authMode=cookie 或换票失败时兜底）；3. 失败报错

_MCM_CONFIG="${HOME}/.mcm-cli/config.json"
_MWS_AUDIENCE="60921859"
_MCM_CLIENT_ID="c1e095b546"
_MCM_CLIENT_SECRET="eaf94f833e914c508dec3ddc015479a8"

# *.mws.sankuai.com 各子域名共享同一顶级域 Cookie（已实测验证：mcm/avatar/mws/mafka
# 四个子域读到的 ssoid 值完全一致），因此直接用 avatar.mws.sankuai.com 域读取即可。
_AVATAR_MWS_DOMAIN="https://avatar.mws.sankuai.com"

# 追溯事件详情页地址前缀。详情页必须带上事件的毫秒级时间范围，避免默认时间窗口
# 导致历史事件显示为空；与 `mcm cloudtrail list/detail -f md` 的 UUID 链接渲染规则保持一致。
EVENT_DETAIL_URL_PREFIX="https://mcm.mws.sankuai.com/#/event-review/detail/"

# 定位 mtsso-token-exchange 可执行文件或脚本路径（供 get_mws_ssoid 调用）
# 输出：mtsso_bin 或 mtsso_script 变量名（调用方须先 local 这两个变量）
_find_mtsso_exchange() {
  # 优先：PATH 里已有可执行 bin
  if command -v mtsso-token-exchange >/dev/null 2>&1; then
    mtsso_bin="mtsso-token-exchange"; return 0
  fi
  # npm 全局安装目录（npm install -g @dp/mcm-cli 时命中）
  local npm_root="" pkg_json=""
  npm_root=$(npm root -g 2>/dev/null || echo "")
  if [ -n "$npm_root" ] && [ -d "$npm_root" ]; then
    pkg_json=$(node -e "try{console.log(require.resolve('@mtfe/mtsso-auth-official/package.json',{paths:[process.argv[1]]}))}catch(e){}" "$npm_root" 2>/dev/null || echo "")
    if [ -n "$pkg_json" ]; then
      mtsso_script="$(dirname "$pkg_json")/dist/scripts/token_exchange.js"; return 0
    fi
  fi
  # 兜底：nvm 各版本的 bin 目录
  # 注：不用 -perm /111（macOS BSD find 不支持），nvm bin 目录里本就是可执行 symlink
  if [ -d "${HOME}/.nvm/versions/node" ]; then
    local _cand
    _cand=$(find "${HOME}/.nvm/versions/node"/*/bin -maxdepth 1 -name 'mtsso-token-exchange' 2>/dev/null | head -1 || true)
    if [ -n "$_cand" ] && [ -x "$_cand" ]; then
      mtsso_bin="$_cand"; return 0
    fi
  fi
  return 1
}

# 把新换到的 mwsSsoid 回写进本地 config，供下次调用复用（避免每次都重新换票）。
# 静默失败即可（回写失败不影响本次查询，只是下次少一次缓存命中的机会）。
_persist_mws_ssoid() {
  local ssoid="$1" expires_in_sec="$2"
  [ -f "$_MCM_CONFIG" ] || return 0
  command -v node >/dev/null 2>&1 || return 0
  local expires_at
  expires_at=$(( $(date +%s) * 1000 + expires_in_sec * 1000 ))
  node -e '
    const fs = require("fs");
    const path = process.argv[1];
    try {
      const cfg = JSON.parse(fs.readFileSync(path, "utf8"));
      cfg.mwsSsoid = process.argv[2];
      cfg.mwsSsoidExpiresAt = Number(process.argv[3]);
      cfg.mwsSsoidSource = "token-exchange";
      fs.writeFileSync(path, JSON.stringify(cfg, null, "\t"));
    } catch (e) { /* 静默失败，不影响本次查询 */ }
  ' "$_MCM_CONFIG" "$ssoid" "$expires_at" 2>/dev/null || true
}

# 用当前 access_token 做 Token Exchange，输出 MWS 票据（成功返回 0，失败返回 1）
_do_token_exchange() {
  local subject_token="$1"
  local mtsso_bin="" mtsso_script=""
  _find_mtsso_exchange || return 1
  _pt_debug "尝试 Token Exchange 换取 MWS 票据（audience=${_MWS_AUDIENCE}）"
  local resp access_tok expires_in
  if [ -n "$mtsso_bin" ]; then
    resp=$("$mtsso_bin" --subject_token "$subject_token" --audience "$_MWS_AUDIENCE" \
      --client_id "$_MCM_CLIENT_ID" --client_secret "$_MCM_CLIENT_SECRET" 2>/dev/null || true)
  else
    resp=$(node "$mtsso_script" --subject_token "$subject_token" --audience "$_MWS_AUDIENCE" \
      --client_id "$_MCM_CLIENT_ID" --client_secret "$_MCM_CLIENT_SECRET" 2>/dev/null || true)
  fi
  access_tok=$(echo "$resp" | jq -r '.access_token // empty' 2>/dev/null || true)
  if [ -n "$access_tok" ]; then
    _pt_debug "Token Exchange 换票成功"
    expires_in=$(echo "$resp" | jq -r '.expires_in // 0' 2>/dev/null || echo 0)
    if [ "${expires_in:-0}" -gt 0 ] 2>/dev/null; then
      _persist_mws_ssoid "$access_tok" "$expires_in" || true
    fi
    echo "$access_tok"
    return 0
  fi
  _pt_debug "Token Exchange 换票失败（resp=${resp:-<empty>}）"
  return 1
}

get_mws_ssoid() {
  # 0. 环境变量直接注入
  if [ -n "${MCM_MWS_SSOID:-}" ]; then
    _pt_debug "使用 MCM_MWS_SSOID 环境变量"
    echo "$MCM_MWS_SSOID"
    return 0
  fi

  local auth_mode="" access_token=""
  if [ -f "$_MCM_CONFIG" ]; then
    auth_mode=$(jq -r '.authMode // empty' "$_MCM_CONFIG" 2>/dev/null || echo "")
  fi

  # 0.5 复用本地已缓存且未过期的 mwsSsoid（无论来自上次 Token Exchange 换票还是
  #     浏览器 Cookie 兜底），避免每次调用都重新发起一次 Token Exchange 网络请求
  #     ——换票本身是独立的外部调用，会偶发失败（网络抖动/SSO 瞬时异常），票据
  #     还在有效期内时完全没必要重新换。缓存失效的兜底：即使这里复用的票据实际已
  #     被服务端提前吊销，下方 mws_get() 调用时仍会按 401/403/3xx 检测出认证失败
  #     并提示重新登录，不会导致假阴性。
  if [ -f "$_MCM_CONFIG" ]; then
    local _cached_ssoid _cached_exp _now_ms
    _cached_ssoid=$(jq -r '.mwsSsoid // empty' "$_MCM_CONFIG" 2>/dev/null || echo "")
    _cached_exp=$(jq -r '.mwsSsoidExpiresAt // 0' "$_MCM_CONFIG" 2>/dev/null || echo 0)
    # config 字段可能被手工/其他工具写坏成非数字，先校验格式再做算术比较，
    # 避免 `[ "$_cached_exp" -gt 0 ]` 因非整数值报 "integer expression expected"
    # 并把这条不该暴露给用户的报错打印到 stderr。
    if ! [[ "$_cached_exp" =~ ^[0-9]+$ ]]; then
      _cached_exp=0
    fi
    _now_ms=$(( $(date +%s) * 1000 ))
    # 留 5 分钟安全余量，避免票据在请求发出瞬间恰好过期
    if [ -n "$_cached_ssoid" ] && [ "$_cached_exp" -gt 0 ] && [ $(( _cached_exp - _now_ms )) -gt 300000 ]; then
      _pt_debug "复用本地缓存的 mwsSsoid（剩余 $(( (_cached_exp - _now_ms) / 60000 )) 分钟，来源: $(jq -r '.mwsSsoidSource // "unknown"' "$_MCM_CONFIG" 2>/dev/null)），跳过 Token Exchange"
      echo "$_cached_ssoid"
      return 0
    fi
  fi

  # 1. CIBA/manual 模式：Token Exchange 换票（最优路径，无需浏览器/Keychain）
  # authMode=ciba：mcm login --mis 完成 CIBA 登录写入
  # authMode=manual：mcm login --token 写入（mtsso 无感换票场景）
  if { [ "$auth_mode" = "ciba" ] || [ "$auth_mode" = "manual" ]; } && command -v node >/dev/null 2>&1; then
    access_token=$(jq -r '.accessToken // empty' "$_MCM_CONFIG" 2>/dev/null || echo "")
    if [ -n "$access_token" ]; then
      local tok
      tok=$(_do_token_exchange "$access_token" || echo "")
      if [ -n "$tok" ]; then
        echo "$tok"; return 0
      fi
      echo "[paas-trace] ⚠ Token Exchange 换票失败（网络/配置问题）" >&2
      echo "[paas-trace]   [AI 指令] 优先（无需用户介入、无需重新走大象 CIBA 确认）：读取并执行 mtsso-skills-official skill 换取 user_access_token，执行 mcm login --token \"\${user_access_token}\" 后重试本脚本；仅当该 skill 不存在或执行报错时，才回退执行 mcm login --mis <MIS号> 重新登录后重试" >&2
      return 1
    fi
  fi

  # 2. 非 CIBA/manual 模式（authMode=cookie 或未配置）：
  #    先尝试自动发起 mcm login --mis 完成 CIBA 认证，再走 Token Exchange。
  #    这样用户只需在大象点一次授权，之后永久走换票路径，彻底告别 Keychain 弹框。
  if [ "$auth_mode" != "ciba" ] && [ "$auth_mode" != "manual" ] && command -v mcm >/dev/null 2>&1; then
    # 尝试从已有 config 获取 mis（复用历史登录的 MIS，无需用户输入）
    local mis=""
    if [ -f "$_MCM_CONFIG" ]; then
      mis=$(jq -r '.userMis // empty' "$_MCM_CONFIG" 2>/dev/null || echo "")
    fi
    if [ -n "$mis" ]; then
      echo "[paas-trace] ℹ 检测到未使用 CIBA 认证（当前：${auth_mode:-未配置}），正在自动发起 CIBA 登录（MIS: ${mis}）..." >&2
      echo "[paas-trace]   请在大象 App 中点击「授权」按钮，完成后脚本自动继续（无需再操作 Chrome/Keychain）" >&2
      if mcm login --mis "$mis" >&2 2>&1; then
        # 登录成功，重读 config 拿新 token，立刻换票
        auth_mode=$(jq -r '.authMode // empty' "$_MCM_CONFIG" 2>/dev/null || echo "")
        access_token=$(jq -r '.accessToken // empty' "$_MCM_CONFIG" 2>/dev/null || echo "")
        if [ "$auth_mode" = "ciba" ] && [ -n "$access_token" ]; then
          local tok
          tok=$(_do_token_exchange "$access_token" || echo "")
          if [ -n "$tok" ]; then
            echo "[paas-trace] ✔ CIBA 登录成功，已通过 Token Exchange 获取 MWS 票据，后续无需 Keychain 授权" >&2
            echo "$tok"; return 0
          fi
        fi
      fi
      echo "[paas-trace] ⚠ CIBA 自动登录未完成（超时/取消），请重新执行 mcm login --mis <MIS号> 后重试" >&2
      return 1
    else
      # 读不到历史 MIS，无法无感发起登录
      echo "[paas-trace] ℹ 未检测到 CIBA 认证，请执行 mcm login --mis <MIS号> 完成一次 CIBA 登录（大象确认）后重试" >&2
      return 1
    fi
  fi

  return 1
}

MWS_SSOID=$(get_mws_ssoid || true)
if [ -z "$MWS_SSOID" ]; then
  echo "[paas-trace] ✗ 无法获取 MWS 认证票据，步骤一（查 Avatar 依赖关系）无法执行" >&2
  echo "[paas-trace]   [AI 指令] 请按以下优先级处理，不要跳过步骤 1 直接问用户或降级查询：" >&2
  echo "[paas-trace]   1.（优先，无需用户介入）读取并执行 mtsso-skills-official skill 换取 user_access_token，" >&2
  echo "[paas-trace]      执行 mcm login --token \"\${user_access_token}\" 完成无感登录后重新执行本脚本；" >&2
  echo "[paas-trace]   2.（仅步骤 1 失败/skill 不存在时）执行 mcm login --mis <MIS号> 完成 CIBA 登录（大象确认）后重试；" >&2
  echo "[paas-trace]   3.（临时排查用）直接设置 export MCM_MWS_SSOID=<token> 后重试。" >&2
  echo "[paas-trace] ⛔ 禁止跳过本脚本、改用业务 appkey 直接调用 mcm cloudtrail list 查询 Squirrel/Mafka/RDS/Eagle：直查会混入 Rocket/HULK/OCTO 等主机运维变更，且查不全这 4 个系统真正的变更记录，会给用户呈现错误结果。请解决上述认证问题后重新执行本脚本。" >&2
  exit 1
fi

# ── MWS API 通用请求函数（步骤一使用） ───────────────
#
# 失败分类（避免认证失效被伪装成"无相关系统依赖"假阴性）：
#   - 401/403/3xx（重定向到登录页）：Cookie 失效，致命
#   - 000（curl 自身失败）/5xx/其他 4xx：瞬时失败，调用方当本轮空处理
#
# ⚠️ 不能在 mws_get 内部 exit：调用方以 resp=$(mws_get ...) 命令替换方式调用，
# 处于子 shell，内部 exit 只会退出子 shell、被外层 if/|| 吞掉，导致认证失败被
# 静默当瞬时失败继续跑。因此改用返回码 + 全局变量，交给主 shell 里的调用方判断：
#   0=成功（body 写入 MWS_RESP） 1=瞬时失败（MWS_RESP 置空） 2=认证失败（调用方须立即 exit 1）
MWS_RESP=""

mws_get() {
  local host="$1" path="$2"
  local tmp http_code body
  tmp=$(mktemp)
  # 不用 -f：它会把 4xx/5xx 统一转成 curl 退出码 22，丢失具体 HTTP 码。
  # 改用 -w 捕获状态码，-o 存 body，手动分类。
  # 不能带 -L：MWS 票据失效时会 302 重定向到登录页，-L 会自动跟随重定向并把
  # 最终登录页(HTML)的 200 状态码返回给 -w，导致下面 case 里的 3* 认证失败分支
  # 永远命中不到，票据失效被静默误判成"接口返回 0 条数据"（假阴性 bug）。
  http_code=$(curl -sS --max-time 15 \
    -H "Cookie: yun_portal_ssoid=${MWS_SSOID}" \
    -H "Accept: application/json" \
    -o "$tmp" -w "%{http_code}" \
    "https://${host}${path}" 2>/dev/null || echo "000")
  body=$(cat "$tmp" 2>/dev/null); rm -f "$tmp"

  case "$http_code" in
    200)
      MWS_RESP="$body"
      return 0
      ;;
    401|403)
      echo "[paas-trace] ✗ MWS 认证失败 (${http_code})，请执行 mcm login --mis <MIS号> 后重试" >&2
      return 2
      ;;
    3*)
      # 重定向通常是被打回登录页 = Cookie 失效，按认证失败处理
      echo "[paas-trace] ✗ MWS 认证失败（被重定向到登录页），请执行 mcm login --mis <MIS号> 后重试" >&2
      return 2
      ;;
    000|5*)
      # 网络超时 / 连接失败 / 服务端 5xx：瞬时，调用方当本轮空继续
      _pt_debug "${host} 请求失败 (http_code=${http_code})，本轮跳过"
      MWS_RESP=""
      return 1
      ;;
    *)
      # 其余 4xx（请求构造问题，本脚本固定请求模板基本不会触发）：也当瞬时容错
      _pt_debug "${host} 请求返回非预期状态 (http_code=${http_code})，本轮跳过"
      MWS_RESP=""
      return 1
      ;;
  esac
}

# 调用 mws_get 并处理三类返回码。成功/瞬时失败时把 MWS_RESP 落到 $1 指定的变量名；
# 认证失败(return 2)时立即 exit 1（此处运行在主 shell，exit 生效）。
# 用法：mws_get_into resp "host" "path"  → 成功 resp=body，瞬时 resp='{}'，认证则 exit 1
mws_get_into() {
  local outvar="$1" host="$2" path="$3" rc=0
  # mws_get 可能返回 1(瞬时)/2(认证)，在 set -e 下裸调用会触发退出，
  # 用 `|| rc=$?` 把它放进豁免上下文，由我们手动判断返回码。
  mws_get "$host" "$path" || rc=$?
  if [ "$rc" -eq 2 ]; then
    exit 1
  elif [ "$rc" -eq 0 ]; then
    printf -v "$outvar" '%s' "$MWS_RESP"
  else
    printf -v "$outvar" '%s' '{}'
  fi
}

# ── 步骤一：把业务 appkey 换成各系统自身的资源标识 ─────────────────────────────

echo "[paas-trace] 正在查询 ${APPKEY} 在 Squirrel/Mafka/RDS/Eagle 的资源依赖关系..." >&2

WANT_ALL=1
[ -n "$ACCOUNT_NAME" ] && WANT_ALL=0
# --account-name 支持逗号分隔多值（如 Squirrel,Mafka,RDS,Eagle），大小写不敏感；
# 用逗号包裹后做子串匹配，避免前缀重叠误匹配（如 Eagle 误匹配到 Eaglex）。
_want() {
  [ "$WANT_ALL" = "1" ] && return 0
  local target
  target="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
  local list
  list=",$(echo "$ACCOUNT_NAME" | tr '[:upper:]' '[:lower:]' | tr -d ' '),"
  case "$list" in
    *",${target},"*) return 0 ;;
    *) return 1 ;;
  esac
}

# Avatar appkeyPaasCapacity：返回 Squirrel/RDS 的集群名映射（自动翻页）。
# 仅 Squirrel/RDS 消费这份数据（取 paasAppkey）；Mafka 路径A 已改为直接用
# 业务 appkey 查询，不再依赖这里的记录做前置判断，因此只有用户想查 Squirrel 或 RDS（或
# 未指定 --account-name 查全部平台）时才有必要发起这个请求，避免用户只查 Mafka/Eagle
# 时被这一步的鉴权失败/超时无谓阻断（mws_get_into 遇 401/403/3xx 会直接 exit 1）。
AVATAR_ITEMS_JSON="[]"
if _want Squirrel || _want RDS; then
  {
    page=1
    pageSize=100
    while true; do
      mws_get_into resp "avatar.mws.sankuai.com" "/api/v2/avatar/appkeyPaasCapacity/$(_urlencode "$APPKEY")?page=${page}&pageSize=${pageSize}"
      items=$(echo "$resp" | jq -c '.data.paasCapacityLevels.items // []' 2>/dev/null || echo '[]')
      count=$(echo "$items" | jq 'length' 2>/dev/null || echo 0)
      AVATAR_ITEMS_JSON=$(jq -c -n --argjson a "$AVATAR_ITEMS_JSON" --argjson b "$items" '$a + $b')
      if [ "$count" -lt "$pageSize" ]; then break; fi
      page=$((page + 1))
      if [ "$page" -gt 500 ]; then break; fi
    done
  } || true
fi
_pt_debug "Avatar appkeyPaasCapacity 返回 $(echo "$AVATAR_ITEMS_JSON" | jq 'length') 条依赖"

# Squirrel/RDS：从 Avatar appkeyPaasCapacity 取各自的 paasAppkey 直查（与 Web 页面一致）；
# 走 paasAppkey 标准路径，数据更稳定、无须依赖 customResourceType 精确过滤。
SQUIRREL_PAAS_APPKEYS=$(echo "$AVATAR_ITEMS_JSON" | jq -r '[.[] | select(.paasName | ascii_downcase == "squirrel") | .paasAppkey] | unique | .[]' 2>/dev/null || true)
RDS_PAAS_APPKEYS=$(echo "$AVATAR_ITEMS_JSON" | jq -r '[.[] | select(.paasName | ascii_downcase == "rds") | .paasAppkey] | unique | .[]' 2>/dev/null || true)

# Mafka：直接查 Mafka API 获取该 appkey 作为 Owner 的 Topic 短名，不依赖 Avatar 前置判断
# （Avatar 无记录不代表真的无 Mafka 依赖，可能只是 Avatar 数据未及时同步）
MAFKA_TOPICS=""
if _want Mafka; then
  pageNum=1; limit=100
  while true; do
    mws_get_into resp "mafka.mws.sankuai.com" "/mafka/restful/topic/list?pageNum=${pageNum}&limit=${limit}&type=2&content=$(_urlencode "$APPKEY")&auth=-1"
    names=$(echo "$resp" | jq -r '.data.list[]?.name // empty' 2>/dev/null || true)
    count=$(echo "$resp" | jq '.data.list | length' 2>/dev/null || echo 0)
    if [ -n "$names" ]; then MAFKA_TOPICS="${MAFKA_TOPICS}
${names}"; fi
    if [ "$count" -lt "$limit" ]; then break; fi
    pageNum=$((pageNum + 1))
    if [ "$pageNum" -gt 500 ]; then break; fi
  done
  MAFKA_TOPICS=$(echo "$MAFKA_TOPICS" | sed '/^$/d' | sort -u)
fi

# Eagle：先查 Avatar middleware 取集群名，再经官方 OpenAPI（无需鉴权）映射为 clusterAppkey
EAGLE_APPKEYS=""
if _want Eagle; then
  mws_get_into eagle_resp "avatar.mws.sankuai.com" "/api/v2/avatar/appkeyMetric/middleware?appkey=$(_urlencode "$APPKEY")"
  eagle_clusters=$(echo "$eagle_resp" | jq -r '.data.Search[]?.key // empty' 2>/dev/null || true)
  if [ -n "$eagle_clusters" ]; then
    # allClusterInfos 是公网 OpenAPI（无需鉴权），失败时不能静默吞成空——否则 Eagle 依赖
    # 存在却查不到 clusterAppkey，Eagle 整段静默消失，用户误以为无 Eagle 依赖（假阴性）。
    # 失败时显式提示并跳过 Eagle（记入 stderr，不进 _failedPaas，因依赖发现阶段尚未到步骤二）。
    if ! all_clusters_resp=$(curl -fsSL --max-time 15 "https://eagleweb.sankuai.com/openapi/clusters/allClusterInfos" 2>/dev/null); then
      echo "[paas-trace] ⚠ Eagle 集群映射 OpenAPI 请求失败，已跳过 Eagle（找到 ${eagle_clusters} 个集群依赖但无法映射为 clusterAppkey）" >&2
    else
      while IFS= read -r cname; do
        if [ -z "$cname" ]; then continue; fi
        capp=$(echo "$all_clusters_resp" | jq -r --arg n "$cname" '.data[]? | select(.clusterName == $n) | .clusterAppkey' 2>/dev/null | head -1 || true)
        if [ -n "$capp" ]; then EAGLE_APPKEYS="${EAGLE_APPKEYS}
${capp}"; fi
      done <<< "$eagle_clusters"
      EAGLE_APPKEYS=$(echo "$EAGLE_APPKEYS" | sed '/^$/d' | sort -u)
    fi
  fi
fi

# DEP_COUNT = 0 表示无可查依赖，提前退出。
# Mafka 路径A 恒可查（业务 appkey 直查，无依赖发现需求），故始终 +1 不参与此判断。
DEP_COUNT=0
if [ -n "$SQUIRREL_PAAS_APPKEYS" ]; then
  DEP_COUNT=$((DEP_COUNT + $(echo "$SQUIRREL_PAAS_APPKEYS" | grep -c . || true)))
fi
if [ -n "$RDS_PAAS_APPKEYS" ]; then
  DEP_COUNT=$((DEP_COUNT + $(echo "$RDS_PAAS_APPKEYS" | grep -c . || true)))
fi
if [ -n "$MAFKA_TOPICS" ]; then
  DEP_COUNT=$((DEP_COUNT + $(echo "$MAFKA_TOPICS" | grep -c . || true)))
fi
if [ -n "$EAGLE_APPKEYS" ]; then
  DEP_COUNT=$((DEP_COUNT + $(echo "$EAGLE_APPKEYS" | grep -c . || true)))
fi
# Mafka 路径A 恒可查（appkey 直查，无需依赖发现），命中时占位 +1 避免误判为"无依赖"。
if _want Mafka; then
  DEP_COUNT=$((DEP_COUNT + 1))
fi

if [ "$DEP_COUNT" -eq 0 ]; then
echo "[paas-trace] ${APPKEY} 在 Avatar 中未找到${ACCOUNT_NAME:+ ${ACCOUNT_NAME} }相关资源依赖" >&2
exit 0
fi

echo "[paas-trace] 已换取资源标识，开始调用 mcm cloudtrail list 查询变更事件..." >&2

# ── 步骤二：拿换到的资源标识，逐个系统调用 mcm cloudtrail list 查询 ────────

# 翻页查询用的公共过滤参数（不含 -s/-f/-p，由 _mcm_list_merge_paged 自行控制）
COMMON_ARGS_FILTER=()
if [ -n "$BEGIN" ]; then COMMON_ARGS_FILTER+=(--begin "$BEGIN"); fi
if [ -n "$END" ]; then COMMON_ARGS_FILTER+=(--end "$END"); fi
if [ -n "$ENV" ]; then COMMON_ARGS_FILTER+=(--env "$ENV"); fi
if [ -n "$USERNAME" ]; then COMMON_ARGS_FILTER+=(--username "$USERNAME"); fi
if [ -n "$USER_TYPE" ]; then COMMON_ARGS_FILTER+=(--user-type "$USER_TYPE"); fi
if [ -n "$EVENT_NAME" ]; then COMMON_ARGS_FILTER+=(--event-name "$EVENT_NAME"); fi

RESULTS_TMP=$(mktemp)
echo "[]" > "$RESULTS_TMP"

# 把 items（JSON 数组）合并进 RESULTS_TMP。用 jq -s 'add' 文件模式读取，避免 jq --argjson
# 把大 JSON 作为命令行参数传入时触发系统 ARG_MAX 导致数据静默丢失（曾造成时间范围越大结果越少的诡异现象）
_merge_items_into_results() {
  local items="$1"
  local items_file merged_tmp
  items_file=$(mktemp)
  printf '%s' "$items" > "$items_file"
  merged_tmp=$(mktemp)
  local err_file
  err_file=$(mktemp)
  if jq -c -s 'add' "$RESULTS_TMP" "$items_file" > "$merged_tmp" 2>"$err_file"; then
    mv "$merged_tmp" "$RESULTS_TMP"
    rm -f "$items_file" "$err_file"
    return 0
  else
    local err_msg
    err_msg=$(tail -1 "$err_file" 2>/dev/null | sed 's/^[[:space:]]*//')
    rm -f "$items_file" "$merged_tmp" "$err_file"
    _pt_debug "结果合并失败（${err_msg:-未知错误}），本批数据可能丢失"
    return 1
  fi
}

# 失败/截断的语义区别详见下方 json 输出分支的注释。
# _QUERIES 存 stderr 展示用的完整文案；_PAAS_NAMES 存归一化平台名（json 字段用，
# 取 desc 首个 ( 前部分，含逗号时按逗号拆成多个独立平台名）。
FAILED_QUERIES=()
FAILED_PAAS_NAMES=()
TRUNCATED_QUERIES=()
TRUNCATED_PAAS_NAMES=()

_record_failed_paas() {
  local names_part="$1" name
  IFS=',' read -ra _names_arr <<< "$names_part"
  for name in "${_names_arr[@]}"; do
    FAILED_PAAS_NAMES+=("$name")
  done
}

_record_truncated_paas() {
  local names_part="$1" name
  IFS=',' read -ra _names_arr <<< "$names_part"
  for name in "${_names_arr[@]}"; do
    TRUNCATED_PAAS_NAMES+=("$name")
  done
}

# pageSize=100；MAX_PAGES=100 对应最多 10000 条安全上限，
# 覆盖 Mafka Topic 精确过滤等数据量较大的场景。
# ⚠️ 本函数内部用 `-f json` + jq 是脚本自身为跨资源标识分页拉取、去重、合并所需的私有实现，
#    仅供脚本内部使用；AI 直接调用 `mcm cloudtrail list` 或本脚本时必须固定用 `-f md`，
_mcm_list_merge_paged() {
  local desc="$1"
  shift
  local filter_account_name=""
  if [ "${1:-}" = "--filter-account-name" ]; then
    filter_account_name="$2"
    shift 2
  fi
  local PAGE_SIZE=100 MAX_PAGES=100
  local page=1 total=0 fetched=0
  local err_file err_msg exit_code
  local resp_cmd
  while [ "$page" -le "$MAX_PAGES" ]; do
    err_file=$(mktemp)
    local resp
    # bash 3.2（macOS 系统自带）在 set -u 下对空数组展开会报 unbound variable，
    # COMMON_ARGS_FILTER 为空时必现，故用数组长度判断分支展开以兼容旧版 bash。
    if [ "${#COMMON_ARGS_FILTER[@]}" -gt 0 ]; then
      resp_cmd=(mcm cloudtrail list -s "$PAGE_SIZE" -p "$page" -f json "${COMMON_ARGS_FILTER[@]}" "$@")
    else
      resp_cmd=(mcm cloudtrail list -s "$PAGE_SIZE" -p "$page" -f json "$@")
    fi
    if resp=$("${resp_cmd[@]}" 2>"$err_file"); then
      exit_code=0
    else
      exit_code=$?
    fi
    if [ "$exit_code" -ne 0 ]; then
      err_msg=$(tail -1 "$err_file" 2>/dev/null | sed 's/^[[:space:]]*//')
      [ -z "$err_msg" ] && err_msg="退出码 ${exit_code}"
      rm -f "$err_file"
      FAILED_QUERIES+=("${desc}: ${err_msg}")
      _record_failed_paas "${desc%%(*}"
      echo "[paas-trace]   ${desc}：查询失败（${err_msg}，已翻 ${fetched} 条），已跳过继续查询其余平台" >&2
      return 0
    fi
    rm -f "$err_file"

    local items page_count
    items=$(echo "$resp" | jq -c '.data // []' 2>/dev/null || echo '[]')
    page_count=$(echo "$items" | jq 'length' 2>/dev/null || echo 0)
    total=$(echo "$resp" | jq -r '.total // 0' 2>/dev/null || echo 0)
    if [ -n "$filter_account_name" ]; then
      local raw_count kept_count noise_count
      raw_count=$page_count
      items=$(echo "$items" | jq -c --arg n "$filter_account_name" '[.[] | select(.accountName == $n)]' 2>/dev/null || echo '[]')
      kept_count=$(echo "$items" | jq 'length' 2>/dev/null || echo 0)
      noise_count=$((raw_count - kept_count))
      page_count=$kept_count
      if [ "$noise_count" -gt 0 ]; then
        echo "[paas-trace]   ⚠ ${desc}：后端 customResourcesFilter 过滤异常，本页 ${raw_count} 条中已客户端过滤掉 ${noise_count} 条非 ${filter_account_name} 噪音" >&2
      fi
    fi
    if ! _merge_items_into_results "$items"; then
      # 合并失败须计入 FAILED_QUERIES，不能只写 debug 日志——否则 fetched 计数正常但条数对不上
      FAILED_QUERIES+=("${desc}: 第 ${page} 页结果合并失败（本页 ${page_count} 条数据已丢失）")
      _record_failed_paas "${desc%%(*}"
      echo "[paas-trace]   ⚠ ${desc}：第 ${page} 页（${page_count} 条）合并失败，已丢失，继续翻下一页" >&2
    fi
    fetched=$((fetched + page_count))
    # 终止：本页为空 / 未拉满（最后一页）/ 已拉够 total / 触达安全上限
    if [ "$page_count" -eq 0 ] || [ "$page_count" -lt "$PAGE_SIZE" ] || { [ "$total" -gt 0 ] && [ "$fetched" -ge "$total" ]; }; then
      # 特判：后端对 total 字段同样有安全上限（与我们的 PAGE_SIZE*MAX_PAGES 相同），
      # 真实数据量超出时后端会把 total 截断到上限值，导致 fetched>=total 但实际数据并未拉完。
      # 识别条件：fetched 恰好等于安全上限 AND 最后一页拉满（说明后端做了截断，而非自然结束）。
      local limit=$((PAGE_SIZE * MAX_PAGES))
      if [ "$fetched" -eq "$limit" ] && [ "$page_count" -eq "$PAGE_SIZE" ]; then
        TRUNCATED_QUERIES+=("${desc}: 查询数据已超过 ${limit} 条，仅按前 ${limit} 条数据进行展示和聚合（建议缩小时间范围或加 --user-type 等过滤条件获取更完整数据）")
        _record_truncated_paas "${desc%%(*}"
        echo "[paas-trace]   ⚠ ${desc}：查询数据已超过 ${limit} 条，仅按前 ${limit} 条数据进行展示和聚合（已拉取 ${fetched} 条）" >&2
      else
        echo "[paas-trace]   ${desc}：共 ${fetched} 条（分页拉取完毕）" >&2
      fi
      return 0
    fi
    page=$((page + 1))
  done
  # 翻满 MAX_PAGES 仍未拉完：变更量超出安全上限，文案对齐 Web 页面「仅按前 N 条展示」，
  # 与查询失败区分（不建议重试，建议缩小时间范围）。
  local limit=$((PAGE_SIZE * MAX_PAGES))
  TRUNCATED_QUERIES+=("${desc}: 查询数据已超过 ${limit} 条，仅按前 ${limit} 条数据进行展示和聚合（建议缩小时间范围或加 --user-type 等过滤条件获取更完整数据）")
  _record_truncated_paas "${desc%%(*}"
  echo "[paas-trace]   ⚠ ${desc}：查询数据已超过 ${limit} 条，仅按前 ${limit} 条数据进行展示和聚合（已拉取 ${fetched} 条）" >&2
}

# Squirrel：逐集群 paasAppkey 直查（分页拉取）
if _want Squirrel && [ -n "$SQUIRREL_PAAS_APPKEYS" ]; then
  while IFS= read -r paasAppkey; do
    if [ -z "$paasAppkey" ]; then continue; fi
    echo "[paas-trace]   查询 Squirrel（paasAppkey: ${paasAppkey}）..." >&2
    _mcm_list_merge_paged "Squirrel(${paasAppkey})" --appkey "$paasAppkey" --account-name Squirrel
  done <<< "$SQUIRREL_PAAS_APPKEYS"
fi

# Mafka：路径A（appkey 直查，走标准 MCP Hub 路径）+ 路径B（Topic 名精确过滤，走 MCM 内部接口）
# 路径A 直接用业务 appkey 查询，不依赖是否发现了 Mafka 依赖。
if _want Mafka; then
  echo "[paas-trace]   查询 Mafka（appkey 直查）..." >&2
  _mcm_list_merge_paged "Mafka(appkey直查)" --appkey "$APPKEY" --account-name Mafka
  if [ -n "$MAFKA_TOPICS" ]; then
    names=$(echo "$MAFKA_TOPICS" | paste -sd, -)
    echo "[paas-trace]   查询 Mafka（Topic 名: ${names}）..." >&2
    # 不带 --appkey：语义为「该服务的 Topic 被谁动过」，保留其他 appkey 对这些 Topic 的操作记录。
    # --filter-account-name Mafka 为客户端兜底过滤，防止后端 customResourcesFilter 异常时引入噪音
    _mcm_list_merge_paged "Mafka(Topic精确过滤)" --filter-account-name Mafka --custom-resource-type "Mafka::TopicName" --custom-resource-names "$names"
  fi
fi

# RDS：appkey 直查（集群维度的 paasAppkey，逐个查询）
# 走标准 MCP Hub 路径且数据量大，用分页拉取避免 15s 超时（RDS 无 customResource 维度，走不了内部接口分批）
if _want RDS && [ -n "$RDS_PAAS_APPKEYS" ]; then
  while IFS= read -r paasAppkey; do
    if [ -z "$paasAppkey" ]; then continue; fi
    echo "[paas-trace]   查询 RDS（paasAppkey: ${paasAppkey}）..." >&2
    _mcm_list_merge_paged "RDS(${paasAppkey})" --appkey "$paasAppkey" --account-name RDS
  done <<< "$RDS_PAAS_APPKEYS"
fi

# Eagle：appkey 直查（集群维度的 clusterAppkey，逐个查询，同样分页拉取）
if _want Eagle && [ -n "$EAGLE_APPKEYS" ]; then
  while IFS= read -r clusterAppkey; do
    if [ -z "$clusterAppkey" ]; then continue; fi
    echo "[paas-trace]   查询 Eagle（clusterAppkey: ${clusterAppkey}）..." >&2
    _mcm_list_merge_paged "Eagle(${clusterAppkey})" --appkey "$clusterAppkey" --account-name Eagle
  done <<< "$EAGLE_APPKEYS"
fi

# ── 输出结果：按 eventUuid 去重，按开始时间倒序 ─────────────────

# 多路结果去重，按开始时间倒序。
# 优先按 eventUuid 去重；uuid 缺失时用「事件名+开始时间+操作人」兜底复合 key，
# 避免 unique_by 把所有 null-key 事件聚合成 1 条导致丢数据。
FINAL=$(jq -c '
  unique_by(.eventUuid // (.eventName // "") + "|" + (.eventStartTime // "") + "|" + (.userIdentity.name // ""))
  | sort_by(.eventStartTime) | reverse
' "$RESULTS_TMP" 2>/dev/null || echo '[]')
rm -f "$RESULTS_TMP"

COUNT=$(echo "$FINAL" | jq 'length' 2>/dev/null || echo 0)
# ⚠️ 本行「共 N 条变更事件」的统计日志故意仅在 MCM_DEBUG=1 时才打印（用 _pt_debug 而非
# 直接 echo）。历史上多次出现 AI 在 total=0 场景下，即使 stdout 已为空，仍从这行 stderr
# 统计日志中"看到了 0 这个数字"、进而觉得"有信息可说"而自创"XX 系统近一天无变更记录"
# 这类说明文字写进回复正文——反复加 [AI 指令] 禁止转述均未能根治（AI 会用不同措辞规避
# 禁止转述的字面约束）。唯一可靠的根治方式是从源头不让 AI 在默认（非 debug）调用下看到
# 任何与"0 条"相关的文字信号：AI 看不到"0 条"这个信息，自然不会产生"要不要说点什么"的
# 冲动。人工排障需要这个数字时，设置 MCM_DEBUG=1 重新执行即可看到完整日志。
if [ "$COUNT" -eq 0 ] && [ "$FORMAT" != "json" ]; then
  _pt_debug "共 ${COUNT} 条变更事件（appkey=${APPKEY}${ACCOUNT_NAME:+, account-name=${ACCOUNT_NAME}}），stdout 无任何输出，回复正文对这一路应保持完全沉默"
else
  echo "[paas-trace] 共 ${COUNT} 条变更事件（appkey=${APPKEY}${ACCOUNT_NAME:+, account-name=${ACCOUNT_NAME}}）" >&2
fi

if [ "${#FAILED_QUERIES[@]}" -gt 0 ]; then
  echo "" >&2
  echo "[paas-trace] ⚠ ${#FAILED_QUERIES[@]} 个子查询失败，以下结果可能不完整：" >&2
  for fq in "${FAILED_QUERIES[@]}"; do
    echo "[paas-trace]   · ${fq}" >&2
  done
  echo "[paas-trace]   建议设置 MCM_DEBUG=1 重新执行排查（常见原因：登录态过期、网络超时）" >&2
fi

if [ "${#TRUNCATED_QUERIES[@]}" -gt 0 ]; then
  echo "" >&2
  echo "[paas-trace] ⚠ ${#TRUNCATED_QUERIES[@]} 个子查询的数据量已超过安全上限，仅按前 N 条数据进行展示和聚合：" >&2
  for tq in "${TRUNCATED_QUERIES[@]}"; do
    echo "[paas-trace]   · ${tq}" >&2
  done
fi

# ── 展示分页 ──────────────────────────────────────────────────
# json 格式直接输出完整数据（供脚本集成，不做任何截断/分页）。
# md/table 格式不再按系统（accountName）分组，而是把所有系统的结果合并为
# 单一列表，按开始时间倒序（FINAL 已排好序），统一做一次分页切片——与
# `mcm cloudtrail list -f md` 的单表 + 单一 -p/-s 语义完全对齐，不区分
# 单系统/多系统场景：查 1 个还是 4 个系统，都只有一张表、一套页码。
# 每行仍保留「系统」列，用户可据此分辨每条记录来自哪个系统。
_TOTAL=$(echo "$FINAL" | jq 'length' 2>/dev/null || echo 0)
_OFFSET=$(( (DISPLAY_PAGE - 1) * DISPLAY_PAGE_SIZE ))
_PAGE_ITEMS=$(echo "$FINAL" | jq -c --argjson offset "$_OFFSET" --argjson limit "$DISPLAY_PAGE_SIZE" '
  .[$offset:($offset+$limit)]
' 2>/dev/null || echo '[]')
_TOTAL_PAGES=$(( (_TOTAL + DISPLAY_PAGE_SIZE - 1) / DISPLAY_PAGE_SIZE ))
[ "$_TOTAL_PAGES" -lt 1 ] && _TOTAL_PAGES=1
# 是否还有下一页未展示（用于底部翻页提示），语义与原「按系统溢出」一致，
# 现在只需判断合并后的单一列表是否还有剩余数据。
_HAS_OVERFLOW=0
[ "$_TOTAL" -gt "$((_OFFSET + DISPLAY_PAGE_SIZE))" ] && _HAS_OVERFLOW=1

if [ "$FORMAT" = "json" ]; then
  # 顶层 shape 固定 {data, _failedPaas, _truncatedPaas}：均无异常时两者为空数组，
  # 消费方（AI/脚本）据此判断结果是否完整，不得因 data 为空就断言"无变更"。
  # _failedPaas：子查询报错/合并失败，数据缺失，建议重试；
  # _truncatedPaas：查询成功但数据量已超过安全上限（当前时间范围内实际变更量更多），
  #   仅按前 N 条数据进行展示和聚合，建议缩小时间范围或加更多过滤条件（如 --user-type）复核。
  if [ "${#FAILED_PAAS_NAMES[@]}" -gt 0 ]; then
    failed_json=$(printf '%s\n' "${FAILED_PAAS_NAMES[@]}" | jq -R . 2>/dev/null | jq -s -c . 2>/dev/null || echo '[]')
  else
    failed_json='[]'
  fi
  if [ "${#TRUNCATED_PAAS_NAMES[@]}" -gt 0 ]; then
    truncated_json=$(printf '%s\n' "${TRUNCATED_PAAS_NAMES[@]}" | jq -R . 2>/dev/null | jq -s -c 'unique' 2>/dev/null || echo '[]')
  else
    truncated_json='[]'
  fi
  echo "$FINAL" | jq -c --argjson failed "$failed_json" --argjson truncated "$truncated_json" '{data: ., _failedPaas: $failed, _truncatedPaas: $truncated}'
elif [ "$FORMAT" = "md" ]; then
  # _TOTAL=0 时（合并后确实无任何变更），不输出标题/⚠️ 提示/表头/AI 指令，
  # 避免 AI 服从"原文复制展示"的强制指令而把这段无意义的空表格展示给用户，
  # 与 commands.md 中「补充查询结果为 0 条时不展示这一路」的规则保持一致，
  # 从数据源头消除"脚本指令"与"文档规则"互相打架的可能。
  # 注意：翻页翻过头（_TOTAL>0 但当前页为空）不属于本分支，仍需正常提示。
  if [ "$_TOTAL" -eq 0 ]; then
    _pt_debug "补充查询结果为 0 条，跳过 md 输出（不展示标题/提示/表头）"
  else
  # 表格列结构与 `mcm cloudtrail list -f md` 完全对齐（开始时间/事件名称/系统/操作人/环境/UUID），
  # 保持两条路径观感一致；不再按系统分组，单一标题 + 单一表格，直接消费上方
  # 已合并排序并按当前页切片好的 _PAGE_ITEMS。
  _MD_JQ='
    # ISO8601（含时区偏移与毫秒）→ epoch 毫秒；解析失败返回 null（兜底行为与 cloudtrail.ts 的
    # formatUuidCell 保持一致：mcmUrl 优先，空串视为缺失；缺失时拼事件毫秒级 begin/end）
    def iso2ms:
      try (
        capture("^(?<dt>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\\.(?<fr>[0-9]+))?(?<tz>Z|[+-][0-9]{2}:?[0-9]{2})?$") as $t
        | ($t.dt | strptime("%Y-%m-%dT%H:%M:%S") | mktime) as $local
        | (($t.tz // "Z") | if . == "Z" then 0
           else capture("^(?<sn>[+-])(?<hh>[0-9]{2}):?(?<mm>[0-9]{2})$")
                | ((.hh | tonumber) * 3600 + (.mm | tonumber) * 60) * (if .sn == "-" then -1 else 1 end)
           end) as $off
        | ($local - $off) * 1000 + (((($t.fr // "0") + "000") | .[0:3]) | tonumber)
      ) catch null;
    def fmtuuid:
      if .eventUuid == null or .eventUuid == "" then "-"
      else
        (if (.mcmUrl // "") != ""
         then .mcmUrl
         else (.eventStartTime | iso2ms) as $b
         | (.eventEndTime | iso2ms) as $e
         | $urlPrefix + .eventUuid
           + (if $b != null and $e != null
              then "?begin=" + ($b | tostring) + "&end=" + ($e | tostring)
              else ""
              end)
         end) as $href
        | "[" + .eventUuid + "](" + $href + ")"
      end;
    def fmtrow:
      [
        (if .eventStartTime then (.eventStartTime | .[0:19] | gsub("T"; " ")) else "-" end),
        (.eventNameCn // .eventName // "-"),
        (.accountName // .accountNameCn // "-"),
        (.userIdentity.name // .userIdentity.nameCN // "-"),
        (.env // "-"),
        fmtuuid
      ]
      | map(gsub("\\|"; "\\|"))
      | map("| " + . + " ") | add + "|";
    ["开始时间","事件名称","系统","操作人","环境","UUID"] as $header
    | ($header | map("| " + . + " ") | add + "|") as $headerLine
    | ($header | map("|---") | add + "|") as $sepLine
    | "## 补充查询结果（共 " + ($total | tostring) + " 条）",
      "",
      "> ⚠️ Squirrel/Mafka/RDS/Eagle 变更无法通过业务Appkey直查，已自动换标识补充查询",
      "",
      (if $page > $totalPages then
        "> 第 " + ($page|tostring) + " 页超出范围（共 " + ($totalPages|tostring) + " 页），以下为空", ""
      elif $total > $pageSize then
        "> 当前展示前 " + ($pageSize | tostring) + " 条", ""
      else empty end),
      $headerLine, $sepLine,
      (.[] | fmtrow),
      "",
      "> 共 " + ($total | tostring) + " 条，第 " + ($page|tostring) + " 页，每页 " + ($pageSize|tostring) + " 条"
  '

  # [AI 指令] 输出到 stderr，AI 工具可读但不会被粘贴进回复正文
  echo "[AI 指令] 请将以下 Markdown 内容原文逐字符复制展示给用户，不得添加任何总结、分析或引导句，不得手工转录/重新打字（尤其 UUID 列必须逐字符原样保留完整 36 位标准格式，禁止因排版考虑截断为前 8 位），直接结束。" >&2

  echo "$_PAGE_ITEMS" | jq -r \
    --argjson total "$_TOTAL" \
    --argjson totalPages "$_TOTAL_PAGES" \
    --argjson page "$DISPLAY_PAGE" \
    --argjson pageSize "$DISPLAY_PAGE_SIZE" \
    --arg urlPrefix "$EVENT_DETAIL_URL_PREFIX" \
    "$_MD_JQ"
  fi
else
  # table：不再按系统分组，单一标题 + 单一 TSV 表（column 对齐），
  # 复用上方已合并排序并切片好的 _PAGE_ITEMS。column 缺失时退化为纯 TSV。
  if [ "$_PAGE_EXPLICIT" -eq 1 ]; then
    if [ "$DISPLAY_PAGE" -gt "$_TOTAL_PAGES" ]; then
      echo "== 补充查询结果（第 ${DISPLAY_PAGE} 页超出范围，共 ${_TOTAL_PAGES} 页/${_TOTAL} 条，以下为空） =="
    else
      echo "== 补充查询结果（第 ${DISPLAY_PAGE}/${_TOTAL_PAGES} 页，每页 ${DISPLAY_PAGE_SIZE} 条） =="
    fi
  elif [ "$_TOTAL" -gt "$DISPLAY_PAGE_SIZE" ]; then
    echo "== 补充查询结果（共 ${_TOTAL} 条，当前展示前 ${DISPLAY_PAGE_SIZE} 条） =="
  else
    echo "== 补充查询结果（共 ${_TOTAL} 条） =="
  fi
  echo "⚠️ Squirrel/Mafka/RDS/Eagle 变更无法通过业务Appkey直查，已自动换标识补充查询"
  echo ""
  _TABLE_JQ='
    ["开始时间","事件名称","系统","操作人","环境","UUID"],
    (.[] |
      [
        (if .eventStartTime then (.eventStartTime | .[0:19] | gsub("T"; " ")) else "-" end),
        (.eventNameCn // .eventName // "-"),
        (.accountNameCn // .accountName // "-"),
        (.userIdentity.nameCN // .userIdentity.name // "-"),
        (.env // "-"),
        (.eventUuid // "-")
      ]
    )
    | @tsv
  '
  if command -v column >/dev/null 2>&1; then
    echo "$_PAGE_ITEMS" | jq -r "$_TABLE_JQ" | column -t -s $'\t'
  else
    echo "[paas-trace] ⚠ 未找到 column 命令，输出未对齐的 TSV（macOS 自带；Linux 可装 bsdmainutils/util-linux）" >&2
    echo "$_PAGE_ITEMS" | jq -r "$_TABLE_JQ"
  fi
  echo ""
fi

# [AI 指令] 用户若要求查看"剩余的/更早的/第 N 页"数据，直接复制下方命令重新执行即可
# （把 -p 换成所需页码，未指定则保持当前 -s），本脚本会返回合并后单一列表对应页的
# 数据，按开始时间/事件名称/系统/操作人/环境/UUID 六列原样展示；禁止改用
# cloudtrail list 重新查询同一 appkey（会查不全，见文件头部说明），也不要再用
# -f json + jq 手工切片。
# ⚠️ 下方打印到 stderr 的翻页命令本身仅供 AI 内部参考/复用，不属于展示内容，
# 禁止原文复述/粘贴进面向用户展示的回复正文（与其余 [paas-trace] stderr 日志处理规则一致）。
if [ "$FORMAT" != "json" ] && [ "$_HAS_OVERFLOW" -eq 1 ]; then
  _NEXT_PAGE=$((DISPLAY_PAGE + 1))
  echo "" >&2
  if [ "$_PAGE_EXPLICIT" -eq 1 ]; then
    echo "[paas-trace] ℹ 当前页（第 ${DISPLAY_PAGE} 页，每页 ${DISPLAY_PAGE_SIZE} 条）未展示完，如需查看下一页，可执行：" >&2
  else
    echo "[paas-trace] ℹ 结果超过展示上限（${DISPLAY_PAGE_SIZE} 条），如需翻页查看更多，可执行：" >&2
  fi
  echo "[paas-trace]   bash skill/mcm-cli/scripts/paas-trace.sh --appkey \"${APPKEY}\" ${ACCOUNT_NAME:+--account-name \"${ACCOUNT_NAME}\" }${BEGIN:+--begin \"${BEGIN}\" }${END:+--end \"${END}\" }-p ${_NEXT_PAGE} -s ${DISPLAY_PAGE_SIZE}" >&2
  echo "[paas-trace]   [AI 指令] 以上翻页命令仅供你（AI）内部参考——若用户后续明确要求查看下一页，直接照抄本段命令重新执行即可，省去手动拼接 appkey/时间参数；本段连同其余 [paas-trace] 开头的 stderr 日志均属过程信息，禁止原文复述/粘贴进面向用户展示的回复正文；当前页结果必须以表格末尾的条数行结束，不追加任何提示。" >&2
fi

# ── UUID 格式自检 ─────────────────────────────────────────────
# 防呆校验：eventUuid 直接取自接口原始字段、未做任何裁剪，理应都是标准 36 位
# UUID。此处并非预期会出错，而是防止未来 jq 逻辑被误改动引入截断时，仍有一道
# 机器可判定的信号可以及时暴露问题，而不是静默展示错误数据。
if [ "$FORMAT" != "json" ]; then
  _BAD_UUID_COUNT=$(echo "$FINAL" | jq '
    [.[] | select(.eventUuid != null and (.eventUuid | test("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$") | not))] | length
  ' 2>/dev/null || echo 0)
  if [ "$_BAD_UUID_COUNT" -gt 0 ]; then
    echo "" >&2
    echo "[paas-trace] ⚠⚠⚠ 数据异常：检测到 ${_BAD_UUID_COUNT} 条 eventUuid 不符合标准 36 位 UUID 格式，请勿直接展示，需先排查是否为接口返回异常或展示环节被截断" >&2
  fi
fi

if [ "${#FAILED_QUERIES[@]}" -gt 0 ]; then
  exit 1
fi
