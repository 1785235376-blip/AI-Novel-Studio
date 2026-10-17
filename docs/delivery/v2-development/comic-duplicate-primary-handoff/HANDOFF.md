# Comic authored panel duplication: primary handoff

Worktree: `/workspace/scratch/20a0022d2b33/studio-comic-duplicate`
Branch: `work/dot-comic-duplicate-20261017`
Baseline: `b5f52c823b4df58ffe69ec309bfc2fc0e4a114fe`
Status: primary and independent gates passed; source frozen; local commit authorized; no push.

## Scope and ownership

Explicit source-panel preview and target coordinates copy authored content only. Source shot remains unchanged. Exact asset/version/crop and appearance references are disclosed. New panel and bubble IDs are generated once on explicit apply; dimensions, Unicode, style and references stay unchanged, bubbles translate exactly, and reading order appends contiguously. Original undo/redo, Save/CAS, preflight, manual review and export remain the owners.

The helper checks actual original limits (24 panels, 12 bubbles per panel, 80 total bubbles, 10,000 Unicode code points), page pixel budget, safe areas, bounds, overlap, spatial/numbered order and current source/reference mappings. Synchronous editor-generation and action-admission guards reject retained callbacks before React rerender. Cancellation, client/scope changes, catalog changes, busy state and IME revoke duplicate intents. Final IME compositionEnd followed by onChange is covered.

Only these six product/test paths changed:

- `frontend/src/experimental/ComicLayoutsPanel.tsx`
- `frontend/src/experimental/comicDuplication.ts` (new)
- `frontend/src/experimental/comicDuplication.test.ts` (new)
- `frontend/src/experimental/ComicLayoutsPanel.duplicate.test.tsx` (new)
- `tests/fixtures/comic_panel_duplicate.json` (new, small shared fixture)
- `tests/test_comic_panel_duplicate.py` (new)

No existing backend, client, renderer, old test, golden row/PNG/ZIP or runner changed. Static reviewer-requested synchronous owner fences were implemented before primary execution. No product runtime fix was needed during primary gates; all three execution corrections below affect new tests only.

## Final acceptance and exact evidence

All links below are relative to this handoff folder. Each named receipt has its exact command, timestamp, environment, source hashes, exit code, source-before/after maps and log SHA-256.

- [Final source/log audit](../comic-duplicate-primary-audit.json): all seven final receipts have identical 2,614-entry source maps before and after; every referenced raw log hash verified.
- [Natural/actual-child origin before](../comic-duplicate-origin-final-before-r2.json), [log](../comic-duplicate-origin-final-before-r2.log), [natural startup](../comic-duplicate-origin/normal-startup-final-before-r2.json).
- [UI r4](../comic-duplicate-ui-r4.json), [raw log](../comic-duplicate-ui-r4.log): **98 passed across six suites**. Includes new helper 35, new UI 25, original arrangement 18, original panel 8, original additive 6, original framing 6.
- [File r2](../comic-duplicate-file-r2.json), [raw log](../comic-duplicate-file-r2.log): **83 passed, 2 skipped, 47 PostgreSQL-only deselected**, 2 dependency warnings. Normal conftest remains active; no guard bypass.
- [Forced TypeScript r2](../comic-duplicate-type-r2.json), [raw log](../comic-duplicate-type-r2.log): PASS, full `tsc -b --force`.
- [Vite build r1](../comic-duplicate-build-r1.json), [raw log](../comic-duplicate-build-r1.log): PASS; existing chunk-size warning remains.
- [Token guard r1](../comic-duplicate-tokens-r1.json), [raw log](../comic-duplicate-tokens-r1.log): PASS, 52 files.
- [Natural/actual-child origin after](../comic-duplicate-origin-final-after-r2.json), [raw log](../comic-duplicate-origin-final-after-r2.log), [natural startup](../comic-duplicate-origin/normal-startup-final-after-r2.json). This strengthened after-probe also explicitly resolves the original comic owner/API; before-probe establishes the same clean product namespace/runtime origins.

Commands and exact proof scripts remain under [comic-duplicate-origin](../comic-duplicate-origin/), including `run-final.sh` and the final before/after proof launchers. Tests use only the clean `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python` and unchanged `scripts/run_v2_checks.py`. There were no provider/network/database installs or writes, browser sessions, Windows execution, or paid resources.

## Persistence, pixels and honest limits

The shared fixture is checked against the actual TypeScript helper and original File save path. A fresh store, repository bundle and service set reopen the saved document. Unicode, bubble geometry, crop, shot and appearance references persist without source/asset mutation. Original CAS conflicts remain atomic and original restore makes a fresh draft.

The **no-text** synthetic copy independently passes original preflight, explicit warning acknowledgment/review and deterministic ZIP export. Manifest source/bindings and PNG hashes match original preview; copied panel crops are pixel-identical at their translated location, with independently checked crop pixels and surrounding white canvas.

