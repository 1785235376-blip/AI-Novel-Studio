# B06 manual COVER framing

Baseline: `d10b72c1bc2db33dc2dff85af4f31ede478cf1fc`. B06 remains **PARTIAL**. This delivery closes the bounded off-center artwork framing gap in the existing comic layout owner.

## Scope and compatibility

Three runtime consumers change: `app/experimental/comic_layouts.py`, `frontend/src/experimental/comicLayoutsClient.ts`, and `frontend/src/experimental/ComicLayoutsPanel.tsx`. Two new self-contained suites add coverage; no historical tests, schemas, asset owners, renderer engines, model providers or shared shell/styles are changed.

- Optional `cover_x_percent` / `cover_y_percent` accept strict integers 0–100, defaulting to center 50. Booleans, strings, nulls, floats and out-of-range values are rejected.
- A panel wrap serializer preserves omitted fields through nested create/update normalization, saved documents and historical restore. Reading old approved documents does not inject defaults or migrate their digest-bound data. Explicit center values persist.
- COVER positions over the available crop travel: `(panel_dimension - resized_dimension) * percent // 100`. At 50 this preserves the original negative floor rounding, including odd excess pixels. These are edge alignment controls, not semantic subject or focus recognition.
- CONTAIN rendering remains unchanged. UI retains values but disables them until COVER is active. The existing local edit/undo/redo, arrangement, CAS save, preflight, warning consent, approval and PNG export paths remain authoritative.
- Actual centered offsets retain `COMIC_CENTER_CROP`; off-center offsets use `COMIC_POSITIONED_CROP`. Inactive axes and rounded-equivalent center positions do not falsely claim positioned cropping. Existing report/manifest fields remain unchanged for legacy center documents.

## Pre-edit compatibility evidence

`docs/delivery/v2-development/comic-framing-baseline-20261017/` retains tiny original synthetic inputs, actual old normalized/stored documents, original report and review digest, actual PNG/ZIP output, and File source state. The state contains synthetic novel/chapter/asset IDs, not host runtime credentials. Empty lock files are excluded. The chapter `public_token` is its public allocation identifier, not an authentication token.

Capture ran before runtime edits against the original owner using Pillow 12.3.0. No time, ID, font, renderer or service monkeypatches were used. The no-text layout authentically reported unavailable pinned font; no font configuration changed. `capture.py` and `verify.py` retain their original historical absolute paths as provenance, not test dependencies. `verify_legacy_portable.py` consumes the committed evidence and a new caller-specified work directory. The shipped pytest/jsdom suites contain no dependency on private capture paths and do not skip when capture files are absent.

Post-edit comparison on a fresh File-state copy verified identical normalized document, report, approved row, stored state and review digest, plus byte-identical PNG and approved ZIP without reapproval. Expected artifacts were not regenerated after edits. The pre-edit PNG hash is also embedded in the self-contained regression test.

## Verification and provenance

The companion JSON index records hashes and paths. Original runner receipts use unchanged `scripts/run_v2_checks.py`, owned profiles, isolated credentials and File-only operation; their 2,602-file snapshots report no source changes during checks.

- Original-runner backend: **63 passed, 1 skipped, 26 deselected**. The skip is the existing real pinned-font test because no font was supplied. PostgreSQL cases are excluded; this is not font or PostgreSQL coverage.
- Original-runner UI: **38 passed**, one worker, cache disabled, covering new framing plus unchanged panel/additive/arrangement tests.
- Forced TypeScript and Vite build, token guard (52 files), PUBLIC closure (493 files), and diff check: **PASS**. Vite retains its existing large-chunk warning.
- Independent reviewer inspected runtime, tests, pre-edit artifacts, hashes, actual logs and receipts: **PASS**. Independent original-runner execution subsequently passed: clean origins, exact legacy copied-state comparison, backend 63 passed / 1 font skip / 26 PostgreSQL exclusions, and UI 38 passed. The `comic-framing-independent-*-r1` receipts retain that separate evidence.

Failures are retained rather than hidden:

1. Initial direct pytest invocation omitted the original runner and therefore its owned application profile. Global startup attempted a read-only default home directory before any test body. `backend.log` is **INVALID PRIMARY GATE**, not an original-runner receipt. It was corrected by using the unchanged original runner, with the safe pre-runner environment from the prior canvas-insert launch pattern.
2. UI r1 failed one new spy assertion: original `forEach(URL.revokeObjectURL)` supplies index/array arguments in addition to the URL. Parent authorized correcting only the new test to assert the exact first-argument call list, including one call. UI r2 passes; runtime and golden output were unchanged. Both original receipts are retained.

## Limits

Browser/native input/visual geometry, Windows/GPU/provider/model artwork, professional print quality, real-font output and PostgreSQL are **NOT VERIFIED** by this delivery. No installation, download, font substitute, provider call, asset copy into the library, user-computer work, push, merge, release or publication occurred. Existing source/privacy/version/authorization and review revocation fences remain in force. Parent integration remains a separate gate. The portable verifier is provided for reproduction but was not itself executed; the independent legacy check used the reviewed original verifier with only its owned baseline path changed.
