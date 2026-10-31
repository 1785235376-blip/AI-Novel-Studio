# Export integrity — NEW rebuild, 2026-10-29 UTC

## Identity and authorization boundary

This is new implementation and newly executed verification from public baseline `395ac26dd2de3d473e56964dbeb9ac9806facb85`. It is NOT the missing original 40-file package, does not recover its SHA or historical evidence, and is not covered by that package's GitHub publication approval. No GitHub changes were made.

- Branch: `work/hermia-export-integrity-rebuild-20261029`
- Tested production/test commit: `78dad87b4fbf3bb8f10a7abbdcfdf65027175df9`
- Tested tree: `c2608d4bb99720243faf5adea49d9fd69728d262`
- Final documentation commit is recorded in the package README. Later doc-only commits do not change tested application/test bytes.

## Changes

1. When a service-owned artifact file is missing, validate inline fallback bytes against any existing SHA256 and size receipt. Preserve legacy no-artifact reads and valid missing-file fallback without writing/re-rendering.
2. Reject encoded legacy `content` + `content_encoding=base64` exceeding the encoded bound before allocating decoded bytes; retain decoded-byte final limit and existing error behavior.
3. Reject non-regular artifacts; bounded descriptor reads use nonblocking POSIX opens, fstat type/identity/size checks and descriptor cleanup. Normalize filesystem errors to the existing result-invalid boundary. Preserve missing-file fallback.

## Newly executed results

- New 18-case baseline suite: **6 failed, 12 passed**; `baseline.log`. Uses spawn subprocess watchdog, not an inherited thread state.
- Fixed new suite plus original export jobs: **89 passed**, exit 0; `fixed.log`.
- Frozen joint 10-file regression: **136 passed**, exit 0, 70.48 seconds; `joint.log`, `joint.xml`, `joint.exit`. 950 tracked app/test file hashes unchanged before/after; `source-before.json`, `source-after.json`.
- Independent clean baseline: **9 failed, 7 passed**. Fixed same 16 plus 2 descriptor-cleanup tests: **18 passed**, exit 0. 601 Python production files unchanged. See `independent/REVIEW.md`, raw logs/XML and manifests.
- These groups overlap and must not be summed. Baseline failing tests are not counts of distinct defects.

Joint command (temporary synthetic XDG and NOVEL_DATA_PATH roots):

`python -m pytest -q tests/test_export_integrity_rebuild.py tests/test_export_jobs.py tests/test_export_owner_independent_edgecases.py tests/test_export_owner_independent_process.py tests/test_export_owner_independent_serialization.py tests/test_export_owner_readonly.py tests/test_export_snapshot_and_import_review.py tests/test_taskcenter_local_export_external.py tests/test_taskcenter_local_export_external_cases.py tests/test_taskcenter_local_export_external_singleton.py --tb=short --junitxml=docs/delivery/hermia-export-integrity-rebuild-20261029/joint.xml`

## Limits and remaining scope

POSIX/File and actual mounted FastAPI routes only. No Windows, PostgreSQL, browser UI, external models or distributed exactly-once validation. This is not a general ancestor-path replacement security guarantee. Legacy no-receipt compatibility is intentional; stricter missing/invalid receipt policy was not invented. No new dependencies, system permissions, user data or paid calls were used.

The absent later cumulative XML, idempotency, execution-owner and VTT changes are NOT included. OTIO work is independent. Original 40-file publication remains blocked on original payload availability; this new package requires its own approval before any external repository publication.
