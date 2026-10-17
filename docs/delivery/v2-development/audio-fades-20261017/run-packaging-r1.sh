#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-audio-fades
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
BUILD=/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12
D=docs/delivery/v2-development/audio-fades-20261017
CLEAN=(env -i PATH=/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
"${CLEAN[@]}" "$PY" -c 'import sys,os,site,json; print(json.dumps({"cwd":os.getcwd(),"executable":sys.executable,"sys_path":sys.path,"user_site":site.ENABLE_USER_SITE},indent=2))' > "$D/packaging-natural-startup.json"
"${CLEAN[@]}" "$BUILD" docs/delivery/v2-development/director-review-origin/packaging-interpreter-probe.py > "$D/packaging-build-interpreter.json"
"${CLEAN[@]}" "$PY" scripts/run_v2_checks.py audio-fades-packaging-origin-before -- python "$D/origin/origin-probe.py" --child
sha256sum packaging/public-build.json > "$D/packaging-manifest-before.sha256"
set +e
"${CLEAN[@]}" PUBLIC_WHEEL_BUILD_PYTHON="$BUILD" PUBLIC_WHEEL_SOURCE="$PWD" PUBLIC_SDIST_SOURCE="$PWD" "$PY" scripts/run_v2_checks.py audio-fades-packaging-r1 -- python -m pytest tests/test_v2_creative_director_binding_packaging.py tests/test_public_build_profile.py tests/test_public_wheel_artifact.py tests/test_public_sdist_artifact.py -m 'not postgres_backend_only' -q --basetemp="$PWD/.runtime/v2-checks/audio-fades-packaging-r1/pytest"
STATUS=$?
set -e
sha256sum -c "$D/packaging-manifest-before.sha256"
"${CLEAN[@]}" "$PY" scripts/run_v2_checks.py audio-fades-packaging-origin-after -- python "$D/origin/origin-probe.py" --child
exit "$STATUS"
