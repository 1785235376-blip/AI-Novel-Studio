# Migration and recovery

## Database migration

`database/migrations/018_context_privacy.sql` follows the existing 017 checksum-ledger migration. It normalizes unknown or malformed foreshadowing policies to LOCAL_ONLY/UNKNOWN, constrains persisted JSON policy, and changes new privacy defaults to conservative values. Existing stricter Canon/column/JSON policies merge conservatively. The migration cannot recover already-lost historical intent.

Packaged bootstrap separates pre-ledger <=016 application from ledgered 017/018. Never edit a previously applied migration checksum to make an existing installation pass. Back up first and test upgrade on an isolated copy.

Screenplay `edit_version` and server-owned `version_history` live in existing File/PG payloads; no parallel screenplay identity or destructive schema rewrite. File mutations use process locks; PostgreSQL whole-metadata writers share the novel row lock. Old payloads are normalized by the version adapter.

## Sidecars

New source privacy, workbench records, review threads, planning runs, import checkpoints, media jobs and visual-reference metadata live under the selected runtime data root. Their scope/owner fields are server-derived. Backups must include the actual `NOVEL_DATA_PATH`, not only the source checkout. Secret stores remain outside ordinary export archives.

## Recovery

Use `app.backup_restore` or the updated PowerShell wrappers. Require offline confirmation, new destination directories and new databases. Every archived file is inventoried and hashed; traversal, symlinks, malformed manifests, extra/missing members and detected plaintext credential fields are rejected. Restore does not overwrite targets or invoke `pg_restore --clean`. Interrupted restore keeps an explicit marker.

Compare chapter/asset bytes, source versions, policy/status fields, task snapshots and all PostgreSQL table digests in a fresh instance. The R2 tests cover same-process and fresh-process reads plus real-PG migrations/dump/restore in the hosted disposable database. Final-SHA results are in TEST_RESULTS.

If recovery fails, retain the source backup and damaged target for inspection. Retry only into a new owned target. Do not automatically delete or reset the user's original database, runtime profile or creative work.
