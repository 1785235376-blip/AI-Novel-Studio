# Bounded backend coverage

The File backend remains one original-order process. PostgreSQL uses exactly
two explicit deterministic node-ID shards, each with its original 55-minute
outer cap. File keeps its 20-minute cap. `postgres_gate.py` is unchanged.
The existing required checks `Backend / file` and `Backend / postgres` now
reconcile all three execution jobs and require every enclosing job to succeed.
No repository protection setting is changed.

Every process imports and collects its entire intended suite before assignment.
SHA256 of the exact UTF-8 node ID, interpreted as a big-endian integer modulo
the shard count, assigns each node once per profile. Within each shard, original
relative order is preserved. File uses a shard count of one. External selection,
collection errors, missing nodes, duplicate executions, unexpected skips,
xfail/xpass, incomplete setup/call/teardown, absent XML and nonzero exits fail.

The reconciler independently checks source digests, complete ordered inventories,
backend classifications, deterministic assignments, exact JUnit node identities,
outcomes, checked-out source/tree, event SHA, repository, run ID and attempt.
It rejects missing or mixed-attempt receipts. Counts are emitted only after
these checks pass. Interop lanes separately run the unchanged complete Interop
scope, with strict rejection of every skip except the opposite backend profile.

## Frozen product inventory and skip provenance

`coverage_manifest.json.gz` contains 6,799 exact product node IDs, 120 added
nodes, and test/fixture source digests. Its original set therefore contains all
6,679 baseline nodes from `bcd60afb96cc69bdfd81db619cb0121d8712f074`.
Compression preserves an existing security case whose raw parameter ID is over
4 MiB; IDs are never shortened, normalized or deduplicated by display name.

One original random UUID parameter now has the explicit ID `unknown-uuid`.
The value remains `str(uuid4())`; every original input and assertion remains.
This narrow identity migration is recorded in the manifest. Without it,
independent collections would assign a different raw node ID to the same case.

Exact historical skip reasons came from successful, revision-verified baseline
GitHub Actions artifacts, with their artifact IDs and ZIP/XML digests retained
in the manifest. Some original `skipif` reasons precede the backend marker's
skip reason; only those exact node/profile/reason combinations are accepted.
No new runtime or missing-database skip is accepted for an applicable PostgreSQL
contract.

The two original File TCP tests are intentionally opt-in in the full suite.
Their original separate `RUN_B10_TCP_SYNC_TEST=1` command remains unchanged and
runs once. The verifier requires its independent `sync-tcp.xml` to contain
exactly those two passed tests, without failures or skips. These two results are
reported separately and never inflate the complete suite's unique counts.

Infrastructure self-tests live beside the CI helpers and run in an explicit
workflow step. They do not enlarge or replace the product collection.

## Evidence boundaries

Successful reconciliation means complete collected backend coverage across the
PostgreSQL shards. It is not a claim that the PostgreSQL suite ran in one process,
or that all cross-shard global-state/order interactions are equivalent. File
retains its monolithic interaction coverage; Interop retains mixed old/new tests.
No extra global cleanup, forced garbage collection, timer suppression, event
disabling or weaker product assertion is introduced to make shards pass.

The prior two 55-minute cancellations remain failed/incomplete evidence. An
inventory or expected count is never a test pass. Do not sum overlapping
Interop, push/PR, or separate TCP results into complete-suite totals. Native
desktop/manual acceptance boundaries remain unchanged.

## Intentional test changes

There is no CI auto-blessing or automatic manifest regeneration. Intentional
product test changes require review of the complete source and node diff,
preservation of the original baseline set, independent successful collection,
and explicit review of any skip changes before the frozen manifest is updated.
Never derive a broader skip allowlist merely from a failing current run.

Run the standalone gate tests with:

`python -m pytest -p no:cacheprovider -q .github/ci/test_suite_coverage.py .github/ci/test_coverage_reconcile.py`

Their negative fixtures cover missing/duplicate/unassigned nodes, wrong source
or attempt, incomplete XML or phase sequences, xfail/xpass, unexpected skips,
nonzero exits, source changes, and missing/altered separate TCP evidence. Actual
synthetic pytest subprocesses exercise File-one/PostgreSQL-two receipts and a
4 MiB node ID without claiming real database test execution.
