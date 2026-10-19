# Compatibility, migrations, resumability and operations contracts

## 1. API / DTO / schema compatibility

- Public HTTP surfaces keep stable paths (/api), with /api/v1 aliases where the repo
  already mounts them; edition/feature gates apply to both prefixes (verified by
  tests/test_public_edition_boundary.py).
- JSON payloads are bounded by strict models with explicit max_length/ge/le and extra-field
  rejection where untrusted input is accepted; new optional fields are additive and must
  not change existing literal contract values.
- Generated artifacts are pinned: API_CATALOG.json + detail gzip bind source hashes and
  operation digests; contracts/local-interop/v1/parity-manifest.json binds schema files and
  the generator (LF bytes on every OS). Regenerate with
  scripts/refresh_product_api_catalog.py and python -m local_interop_protocol.generate_contracts.
- Error codes are explicit literals (e.g. EXPERIMENTAL_FEATURE_DISABLED,
  STUDIO_TIMELINE_RECEIPT_INVALID, COMIC_*); clients and regression tests may pin them.

## 2. Database migrations, rollback and project generations

- Migrations live in database/migrations/001..020_*.sql; the isolated engineering profile
  applies 001..020 once to a disposable database (v2_pg_subset on loopback). The full
  PostgreSQL suite remains BLOCKED_ENVIRONMENT on this Windows host (D-07); the focused
  real-PG contract subset executed 118 passed / 0 failed.
- PostgreSQL and File storage share repository interfaces; destructive operations use
  compensating transactions and cross-file rollback (e.g. project retirement rename/restore
  path with a bounded Windows retry introduced in round 3).
- Project identity/generation: scope rows bind project_id to workspace_id; a project
  incarnation/digest fences late writes after retirement or branch/scope changes.
  Cross-project and post-revocation writes fail closed.
- Migration verification limit: a full migration/rollback matrix against a populated
  PostgreSQL cluster was not executed in this environment; treat migration rollback as
  NOT_RUN except the disposable create/apply path.

## 3. Crash safety and unknown state

- File writes use atomic replace; receipts are read with bounded byte snapshots and
  identity checks. Round 3 added NTFS ChangeTime to the receipt snapshot
  (app/windows_file_identity.py) so a same-size in-place rewrite that restores mtime is
  rejected on Windows too.
- Job unknowns are never auto-replayed; recovery is an explicit action. Queue/cancel paths
  keep the single app/jobs.py manager.

## 4. Logging, backup, disk and supply chain

- app/structured_log.py provides bounded structured logging; benchmark and CI paths redact
  *_API_KEY/_TOKEN/_SECRET values, and the engineering runner strips credential environment
  values before spawning test processes.
- Backup/restore owner: app/backup_restore.py (paths/hashes/verification). Engineering
  rounds keep generated artifacts under <repo>/.runtime or an external owned run directory
  and delete regenerable payloads after evidence is archived (see BASELINE disk sections).
- Supply chain: packaging locks (packaging/requirements-windows.lock.txt,
  packaging/windows-runtime-inputs.json) pin SHA256 for runtime downloads and wheels; the
  portable launcher uses the bundled isolated Python. No credential or model-weight files
  are tracked (scripts/verify_public_edition.py).

## 5. Known limits

- Full PostgreSQL migration/rollback and backup/restore re-proof are not executed this
  round (D-07 environment block); the focused PG subset is the current real-PG evidence.
- Windows installer/upgrade/uninstall and WebView2 acceptance remain LOCAL_REQUIRED (M12).
