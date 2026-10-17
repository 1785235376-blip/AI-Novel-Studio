#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-director-transport
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
CLEAN=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
run() { "${CLEAN[@]}" "$PY" scripts/run_v2_checks.py "director-observation-client-$1-r1" -- "${@:2}"; }
run regression bash --noprofile --norc -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-file-parallelism --no-cache --bail=1 src/creative/directorObservationClient.test.ts src/creative/studioGraphDirectorClient.test.ts src/creative/directorCanvasHandoff.test.ts src/creative/GraphDirectorProposalReview.test.tsx'
run type bash --noprofile --norc -c 'cd frontend && node node_modules/typescript/bin/tsc -b --force'
run build bash --noprofile --norc -c 'cd frontend && node node_modules/vite/bin/vite.js build'
run token node scripts/check_ui_design_tokens.mjs
