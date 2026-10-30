# Verified backend publication checkpoint — 2026-10-30

This is a cumulative backend/test publication candidate for an independent branch. It does not modify `main`, merge a pull request, publish a Release, or claim CI passed. It is not the previously lost original 40-file package and does not reconstruct that package's missing evidence.

## Source identity and upload base

- Verified source commit: `1349026fd209c048f583859f8a9e41af7301160b`.
- Verified source tree: `e8dc68c6fe2ea10b66aec500799f4c817b19a283`.
- Existing published upload base: `2e52c7470593e1c49b08d26a66cd73e2c71b64a0`, tree `f3eb900f5dbd9c2bcf03288048ed08a91a1612c8`.
- Common original product baseline: `395ac26dd2de3d473e56964dbeb9ac9806facb85`.

Relative to the existing upload base, the verified source has 106 changed files: 15 application Python files, 3 historical SQL migrations restored verbatim, 39 test files, and 49 historical evidence/document files. This new directory adds curated public verification evidence and indexes only. All application, migration and test bytes remain exactly those of the verified source commit. The original worktrees and untracked work are not overwritten.

## Included changes

1. Bounded export artifact fallback/read integrity, XML character validity, binary-budget and format-idempotency fixes.
2. Existing public request-budget context isolation, TaskCenter deadline/reader-receipt protections, export worker ownership, cancellation and cleanup integration.
3. External WebVTT HTML reference decoding and caption literal round trips; explicit OTIO clip-link LOSS reporting and strict preview diagnostics.
4. Explicit opt-in `EXTERNAL_NATIVE` OTIO edits. Default `STRICT` behavior and historical replay digest stay compatible; only supported stale trim/speed/gap hints may yield, with explicit acknowledgement and source/context binding.
5. Restored original PostgreSQL migration assets 018–020, verified with the existing migration runner; explicit synthetic-test database selection and removal of unsafe test dotenv fallback.

No frontend changes, user manuscripts/media, production database contents, credentials, `.env`, installed PostgreSQL binaries or temporary database clusters are included. Untracked source-media audit code is excluded. Work-owned audio quota/history/restore development is not included or claimed complete.

## Verification ledger (do not add overlapping counts)

- `342ad72626667d622040d8eca4d6c9ab8d1e2309`: fresh 50-file protection group **958 passed, 11 Windows skips**, exit 0; separate independent group **14 passed**. Earlier timeout and unavailable old raw logs remain disclosed in the copied report. These are not results for the latest commit.
- `651aa1a5ef7fbff3866f920216baa975f8ffea54`: strict OTIO diagnostic group **77 passed**; separate independent group **93 passed**.
- `9f8ca0aff280eb7c055ae47ee3a610022fd90a3d`: explicit OTIO mode group **114 passed**; independent group **110 passed**.
- `3139927b997c18048704aa958a73787fa12a7251`: **34 passed, zero skips**, consisting of **24 actual PostgreSQL scenarios plus 10 migration loader/unit checks**. Separate File/Mock regression **77 passed**.
- `1349026fd209c048f583859f8a9e41af7301160b`: File/Mock **59 passed, 9 explicitly backend-gated skips**. Those nine cases were then executed against real PostgreSQL 16.15: **9 passed, zero skips**, repeated in reverse order and canonical order on fresh databases within one isolated instance. Repetition does not mean 27 distinct cases. All 5,826 tracked file hashes were unchanged.

The earlier 34-case group was not rerun on the latest commit. No full-product PostgreSQL, complete authorization end-to-end, Windows ACL/junction, real external NLE acceptance, or Work audio-capacity closure is claimed. PostgreSQL metadata and filesystem-backed media remain a hybrid architecture; some API contract tests use synthetic authorization/session boundaries.

All temporary PostgreSQL instances used only loopback TCP/SCRAM and were stopped; temporary credentials, database clusters and test assets were removed. Cleanup logs are included.

## Evidence provenance and redaction

`evidence-index.json` identifies source archive filenames, complete archive SHA256 values, original member hashes and published-copy hashes. The public copies normalize cloud workspace/temp paths and private Space artifact identifiers; the originals remain in the user-delivered Space checkpoint packages. Historical documents may describe the packaging state at their original timestamp (including “not uploaded” or an included bundle); those statements are not current remote-state claims, and this curated directory is not a full copy of each archive.

Historical already-tracked delivery evidence elsewhere in this repository is retained byte-for-byte, including non-personal cloud execution paths. Large repeated source manifests, Git bundles, full compiler logs and binary artifacts are not duplicated here. The selected raw logs, result JSON, migration provenance, final reports and cleanup proofs are sufficient to inspect the stated scoped results; archive hashes identify the full evidence packages.

`source-delta-manifest.json` records all 106 cumulative changed source/document files against the published base, including their blob IDs, lengths and SHA256 digests. Remote publication must be read back and its final tree compared with the locally prepared publication tree before upload success is declared.
