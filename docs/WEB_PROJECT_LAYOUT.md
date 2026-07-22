# Web Project Layout

> Where the PWA, agent documentation, and design tokens live in **linear-trend-spotter**.
> Adapted from agent-project-bootstrap; this repo does **not** use `examples/web/`.

## Folder roles

| Path | Purpose | Public? |
|------|---------|---------|
| `docs/` (markdown) | Agent prompts, security playbooks, design guide, ADRs | Docs for agents/humans |
| [`docs/dashboard/`](dashboard/) | **Golden Path PWA** (static HTML/JS/CSS + service worker) | Yes — served as GitHub Pages / static host |
| [`design-tokens/`](../design-tokens/) | Bootstrap token files (parity with template) | No |
| `docs/dashboard/styles.css` | **Current visual source of truth** for the dashboard | Bundled with PWA |

**Note:** Unlike the upstream template, this project's PWA lives under `docs/dashboard/` (historical + Pages-friendly). Agent markdown stays in `docs/*.md`; do not mix unrelated marketing sites into `docs/dashboard/`.

## Golden Path (this repo)

```text
docs/dashboard/          # edit PWA here
  index.html
  app.js
  styles.css             # CSS source of truth until token sync sprint
  sw.js                  # offline-first service worker
  manifest.webmanifest
  config.example.js
  icons/

design-tokens/           # template parity; not yet synced into styles.css
modules/web/MODULE.md    # web module activation checklist
```

Flow:

1. Edit files under `docs/dashboard/`.
2. Bump `sw.js` cache version when shipping asset changes.
3. Deploy via existing Pages / static hosting process (see `docs/WEB_DASHBOARD.md`, `docs/RUNBOOK.md`).
4. Design-token → CSS sync is deferred (see `BUILD_PLAN.md` / `docs/BOOTSTRAP_ALIGNMENT.md`).

## Related docs

- [`docs/WEB_DASHBOARD.md`](WEB_DASHBOARD.md) — operator-facing dashboard guide
- [`docs/DESIGN_GUIDE.md`](DESIGN_GUIDE.md) — tokens / themes (template guidance; map to dashboard CSS)
- [`modules/web/MODULE.md`](../modules/web/MODULE.md) — Lighthouse / a11y deferred items
