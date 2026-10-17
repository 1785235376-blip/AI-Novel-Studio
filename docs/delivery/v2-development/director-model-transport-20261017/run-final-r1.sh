#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-director-transport
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
BUILD=/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12
D=docs/delivery/v2-development/director-model-transport-20261017
CLEAN=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
run() { "${CLEAN[@]}" "$PY" scripts/run_v2_checks.py "director-model-final-$1-r1" -- "${@:2}"; }
"${CLEAN[@]}" "$PY" -c 'import sys; p=sys.argv[1]; globals()["__file__"]=p; exec(compile(open(p).read(),p,"exec"))' "$D/origin-probe.py" --parent > "$D/natural-startup-r1.json"
run origin-before python -c 'import sys; p=sys.argv[1]; globals()["__file__"]=p; exec(compile(open(p).read(),p,"exec"))' "$D/origin-probe.py" --child
run backend python -m pytest tests/test_director_model_transport_additive.py tests/test_director_observation_transport_additive.py tests/test_director_lifecycle_owner_additive.py tests/test_director_durable_pending_review.py tests/test_director_pending_file_races.py tests/test_v2_creative_foundation.py tests/test_v2_creative_workflows.py tests/test_v2_creative_project_lifecycle.py tests/test_director_model_wire_fixture_additive.py -m 'not postgres_backend_only' -q -x -p no:cacheprovider --basetemp="$PWD/.runtime/v2-checks/director-model-final-backend-r1/pytest"
UI_FILES=(directorModelPlanningContract.additive.test.ts studioProductionGraphClient.test.ts studioStoryboardContract.phase4.test.ts directorObservationClient.test.ts GraphDirectorCanvasHandoff.additive.test.tsx directorCanvasHandoff.additive.test.tsx GraphDirectorProposalReview.test.tsx studioGraphDirectorClient.test.ts)
for file in "${UI_FILES[@]}"; do test -f "frontend/src/creative/$file" || exit 3; done
run ui bash --noprofile --norc -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-file-parallelism --no-cache --bail=1 src/creative/directorModelPlanningContract.additive.test.ts src/creative/studioProductionGraphClient.test.ts src/creative/studioStoryboardContract.phase4.test.ts src/creative/directorObservationClient.test.ts src/creative/GraphDirectorCanvasHandoff.additive.test.tsx src/creative/directorCanvasHandoff.additive.test.tsx src/creative/GraphDirectorProposalReview.test.tsx src/creative/studioGraphDirectorClient.test.ts'
run type bash --noprofile --norc -c 'cd frontend && node node_modules/typescript/bin/tsc -b --force'
run build bash --noprofile --norc -c 'cd frontend && node node_modules/vite/bin/vite.js build'
run token node scripts/check_ui_design_tokens.mjs
available_kib=$(df -Pk . | awk 'NR==2 {print $4}')
(( available_kib >= 512000 )) || { echo 'Insufficient disk; retaining evidence'; exit 4; }
"${CLEAN[@]}" "$BUILD" "$D/packaging-interpreter-probe.py" > "$D/build-interpreter-r1.json"
sha256sum packaging/public-build.json > "$D/manifest-packaging-input-r1.sha256"
"${CLEAN[@]}" PUBLIC_WHEEL_BUILD_PYTHON="$BUILD" PUBLIC_WHEEL_SOURCE="$PWD" PUBLIC_SDIST_SOURCE="$PWD" "$PY" scripts/run_v2_checks.py director-model-packaging-r1 -- python -m pytest tests/test_v2_creative_director_binding_packaging.py tests/test_public_build_profile.py tests/test_public_wheel_artifact.py tests/test_public_sdist_artifact.py -m 'not postgres_backend_only' -q -x -p no:cacheprovider --basetemp="$PWD/.runtime/v2-checks/director-model-packaging-r1/pytest"
sha256sum -c "$D/manifest-packaging-input-r1.sha256"
"${CLEAN[@]}" "$PY" "$D/inspect-artifacts.py" > "$D/actual-artifact-inspection-r1.json"
run origin-after python -c 'import sys; p=sys.argv[1]; globals()["__file__"]=p; exec(compile(open(p).read(),p,"exec"))' "$D/origin-probe.py" --child
