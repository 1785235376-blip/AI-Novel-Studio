# Opt-in compact staged catalog snapshots

Owner: B, independent CI-capacity worktree. Parent commit:
`0696f059ad631a88a76b10c9bc2c68c0b064612e`. A owns final integration,
catalog publication and V2 manifest regeneration.

## Result and exact scope

`python scripts/refresh_v2_staged_catalog.py --compact` retains all staged
files except the exact `docs/delivery/` historical-evidence subtree. The original
default full snapshot remains available without an option. The original catalog
generator, historical catalog seeds, application code, isolation environment,
workflow, backend assignments, budgets, existing tests and frozen gates are
unchanged by this increment.

The option streams the exact staged Git tree rather than holding its complete
tar archive in memory. Every retained regular blob is checked against its Git
object ID before generation. It rejects mutable refs, commit IDs, nonempty
destinations, unsupported retained links/submodules, missing/extra archive
members and content transformations. It never copies current checkout files.
The complete `app/` source inventory, tests, frontend, contracts, prompts,
interop packages and non-delivery documentation remain present.

The original generator runs in the existing owned File/mock/offline environment.
Additional compact-only checks reject attempted opens beneath the omitted
directory and loaded application/interop modules outside the snapshot. All four
output files are read and validated as present before the first root-catalog
write. Generator, extraction and import-provenance failures therefore publish
no catalog. Compact receipts use a unique suffix, preserving previous full and
compact receipts and all snapshots.

This does not make four separate filesystem writes a crash-atomic transaction.
A disk failure during publication has the same multi-file-write limitation as
the original wrapper; no broader transaction guarantee is claimed.

## Same-tree equivalence

Existing successful full snapshots were read only. No new full snapshot was
created for this experiment. Both comparisons used the unchanged generator
SHA256 `e9fc5835b4135446a3b0221c07033c7d88330c1658d416117ac68dba7d5268ec`.

| Exact staged tree | Full tracked bytes | Compact retained bytes | Bytes omitted | Reduction |
| --- | ---: | ---: | ---: | ---: |
| `efca85593b86fe4738f8fd83a27f11de4af339ef` | 397,908,909 | 30,899,672 | 367,009,237 | 92.23% |
| `b7e1605713fdd9ae4138cdb1f74ceee72306862a` | 412,252,868 | 30,968,037 | 381,284,831 | 92.49% |

For each tree, `API_CATALOG.json`, `API_CATALOG.md`,
`API_CATALOG_DETAIL.json.gz` and `API_OPENAPI.json.gz` were byte-identical to the
original successful full receipt. All 354 observed project-module origins were
inside the compact snapshot. Reference output hashes were verified both before
and after the experiment. No A repository-root catalog was written.

The source inspection found no catalog-generation read of `docs/delivery/`.
The only application match was a provenance docstring in
`app/native_text_providers.py`. Wrapper/check-runner delivery paths are receipt
outputs in their main functions, not catalog imports. Non-delivery installation
documentation remains available. The earlier 7.36 MB application-only closure
experiment also matched one tree, but is **not** the implemented exclusion rule.

These are two exact-tree equivalence results, not a universal dependency proof.
Future optional `exists()`/directory probes could depend on delivery evidence
without opening a file. Review such new generator/import dependencies before
using compact mode; use the unchanged full mode when uncertain. The open hook
and module-origin check are diagnostics, not a security sandbox or a substitute
for the historically blocked independent review.

## Validation and retained development failures

- Initial new tests: 17 passed, 10 failed. They exposed rejection of a legitimate
  `docs/` ancestor when its only child was the omitted delivery subtree. The
  extractor now validates directories against the full immutable tree inventory.
- Second iteration: 27 passed.
- Third iteration after additional boundary tests: 30 passed, 3 failed because
  the new test's receipt variable was inserted in the wrong fixture block.
  Only that newly authored fixture setup was corrected.
- Final focused run: **33 passed** (28 new engineering cases plus 5 existing
  isolation-runner cases), 1.39 seconds.
- Final complete `.github/ci` suite: **352 passed**, 11.08 seconds.
- Default actionlint validation of the unchanged current workflow: exit 0.
- Source `git diff --check`: clean. Raw captured failure XML and generator logs
  retain their original whitespace; the all-artifact whitespace check reports
  those existing capture bytes. V1 manifest and four original gate/script
  hashes remain identical to the established baseline.

Artifacts, final source hashes, full/compact output hashes and the exact local
comparison driver are under `compact-snapshot-20261010/`. Earlier development
failures are preserved; they are not backend-suite results or reruns of the
original hosted failures.

## Integration and remaining blockers

A can review and transplant this increment, regenerate the additive V2 source
inventory, then opt in for a subsequent staged catalog refresh. No workflow
calls compact mode automatically. This improves future snapshot disk usage;
it deletes none of the existing 3.4 GB snapshot history and does not reduce the
original File/PG test budgets or establish their completion. Hosted File
capacity and the previously observed PostgreSQL failed call remain open.
