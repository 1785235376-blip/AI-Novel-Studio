#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-director-transport
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
BUILD=/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12
D=docs/delivery/v2-development/director-lifecycle-parent-check-20261017
CLEAN=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
"${CLEAN[@]}" "$PY" -c 'import json,hashlib,pathlib; d=pathlib.Path("docs/delivery/v2-development"); r=json.loads((d/"director-lifecycle-final-origin-after-r1.json").read_text()); assert r["status"]=="PASS"; frozen=json.loads((d/"director-lifecycle-parent-check-20261017/final-frozen-source-r1.json").read_text()); assert all(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h for p,h in frozen.items())'
available_kib=$(df -Pk . | awk 'NR==2 {print $4}')
(( available_kib >= 512000 )) || { echo 'Insufficient disk; retaining evidence'; exit 4; }
"${CLEAN[@]}" "$BUILD" "$D/packaging-interpreter-probe.py" > "$D/build-interpreter-r1.json"
sha256sum packaging/public-build.json > "$D/manifest-packaging-input-r1.sha256"
"${CLEAN[@]}" PUBLIC_WHEEL_BUILD_PYTHON="$BUILD" PUBLIC_WHEEL_SOURCE="$PWD" PUBLIC_SDIST_SOURCE="$PWD" "$PY" scripts/run_v2_checks.py director-lifecycle-packaging-r1 -- python -m pytest tests/test_v2_creative_director_binding_packaging.py tests/test_public_build_profile.py tests/test_public_wheel_artifact.py tests/test_public_sdist_artifact.py -m 'not postgres_backend_only' -q -x -p no:cacheprovider --basetemp="$PWD/.runtime/v2-checks/director-lifecycle-packaging-r1/pytest"
sha256sum -c "$D/manifest-packaging-input-r1.sha256"
"${CLEAN[@]}" "$PY" "$D/inspect-artifacts.py" > "$D/actual-artifact-inspection-r1.json"
