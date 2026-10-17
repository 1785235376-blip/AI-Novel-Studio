# Second four-feature merged integration

Scoped primary verification PASS on `b5f52c823b4df58ffe69ec309bfc2fc0e4a114fe`, tree `c69fb267e26f3692f625deb0355bf5c1c3c13ef3`. This is actual merged-source execution, not a sum of isolated branch passes. Independent acceptance also PASS on the same frozen source; details follow.

## Sources and preserved contracts

The four source commits are exact ancestors with every changed runtime/test/document blob preserved: Director `c7c31e3`, interactive membership `69a0b1c`, comic framing `8a113f5d083c1c7c97668bbe7a47c8405f947961`, restored-file verifier `7188ce7560c4f4563520cd9d59ce6b24541c4850`. The only additive integration test was separately reviewed and committed in the tested HEAD. No existing test or product implementation was edited for this run.

All 1,318 pre-wave2 tests and 8,941 historical documents in baseline `d10b72c` retain exact blobs. Full tracked-tree SHA256 freeze covers 12,113 files. Protected runner/infrastructure and original PUBLIC suites are unchanged. PUBLIC manifest SHA256 is `353b92aff6116d873ea4402a1ef627e7899214b46ba823a9b4300ba75c5d0448`; its sole baseline addition is `app/creative/director_terminal_evidence.py`.

The unchanged original runner's actual source map contains 2,609 paths: the prior 2,600 plus nine listed additions, no removals. All nine runner receipts have identical before/after maps and current bytes; tracked-tree guard also passes after all gates. This separately protects historical docs and manifest files outside the runner map.

## Actual serial primary gates

- Natural startup plus actual original-runner child PathFinder checks before/after: PASS, clean approved Python/dependency origins, no product or pytest imported by probes.
- Committed portable comic legacy verifier: PASS using its real `--source` / `--work` CLI on a fresh owned copy. Original normalization, report, approved row, stored state and review digest match; PNG and approved ZIP are byte-identical without reapproval. This is new evidence; prior branch NOT_RUN status for this portable script remains historically intact.
- Combined backend: 1,482 passed, 1 skipped, 494 PostgreSQL-marked cases deselected; 51 explicit nodes/files, 226.10 seconds. Includes private Director publication/races, generic File persistence, Director/Graph, installed-CPU Audio, B05, membership, comic, backup/recovery and the additive cross-feature test.
- Combined frontend: 85 files, 1,262 tests passed; one worker, no file parallelism, no cache, original Vite config. Includes prior Canvas/Prompt/Audio/B05 baseline plus Director/membership/comic controllers.
- Forced TypeScript, Vite production build and design token guard: PASS; 52 token-guard files.
- Actual offline four PUBLIC suites: 87 passed. Two wheels and two sdists built using existing installed tools. Every receipt-listed source payload and all eight affected backend modules match current-source hashes. Archives are read without extraction/installation; per-archive hashes and durable payload inventories are retained.

The sole font skip is the unchanged `test_real_pinned_cjk_font_readable_text_and_overflow`, which requires an unavailable real pinned OFL font. No font replacement, mock or download was used. Existing Pydantic/Starlette warnings, duplicate React key warning and Vite large-chunk advisory remain in raw logs.

The additive test proves original generic `GenerationRepository.save` creates its real generation-write lock housekeeping; original backup/restore retains it; the new verifier accepts exact restored bytes read-only; and a fresh original repository returns the exact synthetic record. All source/backup/target snapshots remain unchanged through verification and read. It does not prove Director authority, application startup/compatibility, readiness, database recovery or model execution.

## Limits and unresolved baseline

Five known failures in `tests/test_v2_studio_audio_listing.py` remain unresolved and excluded, not passed:
1. `test_malformed_tail_is_never_truncated_or_returned[_studio_body-value0-STUDIO_AUDIO_OPERATION_UNSUPPORTED]`
2. `test_original_per_receipt_limits_still_apply_to_tail[prompt-STUDIO_AUDIO_PROMPT_INVALID]`
3. `test_original_per_receipt_limits_still_apply_to_tail[sources-STUDIO_AUDIO_SOURCE_INVALID]`
4. `test_graph_binding_at_tail_is_still_validated`
5. `test_source_snapshot_binding_is_checked_without_refreshing_history`

Their pre-existing immutable-request hash fence yields `STUDIO_AUDIO_JOB_BINDING_CHANGED` before deeper expected validation. No repair or rerun is claimed here. Full repository/product status remains partial. Private Director publication is opt-in historical evidence only and grants no durable adoption/review authority; restored-file verification is byte-only. Real browser/visual/native Windows, PostgreSQL, live providers, user data and readiness are NOT_RUN. No installations, network/provider/paid actions, push, release, main merge or user-computer operation occurred.

All test/runtime verification used only `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python`; the separate installed packaging-build interpreter was hash-pinned to `fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7`. No primary gate failed. Parent owns the evidence commit and canonical inventory reconciliation.

## Independent acceptance binding

Independent review and actual reruns passed on the same `b5f52c8` source: backend 270 passed, 1 original font skip, 86 PostgreSQL exclusions; UI 147 tests across 11 files; committed portable comic golden exact. Five original-runner independent receipts retain the identical 2,609-source map, and all 12,113 tracked hashes remain unchanged. The reviewer independently reopened the actual two wheels and two sdists and verified all archive and source payload hashes. These are repeat acceptance runs, not additional capability counts.

Independent report and finalized index: `../parallel-integration-wave2-independent-20261017/report.md` and `evidence-index.json`. This report's companion index binds the independent index SHA256 and verifies every indexed evidence file plus all five independent receipt/log/source hashes. Existing raw primary and independent artifacts were preserved.
