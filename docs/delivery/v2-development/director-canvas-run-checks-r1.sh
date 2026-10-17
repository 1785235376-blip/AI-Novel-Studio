#!/usr/bin/env bash
source /workspace/scratch/20a0022d2b33/director-canvas-handoff-verification-r1/environment.sh
"$PY" scripts/run_v2_checks.py director-canvas-type-build-r1 -- bash -c 'set -e; cd frontend; /opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node node_modules/typescript/bin/tsc -b --force; /opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node node_modules/vite/bin/vite.js build'
"$PY" scripts/run_v2_checks.py director-canvas-tokens-r1 -- "$NODE" scripts/check_ui_design_tokens.mjs
"$PY" scripts/run_v2_checks.py director-canvas-public-r1 -- python scripts/public_build.py --source .
"$PY" scripts/run_v2_checks.py director-canvas-diff-r1 -- git diff --check
