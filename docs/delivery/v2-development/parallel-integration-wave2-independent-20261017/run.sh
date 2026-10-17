#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
D=docs/delivery/v2-development/parallel-integration-wave2-independent-20261017
P=docs/delivery/v2-development/parallel-integration-wave2-20261017
CLEAN=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
run() { "${CLEAN[@]}" "$PY" scripts/run_v2_checks.py "wave2-independent-$1-r1" -- "${@:2}"; }
"${CLEAN[@]}" "$PY" "$P/check-freeze.py" > "$D/freeze-before.json"
"${CLEAN[@]}" "$PY" -c 'import sys; p=sys.argv[1]; globals()["__file__"]=p; exec(compile(open(p).read(),p,"exec"))' "$P/origin-probe.py" --parent > "$D/natural-startup.json"
run origin-before python -c 'import sys; p=sys.argv[1]; globals()["__file__"]=p; exec(compile(open(p).read(),p,"exec"))' "$P/origin-probe.py" --child > "$D/origin-before-launch.log"
run backend python -m pytest tests/test_wave2_generation_backup_restore_additive.py tests/test_director_terminal_evidence_contract.py tests/test_director_private_publication_races.py tests/test_v2_creative_director_binding_persistence.py tests/test_generation_restart_recovery.py tests/test_interactive_membership_handoff.py tests/test_post_interop_interactive_history.py tests/test_comic_cover_framing.py tests/test_r5_comic_layouts.py tests/test_r5_comic_layouts_additive.py tests/test_restored_file_verification.py tests/test_r2_backup_restore.py -m 'not postgres_backend_only' -q -x -p no:cacheprovider --basetemp="$PWD/.runtime/v2-checks/wave2-independent-backend-r1/pytest" > "$D/backend-launch.log" 2>&1
run comic-golden python docs/delivery/v2-development/comic-framing-baseline-20261017/verify_legacy_portable.py --source "$PWD" --work "$PWD/.runtime/v2-checks/wave2-independent-comic-golden-r1/copied-state" > "$D/comic-golden-launch.log" 2>&1
run ui bash --noprofile --norc -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-file-parallelism --no-cache --bail=1 src/experimental/InteractiveStoryPanel.membership.test.tsx src/experimental/InteractiveStoryPanel.test.tsx src/experimental/InteractiveStoryPanel.additive.test.tsx src/experimental/InteractiveStoryHistory.test.tsx src/experimental/ComicLayoutsPanel.framing.test.tsx src/experimental/ComicLayoutsPanel.test.tsx src/experimental/ComicLayoutsPanel.additive.test.tsx src/experimental/comicArrangement.test.ts src/creative/DirectorModelControls.test.tsx src/creative/DirectorModelControls.storyboard-model.additive.test.tsx src/creative/GraphDirectorProposalReview.test.tsx' > "$D/ui-launch.log" 2>&1
run origin-after python -c 'import sys; p=sys.argv[1]; globals()["__file__"]=p; exec(compile(open(p).read(),p,"exec"))' "$P/origin-probe.py" --child > "$D/origin-after-launch.log"
"${CLEAN[@]}" "$PY" "$P/check-freeze.py" > "$D/freeze-after.json"
echo INDEPENDENT_GATES_PASS
