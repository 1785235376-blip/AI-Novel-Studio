# M1–M3 fixed-source validation

Reporting date: 2026-10-28, Asia/Shanghai. Original execution-host UTC timestamps are retained in receipts without rewriting them to the client reporting date.

The user authorized a fresh isolated local GitHub clone and synthetic validation after the initial M0 checkpoint. All source, fixtures, evidence and dependencies used here are below `D:\PoemSeed-Unified-20261027-94f1c72e`. No old local project/task/media was opened; no paid model or GPU inference was used.

## M1: original File protections with the missing mixed cursor

B was cherry-picked with provenance as `f02ff272ecbef9bdc007c4b28cca2d47b08f8ecc`. Its sole source commit is `f6473e307e9d0501a41dc46dd991645a437103d7`; the existing asset-protection and TaskCenter ancestor merge in A was retained rather than reconstructed.

One real composition-test conflict was reproduced before adaptation: A's TCP test still expected local semantic_import+exports to return 501, but B correctly returned 200. The original red test exited 1 with unchanged source and no timeout. It was replaced by a genuine supported-pair pagination/replay/zero-write test, keeping other unsupported combinations and collaborative mixed queries as refusals. The change did not relax a production permission check.

Fixed A+B verification commit: `7387dd1f6a45e2ee755b0268885617c9b7ff7085`; tree: `0ea839400bdd2ec7e5200324dcab5e97e36a0ed9`. Clean detached verification directory: `m1-verification`.

| Separate group | Passed | Process seconds | Exit / timeout |
| --- | ---: | ---: | --- |
| Real TCP composition | 4 | 249.993 | 0 / no |
| File guards | 150 | 17.882 | 0 / no |
| TaskCenter | 357 | 66.544 | 0 / no |
| Original owner/lifecycle | 187 | 23.495 | 0 / no |
| Windows processes | 26 | 32.708 | 0 / no |

Each group has zero failures/errors/skips, `complete_pass=true`, 1046 identical before/after source/test/script hashes, a clean unchanged checkout and no external app modules. Group counts are not added into a unique total. The TaskCenter group includes the original single-source and local mixed cases plus independent actual-aggregate denial and registry-race cases.

The real TCP extension covers exact six-row original reader order, six cursor pages, repeated-page replay, parameter canonicalization, bounded safe projection, both selected source writers invalidating the cursor, unrelated Timeline writes not invalidating it, old-token 409 across process restart, fresh reads after restart, and exhausted Asset-only budgets not leaking into TaskCenter. Original 200/100 windows and unsupported-mode refusals remain.

Ten original TCP subprocess audit receipts show 286 completed business GETs, zero command/business/strict writes and zero strict-mode file/directory creation. Two ordinary-mode processes each performed one original compatible lock-byte initialization. Stub exporter calls were explicitly authorized fixture POSTs. Child app modules all came from the detached verification checkout.

Raw commands, logs, JUnit, source hashes, module provenance and original TCP audit are in [M1_COMBINED.zip](evidence/M1_COMBINED.zip); [archive hash/size](evidence/M1_COMBINED.json). The archive also retains the original obsolete-assertion failure. It has been read back and every embedded manifest SHA256 verified.

## M2: latest frontend

C was normally merged in `9c01565800931bd1ef49e9949a65e130f754b349`, tree `3eabe753c2036966a42bc6d9bc8f8a1afe792678`. [M2_CONFLICTS.md](M2_CONFLICTS.md) records all seven files and semantic owner decisions.

An independent fixed-commit AST/text review confirmed 26 protected A symbols retained verbatim, including protected production observations/recovery, canvas selection/source epochs and TaskCenter retirement/discard gates. The strict C `canvas_image_node` parsing and `.rcv width > 0` checks remain. `App.tsx` and the main API/client/canvas components match C where appropriate. A+B backend/root scripts/package/Vite config are unchanged by the merge.

