#!/usr/bin/env bash
set -euo pipefail
cd /workspace/scratch/20a0022d2b33/studio-timeline-waveform
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
D=docs/delivery/v2-development/parallel-integration-independent-20261017
CLEAN=(env -i PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false PYTHON_DOTENV_DISABLED=1 PIP_NO_INDEX=1)
run() { "${CLEAN[@]}" "$PY" scripts/run_v2_checks.py "parallel-integration-independent-$1-r1" -- "${@:2}"; }
[[ "$(git rev-parse HEAD)" == 39ba1c7bc6d8438cc7c7d59f5767ba67f97aca0a ]]
[[ -z "$(git diff HEAD --name-only)" ]]
sha256sum packaging/public-build.json scripts/run_v2_checks.py > "$D/input-guards.sha256"
"${CLEAN[@]}" "$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' docs/delivery/v2-development/parallel-integration-20261017/origin-probe.py --parent > "$D/natural-startup.json"
run origin python -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' docs/delivery/v2-development/parallel-integration-20261017/origin-probe.py --child
run backend python -m pytest tests/test_v2_audio_peak_cpu.py tests/test_v2_audio_peak_contract.py tests/test_v2_audio_peak_api.py tests/test_terminology_portability.py tests/test_r5_multilingual_editions.py tests/test_r5_multilingual_editions_mounted.py tests/test_v2_creative_graph_persistence.py tests/test_v2_creative_graph_persistence_additive.py tests/test_v2_graph_schema_version_gate.py -m 'not postgres_backend_only' -q -x --basetemp="$PWD/.runtime/v2-checks/parallel-integration-independent-backend-r1/pytest"
run ui bash --noprofile --norc -c 'cd frontend && node node_modules/vitest/vitest.mjs run --config vite.config.ts --maxWorkers=1 --minWorkers=1 --no-file-parallelism --no-cache --bail=1 src/creative/GraphCanvas.insertion.additive.test.tsx src/creative/StudioGraphInsertion.additive.test.tsx src/creative/StudioGraphInsertion.palette.additive.test.tsx src/creative/studioAudioPeak.additive.test.tsx src/creative/studioAudioFades.additive.test.tsx src/prompt/PromptWorkspace.receiptReopen.test.tsx src/prompt/promptDraft.settlement.test.ts src/experimental/TerminologyPortabilityPanel.test.tsx'
sha256sum -c "$D/input-guards.sha256"
[[ -z "$(git diff HEAD --name-only)" ]]
