#!/bin/bash
set -euo pipefail
ROOT=/workspace/scratch/20a0022d2b33/studio-interactive-removal
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
cd "$ROOT"
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
case "${1:-}" in
origin)
  bash docs/delivery/v2-development/interactive-removal-independent-origin/run-proof.sh
  ;;
file)
  "$PY" scripts/run_v2_checks.py interactive-removal-independent-file-r1 -- python -m pytest -q -p no:cacheprovider --basetemp="$ROOT/.runtime/v2-checks/interactive-removal-independent-file-r1/pytest" -m 'not postgres_backend_only' tests/test_interactive_removal_handoff.py tests/test_interactive_membership_handoff.py tests/test_r5_interactive_story.py tests/test_r5_interactive_story_additive.py tests/test_r5_interactive_story_mounted.py tests/test_post_interop_interactive_history.py
  ;;
ui)
  "$PY" scripts/run_v2_checks.py interactive-removal-independent-ui-r1 -- bash -c 'cd frontend && node node_modules/vitest/vitest.mjs run src/experimental/interactiveNodeRemoval.test.ts src/experimental/InteractiveStoryPanel.removal.test.tsx src/experimental/InteractiveStoryPanel.membership.test.tsx src/experimental/InteractiveStoryPanel.test.tsx src/experimental/InteractiveStoryPanel.additive.test.tsx src/experimental/InteractiveStoryHistory.test.tsx --maxWorkers=1 --minWorkers=1 --no-file-parallelism --no-cache'
  ;;
type)
  "$PY" scripts/run_v2_checks.py interactive-removal-independent-type-r1 -- node frontend/node_modules/typescript/bin/tsc -b frontend/tsconfig.json --force
  ;;
build)
  "$PY" scripts/run_v2_checks.py interactive-removal-independent-build-r1 -- bash -c 'cd frontend && node node_modules/vite/bin/vite.js build'
  ;;
tokens)
  "$PY" scripts/run_v2_checks.py interactive-removal-independent-tokens-r1 -- node scripts/check_ui_design_tokens.mjs
  ;;
*) echo 'Select origin, file, ui, type, build, or tokens' >&2; exit 2;;
esac
