#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-comic-duplicate
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
PROBE=docs/delivery/v2-development/comic-duplicate-origin/origin-comic-probe.py
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
"$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --parent \
  > docs/delivery/v2-development/comic-duplicate-origin/normal-startup-final-after-r2.json \
  2> docs/delivery/v2-development/comic-duplicate-origin/normal-startup-final-after-r2.stderr.log
"$PY" scripts/run_v2_checks.py comic-duplicate-origin-final-after-r2 -- python -c \
  'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --child
