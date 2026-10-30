# Explicit PostgreSQL test selection: real nine-case verification

Final commit (unchanged by this round): 1349026fd209c048f583859f8a9e41af7301160b
Tree: e8dc68c6fe2ea10b66aec500799f4c817b19a283
Base: 3139927b997c18048704aa958a73787fa12a7251
Branch: work/postgres-explicit-test-fixture-20261030

11 test-only files changed relative to base. No production code or migration edits in this branch. No source changes during real PostgreSQL verification. The included compact bundle requires the base3139927 from the previous verified PostgreSQL checkpoint. No GitHub upload.

## Newly completed real PostgreSQL verification

User approved one fresh cloud synthetic test instance with a temporary SCRAM password for these nine cases. PostgreSQL16.15 from the previously verified official install ran once, listening only on127.0.0.1:55432, with Unix sockets disabled. SCRAM/reject authentication and server settings were recorded. Three sequential rounds used distinct freshly created synthetic databases within this one instance and the same unchanged source:

- Implementation canonical order:9 passed,0 skipped/errors/failures,exit0,5.13s.
- Independent reviewer-requested reverse order:9 passed,0 skipped/errors/failures,exit0,5.46s.
- Parent-requested canonical order:9 passed,0 skipped/errors/failures,exit0,5.95s.

These are three repetitions of the SAME9 cases, NOT27 unique cases. Each round ran original baseline SQL001–016 and the original packaged migration runner twice; migration ledger remained unchanged on the second invocation. Each round's5826-file source manifest remained unchanged. Raw sanitized logs, JUnit, explicit node IDs, database provenance and migration evidence are included.

The instance was stopped, pg_ctl confirmed no server running, and temporary credentials, the entire synthetic database cluster and test assets were removed. No user local computer, production database, system network policy or external listener was used.

## Scope

The actual nine cases cover identity membership/cardinality, durable context snapshots and generation links, File/PostgreSQL lore-context parity and same-name novel isolation, atomic save/audit rollback, collaboration snapshot metadata API exposure and concurrent chapter CAS/history. Original business assertions were not replaced or weakened.

Identity uses a synthetic Novels lookup double; collaboration API uses synthetic sessions/membership/scope doubles while chapters/generations/lore are real PostgreSQL. This is targeted persistence/API contract verification, not full security end-to-end or full-product PostgreSQL acceptance. It says nothing about Work-owned audio capacity/history/restore completion.

Earlier File verification at the same final source remains59 passed,9 intentionally backend-gated skips. Those skips were not claimed as PG passes; the newly executed9 above now have separate real-server evidence. Earlier34-case PostgreSQL/loader suite was run on base3139927, not rerun on1349026 here; do not silently transfer or accumulate that result.

## Test-harness correction

Explicit TEST_POSTGRES_DATABASE_URL and STORAGE_BACKEND are captured before per-test environment clearing. No dotenv or production DATABASE_URL fallback is accepted. The test URL must use literal127.0.0.1, an explicit valid port and ai_novel_studio_e2e_ name, with no query/fragment/whitespace. Shape checks do not prove database freshness; this run establishes provenance by creating each database inside the authorized fresh instance.

Only the selected fixture consumers receive the validated URL during app bootstrap. Original settings restore even if bootstrap fails; provider/database environment clearing remains. All9cases have PostgreSQL markers. File-only job imports are lazy to eliminate selected-file collection connections. Backend gating uses captured explicit selection rather than later dotenv/environment changes. Neutral skip reasons do not claim unexecuted coverage.

Prior no-database guards, original defects/failure logs and the previous NOT_RUN checkpoint report are retained as historical evidence and are clearly separate from these real-server results.
