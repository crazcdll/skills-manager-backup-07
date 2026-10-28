#!/usr/bin/env bash
# fetch <pkg> <old-version> <new-version>：下载到独立扫描目录。
# clean <scan_dir>：只删除本次 fetch 返回的目录。
set -uo pipefail

fetch_version() {
  local spec="$1" dest="$2" tgz
  mkdir -p "$dest" || return 1
  if tgz=$(npm pack "$spec" --ignore-scripts --silent --pack-destination "$dest" 2>/dev/null) \
    && [[ -n "$tgz" && "$tgz" != */* && "$tgz" == *.tgz ]] \
    && tar -xzf "$dest/$tgz" -C "$dest" --strip-components=1 2>/dev/null; then
    rm -f "$dest/$tgz"
    return 0
  fi
  # 不把下载失败或解压了一半的目录当作可用源码。
  rm -rf "$dest"
  return 1
}

cmd_fetch() {
  if [[ $# -ne 3 || -z "$1" || -z "$2" || -z "$3" ]]; then
    echo "usage: bash dep-scan.sh fetch <pkg> <old-version> <new-version>" >&2
    return 1
  fi
  local pkg="$1" old_ver="$2" new_ver="$3" scan_dir
  local old_status=unavailable new_status=unavailable old_dir="" new_dir=""
  scan_dir=$(mktemp -d /tmp/fe-ai-review-dep.XXXXXXXX) || return 1
  if fetch_version "${pkg}@${old_ver}" "$scan_dir/old"; then
    old_status=ready
    old_dir="$scan_dir/old"
  fi
  if fetch_version "${pkg}@${new_ver}" "$scan_dir/new"; then
    new_status=ready
    new_dir="$scan_dir/new"
  fi
  printf 'scan_dir=%s\nold_status=%s\nold_dir=%s\nnew_status=%s\nnew_dir=%s\n' \
    "$scan_dir" "$old_status" "$old_dir" "$new_status" "$new_dir"
  [[ "$old_status" == ready && "$new_status" == ready ]]
}

cmd_clean() {
  local scan_dir="${1:-}"
  if [[ $# -ne 1 || ! "$scan_dir" =~ ^/tmp/fe-ai-review-dep\.[[:alnum:]]+$ || -L "$scan_dir" ]]; then
    echo "clean requires the scan_dir returned by fetch" >&2
    return 1
  fi
  rm -rf "$scan_dir" || return 1
  printf '[dep-scan] cleaned: %s\n' "$scan_dir"
}

case "${1:-}" in
  fetch) shift; cmd_fetch "$@" ;;
  clean) shift; cmd_clean "$@" ;;
  *)
    echo "usage: bash dep-scan.sh fetch <pkg> <old-version> <new-version> | clean <scan_dir>" >&2
    exit 1
    ;;
esac
