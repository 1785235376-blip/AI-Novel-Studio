# Shared owner integration proposal and authorized implementation

This proposal was initially paused at the user's shared-owner boundary. After
review, the user explicitly authorized this branch to implement the precise
shared-reader and coordinator changes. They are implemented in source freeze
`18731becb0060d3006dd3f5ab8fe0c6cc00c0266`. The historical rationale below is
retained; the final delivery report and evidence describe the verified result.
No Hermia branch was merged and store.py remains identical to the baseline.

## Existing read boundary

`app/repositories/file/mutation_coordinator.py::workspace_mutation` always calls
`lock_dir.mkdir(parents=True, exist_ok=True)` and opens a lock with `a+b`.
`_lock_file` initializes an empty Windows lock with one byte. An initialized
fixture can have identical file hashes after GET while still using write-capable
opens. Checking existence first does not prevent a subsequent create race.

There is no existing-only coordinator capability to reuse. A query-layer
replacement, monkeypatch, skipped lease, or precreated lock would not meet the
original concurrency contract. No such workaround is introduced.

## Smallest strict-mode owner change for review

1. Owner adds an explicit request/context capability to `workspace_mutation`
   that retains the same process lock, reentrant depth, cross-process lock and
   lock ordering. Default behavior is unchanged.
2. In existing-only mode: no mkdir; open the exact existing lock without create
   or truncate; reject symlinks/reparse points/nonregular files and replacement;
   verify a nonempty Windows lock before `_lock_file` so initialization cannot
   write. Hold the admitted handle through unlock. The original owner must
   define disappearance/replacement behavior for Windows and POSIX.
3. `workspace_mutation_lock` must specify whether strict calls may add process
   registry entries, or require an already registered original lock and reject
   otherwise. Tests snapshot registry keys, depth, directories and file writes.
4. Query routes may then expose a validated explicit strict opt-in using this
   capability before original admission. Missing facilities return one fixed,
   private unsupported code with no-store. Initialized original facilities must
   support actual successful pages. Both aliases and all original reauthorization
   checks remain. No new initialization route is proposed here.

Affected callers are the original `ExperimentalStore.read`,
`CreativeProjectStore.owner_lease` / `incarnation` via project operations,
and AssetLibraryService's original asset/project leases. They must not gain
parallel locking logic.

## Smallest full-chain resource integration for review

The context budget already spans the usage route's original invokers, but the
following readers do not consult it:

- `app/repository.py::read_json` reached by `FileRepository.get_novel`.
- `app/creative/project_store.py::_read_marker` (a module-level function;
  `MAX_MARKER_BYTES=256`, reads at most 257 bytes to detect overflow today,
  rejects more than 256 before JSON decoding, not charged cumulatively).
- `app/repositories/file/identity.py::FileIdentityRepository._read`.
- `app/repositories/file/scope.py::FileScopeRepository._read`.
- `app/repositories/file/scope.py::FileAuthorizationRepository._read` (the
  authorization class shares scope.py; there is no file/authorization.py).
- At baseline, `AssetLibraryService._verified_content` reached by Graph 3/4/5
  did not charge binary bytes to the usage budget. Its normal integrity reader
  now calls the same cumulative read_binary admission while retaining digest
  validation. The separate optional native bounded-content reader is not a
  claimed whole-application budget boundary.

These paths and symbols were verified against the fixed asset-query baseline.
Their required integration is an optional bounded raw-byte callback before JSON
decoding, sharing the same request budget on every reread. No permission result
cache or suppressed authorization is acceptable. These are shared authority
owners; only their optional raw-read hooks were authorized and implemented.
A generic process-wide replacement of open/json.loads is explicitly excluded.
The narrow AssetUsageRequestBudgetMiddleware is registered last/outermost in
app.main so original packaged/collaboration pre-route reads share the same fresh
request budget. It changes only the three canonical paged GET surfaces, and
keeps original authorization and query-validation ordering.

The binary owner needs its own optional usage-budget integration before/while
reading, while retaining existing file integrity/hash checks and asset-list
budget behavior. Rejecting or skipping all schema 3/4/5 consumers would narrow
the existing supported query contract. This path also remains paused here.

Hermia's pending `ExperimentalStore._file_bytes -> _file_snapshot -> _file_read`,
duplicate-key rejection and lifecycle protocol must preserve the existing
`budget.read` hook or receive an owner-reviewed adapter. This branch does not
edit store.py or merge Hermia's branch.

## Review acceptance

The initial review requirements were:
deterministic lock removal/replacement, project same-ID recreation, concurrent
revoke, unavailable facilities, an initialized strict success, and cumulative
all-authority-read tests. The final File payload and strict-mode evidence is
linked from the delivery report. Full OS I/O/metadata syscalls, hard CPU timeout,
RSS, PostgreSQL and cross-worker snapshots remain outside those guarantees.
Python admission counters and tracemalloc do not impose a process RSS hard limit.
