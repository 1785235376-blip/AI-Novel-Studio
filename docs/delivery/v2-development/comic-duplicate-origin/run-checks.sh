#!/bin/bash
set -euo pipefail
ROOT=/workspace/scratch/20a0022d2b33/studio-comic-duplicate
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
cd "$ROOT"
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
case "$1" in
file) "$PY" scripts/run_v2_checks.py comic-duplicate-file-r1 -- python -m pytest -q -p no:cacheprovider --basetemp="$ROOT/.runtime/v2-checks/comic-duplicate-file-r1/pytest" -m 'not postgres_backend_only' tests/test_comic_panel_duplicate.py tests/test_comic_cover_framing.py tests/test_r5_comic_layouts.py tests/test_r5_comic_layouts_additive.py tests/test_r5_comic_mounted.py ;;
ui) "$PY" scripts/run_v2_checks.py comic-duplicate-ui-r1 -- bash -c 'cd frontend && node node_modules/vitest/vitest.mjs run src/experimental/comicDuplication.test.ts src/experimental/ComicLayoutsPanel.duplicate.test.tsx src/experimental/comicArrangement.test.ts src/experimental/ComicLayoutsPanel.test.tsx src/experimental/ComicLayoutsPanel.additive.test.tsx src/experimental/ComicLayoutsPanel.framing.test.tsx --maxWorkers=1 --minWorkers=1 --no-file-parallelism --no-cache' ;;
type) "$PY" scripts/run_v2_checks.py comic-duplicate-type-r1 -- node frontend/node_modules/typescript/bin/tsc -b frontend/tsconfig.json --force ;;
build) "$PY" scripts/run_v2_checks.py comic-duplicate-build-r1 -- bash -c 'cd frontend && node node_modules/vite/bin/vite.js build' ;;
tokens) "$PY" scripts/run_v2_checks.py comic-duplicate-tokens-r1 -- node scripts/check_ui_design_tokens.mjs ;;
esac
