#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
export PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
PROBE=docs/delivery/v2-development/canvas-connect-file-origin/origin-probe.py
"$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --parent > docs/delivery/v2-development/canvas-connect-independent/normal-startup.json
"$PY" scripts/run_v2_checks.py canvas-connect-independent-origin-r1 -- python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --child
"$PY" scripts/run_v2_checks.py canvas-connect-independent-ui-r1 -- bash -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-cache src/creative/GraphCanvas.connection.additive.test.tsx src/creative/StudioGraphConnection.additive.test.tsx src/creative/GraphCanvas.test.tsx src/creative/GraphCanvas.presentation.additive.test.tsx src/creative/graphDraft.test.ts src/creative/graphSelectionCopyController.test.tsx src/creative/GraphReadRevocation.regression.test.tsx src/creative/useStudioGraphEditor.storyboardAuthority.additive.test.tsx'
"$PY" scripts/run_v2_checks.py canvas-connect-independent-file-r1 -- python -m pytest tests/test_v2_creative_graph_persistence.py tests/test_v2_creative_graph_persistence_additive.py tests/test_v2_creative_graph_contracts.py tests/test_v2_graph_schema_version_gate.py -m 'not postgres_backend_only' -q -x --basetemp=.runtime/v2-checks/canvas-connect-independent-file-r1/pytest
