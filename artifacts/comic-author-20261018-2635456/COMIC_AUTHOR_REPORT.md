# Native editable assetless Comic author archive integration

Product checkpoint: dedff1c27e3dd2fcaea53131d5f22fe741a9084b. IMAGE-COMIC-18 and full V2 remain PARTIAL / NOT ACCEPTED.

## Actual user-visible closure

An existing independent PAGE book can explicitly export its editable author content, inspect the saved archive, and restore a new book with fresh page/panel/bubble/layer IDs. Native geometry, editable text, framing, hidden text/image briefs, native layer order/visibility/opacity and chapter/page order survive. The restored pages are unapproved DRAFTs and reopen in the original Comic editor, where subsequent edits and saves remain authoritative. Exact retries return current edited rows without resetting them or creating another book.

This is deliberately assetless: 1–10 independent pages, no image assets, characters, screenplay/shot references, reviewed ORA RASTER layers or WEBTOON. Unsupported dependencies fail before writes; they are not silently stripped. It is not full project portability, media-preserving restoration or whole-instance backup. Author export can reveal hidden text and briefs, so its explicit disclosure and acknowledgement are separate from flattened public reading copies.

## Persistence and admission

Original Comic validation and the original scope transaction own all new pages, book and subordinate import receipt. No new workflow engine or Asset store is introduced. Receipt identity binds archive SHA, request UUID, actor, scope and original incarnation. Twenty non-evicted receipts are disclosed; unavailable/changed results fail without recreation. The ZIP/JSON transport has independent byte/member/depth/value limits and bounds the central directory before parser allocation.

The mounted UI uses a stable inspection identity and real Web Locks, with durable local metadata/readback before dispatch. It persists no archive text or credentials. UNKNOWN attempts are explicitly recovered using the same request key. A separate new-copy action revalidates its expected completed predecessor under the lock; a stale tab cannot overwrite another tab's pending attempt. Retired-scope results cannot select or download old content. No automatic retry or inferred approval is added.

## Verification

- Backend File: 90 native/security tests passed; earlier 116 native/collection tests overlap, and affected collection teardown rerun passed 42. Independent backend review also passed 90; counts are not additive.
- Frontend: 216 tests plus full TypeScript/Vite/token passed on frozen source. All 1,643 frontend inputs match integration; the exact build was copied and verified rather than redundantly rebuilt.
- Real PostgreSQL 17.11 / UTF8 / OID 16384: final 128 passed, 4 deliberate File-only instrumentation skips, 140 non-PG cases deselected. All 14 table row-hash multisets match and the server stopped. Final receipt matches 3170 integrated source paths.
- Initial PG assertions also passed, but cleanup failed because an old original collections test left 2 workspaces, 4 users, 4 memberships and 6 audit events. Exact synthetic IDs and hashes were inspected and restored transactionally. The test-only finally fix preserves all assertions; the same cases then passed with exact cleanup. Initial failure, inspection, cleanup and final success remain recorded.
- PUBLIC wheel/catalog: 6 passed; 2,521 operations, fingerprint 4acb48fee4fb894d671136dfa83b3760cf042cdc3e2a1932c152c7b3eae3e85d. Its sole later source difference is the original test fixture teardown; application and packaging bytes are identical. Private backend exclusion remains enforced.

The independent frontend review reproduced a stale new-copy race that prior tests missed. The corrected direct recheck dispatches zero additional requests and preserves the UNKNOWN key; 17 focused tests pass, including delayed restore/download retirement. Production mounted tests use synthetic HTTP contracts, not a real browser/server end-to-end claim.

## Boundaries and ongoing work

Actual browser multi-tab/visual/keyboard geometry, native Windows, external editor and complete same-candidate system acceptance remain open. Real in-flight role/feature-flag revocation and physical storage failures are not independently certified; session revocation, incarnation drift, generic late guards and injected pre/post-commit failures have bounded coverage. Existing mature-content backend exclusion and release HOLD remain unchanged.

A read-only morning audit corrected stale historical/current ledger labels and obsolete Comic entry/ORA gap summaries without marking any entire requirement accepted. Earlier source 80c8e4c is independently archived at 5776531b8c531a7cc12eba153171c13b10960935, exact parent c4b15e8b: 15 artifacts / 5,544,877 bytes verified. Archive bundles do not advance main or PR source heads and are not releases.

Separate schematic Comic geometry and selective Director camera-field reuse tasks are now active, not included as completed in this checkpoint.
