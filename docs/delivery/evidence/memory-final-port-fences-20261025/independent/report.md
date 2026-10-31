# Independent final-port repair review

## Final opinion

PASS for repair of the six published memory final-port holes and the targeted compatibility/composition boundaries below, conditional on exact final hashes in source-before.sha256. Base: 05682a860fbeb15d108ce6c518cd76c8ce5e9e18. This is not a universal safety, arbitrary callback, crash-atomicity or public admission activation claim.

Final evidence consists of 25 independent targeted probes plus 2 independently written manual accept→memory composition probes, and three separate fresh-process import orders. The six former positive contamination counterexamples now all validly refuse. Every scheduling wrapper accepts and forwards **kwargs unchanged; no TypeError counts as a successful fence.

## Six published holes retested

- Same-thread original delete/recreate inside original LoreService.create_evidence, original FileLoreRepository.create_evidence, or original FileLoreRepository.create_proposal wrappers now refuses with owner-change errors before replacement rows are written. Replacement evidence/proposal counts are zero; old durable receipt remains GENERATING rather than falsely recording a terminal result under a changed owner.
- Final same-root facade repository rotation, same-root backend rotation and other-root facade repository rotation all refuse STORE_MISMATCH before Lore writes. No returned success or COMPLETED receipt is credited. The stronger other-root case leaves both roots without extraction-created Lore rows.

The wrappers and test compositions are the same as the published counterexample probes, changed only to forward the newly added private expected-port argument and assert refusal/zero writes. Earlier published-defect artifacts remain unchanged in the earlier review directory.

## Additional independent coverage

The prior 19 targeted probes pass with only forwarding-compatible scheduling-hook updates: partial relation failure/retry repair; no adoption of legacy proposal provenance; original FAILED-receipt lease; final source-recheck→terminal lease; real deletion proceeds during paused inference and stale completion/error cannot change replacement data; failed same-owner enqueue retry and terminal dedupe; PostgreSQL bound refusal before touching a database; runtime observers acquire lifecycle lock from another thread after publication; removed/null/mixed/bool binding rejection; queued/adapter owner replacement; root rotation during inference; local error without remote fallback; old FAILED owner retry refusal and distinct replacement operation identity; wrong File service refusal; and intentionally retained legacy unbound delayed-adoption counterexample.

Two separately written manual composition checks use the actual cold JobManager, original accepted chapter/Canon, original asynchronous MemoryAgentRunner enqueue and File/Mock adapter chain. Valid output preserves ACCEPTED, produces exactly one bound COMPLETED receipt and consistent PENDING proposal/evidence relation. Invalid model JSON preserves ACCEPTED while independent memory records bound FAILED with no Lore rows. Neither establishes public admission or expands manual review eligibility beyond this code's existing explicit guards.

## Cold import check

Three fresh Python processes independently import:
1. app.main before app.lore.file_memory_ports.
2. app.lore.file_memory_ports, then app.services.lore_service, then app.main.
3. app.repositories.file.lore, then app.services.generation_service, then app.main.

Each imports the actual app and runtime and prints COMPOSITION_READY. Socket connect/connect_ex/create_connection/getaddrinfo are blocked before any app import. No import cycle was observed in these orders. No server, model or provider was installed or started.

## Integrity and reproducibility

Exact commands: bash .runtime/independent-final-port-review/run.sh and bash .runtime/independent-final-port-review/run_manual.sh. Both use env -i, isolated HOME/XDG/data/tmp and the existing dependency environment. Test fixtures block socket connections; all inference is synthetic built-in Mock through original adapter/runtime code. Source-before manifest matches final-frozen-input.sha256, not the earlier targeted freeze. Original changed production/test files are copied under frozen-source. Additional unchanged manual/composition file hashes are recorded in composition-source.sha256. stdout/XML, cold-import logs, probe sources and commands are retained here.

The pre-hardening run passed tests but detected concurrent _FileMemoryPorts/test edits via post-run hash verification. It is preserved under pre-hardening and is not the final frozen opinion. Final checks were rerun after the implementer's new freeze. No production changes, commits or pushes were performed by this reviewer.

## Limits

The new optional expected-port argument preserves direct legacy call shapes; legacy unbound behavior remains intentionally unchanged, including its reproduced replacement-adoption weakness. PostgreSQL coverage is explicit refusal only, not real transaction/isolation testing. Partial multi-file output may remain after failure in the original owner; successful retry of the tested partial relation case is not general crash rollback or exactly-once semantics. Private expected-port data is identity/composition data, not a public authorization grant. This review covers wrappers at the specified original service/repository boundaries, not arbitrary mutation of trusted function implementations or raw filesystem writes. Full public admission, all specialized flows and universal same-thread reentry safety are not claimed.

Final measured runs: 25 passed in 8.88 seconds; 2 manual composition cases passed in 5.61 seconds. Both final post-run source verifications are all OK.
