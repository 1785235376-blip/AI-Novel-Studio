#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
"$PY" scripts/run_v2_checks.py waveform-backend-protected-r3 -- python -m pytest tests/test_asset_library.py tests/test_asset_safety.py 'tests/test_r5_voice_subtitles.py::test_measured_waveform_exact_ticks_split_merge_and_export_readback[file]' 'tests/test_r5_voice_subtitles.py::test_actual_audio_change_invalidates_linked_captions_and_only_actual_waveform[file]' tests/test_v2_timeline_selection_handoff.py tests/test_v2_timeline_trim_handoff.py tests/test_v2_timeline_slip_delete_handoff.py tests/test_v2_timeline_asset_handoff.py -m 'not postgres_backend_only' -q -x --basetemp=.runtime/v2-checks/waveform-backend-protected-r3/pytest
