# Script checkpoint 899d40d: original hosted CI terminal archive

All five original attempt-1 runs reached natural terminal states. Overall acceptance: **FAILED_OBSERVED / incomplete hosted backend CI**. No rerun, cancellation, source/index/workflow edit, push, or PR change was performed by this collector.

- Repository: `1785235376-blip/AI-Novel-Studio`; branch `feature/v2-narrative-platform`; existing Draft PR #47.
- API run head/published commit: `899d40df5273413d987f9ee98d41a7405ed16d0a`; parent `c491d1b0227a877eaa5bad7651ed22ba67463439`.
- Push checkout/event SHA: `899d40df5273413d987f9ee98d41a7405ed16d0a`.
- PR checkout/event merge SHA: `d059cf2cc3aa17e16ec77e7ed1c9edb1f4e45cfe`. Both trees are `01e338ea26b120f364919a94bc42ad14feb9d448`.
- Commit metadata, run head, revision receipts and backend coverage identities were checked separately. R123 deliberately tests a historical baseline.

## Terminal runs

- [Cloud CI / push / 38080738263](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38080738263): **FAILURE**, attempt 1, 11 jobs.
- [Cloud CI / pull_request / 38080743645](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38080743645): **FAILURE**, attempt 1, 11 jobs.
- [Local Interop V1 / push / 38080738340](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38080738340): **SUCCESS**, attempt 1, 3 jobs.
- [Local Interop V1 / pull_request / 38080743613](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38080743613): **SUCCESS**, attempt 1, 3 jobs.
- [Shared R123 evidence / pull_request / 38080743597](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38080743597): **SUCCESS**, attempt 1, 1 jobs.

## Full backend: exact incomplete and failed boundaries

Frozen collection: 11,417 tests per profile. File remains one original-order shard; PostgreSQL remains two shards (5,713 + 5,704). Original File 20-minute / PostgreSQL 55-minute budgets, assertions, skips and joins were not changed.

- File push: CANCELLED / INCOMPLETE_HOSTED_CI; 6,113 observed call passes, 3,216 setup skips; zero observed failed phase events. No final backend JUnit or pytest exit status; complete=false.
- File PR: CANCELLED / INCOMPLETE_HOSTED_CI; 6,534 observed call passes, 3,418 setup skips; zero observed failed phase events. No final backend JUnit or pytest exit status; complete=false.
- PostgreSQL shard 0 push: CANCELLED / INCOMPLETE_HOSTED_CI **and FAILED_OBSERVED_CALL**. Raw events show 3,621 call passes, 1 call failure, 1,824 setup skips. Failed node: `tests/test_v2_graph_text_assets.py::test_manual_refresh_completion_boundary_requires_archive_before_review[postgres-settling]`. No final backend JUnit or pytest traceback was generated before cancellation, so the exact assertion values are not established by this run.
- PostgreSQL shard 0 PR: CANCELLED / INCOMPLETE_HOSTED_CI; 3,784 call passes, 1,879 setup skips, zero observed failed phase events. No final backend JUnit or pytest exit status; complete=false.
- PostgreSQL shard 1 on each event: SUCCESS, complete=true, pytest exit 0; final JUnit 5,704 tests = 3,743 passed / 1,961 skipped / 0 failures or errors. 5,713 deselected belong to the other shard. Pytest time: push 2,976.57 s; PR 3,077.56 s.
- All six backend execution shards passed 174 coverage-harness tests before suite execution.
- Original File TCP on both events: SUCCESS, 2 original TCP tests plus 110 harness tests passed.
- Both strict File and PostgreSQL aggregate jobs on each event: FAILURE at `Require every execution job including original File TCP gate`; actual env is EXECUTION_RESULT=cancelled, TCP_RESULT=success. Artifact download, provenance join, exact full-coverage reconciliation and proof upload steps were SKIPPED. No backend-coverage proof artifact exists.

Raw phase counts above are partial observations, not final suite counts or proof that the remainder passed. Cancellation logs explicitly say “The operation was canceled”; timings align with the frozen 20/55-minute job budgets, but the unavailable check-suite annotation was not guessed.

## Creative, frontend, Windows and Interop

