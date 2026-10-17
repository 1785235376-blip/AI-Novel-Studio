#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
BUILD=/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12
D=docs/delivery/v2-development/waveform-packaging
PROBE=docs/delivery/v2-development/waveform-origin-backend/origin-probe-r3.py
CLEAN=(env -i PATH=/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
"${CLEAN[@]}" "$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --parent > "$D/natural-startup-r1.json" 2> "$D/natural-startup-r1.stderr.log"
"${CLEAN[@]}" "$BUILD" "$D/packaging-interpreter-probe.py" > "$D/build-interpreter-r1.json"
"${CLEAN[@]}" "$PY" scripts/run_v2_checks.py waveform-packaging-origin-before-r1 -- python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --child
sha256sum packaging/public-build.json > "$D/manifest-packaging-input-r1.sha256"
set +e
"${CLEAN[@]}" PUBLIC_WHEEL_BUILD_PYTHON="$BUILD" PUBLIC_WHEEL_SOURCE="$PWD" PUBLIC_SDIST_SOURCE="$PWD" "$PY" scripts/run_v2_checks.py waveform-packaging-r1 -- python -m pytest tests/test_v2_creative_director_binding_packaging.py tests/test_public_build_profile.py tests/test_public_wheel_artifact.py tests/test_public_sdist_artifact.py -m 'not postgres_backend_only' -q -x --basetemp="$PWD/.runtime/v2-checks/waveform-packaging-r1/pytest"
STATUS=$?
set -e
sha256sum -c "$D/manifest-packaging-input-r1.sha256"
if (( STATUS != 0 )); then exit "$STATUS"; fi
"${CLEAN[@]}" "$PY" scripts/run_v2_checks.py waveform-packaging-origin-after-r1 -- python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --child
