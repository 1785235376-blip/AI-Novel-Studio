#!/bin/bash
# New portable helper; this is not a historical execution log.
set -euo pipefail
E=$(cd "$(dirname "$0")" && pwd)
: "${REPO:?Set REPO to the reviewed checkout}"
: "${PYTHON:?Set PYTHON to an existing virtualenv Python executable}"
REPO=$(cd "$REPO" && pwd)
D=$(mktemp -d "${TMPDIR:-/tmp}/adaptation-fixture-rerun.XXXXXX")
mkdir -p "$D"/{home,config,xdg,data,tmp}
export PROJECT_ROOT="$REPO" PYTHONPATH="$REPO:$REPO/tests" PYTHONDONTWRITEBYTECODE=1 HOME="$D/home" XDG_CONFIG_HOME="$D/config" XDG_DATA_HOME="$D/xdg" NOVEL_DATA_PATH="$D/data" TMPDIR="$D/tmp" STORAGE_BACKEND=file MOCK_PROVIDER=true CREDENTIAL_VAULT_BACKEND=memory
unset DATABASE_URL TEST_POSTGRES_DATABASE_URL E2E_DATABASE_URL OPENAI_API_KEY ANTHROPIC_API_KEY DEEPSEEK_API_KEY OPENROUTER_API_KEY GEMINI_API_KEY GOOGLE_API_KEY XAI_API_KEY DASHSCOPE_API_KEY GROQ_API_KEY MISTRAL_API_KEY EXPERIMENTAL_FEATURES V1_ACCEPTANCE_MODE ENABLE_COLLABORATION_RUNTIME ENABLE_PACKAGED_RUNTIME
TESTS=(tests/test_phase7_adaptation_authorization.py tests/test_phase7_adaptation.py)
if [[ "${MODE:-reverse}" == sentinel ]]; then
    export EXPERIMENTAL_FEATURES=adaptation_lifecycle_v1 V1_ACCEPTANCE_MODE=true
    TESTS=(tests/test_phase7_adaptation_authorization.py)
fi
printf 'Fresh runtime and output directory: %s\n' "$D"
cd "$REPO"
"$PYTHON" "$E/independent/run.py" -o "cache_dir=$D/cache" "${TESTS[@]}" -q --junitxml="$D/result.xml" 2>&1 | tee "$D/result.stdout"
