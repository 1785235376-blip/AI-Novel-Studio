# Keyed generation receipt ownership and recovery

Date: 2026-10-25 UTC

## Scope and source lineage

- Original red/probe baseline: `e99e91ed84763224638b80ffb83ae7880fa4f1a0`, tree `82dcf4fd63800bddbecca0772d9a4e456ec9b09b`.
- Final parent: `7cfe858d959d97c3f6934cbe7c2a70ac1d79691d`, tree `7be9547da34dbf318794efa0718c55306273efff`.
- The parent advanced through a separate C-group test-fixture delivery. Its production files were unchanged; this B-group work was preserved byte-for-byte during that advance.
- This change owns exactly `app/api.py`, `app/idempotency.py`, `app/services/generation_idempotency_authority.py`, `tests/test_generation_idempotency_contracts.py`, and this report.
- The original CreativeProjectStore, project/chapter deletion and recreation semantics, Asset owners, and external Work/AudioAsset history are unchanged. Publication is performed separately after parent review and must be confirmed by remote HEAD readback.

Portable evidence is included in [evidence/generation-owner-replay-20261025](evidence/generation-owner-replay-20261025/): final 102-case outcomes and original JUnit digest, fixed source hashes, the original final-run log, independent review, and post-fix counterexample/boundary observations. Checkout paths in copies are normalized. These are preserved actual run results, not another test execution. The independent reviewer found no blocking issue in the frozen three production files.

All runs source `.runtime/activate-backend.sh`, then override HOME, XDG paths, APPDATA, LOCALAPPDATA, NOVEL_DATA_PATH, and TMPDIR/TMP/TEMP into isolated run directories. Storage is File, configuration is Mock/LOCAL_ONLY with cloud disabled, and provider/database credentials are unset. No real provider, model, PostgreSQL, Windows, network service, or installation was used.

## Preserved red evidence

The original B selection collected 44 real nodes. Actual PostgreSQL tests in the mixed files were excluded by exact File node selection. Four postgres-named Markdown cases call a pure renderer, not a database.

Initial B run: **37 passed, 7 failed, 0 skipped**, exit 1, 6.98s.
Independent original-file rerun in fresh directories: **0 passed, 7 failed, 0 skipped**, exit 1, 7.06s.

All seven failures were in `tests/test_generation_idempotency_contracts.py`:

| Node suffix | Original failure |
| --- | --- |
| `test_generation_replay_returns_cached_result_without_creating` | 404 instead of 202 |
| `test_generation_replay_contract_is_stable_across_repeats` | 404 instead of 202 |
| `test_generation_without_idempotency_key_creates_independently` | 404 instead of 202 |
| `test_generation_distinct_keys_create_once_each` | Missing `job_id` |
| `test_generation_idempotency_is_namespaced_by_operation` | Missing `job_id` |
| `test_generation_create_failure_is_not_cached_and_releases_lock` | 404 instead of 500 |
| `test_generation_fresh_store_concurrent_submission_survives_repeated_races` | Missing `job_id` |

The old tests submitted fictional `novel_id=n` and `chapter_id=c` without creating those File owners. The route already validated ownership before cache lookup or dispatch. An isolated diagnostic returned `HTTP_404`, `Not found: c`, and zero dispatcher calls with collaboration disabled. This was not a missing route or a permission rejection. The replay tests also fabricated obsolete unscoped keys and bare results rather than the current authority-scoped key and digest/result envelope.

Original logs, JUnit, exit files, selected targets, and unchanged-source SHA256 manifests remain in `.runtime/recovery-owners-validation-20261025/`.

## Two production counterexamples: red to green

### Legal project deletion and recreation

The original probe used actual HTTP owner routes:

1. A generation request cached `job-1` for a real File project and chapter.
2. DELETE `/api/novels/idempotency-book` returned 204.
3. POST `/api/novels` with the same project ID returned 201.
4. POST the recreated project's `/chapters` returned 201 and legally reused `idempotency-book:1`, now with different source text.
5. The same request key/payload incorrectly returned old `job-1` with 202 and no new dispatch.

