#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-prompt-workspace
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
PROBE=docs/delivery/v2-development/prompt-receipt-reopen-origin/origin-probe.py
SAFE=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1)
"${SAFE[@]}" "$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --parent \
  > docs/delivery/v2-development/prompt-receipt-reopen-origin/normal-startup.json \
  2> docs/delivery/v2-development/prompt-receipt-reopen-origin/normal-startup.stderr.log
"${SAFE[@]}" "$PY" scripts/run_v2_checks.py prompt-receipt-reopen-origin-r1 -- python -c \
  'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --child
