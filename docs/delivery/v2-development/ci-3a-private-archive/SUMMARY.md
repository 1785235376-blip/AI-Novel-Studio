# 3a234ed original hosted CI: final receipt

Final verification: 2026-10-10T23:28:51.916450+00:00. All five original attempt-1 runs and all 29 jobs are terminal.
No collector rerun, cancellation, source/index/workflow change, push or PR change was performed. Full-source acceptance remains false.

Head 3a234ed242a2d15698560752d6ac3a982da7c350; PR merge checkout 0d9d647c05da23582bbdd09c09e38c176f85b152; both have tree 9b2e3e304f3ca603f1a18681194df1ddf4528de9. PR state: {'number': 47, 'state': 'open', 'draft': True, 'head_sha': '3a234ed242a2d15698560752d6ac3a982da7c350', 'merge_commit_sha': '0d9d647c05da23582bbdd09c09e38c176f85b152'}.

## Original run outcomes
- Local Interop V1 / pull_request / 38091679679: success; attempt 1; https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38091679679
- Shared R123 evidence / pull_request / 38091679852: success; attempt 1; https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38091679852
- Cloud CI / pull_request / 38091679805: cancelled; attempt 1; https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38091679805
- Local Interop V1 / push / 38091673128: success; attempt 1; https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38091673128
- Cloud CI / push / 38091673135: cancelled; attempt 1; https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38091673135

Original 29-job conclusions: {'success': 22, 'cancelled': 3, 'failure': 4}.

## Exact full-backend observations
Frozen inventory: 11,901. Original File one shard, PG two shards, 20/55-minute execution budgets and strict joins are unchanged.
- pull_request postgres shard 0: COMPLETE_SHARD_PASS; assigned 5949, complete=True, pytest_exit=0. Final JUnit: 5949 tests = 3968 passed / 1981 skipped / 0 failures / 0 errors, 2964.528 seconds. Raw phases={'setup/skipped': 1981, 'teardown/passed': 5949, 'setup/passed': 3968, 'call/passed': 3968}; failed phase events=[].
- pull_request postgres shard 1: COMPLETE_SHARD_PASS; assigned 5952, complete=True, pytest_exit=0. Final JUnit: 5952 tests = 3898 passed / 2054 skipped / 0 failures / 0 errors, 2677.694 seconds. Raw phases={'setup/passed': 3898, 'call/passed': 3898, 'teardown/passed': 5952, 'setup/skipped': 2054}; failed phase events=[].
- pull_request file shard 0: INCOMPLETE_HOSTED_CI; assigned 11901, complete=False, pytest_exit=None. No final backend JUnit. Raw phases={'setup/passed': 6028, 'call/passed': 6027, 'teardown/passed': 9188, 'setup/skipped': 3161}; failed phase events=[].
- push postgres shard 0: COMPLETE_SHARD_PASS; assigned 5949, complete=True, pytest_exit=0. Final JUnit: 5949 tests = 3968 passed / 1981 skipped / 0 failures / 0 errors, 3007.229 seconds. Raw phases={'setup/skipped': 1981, 'teardown/passed': 5949, 'setup/passed': 3968, 'call/passed': 3968}; failed phase events=[].
- push postgres shard 1: INCOMPLETE_HOSTED_CI; assigned 5952, complete=False, pytest_exit=None. No final backend JUnit. Raw phases={'setup/passed': 3812, 'call/passed': 3811, 'teardown/passed': 5803, 'setup/skipped': 1992}; failed phase events=[].
- push file shard 0: INCOMPLETE_HOSTED_CI; assigned 11901, complete=False, pytest_exit=None. No final backend JUnit. Raw phases={'setup/passed': 6030, 'call/passed': 6029, 'teardown/passed': 9190, 'setup/skipped': 3161}; failed phase events=[].
- Failed phase events observed in these six new original full-backend shards: 0. These observations do not erase or relabel historical e6ff/899/e29 results.
- Raw phase counts are partial execution observations, never final pass counts or proof that unseen tests passed.

## Strict aggregate gates
- pull_request Backend / postgres / 114338623499: failure; failed=['Require every execution job including original File TCP gate']; skipped=["Download this attempt's exact backend shard receipts", "Download this attempt's exact original TCP receipts", 'Validate provenance and create byte-identical aggregation copies', 'Require exact complete collection and successful outcomes in both profiles', 'Upload complete collected-coverage proof', 'Post Run actions/setup-python@v5.6.0'].
- pull_request Backend / file / 114338623509: failure; failed=['Require every execution job including original File TCP gate']; skipped=["Download this attempt's exact backend shard receipts", "Download this attempt's exact original TCP receipts", 'Validate provenance and create byte-identical aggregation copies', 'Require exact complete collection and successful outcomes in both profiles', 'Upload complete collected-coverage proof', 'Post Run actions/setup-python@v5.6.0'].
- push Backend / postgres / 114338954272: failure; failed=['Require every execution job including original File TCP gate']; skipped=["Download this attempt's exact backend shard receipts", "Download this attempt's exact original TCP receipts", 'Validate provenance and create byte-identical aggregation copies', 'Require exact complete collection and successful outcomes in both profiles', 'Upload complete collected-coverage proof', 'Post Run actions/setup-python@v5.6.0'].
- push Backend / file / 114338954274: failure; failed=['Require every execution job including original File TCP gate']; skipped=["Download this attempt's exact backend shard receipts", "Download this attempt's exact original TCP receipts", 'Validate provenance and create byte-identical aggregation copies', 'Require exact complete collection and successful outcomes in both profiles', 'Upload complete collected-coverage proof', 'Post Run actions/setup-python@v5.6.0'].
Official complete-coverage proof artifacts: []. Collector partition reconciliation is not an official complete-coverage proof.

