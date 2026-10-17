#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
D=docs/delivery/v2-development/parallel-integration-wave3-20261017
CLEAN=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
"${CLEAN[@]}" "$PY" "$D/check-freeze.py"
test "$(df -Pk . | awk 'NR==2 {print $4}')" -ge 409600
run() { "${CLEAN[@]}" "$PY" scripts/run_v2_checks.py "wave3-independent-$1-r1" -- "${@:2}"; }
case "$1" in
origin)
"${CLEAN[@]}" "$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$D/origin-probe.py" --parent > "$D/independent-natural-startup-r1.json"
run origin-before python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$D/origin-probe.py" --child ;;
backend) run backend python -m pytest tests/test_wave3_pending_director_canvas_bridge.py tests/test_director_durable_pending_review.py tests/test_director_pending_file_races.py tests/test_caption_timing_offset_additive.py tests/test_interactive_removal_handoff.py tests/test_comic_panel_duplicate.py tests/test_caption_history_additive.py tests/test_caption_import_preview_additive.py tests/test_interactive_membership_handoff.py tests/test_post_interop_interactive_history.py tests/test_comic_cover_framing.py tests/test_generation_restart_recovery.py tests/test_v2_graph_director_proposal_loop.py tests/test_v2_storyboard_director_proposal_loop.py -m 'not postgres_backend_only' -q -x -p no:cacheprovider --basetemp="$PWD/.runtime/v2-checks/wave3-independent-backend-r1/pytest" ;;
ui) run ui bash --noprofile --norc -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-file-parallelism --no-cache --bail=1 src/experimental/SubtitleTimelinePanel.offset.test.tsx src/experimental/captionTimingOffset.test.ts src/experimental/SubtitleTimelinePanel.import.test.tsx src/experimental/SubtitleTimelinePanel.history.test.tsx src/experimental/InteractiveStoryPanel.removal.test.tsx src/experimental/interactiveNodeRemoval.test.ts src/experimental/InteractiveStoryPanel.membership.test.tsx src/experimental/InteractiveStoryHistory.test.tsx src/experimental/ComicLayoutsPanel.duplicate.test.tsx src/experimental/comicDuplication.test.ts src/experimental/ComicLayoutsPanel.framing.test.tsx src/experimental/ComicLayoutsPanel.test.tsx src/experimental/comicArrangement.test.ts src/creative/GraphDirectorStoryboardHandoff.test.tsx src/creative/GraphDirectorProposalReview.test.tsx' ;;
origin-after) run origin-after python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$D/origin-probe.py" --child ;;
esac
