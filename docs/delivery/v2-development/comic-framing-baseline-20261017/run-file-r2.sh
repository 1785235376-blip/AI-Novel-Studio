#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-comic-framing
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
ORIGIN='import sys, PIL, pydantic, app.experimental.comic_layouts as c; print(sys.executable); print(sys.prefix); print(PIL.__version__, PIL.__file__); print(pydantic.__version__, pydantic.__file__); print(c.__file__)'
"$PY" -c "$ORIGIN"
"$PY" scripts/run_v2_checks.py comic-framing-origin-r2 -- python -c "$ORIGIN"
"$PY" scripts/run_v2_checks.py comic-framing-file-r2 -- python -m pytest \
  tests/test_comic_cover_framing.py tests/test_r5_comic_layouts.py tests/test_r5_comic_layouts_additive.py \
  -m 'not postgres_backend_only' -q -x -p no:cacheprovider \
  --basetemp=.runtime/v2-checks/comic-framing-file-r2/pytest
