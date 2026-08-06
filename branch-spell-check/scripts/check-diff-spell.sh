#!/usr/bin/env bash
# Check spelling in files changed on current branch vs base.
# Usage: from repo root (or any subdir), run:
#   .cursor/skills/branch-spell-check/scripts/check-diff-spell.sh [base_branch]
# Example: scripts/check-diff-spell.sh origin/main

set -e
cd "$(git rev-parse --show-toplevel)"

BASE="${1:-origin/main}"
if ! git rev-parse --verify "$BASE" &>/dev/null; then
  BASE="origin/master"
fi
if ! git rev-parse --verify "$BASE" &>/dev/null; then
  echo "Could not resolve base branch (tried origin/main, origin/master). Specify e.g. origin/develop."
  exit 1
fi

# Changed files (text only)
FILES=$(git diff --name-only "$BASE"...HEAD 2>/dev/null | grep -E '\.(tsx?|jsx?|md|json|yml|yaml|mdc)$' || true)
if [ -z "$FILES" ]; then
  echo "No matching changed files for spell check."
  exit 0
fi

echo "Spell checking changed files (base: $BASE)..."
echo "$FILES" | xargs npx cspell --no-progress 2>/dev/null || true
