#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
"$PY" scripts/run_v2_checks.py waveform-backend-additive-r2 -- python -m pytest tests/test_pcm16_envelope_additive.py tests/test_asset_bounded_content_additive.py tests/test_v2_timeline_waveform_preview.py tests/test_v2_timeline_waveform_preview_api.py -m 'not postgres_backend_only' -q -x --basetemp=.runtime/v2-checks/waveform-backend-additive-r2/pytest
