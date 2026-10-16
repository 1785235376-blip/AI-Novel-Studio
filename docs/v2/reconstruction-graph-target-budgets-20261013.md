# Graph target-budget compatibility repair

## Contract preserved

The original `GraphPreflight` and `GraphRunCreate` request contracts again accept
at most 16 target IDs. Schema-1 and schema-2 graph definitions remain limited to
16 nodes. The additive schema-3 media graph still accepts 24 nodes and targets.

`GraphMediaPreflight` and `GraphMediaRunCreate` reuse exactly the original wire
fields. Existing routes admit either bounded envelope, then the original service
and executor select and revalidate the allowance from the saved graph definition.
A parsed media subclass does not grant a larger allowance to an old-schema graph:
its dumped fields are validated again. No caller-supplied schema flag is accepted.

The original version check precedes saved-schema target narrowing, preserving the
409 conflict response for a stale 24-target request after a graph downgrade.
Run admission repeats the schema selection against the row read inside the
original transaction. Planning validates its input on every call, including
persisted selected closures and the validated durable schema-3 snapshot used for
stopped media-review bookkeeping when the current graph was edited or is missing.

The following remain unchanged:

- Empty selection expands to all enabled nodes; the existing UI can submit the
  resulting 24-target list when creating a media run.
- A single target can have a valid 24-node upstream closure.
- Request field serialization, request/preflight digests, idempotency and topology
  checks, original File/PostgreSQL owners, step limits, review and scope guards.
- V1, Interop, frontend behavior and Graph's exclusion of standalone CPU cutout.
- All original test assertions, skip declarations and verification harnesses.

## Additive regression coverage

- Original and media envelope budgets, strict fields and IDs, schema-flag
  rejection, and parsed/model-constructed subclass revalidation.
- Schema-1/2 16/17 and schema-3 17/24/25 boundaries through services and both
  mounted API aliases, including duplicate and unknown target rejection.
- Empty-selection expansion, existing body/digest compatibility, idempotent
  retries, one-target/24-node closure, real persistence reopen and local execution.
- Saved-schema downgrade, stale conflict precedence, transactional schema reread,
  actor/scope isolation, late revocation rollback and unchanged durable state.
- A real local audio-trim candidate paused at the original owner's review
  reservation before promotion. Reopened 24-node runs recover that reservation
  after current-graph downgrade or deletion without rendering, sending,
  promoting or advancing the workflow. Corrupt durable selections fail closed.

The recovery fixture uses an owned synthesized WAV and local FFmpeg. Other new
execution checks use original local text rules. No actual model, remote provider,
paid API, user computer, or Windows runtime acceptance is involved.

## Verification

The pinned CI Python environment and unchanged `scripts/run_v2_checks.py` were
used for both final runs. The fresh PostgreSQL run also used the unchanged
`scripts/run_v2_postgres_checks.py` against a newly initialized disposable
PostgreSQL 17 cluster and a database verified empty before migration.

- File: **848 passed, 393 skipped**, zero failures.
- Fresh PostgreSQL: **848 passed, 393 skipped**, zero failures.
- Each run includes 55 passing additive cases from the three new test files;
  the parametrized owner tests exercise both mounted aliases on each backend.
- The broader selection includes all four original Graph suites and original
  asset-provider, local-image, media API/lifecycle, image transport, independent
  workspace, manual-mask and CPU-cutout regressions.
- The two original target-budget assertions pass unchanged. Original assertions
  and skip policies were not weakened; backend/feature skips remain explicit.
- Source snapshots remained unchanged during both runs and matched the final
  source files. Both captured log hashes were verified.
- All 20 original migrations were applied unchanged; PostgreSQL shutdown and
  cleanup completed successfully.
- The only warning was the existing FastAPI/Starlette TestClient deprecation.

Independent read-only review also checked original assertions, route-union
limits, constructed-subclass rejection, and baseline-versus-repair preflight and
request-digest equality for empty, explicit-24 and one-target/24-node selections.

This is local backend compatibility evidence. Actual model/provider execution,
browser-native display and user Windows acceptance remain outside this check.
Raw logs, runtime configuration, generated inventories and disposable database
state are not part of the source commit.

## Root integration check

After integration at local source commit
`e3a28c1bad8f5c4187266c7625cfa333fcc9f317`, the unchanged original Graph contract
suite and all three additive target-budget suites passed **268 tests**, with
**51 opposite-backend skips**, in the File profile. This check used the original
verification wrapper and does not replace the separate fresh PostgreSQL result.
