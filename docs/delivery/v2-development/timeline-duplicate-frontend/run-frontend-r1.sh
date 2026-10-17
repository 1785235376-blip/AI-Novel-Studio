#!/usr/bin/env bash
# Prepared launcher. Execute only after parent serial verification release.
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
E=docs/delivery/v2-development
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
case "${1:?stage: ui, type, build, token}" in
ui)
  "$PY" scripts/run_v2_checks.py timeline-duplicate-ui-r1 -- bash -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-cache src/creative/StudioTimelineSelectionDuplicate.additive.test.tsx src/nle/ClipInspectorSelectionDuplicate.additive.test.tsx src/nle/timelineSelectionDuplicate.additive.test.ts src/creative/StudioTimelineSelectionMove.additive.test.tsx src/nle/ClipInspectorSelectionMove.additive.test.tsx src/nle/timelineSelectionMove.additive.test.ts src/creative/StudioTimelineSlipDelete.additive.test.tsx src/nle/ClipInspectorSlipDelete.additive.test.tsx src/creative/StudioTimelineTrim.test.tsx src/nle/nlePanels.test.tsx src/nle/timelineOps.test.ts src/creative/ProductionTimeline.test.tsx src/creative/TimelineSourceEditing.phase6.test.tsx src/creative/StudioTimelineAssetHandoff.test.tsx src/ui/AppShell.test.tsx src/ui/primitives.test.tsx'
  ;;
type) "$PY" scripts/run_v2_checks.py timeline-duplicate-type-r1 -- bash -c 'cd frontend && node node_modules/typescript/bin/tsc -b --force' ;;
build) "$PY" scripts/run_v2_checks.py timeline-duplicate-build-r1 -- bash -c 'cd frontend && node node_modules/vite/bin/vite.js build' ;;
token) "$PY" scripts/run_v2_checks.py timeline-duplicate-token-r1 -- node scripts/check_ui_design_tokens.mjs ;;
*) echo 'Unknown stage' >&2; exit 2 ;;
esac
