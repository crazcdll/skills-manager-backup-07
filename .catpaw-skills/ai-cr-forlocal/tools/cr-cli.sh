#!/usr/bin/env bash
# cr-cli.sh — AI Local CR Orchestrator
# 将 Step 0~3 / 5 / 8 的机械逻辑收编为单命令，一次批准跑完。
# Agent 只需：bash cr-cli.sh prep → 读 JSON 摘要 → Step 4 审查 → bash cr-cli.sh publish → Step 6/7 交互
#
# 子命令：
#   prep    Step 0~3 一把跑：环境自检 / GitNexus 后台建图 / diff / ONES / 规则匹配 / 信号检测
#           输出 /tmp/cr_prep_{repo}.json 摘要（含各子步骤 status，失败可降级）
#   publish Step 5 一把跑：调 publish_results_local.py（学城+DB+SDLC JSON+本地报告）
#           进度日志写 /tmp/cr_publish_{repo}.log，stdout 只出报告（防 tail 截断丢状态）
#   clean   Step 8 清理（zsh 通配符安全）
#
# 设计原则：
#   - 幂等可重跑：失败后直接重跑同命令，各阶段产物独立落盘
#   - 失败不阻塞：单个子步骤失败只标记 status=failed/degraded，摘要照常输出
#   - 判断权在 Agent：prep 只交数据（信号/规则组/SDD 可用性），分组与 spawn 决策留给主 Agent

set -u

# ── bash 3.2 兼容：set -u 下空数组/命令替换缺陷的统一防御 ──
# macOS 自带 bash 3.2.57 对空数组展开 "${ARR[@]}" 和命令替换赋值有已知缺陷
# 在 set -u 下会误报 unbound variable。此处用 __u_guard 包裹风险区段。
__u_guard() { set +u; }
__u_restore() { set -u; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"

log() { echo "[cr-cli] $*" >&2; }

# ── 从 git remote 解析 org/repo（与 agent 对齐），失败回退 basename ──
resolve_repo_name() {
  local rp="$1"
  local remote_url repo_name
  remote_url=$(git -C "$rp" remote get-url origin 2>/dev/null || echo "")
  if [ -n "$remote_url" ]; then
    repo_name=$(python3 -c "
import re, sys
u = sys.argv[1]
m = re.search(r'[:/]code/([^/]+/[^/]+?)(\.git)?$', u) or re.search(r'[:/]([^/]+/[^/]+?)(\.git)?$', u)
print(m.group(1) if m else '')
" "$remote_url" 2>/dev/null || echo "")
    [ -n "$repo_name" ] && { echo "$repo_name"; return; }
  fi
  basename "$(git -C "$rp" rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || basename "$rp"
}

# ── 跨平台 timeout 兼容（macOS 无 timeout，回退 gtimeout；都没有则裸跑）──
run_to() {
  local secs="$1"; shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$secs" "$@"
  else
    log "⚠️ 无 timeout/gtimeout，裸跑（可能挂起）: $*"
    "$@"
  fi
}

# ── 参数解析 ──
CMD="${1:-}"; shift || true
REPO_PATH="" BRANCH="" BASE="" ONES_ID="" OPERATOR_MIS=""
ISSUES_FILE="" OVERVIEW="" CONCLUSION="" EXTRA_ARGS=()
# Bug 1 防御：所有可能被 set -u 引用前未赋值的变量在此预初始化
RF_SUM="" TIER="" TOTAL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)    REPO_PATH="$2"; shift 2 ;;
    --branch)  BRANCH="$2";  shift 2 ;;
    --base)    BASE="$2";    shift 2 ;;
    --ones|--ones-id)  ONES_ID="$2"; shift 2 ;;   # 纯数字=全局ID(建联)；FEVUO/ONES-xxx=仅审查上下文(见 prep 1B)；--ones-id 为对外 SOP 别名
    --operator-mis) OPERATOR_MIS="$2"; shift 2 ;;
    --issues-file) ISSUES_FILE="$2"; shift 2 ;;
    --overview) OVERVIEW="$2"; shift 2 ;;
    --conclusion-override) CONCLUSION="$2"; shift 2 ;;
    --) shift; EXTRA_ARGS+=("$@"); break ;;
    *) EXTRA_ARGS+=("$1"); shift ;;
  esac
done

