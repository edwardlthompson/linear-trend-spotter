#!/usr/bin/env bash
# Verify required bootstrap artifacts exist and pass delegated checks
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REQUIRED=(
  README.md
  LICENSE
  CONTRIBUTING.md
  SECURITY.md
  CODE_OF_CONDUCT.md
  BUILD_PLAN.md
  AGENTS.md
  AGENT_MEMORY.md
  docs/START_HERE.md
  docs/INITIALIZATION_PROMPT.md
  docs/SECURITY_TRIAGE.md
  docs/THREAT_MODEL.md
  docs/PRIVACY.md
  docs/RUNBOOK.md
  .github/dependabot.yml
  .github/CODEOWNERS
  THIRD_PARTY_LICENSES.md
  .env.example
)

ERRORS=0

run_check() {
  if ! "$@"; then
    ERRORS=$((ERRORS + 1))
  fi
}

for f in "${REQUIRED[@]}"; do
  if [ ! -e "$f" ]; then
    echo "MISSING: $f"
    ERRORS=$((ERRORS + 1))
  fi
done

if [ -f LICENSE ] && [ ! -s LICENSE ]; then
  echo "EMPTY: LICENSE"
  ERRORS=$((ERRORS + 1))
fi

if [ ! -f uv.lock ]; then
  echo "MISSING: uv.lock (required for locked Python installs)"
  ERRORS=$((ERRORS + 1))
fi

if [ ! -f docs/EXECUTION_PLAN.md ]; then
  echo "MISSING: docs/EXECUTION_PLAN.md (project-specific task board)"
  ERRORS=$((ERRORS + 1))
fi

if ! grep -q '\[AGENT\]' BUILD_PLAN.md && ! grep -q '\[HUMAN\]' BUILD_PLAN.md; then
  echo "MISSING: BUILD_PLAN.md owner labels"
  ERRORS=$((ERRORS + 1))
fi

run_check bash scripts/check-file-encoding.sh
run_check bash scripts/validate-workflow-actions.sh
run_check bash scripts/validate-template-index.sh

if [ "$ERRORS" -gt 0 ]; then
  echo "$ERRORS bootstrap check(s) failed"
  exit 1
fi

echo "Bootstrap validation passed"
