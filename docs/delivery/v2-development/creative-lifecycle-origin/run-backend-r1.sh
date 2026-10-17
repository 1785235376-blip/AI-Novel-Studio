#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-creative-lifecycle
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
PROBE=docs/delivery/v2-development/creative-lifecycle-origin/origin-probe.py
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
unset PROMPT_PATH PUBLIC_WHEEL_BUILD_PYTHON PUBLIC_WHEEL_SOURCE PUBLIC_SDIST_SOURCE
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1
"$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --parent > docs/delivery/v2-development/creative-lifecycle-origin/backend-normal-startup-r1.json 2> docs/delivery/v2-development/creative-lifecycle-origin/backend-normal-startup-r1.stderr.log
"$PY" scripts/run_v2_checks.py creative-lifecycle-origin-r2 -- python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --child
"$PY" scripts/run_v2_checks.py creative-lifecycle-backend-r1 -- python -m pytest \
 tests/test_v2_creative_director_invocation.py tests/test_v2_creative_director_execution_lifecycle.py \
 tests/test_v2_creative_director_binding.py tests/test_v2_creative_director_binding_persistence.py \
 tests/test_v2_model_execution.py tests/test_v2_generation_incarnation.py \
 tests/test_shared_generation_terminal_protocol.py tests/test_r4_generation_origin_guards.py \
 tests/test_r4_generation_origin_regression.py tests/test_r4_broker_cancel_dispatch.py \
 tests/test_r4_model_broker.py tests/test_r4_broker_mounted.py tests/test_v2_source_adaptation.py tests/test_v2_storyboard_model_contract.py \
 -m 'not postgres_backend_only' -q --basetemp=.runtime/creative-lifecycle-backend-r1-pytest
