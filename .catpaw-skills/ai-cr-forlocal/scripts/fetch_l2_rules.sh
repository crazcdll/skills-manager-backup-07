#!/usr/bin/env bash
# fetch_l2_rules.sh — 平台L2团队规则拉取(防腐层)
#
# ┌─ 设计契约(上层唯一依赖,内部实现可替换) ──────────────────────┐
# │ 输入: --repo org/repo  [--out <bundle目录>] [--timeout N]      │
# │       (--out 缺省时从 --repo 单点推导 /tmp/cr_l2_bundle_{org_repo} │
# │        对齐 agent skill fetch-rule-bundle.sh 命名模式)      │
# │ 输出: 0=成功  2=参数错  3=依赖缺失/认证不可用  4=失败/超时   │
# │       5=domain确认(同步模式预传 domain,按 4 处理)             │
# │       6=链路健康但无L2团队规则(未登记/未订阅)                │
# │ 成功时产出: {out}/team/<规则集ID>/*.md + manifest.json        │
# └─────────────────────────────────────────────────────────────┘
# 底层实现 v1: 探测 mt-code-standards-setup skill + node Runner
#   v2(官方 CLI 就绪后): 只替换本层内部调用,上层契约不变
#
# 防腐原则: 本脚本任何失败 → 上层(3A3)仅记录日志,绝不阻断 prep。
# 主流程不变量: L2 链路失败时,CR 结果与无 L2 能力时完全一致。

set -uo pipefail

LOG_PREFIX="[L2]"
log() { echo "$LOG_PREFIX $(date '+%H:%M:%S') $*" >&2; }  # stderr: 保证 stdout 纯净(probe-only 契约),主流程 stderr 同样进日志文件

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_FULL=""
OUT=""
TIMEOUT=50

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)    REPO_FULL="$2"; shift 2 ;;
    --out)     OUT="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --probe-only) PROBE_ONLY=1; shift ;;
    *) log "ERROR: 未知参数 $1"; exit 2 ;;
  esac
done

# --probe-only: 仅探测 Runner 可用性（供 env-check 等外部环节消费，单一真源）
# rc=0 + stdout=Runner 路径；rc=3 未找到（stderr 带安装指引）
# 注意: 此块必须在函数定义之后执行(见文件后段)

