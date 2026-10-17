# Storyboard image handoff test evidence

Final stable result: **176 unique cases passed across 6 suites**. This includes 129 new additive cases (82 controller, 19 fully mounted host, 28 direct recipient wrapper) and 47 unchanged regressions (24 original storyboard panel, 15 original navigation, 8 original workspace). Counts are not added across reruns.

| Run | Exit | Passed | Failed | Source changed | Use |
| --- | ---: | ---: | ---: | --- | --- |
| 1 | 0 | 64 | 0 | false | Stable intermediate verification, superseded |
| 2 | 1 | 124 | 17 | true | Diagnostic only; not acceptance |
| 3 | 0 | 145 | 0 | false | Stable prior verification, superseded |
| 4 | 0 | 168 | 0 | false | Stable prior verification, superseded |
| 5 | 0 | 176 | 0 | false | Final stable targeted verification |

`runs.json` records exact commands, working directory, exit codes, counts, timestamps and raw-log SHA-256 values. Each run preserves its raw stdout/stderr log and before/after source SHA-256 snapshots. Snapshot paths are relative to `frontend/`. `SHA256SUMS` covers all evidence files except itself.

## Run 2: preserved failure and source overlap

The runtime owner disclosed a controller edit at 23:53:46 UTC during run 2. Its before/after controller hashes differ; therefore the entire run is diagnostic only. No tests or assertions were edited during that run.

There were also 17 genuine failures in the fully mounted new-host suite: the recipient retired immediately after route entry and hid the existing-document directory button. These failed before the storyboard controller mounted. The host's automatic production asset read acquired the unrelated shared busy semaphore on handoff entry, triggering permanent recipient retirement. The runtime owner gated that automatic read and workflow activity while the recipient is active. The tests were not weakened. Run 3 verifies the corrected route on an unchanged source boundary; run 4 adds direct wrapper retained-handler and cache-retirement coverage on a stable boundary.

## Scope

The additive suites use the original controller and a real mounted IndependentStudioWorkspace → asset browser → recipient → panel → controller → production client flow with controlled fetch responses. They cover explicit GET-only inspection and selection, one exact original binding POST, unchanged authored shots/provenance, version advance and revoked approval, cancellation/dirty navigation, source and target invalidation, delayed/ABA/ownership fences, malformed receipts, unknown outcomes, no automatic retries, and authoritative observations that retain uncertainty.

All runs use one worker, disabled cache and default timeouts. Existing test files were unchanged. These are synthetic controlled frontend tests, not live backend, model execution, browser/visual acceptance, or release acceptance.

## Forced type check

After run 4, `./node_modules/.bin/tsc -b --force --pretty false` exited 0 with no diagnostics. The before/after source hashes are identical. Its zero-byte raw log, exit file and source snapshots are retained as `typecheck4.*`.

Run 5 adds owner-output false→true ABA fences at the recipient and original controller layers, including delayed source/target/POST results. A positive case proves a new callback identity with unchanged true authority does not retire the recipient. All 176 unique cases pass on identical before/after source hashes. The final forced TypeScript check also exits 0 without diagnostics or source changes; evidence is retained in `typecheck5.*`. Earlier run/type-check receipts remain intact.