The two skipped tests are genuine font prerequisites:

1. Existing `tests/test_r5_comic_layouts.py` licensed-text raster scenario: `NOT_RUN: pinned OFL test font not supplied; hosted gate prepares it`.
2. New `test_authored_copy_text_pixels_require_real_pinned_font[file]`: `BLOCKED: original pinned OFL font unavailable; no rendered Unicode claim`.

The separate new Unicode persistence test **passes** and asserts that missing original pinned font blocks preflight/render/approval. No font was installed, substituted or mocked. No rendered-Unicode, browser/visual, Windows, PostgreSQL, model-artwork or deployment acceptance is claimed. The existing component/client exposes no explicit read-only prop: unavailable catalog/records and stale saved rows fail closed; actual write authorization remains with the original backend Save owner.

## Initial failures retained, never rewritten as success

- [UI r1 receipt](../comic-duplicate-ui-r1.json), [raw log](../comic-duplicate-ui-r1.log): **73 passed; five suites passed and new UI suite failed collection**. jsdom transformed `import.meta.url` into a non-file URL, so a new test's fs URL fixture loader failed. Corrected only new UI test to use the existing supported static JSON import.
- [UI r2 receipt](../comic-duplicate-ui-r2.json), [raw log](../comic-duplicate-ui-r2.log): **97 passed, 1 failed**. New assertion expected URL.revokeObjectURL to receive only one argument; original Array.forEach also passes index/array. Changed only the new test to assert the exact first-argument call list equals one expected URL. Original cleanup untouched.
- [Type r1 receipt](../comic-duplicate-type-r1.json), [raw log](../comic-duplicate-type-r1.log): **FAIL, TS2352** for a new malformed-input fixture directly asserted as ComicDocument. Added intentional `as unknown as ComicDocument` to that new test only.

Intermediate UI r3 (98 passed) and File r1 (83 passed, 2 skipped, 47 deselected) remain preserved. The final fresh origin/UI/File/type/build/token/origin run followed the last correction, with identical final source maps.

## Durable runtime provenance and checksum index

`runtime/setup-receipt.json`, `runtime/environment-evidence-index.json`, and `runtime/startup-probe-r3.json` are byte-exact, cmp-verified copies of the original clean interpreter evidence. Their original paths remain named in the files; no original evidence was overwritten. Setup receipt is about 1.4 MiB; no environment/archive copy was made.

`SHA256SUMS.txt` indexes all retained comic duplication raw receipts/logs, proof scripts and startup evidence plus these runtime copies. Source hashes are authoritative in the final audit and below:

- ComicLayoutsPanel.tsx: `68925731310eed114a1980a1134f2f27152d67c80b6fcd38925b51a05255113f`
- comicDuplication.ts: `ee6d29f51434fb767ee81d26b47ed80225e8620b538ff53c8b936cee94b2ef0a`
- comicDuplication.test.ts: `6a8bf18c39746caa30775a5a206265d09b663dbf4e18704c47dbe5efa35f78ae`
- ComicLayoutsPanel.duplicate.test.tsx: `eb9182b46eaa851c0727f26f76190406d10b6c8908786339d06865b0d4577ecd`
- tests/fixtures/comic_panel_duplicate.json: `69c4024e1ea9dacbe7ecd431ca9bf8deb4396b442310151952bf6d46ef389f4b`
- tests/test_comic_panel_duplicate.py: `52c4760f05d8eb88e08ca23afb3e3b70d321bb1cc6275af543cebd3582cc9faf`

## Independent execution and local commit admission

Independent execution passed against the exact frozen sources:

- [Independent audit](../comic-duplicate-independent-audit.json): all eleven primary/independent receipts have identical before/after/current **2,614-entry** source maps; log hashes verified.
- [Independent UI receipt](../comic-duplicate-independent-ui.json), [log](../comic-duplicate-independent-ui.log): **98 passed, six suites**.
- [Independent File receipt](../comic-duplicate-independent-file.json), [log](../comic-duplicate-independent-file.log): **83 passed, two real font skips, 47 PostgreSQL-only deselected**, two existing warnings.
- [Before child-origin receipt](../comic-duplicate-independent-origin-before.json), [log](../comic-duplicate-independent-origin-before.log), [natural startup](../comic-duplicate-independent-natural-before.json).
- [After child-origin receipt](../comic-duplicate-independent-origin-after.json), [log](../comic-duplicate-independent-origin-after.log), [natural startup](../comic-duplicate-independent-natural-after.json).

Independent execution made no product edits and installed/substituted no font. All raw failures above remain intact. Parent authorized a local-only commit of precisely the six reviewed source/test paths and newly owned comic-duplicate evidence, excluding `.runtime` and `frontend/node_modules`. No push, release, or main-branch action is authorized here. Final commit identity is reported separately for reviewer Git binding.
