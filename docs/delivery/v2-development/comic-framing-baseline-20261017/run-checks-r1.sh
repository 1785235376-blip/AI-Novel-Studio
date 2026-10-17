#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-comic-framing
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
"$PY" scripts/run_v2_checks.py comic-framing-type-build-r1 -- bash -c 'set -e; cd frontend; node node_modules/typescript/bin/tsc -b --force; node node_modules/vite/bin/vite.js build'
"$PY" scripts/run_v2_checks.py comic-framing-tokens-r1 -- node scripts/check_ui_design_tokens.mjs
"$PY" scripts/run_v2_checks.py comic-framing-public-r1 -- python scripts/public_build.py --source .
"$PY" scripts/run_v2_checks.py comic-framing-diff-r1 -- git diff --check
