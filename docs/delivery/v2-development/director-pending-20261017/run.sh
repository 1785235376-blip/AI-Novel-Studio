#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-director-pending
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
BUILD=/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12
D=docs/delivery/v2-development/director-pending-20261017
CLEAN=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
REV=${2:-r1}
run() { "${CLEAN[@]}" "$PY" scripts/run_v2_checks.py "director-pending-$1-$REV" -- "${@:2}"; }
case "${1:?stage}" in
origin)
  "${CLEAN[@]}" "$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$D/origin-probe.py" --parent > "$D/natural-startup-$REV.json"
  run origin-before python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$D/origin-probe.py" --child ;;
new) run new python -m pytest tests/test_director_durable_pending_review.py tests/test_director_pending_file_races.py -m 'not postgres_backend_only' -q -x -p no:cacheprovider --basetemp="$PWD/.runtime/v2-checks/director-pending-new-$REV/pytest" ;;
regression) run regression python -m pytest tests/test_director_terminal_evidence_contract.py tests/test_director_private_publication_races.py tests/test_v2_creative_director_execution_lifecycle.py tests/test_v2_creative_director_invocation.py tests/test_v2_creative_director_binding.py tests/test_v2_creative_director_binding_persistence.py tests/test_v2_creative_director_review_contract.py tests/test_v2_independent_director_adoption.py tests/test_generation_restart_recovery.py tests/test_v2_generation_incarnation.py tests/test_v2_creative_graph_execution.py tests/test_v2_graph_director_proposal_loop.py tests/test_v2_storyboard_director_proposal_loop.py tests/test_a43_detached_generation_acceptance.py tests/test_repository_contracts.py::test_generation_contract tests/test_stability_v04.py::test_job_repository_survives_new_instance tests/test_generation_snapshot_runtime_v056.py -m 'not postgres_backend_only' -q -x -p no:cacheprovider --basetemp="$PWD/.runtime/v2-checks/director-pending-regression-$REV/pytest" ;;
ui) run ui bash --noprofile --norc -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-file-parallelism --no-cache --bail=1 src/creative/DirectorModelControls.test.tsx src/creative/DirectorModelControls.storyboard-model.additive.test.tsx src/creative/GraphDirectorStoryboardHandoff.test.tsx src/creative/GraphDirectorProposalReview.test.tsx src/creative/GraphModelExecutionPanel.test.tsx src/creative/studioGraphDirectorClient.test.ts' ;;
type) run type bash --noprofile --norc -c 'cd frontend && node node_modules/typescript/bin/tsc -b --force' ;;
build) run build bash --noprofile --norc -c 'cd frontend && node node_modules/vite/bin/vite.js build' ;;
token) run token node scripts/check_ui_design_tokens.mjs ;;
packaging)
  "${CLEAN[@]}" "$BUILD" "$D/packaging-interpreter-probe.py" > "$D/build-interpreter-$REV.json"
  sha256sum packaging/public-build.json > "$D/manifest-input-$REV.sha256"
  "${CLEAN[@]}" PUBLIC_WHEEL_BUILD_PYTHON="$BUILD" PUBLIC_WHEEL_SOURCE="$PWD" PUBLIC_SDIST_SOURCE="$PWD" "$PY" scripts/run_v2_checks.py "director-pending-packaging-$REV" -- python -m pytest tests/test_v2_creative_director_binding_packaging.py tests/test_public_build_profile.py tests/test_public_wheel_artifact.py tests/test_public_sdist_artifact.py -m 'not postgres_backend_only' -q -x -p no:cacheprovider --basetemp="$PWD/.runtime/v2-checks/director-pending-packaging-$REV/pytest"
  sha256sum -c "$D/manifest-input-$REV.sha256" ;;
origin-after) run origin-after python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$D/origin-probe.py" --child ;;
*) exit 2 ;;
esac
