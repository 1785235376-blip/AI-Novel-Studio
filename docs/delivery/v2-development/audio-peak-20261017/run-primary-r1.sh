#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-audio-normalize
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
NODE=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node
D=docs/delivery/v2-development/audio-peak-20261017
CLEAN=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
"${CLEAN[@]}" "$PY" -c 'import sys,os,site,json; print(json.dumps({"cwd":os.getcwd(),"executable":sys.executable,"sys_path":sys.path,"user_site":site.ENABLE_USER_SITE},indent=2))' > "$D/primary-natural-startup-r1.json"
"${CLEAN[@]}" "$PY" scripts/run_v2_checks.py audio-peak-primary-origin-before-r1 -- python "$D/origin/origin-probe.py" --child
"${CLEAN[@]}" "$PY" scripts/run_v2_checks.py audio-peak-new-backend-r1 -- python -m pytest tests/test_v2_audio_peak_contract.py tests/test_v2_audio_peak_api.py tests/test_v2_audio_peak_cpu.py -m 'not postgres_backend_only' -q --basetemp="$PWD/.runtime/v2-checks/audio-peak-new-backend-r1/pytest"
"${CLEAN[@]}" "$PY" scripts/run_v2_checks.py audio-peak-primary-origin-after-r1 -- python "$D/origin/origin-probe.py" --child
