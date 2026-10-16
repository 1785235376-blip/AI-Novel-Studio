# Project retirement checkpoint - 2026-10-16

Base/PR #47 HEAD: `045b865e5a003cac3333462d055f22099f6368d6`.
Remote main: `fed2404c8e30b44061b7139dced45b7f3301601c`.
The complete branch/PR/tag inventory and eleven verified requested SHAs are in
`remote-audit.json`. No missing SHA, rewrite, force push, or main change.

## Implemented checkpoint

- Normal and audited deletion share the original novel/scope/authorization retirement path.
- PostgreSQL deletes the novel, project grants, binding and descendant scopes in one transaction.
- File holds the original project lease and shared authorization/scope mutation locks, restoring
  snapshots on pre-commit failure. Authorization reads retain atomic-file snapshots to avoid
  project/authorization lock inversion.
- Workspace grants, memberships, unrelated projects and immutable authorization history survive.
- Creation and workspace linking share a commit; failed creations leave the public namespace before
  physical cleanup. Cleanup failure retains a hidden reclaim tombstone and logs the failure; it
  never restores a partly removed owner with old authority. An unchanged tree can safely
  roll back and propagate the original cleanup error, preserving the frozen failure contract.
- Grant validation/save holds the original project lease. Delayed DELETE requests reauthorize
  under the project lock. Reauthorized actors/scopes must match the captured request identity.
- Original PROJECT notifications are deduplicated and emitted after composite creation commits;
  failed links emit no successful owner notification.

## Validation and evidence

All receipts and failed attempts are retained under `docs/delivery/v2-development/retirement-*`.

| Gate | Recorded result |
| --- | --- |
| File real-identity API/owner retirement | 28 passed, 28 PostgreSQL cases deselected, `retirement-file-r5` |
| File lifecycle/physical cleanup/notification | 30 passed, `file-io-frozen-final.log`; original frozen test blob unchanged |
| File lock order and unrelated scope rollback | 2 passed, `retirement-lock-order-final.log` |
| File authorization/admin/initial workspace regression | 58 passed, `retirement-auth-regression` |
| Earlier expanded File regression | 248 passed, 205 PostgreSQL cases deselected, `retirement-file-regression-r2`; precedes final extra hardening |
| Real PostgreSQL retirement plus original defect reproduction | 29 passed, 28 File cases deselected, `retirement-pg-r3`; real PostgreSQL 16.15, new migrated database, instance stopped |
| Frontend/tsc/Vite/browser | Separate Canvas/Director slices; not claimed by the retirement API tests |
| Windows/GPU inference | NOT_RUN / LOCAL_REQUIRED |

The original real PostgreSQL reproduction now checks exact `403 PROJECT_SCOPE_FORBIDDEN`
for the unchanged old token and branch. It also proves new-author creation/read `201/200`,
new UUID, retired grants/binding, and fresh-author old data/asset invisibility `404`.
Other checks include data, asset, graph/import idempotency, cross-workspace recreation,
failure before/after link and original create, delayed grant/delete races, and independent
process writes surviving rollback. Skips/deselection are not passes.

Initial runner/profile/fixture failures remain evidence. A separate Windows symlink test
encountered WinError 1314 (missing symlink privilege); this is not a passing security case.

## Limits and next entry point

This checkpoint is **PARTIAL for total P0 closure**: creation must still retire or reject
orphan project authority left by a deletion performed before this fix. The next exact entry
point is `AtomicPathMutationPort.create_linked_novel`, under its existing File/PG transaction.
Remaining R3 prompt/concurrency gates and complete V2 product acceptance remain pending.
File compensation is not a claim of power-loss atomicity or completed storage/crash recovery.

Changed implementation owners: `app/project_retirement.py`, `app/api.py`,
`app/application/persistence.py`, `app/runtime_events.py`, `app/repository.py`, File/PG novel
and scope repositories, authorization protocol/service, collaboration scope service.
Tests: `test_v2_project_retirement.py`, `test_round3i_pg_incarnation.py`,
`test_v2_project_retirement_file_io.py`, `test_v2_retirement_lock_order.py`.
`test_file_project_lifecycle.py` is retained byte-for-byte; new IO cases are additive.

## Followup: pre-upgrade orphan authority and audited scope writes

The earlier checkpoint's orphan-creation gap is now implemented and validated. The retained
`scope-legacy-orphan-before` receipt reproduced stale same-id authority before this followup.
Both normal and reserved creation now retire same-workspace orphan grants/scopes inside the
existing creation transaction. A conflicting foreign binding returns exact HTTP 400 and
leaves no public owner; rollback restores prior orphan state so a legitimate retry can succeed.
Assignment rejects an absent original novel even when a historical binding still exists.

Original scope creation holds the project authority lease from parent validation through
write. Audited project/storyline/branch mutations reauthorize the original actor and active
membership inside their commit boundary. Revocation at final validation returns exact
`403 INACTIVE_MEMBERSHIP` and rolls back scope/audit writes. No second authorization owner
or manual database repair was introduced.

Final followup evidence, pinned Python/pytest 8.4.2:

- File: **62 passed**, 47 PostgreSQL cases deselected; `scope-orphan-file-r3`.
- Real PostgreSQL 16.15: initial followup **20 passed** (`scope-orphan-pg-r1`), then
  combined final candidate **48 passed**, 47 File cases deselected;
  `retirement-scope-pg-final`, fresh migrated database, owned server stopped cleanly.
- Final frozen lifecycle/additive IO/lock-order regression: **32 passed**;
  `retirement-io-lock-pinned-final`.
- Final File 62, File IO/locks 32 and combined PG 48 receipts record unchanged source
  snapshots during their respective checks. The earlier PG 29 receipt recorded concurrent
  File-only source changes; it is retained but replaced by this combined final acceptance.

This closes the specified reincarnation/orphan defects within the tested lifecycle paths.
The complete V2 remains **PARTIAL**. Prompt write-time binding, tombstone/deletion and broader
R3 concurrency gates still require their own source-backed acceptance; File compensation is
still not power-loss atomicity. See `SCOPE_ORPHAN_FOLLOWUP_REPORT.md` and the final round report.
