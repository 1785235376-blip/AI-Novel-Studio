# Additive V2 coverage inventory

The V2 branch uses `coverage_manifest_v2.json.gz`. The existing
`coverage_manifest.json.gz` is immutable historical V1 evidence, with SHA256
`6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.
The original V2 baseline is `e21075d10801a60bdcb4282a6d5ce8068be21503`.

## Explicit generation, never CI auto-blessing

After sources are stable, run:

    python scripts/extend_v2_coverage_manifest.py

This performs complete, unfiltered collect-only in an owned profile and writes
`docs/delivery/v2-development/cloud-v2-collection.json`. Review the source drift
and additions; then run with `--write` to create the separate V2 manifest.
Generation rejects collection errors/skips, duplicate or missing baseline nodes,
changes to baseline relative order, concurrent source edits, missing source
hashes, and changes to existing test or coverage-gate bytes.

The one explicitly reviewed preexisting V2 baseline migration is
`tests/test_windows_portable_entry.py` at commit
`1b7ff50a7e64742916bc64730df884cea819b379`: add `-B` before `-I` in the launcher
expectation. The generator verifies the historical and current exact hashes and
requires that single replacement to reproduce every byte. Generation therefore
requires that historical Git object; CI does not generate the manifest and its
self-tests work with a shallow checkout. No other existing test/gate drift is
accepted.

Every original node and both exact historical skip maps remain present. New
nodes receive no additional skip exception. Existing opposite-backend marker
skips continue under the unchanged verifier. All current product/test/helper
sources receive exact hashes. The frozen manifest and original source hashes
remain independently identified in the V2 extension metadata.

Generated fixture state is not source: untracked files beneath fixture
`.workspace-mutation-locks` directories and untracked fixture
`chapter_identity.json` files are omitted. This does not omit tests, genuine
fixtures, Git-tracked matching files, or any source entry in the frozen
manifest. Generation never removes these runtime files while tests are using
them. If Git tracking cannot be established, name-based exclusion is disabled.

## Execution remains independently required

Collection counts are inventory only. They do not establish passed tests or
coverage. The unchanged PostgreSQL gate, ordered full collection, File process,
two deterministic PostgreSQL shards, complete phase/JUnit reconciliation,
separate TCP gate, check names, timeouts and strict unexpected-skip handling
remain required. Interop uses the same additive source inventory with its
unchanged exact Interop scope.

V2 backend state and pytest temporary directories live below the CI checkout's
`.runtime` directory. The Windows lane adds only narrow environment fixture
contracts. It does not claim actual GPU, driver, inference, interactive desktop
or user-machine acceptance.

## Disposable cloud PostgreSQL

Given existing PostgreSQL binaries and an already initialized/migrated cluster
under the checkout's `.runtime`, run checks in one command lifecycle:

    python scripts/run_v2_postgres_checks.py --pg-bin PATH_TO_BIN --data .runtime/postgresql/data cloud-v2-check -- python -m pytest --basetemp=.runtime/v2-checks/cloud-v2-check/pytest tests/test_v2_creative_foundation.py

The wrapper refuses an unowned or already-running cluster, binds loopback only,
verifies live SQL identity, records the actual PostgreSQL version, and stops the
server when the command completes. It never downloads, installs, initializes,
or reuses a user/production database. Separate cloud command namespaces may not
share loopback, so the server and test subprocess must share this lifecycle.
