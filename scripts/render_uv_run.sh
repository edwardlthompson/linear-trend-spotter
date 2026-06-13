#!/usr/bin/env bash
# Run a command inside the repo-root uv venv (Render start helper).
# Usage: scripts/render_uv_run.sh [--project DIR] COMMAND [ARGS...]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="$ROOT"

if [[ "${1:-}" == "--project" ]]; then
  PROJECT="$(cd "$2" && pwd)"
  shift 2
fi

if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

cd "$PROJECT"
exec uv run "$@"
