# Acceptance results

This delivery distinguishes deterministic implementation, exact-source tests, native/runtime quality and user acceptance. All forty IDs, seven waves, exact allowlists/dependencies, default-OFF and server-enforced V1 override are registered and tested. A registered or locally tested package is not automatically a fully accepted product capability.

## Published source receipts

- F00 `ad17f905` and isolated File lifecycle repair `0e5ea915`: both push and PR hosted runs passed.
- First UX slice and corrections `fc9e39d`: PR and the targeted duplicate-push rerun passed all five lanes. Later source is not covered by that result.
- Wave 2/3 `12745cbb`: File/PG/Windows passed; browser failures were retained and repaired in subsequent commits.
- Wave 4/5 plus broker cancellation repair `e12db8d`: File and both Windows passed; R4 browser 22/25 passed. PostgreSQL/frontend still failed. See WAVE_4_5_CI_CORRECTIONS.md for the actual errors and unchanged assertions.
- Correction `60314f9d`, exact tree `cea3e3bada5ab113576945d1528eb21efd594371`: push `37359470961` and PR `37359477778` are pending. Correction checks passed 78 File reader/portable cases and 20 mounted multilingual File cases, with actual PG parameters explicitly excluded locally.

## Next pinned full integration

Runtime `d2390d12cea037aa848b769d1f87822922832258` includes concrete bounded slices for all forty packages. Full File-compatible execution: 3,367 passed / 9 skipped / 993 PostgreSQL-only deselected in 277.29 seconds. The separately enabled TCP case passed and remains an explicit skip in the generic full run. Full frontend: 932 passed / 6 optional HTTP skipped; types, production build and 42-file token guard passed. Original two-process loopback synchronization: 1 passed. App is 619.08 kB minified plus a deferred 474.00 kB workbench; the large App warning remains visible.

Hosted browser is the real React/File evidence route; local Chromium is unavailable under the established launch restriction and was not retried. PostgreSQL results must come from its real hosted service, with no skipped marked-PG tests accepted. U13_BROWSER_MEASUREMENTS.md provides actual synthetic Linux/Chromium/File measurements and their method, not physical input latency.

## Separate gates

Independent follow-up review: **BLOCKED**, with original error/scope retained in SECOND_SLICE_REVIEW_STATUS.md. Reported implementation defects have regression repairs; this is not independent review closure.

Real model/GPU/interactive Windows/target-software/user acceptance: **NOT_RUN** unless a specific package receipt states a narrower native build/parser result. No paid API, private credentials, automatic runtime changes, merge, release or deployment occurred. Existing R3 exact-parent evidence in BASELINE_RECEIPT.md is historical and not added to new test counts.

## Final workspace/sample and accessibility extension

FINAL_UX_CI_CORRECTIONS.md records the subsequent bounded U01/U10 loops and all observed 344062df failures. Full File-compatible backend at `a6815ae`: 3,409 passed / 9 skipped / 1,035 actual-PG-only deselected, 289.03 s. Backend code remains unchanged through the later accessible-label and fixture-only repairs. Final full UI: 971 passed / 6 optional HTTP skipped; types/build/token guard passed. Real TCP synchronization: 1 passed / 15.49 s. Corrected fork inventory focused run: 42 passed / 39 PG-only deselected. App is 634.69 kB plus deferred workbench 477.43 kB minified; warning retained. Exact new-head hosted results remain pending at this receipt.

## Real 1d results and screenshot-driven correction

PR 37363904465 at 1d1b9756: actual PG 3,411 passed / 1,042 skipped / zero failures/errors; unchanged postgres_gate rejects any skipped marked-PG contract. Of the skips, 1,033 are File-only, the remainder are explicit native/legacy/opt-in TCP boundaries. PR retry preserved PG and Windows compile, passed Windows package, and ran R4 browser 34/35. File remained cancelled/unexecuted. The initial queued cancellations have no exposed cause in available metadata; root confirmed no user stop or intentional cancellation.

Named task-center region and screenshot-discovered editor-chrome corrections are in afa975a. Full UI 978 passed / 6 optional HTTP skipped, types/build/token checks passed. Backend/CI/dependency source is unchanged. EDITOR_CHROME_REPAIR.md and the retained source-specific evidence distinguish functional execution, known visual regression, its repair and the still-pending new hosted visual checks. These results do not close the blocked independent review.

### Toolbar action-hit repair

Pinned UI `81af92aa5c8f363f73edae9cf0233460209908ab`: full frontend **981 passed / 6 optional HTTP skipped**, types/build/token guard passed. Predecessor 038c322d passed actual File/PG/Windows and all new prose geometry, but retained 34/35 R4 and 1/2 business because the sidebar-edge toggle covered Save/export targets. The new consumer repair retains original click/download checks and requires a new hosted result. See EDITOR_CHROME_REPAIR.md; this is not an independent-review closure.
