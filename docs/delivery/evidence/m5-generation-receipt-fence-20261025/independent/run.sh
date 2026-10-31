#!/bin/bash
set -o pipefail
R=/workspace/scratch/20a0022d2b33/review-m5-receipt-independent
W=${REVIEW_TARGET:-/workspace/scratch/20a0022d2b33/studio-m5-receipt-fence}
mkdir -p "$R/home" "$R/data" "$R/tmp" "$R/xdg"
export PYTHONDONTWRITEBYTECODE=1 HOME="$R/home" XDG_CONFIG_HOME="$R/xdg" XDG_DATA_HOME="$R/xdg" NOVEL_DATA="$R/data" TMPDIR="$R/tmp" STORAGE_BACKEND=file MOCK_PROVIDER=true CREDENTIAL_VAULT_BACKEND=memory
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL OPENAI_API_KEY ANTHROPIC_API_KEY DEEPSEEK_API_KEY
printf '%q ' /workspace/scratch/20a0022d2b33/studio-backend-20261025/.venv/bin/python "$R/run.py" "$@"; echo
STAMP=$(date -u +%Y%m%dT%H%M%S%N)
cd "$W"
git diff > "$R/$STAMP.patch"
tar -czf "$R/$STAMP-source.tar.gz" app tests/test_file_local_bound_review.py 2>/dev/null
git rev-parse HEAD; git status --short
find app -name '*.py' -print0 | sort -z | xargs -0 sha256sum > "$R/$STAMP-source-before.sha256"
/workspace/scratch/20a0022d2b33/studio-backend-20261025/.venv/bin/python "$R/run.py" "$@"
code=$?
find app -name '*.py' -print0 | sort -z | xargs -0 sha256sum > "$R/$STAMP-source-after.sha256"
exit $code
