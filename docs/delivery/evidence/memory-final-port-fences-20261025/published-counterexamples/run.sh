#!/bin/bash
set -o pipefail
cd /workspace/scratch/20a0022d2b33/studio-file-bound-review
D="$PWD/.runtime/bound-memory-reentrant-review"
mkdir -p "$D/home" "$D/xdg" "$D/data" "$D/tmp" "$D/frozen-source"
files='app/lore/memory_agent.py app/lore/memory_project_binding.py app/repositories/generation_repository.py app/repositories/file/lore.py app/services/lore_service.py app/file_project_lifecycle.py app/creative/project_store.py app/repositories/file/mutation_coordinator.py'
sha256sum $files > "$D/source-before.sha256"
for f in $files; do mkdir -p "$D/frozen-source/$(dirname "$f")"; cp "$f" "$D/frozen-source/$f"; git -C ../studio-backend-20261025 show "5eb983f:$f" | sha256sum; done > "$D/published-source-hashes.txt"
env -i PATH="$PATH" HOME="$D/home" XDG_DATA_HOME="$D/xdg" NOVEL_DATA_PATH="$D/data" TMPDIR="$D/tmp" PROJECT_ROOT="$PWD" PYTHONPATH="$PWD:$PWD/tests" ../studio-backend-20261025/.venv/bin/python -m pytest "$D/test_reentrant.py" -q -s --junitxml="$D/results.xml" 2>&1 | tee "$D/stdout.txt"
status=${PIPESTATUS[0]}
sha256sum -c "$D/source-before.sha256" > "$D/source-verified.txt"
exit "$status"