The first merged build found duplicate ImageRebuild task bindings created outside textual conflict markers; deduplication fixed TS2451. The corrected build exited 0 in 38.28 seconds. An initial wrong-directory wrapper failure and the compiler failure remain preserved as development evidence. Build success is not full frontend or browser acceptance.

## M3: first formal IMAGE result association

The original application process, original File owners, real loopback HTTP and a deterministic local A1111 Mock provider reproduced 403 under both `/api` and `/api/v1` after legitimate preview, queue, execute, candidate read and explicit review. The test asserted 200, therefore failed twice on the pre-fix source. Refusal preserved Canvas/history/Job/Asset and only one provider call occurred. This was not a manufactured APPROVED fixture.

The fix adds an explicit default-false source-read requirement to the original graph invoker and requests it on the outer image-node-result write. The same outer closure now acquires real original read authorization before first origin insertion and retains write/read/current guards through commit. No `local_input=True` override, token bypass, scope expansion, approval shortcut or 403 swallowing was introduced. Other invoker callers retain the original default behavior.

Fixed A+B+C+fix commit: `c479995fb976044782eac200775e3990083f3902`; tree: `0d7b338db6286c11a1994209c4ea9b9a28e060d6`. Clean detached directory: `m3-verification`.

| Separate group | Passed | Pytest seconds | Exit / timeout |
| --- | ---: | ---: | --- |
| New original IMAGE result/restart/authority cases | 28 | 139.64 | 0 / no |
| Original Canvas owner protections | 52 | 22.82 | 0 / no |

Both groups have `complete_pass=true`, unchanged source, clean before/after status and zero external app modules. The 28 cases include first-association 200, exact replay, process restart and alias reads, wrong source/version/digest/incarnation refusals, actual packaged collaboration Host issuance, and original read/write/session revocation both before the request and after change_row before commit. Missing/unknown sessions and wrong branches retain original refusal semantics. Original production transitions and authority guards are not mocked out.

The existing local File mode retains its original trusted-host contract; lack of a local token is not presented as a new per-user authorization guarantee. Token/revocation negative cases use actual packaged collaboration authority.

Raw positive/negative HTTP receipts, deterministic provider calls, logs, JUnit, module sources, source hashes and the genuine pre-fix red tests are in [M3_FROZEN.zip](evidence/M3_FROZEN.zip); [archive hash/size](evidence/M3_FROZEN.json). Mutable source-negative development observations and initial test-fixture setup failures are retained with their original failed/non-acceptance receipts. They are not counted as clean verification passes. Every archived payload hash was verified after ZIP creation.

## Remaining work and boundaries

These stage results do not establish M4 real-browser acceptance or final M6 independent acceptance. Those require the final source freeze and their own evidence. The old stage3 browser script's safe 403 result remains negative evidence only.

Fixed C frontend baseline in this environment: build exit 0; one complete Vitest run exited 1 with 54 failed files, 951 passed files and one skipped file; assertions 329 failed, 13110 passed and six skipped. Its 3752 tracked files stayed identical. Raw baseline is [C_FRONTEND_BASELINE.zip](evidence/C_FRONTEND_BASELINE.zip), with [archive metadata](evidence/C_FRONTEND_BASELINE.json). The full integration comparison is a separate ongoing run; there is no claim of an all-green frontend or no regressions yet. Current baseline causes include missing mock exports, missing source fixtures and Windows `python3` discovery errors, not an unsupported blanket flaky label.

Windows asset-list cursor 503 has been reproduced on the unified c479995f source and remains OPEN. The prior candidate F's 37 unexplained refusals remain OPEN. Audio restore remains deferred/PARTIAL. PostgreSQL, packaged mixed cursors, arbitrary source combinations, real AI quality, GPU, hosted CI, deployment and overall Studio V2 release are not validated by these groups. main readiness remains NOT_READY pending final evidence and explicit unresolved-defect assessment.
