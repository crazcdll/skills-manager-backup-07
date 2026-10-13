#!/bin/bash
# hotel-product-testdata 依赖安装脚本（.catpaw/skills 版本）
#
# 用法:
#   bash scripts/setup.sh [--target-dir <dir>]
#
# 功能:
#   1. 确保 mtskills CLI 可用（npm 全局安装）
#   2. 安装所有依赖的 Skill（通过 mtskills）
#
# 选项:
#   --target-dir <dir>   指定 skill 安装目录
#                        默认安装到项目根目录 <项目根>/.claude/skills/（固定路径，不随 cwd 漂移）
#
# 已安装检查（直接探测目录，不依赖 mtskills list）：
#   依次检查以下位置，任一存在即视为已安装、跳过安装：
#     1. <项目根>/.claude/skills/<skill>     （项目级安装位置）
#     2. <项目根>/.catpaw/skills/<skill>     （CatPaw workspace 级，mtskills 扫不到）
#     3. ~/.claude/skills/<skill>            （用户全局）
#     4. ~/.catpaw/skills/<skill>            （CatPaw 用户全局，mtskills 扫不到）
#   注：mtskills list 只扫 <cwd>/.agent|~/.agent|<cwd>/.claude|~/.claude 四条路径，
#       既看不见 .catpaw/skills，也随 cwd 漂移，故不再使用它做检查。
#
# 退出码:
#   0  全部依赖安装成功
#   1  有依赖安装失败

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 锁定 cwd：防止 mtskills 默认"项目级安装"落到执行时所在的任意目录（cwd 漂移）
cd "$SKILL_DIR"

# 项目根定位：skill 位于 <项目根>/.catpaw/skills/<skill-name>/，项目根即往上三级
PROJECT_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[✓]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
log_error() { echo -e "${RED}[✗]${NC} $*" >&2; }

# ========== 参数解析 ==========
TARGET_DIR_ARG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target-dir) TARGET_DIR_ARG="$2"; shift 2 ;;
        -h|--help)
            echo "用法: bash scripts/setup.sh [--target-dir <dir>]"
            echo ""
            echo "安装 hotel-product-testdata 所有依赖："
            echo "  - CLI: @mtfe/mtskills（npm 全局包）"
            echo "  - Skills: testdata-report-execution"
            exit 0
            ;;
        *) log_error "未知参数: $1"; exit 1 ;;
    esac
done

# ========== mtskills CLI ==========
echo "━━━ mtskills CLI 检查 ━━━"

if command -v mtskills &>/dev/null; then
    log_info "mtskills 已安装"
else
    log_warn "mtskills 未安装，正在安装..."
    if npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com 2>/dev/null; then
        log_info "mtskills 安装成功"
    else
        log_error "mtskills 安装失败，请检查 npm 环境"
        exit 1
    fi
fi

echo ""

# ========== Skill 依赖 ==========
echo "━━━ Skill 依赖检查 ━━━"

# 依赖 skill 列表
SKILL_DEPS=(
    "testdata-report-execution"
)

# 已安装探测位置（按优先级）：项目目录优先，其次用户目录；覆盖 .claude 与 .catpaw 两套体系
SKILL_SEARCH_DIRS=(
    "$PROJECT_ROOT/.claude/skills"
    "$PROJECT_ROOT/.catpaw/skills"
    "$HOME/.claude/skills"
    "$HOME/.catpaw/skills"
)

# 默认安装目录：项目根 .claude/skills（固定路径；显式 --target-dir 时以参数为准）
DEFAULT_INSTALL_DIR="$PROJECT_ROOT/.claude/skills"

# 检查某个 skill 是否已安装（探测目录存在性，而非 mtskills list）
skill_installed() {
    local skill="$1" dir
    for dir in "${SKILL_SEARCH_DIRS[@]}"; do
        if [[ -d "$dir/$skill" ]]; then
            echo "$dir/$skill"
            return 0
        fi
    done
    return 1
}

FAILED=0

for skill in "${SKILL_DEPS[@]}"; do
    if found_path="$(skill_installed "$skill")"; then
        log_info "$skill 已安装 → $found_path"
    else
        install_dir="${TARGET_DIR_ARG:-$DEFAULT_INSTALL_DIR}"
        log_warn "$skill 未安装，正在安装到 $install_dir ..."
        mkdir -p "$install_dir"
        install_cmd="mtskills i $skill --target-dir $install_dir"

        if eval "$install_cmd" 2>/dev/null; then
            log_info "$skill 安装成功 → $install_dir/$skill"
        else
            log_error "$skill 安装失败"
            FAILED=$((FAILED + 1))
        fi
    fi
done

echo ""

# ========== 汇总 ==========
if [[ $FAILED -eq 0 ]]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "所有依赖安装完成！"
    echo "━━━━━━━━━━━━━━━━━━━━━━━"
    exit 0
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━"
    log_error "有 $FAILED 个 skill 安装失败，请检查网络或手动安装"
    echo "━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1
fi