## Creative, frontend and scoped evidence
- pull_request, local-interop-postgres-0d9d647c05da23582bbdd09c09e38c176f85b152, local-interop.xml: 345 passed / 68 skipped / 0 failures / 0 errors.
- pull_request, local-interop-file-0d9d647c05da23582bbdd09c09e38c176f85b152, local-interop.xml: 345 passed / 68 skipped / 0 failures / 0 errors.
- pull_request, v2-creative-browser-0d9d647c05da23582bbdd09c09e38c176f85b152-attempt-1, receipts/v2-creative-workbench.xml: 8 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, v2-creative-browser-0d9d647c05da23582bbdd09c09e38c176f85b152-attempt-1, receipts/v2-creative-live.xml: 12 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, frontend-compact-0d9d647c05da23582bbdd09c09e38c176f85b152, receipts/export-browser.xml: 1 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, frontend-compact-0d9d647c05da23582bbdd09c09e38c176f85b152, receipts/functional-surface-browser.xml: 9 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, frontend-compact-0d9d647c05da23582bbdd09c09e38c176f85b152, receipts/geometry.xml: 9 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, frontend-compact-0d9d647c05da23582bbdd09c09e38c176f85b152, receipts/frontend.xml: 2442 passed / 8 skipped / 0 failures / 0 errors.
- pull_request, frontend-compact-0d9d647c05da23582bbdd09c09e38c176f85b152, receipts/business.xml: 2 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, frontend-compact-0d9d647c05da23582bbdd09c09e38c176f85b152, receipts/r4-ux.xml: 63 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, frontend-compact-0d9d647c05da23582bbdd09c09e38c176f85b152, receipts/experimental.xml: 7 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, frontend-compact-0d9d647c05da23582bbdd09c09e38c176f85b152, receipts/branch-surface-browser.xml: 1 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, backend-tcp-0d9d647c05da23582bbdd09c09e38c176f85b152-attempt-1, tcp-harness.xml: 110 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, backend-tcp-0d9d647c05da23582bbdd09c09e38c176f85b152-attempt-1, sync-tcp.xml: 2 passed / 0 skipped / 0 failures / 0 errors.
- pull_request, v2-independent-media-0d9d647c05da23582bbdd09c09e38c176f85b152-attempt-1, v2-independent-live.xml: 18 passed / 0 skipped / 0 failures / 0 errors.
- push, local-interop-postgres-3a234ed242a2d15698560752d6ac3a982da7c350, local-interop.xml: 345 passed / 68 skipped / 0 failures / 0 errors.
- push, local-interop-file-3a234ed242a2d15698560752d6ac3a982da7c350, local-interop.xml: 345 passed / 68 skipped / 0 failures / 0 errors.
- push, frontend-compact-3a234ed242a2d15698560752d6ac3a982da7c350, receipts/export-browser.xml: 1 passed / 0 skipped / 0 failures / 0 errors.
- push, frontend-compact-3a234ed242a2d15698560752d6ac3a982da7c350, receipts/functional-surface-browser.xml: 9 passed / 0 skipped / 0 failures / 0 errors.
- push, frontend-compact-3a234ed242a2d15698560752d6ac3a982da7c350, receipts/geometry.xml: 9 passed / 0 skipped / 0 failures / 0 errors.
- push, frontend-compact-3a234ed242a2d15698560752d6ac3a982da7c350, receipts/frontend.xml: 2442 passed / 8 skipped / 0 failures / 0 errors.
- push, frontend-compact-3a234ed242a2d15698560752d6ac3a982da7c350, receipts/business.xml: 2 passed / 0 skipped / 0 failures / 0 errors.
- push, frontend-compact-3a234ed242a2d15698560752d6ac3a982da7c350, receipts/r4-ux.xml: 63 passed / 0 skipped / 0 failures / 0 errors.
- push, frontend-compact-3a234ed242a2d15698560752d6ac3a982da7c350, receipts/experimental.xml: 7 passed / 0 skipped / 0 failures / 0 errors.
- push, frontend-compact-3a234ed242a2d15698560752d6ac3a982da7c350, receipts/branch-surface-browser.xml: 1 passed / 0 skipped / 0 failures / 0 errors.
- push, backend-tcp-3a234ed242a2d15698560752d6ac3a982da7c350-attempt-1, tcp-harness.xml: 110 passed / 0 skipped / 0 failures / 0 errors.
- push, backend-tcp-3a234ed242a2d15698560752d6ac3a982da7c350-attempt-1, sync-tcp.xml: 2 passed / 0 skipped / 0 failures / 0 errors.
- push, v2-independent-media-3a234ed242a2d15698560752d6ac3a982da7c350-attempt-1, v2-independent-live.xml: 18 passed / 0 skipped / 0 failures / 0 errors.
- push, v2-creative-browser-3a234ed242a2d15698560752d6ac3a982da7c350-attempt-1, receipts/v2-creative-workbench.xml: 8 passed / 0 skipped / 0 failures / 0 errors.
- push, v2-creative-browser-3a234ed242a2d15698560752d6ac3a982da7c350-attempt-1, receipts/v2-creative-live.xml: 12 passed / 0 skipped / 0 failures / 0 errors.
- Both Creative jobs pass the original live-browser suite, including the formerly failing Script reload path, plus geometry. This does not replace the historical e29 browser failure record.
- R123 SUCCESS means the historical c6f2126 RED defects reproduced, not a repaired/current-source independent audit.
- Hosted bounded Windows smoke remains distinct from user Windows/GPU acceptance; native smoke receipts explicitly mark interactive_desktop and user_acceptance NOT_RUN. No Windows binary archive was downloaded.
- Independent-media providers are synthetic/mock. Selected local tests and real-CPU malformed raw DRAFT rejection remain separate; the real-CPU acceptance harness FAIL is unchanged.

