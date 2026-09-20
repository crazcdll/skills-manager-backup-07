#!/usr/bin/env bash
# Fetch an external KB and read immutable Git objects, without checking out or executing its files.
set -euo pipefail

CACHE_ROOT="${TRADE_KB_EXTERNAL_DIR:-$HOME/.trade-fe-kb-external}"

fail() { printf '[external-kb][%s] %s\n' "$1" "$2" >&2; exit 2; }

check_path() {
  case "$1" in
    ''|/*|./*|../*|*/../*|*/..|*/./*|*/.|*//*|*$'\n'*|*$'\r'*)
      fail CONFIG 'Expected a repository-relative path without traversal.' ;;
  esac
}

check_cache() {
  [ ! -L "$CACHE_ROOT" ] && [ ! -L "$REPO_DIR" ] || fail CACHE 'Cache directories must not be symlinks.'
  [ -d "$CACHE_DIR" ] && [ ! -L "$CACHE_DIR" ] || fail CACHE 'Cache is missing or is a symlink.'
  [ "$(git --git-dir="$CACHE_DIR" rev-parse --is-bare-repository 2>/dev/null)" = true ] || fail CACHE 'Cache is not a bare repository.'
  local actual
  actual="$(git --git-dir="$CACHE_DIR" config --get-all remote.origin.url)" || fail CACHE 'Cache has no origin.'
  [ "$actual" = "$REPOSITORY_URL" ] || fail CACHE 'Cached origin differs from the registry; cache was not changed.'
}

check_commit() {
  [[ "$COMMIT" =~ ^[0-9a-f]{40}$|^[0-9a-f]{64}$ ]] || fail CONFIG 'Expected a full commit ID returned by sync.'
  git --git-dir="$CACHE_DIR" cat-file -e "$COMMIT^{commit}" 2>/dev/null || fail VERSION 'Commit is not available.'
}

check_file() {
  local path="$1" mode
  check_path "$path"
  mode="$(git --git-dir="$CACHE_DIR" ls-tree "$COMMIT" -- ":(literal)$path")"
  case "$mode" in
    '100644 blob '*|'100755 blob '*) ;;
    *) fail ENTRY 'Path is missing or is not a regular file at this commit.' ;;
  esac
}

sync_repository() (
  local ref="$1" entrypoint="$2" lock staging='' commit
  check_path "$entrypoint"
  case "$ref" in
    refs/heads/*|refs/tags/*) git check-ref-format "$ref" >/dev/null || fail CONFIG 'Invalid Git ref.' ;;
    *) [[ "$ref" =~ ^[0-9a-f]{40}$|^[0-9a-f]{64}$ ]] || fail CONFIG 'Use refs/heads/..., refs/tags/... or a full commit ID.' ;;
  esac
  umask 077
  [ ! -L "$CACHE_ROOT" ] && [ ! -L "$REPO_DIR" ] || fail CACHE 'Cache directories must not be symlinks.'
  mkdir -p "$REPO_DIR"
  lock="$REPO_DIR/.sync-lock"
  mkdir "$lock" 2>/dev/null || fail BUSY 'Another sync is running; retry after it finishes. A stale lock needs manual inspection.'
  trap 'if [ -n "$staging" ]; then rm -rf -- "$staging"; fi; rmdir "$lock"' EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  if [ ! -e "$CACHE_DIR" ] && [ ! -L "$CACHE_DIR" ]; then
    staging="$(mktemp -d "$REPO_DIR/.init.XXXXXX")"
    git init --bare --quiet "$staging"
    git --git-dir="$staging" config remote.origin.url "$REPOSITORY_URL"
    mv "$staging" "$CACHE_DIR"
    staging=''
  fi
  check_cache
  # The per-repository lock protects FETCH_HEAD. Retaining a ref keeps older query snapshots reachable.
  if ! GIT_TERMINAL_PROMPT=0 git -c gc.auto=0 --git-dir="$CACHE_DIR" fetch --no-tags origin "$ref" >&2; then
    fail FETCH 'Fetch failed; this query must not read an older cached version. Check Git access and the configured ref.'
  fi
  commit="$(git --git-dir="$CACHE_DIR" rev-parse --verify 'FETCH_HEAD^{commit}')" || fail VERSION 'Ref does not resolve to a commit.'
  COMMIT="$commit"
  check_file "$entrypoint"
  git --git-dir="$CACHE_DIR" update-ref "refs/kb-snapshots/$commit" "$commit"
  jq -n --arg id "$ID" --arg url "$REPOSITORY_URL" --arg commit "$commit" \
    --arg entrypoint "$entrypoint" --arg cache "$CACHE_DIR" \
    '{id:$id,repository_url:$url,commit:$commit,entrypoint:$entrypoint,cache_dir:$cache}'
)

usage() {
  printf '%s\n' \
    'Usage: external-kb.sh sync <id> <repository_url> <ref> <entrypoint>' \
    '       external-kb.sh read <id> <repository_url> <commit> <path> [start-line end-line]' \
    '       external-kb.sh search <id> <repository_url> <commit> <literal-term> <path-or-directory>' >&2
  exit 2
}

[ "$#" -ge 1 ] || usage
ACTION="$1"; shift
case "$ACTION:$#" in sync:4|read:4|read:6|search:5) ;; *) usage ;; esac
ID="$1"; REPOSITORY_URL="$2"; shift 2
[[ "$ID" =~ ^[a-z][a-z0-9-]*$ ]] && [ "$ID" != default ] || fail CONFIG 'Invalid external repository ID.'
case "$REPOSITORY_URL" in ssh://*|https://*) ;; *) fail CONFIG 'Expected an SSH or HTTPS Git repository URL.' ;; esac
REPO_DIR="$CACHE_ROOT/$ID"
CACHE_DIR="$REPO_DIR/repository.git"
command -v git >/dev/null || fail ENV 'Missing command: git'
if [ "$ACTION" = sync ]; then
  command -v jq >/dev/null || fail ENV 'Missing command: jq (required only for sync result formatting)'
fi

if [ "$ACTION" = sync ]; then
  sync_repository "$1" "$2"
  exit
fi
check_cache
COMMIT="$1"; shift
check_commit
if [ "$ACTION" = read ]; then
  check_file "$1"
  if [ "$#" -eq 3 ]; then
    [[ "$2" =~ ^[1-9][0-9]{0,8}$ ]] && [[ "$3" =~ ^[1-9][0-9]{0,8}$ ]] && [ "$2" -le "$3" ] || fail CONFIG 'Expected positive start/end lines in ascending order.'
    git --git-dir="$CACHE_DIR" show "$COMMIT:$1" | nl -ba | sed -n "${2},${3}p"
  else
    git --git-dir="$CACHE_DIR" show "$COMMIT:$1" | nl -ba
  fi
else
  TERM_LITERAL="$1"; SEARCH_PATH="$2"
  [ -n "$TERM_LITERAL" ] || fail CONFIG 'Search term must not be empty.'
  check_path "$SEARCH_PATH"
  git --git-dir="$CACHE_DIR" cat-file -e "$COMMIT:$SEARCH_PATH" 2>/dev/null || fail ENTRY 'Search path does not exist at this commit.'
  # git grep exit 1 means no match; other nonzero statuses mean execution failed.
  git --git-dir="$CACHE_DIR" grep -n -I -F -e "$TERM_LITERAL" "$COMMIT" -- ":(literal)$SEARCH_PATH"
fi