# --probe-only 模式无需 --repo/--out（纯探测，供 env-check 消费）
if [ "${PROBE_ONLY:-0}" != "1" ]; then
  [ -n "$REPO_FULL" ] || { log "ERROR: 缺少 --repo"; exit 2; }
  [ -n "$OUT" ] || { OUT="/tmp/cr_l2_bundle_$(echo "$REPO_FULL" | tr '/' '_')"; }  # 缺省从 --repo 单点推导,对齐 agent 命名模式
  case "$REPO_FULL" in */*) ;; *) log "ERROR: --repo 需 org/repo 格式,当前: $REPO_FULL"; exit 2 ;; esac
fi

# ══ 1. Runner 探测(A 层: 多候选 + 三件套完整性检查,防止探测到旧版本残留) ══
probe_l2_runner() {
  local cands=(
    "${HOME:-$PWD}/.openclaw/skills/mt-code-standards-setup/scripts/sync-effective-rules-with-sso.mjs"
    "$SCRIPT_DIR/../../mt-code-standards-setup/scripts/sync-effective-rules-with-sso.mjs"
    "${HOME:-$PWD}/.mtskills/mt-code-standards-setup/scripts/sync-effective-rules-with-sso.mjs"
  )
  # env 显式覆盖(仅绝对路径;防止相对路径执行向量)
  if [ -n "${CR_L2_RUNNER:-}" ]; then
    case "$CR_L2_RUNNER" in
      /*) cands=("$CR_L2_RUNNER" "${cands[@]}") ;;
      *)  log "WARN: CR_L2_RUNNER 非绝对路径,忽略: $CR_L2_RUNNER" ;;
    esac
  fi
  local r
  for r in "${cands[@]}"; do
    [ -n "$r" ] || continue
    [ -f "$r" ] || continue
    # 三件套: 存在 + 同级认证模块 + 语法检查(损坏/半安装拦截)
    if [ ! -f "$(dirname "$r")/portable-user-auth.mjs" ]; then
      log "候选缺同级认证模块(portable-user-auth.mjs),跳过: $r"
      continue
    fi
    if ! node --check "$r" >/dev/null 2>&1; then
      log "候选语法检查失败(疑似损坏/半安装),跳过: $r"
      continue
    fi
    RUNNER="$r"
    log "Runner 命中: $r (mtime $(stat -c %y "$r" 2>/dev/null | cut -d. -f1))"
    return 0
  done
  log "SKIP: 未找到 mt-code-standards-setup"
  log "  → 安装: mtskills pull mt-code-standards-setup(CatPaw skill 市场亦可)"
  log "  → 不需要平台L2规则可忽略,仓库内规则不受影响"
  return 3
}

# ══ 2. 认证预检短路(避免在注定失败的拉取上消耗 60s 超时) ══
auth_signal() {
  [ -n "${RULE_OBSERVABILITY_USER_TOKEN:-}" ] && return 0
  env | grep -qE '^(CATPAW_|CATX_|CATDESK_|CATCLAW_|SANDBOX_|CLAUDE_|CODEX_)' && return 0
  return 1
}

# ══ 3. 主流程 ══
RUNNER=""
if [ "${PROBE_ONLY:-0}" = "1" ]; then
  # probe 模式: 仅探测 + 认证信号提示,不做拉取
  if probe_l2_runner; then
    if ! auth_signal; then
      log "注意: Runner 已安装但当前无认证环境信号(CatPaw/token)，运行时 L2 将跳过"
    fi
    echo "$RUNNER"
    exit 0
  fi
  exit 3
fi
probe_l2_runner || exit 3
auth_signal || { log "SKIP: 无认证环境信号(CatPaw/env token),L2 跳过(省去注定失败的超时)"; exit 3; }

# rm -rf 护栏: 只允许 /tmp/ 下目录(防参数写错时误删仓库/家目录)
case "$OUT" in
  /tmp/*) ;;
  *) log "ERROR: --out 仅允许 /tmp/ 下目录,当前: $OUT"; exit 2 ;;
esac

# ── timeout 兼容层(与 cr-cli.sh run_to 逻辑一致,本脚本独立部署不能 source 依赖)──
run_to() {
  local secs="$1"; shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$secs" "$@"
  else
    log "⚠️ 无 timeout/gtimeout,直接执行(无超时保护,进程可能挂起): $*"
    "$@"
  fi
}

[ -d "$OUT" ] && { rm -rf "$OUT"; log "清理旧 bundle: $OUT"; }
mkdir -p "$OUT" || { log "ERROR: 无法创建 $OUT"; exit 4; }

# 空目录 git init: Runner 只验证 .git 存在性(域自判),不读代码
(cd "$OUT" && git init -q .) || { log "ERROR: git init 失败"; exit 4; }

log "拉取开始: repo=$REPO_FULL domain=backend timeout=${TIMEOUT}s"
# Runner 参数契约(mt-code-standards-setup sync-effective-rules-with-sso.mjs):
#   合法: --repo-root --repository --gateway-url --execution-agent --auth-agent
#         --skill-version --pull-id --mis --domain --stage (均为带值参数,无 --l2-only/--timeout)
#   --timeout 是本脚本(上层调用方)的 shell 层参数,不能透传给 Runner;
#   l2-only 语义由本脚本提取层实现(只 mv team/,company/ 直接清)
run_to "$TIMEOUT" node "$RUNNER" \
    --repo-root "$OUT" \
    --repository "$REPO_FULL" \
    --stage cr \
    --execution-agent sandbox \
    --domain backend \
    > "$OUT/.runner.log" 2>&1
RC_NODE=$?
# domain 确认模式: rc=5 语义(Runner 未识别 domain 且仓库无代码特征)——本脚本已显式传
# --domain backend,理论上不触达;保留 grep 兜底以防 Runner 行为变化
if grep -q "RULE_BUNDLE_DOMAIN_CONFIRMATION_REQUIRED" "$OUT/.runner.log" 2>/dev/null; then
  log "domain 确认模式(已显式传 backend 仍要求确认)——按契约当作拉取失败处理"
  rm -rf "$OUT/.git" 2>/dev/null
  exit 5
fi
if [ $RC_NODE -ne 0 ]; then
  log "拉取失败(rc=$RC_NODE)——可能原因: 认证过期/网络/首次安装窗口(重跑一次即恢复)"
  log "  若持续失败且刚更新过 mt-code-standards-setup,可能是参数契约变化,检查其更新说明"
  tail -3 "$OUT/.runner.log" >&2 2>/dev/null || true
  # 失败清理: 避免不完整的 .git/.mdp 残留占 /tmp(下轮重跑会 rm -rf,但当日多次失败会堆积)
  rm -rf "$OUT/.git" 2>/dev/null
  exit 4
fi
# 收据校验: Runner 成功但无收据 schema → 输出不完整风险,按失败处理
if ! grep -qE "mt-(effective-rule-bundle|l1-bootstrap)-install/v1" "$OUT/.runner.log" 2>/dev/null; then
  log "Runner rc=0 但未识别到收据 schema,按失败处理"
  rm -rf "$OUT/.git" 2>/dev/null
  exit 4
fi

# ══ 4. l2-only 丢弃层: 只留 team/,其余(L1 company/等)零残留 ══
if [ ! -d "$OUT/.mdp/rules/team" ]; then
  log "拉取成功但无 team 规则集(未订阅/纯公司层)"
  rm -rf "$OUT/.mdp" "$OUT/.git" 2>/dev/null
  # 目录保留(空 team 状态)
  # rc=6: 拉取链路健康但无 L2 团队规则(未登记/未订阅),与真失败(rc=4)区分供上层归因
  exit 6
fi
mv "$OUT/.mdp/rules/team" "$OUT/team" || { rm -rf "$OUT/.git" 2>/dev/null; log "ERROR: team 目录迁移失败"; exit 4; }
[ -f "$OUT/.mdp/rules/manifest.json" ] && mv "$OUT/.mdp/rules/manifest.json" "$OUT/manifest.json"
rm -rf "$OUT/.mdp" "$OUT/.git" "$OUT/.runner.log"

# 规则文件计数: 只计 team/*/<顶层>md(与 cr-cli 提取口径一致——cr-cli 只扫 team/<规则集>/*.md 顶层,不递归子目录)
# 口径不一致会导致: 规则全在子目录时 find 递归计数>0 但提取结果为空 → 统一为顶层口径
RULE_COUNT=$(find "$OUT/team" -maxdepth 2 -name '*.md' 2>/dev/null | wc -l)
log "拉取完成: ${RULE_COUNT} 个规则文件(顶层口径)"
# team/ 存在但顶层无 md(规则全在子目录/空集) → rc=6(no-team-rules)而非 rc=4:
# 链路是健康的,归因 fetch-failed 会误导排查方向
[ "$RULE_COUNT" -gt 0 ] || exit 6
exit 0
