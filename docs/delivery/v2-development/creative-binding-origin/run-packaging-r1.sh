#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-creative-binding
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE PYTEST_ADDOPTS PYTEST_PLUGINS
unset PACKAGED_RUNTIME_INSTANCE_ID PACKAGED_BOOTSTRAP_SECRET PACKAGED_CONTROL_PIPE
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL COLLABORATION_DEV_SESSIONS_JSON
unset PROMPT_PATH
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1
export PUBLIC_WHEEL_BUILD_PYTHON=/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12
export PUBLIC_WHEEL_SOURCE=/workspace/scratch/20a0022d2b33/studio-creative-binding
export PUBLIC_SDIST_SOURCE=/workspace/scratch/20a0022d2b33/studio-creative-binding
sha256sum packaging/public-build.json > docs/delivery/v2-development/creative-binding-origin/packaging-manifest-before.sha256
"$PY" scripts/run_v2_checks.py creative-binding-packaging-r1 -- python -m pytest \
 tests/test_v2_creative_director_binding_packaging.py tests/test_public_build_profile.py \
 tests/test_public_wheel_artifact.py tests/test_public_sdist_artifact.py \
 -m 'not postgres_backend_only' -q --basetemp=.runtime/creative-binding-packaging-r1-pytest
sha256sum -c docs/delivery/v2-development/creative-binding-origin/packaging-manifest-before.sha256
