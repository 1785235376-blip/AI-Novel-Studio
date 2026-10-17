#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-prompt-workspace
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 \
  "$PY" scripts/run_v2_checks.py prompt-receipt-reopen-ui-r1 -- bash -c \
  'cd frontend && node node_modules/vitest/vitest.mjs run src/prompt --maxWorkers=1 --minWorkers=1 --no-file-parallelism --no-cache'
