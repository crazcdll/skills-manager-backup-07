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
#                        默认不指定，由 mtskills 自行决定安装位置
#
# 退出码:
#   0  全部依赖安装成功
#   1  有依赖安装失败

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

# 获取已安装列表（一次性查询）
INSTALLED_SKILLS=$(mtskills list 2>/dev/null || true)

FAILED=0

for skill in "${SKILL_DEPS[@]}"; do
    if echo "$INSTALLED_SKILLS" | grep -q "$skill"; then
        log_info "$skill 已安装"
    else
        log_warn "$skill 未安装，正在安装..."
        local_install_cmd="mtskills i $skill"
        if [[ -n "$TARGET_DIR_ARG" ]]; then
            local_install_cmd="$local_install_cmd --target-dir $TARGET_DIR_ARG"
        fi

        if eval "$local_install_cmd" 2>/dev/null; then
            log_info "$skill 安装成功"
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

