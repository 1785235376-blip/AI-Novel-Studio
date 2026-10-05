# Shared fixes eligible for later backport review

This file records candidates only. The frozen V1/PR #37 and R3/PR #38 branches
are not modified by this work. A candidate is not a backport approval or a claim
that all U02 data-loss cases are closed.

## U02-FILE-01: project deletion versus lazy chapter migration and late writes

Status: implemented and locally contract-verified on the dedicated R4/R5/UX
branch. No PostgreSQL, native Windows, production, or user-acceptance claim.

### Inherited evidence

The pre-fix synthetic reproduction paused `ChapterRepository.get` immediately
after `FileRepository.chapter` read Markdown, completed `delete_novel`, then
resumed the read. Lazy migration recreated `documents/chapter-0001.json` and its
project directory, and `list_novels` returned the ghost project. Two independent
executions reproduced that sequence. The saved baseline receipt dated
2026-10-05 records `absent_after_delete`, `recreated_by_read`, and
`ghost_list_entry` all true; local source `e6cae2440478bb8c70cdc0471c47319790979c6c`
had remote-equivalent source `4c43add056ba541c196a683fd7eee61534b38b6f` and tree
`91135f6ec842bf443a2c5fd1dda58ea7bda62d2f`.

The separately observed hosted-CI `DirectoryNotEmpty` deletion error is retained
as a separate inherited symptom. This reproduction does not identify every
writer involved in that CI failure, and this fix does not claim to close it
universally.

### Change and compatibility

- Reuse the existing reentrant thread plus OS-file `workspace_mutation`
  coordinator. The project-specific lock is at the data root, outside the
  removable project tree; lock identity uses the resolved project path. The
  lock file must not be deleted while any cooperating process can still use it.
- Guard each participating operation from its initial existence/read check
  through its final write/return, not merely `atomic_write`. A delete waits for
  an already-running operation. A later operation acquires the same lock, checks
  existence again, and raises `FileNotFoundError` instead of recreating a project.
- Participants are `FileRepository`, `ChapterRepository`, File novel/chapter
  facade operations, and the File portions of `AtomicPathMutationPort` project
  creation/deletion and compensation. Audited chapter operations retain their
  `_file_save_lock` context-manager entry point, now using the same project
  guard for capture/save/audit/rollback.
- Audited operations acquire the authorization lock before the project lock.
  Their nested repository calls reenter the project guard. Direct repository
  calls do not acquire authorization locks. This preserves existing permission
  checks and avoids an inverse project/authorization lock order.
- Legacy Markdown still migrates lazily to a version-1 `MIGRATED` package.
  Existing document source, timestamp, version CAS, immutable history metadata,
  restore, archive and chapter-order semantics remain in place. Participating
  missing-project reads/writes now consistently fail with `FileNotFoundError`.
- No migration, database change, rmtree retry loop, swallowed deletion error,
  irreversible conversion, dependency addition, or frozen-branch edit.

### Regression evidence

Environment: Linux, Python 3.12, File backend, owned disposable synthetic data,
offline/mock providers, no real user manuscripts or model calls. Tests run via
the isolated runner and existing project virtual environment. These are results
for source commit `b37860b2a8b649ab17933185980a5dc1f3166664`, not cumulative
historical totals. A later independent-review correction is recorded below.

`tests/test_file_project_lifecycle.py` adds 24 deterministic coordinated tests:

- Paused lazy read/save/duplicate/rename versus deletion across repository
  instances; no recreated directory or ghost list result after completion.
- Delete-first rejection of late reads, saves, creates, summaries, metadata,
  character writes, archive and move operations.
- Independent spawned processes for read/delete, save/delete, delete/save, and
  chapter CAS. Competing version-1 saves have exactly one version-2 winner and
  one history row; the losing process receives `VersionConflict`.
- Legacy migration and revision metadata, archive/restore, unrelated-project
  progress, persistent external lock location, and explicit project recreation.
- Deletion errors remain visible and release locks.
- Audited chapter failure/rollback versus both deletion paths, project-delete
  audit compensation, and audited calls arriving after deletion.

Final combined targeted command on 2026-10-05:

```text
python -m pytest -q \
  tests/test_file_project_lifecycle.py \
  tests/test_chapter_concurrency.py tests/test_repository_contracts.py \
  tests/test_chapter_archive_lifecycle_v070.py tests/test_chapter_markdown_contract.py \
  tests/test_v056_atomic_persistence_integration.py tests/test_v060_project_path_persistence.py \
  tests/test_application_contracts.py tests/test_collaboration_application_service_v056.py \
  tests/test_authorization_foundation.py tests/test_collaboration_http_boundary_v056.py \
  tests/test_phase4_characters.py tests/test_phase4_locations.py tests/test_phase4_timeline.py \
  tests/test_phase4_foreshadowing.py tests/test_phase4_relationships.py \
  tests/test_phase5_outline.py tests/test_phase5_volumes.py tests/test_phase5_scenes.py \
  tests/test_phase5_story_routes.py tests/test_phase7_adaptation.py tests/test_phase8_screenplay.py \
  tests/test_r2_acceptance_integrity.py tests/test_atomic_write_windows.py \
  tests/test_v059_collaboration_admin.py
```

