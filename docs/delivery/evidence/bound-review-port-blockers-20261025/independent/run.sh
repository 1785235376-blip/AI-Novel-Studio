#!/bin/bash
set -o pipefail
cd /workspace/scratch/20a0022d2b33/studio-file-bound-review
D="$PWD/.runtime/bound-memory-independent"
mkdir -p "$D/home" "$D/xdg" "$D/data" "$D/tmp"
sha256sum app/lore/memory_agent.py app/lore/memory_project_binding.py app/repositories/generation_repository.py app/repositories/postgres/generation.py app/services/generation_project_binding.py app/jobs.py > "$D/source-before.sha256"
env -i PATH="$PATH" HOME="$D/home" XDG_DATA_HOME="$D/xdg" NOVEL_DATA_PATH="$D/data" TMPDIR="$D/tmp" PROJECT_ROOT="$PWD" PYTHONPATH="$PWD:$PWD/tests" ../studio-backend-20261025/.venv/bin/python -m pytest "$D/test_independent.py" -q --junitxml="$D/results.xml" 2>&1 | tee "$D/stdout.txt"
status=${PIPESTATUS[0]}
sha256sum -c "$D/source-before.sha256" > "$D/source-verified.txt"
exit "$status"
