# Backend query and existing identity/history contracts

## Fixed scope

- Public baseline: `4c5535481158de3ce7f0e7dbe5aa00d7058eccec`, tree `3a0e7f822eb9ad6cfe4e7b47580148c83cfcdda4`.
- Working branch: `work/hermia-backend-contracts-20261025`.
- Implemented on dot's independent cloud checkout, not the previous Codex cloud task or the user's computer.
- Frontend handoff inspected read-only: `f778eaec77e5cbda4c29766ced51455816180066`, `docs/delivery/INTERFACE_COVERAGE.md`. No frontend branch merge.
- The previously exported `0e9a847b` frontend increment is NOT included.

## Delivered scope

1. Production jobs: opt-in `owner`, `operation_id`, `limit`, and `offset` on the existing GET route. Original unpaged response and internal callers remain unchanged. See [query contract](../studio_production_query_backend.md).
2. Evidence and integration guidance for existing `project.incarnation`, AUDIO Timeline history/restore, and Asset undelete. See [identity/history contract](../studio_workspace_identity_audio_history_contract.md).

Only three production backend files change. Other additions are tests and documentation. No frontend, SDK, queue owner, permission owner, dependency manifest or lockfile change. No execution or automatic approval is introduced.

## Verification ledger

These runs overlap; do not add them into a unique test total.

| Run | Result | Evidence boundary |
| --- | --- | --- |
| Environment smoke: asset query, cursor, audio envelope | 124 passed, 38 PostgreSQL-only skipped | File backend; synthetic WAV with real CPU FFmpeg, no model calls |
| Initial query tests on original production code | 18 failed, 1 passed | Demonstrates absent filter/paging/validation behavior |
| Final new Production query tests | 41 passed | File/API, original guards, synthetic video/timeline queue metadata |
| Production compatibility set | 293 passed, 122 PostgreSQL-only skipped | 14 files; not the entire backend suite |
| Identity/history focused contracts and original lifecycle cases | 13 passed | Includes 5 new File/HTTP tests; no render/provider calls |
| Independent reviewer rerun of both new test files | 46 passed | Separate invocation; not additional unique coverage |
| Final independent rerun, including six additional probes | 52 passed, 3 warnings, exit 0 | 16.51 seconds; production file hashes unchanged; no blocking P1/P2 found |

The original collection failure caused by inherited XDG configuration and the test-only delete-response assumption are retained in local evidence. Neither is reported as a product regression. Test data paths were isolated below `.runtime`; dependency installation used a separate `.venv`. Original source and dependency locks were preserved.

Local evidence directories: `.runtime/backend-smoke-20261025`, `.runtime/production-query-20261025`, and `.runtime/review-backend-query-20261025`. Exact query commands, status codes and limitations are in the query contract. Product tests and independent review must be reported separately from any later remote publication verification.

## Explicit limitations

- This does NOT implement TaskCenter `G-TC-1`; that is a separate bounded aggregate with its own coverage limitations.
- Production pagination bounds response size, not storage reads, memory or sorting costs. No cross-owner or cross-request snapshot is promised.
- Existing owner validation is preserved, not strengthened into a new proof of every receipt field. In particular, ordinary queued Audio speech rows do not independently rehash every `receipt_digest` field; the reviewer observed the same behavior without queries. Existing request and binding checks remain unchanged.
- Timeline version restore is not a generic Audio Asset metadata/binary version archive. Asset `/restore` remains undelete.
- No real PostgreSQL, Windows Host, external provider/model/GPU, frontend integration or remote CI validation is claimed.
- `main`, other developers' branches, releases and private history are untouched. Publication must be confirmed by a separate remote HEAD readback; this document alone is not proof of upload.

## Follow-on: bounded TaskCenter projection paging

Fixed starting commit: `90c09981e7d9418c15eca4043338146aa5293549`.

The separate `G-TC-1` endpoint now supports explicit `limit`/`offset` paging of its existing authorized, filtered projection. It reports `observed_total`, not a global `total`, and always marks coverage completeness `NOT_ASSERTED`. Original reader scan windows and permission rules are unchanged. The old unpaged response keeps its exact fields, ordering and 500-item response cap. No frontend or SDK is changed. See [TaskCenter contract](../taskcenter_query_backend.md).

- Original-code red run: 41 failed / 8 passed.
- Final new TaskCenter cases: 65 passed, also independently rerun.
- Combined ten-file regression: final 195 passed / 6 failed (31.35 seconds); preceding 193 passed / 6 failed retained. **Neither run is a green suite**.
- All six failures reproduced with the same node IDs and failure messages in a complete `git archive` of the fixed baseline, isolated working directory and the same virtual environment. Loaded module paths and SHA256 values were checked against baseline Git objects by the independent reviewer. Process-replacement experiments are not the final baseline proof.
- Independent boundary probes: 73 passed. These are separate from, and overlap with, product tests; do not sum counts into unique coverage.

The six retained baseline failures involve an incomplete project-delete mock, an agent-review actor expectation, and export mocks/readiness expectations. This slice does not change their owners or weaken their assertions. Baseline and candidate logs remain under `.runtime/taskcenter-query-20261025`; independent probes and comparisons remain under `.runtime/taskcenter-independent-20261025`.

This is response paging over bounded observed task projections, not complete history traversal, a global queue index, or a storage performance improvement. Some original owners silently truncate their search window. A final page with `has_more=false` does not prove complete project history. Real PostgreSQL, external providers, Windows, frontend integration and remote CI are not claimed.