case "$CMD" in
prep)
  # ═══════════ Step 0~3 编排 ═══════════

  # ── 预清理：确保上一次 CR 的中间产物不污染本次 ──
  setopt null_glob 2>/dev/null || true
  rm -f /tmp/local_cr_diff.txt /tmp/local_cr_diff_slim.txt /tmp/cr_slim.log /tmp/local_cr_files.txt /tmp/cr_matched_rules.json 2>/dev/null
  rm -f /tmp/cr_changed_symbols.json /tmp/cr_signal_rules.json 2>/dev/null
  rm -f /tmp/cr_signals_*.md /tmp/cr_ones_context.json /tmp/cr_ones_err.log /tmp/cr_ones_db_info.json /tmp/cr_ones_detail.json 2>/dev/null
  rm -f /tmp/cr_route_plan.json /tmp/cr_route_plan.log 2>/dev/null
  rm -f /tmp/cr_route_4a_*.md /tmp/cr_route_4b_*.md 2>/dev/null
  rm -f /tmp/cr_suspects_*.json 2>/dev/null
  rm -rf /tmp/cr_rule_trim 2>/dev/null
  rm -f /tmp/cr_rule_filter.json /tmp/cr_rule_filter.log 2>/dev/null
  rm -f /tmp/cr_business_context.md /tmp/cr_review_*.json /tmp/cr_custom_rules_*.md /tmp/cr_source_context.md 2>/dev/null
  rm -f /tmp/cr_4d_input_core.md /tmp/cr_4d_input_code.md 2>/dev/null
  rm -f /tmp/cr_issues_*_*.json /tmp/cr_issues_*_*.json.tmp 2>/dev/null
  rm -f /tmp/cr_gitnexus_build.pid /tmp/cr_gitnexus_build.log 2>/dev/null
  # ⚠️ ai_cr_result_*.json 是最终产物（SDLC JSON），预清理不删除（上次 CR 可能卡在 Step 7 未走 Step 8）
  rm -f /tmp/cr-env-cache-* 2>/dev/null
  rm -f /tmp/cr_prep_*.json /tmp/cr_publish_*.log /tmp/cr_publish_*.stdout /tmp/cr_publish_stdout.txt /tmp/cr_env_check_*.log 2>/dev/null
  rm -f /tmp/cr_probe_mapper.txt /tmp/cr_review_input_*.json /tmp/cr_review_miss_*.json /tmp/cr_review_rules_*.md /tmp/cr_review_verdict_*.json 2>/dev/null
  rm -f /tmp/cr_review_meta_*.json /tmp/cr_route_4a_all.md 2>/dev/null
  rm -rf /tmp/cr_layer2_results 2>/dev/null
  rm -f /tmp/cr_signals_run.log /tmp/cr_l2_extract.log /tmp/cr_rules_err.log /tmp/cr_db_write_async.log 2>/dev/null
  rm -f /tmp/ai_cr_hook_trigger_*.json /tmp/ai_cr_ide_trigger_*.json 2>/dev/null
  # GitNexus 仓库内产物（上次 CR 残留）
  RepoRoot=$(git -C "$REPO_PATH" rev-parse --show-toplevel 2>/dev/null || echo "$REPO_PATH")
  [ -d "$RepoRoot/.gitnexus" ] && rm -rf "$RepoRoot/.gitnexus/"
  [ -d "$RepoRoot/.claude/skills/gitnexus" ] && rm -rf "$RepoRoot/.claude/skills/gitnexus/"

  INVOKE_MODE="${INVOKE_MODE:-}"
  if [ -z "$REPO_PATH" ]; then
    if [ "$INVOKE_MODE" = "sdlc" ]; then log "❌ sdlc 模式必须 --repo"; exit 1; fi
    read -p "📝 本地仓库路径: " REPO_PATH
  fi
  REPO_PATH=$(realpath "$REPO_PATH" 2>/dev/null || echo "$REPO_PATH")
  if [ ! -d "$REPO_PATH/.git" ]; then log "❌ 不是 git 仓库: $REPO_PATH"; exit 1; fi
  BRANCH="${BRANCH:-$(git -C "$REPO_PATH" branch --show-current 2>/dev/null)}"
  BASE="${BASE:-master}"
  export LOCAL_REPO_PATH="$REPO_PATH" LOCAL_BRANCH="$BRANCH" BASE_BRANCH="$BASE" SKILL_ROOT

  REPO_FULL=$(resolve_repo_name "$REPO_PATH")   # org/repo 格式（DB + publish 用）
  REPO_NAME="${REPO_FULL##*/}"                    # 只取 repo 部分（文件名用，不带斜杠）
  SUMMARY="/tmp/cr_prep_${REPO_NAME}.json"
  : > "$SUMMARY"

  emit() { # emit <key> <value> —— 增量拼 JSON（python 兜底转义）
    python3 - "$SUMMARY" "$1" "$2" << 'PYEOF'
import json, sys
p, k, v = sys.argv[1], sys.argv[2], sys.argv[3]
try: d = json.load(open(p))
except Exception: d = {}
d[k] = v
json.dump(d, open(p, 'w'), ensure_ascii=False)
PYEOF
  }

  emit_json() { # emit_json <key> <json_literal>
    python3 - "$SUMMARY" "$1" "$2" << 'PYEOF'
import json, sys
p, k, raw = sys.argv[1], sys.argv[2], sys.argv[3]
try: d = json.load(open(p))
except Exception: d = {}
d[k] = json.loads(raw)
json.dump(d, open(p, 'w'), ensure_ascii=False)
PYEOF
  }

  # ── 0A 环境自检（PID 级缓存）──
  ST_ENV=ok
  if ! bash "$SKILL_ROOT/scripts/env-check.sh" > /tmp/cr_env_check_${REPO_NAME}.log 2>&1; then
    ST_ENV=degraded; log "⚠️ env-check 降级（详见 /tmp/cr_env_check_${REPO_NAME}.log）"
  fi
  emit env "$ST_ENV"

  # ── 0B GitNexus 后台建图（非阻塞）──
  rm -f /tmp/cr_gitnexus_build.pid
  ST_GN=skipped
  if command -v gitnexus >/dev/null 2>&1 && [ -x "$REPO_PATH" ]; then
    [ -f "$HOME/.openclaw/sqt-env" ] && source "$HOME/.openclaw/sqt-env" 2>/dev/null || {
      export GITNEXUS_EMBEDDING_URL=https://mmc.sankuai.com/openclaw/v1/native
      export GITNEXUS_EMBEDDING_API_KEY=***
      export GITNEXUS_EMBEDDING_MODEL=text-embedding-3-large
      export GITNEXUS_EMBEDDING_DIMS=3072
    }
    (
      cd "$REPO_PATH"
      S=$(date +%s)
      gitnexus analyze --force --skip-agents-md > /tmp/cr_gitnexus_build.log 2>&1
      echo "BUILD_SECONDS=$(( $(date +%s) - S ))" >> /tmp/cr_gitnexus_build.log
    ) & disown 2>/dev/null || true
    echo $! > /tmp/cr_gitnexus_build.pid
    ST_GN=building
    log "📌 GitNexus 后台建图 PID=$(cat /tmp/cr_gitnexus_build.pid)"
  fi
  emit gitnexus "$ST_GN"

  # ── 1A diff（三层 fallback）──
  ST_DIFF=ok; DIFF_LINES=0; SUBS=0; EMPTY_REASON=""
  cd "$REPO_PATH"
  git diff "$BASE...$BRANCH" > /tmp/local_cr_diff.txt 2>/dev/null \
    || git diff "origin/$BASE...$BRANCH" > /tmp/local_cr_diff.txt 2>/dev/null \
    || git diff "$BASE..$BRANCH" > /tmp/local_cr_diff.txt 2>/dev/null \
    || git diff HEAD~1 > /tmp/local_cr_diff.txt 2>/dev/null \
    || ST_DIFF=failed
  git diff --name-only "$BASE...$BRANCH" > /tmp/local_cr_files.txt 2>/dev/null || true
  if [ "$ST_DIFF" = "ok" ]; then
    DIFF_LINES=$(wc -l < /tmp/local_cr_diff.txt | tr -d ' ')
    SUBS=$(grep -vE '\.(lock|generated|auto)$|/generated/|/auto/' /tmp/local_cr_files.txt 2>/dev/null | grep -v '^$' | wc -l | tr -d ' ')
    [ "$DIFF_LINES" -le 1 ] && EMPTY_REASON="diff 为空"
    if [ -z "$EMPTY_REASON" ] && [ "${SUBS:-0}" -eq 0 ]; then EMPTY_REASON="变更文件均为 lock/generated 类"; fi
  fi
  emit diff_lines "$DIFF_LINES"; emit substantive_files "$SUBS"; emit diff_status "$ST_DIFF"
  if [ -n "$EMPTY_REASON" ]; then
    emit empty_reason "$EMPTY_REASON"
    emit repo "$REPO_NAME"; emit branch "$BRANCH"; emit base "$BASE"
    log "✅ ${EMPTY_REASON}，无需审查（SDLC 零问题 JSON 由 publish --empty-result 产出）"
    cat "$SUMMARY"; exit 0
  fi

  # ── 1D 前端候选检测（后缀仅作线索，Agent 核对模块用途后决定委托）──
  FRONTEND_ONLY=false; FE_FILES=""
  if [ -s /tmp/local_cr_files.txt ]; then
    # 前端扩展名集合
    FE_EXT='\.(vue|tsx|jsx|ts|js|css|scss|less|sass|styl|html|svelte|astro)$'
    # 后端扩展名集合（任一存在就不是纯前端）
    BE_EXT='\.(java|py|go|rs|c|cpp|cc|h|hpp|kt|scala|rb|php|swift|dart)$'
    TOTAL_FE=$(grep -ciE "$FE_EXT" /tmp/local_cr_files.txt 2>/dev/null || true)
    TOTAL_BE=$(grep -ciE "$BE_EXT" /tmp/local_cr_files.txt 2>/dev/null || true)
    if [ "$TOTAL_BE" -eq 0 ] && [ "$TOTAL_FE" -gt 0 ]; then
      FRONTEND_ONLY=true
      FE_FILES=$(grep -iE "$FE_EXT" /tmp/local_cr_files.txt | tr '\n' ',' | sed 's/,$//')
      log "📌 检测到前端候选（${TOTAL_FE} 文件），需 Agent 核对模块用途"
    fi
  fi
  emit frontend_only "$FRONTEND_ONLY"; emit frontend_files "$FE_FILES"
  if [ "$FRONTEND_ONLY" = "true" ]; then
    emit repo "$REPO_NAME"; emit branch "$BRANCH"; emit base "$BASE"
    emit operator_mis "${OPERATOR_MIS:-unknown}"
    # 候选路径提前返回；Agent 核对模块用途后决定 Step 1F 或补齐后端准备
    cat "$SUMMARY"; exit 0
  fi

  # ── 1A2 diff 瘦身（剥离 import/Lombok/空行，压缩 context → 子 Agent 读 slim 版）──
  SLIM_LINES=0; SLIM_SAVED=0
  if [ -s /tmp/local_cr_diff.txt ]; then
    python3 "${SKILL_ROOT}/scripts/diff_slim.py" \
      --diff /tmp/local_cr_diff.txt \
      --output /tmp/local_cr_diff_slim.txt > /tmp/cr_slim.log 2>&1
    if [ -s /tmp/local_cr_diff_slim.txt ]; then
      SLIM_LINES=$(wc -l < /tmp/local_cr_diff_slim.txt | tr -d ' ')
      SLIM_SAVED=$((DIFF_LINES - SLIM_LINES))
      log "📏 diff_slim: ${DIFF_LINES}→${SLIM_LINES} 行 (省 ${SLIM_SAVED} 行)"
    else
      # 瘦身失败 → slim 版 = 原始版
      cp /tmp/local_cr_diff.txt /tmp/local_cr_diff_slim.txt
      SLIM_LINES=$DIFF_LINES
      log "⚠️ diff_slim 失败，使用原始 diff（$(cat /tmp/cr_slim.log)）"
    fi
  fi
  emit slim_lines "$SLIM_LINES"; emit slim_saved "$SLIM_SAVED"

  # ── 1A3 变更文件源码包（子 Agent 公共上下文，避免各自重复 git show）──
  # 大 PR（diff > 500 行）时对测试/配置/纯删除文件裁剪，生产代码全量保留
  SOURCE_CTX="/tmp/cr_source_context.md"
  SOURCE_COUNT=0
  SLIM_SKIP=0
  BIG_PR=0; [ "${DIFF_LINES:-0}" -gt 500 ] && BIG_PR=1
  if [ -s /tmp/local_cr_files.txt ]; then
    {
      echo "# 变更文件完整源码（prep 自动提取，子 Agent 公共上下文）"
      if [ "$BIG_PR" -eq 1 ]; then
        echo "（大 PR diff>500 行：测试/配置/纯删除文件已裁剪，生产代码全量保留）"
      fi
      echo
      while IFS= read -r f; do
        [ -z "$f" ] && continue
        case "$f" in
          *.java|*.kt|*.scala|*.py|*.go|*.xml|*.yaml|*.yml|*.properties)
            content=$(git -C "$REPO_PATH" show "$BRANCH:$f" 2>/dev/null || true)
            if [ -n "$content" ]; then
              # 大 PR 裁剪：测试文件 / 配置文件 / 纯删除文件
              SKIP_FILE=0
              if [ "$BIG_PR" -eq 1 ]; then
                # A. 测试文件：只留类签名 + 方法签名
                case "$f" in
                  *Test.java|*Tests.java|*Spec.java|*Specs.java|*IT.java|*ITs.java|*/test/*|*/tests/*|*_test.go|*_test.py|*spec.py|*conftest.py)
                    SKIP_FILE=1 ;;
                esac
                # B. 配置文件：只留 key 级摘要
                if [ "$SKIP_FILE" -eq 0 ]; then
                  case "$f" in
                    *.xml|*.yaml|*.yml|*.properties) SKIP_FILE=2 ;;
                  esac
                fi
                # C. 纯删除文件：diff 中该文件只有删除操作，跳过源码
                if [ "$SKIP_FILE" -eq 0 ]; then
                  DEL_ONLY=$(git -C "$REPO_PATH" diff --numstat "$BASE...$BRANCH" -- "$f" 2>/dev/null | awk '{print $1, $2}')
                  ADD_LINES=$(echo "$DEL_ONLY" | awk '{print $1}')
                  DEL_LINES=$(echo "$DEL_ONLY" | awk '{print $2}')
                  if [ "$ADD_LINES" = "0" ] && [ "$DEL_LINES" != "0" ] && [ -n "$DEL_LINES" ]; then
                    SKIP_FILE=3
                  fi
                fi
              fi
              if [ "$SKIP_FILE" -eq 0 ]; then
                echo "## File: $f"
                echo '```'
                echo "$content"
                echo '```'
                echo
                SOURCE_COUNT=$((SOURCE_COUNT + 1))
              elif [ "$SKIP_FILE" -eq 1 ]; then
                # 测试文件：只保留 class/method 签名行
                echo "## File: $f (测试文件，大 PR 裁剪：仅签名)"
                echo '```'
                echo "$content" | grep -E 'class |interface |enum |public |private |protected |fun |def |@Test|@BeforeEach|@AfterEach|@Before|@After|@ParameterizedTest|import |package ' || echo '// (无签名行)'
                echo '```'
                echo
                SLIM_SKIP=$((SLIM_SKIP + 1))
              elif [ "$SKIP_FILE" -eq 2 ]; then
                # 配置文件：properties/yaml 去注释去空行，xml 保留结构标签但去纯文本噪音
                echo "## File: $f (配置文件，大 PR 裁剪：仅 key)"
                echo '```'
                case "$f" in
                  *.xml)
                    # XML: 保留标签结构，去掉纯空行，截断 50 行
                    echo "$content" | grep -vE '^\s*$' | head -50 ;;
                  *.properties|*.yaml|*.yml)
                    # properties/yaml: 去注释去空行，截断 50 行
                    echo "$content" | grep -vE '^\s*$|^\s*#' | head -50 ;;
                  *)
                    echo "$content" | head -50 ;;
                esac || echo '// (空配置)'
                echo '```'
                echo
                SLIM_SKIP=$((SLIM_SKIP + 1))
              elif [ "$SKIP_FILE" -eq 3 ]; then
                # 纯删除文件：不输出源码
                echo "## File: $f (纯删除文件，大 PR 裁剪：已删除)"
                echo
                SLIM_SKIP=$((SLIM_SKIP + 1))
              fi
            fi
            ;;
        esac
      done < /tmp/local_cr_files.txt
    } > "$SOURCE_CTX"
    if [ "$BIG_PR" -eq 1 ] && [ "$SLIM_SKIP" -gt 0 ]; then
      log "📦 source_context: ${SOURCE_COUNT} 个完整 + ${SLIM_SKIP} 个裁剪(测试/配置/删除) → ${SOURCE_CTX}（diff>${DIFF_LINES} 行触发大 PR 裁剪）"
    else
      log "📦 source_context: ${SOURCE_COUNT} 个变更文件完整源码 → $SOURCE_CTX"
    fi
  fi
  emit source_context_files "$SOURCE_COUNT"


  # ── 1B ONES 上下文（分道路：显式数字ID→workitem-detail 建联；项目内键→旧链路仅上下文）──
  # 项目内键（FEVUO/ONES-xxx）尾号为项目内序号，非全局 ID，不用于建联
  # 建联信息落 /tmp/cr_ones_db_info.json（仅显式数字传参才产出）
  rm -f /tmp/cr_ones_db_info.json /tmp/cr_ones_detail.json 2>/dev/null
  ST_ONES=skipped; ONES_EVER=""

  # 道路1：显式数字全局 ID（--ones 传入）
  ONES_EXPLICIT="${ONES_ID:-}"
  if [ -n "$ONES_EXPLICIT" ] && [[ "$ONES_EXPLICIT" =~ ^[0-9]+$ ]]; then
    if command -v ones >/dev/null 2>&1; then
      if run_to 10 ones workitem-detail -i "$ONES_EXPLICIT" --json > /tmp/cr_ones_detail.json 2>/tmp/cr_ones_err.log; then
        python3 - "$ONES_EXPLICIT" <<'PYE' 2>/dev/null
import json, sys
try:
    d = json.load(open('/tmp/cr_ones_detail.json'))
    wid = d.get('workItem', d) if isinstance(d, dict) else {}
    name = (((wid.get("name") or {}).get("value")) or "").strip()
    wtype = str(wid.get("type") or "").strip()
    db_id = ""
    raw = wid.get("id")
    if isinstance(raw, dict):
        raw = ((raw.get("value") or "")).strip()
    else:
        raw = str(raw or "").strip()
    if raw.isdigit():
        db_id = raw
    if not db_id and sys.argv[1].isdigit():
        db_id = sys.argv[1]
    if db_id and name:
        json.dump({"onesId": db_id, "onesType": wtype, "onesName": name},
                  open('/tmp/cr_ones_db_info.json', 'w'), ensure_ascii=False)
except Exception:
    pass
PYE
        ST_ONES=ok; ONES_EVER="$ONES_EXPLICIT"
        # 审查上下文复用（尽力而为，失败不影响状态）
        python3 - <<'PYE' 2>/dev/null
import json
try:
    d = json.load(open('/tmp/cr_ones_detail.json'))
    wid = d.get('workItem', d) if isinstance(d, dict) else {}
    desc = wid.get("description")
    desc = (desc.get("value") or "") if isinstance(desc, dict) else str(desc or "")
    out = {"title": ((wid.get("name") or {}).get("value") or ""),
           "type": wid.get("type") or "",
           "description": desc}
    json.dump(out, open('/tmp/cr_ones_context.json', 'w'), ensure_ascii=False)
except Exception:
    pass
PYE
      else
        ST_ONES=failed; log "⚠️ ONES workitem-detail 拉取失败，建联跳过（4-D 降级双源）"
      fi
    else
      ST_ONES="no-cli"; log "⚠️ ones CLI 不可用，建联跳过"
    fi
  elif [ -n "$ONES_EXPLICIT" ]; then
    ST_ONES=skipped; log "⚠️ --ones 非纯数字全局 ID，不建联，仅作上下文参考"
  fi

  # 道路2：分支名提取项目内键 → 旧链路仅作审查上下文，不建联
  if [ -z "$ONES_EVER" ]; then
    ONES_EVER=$(echo "$BRANCH" | grep -oE '(FEVUO|ONES)-[0-9]+' | head -1)
    if [ -n "$ONES_EVER" ] && command -v ee-ones >/dev/null 2>&1; then
      if run_to 10 ee-ones issue info "$ONES_EVER" > /tmp/cr_ones_context.json 2>/tmp/cr_ones_err.log; then
        ST_ONES=ok
      else
        ST_ONES=failed; log "⚠️ ONES 拉取失败（无权限/超时），4-D 降级双源"
      fi
    elif [ -n "$ONES_EVER" ]; then
      ST_ONES="no-cli"
    fi
  fi
  emit ones_id "${ONES_EVER:-}"; emit ones_status "$ST_ONES"
  # 建联信息存在性标记（仅显式数字传参才产出，供 publish 判断）
  if [ -s /tmp/cr_ones_db_info.json ]; then
    emit ones_db_info "ready"
  else
    emit ones_db_info "absent"
  fi

  # ── 1D 业务上下文合成（Layer 3 落盘，供 4-A-P0 / 4-D 消费）──
  # /tmp/cr_business_context.md = 领域知识库 + ONES 语义 + 白盒测试点（各源如有则拼）
  # 此前该文件"如有先读"但从未有人生成——空挂。现在 prep 固化产出。
  ST_BC=ok
  {
    echo "# 业务上下文（Layer 3 合成，prep 自动生成）"
    echo
    # 源1：领域知识库（cr-config.yaml domain_knowledge 路径）
    DK_PATH=$(python3 -c "
import yaml
try:
    c = yaml.safe_load(open('$SKILL_ROOT/cr-config.yaml'))
    p = c.get('domain_knowledge','') or ''
    print(p if p else 'references/domain-knowledge.md')
except Exception: print('references/domain-knowledge.md')" 2>/dev/null || echo "references/domain-knowledge.md")
    case "$DK_PATH" in /*) ;; *) DK_PATH="$SKILL_ROOT/$DK_PATH" ;; esac
    if [ -f "$DK_PATH" ]; then
      echo "## 领域知识库（团队 ID 体系 / 双平台规范 / CR 触发映射）"
      cat "$DK_PATH"
      echo
    fi
    # 源2：ONES 需求语义
    if [ -s /tmp/cr_ones_context.json ]; then
      echo "## ONES 需求语义"
      python3 -c "
import json
try:
    d = json.load(open('/tmp/cr_ones_context.json'))
    if isinstance(d, dict):
        for k in ('title','description','requirement','acceptance'):
            v = d.get(k)
            if v: print(f'### {k}\n{v}\n')
    else:
        print(str(d)[:3000])
except Exception as e:
    print(f'(ONES 上下文解析失败: {e})')" 2>/dev/null
    fi
    # 源3：白盒测试点（SPECS_DIR 环境变量）
    if [ -n "${SPECS_DIR:-}" ] && [ -f "$SPECS_DIR/testpoints.json" ]; then
      echo "## Whitebox 测试点（代码必须实现所有功能点）"
      cat "$SPECS_DIR/testpoints.json"
      echo
    fi
  } > /tmp/cr_business_context.md 2>/dev/null || ST_BC=failed
  if [ -s /tmp/cr_business_context.md ] && [ "$(wc -l < /tmp/cr_business_context.md)" -gt 2 ]; then
    log "🧠 业务上下文已合成: $(wc -l < /tmp/cr_business_context.md) 行 → /tmp/cr_business_context.md"
  else
    rm -f /tmp/cr_business_context.md  # 只剩标题的空壳不留
  fi

  # ── 1C 操作者 MIS（触发用户 > git 校验 > config > unknown）──
  OM="${OPERATOR_MIS:-}"
  if [ -z "$OM" ]; then
    for _e in X_AI_USER_MIS X_AI_OPERATOR X_AI_USERNAME; do
      _v=$(printenv "$_e" 2>/dev/null | tr -d '[:space:]')
      if [ -n "$_v" ] && [ "$_v" != "root" ]; then OM="$_v"; break; fi
    done
  fi
  if [ -z "$OM" ]; then
    _g=$(git -C "$REPO_PATH" config user.email 2>/dev/null | cut -d@ -f1)
    case "$_g" in ""|root|test|unknown|temp|tmp|placeholder|admin|local) _g="" ;; esac
    OM="$_g"
  fi
  if [ -z "$OM" ] && [ -f "$SKILL_ROOT/cr-config.yaml" ]; then
    OM=$(python3 -c "
import yaml
try:
    c = yaml.safe_load(open('$SKILL_ROOT/cr-config.yaml'))
    print(c.get('operator_mis','') or '')
except Exception: print('')" 2>/dev/null || echo "")
  fi
  OM="${OM:-unknown}"
  export OPERATOR_MIS="$OM"
  emit operator_mis "$OM"; emit repo "$REPO_NAME"; emit repo_path "$REPO_PATH"; emit branch "$BRANCH"; emit base "$BASE"

  # ── MIS→学城目录路由（V115：恢复旧版 agent 的 qing 接口路由）──
  CITADEL_PARENT_ID=""
  # 优先级：手动指定 > qing 接口 > citadel_parent_by_mis 映射 > 默认
  if [ -f "$SKILL_ROOT/scripts/get_org_info.py" ]; then
    _ORG_JSON=$(python3 "$SKILL_ROOT/scripts/get_org_info.py" "$OM" 2>/dev/null || echo '{}')
    _API_CPID=$(echo "$_ORG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('citadelParentId',''))" 2>/dev/null || echo "")
    if [ -n "$_API_CPID" ]; then
      CITADEL_PARENT_ID="$_API_CPID"
      log "📋 学城目录（qing 接口）：$_API_CPID"
    fi
  fi
  # qing 接口未命中 → 尝试 citadel_parent_by_mis 本地映射
  if [ -z "$CITADEL_PARENT_ID" ] && [ -f "$SKILL_ROOT/cr-config.yaml" ]; then
    _LOCAL_CPID=$(python3 -c "
import yaml
try:
    c = yaml.safe_load(open('$SKILL_ROOT/cr-config.yaml'))
    by_mis = c.get('citadel_parent_by_mis', {}) or {}
    print(by_mis.get('$OM', ''))
except Exception: print('')
" 2>/dev/null || echo "")
    if [ -n "$_LOCAL_CPID" ]; then
      CITADEL_PARENT_ID="$_LOCAL_CPID"
      log "📋 学城目录（本地映射）：$_LOCAL_CPID"
    fi
  fi
  # 最终兜底：cr-config.yaml 默认 citadel_parent_id
  if [ -z "$CITADEL_PARENT_ID" ] && [ -f "$SKILL_ROOT/cr-config.yaml" ]; then
    _DEF_CPID=$(grep -oE 'citadel_parent_id:[[:space:]]*"?[0-9]+' "$SKILL_ROOT/cr-config.yaml" 2>/dev/null | grep -oE '[0-9]+' | head -1)
    [ -n "$_DEF_CPID" ] && CITADEL_PARENT_ID="$_DEF_CPID"
  fi
  emit citadel_parent_id "$CITADEL_PARENT_ID"
  # 同步推群 group id（qing 接口返回 chatGroupId）
  _API_CHAT_GROUP=$(echo "$_ORG_JSON" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('chatGroupId',''))" 2>/dev/null || echo "")
  emit chat_group_id "${_API_CHAT_GROUP:-}"

  # ── 2B-2 等建图 + symbol 提取 + 全量并行反查 ──
  ST_L2=ok
  if [ -f /tmp/cr_gitnexus_build.pid ]; then
    BP=$(cat /tmp/cr_gitnexus_build.pid 2>/dev/null)
    if [ -n "$BP" ] && kill -0 "$BP" 2>/dev/null; then
      log "⏳ 等 GitNexus 建图（90s 兜底）..."
      run_to 90 tail --pid="$BP" -f /dev/null 2>/dev/null || true
    fi
    rm -f /tmp/cr_gitnexus_build.pid
  fi
  mkdir -p /tmp/cr_layer2_results
  python3 - "$SKILL_ROOT" "$REPO_PATH" > /tmp/cr_l2_extract.log 2>&1 << 'PYEOF' || ST_L2=degraded
import json, re, subprocess, sys, os
skill, repo = sys.argv[1], sys.argv[2]
diff = open('/tmp/local_cr_diff.txt', encoding='utf-8', errors='replace').read()
syms = set()
for m in re.finditer(r'^@@.*?\+(?:\d+)(?:,\d+)? @@\s*(?:\w[\w\s<>\[\],]*?)?(\w+)\s*\(', diff, re.M):
    syms.add(m.group(1))
for m in re.finditer(r'^\+\s*(?:public|private|protected|static).*?(\w+)\s*\(', diff, re.M):
    syms.add(m.group(1))
for m in re.finditer(r'^\+\s*(?:private|public|protected)\s+(?:static\s+)?(?:final\s+)?[\w<>\[\],.]+\s+(\w+)\s*[;=]', diff, re.M):
    syms.add(m.group(1))
syms = {s for s in syms if len(s) > 2 and s[0].isupper() or (len(s) > 3 and s not in ('return','String','Integer','Boolean','Object','Override','Test','throws','throw','value','name','type'))}
json.dump(sorted(syms), open('/tmp/cr_changed_symbols.json', 'w'))
src = os.path.join(repo, 'src/main/java')
gn = subprocess.run(['gitnexus', 'status'], capture_output=True, text=True).stdout if os.path.isdir(os.path.expanduser('~/.gitnexus')) else ''
use_gn = 'indexed' in gn
import concurrent.futures as cf
def rev(s):
    if use_gn:
        r = subprocess.run(['gitnexus', 'impact', s, '-d', 'upstream', '--depth', '2'], capture_output=True, text=True)
        open(f'/tmp/cr_layer2_results/{s}.impact', 'w').write(r.stdout)
    else:
        subprocess.run(f'grep -rn "{s}" "{src}" --include="*.java" | grep -vE "^.*:\\d+:import " | head -50 > "/tmp/cr_layer2_results/{s}.grep" 2>/dev/null', shell=True)
with cf.ThreadPoolExecutor(8) as ex:
    list(ex.map(rev, sorted(syms)))
print(f'L2 done: {len(syms)} symbols, gitnexus={use_gn}')
PYEOF
  emit layer2_status "$ST_L2"

  # ── Layer2 可用性契约（V115）──
  L2_META=$(python3 - << 'L2PY'
import json
from pathlib import Path
symbols_path = Path("/tmp/cr_changed_symbols.json")
result_dir = Path("/tmp/cr_layer2_results")
try:
    symbols = json.loads(symbols_path.read_text()) if symbols_path.exists() else []
    if not isinstance(symbols, list):
        raise ValueError("symbols-not-list")
except Exception:
    symbols = None
files = sorted(str(p) for p in result_dir.glob("*") if p.is_file() and p.stat().st_size > 0)
if symbols is None:
    status, available, reason = "unavailable", False, "symbol-extraction-failed"
elif not symbols:
    status, available, reason = "empty", False, "no-symbol-extracted"
elif files:
    status, available, reason = "ok", True, ""
else:
    status, available, reason = "degraded", False, "no-readable-result-files"
print(json.dumps({
    "layer2_status": status, "layer2_available": available,
    "layer2_symbols": symbols or [], "result_dir": str(result_dir),
    "result_files": files, "layer2_reason": reason,
}, ensure_ascii=False))
L2PY
)
  emit_json layer2_meta "$L2_META"

  # ── 2B-3 反查产物追加到 source_context（子 Agent 公共上下文增强）──
  if [ -d /tmp/cr_layer2_results ] && [ -s /tmp/local_cr_files.txt ]; then
    L2_COUNT=$(find /tmp/cr_layer2_results -name '*.grep' -size +0c 2>/dev/null | wc -l)
    if [ "$L2_COUNT" -gt 0 ]; then
      # 如果 1A3 未生成 source_context（空变更列表），先创建头
      [ ! -f "$SOURCE_CTX" ] && { echo "# 子 Agent 公共上下文"; echo; } > "$SOURCE_CTX"
      {
        echo ""
        echo "---"
        echo ""
        echo "# Layer2 反查结果（变更 symbol 的全仓库引用）"
        echo
        for gf in /tmp/cr_layer2_results/*.grep; do
          [ ! -s "$gf" ] && continue
          sym=$(basename "$gf" .grep)
          echo "## Symbol: $sym"
          echo '```'
          cat "$gf"
          echo '```'
          echo
        done
      } >> "$SOURCE_CTX"
      log "📦 source_context: 追加 ${L2_COUNT} 个 symbol 反查结果"
    fi
  fi

  # ── 2C mapper wiring 探查（diff 含 sqlmap/mybatis xml 变更时预跑，7 条 grep 链）──
  ST_PROBE=skipped
  if grep -qE 'sqlmap|mapper.*\.xml|\.xml.*mapper' /tmp/local_cr_files.txt 2>/dev/null; then
    ST_PROBE=ok
    {
      echo "# Mapper wiring probe（prep 预跑，4-A-P0 直接消费）"
      cd "$REPO_PATH" 2>/dev/null || exit 1
      XMLS=$(grep -E 'sqlmap|mapper.*\.xml' /tmp/local_cr_files.txt | head -5)
      echo "## 变更的 mapper xml: $XMLS"
      for x in $XMLS; do
        echo "### $x"
        # xml 里 resultMap id / insert|select|update|delete id 清单
        python3 - "$x" << 'PROBE_PY'
import re, sys
try:
    src = open(sys.argv[1], encoding='utf-8', errors='replace').read()
    for m in re.finditer(r'(resultMap|insert|select|update|delete)\s+id="(\w+)"', src):
        print(f'{m.group(1)} id={m.group(2)}')
except Exception as e:
    print(f'probe-error: {e}')
PROBE_PY
      done
      echo "## MapperScan/扫描配置"
      grep -rn "MapperScan" --include="*.java" src/main/java 2>/dev/null | head -5
      echo "## sqlmap 加载配置"
      grep -rn "mapperLocations\|sqlmap" src/main/resources/spring/*.xml src/main/resources/META-INF/*.properties 2>/dev/null | head -8
      echo "## datasource/zebra"
      grep -rn -iE "zebra|datasource" src/main/resources/spring/*.xml 2>/dev/null | head -5
    } > /tmp/cr_probe_mapper.txt 2>&1 || ST_PROBE=degraded
    log "📌 mapper wiring 探查 → /tmp/cr_probe_mapper.txt"
  fi
  emit mapper_probe "$ST_PROBE"

  # ── 3A SDD 检测 ──
  SDD=false
  if [ -d "$REPO_PATH/specs" ] && ls "$REPO_PATH/specs/"*.md >/dev/null 2>&1; then SDD=true; fi
  emit sdd_available "$SDD"

  # ── 3A2 自定义规则探测+预合并（.mdp/rules + .catpaw/rules → 4-C 消费）──
  # 此前 .mdp/rules 的读取完全靠主 Agent 自觉（SKILL.md 文字），prep 管道零探测——
  # 固化流程：探测+脚本预筛+合并落盘。
  CR_CUSTOM_OUT="/tmp/cr_custom_rules_${REPO_NAME}.md"
  CU_COUNT=0
  {
    for RD in "$REPO_PATH/.mdp/rules/team" "$REPO_PATH/.mdp/rules/project" "$REPO_PATH/.catpaw/rules"; do
      [ -d "$RD" ] || continue
      for F in "$RD"/*.md; do
        [ -f "$F" ] || continue
        # 脚本级预筛：标题+前10行含工作流/规范于人关键词 → 跳过（保守：仅明确非代码规则才剔）
        if head -11 "$F" | grep -qiE 'specify|工作流|workflow|AI 协作|ai-collaboration|协作流程|需求管理|提交流程|branch|分支规范|git flow'; then
          continue
        fi
        echo "## $(basename "$F")"
        cat "$F"
        echo
        CU_COUNT=$((CU_COUNT+1))
      done
    done
  } > "$CR_CUSTOM_OUT" 2>/dev/null || true
  if [ "$CU_COUNT" -eq 0 ]; then
    rm -f "$CR_CUSTOM_OUT"
    emit custom_rules "none"
  else
    emit custom_rules "$CU_COUNT"   # 预筛后保留的规则文件数
  fi

  # ── 3A3 平台L2团队规则拉取（防腐层：fetch_l2_rules.sh，never-block）──
  # 依赖：mt-code-standards-setup skill（可选，缺失自动降级+日志指引）
  # 不变量：本段任何失败 → CR 结果与无 L2 能力时完全一致（仅一行日志）
  # 灰度开关：CR_L2_DISABLE=1 跳过（灰度期一键回退）
  CR_L2_OUT="/tmp/cr_l2_rules_${REPO_NAME}.md"
  # 先清旧产物再拉取: 防止上次成功/本次失败的跨 run 残留(陈旧规则注入 4-C)
  rm -f "$CR_L2_OUT" 2>/dev/null
  if [ "${CR_L2_DISABLE:-0}" = "1" ]; then
    log "3A3: CR_L2_DISABLE=1，跳过平台L2拉取"
    emit l2_rules "none(disabled)"
  else
    L2_BUNDLE="/tmp/cr_l2_bundle_$(echo "$REPO_FULL" | tr '/' '_')"  # 从 --repo 单点推导,对齐 agent 命名
    # 无 remote 仓库(如本地新建/沙箱测试仓库)无 org/repo 定位信息,
    # 平台侧无法定位规则集,直接显式归因跳过(比传非法格式等 fetch 报 arg-error 更直接)
    case "$REPO_FULL" in
      */*) : ;;
      *) log "3A3: 仓库无 remote($REPO_FULL),无法定位平台规则集,跳过L2拉取"
         emit l2_rules "none(no-remote)"
         L2_RC=9 ;;
    esac
    if [ "${L2_RC:-0}" != "9" ]; then
    bash "$SKILL_ROOT/scripts/fetch_l2_rules.sh" \
      --repo "$REPO_FULL" \
      --timeout 50 > "/tmp/cr_l2_extract_${REPO_NAME}.log" 2>&1
    L2_RC=$?
    fi
    L2_COUNT=0
    if [ $L2_RC -eq 0 ] && [ -d "$L2_BUNDLE/team" ]; then
      {
        for D in "$L2_BUNDLE"/team/*/; do
          [ -d "$D" ] || continue
          SET_ID=$(basename "$D")
          for F in "$D"*.md; do
            [ -f "$F" ] || continue
            echo "## ${SET_ID}/$(basename "$F")"
            cat "$F"
            echo
            L2_COUNT=$((L2_COUNT+1))
          done
        done
      } > "$CR_L2_OUT" 2>/dev/null || true
      [ "$L2_COUNT" -eq 0 ] && rm -f "$CR_L2_OUT"
    fi
    case "$L2_RC" in
      0) emit l2_rules "$L2_COUNT" ;;
      3) emit l2_rules "none(skill-missing)" ;;
      4|5) emit l2_rules "none(fetch-failed)" ;;
      6) emit l2_rules "none(no-team-rules)" ;;
      9) : ;;  # no-remote 已在拉取前 emit,不重复
      2) emit l2_rules "none(arg-error)" ;;
      *) emit l2_rules "none(fetch-failed)" ;;  # 127(脚本缺失)等未定义码统一归 fetch-failed,保证摘要字段必存在
    esac
    # 去重防御：本地 .mdp/rules/team 子目录规则集ID与平台重合 → 标记，4-C 输入提示平台为准
    # （本地子目录规则集本就不进 CU——3A2 仅收顶层 md，标记为信息性归因，不产生双重消费）
    # 注意: emit 是覆写语义,多规则集重复必须累积后一次性 emit_json,否则只剩最后一个
    if [ -d "$REPO_PATH/.mdp/rules/team" ] && [ -f "$L2_BUNDLE/manifest.json" ]; then
      L2_DUP_SETS=""
      for D in "$REPO_PATH/.mdp/rules/team"/*/; do
        [ -d "$D" ] || continue
        SET_ID=$(basename "$D")
        if [ -d "$L2_BUNDLE/team/$SET_ID" ]; then
          log "⚠️ 本地规则集 $SET_ID 与平台重复，4-C 以平台为准"
          L2_DUP_SETS="$L2_DUP_SETS$SET_ID "
        fi
      done
      if [ -n "$L2_DUP_SETS" ]; then
        emit_json l2_dup "$(python3 -c "import json,sys; print(json.dumps(sys.argv[1].split()))" "${L2_DUP_SETS% }")"
      fi
    fi
    rm -rf "$L2_BUNDLE" 2>/dev/null || true
  fi

  # ── 3A3 4-D 合并输入文件生成（在业务上下文 + 自定义规则均就绪后生成）──
  INPUT_CODE_READY=false
  INPUT_CORE_READY=false
  if [ -s "$SOURCE_CTX" ] && [ -s /tmp/local_cr_diff_slim.txt ]; then
    {
      cat "$SOURCE_CTX"
      echo ''
      echo '---'
      echo ''
      echo '# 变更 Diff（slim 版）'
      echo '```diff'
      cat /tmp/local_cr_diff_slim.txt
      echo '```'
    } > /tmp/cr_4d_input_code.md 2>/dev/null
    [ -s /tmp/cr_4d_input_code.md ] && INPUT_CODE_READY=true
    log "📦 4-D 输入文件 code 已生成 → /tmp/cr_4d_input_code.md"
  fi
  emit input_code_ready "$INPUT_CODE_READY"

  if [ -s /tmp/cr_business_context.md ]; then
    {
      echo '# 4-D 核心上下文（业务上下文 + 疑点清单 + SDD alignment）'
      echo ''
      # 业务上下文段
      if [ -s /tmp/cr_business_context.md ]; then
        echo '## 业务上下文'
        cat /tmp/cr_business_context.md
        echo ''
      fi
      # V117: 自定义规则已迁出至 4-C 输入(/tmp/cr_custom_rules_{repo}.md 随 task 注入 4-C),
      # 不再嵌入 4-D core,避免 CU 双路重复消费
      # 疑点清单占位符（主 Agent spawn 4-D 前填充）
      echo '<!-- SUSPECTS_PLACEHOLDER -->'
      # SDD alignment 占位符（主 Agent spawn 4-D 前填充）
      echo '<!-- SDD_ALIGN_PLACEHOLDER -->'
    } > /tmp/cr_4d_input_core.md 2>/dev/null
    [ -s /tmp/cr_4d_input_core.md ] && INPUT_CORE_READY=true
    log "📦 4-D 输入文件 core 已生成 → /tmp/cr_4d_input_core.md"
  fi
  emit input_core_ready "$INPUT_CORE_READY"

  # ── 3B 信号检测（python 扫描 diff，路由表静态映射内置）──
  ST_SIG=ok
  python3 - "$REPO_NAME" > /tmp/cr_signals_run.log 2>&1 << 'PYEOF' || ST_SIG=failed
import json, re, sys
repo = sys.argv[1]
diff = open('/tmp/local_cr_diff.txt', encoding='utf-8', errors='replace').read()
TABLE = {
 'SIG-CONCURRENCY': (r'Thread|Runnable|Executor|ThreadPool|synchronized|Lock\b|volatile|CompletableFuture|parallelStream|ForkJoinPool', 'subagent-java,subagent-ha'),
 'SIG-EXCEPTION': (r'\btry\b|\bcatch\b|\bfinally\b|\bthrow\b|Exception|\bthrows\b', 'subagent-java,subagent-ha'),
 'SIG-SQL': (r'@Transactional|Mapper|MyBatis|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bsql\b|JdbcTemplate', 'subagent-db-dep,subagent-ha'),
 'SIG-DDL': (r'CREATE TABLE|ALTER TABLE|ADD COLUMN|DROP COLUMN|\bMODIFY\b', 'subagent-db-dep'),
 'SIG-CACHE': (r'Redis|CacheManager|@Cacheable|Jedis|Lettuce|RedisTemplate', 'subagent-ha'),
 'SIG-MQ': (r'Mafka|Consumer|Producer|@KafkaListener|MessageListener|SendResult', 'subagent-ha'),
 'SIG-RPC': (r'OCTO|MTthrift|HttpClient|RestTemplate|@RequestMapping|WebClient|Feign', 'subagent-ha'),
 'SIG-LOG': (r'log\.|Logger|Log4j|scribeAppender|XMDFileAppender|@Slf4j|AsyncScribe|Metric|Raptor|Cat\.|\bTransaction\b', 'subagent-java,subagent-ha'),
 'SIG-SECURITY': (r'@PreAuthorize|@RequiresPermission|Token|Password|encrypt|decrypt|SSRF|\bXSS\b|CSRF', 'subagent-sec,subagent-ha'),
 'SIG-CONFIG': (r'Lion|@Value|@ConfigurationProperties|\.yml|\.properties|Switch\b|FeatureToggle', 'subagent-ha'),
 'SIG-INTERFACE': (r'@RequestMapping|@GetMapping|@PostMapping|\binterface\b|\bDTO\b|\bVO\b|\bRequest\b|\bResponse\b', 'subagent-java,subagent-ha'),
 'SIG-DEPENDENCY': (r'<dependency>|pom\.xml|<groupId>|<artifactId>|<version>', 'subagent-db-dep'),
 'SIG-ES': (r'\bEagle\b|Elasticsearch|RestHighLevelClient|SearchRequest|BulkRequest', 'subagent-ha'),
 'SIG-HBASE': (r'HBase|HTable|\bScan\b|\bPut\b|\bGet\b|BufferedMutator', 'subagent-ha'),
 'SIG-TEST': (r'@Test|@Mock|@MockBean|\bAssert\b|Mockito', 'subagent-java'),
 'SIG-NPE': (r'\.get\(\)|\.get\w+\(\)|Optional\b|\bnull\b|NullPointerException', 'subagent-java,subagent-ha'),
 'SIG-RESOURCE': (r'InputStream|OutputStream|\bConnection\b|\bReader\b|\bWriter\b|BufferedReader', 'subagent-ha'),
 'SIG-IDEMPOTENCY': (r'RECONSUME_LATER|幂等|idempotent|@Idempotent', 'subagent-ha'),
 'SIG-COMPATIBILITY': (r'@Deprecated|serialVersionUID|FAIL_ON_UNKNOWN_PROPERTIES|\boptional\b|\breserved\b', 'subagent-ha'),
 'SIG-COLLECTION': (r'\bList\b|\bMap\b|\bSet\b|\bCollection\b|\bIterator\b|\bHashMap\b|\bConcurrentHashMap\b|\bArrayList\b|\bLinkedList\b', 'subagent-java'),
 'SIG-OOP': (r'\bclass\b|\binterface\b|\bextends\b|\bimplements\b|\babstract\b|@Override', 'subagent-java'),
 'SIG-CONSTANT': (r'static\s+final|\benum\b|\bEnum\b|\bConstants\b', 'subagent-java'),
}
RULEMAP = {'subagent-java': ['JAVA-01','JAVA-02','JAVA-03','JAVA-04','JAVA-05','JAVA-06','JAVA-07','JAVA-08'],
           'subagent-db-dep': ['DB-01','DB-02','DB-03','DB-04','DEP-01'],
           'subagent-ha': ['HA-01','HA-02','HA-03','HA-04','HA-05','HA-06','HA-07','HA-09','HA-10','HA-11','HA-12','HA-13','HA-14'],
           'subagent-sec': ['SEC-A','SEC-B','SEC-C']}
# 信号→文件映射（用于 4-B 按信号精确加载）
SIG_TO_FILES = {
 'SIG-CONCURRENCY': {'subagent-java': ['JAVA-04'], 'subagent-ha': ['HA-07']},
 'SIG-EXCEPTION': {'subagent-java': ['JAVA-05'], 'subagent-ha': ['HA-03']},
 'SIG-SQL': {'subagent-db-dep': ['DB-01','DB-02','DB-04'], 'subagent-ha': ['HA-04']},
 'SIG-DDL': {'subagent-db-dep': ['DB-03']},
 'SIG-CACHE': {'subagent-ha': ['HA-05']},
 'SIG-MQ': {'subagent-ha': ['HA-06']},
 'SIG-RPC': {'subagent-ha': ['HA-01','HA-10']},
 'SIG-LOG': {'subagent-java': ['JAVA-06'], 'subagent-ha': ['HA-02']},
 'SIG-SECURITY': {'subagent-sec': ['SEC-A','SEC-B','SEC-C'], 'subagent-ha': ['HA-12']},
 'SIG-CONFIG': {'subagent-ha': ['HA-11']},
 'SIG-INTERFACE': {'subagent-java': ['JAVA-08'], 'subagent-ha': ['HA-10']},
 'SIG-DEPENDENCY': {'subagent-db-dep': ['DEP-01']},
 'SIG-ES': {'subagent-ha': ['HA-13']},
 'SIG-HBASE': {'subagent-ha': ['HA-14']},
 'SIG-TEST': {'subagent-java': ['JAVA-07']},
 'SIG-NPE': {'subagent-java': ['JAVA-05'], 'subagent-ha': ['HA-03']},
 'SIG-RESOURCE': {'subagent-ha': ['HA-03']},
 'SIG-IDEMPOTENCY': {'subagent-ha': ['HA-09','HA-06']},
 'SIG-COMPATIBILITY': {'subagent-ha': ['HA-10']},
 'SIG-COLLECTION': {'subagent-java': ['JAVA-03']},
 'SIG-OOP': {'subagent-java': ['JAVA-02']},
 'SIG-CONSTANT': {'subagent-java': ['JAVA-01']},
}
hits, agents = [], set()
agent_files = {}  # per-agent rule_files (deduplicated, signal-driven)
for sig, (pat, ags) in TABLE.items():
    if re.search(pat, diff):
        hits.append(sig)
        for a in ags.split(','):
            agents.add(a)
            # 从 SIG_TO_FILES 获取该信号对应的文件
            for agent, files in SIG_TO_FILES.get(sig, {}).items():
                if agent not in agent_files:
                    agent_files[agent] = []
                for f in files:
                    if f not in agent_files[agent]:
                        agent_files[agent].append(f)
# 兜底：如果没命中任何信号，全部 agent 按全量加载
if not hits:
    for a, files in RULEMAP.items():
        agent_files[a] = files
    agents = set(RULEMAP.keys())
with open(f'/tmp/cr_signals_{repo}.md', 'w') as f:
    f.write('# 活跃信号\n\n' + '\n'.join(f'- {h}' for h in hits) + f'\n\n**需启动子 Agent**: {", ".join(sorted(agents))}\n')
json.dump({'active_signals': hits, 'agents': sorted(agents), 'agent_files': agent_files}, open('/tmp/cr_signal_rules.json', 'w'), ensure_ascii=False, indent=1)
print(f'signals: {len(hits)}, agents: {len(agents)}, files: {sum(len(v) for v in agent_files.values())}')
PYEOF
  emit signals_status "$ST_SIG"

  # ── 3C 路由计划（信号驱动 + diff 规模 → spawn 计划）──
  ST_ROUTE=ok
  if python3 "$SKILL_ROOT/scripts/route_plan.py" --repo "$REPO_PATH" --name "$REPO_NAME" > /tmp/cr_route_plan.log 2>&1; then
    # Bug 4 修复：字段访问改用 .get() 容错
    TIER=$(python3 -c "import json; d=json.load(open('/tmp/cr_route_plan.json')); print(d.get('tier','unknown'))" 2>/dev/null || echo unknown)
    TOTAL=$(python3 -c "import json; d=json.load(open('/tmp/cr_route_plan.json')); print(d.get('total_subagents',0))" 2>/dev/null || echo 0)
    log "📋 路由计划: tier=$TOTAL $TIER 路（详见 /tmp/cr_route_plan.json）"
  else
    ST_ROUTE=failed
    log "⚠️ 路由计划生成失败，回退固定路由（见 /tmp/cr_route_plan.log）"
  fi
  emit route_status "$ST_ROUTE"

  emit prep_done true
  log "✅ prep 完成 → $SUMMARY"
  cat "$SUMMARY"
  ;;

merge-review)
  # ═══════════ Step 4 后段编排：merge + 复审触发 + 预处理（一条命令替代 3 条，省 2 次主 Agent 审批）═══════════
  if [ -z "$REPO_PATH" ] || [ ! -d "$REPO_PATH" ]; then
    log "❌ --repo 必填（本地仓库路径）"; exit 1
  fi
  # REPO_NAME 与 prep 同源：prep 摘要 repo 字段 > resolve_repo_name(平台名) > basename 兜底
  # 注: 直接 basename(toplevel) 会与 prep 产物名失配(clone 改名场景: prep 用平台名,产物
  # 文件名以平台名为准),优先从 prep 摘要与 remote 推导,与 prep 命名链一致
  _TOP_DIR=$(git -C "$REPO_PATH" rev-parse --show-toplevel 2>/dev/null || echo "")
  _PREP_JSON="/tmp/cr_prep_$(basename "${_TOP_DIR:-$REPO_PATH}").json"
  _PREP_REPO=$(python3 -c "import json; print(json.load(open(\"$_PREP_JSON\")).get(\"repo\",\"\"))" 2>/dev/null || echo "")
  REPO_NAME="${REPO_NAME:-${_PREP_REPO:-$(resolve_repo_name "$REPO_PATH")}}"
  [ -z "$REPO_NAME" ] && REPO_NAME=$(basename "${_TOP_DIR:-$REPO_PATH}" 2>/dev/null || echo unknown)
  REPO_FULL="${REPO_FULL:-$(resolve_repo_name "$REPO_PATH")}"
  # 1) 合并去重
  python3 "$SKILL_ROOT/scripts/merge_issues.py" --repo "$REPO_NAME" || exit 1
  # 2) P0/P1 计数 → 复审触发判定 + 预处理 + spawn 指令（<3 自动 skipped）
  bash "$SKILL_ROOT/scripts/cr-review.sh" --repo "$REPO_NAME" --repo-path "$REPO_PATH" --skill-root "$SKILL_ROOT"
  ;;

