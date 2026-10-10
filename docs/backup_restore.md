# Verified backup and recovery (R2)

Stop the application and all other writers first. Backup is an offline operation;
PostgreSQL dump consistency alone cannot synchronize concurrently modified assets
and filesystem sidecars. Use a separate destination outside the source/data roots.
The new format is `0.2.0`; app version remains a separate field.

## File backend

From the repository root:

```powershell
scripts/backup.ps1 -Destination D:\Backups\Novel-R2 -OfflineConfirmed
scripts/restore.ps1 -BackupPath D:\Backups\Novel-R2 -Destination D:\Recovery\Novel-R2
```

For DesktopHost or a non-default `NOVEL_DATA_PATH`, supply its actual data root:

```powershell
scripts/backup.ps1 -Destination D:\Backups\Novel-R2 -DataDirectory "$env:LOCALAPPDATA\AI-Novel-Studio\UserData\NovelData" -OfflineConfirmed
```

The same engine runs on Linux/macOS or an isolated test host:

```sh
python -m app.backup_restore backup --source /path/to/app --data-directory /path/to/actual/NovelData --destination /separate/backup --app-version 0.7.0 --offline-confirmed
python -m app.backup_restore verify --backup /separate/backup
python -m app.backup_restore restore --backup /separate/backup --destination /new/recovery
```

Only `novel_data`, prompts, workflows, config and migration files are copied.
The entire selected runtime data root becomes `novel_data` in the backup, preserving
chapters, document history, assets, identity/membership data, snapshots and job
sidecars as bytes. Application/model binaries are installed separately. Configure
the recovered application to use the recovered `novel_data` only after validation;
this tool does not switch a live installation or start services automatically.

## PostgreSQL backend

Use PostgreSQL client tools compatible with the server (`pg_dump`, `pg_restore`
available on PATH). Explicitly select an environment variable containing the
source URL with `-DatabaseUrlEnv SOURCE_DATABASE_URL` / `--database-url-env SOURCE_DATABASE_URL`.
Restore uses a different variable pointing to a NEW database on the recovery
server. The restore identity needs permission to create that database. Credentials
stay in process environment, never CLI arguments or the manifest.

A database dump must restore together with its filesystem sidecars. The tool
refuses to silently skip a missing DB target. It refuses an existing target database,
including an empty one, and refuses system database names. `pg_restore` uses a
single transaction, error-stop, and no `--clean`. A failed DB import leaves the new
empty database and an incomplete filesystem target for inspection. It does not drop
anything, retry into an existing target, or roll back by deleting user data.

## Integrity and safety

- SHA-256 and size for every backed-up file; exact membership check before restore
- Missing, extra, duplicate, changed, traversal and symlink members rejected
- Existing backup/restore directories always refused, even if empty; `-Force` refused
- Interrupted work keeps `.incomplete` / `.restore-incomplete`; never reports success
- OS vault, environment/private-key files excluded; plaintext credential fields in
  JSON cause a safe failure before backup publication. Fictional `secrets.json`
  remains protected story data and is backed up normally.
- Raw prose and arbitrary binary assets are not a secret-detection system. Do not
  store real credentials in story content. Database credential-vault contents are
  not exported; the OS vault must be reconfigured separately on the new machine.
- Checksums detect corruption, not an attacker who can replace the manifest too.
  Restore only a trusted backup. A PostgreSQL dump is executable database content.
- Legacy `0.1.0` backups require manual review; the new verifier refuses them rather
  than claiming that their incomplete inventories satisfy the new contract.

Linux isolated File roundtrip, corruption, no-overwrite, symlink/path safety,
credential exclusion, interruption and fresh-process checks are automated in
`tests/test_r2_backup_restore.py`. Real PG migration/dump/restore checks are in
`tests/test_r2_privacy_postgres_recovery.py`. Actual Windows PowerShell/ACL/desktop
recovery and the user's own data remain separate acceptance gates.
