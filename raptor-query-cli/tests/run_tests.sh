#!/usr/bin/env bash
# run_tests.sh — 自动解析 TESTCASES.md 执行测试
# 格式：CMD: <命令>  EXPECT: <关键字>  EXPECT_FAIL: true  EXPECT_EMPTY: true
# 用法：
#   bash run_tests.sh                    # 全量回归
#   bash run_tests.sh --smoke            # 冒烟测试（[smoke]标记的用例）
#   bash run_tests.sh --filter <关键字>  # 按名称过滤

set -o pipefail
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
TESTFILE="${TESTFILE:-$SCRIPT_DIR/TESTCASES.md}"

# 自动将 raptor CLI 加入 PATH（-f 而非 -x，因为安装后权限可能丢失）
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
if [[ -f "$SKILL_DIR/raptor-prod" ]]; then
    chmod +x "$SKILL_DIR/raptor-prod" 2>/dev/null
    export PATH="$SKILL_DIR:$PATH"
fi

SMOKE=false
FILTER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --smoke) SMOKE=true; shift ;;
        --filter) FILTER="$2"; shift 2 ;;
        *.md) TESTFILE="$1"; shift ;;
        *) shift ;;
    esac
done

[[ ! -f "$TESTFILE" ]] && { echo "❌ 找不到 $TESTFILE"; exit 1; }

PASS=0 FAIL=0 SKIP=0 TOTAL=0
FAILURES=()

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'

run_case() {
    local name="$1" cmd="$2" expect_fail="$3" expect_empty="$4" is_smoke="$5"
    shift 5
    local expects=("$@")

    ((TOTAL++))

    if $SMOKE && [[ "$is_smoke" != "true" ]]; then
        ((SKIP++)); return
    fi

    [[ -n "$FILTER" && "$name" != *"$FILTER"* ]] && { ((SKIP++)); return; }

    local output exit_code
    output=$(eval "$cmd" 2>&1)
    exit_code=$?

    local ok=true reason=""

    if [[ "$expect_fail" == "true" ]]; then
        [[ $exit_code -eq 0 ]] && { ok=false; reason="预期失败但 exit=0"; }
    else
        [[ $exit_code -ne 0 && "$expect_empty" != "true" ]] && { ok=false; reason="exit=$exit_code"; }
    fi

    if [[ "$expect_empty" == "true" ]]; then
        [[ -n "$output" ]] && { ok=false; reason="预期无输出但有: ${output:0:80}"; }
    fi

    for exp in "${expects[@]}"; do
        if ! grep -qF -- "$exp" <<< "$output"; then
            ok=false; reason="缺少预期关键字: $exp"; break
        fi
    done

    if $ok; then
        ((PASS++))
        printf "${GREEN}✅ %-40s${NC}\n" "$name"
    else
        ((FAIL++))
        printf "${RED}❌ %-40s %s${NC}\n" "$name" "$reason"
        FAILURES+=("$name: $reason")
    fi
}

MODE="全量回归"
$SMOKE && MODE="冒烟测试"
[[ -n "$FILTER" ]] && MODE="过滤: $FILTER"

echo "🧪 raptor-query-cli 自动化测试 [$MODE]"
echo "   测试集: $TESTFILE"
echo "   $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================"

current_name="" current_cmd="" expect_fail="false" expect_empty="false" current_smoke="false"
declare -a current_expects=()

flush_case() {
    if [[ -n "$current_cmd" ]]; then
        run_case "$current_name" "$current_cmd" "$expect_fail" "$expect_empty" "$current_smoke" "${current_expects[@]}"
    fi
    current_name="" current_cmd="" expect_fail="false" expect_empty="false" current_smoke="false"
    current_expects=()
}

while IFS= read -r line; do
    if [[ "$line" =~ ^###[[:space:]]+Case ]]; then
        flush_case
        current_name="${line#*Case }"
        current_name="${current_name%%$'\r'}"
        if [[ "$current_name" == *"[smoke]"* ]]; then
            current_smoke="true"
            current_name="${current_name/\[smoke\]/}"
            current_name="${current_name%% }"
        fi
    elif [[ "$line" =~ ^CMD:[[:space:]]+(.*) ]]; then
        current_cmd="${BASH_REMATCH[1]%%$'\r'}"
    elif [[ "$line" =~ ^EXPECT_FAIL:[[:space:]]+true ]]; then
        expect_fail="true"
    elif [[ "$line" =~ ^EXPECT_EMPTY:[[:space:]]+true ]]; then
        expect_empty="true"
    elif [[ "$line" =~ ^EXPECT:[[:space:]]+(.*) ]]; then
        current_expects+=("${BASH_REMATCH[1]%%$'\r'}")
    fi
done < "$TESTFILE"
flush_case

echo ""
echo "================================================"
printf "总计: %d | ${GREEN}通过: %d${NC} | ${RED}失败: %d${NC}" "$TOTAL" "$PASS" "$FAIL"
[[ $SKIP -gt 0 ]] && printf " | ${YELLOW}跳过: %d${NC}" "$SKIP"
echo ""

if [[ ${#FAILURES[@]} -gt 0 ]]; then
    echo ""
    echo "失败详情:"
    for f in "${FAILURES[@]}"; do
        printf "  ${RED}• %s${NC}\n" "$f"
    done
    exit 1
fi
