# Verify restored File bytes before manual recovery validation

The existing R2 `verify` command checks a backup. The additive `verify-restored`
command compares a completed restore directory to an explicitly selected, trusted
R2 backup. It is read-only: it does not repair, delete, write receipts, select live
data roots, start services, discover installations, or contact a database/provider.
Existing backup/restore commands and receipt formats are unchanged.

Stop the application and **all writers to both directories**, and keep them stopped
until verification ends. From the repository root:

```sh
python -m app.backup_restore verify-restored --backup /separate/trusted-backup --destination /new/recovery --offline-confirmed
```

`--destination` is the complete original restore output, containing `novel_data`
and `restore-receipt.json`, not just its `novel_data` subdirectory. Choose both
paths yourself. Neither may contain the other. Missing offline confirmation fails.
The Python API is `verify_restored_directory(backup, destination,
offline_confirmed=True)` in the original `app.backup_restore` module.

## Meaning of success

Exit 0 returns a small JSON object with `status: file_bytes_verified`, verified
File-member/byte counts, `application_compatibility: not_verified`,
`database_validation: not_applicable` (or `unsupported`), and
`switch_performed: false`. No filenames, file content, application-version strings,
or absolute paths are included. This is byte-level evidence only. It does not
prove application/version compatibility, valid relationships, usable credentials,
Windows ACL behavior, or operational readiness. Continue separate application
and platform recovery validation before any manual live data-root switch.

For a PostgreSQL-containing backup, the original backup verifier still checks the
dump's bytes. The target comparison excludes `database.dump`, because the original
restore does not copy it into the target tree. Success verifies sidecar files
only, always reports `database_validation: unsupported`, and does not connect to
or validate the recovered database. A receipt's database flag is not database
validation. A synthetic dump in automated tests is not a real PG recovery gate.

## Checks and limits

- Reject linked roots and any linked ancestor (including legitimate symlink-based
  paths); reject symlinks, hard-linked files and special files anywhere in either
  tree. Paths containing `..` are rejected. Inputs must be trusted directories.
- Metadata-only preflight rejects incomplete markers and unlisted files/directories
  before opening any unexpected file body. Target membership is exactly the
  manifest's File members, their ancestor directories, and `restore-receipt.json`.
  Even an extra empty directory fails. The backup must likewise have exact members.
- Reuse original manifest path, SHA-256, size and JSON-credential validation. Target
  files are compared by byte size and SHA-256; they are not parsed as application
  records. Expected story/binary content is not a credential-discovery system.
- Require exactly the original receipt's five fields: backup/app versions and full
  manifest file count must match; `database_restored` must be a Boolean matching
  the manifest; `restored_at` must parse as a timezone-aware ISO timestamp. A receipt
  is completion metadata, not cryptographic provenance or proof of a DB restore.
- At most 100,000 entries per tree, including root and directories; depth at most
  64 below root; manifest member paths at most 4096 characters; manifest at most
  16 MiB, each expected backup JSON member at most 16 MiB for credential checking,
  and receipt at most 64 KiB. Limits fail
  closed. File hashing streams in the original 1 MiB blocks. There is no total-file
  byte or elapsed-time limit; large trusted backups can take substantial time.
  The shared original backup checks use the already bounded parsed manifest.
  In this command only, expected JSON credential checks read at most their cap
  plus one byte before parsing. An oversized legitimate JSON file is a policy
  limit failure, not a claim of corruption. Existing commands retain their old
  defaults. Parsed JSON objects can use more memory than their encoded bytes.
  Keep both trees unchanged throughout verification.
- Recheck inventory and metadata (identity, type, size, modification/change times)
  after hashing. This detects ordinary concurrent changes but is **not an atomic
  snapshot**, a lock, or protection against a malicious filesystem actor. Path
  checks and later opens have race windows. Do not run on adversarial or active
  trees. Checksums cannot authenticate a backup whose manifest was also replaced.

Failures exit 1 with a bounded code (no raw exception or path):
`RESTORED_OFFLINE_REQUIRED`, `RESTORED_UNSAFE_ROOT`, `RESTORED_OVERLAPPING_ROOTS`,
`RESTORED_UNSAFE_ENTRY`, `RESTORED_INCOMPLETE`, `RESTORED_LIMIT_EXCEEDED`,
`RESTORED_BACKUP_INVALID`, `RESTORED_MEMBERSHIP_MISMATCH`,
`RESTORED_RECEIPT_INVALID`, `RESTORED_CONTENT_MISMATCH`, `RESTORED_TREE_CHANGED`,
or `RESTORED_INPUT_INVALID_OR_UNREADABLE`. Inspect the selected trees manually;
the verifier never repairs failures. CLI argument usage errors retain argparse's
usual diagnostics; don't put secrets into command-line arguments.

## Acceptance scope

`tests/test_restored_file_verification.py` exercises original File backup/restore,
fresh-process CLI success/failure without application imports, byte preservation,
rejected unsafe/malformed/interrupted inputs, bounded/redacted errors, mutation
checks, and reopening restored content with the original asset service. Original
R2 backup tests remain separate regression coverage. Real PostgreSQL recovery,
Windows PowerShell/ACL/desktop validation and user data are separate acceptance
gates; no PowerShell wrapper is added here.
