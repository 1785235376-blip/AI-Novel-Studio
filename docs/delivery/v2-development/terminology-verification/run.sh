#!/bin/bash
set -euo pipefail
ROOT=/workspace/scratch/20a0022d2b33/studio-terminology-portability
PY=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python
cd "$ROOT"
if [[ ${TERMINOLOGY_CLEAN_LAUNCH:-} != 1 ]]; then
  exec env -i PATH="$PATH" HOME="$ROOT/.runtime/terminology-portability-runner/home" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PACKAGED_WINDOWS_MODE=false \
    TERMINOLOGY_CLEAN_LAUNCH=1 /bin/bash --noprofile --norc "$0" "$@"
fi
phase=${1:?phase required}; revision=${2:-r1}; label="terminology-${phase}-${revision}"
runner=("$PY" scripts/run_v2_checks.py "$label" --)
case "$phase" in
  origin)
    "$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' .runtime/terminology-portability-runner/origin-probe.py --parent > ".runtime/terminology-portability-runner/outer-origin-${revision}.json"
    "${runner[@]}" "$PY" -c 'import sys; path=sys.argv[1]; globals()["__file__"]=path; exec(compile(open(path).read(),path,"exec"))' .runtime/terminology-portability-runner/origin-probe.py --child
    ;;
  owner) "${runner[@]}" "$PY" -m pytest tests/test_terminology_portability.py -q -m 'not postgres_backend_only' --basetemp "$ROOT/.runtime/terminology-portability-runner/${label}-tmp" ;;
  regression) "${runner[@]}" "$PY" -m pytest tests/test_r5_multilingual_editions.py tests/test_r5_multilingual_editions_mounted.py tests/test_r5_multilingual_translation.py -q -m 'not postgres_backend_only' --basetemp "$ROOT/.runtime/terminology-portability-runner/${label}-tmp" ;;
  ui) "${runner[@]}" /bin/bash --noprofile --norc -c 'cd frontend && node node_modules/vitest/vitest.mjs run src/experimental/TerminologyPortabilityPanel.test.tsx src/experimental/MultilingualEditionsPanel.test.tsx src/experimental/MultilingualEditionsPanel.additive.test.tsx src/experimental/TerminologyIssueNavigator.test.tsx src/experimental/LanguageTranslationPanel.test.tsx src/experimental/TranslationMemoryPanel.test.tsx --maxWorkers=1 --minWorkers=1' ;;
  type) "${runner[@]}" /bin/bash --noprofile --norc -c 'cd frontend && node node_modules/typescript/bin/tsc -b --force' ;;
  build) "${runner[@]}" /bin/bash --noprofile --norc -c 'cd frontend && node node_modules/vite/bin/vite.js build' ;;
  token) "${runner[@]}" node scripts/check_ui_design_tokens.mjs ;;
  *) echo 'Unknown phase' >&2; exit 2 ;;
esac