publish)
  # ═══════════ Step 5 编排 ═══════════
  REPO_FULL="${REPO_FULL:-$(resolve_repo_name "$REPO_PATH")}"
  # 兼容修复：文件名变量取 repo 短名（不带斜杠），与 prep 分支保持一致；
  # REPO_FULL（org/repo）仅用于 --repo 参数，不能直接拼 /tmp 文件路径（父目录不存在会报错）
  REPO_NAME="${REPO_NAME:-${REPO_FULL##*/}}"
  [ -z "$REPO_NAME" ] && REPO_NAME=$(basename "$REPO_PATH" 2>/dev/null || echo unknown)
  if [ -z "$ISSUES_FILE" ] || [ ! -f "$ISSUES_FILE" ]; then
    log "❌ --issues-file 必填（Step 4 合并产物）"; exit 1
  fi
  ARGS=(--repo "${REPO_FULL:-$REPO_NAME}" --branch "${BRANCH:-}" --issues-file "$ISSUES_FILE")
  [ -n "$OPERATOR_MIS" ] && ARGS+=(--operator-mis "$OPERATOR_MIS")
  # ONES 建联（prep 已落 /tmp/cr_ones_db_info.json 时 cr_record 可自动补齐；
  # 此处透传兜底两再用：prep 未落 db_info（如 prep 缺 --ones）时显式传参仍能建联）
  [ -n "$ONES_ID" ] && ARGS+=(--ones-id "$ONES_ID")
  [ -n "$BASE" ] && ARGS+=(--base-branch "$BASE")
  [ -n "$OVERVIEW" ] && ARGS+=(--overview "$OVERVIEW")
  [ -n "$CONCLUSION" ] && ARGS+=(--conclusion-override "$CONCLUSION")
  # 学城父目录 ID（V115：优先从 prep 摘要读 MIS 路由结果，回落 cr-config.yaml）
  _PREP_SUMMARY="/tmp/cr_prep_${REPO_NAME}.json"
  CPID=""
  if [ -f "$_PREP_SUMMARY" ]; then
    CPID=$(python3 -c "import json; print(json.load(open('$_PREP_SUMMARY')).get('citadel_parent_id',''))" 2>/dev/null || echo "")
  fi
  if [ -z "$CPID" ] && [ -f "$SKILL_ROOT/cr-config.yaml" ]; then
    CPID=$(grep -oE 'citadel_parent_id:[[:space:]]*"?[0-9]+' "$SKILL_ROOT/cr-config.yaml" 2>/dev/null | grep -oE '[0-9]+' | head -1)
  fi
  [ -n "$CPID" ] && ARGS+=(--citadel-parent-id "$CPID")
  # 技术栈通过 -- --tech-stack 显式传入，不从 frontend_only 推导框架。
  # Bug 2 修复：bash 3.2 空数组 + set -u 防御
  if [ ${#EXTRA_ARGS[@]} -gt 0 ]; then
    for a in "${EXTRA_ARGS[@]}"; do [ -n "$a" ] && ARGS+=("$a"); done
  fi
  # 进度日志落文件，stdout 只出报告（防 tail 截断丢状态）
  python3 "$SKILL_ROOT/scripts/publish_results_local.py" "${ARGS[@]}" \
    > "/tmp/cr_publish_${REPO_NAME}.stdout" 2> "/tmp/cr_publish_${REPO_NAME}.log"
  RC=$?
  # 状态摘要（从 stdout 提取关键行 + 日志尾部）
  grep -E '学城文档|结论|SDLC JSON|DB 写入' "/tmp/cr_publish_${REPO_NAME}.stdout" "/tmp/cr_publish_${REPO_NAME}.log" 2>/dev/null | tail -6 >&2
  cat "/tmp/cr_publish_${REPO_NAME}.stdout"
  exit $RC
  ;;

clean)
  # ═══════════ Step 8 编排（zsh 安全）═══════════
  REPO_NAME="${REPO_NAME:-*}"
  setopt null_glob 2>/dev/null || true

  # ── 0. 仓库路径自动恢复（Agent 可能漏传 --repo）──
  if [ -z "$REPO_PATH" ]; then
    for _f in /tmp/cr_prep_*.json; do
      [ -f "$_f" ] || continue
      _RP=$(python3 -c "import json; d=json.load(open('$_f')); print(d.get('repo_path',''))" 2>/dev/null || echo "")
      if [ -n "$_RP" ] && [ -d "$_RP" ]; then
        REPO_PATH="$_RP"
        log "📋 自动恢复仓库路径（from $(basename $_f)）：$REPO_PATH"
        break
      fi
    done
  fi

  # ── 1. /tmp 中间产物清理（无条件执行）──
  rm -f /tmp/local_cr_diff.txt /tmp/local_cr_diff_slim.txt /tmp/cr_slim.log /tmp/local_cr_files.txt /tmp/cr_matched_rules.json 2>/dev/null
  rm -f /tmp/cr_changed_symbols.json /tmp/cr_signal_rules.json 2>/dev/null
  rm -f /tmp/cr_signals_*.md /tmp/cr_ones_context.json /tmp/cr_ones_err.log /tmp/cr_ones_db_info.json /tmp/cr_ones_detail.json 2>/dev/null
  rm -f /tmp/cr_route_plan.json /tmp/cr_route_plan.log 2>/dev/null
  rm -f /tmp/cr_route_4a_*.md /tmp/cr_route_4b_*.md 2>/dev/null
  rm -f /tmp/cr_suspects_*.json 2>/dev/null
  rm -rf /tmp/cr_rule_trim 2>/dev/null
  rm -f /tmp/cr_rule_filter.json /tmp/cr_rule_filter.log 2>/dev/null
  rm -f /tmp/cr_business_context.md /tmp/cr_review_*.json /tmp/cr_custom_rules_*.md /tmp/cr_source_context.md 2>/dev/null
  rm -f /tmp/cr_4d_input_core.md /tmp/cr_4d_input_code.md 2>/dev/null
  rm -f /tmp/cr_l2_rules_*.md /tmp/cr_l2_extract_*.log /tmp/cr_4c_shard_*.md /tmp/cr_l2_probe.log 2>/dev/null
  rm -rf /tmp/cr_l2_bundle_* 2>/dev/null
  rm -f /tmp/cr_issues_*_*.json /tmp/cr_issues_*_*.json.tmp 2>/dev/null
  rm -f /tmp/cr_gitnexus_build.pid /tmp/cr_gitnexus_build.log 2>/dev/null
  # ⚠️ ai_cr_result_*.json 是最终产物（SDLC JSON），Step 8 不删除
  rm -f /tmp/cr-env-cache-* 2>/dev/null
  rm -f /tmp/cr_prep_*.json /tmp/cr_publish_*.log /tmp/cr_publish_*.stdout /tmp/cr_publish_stdout.txt /tmp/cr_env_check_*.log 2>/dev/null
  rm -f /tmp/cr_probe_mapper.txt /tmp/cr_review_input_*.json /tmp/cr_review_miss_*.json /tmp/cr_review_rules_*.md /tmp/cr_review_verdict_*.json 2>/dev/null
  rm -f /tmp/cr_review_meta_*.json /tmp/cr_route_4a_all.md 2>/dev/null
  rm -f /tmp/cr_issues_*.json.tmp /tmp/cr_issues_*_main_p*.json 2>/dev/null
  rm -rf /tmp/cr_layer2_results 2>/dev/null
  rm -f /tmp/cr_signals_run.log /tmp/cr_l2_extract.log /tmp/cr_rules_err.log /tmp/cr_db_write_async.log 2>/dev/null
  rm -f /tmp/ai_cr_hook_trigger_*.json /tmp/ai_cr_ide_trigger_*.json 2>/dev/null

  # ── 2. 仓库内 GitNexus 产物清理 ──
  if [ -n "$REPO_PATH" ] && [ -d "$REPO_PATH" ]; then
    RepoRoot=$(cd "$REPO_PATH" && git rev-parse --show-toplevel 2>/dev/null || echo "$REPO_PATH")
    if [ -d "$RepoRoot/.gitnexus" ]; then
      rm -rf "$RepoRoot/.gitnexus/"
      log "🗑️ 已清理 $RepoRoot/.gitnexus/"
    fi
    if [ -d "$RepoRoot/.claude/skills/gitnexus" ]; then
      rm -rf "$RepoRoot/.claude/skills/gitnexus/"
      log "🗑️ 已清理 $RepoRoot/.claude/skills/gitnexus/"
    fi
  fi

  # ── 3. .gitignore 检查提醒 ──
  if [ -n "$REPO_PATH" ] && [ -d "$REPO_PATH" ]; then
    RepoRoot=$(cd "$REPO_PATH" && git rev-parse --show-toplevel 2>/dev/null || echo "$REPO_PATH")
    Missing=""
    grep -q '^\.gitnexus' "$RepoRoot/.gitignore" 2>/dev/null || Missing="$Missing\n.gitnexus/"
    grep -q '^\.claude/skills/gitnexus' "$RepoRoot/.gitignore" 2>/dev/null || Missing="$Missing\n.claude/skills/gitnexus/"
    if [ -n "$Missing" ]; then
      log "⚠️ 建议在 .gitignore 中添加以下条目，避免被提交到仓库："
      echo -e "$Missing"
    fi
  fi

  log "✅ 清理完成"
  ;;

*)
  echo "用法: bash cr-cli.sh <prep|publish|clean> [参数]"
  echo "  prep    --repo <路径> [--branch b] [--base master] [--ones|--ones-id ID] [--operator-mis mis]"
  echo "  publish --repo <路径> --issues-file <step4.json> [--operator-mis mis] [--overview 文案] [-- 透传 publish_results_local.py 参数]"
  echo "  clean   [--repo <路径>]（--repo 指定时同时清理仓库内 .gitnexus/ 与 .claude/skills/gitnexus/）"
  [ -n "$CMD" ] && exit 1 || exit 0
  ;;
esac
