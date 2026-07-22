#!/usr/bin/env bash
# Fail if any tracked file exceeds size budget (matches pre-commit 500KB gate)
# Optional allowlist: .large-files-allowlist (exact path or prefix ending with /)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAX_KB=500
MAX_BYTES=$((MAX_KB * 1024))
ERRORS=0
MAX_REPORT=20
reported=0

ALLOWLIST_FILE="$ROOT/.large-files-allowlist"
is_allowlisted() {
  local file="$1"
  [ -f "$ALLOWLIST_FILE" ] || return 1
  while IFS= read -r pattern || [ -n "${pattern:-}" ]; do
    [[ -z "${pattern:-}" || "$pattern" =~ ^[[:space:]]*# ]] && continue
    pattern="${pattern#"${pattern%%[![:space:]]*}"}"
    pattern="${pattern%"${pattern##*[![:space:]]}"}"
    if [[ "$pattern" == */ ]]; then
      if [[ "$file" == "$pattern"* ]]; then
        return 0
      fi
    elif [[ "$file" == "$pattern" ]]; then
      return 0
    fi
  done < "$ALLOWLIST_FILE"
  return 1
}

while IFS= read -r file; do
  [ -z "$file" ] && continue
  if is_allowlisted "$file"; then
    continue
  fi
  size=$(git cat-file -s "HEAD:$file" 2>/dev/null || echo 0)
  if [ "$size" = "0" ] && [ -f "$file" ]; then
    size=$(wc -c < "$file" | tr -d ' ')
  fi
  if [ "$size" -gt "$MAX_BYTES" ]; then
    kb=$((size / 1024))
    echo "LARGE TRACKED FILE: $file (${kb} KB > ${MAX_KB} KB)"
    ERRORS=$((ERRORS + 1))
    reported=$((reported + 1))
    if [ "$reported" -ge "$MAX_REPORT" ]; then
      echo "... truncated (max $MAX_REPORT)"
      break
    fi
  fi
done < <(git ls-files)

if [ "$ERRORS" -gt 0 ]; then
  echo "$ERRORS tracked file(s) exceed ${MAX_KB} KB"
  exit 1
fi

echo "Large tracked file check passed"