This is whole-project retirement/recreation, not direct chapter-number reuse inside a surviving project. The latter retains its allocation ledger and does not permit that reuse.

Regression: `test_generation_cached_result_rejects_recreated_project_incarnation`.
Before fix: **202 instead of required 409**.
After fix: **409 `IDEMPOTENCY_OWNER_CHANGED`**, no redispatch, no receipt overwrite, and no automatic replacement marker on replay.

### Source deletion during cached job lookup

After the real branch route seeded a cache entry, the controlled dispatcher lookup hook archived and deleted the real branch source using successive current versions. No source or authorization function was stubbed.

Before fix, the in-flight replay returned 202 metadata; the immediately following identical request returned 404 `CHAPTER_NOT_FOUND`. This demonstrated stale job-metadata replay, not generated-content disclosure or external execution.

Regression: `test_generation_cached_result_rechecks_source_deleted_during_replay`.
Before fix: **202 instead of required 404**.
After fix: **404 `CHAPTER_NOT_FOUND`**, no redispatch and unchanged retained receipt.

The two explicit failing regression tests were run before production changes: **0 passed, 2 failed, 0 skipped**, exit 1, 6.35s. Their logs/JUnit and original probe output remain under `.runtime/recovery-owners-repair-20261025/`, including `production-regressions-red.*`, `owner-probes.json`, and `probe_owner_replay.py`.

## Minimal production change

### Retain request identity; bind the receipt

The original authority/operation cache key is unchanged. Its value now has schema version 2 and a canonical `project_incarnation`, alongside the request digest and original result. Putting incarnation only into a new key would turn a previously executed request into a miss, so this implementation deliberately does not do that.

The new authority adapter derives its owner from the actual novel and chapter repositories:

- File: validate their data roots, then use the original CreativeProjectStore marker and lifecycle lease. A registered branch store and its project/mainline repositories must resolve to the same root.
- PostgreSQL: require the actual shared repository Database. A narrow adapter uses its existing engine, transaction, and original `SELECT id FROM novels WHERE slug = %s FOR KEY SHARE` protocol. Registered branch configuration must identify the same database, including relevant connection configuration.
- Global `settings.data_path`, creation time, inode, and content hashes are not substitute identities. No new registry or global service/store fallback is introduced.
- Only a new explicit request key may provision the existing File owner marker. Replay uses `existing_owner_only`; a missing or invalid marker is not recreated or adopted.

### Explicit keyed-generation migration and TTL tightening

A read-only `IdempotencyStore.retained()` distinguishes a genuinely absent file/key from malformed existing JSON or records. It does not evict or rewrite anything. Other callers of the original `get()` retain their previous TTL behavior.

For **keyed generation only**:

| Retained state | Result |
| --- | --- |
| Old unbound scoped/unscoped record, or malformed record | 409 `IDEMPOTENCY_RECORD_UNVERIFIED` |
| Unverifiable repository/root binding | 409 `IDEMPOTENCY_OWNER_UNVERIFIED` |
| Missing/invalid/replaced original owner marker or different incarnation | 409 `IDEMPOTENCY_OWNER_CHANGED` |
| Same current owner, but receipt expired | 409 `IDEMPOTENCY_KEY_EXPIRED` |
| Same current owner/key with different payload | 409 `IDEMPOTENCY_REQUEST_MISMATCH` |

Old and expired receipts remain intact. They are not silently treated as misses, automatically dispatched again, or deleted. A new task requires an explicit new request key after the caller checks the existing task. Fixed response codes/messages do not expose data roots, DSNs, or raw owner/database errors.

This is an intentional tightening of keyed-generation TTL behavior, not a universal change to the idempotency store.

### Revalidate at the replay/final observation boundary

Keyed generation validates exact source identity and rejects archived/deleted sources. After cached job lookup it repeats the original source, feature, session, actor, scope, and permission checks, then compares the original incarnation under a short existing-owner lease.

If a first dispatch succeeds, its original binding receipt is persisted before final validation. A late source or owner rejection preserves that receipt, so the same retained request is not silently dispatched again. A dispatcher that explicitly raises before returning a job preserves the original failure/retry contract.

