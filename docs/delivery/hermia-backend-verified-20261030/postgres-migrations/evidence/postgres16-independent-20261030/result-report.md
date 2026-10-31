# PostgreSQL 16 / external-native OTIO verification

## Implemented correction

The existing integration imported PostgreSQL runtime code requiring three migration assets but omitted those SQL files. This omission predates the new OTIO mode and was already present at public baseline395ac26. Default/experimental migration loading raised FileNotFoundError018; identity loading raised FileNotFoundError020. Original pre-fix logs are retained.

Recovered SQL018–020 byte-for-byte from their original local Git history, including the latest typed-UUID correction in020. No ad hoc schema, production Python change, new privilege model, or redesigned migration was introduced. Full source/blob attribution is in migration-provenance.md and repair commit668b51c2d32694442aab8d6f10f557418cfb9e7f.

The old packaged-migration unit test still expected the pre-privacy0001-only registry. It initially failed against the existing loader's0001+0002 contract. The assertion was updated to require both checksummed migrations and privacy SQL, not weakened to omit privacy. First failure and corrected10-pass unit run remain separate.

## Real PostgreSQL execution

A fresh isolated PostgreSQL16.15 instance used TCP127.0.0.1 only, no Unix socket, temporary SCRAM credentials, and a newly-created synthetic database. The wrapper applied original SQL001–016, then ran the original PackagedPostgresMigrationRunner with experimental migrations enabled twice. Readiness checks passed, and the entire migration ledger, including applied timestamps, remained unchanged on the second run. This is ledger-based rerun safety; raw018 SQL is not independently rerunnable because it adds a constraint.

OTIO module initial run:14 passed,0 skipped,exit0,24.38seconds. Source HEAD668b51c2d32694442aab8d6f10f557418cfb9e7f with the then-uncommitted exact test module SHA25637d46e489be04cb7339bb3b17304ed9fbd7c9c3b7ce29b4f3a40299833a04311. All638 recorded source hashes unchanged. The tested module was subsequently committed unchanged in2cccb50323307ff0c6126557b67833c38905634d, tree03d2d7a52245f732284c544f6162e0abd86ff2ba.

Real coverage: both mounted API prefixes; strict rejection retained; explicit native trim/speed/gap; mandatory loss acknowledgement; reviewed preview binding; successful save; idempotent replay; rejected changed bytes/media binding/mode/CAS/digest/source leaves actual PostgreSQL document and revision unchanged; new PostgreSQL owner/store instances read persisted results.

## Limits

This is hybrid production architecture: project and scope metadata use real PostgreSQL, but binary media and auxiliary image/video/audio stores remain filesystem-backed. It does not certify all Studio persistence, full-product PostgreSQL parity, audio capacity/history/restore, real external NLE applications, Windows ACL/junction behavior, or previously blocked publication review.

The setup wrapper stops each synthetic server and removes its temporary credentials, database cluster and test media. Cleanup completion is recorded per run. Nothing was uploaded to GitHub, merged, released or written to main.

## Independent final frozen-source acceptance

Final HEAD3139927b997c18048704aa958a73787fa12a7251, treef795da73025730744ee92f26f4b467114e9df6b5. Exact seven changed files relative to9f8ca0: three restored SQL migrations, two updated legacy tests, and two new test modules. No production Python edits.

Parent independently ran six test files against a newly-created PostgreSQL16.15 cluster:34 passed,0 skipped,exit0,21.71seconds. Breakdown:24 actual PostgreSQL scenarios (14 OTIO plus10 repository/lore/admin-concurrency contracts), plus10 migration-loader/unit checks. Do not describe all34 as database integration scenarios. Source manifest unchanged=true. Original migration runner second execution preserved complete ledger timestamps. Server shutdown and subsequent no-server-running check passed; temporary credentials, cluster and assets removed.

The initial PG contract group had9 passed,1 failed because its old fake runtime exposed only router(), while the real MemoryAgentRunner uses the current local-provider context and privacy/provider-selection methods. A test-only update reused the existing verified test_memory_workflow Runtime and memory_settings fixtures, retaining original pending-proposal/no-approved-memory assertions and adding an exact provider call assertion. Corrected PG group10 passed; the referenced File memory group11 passed. These groups overlap final acceptance and must not be added.

Final independent evidence is in evidence/postgres16-20261030/parent_final. Earlier runs and failures are preserved separately.


## Frozen-source File/Mock regression

On the same final3139927b HEAD, the six-file File/Mock regression passed77 tests,0 skipped,exit0,21.95seconds. It covers prior external-native OTIO/runtime/precision diagnostics, original memory agent contracts, and migration loader/unit checks. All5824 tracked file hashes remained unchanged. This overlaps other groups and is not added to them. Raw command/log/hash evidence is in evidence/postgres16-20261030/file-final.
