#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-selection
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
D=docs/delivery/v2-development/timeline-selection-independent-origin
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
"$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$D/origin-probe.py" --parent > "$D/normal-startup.json" 2> "$D/normal-startup.stderr.log"
"$PY" scripts/run_v2_checks.py timeline-selection-independent-origin-r1 -- python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$D/origin-probe.py" --child
"$PY" scripts/run_v2_checks.py timeline-selection-independent-file-r1 -- python -m pytest tests/test_v2_timeline_selection_handoff.py tests/test_v2_timeline_trim_handoff.py tests/test_v2_timeline_slip_delete_handoff.py tests/test_v2_timeline_asset_handoff.py tests/test_v2_caption_transfer_preflight.py -m 'not postgres_backend_only' -q --basetemp=.runtime/v2-checks/timeline-selection-independent-file-r1/pytest
"$PY" scripts/run_v2_checks.py timeline-selection-independent-ui-r1 -- bash -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-cache src/creative/StudioTimelineSelectionMove.additive.test.tsx src/nle/ClipInspectorSelectionMove.additive.test.tsx src/nle/timelineSelectionMove.additive.test.ts src/creative/StudioTimelineSlipDelete.additive.test.tsx src/creative/StudioTimelineTrim.test.tsx'
