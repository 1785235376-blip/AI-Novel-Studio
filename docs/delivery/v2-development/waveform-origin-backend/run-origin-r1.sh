#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
PROBE=docs/delivery/v2-development/waveform-origin-backend/origin-probe-r1.py
"$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --parent > docs/delivery/v2-development/waveform-origin-backend/normal-startup-r1.json 2> docs/delivery/v2-development/waveform-origin-backend/normal-startup-r1.stderr.log
"$PY" scripts/run_v2_checks.py waveform-origin-backend-r1 -- python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' "$PROBE" --child
