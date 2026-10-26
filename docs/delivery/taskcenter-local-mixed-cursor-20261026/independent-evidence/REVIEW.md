# Independent exact-pair local mixed cursor review

Final production freeze:c68857c59d50dfe90b8edc5e88e8de2cc81d5fc3.
Final app tree:7e357c95629c255854e4287e02c4c57777097573.
Test-only delivery commit:a83aa5d85d4058b73f6ce12420b6cf9461bc86f3 (parentc688;7 test files,332 lines).

## Final result

- candidate-c688-receipt-focus:10 PASS, exit0,185.99s.
- candidate-c688-regression:35 PASS, exit0,213.65s.
- These two final groups have disjoint node IDs:45 independent cases (42 mounted HTTP cases and3 private-observer unit cases). Other historical counts overlap and must not be added.
- No timeout or outside-source app modules. Full app before/after SHA256 manifests are identical. Production remained immutable throughout both final groups.

Real mounted /api and /api/v1, original POST exports202 and imports201, original File owners/project identity, original authorization, source readers, safe task projection and cursor engine. Only actual temporary storage/service roots and deterministic race hooks replace runtime inputs; export submission/snapshot provider are stubbed to avoid real jobs. No fake successful adapter or replacement authorizer.

Coverage: registry order versus normalized query order/duplicates; original200+100 caps,300 bounded combined observation; ID collisions with authority-qualified nonces; selected privateABA versus unmatched changes; empty-one/both and empty-source document incarnation; source singleton and document replacement; project replacement; before/after/final engine hooks; feature invalidation; original reauthorization; other mixed/collaboration rejection; original actual-aggregate read403/404 for empty and nonempty source; default observer compatibility, actual read count/order, receiptFalse for denied reads, and callback failure propagation.

## Actual defects found and closed

1. dac25da returned200 when actual reader registry order changed inside the last component of the final capture. candidate-dac-order-probe is actual RED, not theory. cd32 added a final registry-order comparison; final source retains it and the probe is GREEN.
2. cd32 returned200+cursor when one selected source was empty and its original reader denied403; the original aggregate intentionally omits denied-source rows. candidate-cd32-empty-denial-probe records two actual RED cases. Separate pre/post probes were explicitly rejected as insufficient: only the actual aggregate read's result can certify that request. Final c688 uses one normal aggregate invocation with private, request-local receipts and validates both reader identities/order/success. The final matrix denies only actual WorkspaceToolsService.tasks calls, while any hypothetical separate probe would succeed; both403/404, empty/nonempty and import/export pass fail-closed checks.

The newly approved ux.py private _read_observer hook defaults to None, exposes no response payload and changes no old response contract. Observer failures escape source-error handling rather than becoming SOURCE_UNAVAILABLE. No shared registry wrappers or cross-request receipt state exist. The base adapter's default aggregate hook retains its original arguments.

No unresolved defect found in this exact local pair's bounded composition. This is not collaboration support, global mixed-source support, a cross-file atomic snapshot, full ABA/backup replay protection, complete history, exclusive executor ownership, real model/paid resource execution, hosted deployment or CI verification. Tests ran in dot's native cloud workspace with synthetic data and private internal workspace provenance paths.

## Preserved provenance

- baseline-red: old9780594, both original POSTs succeed, both mixed cursor prefixes intentionally fail501.2 expected failures,231.55s.
- candidate-dac-final:30 PASS+1 harness error: test expected401 after switching runtime to collaboration mid-read; original boundary correctly returns400 BRANCH_SCOPE_REQUIRED. Corrected only test expectation, not production auth.
- candidate-dac-order-probe:1 actual production failure described above.
- candidate-cd32-final:32 PASS before empty-denial gap was discovered; no final approval implied.
- candidate-cd32-empty-denial-probe:2 actual production failures described above.
- 5349824 intermediate separate-reader probe was rejected and was NOT accepted or run as final evidence by this reviewer.
- candidate-c688-receipt-focus and candidate-c688-regression are the final authoritative results.

All raw logs/XML/summaries/loaded-module receipts, source manifests and final test files are included. run900.py used900s for historical runs; run1800.py used1800s for final groups due slow cold imports/filesystem, preserving original isolated verifier settings. No independent run timed out. No uploads performed.
