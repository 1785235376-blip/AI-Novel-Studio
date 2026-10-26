# Independent local-export TaskCenter cursor review

Production candidate1799b098f1f5b5639e151c66be21a175387cb047, app tree591cc74b70cf5546f6cf604d985e484f40c18567. Test-only delivery commit3dc5eef955f947fe3e2829b7829df46a7585d2a7 is directly based on1799 and adds only three test files.

Final candidate-1799-reviewed:22 PASS, exit0, no timeout or outside-source app modules. Entire app SHA256 manifests before/after are identical. The application source remained immutable throughout all independent candidate runs.

## Evidence-based scope

Real mounted /api and /api/v1 routes, original POST /exports writer returning202, original ExportJobService singleton, original authorizer and exports reader. Fixture replaces storage roots/services with temporary actual File owners, provisions identity through original project owner, and stubs only background submission/snapshot provider/exporter to prevent actual export execution. It does not replace authorization or fake a successful cursor adapter. GET submission-call count and business bytes remain unchanged.

Final22 cover first/next/replay/final; original private-row ABA, delete/recreate, entire source-document recreate, project marker recreate; unmatched/foreign/wrong-local-actor edits not invalidating observed rows; empty bound window; zero-write missing/legacy rejection; mixed-source and collaboration-export rejection; original denied-source semantics; actual source root and singleton replacement;100-row pre-query window, overflow and empty matching query; hidden tail changes versus window reentry; original TaskCenter scope fence suppressing wholly rejected overflow; selected privateABA during original reader.

Original aggregate intentionally omits denied source403/404 rows. The existing local cursor contract is initial501 or continuation409 after projected-source mismatch, not direct403 propagation. The final test asserts exactly this contract and verifies no captured rows grant access.

No unresolved production issue found in the scoped local-export composition. No claim of collaboration exports, multi-source cursor, full history, cross-owner atomic snapshot, full ABA, external backup replay protection, single-worker execution, PG/model/hosted deployment/CI success. Tests actually ran in dot's cloud workspace with synthetic data; this is not a claim of hosted deployment verification.

## Retained unsuccessful/harness history

- baseline-red: original bfca production, original POST202 succeeds then both cursor endpoints return501; two intentional RED assertions.
- candidate-1799: original happy paths2 PASS,18 harness fixture-registration setup errors in supplementary module.
- candidate-1799-extra:2 fixture-registration setup errors. Neither setup error is a production defect.
- candidate-1799-final:21 PASS, one incorrect harness expectation of propagated403; corrected against original aggregate code and existing semantic cursor denial test. No production edits.
- candidate-1799-reviewed: final22 PASS, authoritative final independent suite. Counts overlap and must not be summed.

All summaries/logs/XML/module receipts, initial/final runners, final test source and before/after app manifests are retained in this folder. run.py uses240s; final run900.py uses900s with otherwise identical original isolated verifier. No test run timed out. No uploads were performed by the reviewer.
