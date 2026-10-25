#!/bin/bash
set -uo pipefail
source .runtime/activate-backend.sh
RUN="$PWD/.runtime/integrated-worker-review"
export HOME="$RUN/home" APPDATA="$RUN/appdata" LOCALAPPDATA="$RUN/localappdata"
export XDG_CONFIG_HOME="$RUN/config" XDG_CACHE_HOME="$RUN/cache" XDG_DATA_HOME="$RUN/xdg-data" XDG_STATE_HOME="$RUN/state" XDG_RUNTIME_DIR="$RUN/xdg-run"
export NOVEL_DATA_PATH="$RUN/data" TMPDIR="$RUN/tmp" TMP="$RUN/tmp" TEMP="$RUN/tmp"
mkdir -p "$HOME" "$APPDATA" "$LOCALAPPDATA" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME" "$XDG_RUNTIME_DIR" "$NOVEL_DATA_PATH" "$TMPDIR"
export PYTHONPATH="$PWD:$PWD/tests" PROJECT_ROOT="$PWD" CREDENTIAL_VAULT_BACKEND=memory
export ENABLE_CLOUD=false ENABLE_CLOUD_FALLBACK=false MOCK_PROVIDER=true STORAGE_BACKEND=file CREATION_PROFILE=LOCAL_ONLY
sha256sum app/jobs.py app/api.py app/idempotency.py app/services/generation_admission_receipt.py tests/test_generation_worker_authority.py tests/test_generation_admission_receipts.py tests/test_generation_idempotency_contracts.py > "$RUN/before.sha256"
python "$RUN/run_tests.py" -q "$RUN/test_replay_refusal.py" --junitxml="$RUN/results.xml" -o cache_dir="$RUN/pytest-cache" > "$RUN/pytest.log" 2>&1
result=$?
echo "$result" > "$RUN/exit.txt"
sha256sum -c "$RUN/before.sha256" > "$RUN/after.log"
cat "$RUN/pytest.log"
exit "$result"
