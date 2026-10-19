# Comic panel Image generation: bounded integration

Product source: b81b3aad9b28f3f20ee7ef73005b998fe926aa82. Baseline: 4430ce309c6a460d6d91d6e0e4b40336a0b6a544.
Updated 2026-10-19 00:12 UTC. This is partial IMAGE-COMIC-05, not V2 release acceptance.

## Implemented workflow

A saved IMAGE panel with a nonempty saved brief can explicitly prepare a LOCAL T2I request through the existing production owner. Original preview, queue, execute, private candidate, pixel/digest review and approval precede separate explicit adoption into the same Comic page. Adoption produces a DRAFT and clears page approval. It does not automatically approve, generate, save unrelated content or create a second workflow engine.

Exact page/panel/brief, actor, scope, incarnation and source digests are checked across request, execution, review and adoption. Changed or retired sources fail closed. Approval of an image does not edit the Comic. Asset/job/request/output versions are rechecked on adoption. The adopted approved Asset remains usable after the page version advances; old producer page-version validation is not incorrectly reapplied to normal approved Asset rendering.

BLANK panels, appearance references, cloud routes and non-T2I operations are outside this slice and rejected. No Broker integration is claimed for this standalone Image path. Original source serialization and original Image/Speech paths remain compatible. A repeated stale adoption fails CAS rather than returning idempotent success.

## Evidence

- Frozen original-owner File/API tests: 80 passed. Strict source/route negative checks: 30 passed.
- Real PostgreSQL: 80 passed, 80 File cases deselected; exact before/after hashes for 14 persistent tables, server stopped. No residue.
- PUBLIC artifact checks: 6 passed. New runtime module and contract included in original public allowlists.
- Pinned-font original Comic checks: 2 passed, no skips.
- Actual mounted File API capture: 1 passed. Captured providers/request/preview/queued/executed/read/review/adopt responses decoded through actual frontend clients in a passing wire test.
- Root final UI: 119 tests / 12 suites, TypeScript build, Vite production build, token guard PASS.
- Independent UI review: 168 tests / 16 suites plus TypeScript no-emit PASS. Counts overlap and must not be added.
- Root final UI source map matches all 3203 paths. Earlier PG/PUBLIC/CJK evidence matches all 542 app paths after frontend integration. Source reconciliation receipts explicitly retain these different execution heads.
- Catalog has 2525 operations, fingerprint 0afe0bea69127c88ff104da4126a9b91fec6fbae6872332f5c13a6bab3f2c216.

## Failures and review corrections retained

Original root UI run had 118 pass / 1 failure: a retained IME callback can be invoked without an event. Optional event/target/closest handling preserves existing semantics and the child-generation exemption; the unchanged original test now passes. No test was weakened. Independent failure log is retained.

Review also corrected stale retained callback/ABA dispatch, StrictMode replay handling, backend acceptance-field decoding and provider capability mismatch. Actual captured wire is used rather than merely agreeing synthetic frontend fixtures. Synthetic provider data still supplies the generated PNG.

Vite retains its large-chunk warning. The independent typecheck initially named a nonexistent tsconfig.app.json; actual tsconfig.json passes. This is recorded as a harness command mistake, not a product defect.

## Acceptance limits

No live model inference, image quality, real browser, Windows/GPU, large-book or whole-product acceptance. Tests use synthetic generated PNG bytes through original owners. No new paid API, quota, credentials, main merge, Release or PR source push. Prompt Adoption remains closed and public private-content exclusions unchanged.

Existing archive delivery uses prerequisite-bound incremental Git bundles. An archive HEAD is not a product source HEAD. New archive publication must be verified separately.
