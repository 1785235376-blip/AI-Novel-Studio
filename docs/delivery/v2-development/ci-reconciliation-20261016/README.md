# CI reconciliation evidence — 2026-10-16

Source checkpoint: 14ced1025b51af3b9636fc9564366bd5aba1946d (126 exact source/test paths; see source-126-map.json).

## Current result
- 43 protected original test files restored byte-for-byte from a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3. All 1,123 old V2 protected source hashes remain exact.
- Additions and deliberate compatibility variants are separately recorded in ledgers/. The sole existing frozen migration is Windows launcher -B; no guard or protected assertion was relaxed.
- Focused clean backend runs: 88 + 19 + 2 + 1 = 110 passed; PostgreSQL cases were deselected, not accepted as passing.
- UI ownership scope: 348 unique cases across 43 files, aggregated from the documented 337-case run and 21-case retry with 10 repeats. Canvas focused final run: 129 passed. These overlapping scopes are not summed into a broad coverage claim.
- TypeScript, Vite build and token lint succeeded; Vite chunk-size warning is retained.
- Unchanged CI helper suites: 27 + 126 + 13 = 166 passed.
- Review and candidate collections: 15,617 inventory rows, with every old 15,142 row/order/backend classification preserved. All 475 additions are in 29 previously unregistered suites. Inventory is not test execution.
- Independent candidate signoff passed. Exact gzip bytes were promoted to canonical V2; a separate no-write confirmation produced byte-identical raw inventory. Canonical SHA256: bffc623ae02c28b8cf8c4022b3ed33674e6b14b9fc7a1ccab2326c36ccf3bb5c. All three raw inventory SHA256s: b921230f2888db9f7be9fd32f1f3e3d2dfaf45c2ce528886897a17ba7fa78ede.

## Evidence layout
- audits/: immutable investigation, verification plan and import/environment assessments.
- ledgers/: exact restoration/extraction/fixture/host migration paths and assertions.
- frontend/, backend/: final source-bound results and original failed/intermediate evidence.
- helpers/: three unchanged CI helper receipts and logs.
- environment/: dependency-only setup/copy inventory and startup/actual-child origin probes, including the initial failed probe. No dependency package or interpreter is included.
- inventory/: old raw rows, immutable review/candidate raw archives, candidate gzip, all source/companion brackets, command boundaries and validation reports.
- independent/: independent source, frontend and dependency checks.
- artifact-relocation-map.json: exact byte hashes and relocation of historical absolute artifact paths. Original reports are copied unchanged, so historical pending labels are interpreted in time order, not rewritten. The authoritative final extraction ledger is ledgers/ci-reconciliation-ui-extraction-20261016.json; frontend/ui/ledger.json and final-assertion-audit.json are earlier evidence, not final acceptance. independent/current-source-review-20261016.json is the current source checkpoint review.

## Source counts
The 2,525 bracket entries are 2,514 normal traversal entries plus 11 frontend/scripts and frontend/e2e companion files. The generator source map is 2,576 entries: the same 2,514 normal entries plus 62 inherited frozen-baseline inputs. The 11-file companion stays separate because the unchanged generator does not traverse those directories.

## Preservation and reproduction
Use the committed command/selection receipts and the exact source checkpoint. The environment summary pins Python 3.12.14 and 36 validated distributions (the initial proposal prose has a 37-distribution typo; its JSON and actual setup receipt correctly say 36). The separate pypdf 6.19.0 declaration is retained. Do not process an old editable .pth or finder.
The inventory command uses the existing scripts/extend_v2_coverage_manifest.py with the complete sanitized environment in inventory/execution-boundary.json, including PYTHON_DOTENV_DISABLED=1, disabled plugin autoload, packaged reader off and absent database URLs. It intentionally imports app modules and initializes only an owned profile; it does not execute product test bodies.
Each generator invocation overwrites its fixed raw collection path. Archive those bytes immediately, compare all old rows and full review/candidate equality, and validate the exact generator source closure. Canonical promotion is a separate reviewed byte-copy step.
Original source failures, the initial startup probe failure and provenance-qualified old-interpreter results remain visible. They are not silently replaced by successful retries.

## Scope limits
No hosted CI, PostgreSQL runtime, real model/provider service, full product test execution, public push or old blocked candidate execution is claimed. The earlier blocked candidate and its lifecycle/security tests remain outside the authorized execution scope.

## Offline evidence verification
Run node docs/delivery/v2-development/ci-reconciliation-20261016/verify_bundle.mjs from the repository. This hashes committed evidence and source files and compares inventory rows; it does not run pytest, import the product, access services, or recreate the interpreter. The historical command scripts are retained unchanged as audit evidence; the portable verifier is the read-only entry point.
