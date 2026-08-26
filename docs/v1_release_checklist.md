# V1.0 Backend Release Checklist

## Verified

- [x] Phase 8 screenplay and asset pipeline implemented
- [x] Provider catalog, adapter contract, and Credential Vault integration
- [x] Worker claim, dispatch, timeout, recovery, cleanup, statistics, and lifecycle APIs
- [x] Non-sensitive Provider and Worker configuration persistence
- [x] Packaged-runtime session guard for real asset execution
- [x] Phase 8 regression: 26 tests passed
- [x] Durable local export queue, idempotency, safe download response, DOCX/EPUB package output, and deterministic preview formats
- [x] Export progress, cooperative cancel, failed/cancelled retry, and startup recovery metadata

## Release prerequisites

- [ ] Run the full repository test suite in a clean environment
- [ ] Run PostgreSQL parity tests against a real PostgreSQL 16 instance
- [ ] Set `POSTGRES_PASSWORD` and review `.env` without committing it
- [ ] Configure credentials through the application; do not place keys in `.env`
- [ ] Verify backup and restore before production data migration
- [ ] Build and smoke-test the Windows desktop package
- [ ] Perform one authorized real-provider smoke test only after quota approval
- [ ] Record release version and package checksum
- [ ] Complete PDF and standard screenplay/shot-list/storyboard exports (minimal DOCX/EPUB exports are available)
- [ ] Add immutable export snapshots, missing-resource report, and export permission checks

## Rollback

Stop the service, restore the latest verified data backup, deploy the previous package, and rotate any credential that may have been exposed. Do not delete the source data directory during rollback.
