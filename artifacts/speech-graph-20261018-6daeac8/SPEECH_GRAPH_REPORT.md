# Storyboard speech and Graph failure navigation: bounded integration

Product checkpoint: 35d9167f63cc462052fcff3b30445a76654b95e8. Full V2 remains NOT ACCEPTED.

## Delivered

- An approved saved Storyboard shot can prepare one explicitly selected dialogue line for the original Audio speech owner. Document/shot/index/text pins, provider/model, voice and rate are explicit. Preparation writes no job and calls no model. The original preview → queue → private candidate → human review → Audio Asset chain preserves provenance and rechecks source, actor, branch, incarnation and authority. No new execution owner or automatic Timeline placement was added.
- Actual mounted response fixtures validate frontend decoders; legitimate null execution/reconciliation values remain null. Actual baseline ce3ac098 canonical speech/video bytes and hashes remain compatible. Synthetic WAV provider tests exercise ownership and transport, not speech synthesis or quality.
- Failed/skipped/rejected Graph node rows provide conservative code-specific advice and explicit exact-node selection/focus in the original inspector. Permanent owner/graph/read/authority lifetime tokens block stale callbacks and ABA. Author dirty input, external execution and pending IMAGE fences remain. There is no automatic retry, execution or cost inference; unknown outcomes are explicitly not retry authority.

## Evidence

- Integrated File: 57 passed, 55 PG parameters deselected.
- Real PostgreSQL: 55 passed, 57 non-PG parameters deselected. Existing UTF8 PostgreSQL 17.11 database OID16384 reused; no migration or creation. Exact row hashes across 14 tables match before/after, and the server stopped.
- Combined UI: 386 tests in 21 suites; full TypeScript build, Vite production build and UI token guard passed. These overlap builder and reviewer runs; counts are not additive.
- PUBLIC wheel/catalog: 6 passed. Catalog now has 2501 operations, fingerprint 0581733a9255a039bce6704b83559df0debf20e3d9089a1e714233091c9128ca. Private backend exclusion remains enforced.
- File and final UI receipts match all 3149 source paths at final product. PG/PUBLIC were run immediately before the UI-only Graph navigation commit; their only source-map differences are the five Graph UI/test files and three new Graph UI/test paths. Backend, packaging and API catalog bytes are identical, so those backend checks were not needlessly repeated.

## Failed checks retained and corrected

The initial speech final regression failed four promotion cases due to an undefined job variable in the new origin check. It now uses the original Audio owner's server-built review source_job_id; successful promotion and forged-candidate tests pass. The raw failure is preserved.

Independent UI review found delayed speech response ABA and a dialogue choice carried across a reread that selected another shot. Lifetime invalidation and explicit choice reset correct both. Actual response fixtures also exposed legitimately nullable wire fields; types were corrected without substituting false certainty.

Initial Graph tests caught two real retained-callback revivals: busy→idle and same-batch run reread returning the identical object. Permanent editor and synchronous read tokens now fence them. A separate assertion incorrectly expected a disabled button after reread, while the original behavior clears selected run; that assertion now verifies absence. All original failure logs remain unchanged.

## Limits and next work

Browser, geometry, real keyboard/screen-reader, native Windows, actual speech model/provider and full cross-module acceptance remain NOT_RUN. A retained visual attempt failed before launching a page because bundled Chromium was absent. The new Graph action focuses the inspector in jsdom; it does not establish viewport pan/zoom geometry in a browser.

A09, DIF-02 and GRAPH-07/22 remain broader partial requirements. Prior source9a3b3a51 was independently archived as0ea2c08e889dd7aba5d0df68d0ae944289c33e2a, exact parentce99a289, 14 artifacts / 5,565,777 bytes. Publication is a prerequisite-bound archive bundle, not a main/PR source update or release. Current isolated work adds a bounded PDF reading copy using existing Comic publication owners; it is not yet integrated or accepted.
