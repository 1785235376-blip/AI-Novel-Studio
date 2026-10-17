#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-director-transport
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
D=docs/delivery/v2-development/director-lifecycle-parent-check-20261017
CLEAN=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
run() { "${CLEAN[@]}" "$PY" scripts/run_v2_checks.py "director-lifecycle-final-$1-r1" -- "${@:2}"; }
"${CLEAN[@]}" "$PY" -c 'import sys; p=sys.argv[1]; globals()["__file__"]=p; exec(compile(open(p).read(),p,"exec"))' "$D/origin-probe.py" --parent > "$D/final-natural-r1.json"
run origin-before python -c 'import sys; p=sys.argv[1]; globals()["__file__"]=p; exec(compile(open(p).read(),p,"exec"))' "$D/origin-probe.py" --child
run backend python -m pytest tests/test_director_lifecycle_owner_additive.py tests/test_director_durable_pending_review.py tests/test_director_pending_file_races.py tests/test_director_terminal_evidence_contract.py tests/test_director_private_publication_races.py tests/test_v2_creative_director_execution_lifecycle.py tests/test_v2_creative_director_invocation.py tests/test_v2_creative_director_binding.py tests/test_v2_creative_director_binding_persistence.py tests/test_v2_creative_director_review_contract.py tests/test_v2_independent_director_adoption.py tests/test_generation_restart_recovery.py tests/test_v2_generation_incarnation.py tests/test_v2_creative_graph_execution.py tests/test_v2_graph_director_proposal_loop.py tests/test_v2_storyboard_director_proposal_loop.py tests/test_a43_detached_generation_acceptance.py tests/test_repository_contracts.py::test_generation_contract tests/test_stability_v04.py::test_job_repository_survives_new_instance tests/test_generation_snapshot_runtime_v056.py -m 'not postgres_backend_only' -q -x -p no:cacheprovider --basetemp="$PWD/.runtime/v2-checks/director-lifecycle-final-backend-r1/pytest"
run type bash --noprofile --norc -c 'cd frontend && node node_modules/typescript/bin/tsc -b --force'
run build bash --noprofile --norc -c 'cd frontend && node node_modules/vite/bin/vite.js build'
run token node scripts/check_ui_design_tokens.mjs
run origin-after python -c 'import sys; p=sys.argv[1]; globals()["__file__"]=p; exec(compile(open(p).read(),p,"exec"))' "$D/origin-probe.py" --child
