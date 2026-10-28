#!/bin/bash
cd /workspace/scratch/20a0022d2b33/text-artifact-publicbase-final
export PROJECT_ROOT="$PWD" LOCALAPPDATA="$PWD/.runtime/localapp" XDG_DATA_HOME="$PWD/.runtime/xdg" NOVEL_DATA="$PWD/.runtime/data" STORAGE_BACKEND=file PYTHONPATH="$PWD"
PY=/workspace/scratch/20a0022d2b33/studio-overnight/.venv/bin/python
E=/workspace/scratch/20a0022d2b33/text-artifact-publicbase-evidence
for name in final-artifact final-regression; do
 if [ "$name" = final-artifact ]; then args=(tests/test_export_artifact_recovery_generator.py); else args=(tests/test_export*.py tests/test_docx_export.py tests/test_pdf_export.py); fi
 timeout 1200 "$PY" "$E/run_frozen.py" "$name" "${args[@]}" --basetemp="$PWD/.runtime/$name" > "$E/$name.log" 2>&1
 ec=$?;echo "$ec" > "$E/$name-exit.txt";tail -2 "$E/$name.log";echo "$name exit=$ec"
done
