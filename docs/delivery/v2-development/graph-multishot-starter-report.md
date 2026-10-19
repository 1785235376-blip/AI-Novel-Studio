# Explicit multi-shot Graph starter

Base: f1b33b31. Isolated worktree: studio-graph-multishot. No primary checkout edits, engine/store changes, generator capacity changes, provider calls, credential access, pushes or releases.

## Delivered

- Existing single-shot builder remains a compatible wrapper. Additive builder accepts an explicit unique subset of 1–4 approved original storyboard shots, retaining document and per-shot ID/version/digest pins in original shot-number order.
- One shared storyboard_plan plus each storyboard_shot → video_generate → media_review branch: maximum 13 nodes, 12 original typed edges, 4 generators. Reject empty/duplicate/unknown/>4 selections, nonempty or non-v5 drafts, missing catalogue capabilities and colliding node/edge IDs. No truncation and no input draft mutation.
- Native labeled multi-select shows all original shots, visible maximum and selected count; preview shows branch/node/edge/generator counts, LOCAL_ONLY, exact pins and required provider/model configuration. Provider/model remain blank, allow_cloud false; no save/run/approval is implicit.
- Existing controller performs one history change, hence one undo/redo. Exact-source validation, authority/scope/selection epochs, DOM selection check, retained-callback and consumed-proof fences remain in place.

## Verification

- 27 frontend tests PASS (9 unchanged single-shot, 18 additive multi-shot), including 1/2/4 branches, IDs/pins/typed ports/unmodified inputs, invalid selections, >4-source explicit subset, >4 rejection without truncation, preview, DOM drift, selection ABA, authority ABA, retained/unmounted callbacks, double apply, and 2/4-branch controller undo/redo with no automatic writes or dispatch.
- TypeScript build-mode typecheck PASS after correcting the new table-driven test's argument shape. UI token guard PASS (52 files). git diff --check PASS.
- Original runner and original rig: 19 File tests PASS; 9 PG variants deliberately deselected. New backend tests approve the source through the original owner, fill original provider/model configuration and verify 13-node/12-edge create/save/readback/reopen plus unchanged fifth-generator rejection with no persistence. Transport calls and lifecycle starts remain zero. Adjacent original video-foundation tests included; two pre-existing warnings retained.
- Independent read-only runtime review and independent 27-test run: no concrete defects found.
- Browser visual/geometry attempt BLOCKED before rendering: Playwright Chromium headless shell 1234 is absent. Five launch failures retained; no visual PASS claimed, no browser download or fallback launch. Canonical VIDEO reference and design-system rules reviewed. No protected shell/token changes.
- PostgreSQL execution, final combined production build, publication/archive remain root-owned, not claimed here.

## Commands and evidence

Node runtime: /opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin. Shared existing frontend/node_modules symlink is excluded from commit; no dependency installation.

- node frontend/node_modules/vitest/vitest.mjs run --root frontend src/creative/GraphStoryboardStarter.additive.test.tsx src/creative/GraphStoryboardStarter.multishot.test.tsx
- node frontend/node_modules/typescript/bin/tsc -b frontend --pretty false
- node scripts/check_ui_design_tokens.mjs
- In frontend: node node_modules/@playwright/test/cli.js test --config playwright.visual.config.ts --grep 'video workspace visual baseline|shell geometry'
- /workspace/scratch/20a0022d2b33/studio-director-transport/.runtime/recovered-python-20261018/bin/python scripts/run_v2_checks.py graph-multishot-video-regression-final-file -- python -m pytest -q tests/test_v2_graph_multishot_starter_additive.py tests/test_v2_graph_video_foundation.py -m 'not postgres_backend_only' --basetemp=.runtime/pytest-graph-multishot-video-regression-final-file

Raw frontend/type/token/browser logs and exact source SHA-256 manifest: graph-multishot-evidence/. Final backend receipt/log: graph-multishot-video-regression-final-file.{json,log}. Earlier evidence is retained under graph-multishot-* labels. Initial frontend fixture failures (incomplete continuity and stale cloned video-result pins) and the test table typecheck failure were fixed without changing production validators. One initial backend sparse-import failure was overwritten by the immediate retry; its original tool transcript remains, and this is not represented as a preserved file. The existing rig requires basetemp under worktree .runtime, so /tmp was not used for backend fixtures.
