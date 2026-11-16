#!/usr/bin/env bash
# =============================================================================
# init-fe-rd-workflow-skill.sh
# 使用 mtskills 安装/更新 fe-rd-workflow skill
# 适用平台：macOS (darwin/arm64 & x86_64)
#
# 用法：
#   bash init-fe-rd-workflow-skill.sh                        # 全局安装（已存在则跳过）
#   bash init-fe-rd-workflow-skill.sh --update               # 全局强制更新
#   bash init-fe-rd-workflow-skill.sh --dir /path/to/project # 安装到指定项目目录
#   bash init-fe-rd-workflow-skill.sh --dir /path --update   # 指定目录强制更新
#
# 未指定 --dir 时：安装到 ~/.claude/skills/（全局）
# 指定 --dir 时：安装到 <dir>/.claude/skills/（项目级）
# =============================================================================

set -euo pipefail

# ── 颜色输出 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 参数解析 ──────────────────────────────────────────────────────────────────
UPDATE=false
TARGET_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --update)
      UPDATE=true; shift ;;
    --dir)
      [[ -n "${2:-}" ]] || error "--dir 需要指定目录路径，例如：--dir /path/to/project"
      TARGET_DIR="$2"; shift 2 ;;
    --dir=*)
      TARGET_DIR="${1#--dir=}"; shift ;;
    *)
      error "未知参数: $1\n用法: bash $0 [--dir <path>] [--update]" ;;
  esac
done

# ── 配置 ──────────────────────────────────────────────────────────────────────
SKILL_NAME="fe-rd-workflow"
CATPAW_SYNC_PATH="${HOME}/.catpaw/skills/skills-market/${SKILL_NAME}"

# 根据是否指定 --dir 决定安装模式
if [[ -n "${TARGET_DIR}" ]]; then
  MODE="project"
  TARGET_DIR="$(cd "${TARGET_DIR}" 2>/dev/null && pwd || error "目录不存在: ${TARGET_DIR}")"
  INSTALL_PATH="${TARGET_DIR}/.claude/skills/${SKILL_NAME}"
else
  MODE="global"
  INSTALL_PATH="${HOME}/.claude/skills/${SKILL_NAME}"
fi

# ── 打印头部信息 ───────────────────────────────────────────────────────────────
echo ""
echo "=================================================="
echo "  fe-rd-workflow Skill 安装脚本（via mtskills）"
if [[ "${MODE}" == "project" ]]; then
  echo "  模式：项目级安装 → ${TARGET_DIR}"
else
  echo "  模式：全局安装"
fi
$UPDATE && echo -e "  操作：${YELLOW}强制更新${NC}" || echo "  操作：安装（已存在则跳过）"
echo "=================================================="
echo ""

# ── 前置检查：mtskills ────────────────────────────────────────────────────────
info "检查 mtskills..."

# 查找 mtskills：PATH -> nvm 所有版本
MTSKILLS_BIN="$(command -v mtskills 2>/dev/null || true)"
if [[ -z "${MTSKILLS_BIN}" ]]; then
  for nvm_bin in "${HOME}/.nvm/versions/node"/*/bin/mtskills; do
    [[ -x "${nvm_bin}" ]] && MTSKILLS_BIN="${nvm_bin}" && break
  done
fi

# 找不到则自动安装
if [[ -z "${MTSKILLS_BIN}" ]]; then
  warn "未找到 mtskills，尝试自动安装..."

  # 查找可用的 npm
  NPM_BIN="$(command -v npm 2>/dev/null || true)"
  if [[ -z "${NPM_BIN}" ]]; then
    for nvm_npm in "${HOME}/.nvm/versions/node"/*/bin/npm; do
      [[ -x "${nvm_npm}" ]] && NPM_BIN="${nvm_npm}" && break
    done
  fi
  [[ -n "${NPM_BIN}" ]] || error "未找到 npm，请先安装 Node.js：https://github.com/nvm-sh/nvm"

  info "使用 npm 安装 @mtfe/mtskills（registry: http://r.npm.sankuai.com）..."
  "${NPM_BIN}" i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com

  # 安装后重新查找
  MTSKILLS_BIN="$(command -v mtskills 2>/dev/null || true)"
  if [[ -z "${MTSKILLS_BIN}" ]]; then
    # npm -g 的 bin 目录可能不在 PATH，从 npm prefix 推导
    NPM_PREFIX="$("${NPM_BIN}" prefix -g 2>/dev/null || true)"
    [[ -x "${NPM_PREFIX}/bin/mtskills" ]] && MTSKILLS_BIN="${NPM_PREFIX}/bin/mtskills"
  fi
  [[ -n "${MTSKILLS_BIN}" ]] || error "mtskills 安装后仍未找到，请重新打开终端后再试。"
  success "mtskills 安装完成：${MTSKILLS_BIN}"
