# Third-wave three-gate inventory reconciliation

Evidence/source checkpoint: `4d6bbe985994c7a679d17bfddd600658a358bc76`.
Canonical predecessor: `9325818bbd98ad086db64ca0266aca6e7c4223b8`, V2 SHA256 `a76dd7d972e932fe8711e1d193068839813bf67c0dc87625af9fb9f97f58f2a9`, 17,289 full Python inventory rows and 2,671 source entries.

Preparation was held until the supplemental evidence was committed. Parent now explicitly releases only the first no-write collection on the final evidence checkpoint. The original generator, original runner and fixed approved clean interpreter are unchanged. The interpreter directory always remains ci-reconciliation-python-r1, irrespective of inventory phase/profile labels.

## Exact planned source change

`preparation-scope.json` derives 20 new sources and eleven changed existing runtime/UI sources from committed Git blobs. Expected source-map count is 2,691; actual row counts remain unknown until collection. Six new backend test files cover Director pending/races, caption offset, interactive removal, Comic duplication and the separately approved corrected Director→Canvas bridge. The new Comic JSON fixture and all new frontend tests/helpers remain in the source map.

## Three separate approval gates

1. Parent writes parent-release.json with status APPROVE_FIRST_NOWRITE_COLLECTION and exact source_commit, then releases the global slot. Run collect.mjs review, then check.mjs review. This is no-write inventory collection only. Parent independently reviews the retained raw rows, old full dictionaries/order/backend classes, source derivation and evidence before writing independent-review.json with APPROVE_CANDIDATE_GENERATION.
2. Only after that approval, collect.mjs candidate invokes the unchanged original generator with --write --output targeting the owned .runtime/parallel-integration-wave3-inventory/candidate-manifest-v2.json.gz. It never writes canonical V2. Check the candidate using check.mjs candidate with its exact path. Parent independently approves exact bytes in independent-candidate-review.json with APPROVE_EXACT_CANDIDATE_PROMOTION before any promotion.
3. Parent controls approved exact-byte canonical promotion (including explicit delegation) and writes canonical-promotion.json. Only after explicit confirmation-stage release, collect.mjs confirmation performs a third no-write collection. All three raw collection results must match byte-for-byte. Final checker verifies candidate/canonical SHA and approval hash binding.

Approval files are not authored by this worker as a substitute for parent authorization. Existing failed/successful stage output must never be overwritten. If a stage fails, stop, preserve and report before changes/retries.

## Guards and bounded evidence

Each stage verifies committed source blobs, full source hashes before/after, exact original source delta, every predecessor test/fixture/snapshot/CI entry, frontend scripts/E2E companion closure, all committed documents at the evidence checkpoint, frozen V1, original screenplay/Graph and Audio omission goldens, and unchanged PUBLIC manifest SHA256 `353b92aff6116d873ea4402a1ef627e7899214b46ba823a9b4300ba75c5d0448`. Fresh natural startup and actual unchanged-runner child origin proofs precede each collection. No PYTHONPATH injection outside original runner, no .pth changes or sys.path replacement. Use normal conftest and no installs; PIP_NO_INDEX=1.

Reuse predecessor raw collection and primary/independent evidence by reference. Retain three bounded raw JSON outputs and source/Git maps, one predecessor gzip and one owned candidate. Packet limit is 40 MiB; no worktree/archive duplication or deletion of any prior file. Initial preparation free disk was about 611 MiB. Stop/report capacity issues rather than removing prior evidence.

The six raw original-runner origin files at docs/delivery/v2-development/wave3-integration-inventory-{review,candidate,confirmation}-origin.{json,log} MUST be included in the final parent evidence commit as well as indexed as external dependencies. A copied packet-local receipt does not replace persistence of its original root receipt/log. This explicitly avoids repeating wave2's corrected omission.

Inventory records collection/classification, never tests executed or passed. Five known Audio listing failures remain unresolved and excluded from runtime acceptance; primary runtime evidence has two genuine font skips. No PostgreSQL execution, browser, Windows-native, providers, main merge, push, release or cleanup is authorized by this packet.

## Completed three-gate closure

All three original-generator collection stages and separate parent audits passed on source/evidence checkpoint `4d6bbe985994c7a679d17bfddd600658a358bc76`. The preparation instructions above record the initial workflow; this section records actual closure.

Canonical V2 is exactly the parent-approved 646,038-byte owned candidate, SHA256 `6a94abca1ad6fe835e1ad483774b1fbfb660b6e599a69a2b48533ee2141abb77`, promoted under explicit parent authorization without recompression. Predecessor SHA256 remains `a76dd7d972e932fe8711e1d193068839813bf67c0dc87625af9fb9f97f58f2a9` in the retained predecessor gzip.

Actual inventory: **17,425 Python rows and 2,691 source entries**. All 17,289 predecessor full raw row dictionaries, order and backend classifications remain byte-semantically exact. The 136 additions are 119 File-only and 17 PostgreSQL-only classifications, no both-backend additions: caption 28, comic duplication 6, durable pending 97, pending File races 2, interactive removal 2, Director→Canvas bridge 1. These are collected/classified rows, not tests executed or passing.

Exactly 20 new source files and 11 changed existing runtime/UI files derive from committed Git blobs. All 1,344 protected predecessor source entries, 11 frontend scripts/E2E companions and 9,711 committed historical documents remain exact. Frozen V1, original tests/fixtures/Goldens, runner/generator and PUBLIC manifest are unchanged. All three complete source brackets and Git source bindings agree.

All three raw collection byte streams are identical, SHA256 `8489499d82e9ebeeeb6ae455dbd7ee7659f2a9ae56ef5b2b563f579d082984a3`. Fresh natural and actual original-runner child origin proofs preceded every stage. Parent independently checked the first source map against all 2,691 committed Git blobs, then exact candidate gzip/schema/full old node order, then final raw equality and canonical bytes. Parent review files are retained in this packet.

The finalized index includes all packet files and references all six original root origin receipts/logs, plus prior raw inventory, setup receipt and accepted primary/independent/supplemental evidence. All six root files must be included in the same parent commit as this packet and canonical manifest. Earlier runtime acceptance remains its own immutable scoped evidence: 1,799 backend passes at `db6487b` reused only after exact backend identity, and fresh 1,667 frontend passes at `f4a6fed`; inventory adds no fresh passing-test claim.

Packet remains approximately 31 MiB, below 40 MiB; free disk approximately 540 MiB, above 300 MiB reserve. No prior files were deleted, no archives/worktrees duplicated, no additional tests/collections are scheduled by this closure. Parent owns the final commit. No main merge/push/release occurred.
