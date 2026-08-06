#!/usr/bin/env bash
# dep-scan.sh — 依赖升级扫描工具
#
# 子命令：
#   fetch <pkg-name> <old-version> <new-version>
#       下载指定包的新旧两个版本 tgz 并解压到临时目录，输出路径供 Agent 读取
#   clean
#       清理 /tmp/fe-ai-review/ 下所有临时文件
#
# 路径保护：所有操作固定在 /tmp/fe-ai-review/ 下，不操作任意路径。

set -uo pipefail

SKILL_TMP="/tmp/fe-ai-review"
SUBCMD="${1:-}"

# ── fetch ─────────────────────────────────────────────────────────────────────
cmd_fetch() {
  local PKG="${1:-}" OLD_VER="${2:-}" NEW_VER="${3:-}"

  if [[ -z "$PKG" || -z "$OLD_VER" || -z "$NEW_VER" ]]; then
    echo "usage: bash dep-scan.sh fetch <pkg-name> <old-version> <new-version>" >&2
    exit 1
  fi

  # 把包名中的 / @ 替换为 _ 作为目录名（避免路径问题）
  local SAFE_PKG BASE_DIR OLD_DIR NEW_DIR
  SAFE_PKG=$(echo "$PKG" | tr '/@' '_' | sed 's/^_//')
  BASE_DIR="${SKILL_TMP}/dep-upgrade-scan/${SAFE_PKG}"
  OLD_DIR="${BASE_DIR}/old"
  NEW_DIR="${BASE_DIR}/new"

  mkdir -p "$OLD_DIR" "$NEW_DIR"

  # 下载 & 解压 old
  echo "[dep-scan] Fetching ${PKG}@${OLD_VER} ..."
  local OLD_TGZ
  if OLD_TGZ=$(npm pack "${PKG}@${OLD_VER}" --pack-destination "${BASE_DIR}" 2>/dev/null); then
    tar -xzf "${BASE_DIR}/${OLD_TGZ}" -C "$OLD_DIR" --strip-components=1 2>/dev/null \
      || { echo "[dep-scan] warn: failed to extract old tgz" >&2; }
    [[ "${BASE_DIR}/${OLD_TGZ}" == /tmp/fe-ai-review/* ]] && rm -f "${BASE_DIR}/${OLD_TGZ}"
  else
    echo "[dep-scan] warn: npm pack failed for ${PKG}@${OLD_VER}, skipping old version" >&2
  fi

  # 下载 & 解压 new
  echo "[dep-scan] Fetching ${PKG}@${NEW_VER} ..."
  local NEW_TGZ
  if NEW_TGZ=$(npm pack "${PKG}@${NEW_VER}" --pack-destination "${BASE_DIR}" 2>/dev/null); then
    tar -xzf "${BASE_DIR}/${NEW_TGZ}" -C "$NEW_DIR" --strip-components=1 2>/dev/null \
      || { echo "[dep-scan] warn: failed to extract new tgz" >&2; }
    [[ "${BASE_DIR}/${NEW_TGZ}" == /tmp/fe-ai-review/* ]] && rm -f "${BASE_DIR}/${NEW_TGZ}"
  else
    echo "[dep-scan] warn: npm pack failed for ${PKG}@${NEW_VER}, skipping new version" >&2
  fi

  # 输出路径供 Agent 使用
  echo "[dep-scan] old_dir=${OLD_DIR}"
  echo "[dep-scan] new_dir=${NEW_DIR}"
}

# ── clean ─────────────────────────────────────────────────────────────────────
cmd_clean() {
  if [[ -d "$SKILL_TMP" && "$SKILL_TMP" == /tmp/fe-ai-review ]]; then
    rm -rf "$SKILL_TMP"
    echo "[fe-ai-review] cleaned: $SKILL_TMP"
  else
    echo "[fe-ai-review] skip: $SKILL_TMP not found"
  fi
}

# ── 路由 ──────────────────────────────────────────────────────────────────────
case "$SUBCMD" in
  fetch) shift; cmd_fetch "$@" ;;
  clean) cmd_clean ;;
  *)
    echo "usage: bash dep-scan.sh <fetch|clean> [args...]" >&2
    echo "  fetch <pkg-name> <old-version> <new-version>  — 下载并解压新旧版本" >&2
    echo "  clean                                         — 清理所有临时文件" >&2
    exit 1
    ;;
esac