else
  success "mtskills 就绪：${MTSKILLS_BIN}"
fi

# ── 安装/更新 ─────────────────────────────────────────────────────────────────
if [[ -f "${INSTALL_PATH}/SKILL.md" ]] && ! $UPDATE; then
  success "${SKILL_NAME} 已安装，跳过。（使用 --update 可强制更新）"
else
  # 更新模式：先删除旧版本
  if [[ -d "${INSTALL_PATH}" ]] && $UPDATE; then
    info "删除旧版本 → ${INSTALL_PATH}"
    rm -rf "${INSTALL_PATH}"
  fi

  # 构造 mtskills install 参数
  MTSKILLS_ARGS=("${SKILL_NAME}" "-y")
  if [[ "${MODE}" == "global" ]]; then
    MTSKILLS_ARGS+=("-g")
  else
    # mtskills --target-dir 只支持相对路径，用 cd 切到父目录执行
    MTSKILLS_ARGS+=("--target-dir" ".claude/skills")
  fi

  info "安装 ${SKILL_NAME}..."
  if [[ "${MODE}" == "project" ]]; then
    (cd "${TARGET_DIR}" && "${MTSKILLS_BIN}" install "${MTSKILLS_ARGS[@]}")
  else
    "${MTSKILLS_BIN}" install "${MTSKILLS_ARGS[@]}"
  fi

  [[ -f "${INSTALL_PATH}/SKILL.md" ]] || error "安装后未找到 SKILL.md，请检查网络或重试。"
  success "安装完成 → ${INSTALL_PATH}"
fi

# ── 同步到 ~/.catpaw/skills/skills-market ────────────────────────────────────
# 以 ~/.claude/skills 下的全局安装结果为准进行同步
CLAUDE_GLOBAL_PATH="${HOME}/.claude/skills/${SKILL_NAME}"
if [[ -f "${CLAUDE_GLOBAL_PATH}/SKILL.md" ]]; then
  if [[ -d "${HOME}/.catpaw/skills" ]]; then
    mkdir -p "${HOME}/.catpaw/skills/skills-market"
    if [[ -d "${CATPAW_SYNC_PATH}" ]] && $UPDATE; then
      info "CatPaw: 删除旧版本..."
      rm -rf "${CATPAW_SYNC_PATH}"
    fi
    if [[ ! -d "${CATPAW_SYNC_PATH}" ]]; then
      info "CatPaw: 同步到 ${CATPAW_SYNC_PATH}..."
      cp -r "${CLAUDE_GLOBAL_PATH}" "${CATPAW_SYNC_PATH}"
      [[ -f "${CATPAW_SYNC_PATH}/SKILL.md" ]] || error "同步到 CatPaw 失败。"
      success "CatPaw: 同步完成 → ${CATPAW_SYNC_PATH}"
    else
      success "CatPaw: 已存在，跳过。（使用 --update 可强制同步）"
    fi
  else
    warn "未找到 ~/.catpaw/skills 目录，跳过 CatPaw 同步。"
  fi
else
  warn "未找到全局 skill（${CLAUDE_GLOBAL_PATH}），跳过 CatPaw 同步。"
fi

# ── 结果汇总 ──────────────────────────────────────────────────────────────────
echo ""
echo "=================================================="
echo -e "${GREEN}  ✅ fe-rd-workflow skill 操作完成！${NC}"
echo ""
echo "  安装路径: ${INSTALL_PATH}"
echo "  CatPaw:   ${CATPAW_SYNC_PATH}"
echo "=================================================="
echo ""
