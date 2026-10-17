# Caption import inventory refresh

Source checkpoint: `4ebac7a0b039c1cf6bdf3103650185325875260d`. The subsequent inventory/evidence commit is not the source checkpoint.

The unchanged generator completed exactly three invocations: no-write review, owned candidate write, and separate no-write post-promotion confirmation. The generator enforces frozen V1; additional offline validation and independent review enforce the entire preceding V2 inventory. No product test bodies or lifecycle fixtures are executed by inventory collection.

- 15,742 collected rows: all 15,617 old rows retain exact relative order and backend classification; 125 new subtitle import rows comprise 62 file-only, 62 postgres-only and one both-backend lexical parser. The latter accounts for 63 File-applicable focused tests, not 63 file-only rows.
- The first post-collection validator incorrectly expected 63 file-only rows. The generator itself exited zero. The original launcher and diagnostic are preserved; validation was recovered from immediately archived raw bytes without invoking collection again. No test markers or source bytes changed. The initial launcher had not reached its independent source postcheck and did not persist its in-memory pre-snapshot; the unchanged generator did complete its own full pre/post source comparison. Recovery separately bound current sources to the frozen source commit. Candidate and confirmation persist their full pre/post snapshots under .runtime.
- 2,584 source hashes reconstruct from the preceding 2,582-source manifest with five runtime changes and two new test files. All 1,271 prior protected hashes, historical skips, external gates, frozen V1, generator/runner and complete 11-file frontend/scripts and frontend/e2e companion remain exact.
- Raw new collection bytes are included once in this portable bundle. Each invocation also archives its fixed raw collection immediately under .runtime. Previous 15,617 and 15,142 archives remain hash-bound references.
- Startup proof is copied byte-exact from the source checkpoint. Only the approved clean interpreter and sanitized command-local environment are used; the original runner owns the File/mock/cloud-off profile.

This evidence demonstrates collection and source preservation only. It is not full discovery execution, full E2E, browser, live provider, PostgreSQL execution, or hosted CI acceptance. Focused execution evidence is separately recorded in the committed backend/UI evidence.

Offline verification from repository root:

`node docs/delivery/v2-development/caption-import-20261017/inventory/check.mjs .github/ci/coverage_manifest_v2.json.gz final`

This verifier is read-only, imports no product code, and runs no tests. It checks exact canonical bytes, all current source hashes, complete source reconstruction, old protected entries, immutable guards, companion closure, exact old and new rows/classifications, historical archive references, per-invocation bindings and evidence hashes. It requires local Git history containing the baseline checkpoint.

## Protocol diagnostics and recovery

The local candidate checker initially assumed new added_nodes were appended after all prior V2 additions. The unchanged generator instead rebuilds them from frozen V1 in collection order. The corrected checker validates that exact construction, all prior added-node relative order, membership and uniqueness. The initial checker and diagnostic are preserved. Independent review also records a source_changes object-key-order comparison correction; candidate bytes did not change.

Work stopped during the environment outage after candidate generation. No promotion, confirmation collection or other execution occurred during the outage. After the same environment recovered, normal startup matched the original proof exactly and the current-root actual-child stdlib-only origin probe passed again. Independent exact-candidate approval and parent release preceded canonical promotion.

## Final result

All three generator invocations exited zero. Their raw collections are byte-identical, SHA256 `137bb78b6fe8c9b4c5f64589dca22c9b73ea5733dd9d597ce520b5309c15b23c`. The approved candidate was promoted byte-exact and remains unchanged after the separate no-write confirmation: canonical SHA256 `414865364741d8836181670735f2e4cecb041541645c3cfc8fd7a52f2492a254`. Candidate and confirmation persisted full pre/post source snapshots and both pairs are byte-identical to the bound complete source map. No files were staged or committed by the inventory worker.
