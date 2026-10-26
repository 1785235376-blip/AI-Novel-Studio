# Fresh reconstruction independent review

This report belongs to newly reconstructed source and newly executed evidence. The former shared-workspace bf0bbdb2 package, its logs and archive were not recovered and are NOT claimed present. Prior test counts are not reused.

Final source: 14650cef5877b06e69eaa42abb2eb03b066095e1; tree d383de3562235fbe78f02cb5b42591591b310e80; app tree 775a084c75dd5cfd7ccf0189060b056bf8f1c309. Independent detached checkout uses scratch-local runtime and logs.

Fresh e5 baseline: 26 reconstructed tests, 22 failed and 4 passed, pytest exit 1. Original app source manifest: 600 files unchanged, no foreign app modules. The three newly added tests are separately hashed and identical to final versions. Request-context cases: 10 failed/2 passed; observer cases: 4 failed/2 passed; real h11 pipelined TCP: 8 failed. These fail for the intended inherited-budget/strictness or stale observer attribution assertions, not setup errors.

Fresh final: 79 passed, pytest exit 0, 601 app source hashes unchanged, no foreign app modules. Includes the 26 reconstructed cases plus 53 donor mixed-source, race, empty/actual-aggregate denial and observer receipt cases. Counts overlap parent groups and cannot be added to them. These are new test implementations and runs; they are not represented as byte-for-byte restoration of the lost independent94/15 group.

The production fix is scoped to the existing five-file reviewed mixed port plus three request-isolation files. Store, identity, scope, ExportJobService and canvas adoption authorization remain byte-identical to e5. Budget and coordination changes add context token/reset helpers; middleware establishes a clean budget and strict marker at each independent ASGI entry, restoring caller contexts in finally. Original budget numbers, route selection, error policy, locks, nested same-request budget reuse and monotonic strict nesting remain unchanged.

Independent context tests cover unrelated POST/GET/websocket, fresh compatible and strict asset requests, simultaneous requests, nested reuse, exception/cancellation restoration and true request-owned background context retention. Observer tests compile only the exact helper app function without importing its global hooks and preserve genuine GET-owned background attribution.

Eight socket tests use real uvicorn h11, send two HTTP requests in one socket write, parse both exact Content-Length responses and verify strictness/budget/expiry. No reset_contextvars configuration masks the product boundary. The downstream endpoint reports context only; original business-owner TCP is the parent's separate acceptance, not claimed by this scope probe.

No real credential, model, private project or user workstation is used. Windows, PG, browser, model/GPU and CI are unverified here. Existing F37 and Windows asset-list observations remain unresolved; no hard RSS/CPU/wait limits, strong historical ABA or cross-owner atomic snapshot claim. No publication or main modification.