- Creative live browser on both events: **9 passed / 2 failed**; each failing test exceeded 180,000 ms while waiting in exact getByLabel/selectOption. Screenplay export fails at spec line 422; generic Script purpose at line 488. HTTP-only equivalents passed. Subsequent geometry/keyboard suite still passed 8/8.
- Original error PNGs show the dropdowns rendered; trace DOM contains wrapping LABEL/SPAN/SELECT with options and no explicit SELECT aria-label/id. `creative-failure-dom.json` preserves the exact observed fragments. This archive makes no current-source fix acceptance claim.
- Independent-media browser on both events: 17 passed / 0 failures / 0 skips; real File/HTTP with mock providers. No real model or paid provider calls.
- Legacy frontend on both events: SUCCESS; 2,428 unit passes / 8 old skips; type/build/token steps success. JUnit browser passes: geometry 9, business 2, experimental 7, R4 63, export recovery 1, functional surface 9, branch surface 1. Interop-client/browser steps also succeeded; complete original logs and compact artifacts retained.
- Windows Host on both events: fresh compile and 59 native/packaging + 3 environment fixture tests passed. Bounded native package receipts report smoke PASS, but interactive_desktop/user_acceptance remain NOT_RUN. No Windows executable or package ZIP was downloaded.
- Interop on both events: all three jobs SUCCESS. Each File/PG profile has 413 tests = 345 passed / 68 skipped. Times: push File 17.77 s, PG 512.84 s; PR File 28.77 s, PG 731.90 s. Windows pipe reference remains 8 MOCK_ONLY checks, real Desktop LOCAL_REQUIRED, cross-user hostile attempt NOT_RUN. Each preparation harness remains 23 MOCK_ONLY passes + 1 native-required NOT_RUN.
- R123 workflow SUCCESS means `ALL_THREE_KNOWN_DEFECTS_REPRODUCED_RED` at baseline `c6f2126115b52e17839d48efea091dc21ec08c61`, tree `eb80a9fa5f5aa6b8c2cbd0e1e67f7b7a48ac522f`; scripts_exit_zero_is_not_pass=true. This is not current-source independent security acceptance.

## Cache observations

All eight backend execution jobs completed the isolated cache-selection/setup initialization and reported initial pip cache **MISS**. Setup-python / dependency install seconds:
- Push TCP 12 / 22; File 9 / 22; PG0 11 / 19; PG1 10 / 20.
- PR TCP 10 / 20; File 12 / 21; PG0 11 / 19; PG1 10 / 20.
Both TCP jobs saved the cache. Both successful PG1 post steps logged “Failed to save: Unable to reserve cache” for the same key; they did not prove cache-save success. Cancelled File and PG0 jobs skipped their post setup-python step. No hit or causal performance improvement is claimed. `cache-observations.json` retains exact lines and timings.

## Integrity and retained boundaries

- 23 downloaded artifact ZIPs, 81,309,866 bytes, 585 members. All GitHub sizes/SHA-256 digests, CRCs and safe member paths verified; 29 original decoded job logs retained.
- Text and PNGs extracted; four failure trace ZIPs also individually verified (CRC/member hashes). Eight UI/media MP4 members remain inside their original artifact ZIPs, unextracted. No Windows payload downloaded.
- Both original Creative failure archives retained once: artifact 11680666681 SHA-256 b3857236dbc47d129dc504568ac1fbe7f4df6c00f6e56942c53d19c17001116a; artifact 11679774651 SHA-256 f20eb0cc175ee56516ec0fa15520b69dbf6be16f76056a7aafae7f6871531c44.
- Four large frontend PNG parts remain remote (~80 MB total); their metadata/digests are retained. Compact frontend receipts were used; duplicate full frontend payloads were not downloaded. Windows Host/acceptance payload metadata retained only.
- Historical c491 local PG16 failures and zero-job Cloud failure, and e6ff incomplete File/failed PG settling remain FAILED_OBSERVED as historically recorded. New results do not erase them. Local Chromium EPERM and historical independent security review BLOCKED remain separate.
- Focused local tests and later unpublished development are not substitutes for this exact hosted checkpoint. Full-source acceptance is false.
- Historical denied artifacts 11615127270/11618169199 were never requested. The allowlist-blocked check-suite annotation endpoint was neither retried nor rerouted.

Files: `terminal.json` (compact receipt), `terminal-detail.json` (full step/detail record), `artifact-integrity.json`, `trace-integrity.json`, `backend-execution-observations.json`, `cache-observations.json`, `source-verification.json`, and `archive-files.sha256.json`.

Final verification: 2026-10-10T20:40:05.002351+00:00.