Result: **123 passed, 2 skipped, 1 warning**, 10.64 seconds. The two real-PG
contracts were skipped, not passed. The warning is the existing Starlette/httpx
TestClient deprecation. `test_atomic_write_windows.py` is host-run unit coverage,
not native Windows execution. `git diff --check` passed.

Additional inherited compatibility command on the same source:

```text
python -m pytest -q tests/test_screenplay_cas_history.py \
  tests/test_r2_privacy_persistence.py tests/test_r2_import_apply_journal.py \
  tests/test_revision_context_snapshot_v056.py tests/test_stability_v04.py
```

Result: **62 passed, 1 warning**, 2.85 seconds. The warning is the same existing
TestClient deprecation. This separate run is not added to the combined count.

An early development run stopped during collection after `_file_save_lock` was
removed; the audited caller dependency was then integrated rather than dropped.
The complete final targeted command above was rerun successfully. Initial
collection failures are not counted as passing assertions.

### Remaining boundaries and backport conditions

- Coordination is opt-in, not a filesystem sandbox. Existing direct-path
  canon/lore repositories, backup/import utilities and other services not using
  this guard can still race deletion. In particular, some lore reads create
  directories. No universal `DirectoryNotEmpty` or resurrection closure is
  claimed for those paths.
- Explicitly creating a new project with the same ID remains allowed. There is
  no incarnation token/tombstone, so a stale caller arriving after ID reuse is
  outside this guarantee. CAS alone cannot identify a previous incarnation.
- File multi-file compensation is not a crash-safe database transaction. Shared
  authorization/scope files retain their existing broader concurrency limits;
  this change is not a cross-project or distributed authorization transaction.
- Verified process coverage uses independent spawned processes on Linux and
  local storage. Native Windows, fork-while-locked, network-filesystem locking,
  crash/restart fault injection, and large-project throughput are not verified
  here. Participating operations serialize per project; no performance claim.
- Before any requested backport: review applicability to the frozen target,
  port only this small shared fix plus tests, rerun its full required File/PG/UI
  regressions on that target, and obtain the separate user authorization. Do not
  rewrite the prior acceptance evidence or treat this follow-on as accepted V1.


### Independent-review correction: internal delete backup listing

An independent Astra audit pinned to
`b37860b2a8b649ab17933185980a5dc1f3166664` found a **MEDIUM** issue within the
participating list/delete paths: while `AtomicPathMutationPort.delete_project`
was paused after renaming a project to `.<id>.delete-backup-<UUID>`,
`FileRepository.list_novels` treated that backup directory as a new project.
It exposed the original title and chapter count under a dead backup ID because
the temporary directory used a different lifecycle-lock identity. Successful
final cleanup did not erase this transient listing defect.

The correction excludes only the exact reserved
`.<project>.delete-backup-<UUID>` directory namespace before project listing.
Normal project IDs created by the application cannot occupy this namespace.
Generic hidden directories, ordinary names containing `delete-backup`, legacy
directories without `novel.json`, and imported metadata-ID mismatches remain
visible under their existing semantics. This is internal-entry filtering, not
suppression of directory-deletion errors or broad invalid-metadata filtering.

Two new synthetic regressions pause the real audited delete after rename,
verify an unrelated project remains visible and the backup does not, then
verify successful deletion or audit-failure rollback. One additional case
protects ordinary and legacy project names: 27 lifecycle cases in total.

The reviewer's unchanged reproduction was rerun against the correction on
2026-10-05 and returned:

```json
{"during_delete": [], "original_absent": true}
{"after_delete": [], "errors": [], "delete_alive": false}
```

Verification of the corrected source:

- Focused lifecycle, repository, project-path and collaboration-admin selection:
  **50 passed**, 1 existing TestClient deprecation warning, 6.03 seconds.
- The complete combined targeted command printed above, rerun with the three
  added regressions: **126 passed, 2 skipped, 1 warning**, 9.62 seconds.
  The real-PG skips and existing warning retain their original meaning.
- `git diff --check`: passed.

The original audit finding and earlier test results are retained here as
provenance. The remaining coordination and platform boundaries above still
apply; this correction is not a claim of universal deletion-race closure.
