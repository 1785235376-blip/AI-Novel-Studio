#!/bin/bash
set -o pipefail
cd /workspace/scratch/20a0022d2b33/studio-memory-final-port-fences
D="$PWD/.runtime/independent-final-port-review"
mkdir -p "$D/home" "$D/xdg" "$D/data" "$D/tmp" "$D/frozen-source"
cp docs/delivery/evidence/memory-final-port-fences-20261025/targeted-input.sha256 "$D/source-before.sha256"
sha256sum -c "$D/source-before.sha256" > "$D/source-start-verified.txt" || exit 2
while read -r h f; do mkdir -p "$D/frozen-source/$(dirname "$f")"; cp "$f" "$D/frozen-source/$f"; done < "$D/source-before.sha256"
export PATH HOME="$D/home" XDG_DATA_HOME="$D/xdg" NOVEL_DATA_PATH="$D/data" TMPDIR="$D/tmp" PROJECT_ROOT="$PWD" PYTHONPATH="$PWD:$PWD/tests"
PY=../studio-backend-20261025/.venv/bin/python
for modules in 'app.main app.lore.file_memory_ports' 'app.lore.file_memory_ports app.services.lore_service app.main' 'app.repositories.file.lore app.services.generation_service app.main'; do
  env -i PATH="$PATH" HOME="$HOME" XDG_DATA_HOME="$XDG_DATA_HOME" NOVEL_DATA_PATH="$NOVEL_DATA_PATH" TMPDIR="$TMPDIR" PROJECT_ROOT="$PROJECT_ROOT" PYTHONPATH="$PYTHONPATH" "$PY" "$D/cold_import.py" $modules || exit 3
done | tee "$D/cold-import-stdout.txt"
env -i PATH="$PATH" HOME="$HOME" XDG_DATA_HOME="$XDG_DATA_HOME" NOVEL_DATA_PATH="$NOVEL_DATA_PATH" TMPDIR="$TMPDIR" PROJECT_ROOT="$PROJECT_ROOT" PYTHONPATH="$PYTHONPATH" "$PY" -m pytest "$D/test_repaired.py" "$D/test_compatibility.py" -q -s --junitxml="$D/results.xml" 2>&1 | tee "$D/stdout.txt"
status=${PIPESTATUS[0]}
sha256sum -c "$D/source-before.sha256" > "$D/source-verified.txt"
exit "$status"