## Cache observations
- pull_request Backend execution / postgres / shard 1: hit=True, restored=True, actual install=True, pip check clean=True, primary hit not saving=True, post setup skipped=False.
- pull_request Backend execution / original File TCP: hit=True, restored=True, actual install=True, pip check clean=True, primary hit not saving=True, post setup skipped=False.
- pull_request Backend execution / postgres / shard 0: hit=True, restored=True, actual install=True, pip check clean=True, primary hit not saving=True, post setup skipped=False.
- pull_request Backend execution / file / shard 0: hit=True, restored=True, actual install=True, pip check clean=True, primary hit not saving=False, post setup skipped=True.
- push Backend execution / file / shard 0: hit=True, restored=True, actual install=True, pip check clean=True, primary hit not saving=False, post setup skipped=True.
- push Backend execution / original File TCP: hit=True, restored=True, actual install=True, pip check clean=True, primary hit not saving=True, post setup skipped=False.
- push Backend execution / postgres / shard 0: hit=True, restored=True, actual install=True, pip check clean=True, primary hit not saving=True, post setup skipped=False.
- push Backend execution / postgres / shard 1: hit=True, restored=True, actual install=True, pip check clean=True, primary hit not saving=False, post setup skipped=True.
No new cache-save success or causal speedup is inferred.

## Integrity
{"downloaded_artifacts": 23, "zip_bytes": 39577499, "member_count": 622, "all_sizes_and_digests_match": true, "all_zip_crc_pass": true, "windows_binaries_downloaded": false, "job_log_count": 29, "nested_trace_count": 0}
All downloaded archives verified against GitHub size/SHA-256 and ZIP CRC, with safe member paths. Exact binary/omitted payload metadata is indexed, but those payload bytes were not downloaded or verified. Original archive ZIPs preserve all downloaded members.
No new failure trace was produced by the successful original Creative runs; their screenshots and reports are preserved. Historical failure traces remain only in their original archive.

## Files
terminal.json, terminal-detail.json, handoff-summary.json, runs-terminal.json, run-*-terminal.json, artifact-index.json, artifact-integrity.json, source-verification.json, cache-observations.json, backend-execution-observations.json, collector-crosscheck.json and archive-files.sha256.json.

## Boundaries
- All results belong to the original 3a234ed attempt-1 runs; historical runs remain unchanged and later edits/runs cannot replace these.
- Original File one shard / PostgreSQL two shards, 20/55 minute execution budgets and strict joins unchanged.
- Cancelled or timed-out suites remain incomplete; any observed failed phase is preserved, never relabeled capacity-only.
- Raw phase counts are partial observations, not final JUnit counts or proof that unseen tests passed.
- R123 workflow success reproduces historical c6f2126 defects RED, not current-source independent security acceptance.
- Hosted bounded Windows smoke is not user Windows/GPU acceptance, interactive desktop, installer, signing, release or real-model acceptance.
- Selected local File/PG/UI checks and malformed real-CPU raw DRAFT rejection are separate from hosted CI; the real-CPU acceptance harness FAIL remains.
- Historical independent audit BLOCKED remains; this collector is evidence archival, not a separate audit.
- Cache HIT/restore and actual install/check are reported separately; no causal performance improvement is claimed.
- Historical denied artifacts 11615127270/11618169199 were never downloaded or rerouted.
- No check-suite annotation endpoint or alternate credential route was accessed. Timeout cause is not guessed beyond logs and frozen budgets.
- Canonical per-report JUnit results must not be summed with duplicate copies in the same artifact.
