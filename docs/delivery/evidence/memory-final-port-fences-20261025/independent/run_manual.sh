#!/bin/bash
set -o pipefail
cd /workspace/scratch/20a0022d2b33/studio-memory-final-port-fences
D="$PWD/.runtime/independent-final-port-review"
env -i PATH="$PATH" HOME="$D/home" XDG_DATA_HOME="$D/xdg" NOVEL_DATA_PATH="$D/data" TMPDIR="$D/tmp" PROJECT_ROOT="$PWD" PYTHONPATH="$PWD:$PWD/tests" ../studio-backend-20261025/.venv/bin/python -m pytest "$D/test_manual_composition.py" -q --junitxml="$D/manual-results.xml" 2>&1 | tee "$D/manual-stdout.txt"
status=${PIPESTATUS[0]}
sha256sum -c "$D/source-before.sha256" > "$D/manual-source-verified.txt"
exit "$status"
