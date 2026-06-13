# Build Plan

> Bootstrap adoption and agent-ops task board. Product milestones AùQ live in `docs/EXECUTION_PLAN.md`.
> Move completed items to `COMPLETED_TASKS.md`.

## Owner Label Legend

| Label | Owner | When to use |
|-------|-------|-------------|
| `AGENT` | Cursor Agent | Code, docs, scaffolding, tests, CI config |
| `HUMAN` | Human developer | Approvals, credentials, GitHub settings, product decisions |
| `ADB` | Human (Android) | Not applicable to this project |
| `AUTO` | CI/scripts/bots | GitHub Actions, Dependabot, pre-commit, update checker |

**Filter by label:**

```bash
grep '\[AGENT\]' BUILD_PLAN.md
grep '\[HUMAN\]' BUILD_PLAN.md
grep '\[AUTO\]' BUILD_PLAN.md
```

---

## Sprint 0 ù Bootstrap Adoption

### Sequential (must complete in order)

1. [x] [AGENT] Copy bootstrap scaffold (`.cursor/rules`, agent memory, legal, docs, scripts, `.devcontainer`)
2. [x] [AGENT] Set CODEOWNERS to `@edwardlthompson`; run init customization
3. [x] [AGENT] Customize `AGENTS.md`, `AGENT_MEMORY.md`, `BUILD_PLAN.md`, `TEMPLATE_INDEX.json`
4. [x] [AGENT] Add MIT `LICENSE`, `THIRD_PARTY_LICENSES.md`, community docs
5. [ ] [HUMAN] Enable Dependabot alerts + security updates (`docs/SECURITY_TRIAGE.md`)
6. [ ] [HUMAN] Enable private vulnerability reporting + branch protection on `main`
7. [x] [AGENT] Draft `docs/THREAT_MODEL.md`, `docs/PRIVACY.md`, `docs/RUNBOOK.md`
8. [x] [AUTO] `scripts/validate-bootstrap.sh` passes
9. [ ] [HUMAN] Approve Sprint 0 after CI green on `main`

### Parallel (safe after Sequential step 3)

| Task | Owner | Isolated scope |
|------|-------|----------------|
| Merge copilot-instructions into AGENTS.md | AGENT | `AGENTS.md`, `.github/copilot-instructions.md` |
| Configure `.template-update.json` interval | HUMAN | `.template-update.json` |
| Set GitHub repo About from `docs/GITHUB_ABOUT.md` | HUMAN | GitHub settings |

---

## Sprint 1 ù uv + CI Parity

### Sequential (must complete in order)

1. [x] [AGENT] Consolidate deps in `pyproject.toml`; generate `uv.lock`
2. [x] [AGENT] Update `scripts/ci_verify.sh`, `render.yaml`, pre-commit to `uv sync --locked`
3. [x] [AGENT] Merge bootstrap guardrail jobs into `.github/workflows/ci.yml`
4. [x] [AGENT] Add CodeQL, Trivy, dependency-review, health-check, release workflows
5. [x] [AGENT] Extend `scripts/check_github_ci.py` for CI + Security Scan + CodeQL
6. [x] [AUTO] Full CI matrix green on `main`
7. [ ] [HUMAN] Sign off Sprint 1

### Parallel (safe after Sequential step 4)

| Task | Owner | Isolated scope |
|------|-------|----------------|
| Export legacy `requirements*.txt` from uv | AGENT | `requirements.txt`, `requirements-ci.txt` |
| Expand pre-commit hooks | AGENT | `.pre-commit-config.yaml` |
| Update README quick-start to uv | AGENT | `README.md` |

---

## Sprint 2 ù Security & Ops Hardening

### Sequential

1. [ ] [HUMAN] Weekly CVE triage pass per `docs/SECURITY_TRIAGE.md`
2. [ ] [AGENT] Review `THIRD_PARTY_LICENSES.md` after dependency changes
3. [ ] [AUTO] Trivy + CodeQL + CI green after merges

---

## Sprint 3+ ù Web Module (Deferred)

### Parallel

| Task | Owner | Isolated scope |
|------|-------|----------------|
| Lighthouse CI for `docs/dashboard/` | AGENT | `docs/dashboard/`, new npm tooling |
| axe-core accessibility tests | AGENT | `docs/dashboard/` |
| File line-limit refactor (legacy exemptions) | HUMAN decision | large Python/JS modules |

---

## Ongoing Maintenance

- [ ] [HUMAN] Weekly CVE triage (recommended: Monday)
- [ ] [AGENT] Apply Dependabot bumps as needed
- [ ] [AUTO] Template update check (`scripts/check-template-updates.sh`)

## Milestone Gates

- [x] [AUTO] `scripts/validate-bootstrap.sh` green
- [x] [AUTO] `scripts/ci_verify.sh` green (local + Render)
- [x] [AUTO] Required workflows: CI, Security Scan, CodeQL
- [ ] [HUMAN] Zero open Critical/High Dependabot alerts (or documented exception)
- [ ] [HUMAN] `CHANGELOG.md` updated on releases
