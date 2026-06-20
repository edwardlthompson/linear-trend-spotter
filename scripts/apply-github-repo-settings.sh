#!/usr/bin/env bash
# Apply GitHub repo settings that are normally [HUMAN] in BUILD_PLAN.md.
# Requires: gh CLI authenticated with admin access to the repository.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v gh >/dev/null 2>&1; then
  echo "FAIL: gh CLI not found. Install GitHub CLI and run: gh auth login"
  exit 1
fi

OWNER_REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
OWNER="${OWNER_REPO%%/*}"
REPO="${OWNER_REPO##*/}"

echo "=== GitHub repo settings: $OWNER_REPO ==="

echo "Enabling Dependabot alerts..."
gh api -X PUT "repos/${OWNER}/${REPO}/vulnerability-alerts" >/dev/null

echo "Enabling Dependabot security updates..."
gh api -X PUT "repos/${OWNER}/${REPO}/automated-security-fixes" >/dev/null

echo "Enabling private vulnerability reporting..."
if gh api -X POST "repos/${OWNER}/${REPO}/private-vulnerability-reporting" >/dev/null 2>&1; then
  echo "  private vulnerability reporting: enabled"
else
  echo "  WARN: could not enable private vulnerability reporting via API (check admin token or org policy)"
fi

ABOUT_FILE="$ROOT/docs/GITHUB_ABOUT.md"
if [ "${APPLY_GITHUB_ABOUT:-0}" = "1" ] && [ -f "$ABOUT_FILE" ]; then
  DESC="$(python3 - "$ABOUT_FILE" << 'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"## Draft Description[^\n]*\n\n(.+?)\n\n## Topics", text, re.S)
print(m.group(1).strip() if m else "")
PY
)"
  TOPICS="$(python3 - "$ABOUT_FILE" << 'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"## Topics\n\n(.+?)(?:\n\n|$)", text, re.S)
if not m:
    sys.exit(0)
for t in m.group(1).split():
    print(t)
PY
)"
  if [ -n "$DESC" ]; then
    echo "Updating repository description..."
    gh repo edit "$OWNER_REPO" --description "$DESC"
  fi
  if [ -n "$TOPICS" ]; then
    echo "Adding repository topics..."
    # shellcheck disable=SC2086
    gh repo edit "$OWNER_REPO" --add-topic $TOPICS
  fi
fi

echo "Updating branch protection on main..."
PROTECTION_JSON="$(mktemp)"
trap 'rm -f "$PROTECTION_JSON"' EXIT
python3 - "$PROTECTION_JSON" << 'PY'
import json, sys
payload = {
    "required_status_checks": {
        "strict": True,
        "checks": [
            {"context": "Verify", "app_id": 15368},
            {"context": "Secret scan", "app_id": 15368},
            {"context": "Trivy FS Scan", "app_id": 15368},
            {"context": "Analyze (python)", "app_id": 15368},
        ],
    },
    "enforce_admins": True,
    "required_pull_request_reviews": {"required_approving_review_count": 1},
    "restrictions": None,
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(payload, f)
PY

gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "repos/${OWNER}/${REPO}/branches/main/protection" \
  --input "$PROTECTION_JSON"

echo ""
echo "=== Current security settings ==="
gh api "repos/${OWNER}/${REPO}" --jq '{
  description: .description,
  topics: .topics,
  security: .security_and_analysis
}'
gh api "repos/${OWNER}/${REPO}/private-vulnerability-reporting" 2>/dev/null || true
gh api "repos/${OWNER}/${REPO}/branches/main/protection" --jq '{
  enforce_admins: .enforce_admins.enabled,
  required_checks: [.required_status_checks.checks[].context]
}' 2>/dev/null || true

echo ""
echo "Done. Run: python scripts/check_github_ci.py --wait 300"
