#!/usr/bin/env bash
# Prepared launcher. Execute only after parent serial verification release.
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
NODE=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node
export PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin
E=docs/delivery/v2-development
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
case "${1:?stage: ui, type, build, token}" in
ui)
  "$PY" scripts/run_v2_checks.py canvas-insert-ui-r2 -- bash -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-cache src/creative/GraphCanvas.insertion.additive.test.tsx src/creative/StudioGraphInsertion.additive.test.tsx src/creative/StudioGraphInsertion.palette.additive.test.tsx src/creative/GraphCanvas.connection.additive.test.tsx src/creative/StudioGraphConnection.additive.test.tsx src/creative/GraphCanvas.test.tsx src/creative/GraphCanvas.presentation.additive.test.tsx src/creative/GraphCanvasLargeNotes.test.tsx src/creative/graphCanvasGeometry.test.ts src/creative/graphCanvasGeometry.presentation.additive.test.ts src/creative/graphCanvasPresentation.test.ts src/creative/graphCanvasNotes.test.ts src/creative/graphCanvasLargeNotes.test.ts src/creative/GraphNodeNavigator.test.tsx src/creative/graphDraft.test.ts src/creative/graphSelectionCopyController.test.tsx src/creative/StudioGraphDraftRecovery.test.tsx src/creative/StudioGraphDraftRecovery.notes.test.tsx src/creative/studioGraphLocalDraft.test.ts src/creative/IndependentStudioGraphWorkspace.test.tsx src/creative/IndependentStudioGraphWorkspace.presentation.additive.test.tsx src/creative/GraphReadRevocation.regression.test.tsx src/creative/useStudioGraphEditor.storyboardAuthority.additive.test.tsx src/canvasops/canvasOps.test.ts src/canvasops/canvasOps.layout.additive.test.ts src/canvasops/canvasOpsPanels.test.tsx src/canvasops/canvasOpsPanels.layout.additive.test.tsx src/ui/AppShell.test.tsx src/ui/primitives.test.tsx'
  ;;
type) "$PY" scripts/run_v2_checks.py canvas-insert-type-r2 -- bash -c 'cd frontend && node node_modules/typescript/bin/tsc -b --force' ;;
build) "$PY" scripts/run_v2_checks.py canvas-insert-build-r2 -- bash -c 'cd frontend && node node_modules/vite/bin/vite.js build' ;;
token) "$PY" scripts/run_v2_checks.py canvas-insert-token-r2 -- "$NODE" scripts/check_ui_design_tokens.mjs ;;
*) echo 'Unknown stage' >&2; exit 2 ;;
esac