The short project lease contains only incarnation checking/return, never authorization, source reads, or JobManager calls. The existing global idempotency execution lock ordering is unchanged. No final combined source/project lease was added. No-key generation and variants retain their original route behavior and do not provision an idempotency owner marker.

## Test strategy and final results

The original seven test names and semantics remain: replay, repeated/cold replay, no-key independence, different-key independence, operation separation, actual dispatch exception/retry, and 100 rounds of three concurrent requests with exactly one dispatch per round.

All ordinary replay entries are produced by a first real HTTP request; cold replay reopens the actual persisted store. Legacy/corruption tests deliberately transform a real-produced receipt to exercise historical/malformed states, not to fabricate successful current cache state.

The only execution double is the job dispatcher. Real File project/chapter owners, scope repositories, memberships, roles, server-side opaque sessions, and registered branch manuscript owners remain active. Tests do not trust body actor data or bypass `_generation_request_context`. Dispatch counts are not model execution counts.

Final stable-source run on parent `7cfe858`:

**102 passed, 0 failed, 0 skipped**, exit 0, 16.73s.

| Component | Passed |
| --- | ---: |
| Original B non-idempotency scope | 37 |
| Updated keyed-generation/idempotency contracts | 55 |
| Current parent's complete variants file, actually rerun | 10 |
| Total | 102 |

The 55 idempotency cases include both original counterexamples, owner/actor/branch separation, payload conflicts, pre-replay and lookup-time revocation, source archival/deletion, feature disablement, missing/corrupt markers, malformed cache files, old/expired receipt preservation, wrong repository roots, decoy settings, late-rejection receipt retention, and unchanged no-key/variants behavior.

Three PostgreSQL adapter protocol cases check the original SQL/tuple parameters, exact engine, and commit/rollback/connection cleanup. Nine offline configuration cases check driver spelling equivalence and rejection of mismatched database/host/port/query/user or repository Database owners. **Real PostgreSQL is NOT_RUN**; these are not database integration claims.

Earlier focused/partial runs overlap the final run and must not be added as distinct coverage. The earlier unchanged variants concurrency failure was preserved separately; the final 10 passing variants tests are a new real run against the separately repaired C-group file, which this task did not edit.

Final evidence: `.runtime/recovery-owners-production-20261025/final-batch.log`, `final-batch.xml`, `final-batch.exit`, `final-source.sha256`, `final-source-verify.log`, and `production-frozen.sha256`. Source hashes remained unchanged during the run and `git diff --check` passed. Three existing dependency/model warnings remain.

Frozen production SHA256:

- `app/api.py`: `d40588c7190472b778b41ad67bf4ea6bc69f8613d4858ca46b8c92471fb08ed7`
- `app/idempotency.py`: `88b03eff20b10333645ae443169611adff1fe730c48453c2966f3a80d6e3214d`
- `app/services/generation_idempotency_authority.py`: `acdeb4d93a14103d4c7f0c0f50a3e57f57c3bad40ca7ba54bc2f681015941437`

## Explicit limits

This change makes safe replay decisions for **receipts that remain present**. It does not provide crash-safe or cross-process exactly-once execution when the cache file is lost, a process crashes after dispatch but before receipt persistence, or multiple processes dispatch concurrently. It does not add a globally indexed or bounded cache store; the existing whole-JSON read/write cost remains.

The final source observation and short incarnation lease are not a combined linearizable source/auth/project transaction. Changes after the last source observation remain possible. This closes the demonstrated lookup-time metadata replay gaps without claiming a zero-race system.

The request authorization callback is the existing transient hook. This change does not prove that every local JobManager worker invokes it, or resolve all historical JobManager owner isolation. It verifies the API admission/replay/final-observation boundaries tested here.

This is not full-suite, real-model, provider/privacy egress, UI, Windows, or PostgreSQL integration verification. Original restore-as-new-current/CAS/rollback/audit tests passed, but this does not establish all cross-owner history boundaries. No external Work or AudioAsset history coverage is claimed.
