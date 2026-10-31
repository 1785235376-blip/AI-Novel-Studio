#!/usr/bin/env bash
set -euo pipefail
# Usage: PYTHON_BIN=/path/to/existing/venv/bin/python bash run_evidence.sh /path/to/worktree
ROOT="$(cd "${1:?Pass the implementation worktree}" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:?Set PYTHON_BIN to an existing dependency-complete interpreter}"
export HOME="$HERE/home" XDG_DATA_HOME="$HERE/data" XDG_CONFIG_HOME="$HERE/home/config"
export XDG_CACHE_HOME="$HERE/home/cache" XDG_STATE_HOME="$HERE/home/state"
export NOVEL_DATA="$HERE/data" TMPDIR="$HERE/tmp" PYTHONPATH="$ROOT"
mkdir -p "$HOME" "$XDG_DATA_HOME" "$TMPDIR"
cd "$ROOT"
sha256sum app/repositories/generation_repository.py app/repositories/postgres/generation.py app/services/generation_project_binding.py > "$HERE/evidence-before.sha256"
"$PYTHON_BIN" -m pytest -q "$HERE/test_independent.py" --basetemp="$HERE/tmp/evidence-pytest" --junitxml="$HERE/independent-results.xml" 2>&1 | tee "$HERE/independent-results.log"
"$PYTHON_BIN" "$HERE/chapter_boundary.py" 2>&1 | tee "$HERE/chapter-boundary-results.log"
sha256sum -c "$HERE/evidence-before.sha256" | tee "$HERE/source-verification.log"
