# GitHub About Block

## Draft Description (edit to <=350 chars)

Linear Trend Spotter - Crypto exchange scanner with backtesting and static PWA dashboard. Built with agent-project-bootstrap. FOSS MIT.

## Topics

crypto scanner backtesting pwa python flask render github-actions foss mit cursor

## Human Setup Checklist

Most settings can be applied via `bash scripts/apply-github-repo-settings.sh` (requires `gh` admin access).

Manual fallback in GitHub **Settings** if the API cannot enable private vulnerability reporting:

1. **Settings → Code security and analysis**
   - Enable **Dependabot alerts** (script: `PUT .../vulnerability-alerts`)
   - Enable **Dependabot security updates** (script: `PUT .../automated-security-fixes`)
   - Enable **Private vulnerability reporting** (UI only if POST returns 404)
2. **Settings → Branches → `main`**
   - Require pull request before merging
   - Require status checks: **Verify**, **Trivy FS Scan**, **Analyze (python)**
   - Enforce for administrators
3. **Settings → General → Repository details**
   - Optional: set `APPLY_GITHUB_ABOUT=1` when running the script to sync from the draft below

See `docs/SECURITY_TRIAGE.md` for weekly CVE triage.
