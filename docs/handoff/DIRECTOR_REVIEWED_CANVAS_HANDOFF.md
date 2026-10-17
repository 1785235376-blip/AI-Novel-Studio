# Reviewed Director draft to canvas handoff

Status: implemented, independently statically reviewed, and primary verification passed on the frozen sources. Independent verification also passed unchanged. This document does not claim browser, PostgreSQL, Windows, release, or native-provider verification.

Baseline: `9b72ff93b48dbed4c2631a83222843829ecb5505`.
Branch: `work/dot-director-canvas-handoff-20261017`.

## User workflow

1. Use the existing admitted Director proposal/manual-review workflow to adopt its original Creative `DIRECTOR` `DRAFT`.
2. Explicitly choose a compatible Graph/catalog using the existing Graph controls. No schema migration or new Graph is implicit.
3. Select “核对导演原文档版本”. The original Creative owner exports the exact reviewed ID/version and validates its DRAFT status and digest. A changed target/selection/author lifetime rejects a late response.
4. Select “将此审核草稿添加到画布”. A one-shot proof stages a normal `director_plan` through the existing controller insertion path. Only `document_snapshot: { id, version, digest }` enters Graph parameters.
5. Save Graph explicitly using the original save/CAS/history owner. A failed Graph save retains its local draft and does not recreate or re-review the Creative document.

An explicit fresh verification can authorize another insertion after undo or a different target. Repeated clicks and retained callbacks cannot reuse consumed or retired verification. Source edits, composition, source replacement, actor/scope/incarnation changes, Graph version/edit/selection/navigation changes and ABA transitions retire stale intent. Local UI proof never substitutes for current server access or final original Graph validation.

## Preserved boundaries

No backend endpoint, gate, storage, provider, review, execution, or public private-pending transport changes. The private pending flow remains private. Existing rule/manual review can use this UI only under existing admitted owner/catalog/schema gates. `director_plan` emits `DIRECTOR_PLAN`; Creative DRAFT status is not a Graph text DRAFT port.

No automatic connection, replacement, upgrade, save, run, model call, rebind, or removal. In particular a source Storyboard is an ancestor of its reviewed Director, never an automatically connected downstream node. Existing immutable bindings, undo/redo, positions, Graph selection and CAS remain with the original controller.

## Source and checks

Runtime scope: `GraphDirectorConsole.tsx`, `useStudioGraphEditor.tsx`, `useStudioGraphEditorController.ts`, and small ephemeral helper `directorCanvasHandoff.ts`.

New tests only: `directorCanvasHandoff.additive.test.tsx`, `GraphDirectorCanvasHandoff.additive.test.tsx`, `ReviewedDirectorCanvas.integration.test.tsx`. Original tests and runner are unchanged. Tests cover scalar insertion, explicit save/history, reverse-ancestry nonconnection, incompatible schema, malformed/stale pins, authority/selection/navigation ABA, same-tick retained callbacks, IME, source edits, late reads, failed placement/save, and explicit renewed intent. The integration case uses real Console/editor/controller wiring and a busy read lifecycle, with only proposal input and large graph rendering mocked.

Prepared owned verification launchers: `/workspace/scratch/20a0022d2b33/director-canvas-handoff-verification-r1/`. These use the original `scripts/run_v2_checks.py`, dedicated clean Python, original frontend dependencies/configuration, one Vitest worker, default test timeouts and no cache. The source guard compares every baseline test/config/fixture byte; original-runner receipts include complete before/after source maps. Launchers and full frozen SHA-256 manifest are retained separately. Primary launchers completed successfully without source or test corrections; all original-runner logs and receipts are retained under `docs/delivery/v2-development/director-canvas-*`.

Completed primary checks: all three new suites; original Console/proposal/source-impact/Storyboard handoff/director projection suites; insertion/palette/connection/authority and production Graph tests; shell geometry; forced TypeScript/Vite, design tokens, public scope, and diff check. No additional backend test is introduced: the existing public rule/manual-review/File bridge and separately owned private-pending/File bridge remain independent evidence.

## Primary verification results

- Original-runner Vitest: **16 suites, 169 tests passed**, including **29 new tests**.
- Forced TypeScript and Vite build passed. Existing large-chunk warnings remain advisory.
- UI design token guard passed (52 files); public source-scope guard passed (494 files).
- Natural and actual original-runner child clean-Python origin proofs passed without importing product code or tests.
- Original-test byte guards passed before and after, covering 1,368 baseline paths.
- All 8 original-runner receipts have identical 2620-file before/after/current source maps and matching retained raw-log hashes.
- Seven frozen implementation/test hashes remain exact. No failed or corrected primary attempt exists.
- `director-canvas-primary-audit.json` records this reconciliation. This primary count does not include independent reruns or separate backend/File bridge verification.

## Independent verification

- Independent original-runner execution passed the same **16 suites / 169 tests**, including all 29 new cases, without source changes or harness corrections. These repeated counts are not added to primary counts.
- Independent natural-startup and actual-original-runner-child origin proofs passed. Both independent original-test guards preserve all 1,368 baseline test/config/fixture paths.
- `director-canvas-independent-audit-r1.json` reconciles all **12 primary and independent receipts** against the exact **2,620-file** before/after/current source maps and retained log hashes. It also verifies the primary TypeScript/build evidence against those unchanged sources.
- Source freeze and scalar-pin ownership boundaries remain unchanged. Existing raw receipts/logs and the historical primary audit are retained byte-for-byte.
- `director-canvas-evidence-index.json` indexes every retained owned artifact and this handoff, excluding itself. No browser visual, provider, PostgreSQL, Windows, public private-pending activation, push or release claim is made.
