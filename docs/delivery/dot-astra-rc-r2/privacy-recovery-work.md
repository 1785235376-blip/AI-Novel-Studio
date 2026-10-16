# D01 / D16: privacy and recovery work

Baseline: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`. Implemented with synthetic
fixtures only; no user database, manuscript, credentials or real model calls.

## Before → after

- AN-AUDIT-01: timeline serialization omitted the column policy. Strict policies
  are now explicit and conservatively merged with any JSON policy. Omitted updates
  preserve the existing effective policy through File and PostgreSQL API paths.
- AN-AUDIT-02: foreshadowing only echoed the request policy. Policy now persists in
  `details.privacy_level`, validated by a database CHECK constraint. Migration 018
  marks absent/invalid old values `LOCAL_ONLY` with `privacy_status=UNKNOWN` for
  review; no attempt to invent lost history. File legacy reads also expose unknown.
- AN-AUDIT-03: permissive Canon JSON overrode strict columns. All supplied policies
  now merge as LOCAL_ONLY > REDACT_BEFORE_CLOUD > CLOUD_ALLOWED. Invalid/missing
  effective policy denies remote use. The existing stricter-JSON case is retained.
- Legacy cloud context filtered only secrets. All policy-bearing collections and
  derived state/summary/style now fail closed. Redaction emits a fixed allowlist
  and recursively removes stricter nested content; no original-text fallback.
- Lore selection retains local omission auditing without returning the local base.
  Restricted/unknown evidence now withholds the whole derived memory, including
  REDACT_BEFORE_CLOUD; narrative projection filters its sources before dropping
  policy fields. A synthetic actual Node.stream capture checks private narrative
  markers are absent from the dispatched writer prompt.
- Repeated File→PG migration could reset restrictions; it now preserves the stricter
  existing value. Migrated timeline/foreshadow source IDs are resolved on normal
  update, preventing duplicate rows under the unrelated runtime UUID namespace.
- Packaged startup applies 018 through the checksum ledger, after 017, and keeps
  pre-ledger bootstrap separate. No process-ownership logic changed.
- Backup previously overwrote targets, skipped checksum validation and restored
  with `pg_restore --clean`. New `app.backup_restore` backs up to an exclusive,
  separate directory; verifies every digest and exact inventory; rejects paths,
  symlinks, corruption and known plaintext credential fields; preserves the whole
  chosen runtime-data tree; restores only into new directories and new databases.
  Interruption markers prevent false success. PowerShell wrappers use this engine.

## Evidence

`privacy-before.txt`: all three recreated audit serializer canaries leaked into
`cloud_safe_context` on the unchanged baseline. This is a code-level reproduction,
not evidence that a real external request previously occurred.

Focused command (isolated HOME/data, memory vault, Mock Provider, cloud disabled):

```
python -m pytest tests/test_r2_privacy_persistence.py tests/test_r2_backup_restore.py tests/test_r2_privacy_postgres_recovery.py tests/test_postgres_context_serialization.py tests/test_packaged_postgres_migrations_v070.py tests/test_packaging_foundation_v070.py tests/test_packaged_process_factory_v070.py tests/test_core.py tests/test_repository_contracts.py tests/test_context_migration_sync.py tests/test_lore_context_contract.py tests/test_narrative_context.py -q
```

See `privacy-recovery-focused.txt` for the latest actual focused result. New real
PostgreSQL checks exercise <=016 upgrade through 017/018 twice, invalid-write
rejection, a fresh interpreter, File import/idempotence/no-downgrade, source-ID
updates and pg_dump→new-database recovery with every table's content digest plus
sidecars. They require explicit TEST_POSTGRES_DATABASE_URL and matching client
binaries. They are NOT_RUN on the local File-only host; the delivery owner will
attach exact-SHA PostgreSQL CI results separately. Contract substitutes are not
claimed as real PostgreSQL validation.

## Known limits / local acceptance

- Actual Windows PowerShell, ACLs, DesktopHost restart/upgrade and real-user-data
  recovery: NOT_RUN. User acceptance remains pending.
- Real cloud/model execution: NOT_RUN. Provider workers own last-send boundary
  tests; this work verifies the shared context/filter contract with canaries.
- File→PG relational migration still does not convert every newer sidecar-backed
  product subsystem into SQL tables. Keep the complete runtime data directory;
  backup/restore preserves those sidecars, assets, versions and task references.
- Unknown history stays local until a user explicitly classifies it. This can
  reduce cloud context versus older permissive behavior; it is intentional.
- Credential fields in JSON are rejected/excluded; arbitrary prose/binary secret
  discovery and adversarial backup authenticity are outside this verifier.
- Restore is intentionally non-destructive. Existing targets, including a failed
  newly created target, need a new destination or separate user-reviewed cleanup.
