# Studio V2 unified integration — M0 remote checkpoint

Date: 2026-10-27 (Asia/Shanghai)  
Status: **PARTIAL / EXECUTION BLOCKED / NOT_READY**  
Branch: `work/studio-v2-unified-integration-20261027`

This checkpoint is not the requested runnable unified candidate. It preserves the verified remote inputs and the work completed before the execution-environment boundary. No B/C merge, production fix, application test, browser acceptance, or independent frozen-checkout verification has been performed. Historical input reports are not current-run passes.

## Execution boundary and model evidence

The user permits only the current Work cloud environment, GitHub source, and synthetic data. Both exposed general execution surfaces were probed without reading project files:

- Shell: Microsoft Windows 10.0.26100, X64, PowerShell Core 7.6.6, cwd `D:\PoemSeed`; probe exited 0.
- JavaScript execution: win32 10.0.26100, x64, cwd `D:\PoemSeed`, temporary directory `C:\Windows\TEMP`.
- No general cloud terminal/container execution capability was exposed. Cloud Python, Node, browser, PostgreSQL, and application runtimes could not be verified.
- No local old repository, task data, memory archive, media, or project graph was opened. No local checkout was created. No paid provider or GPU work was invoked.
- Three independent review units were launched with explicit `gpt-6-astra` model configuration accepted by the orchestration tool. The service did not expose a separately verifiable served-model ID. The primary session has no model-switch control; a primary-session switch is not claimed.
- The installed GraphFlow skill was read. Its required `graphflow_context` and `graphflow_plan` interfaces are absent from the exposed tools; only `gf_read/gf_exec/gf_edit/gf_macro` are present. No local graph was read as a substitute. No source change was made, so source re-indexing was not applicable.

A pending clarification offers either retaining the cloud-only boundary or explicitly allowing a fresh isolated GitHub clone. No answer or elapsed time has been treated as permission. This checkpoint follows the original cloud-only boundary.

## Frozen remote inputs

All branch refs still match the task's fixed inputs. Full commit/tree and direct connector readbacks are in [M0_REMOTE_EVIDENCE.json](M0_REMOTE_EVIDENCE.json).

| Input | Commit | Tree |
| --- | --- | --- |
| main | `7b35e4cb4bd9efabe7cff54e67d7b24e8e469385` | `36bcb60e21dd5f248365c300f2d1d1ef545f2bc4` |
| A | `457ea4a5a45ab13f351980665e053c5c77d15c82` | `ad5e7ff0db33998026b0016d9adb752e8e82f9c5` |
| G | `d24458225be78f3cbe804b2e325a2f02c3e95568` | `f17fe2b160606c660bca6c0d400c21aff29b30ef` |
| B | `f6473e307e9d0501a41dc46dd991645a437103d7` | `9aad85d79c86030dcea6445551ea7864b0f0f43e` |
| C | `fe4f55412299fadfada0354725b3ca46e418c46a` | `dd0910d4830c7106b3ec5e5a8f2b3529345a285f` |
| audio, deferred | `2acab55d2ef64ca76f2093e376bf6388af364282` | `3f543bdc8543e31003fdf0d5459611ba429ba4a3` |

The new remote branch was absent at initial inspection and was created exactly at A using the GitHub connector. It was independently read back at A before this documentation commit. No existing unified PR was found. Existing PR49 is related engineering/CI work, not this unified integration.

main is an ancestor of A/B/C: ahead counts respectively 263/178/248, behind 0. A and C diverge at `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`, with C ahead 162 and behind 177 relative to A.

### Complete tree differences

An independent review unit compared complete remote recursive Git Trees, all `truncated=false`, with no gitlinks. Counts compare path/blob/type/mode; they do not treat GitHub compare's first 300 files as complete.

| Direction | Added | Deleted | Modified | Mode only | Unchanged |
| --- | ---: | ---: | ---: | ---: | ---: |
| main → A | 4062 | 0 | 187 | 0 | 910 |
| main → B | 3681 | 0 | 187 | 0 | 910 |
| main → C | 2655 | 0 | 181 | 0 | 916 |
| A → C | 441 | 1848 | 148 | 0 | 3163 |

A→C includes app: 26 deleted/47 modified; frontend: 160 added/5 deleted/93 modified; tests: 1 added/90 deleted/8 modified; docs: 26 added/1719 deleted; scripts: 7 deleted; .github: 1 deleted; artifacts: 245 added; logs: 8 added; root: 1 added. These are endpoint differences, not merge instructions. Replacing A with C would discard File, Asset, TaskCenter, admission, and image-node owners.

### G → A source/evidence mapping

A is four documentation descendants after G, through:
`ba00742e2ac86591527e0c3f309e2b6f9823c25c`,
`edd5a0be94429749c911b550f0254d7d99e3a475`,
`91eedc376ccfc7002632793b07f97a221caebbd5`,
then A.

Only the docs root differs. Complete docs-tree comparison confirms 161 added, 5 modified, zero deleted leaf files, all below `docs/delivery/file-backend-safety-integration-20261026/`. app/tests/scripts/frontend trees are byte-identical:

| Root | G and A tree |
| --- | --- |
| app | `d4d7ab0da6f4d0b336dadf7aede239ef151e7c74` |
| tests | `0bf758b8dc455ab910fee905cca41af9918a31f0` |
| scripts | `eea06c594754a1e906e7f584f89e0613fc36a23c` |
| frontend | `0ab4a9c06ece50a0d0d842281a05dec51c9d9277` |

The existing merge `f6ae6c5fb2bda8b875bdbd1f32b5bafd18d9d070` has parents `856d1ed3341fe0c24df1daff9a8bc1242c260e6c` and `31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f`. Those original protections must not be re-ported.

### Missing B increment

B's sole parent is `31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f`; it adds exactly one commit, 95 files: 5 production, 10 tests, 80 documentation/evidence. app tree matches `7e357c95629c255854e4287e02c4c57777097573`.

Production paths are `app/experimental/api.py`, `taskcenter_cursor_http.py`, new `taskcenter_local_mixed_cursor.py`, `taskcenter_query.py`, and `ux.py`. Static review found actual request-local reader receipts, final registry-order checks, original import 200/export 100 windows, and preserved aggregate 403/404 omission behavior. Observer errors are not swallowed by source-error handling.

**B is not yet integrated.** Once a permitted executor exists, apply only B's unique increment with source tracking, then test the combined A+B tree. Separate historical passes do not establish combination compatibility.

## Inputs and owner documents reviewed

- A: `AGENTS.md`, `docs/ui/design_system.md`, `docs/ui/protected_ui_surfaces.md`.
- A: `docs/delivery/file-backend-safety-integration-20261026/{DELIVERY.md,M1_INTEGRATION.md,HERMIA_HANDOFF.md,LIMITS.md}`.
- B: `docs/delivery/taskcenter-local-mixed-cursor-20261026/stable-slice.md`, `independent-evidence/REVIEW.md`, `verification.json`, and selected immutable/raw verification receipts.
- C: `artifacts/unified-workspace-refactor/INDEPENDENT_REVIEW.md`, `frontend/scripts/pw_dci_stage3.mjs`, relevant image client/parser and canvas geometry tests.
- A: `docs/delivery/STUDIO_BACKEND_INTEGRATION_20261026.md` and `HERMIA_AUDIO_HISTORY_REVIEW_20261025.md`; both paths return 404 at C.
- Published manifests: Python >=3.11; C frontend Node >=22.14.0 <25 and pnpm 10.6.5; build `pnpm build`, unit entry `pnpm test`, backend `python -m pytest`. These are source requirements, not installed/runtime verification.

Preserve original Asset, Graph, Production, Review, TaskCenter, Export, identity/scope/grant/lock and UI-shell owners. No visible UI work was performed. The project-specific UI skill would still need to be loaded before future visible UI changes.

## IMAGE 403: static finding, not a reproduced or fixed result

At A:

1. `app/creative/canvas_view_api.py:100–112` takes outer domain.write and inner domain.read guards.
2. `graph_api.py:46–58` classifies source-read necessity from current target state. An initial empty canvas has no image_node_origin.
3. Outer admission at `graph_api.py:102–115` can therefore leave its closed-over source_read_authorized false. The inner guard belongs to a different closure.
4. `canvas_views.py:243–251` writes origin and calls current(). The outer commit guard at `graph_api.py:74–80` now sees origin requiring a source read, while its authorization state remains false.

This supports a specific closure/admission inconsistency hypothesis. It has **not** been reproduced on an A+B+C tree.

A possible original-owner repair to evaluate is an explicit keyword-only requires_source_read parameter, default false, OR-ed with the original source-read classification, passed only by the outer image_node_result operation. It must acquire the real original read authorization and retain current target/source guards at commit. This is a proposed direction, not implemented code. Do not force local_input=True, directly mark authorization successful, ignore token/scope, remove commit checks, or change 403 expectations to obtain success. Preserve ordinary write-only empty-canvas save behavior and existing 403/404 priority.

C already accepts and strictly validates canvas_image_node; the old SDK-rejection statement is obsolete for C. C's own backend has no image-node-result route, so its backend cannot replace A.

C `pw_dci_stage3.mjs:229–240` marks 403/no leak/no success toast as backfill.rejectedSafely PASS. That is negative safety evidence. It is not successful backfill evidence. Add a separate legitimate APPROVED Job/Asset first-association positive test, exact node/job/asset/digest/scope/incarnation/version assertions, replay safety, reopen and backend restart. Keep the existing negative test.

A `tests/test_cloud_formal_canvas_node.py:328–386` anchors wrong-branch, revoked-write and write-without-read denial tests. Its metadata-only fixture forbids execute/review/content and cannot prove a complete generation-positive loop. Add real mounted HTTP positive and commit-window read/write revocation tests, missing/unknown/revoked identity, actor/scope/incarnation changes, provenance/version/CAS changes, and a revert-the-fix negative control.

The historical C review used frontend 7c964d66 and backend 8ea45399, not this unified candidate. Its local_input/no-token observations require fresh real-auth verification. No assertion here promotes them to a safe repair.

Formal IMAGE single-node execution, local graph drafts, and VIDEO unsupported remain distinct capabilities. Two visible canvases do not prove orchestration.

## Historical evidence, known defects, and current-run limits

A selected G receipts record 192/4/23 passes in separate groups; B reports 312/198/10/35 in separate groups. These are historical published results. Groups overlap and must not be added into a unique total. No application tests were run in this checkpoint.

Still OPEN:
- A candidate F's 37 unexplained refusals; later G passes do not explain them.
- Windows asset-list cursor 503; asset-reference query success does not replace list coverage.
- Frontend approximately 292–294 historical failures; no same-environment frozen-baseline comparison was run here.
- Audio restore remains PARTIAL; no restore write route was opened.
- PostgreSQL, packaged, collaboration mixed/exports, arbitrary source combinations, real-model/GPU and full VIDEO execution acceptance remain unverified/unsupported as applicable.

No cloud runtime source hashes, loaded-module paths, new JUnit, browser screenshots, process-restart logs, or test exit codes exist for this run. They are NOT_RUN/BLOCKED, not omitted passes.

## Old PR and branch disposition

Both PR47 and PR48 remain open Draft, mergeable=false/dirty. PR47 targets main; PR48 targets feature/v2-narrative-platform. Their heads are respectively `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3` and `58bbaad11360330d51f49fc2bb78a955a26469f0`. PR API base SHAs are not current target tips.

| Item | Verified content | Disposition |
| --- | --- | --- |
| PR47 runtime sources | 1409 app/frontend-src leaf paths: 1111 same blob as at least one ABC, 298 different, 0 absent at same path | Preserve source/evidence; no wholesale merge or blanket obsolescence judgment |
| PR48 exact inherited paths | 34 of 112 changed paths match at least one ABC | Do not duplicate |
| PR48 renamed receipt helper | taskCostReceipt.ts → taskCostReceiptHelpers.ts, blob 7501c47ddb55c1852719540fb6998b583a9436ac | Renamed inheritance, not missing functionality |
| PR48 differing paths | 61 same paths with different content | Semantic reconciliation still OPEN |
| PR48 absent paths | 17 absent at same path, including the confirmed rename above | Check individually, not all lost features |
| Test-discovery guard | frontend/scripts/check-test-discovery.mjs and frontend/test-runner-manifest.json absent from ABC | Useful missing validation candidate; adapt inventory before restoring |
| Other missing tests | tests/test_v2_audio_mp3.py, test_v2_audio_mp3_api.py, test_public_build_profile.py | Review replacement coverage; do not restore blindly |
| Old save-state/Phase4–6 evidence | Several test/evidence paths missing | Keep provenance, never count as new acceptance |
| Audio history 2acab55d | Explicit PARTIAL | Deferred; not integrated |
| PR49 | CI/PostgreSQL/portability engineering scope | Related, not the unified candidate |

## Hosted CI

Exact A/B/C SHAs each have zero workflow runs. PR47 head has 5 runs/29 jobs and PR48 head has 5 runs/29 jobs: all failure, runner_id=0 and steps empty. Older TaskCenter run 40206566004 likewise has zero executed steps. Examples: [38961150539](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38961150539), [38868809669](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38868809669), [40206566004](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/40206566004).

The annotations endpoint was rejected by the connector URL allowlist, so the precise billing cause was not independently established. These are blocked execution / NOT_RUN tests, never CI PASS. This documentation publication uses [skip ci]; no paid CI capacity was requested.

## Milestones and continuation

| Milestone/result | Current status |
| --- | --- |
| M0 remote input/evidence inspection | PARTIAL: remote checks done; cloud runtime unavailable |
| M1 A+B integration and combination tests | BLOCKED / NOT_RUN |
| M2 C integration/conflict reconciliation | BLOCKED / NOT_RUN |
| M3 403 reproduction/repair | BLOCKED; static hypothesis only |
| M4 true frontend + File + HTTP + browser + Mock loop/restart | BLOCKED / NOT_RUN |
| M5 combined regressions and baseline comparison | BLOCKED / NOT_RUN |
| M6 clean frozen independent checkout and negative control | BLOCKED / NOT_RUN |
| M7 | PARTIAL: remote M0 checkpoint only, no tested integration candidate |
| Unified code integration | BLOCKED |
| IMAGE browser backfill/restart | BLOCKED |
| File protections + mixed cursor combination | BLOCKED |
| Frontend build/regression | NOT_RUN |
| main merge readiness | NOT_READY |
| Studio V2 overall release | NOT_COMPLETE |

Continue from the source freeze A. Apply B only once, then perform a real three-way integration of C while retaining A's backend owners. Record actual conflicts and semantic decisions at that time; there is no conflict-resolution log yet because no merge was attempted. Reproduce 403 before the explicit-read repair, run the original-authority positive and negative cases, then the same-checkout browser/restart loop and combined regressions. Freeze a new source commit only after validation and verify in a separate clean checkout.

The remote checkpoint adds only this directory's documentation. Its parent is A; publication HEAD/tree are recorded in the Draft PR and final delivery response. It is not a tested M6 freeze. Resume at that checkpoint or create a later ordinary commit from it. If the checkpoint must be undone, revert its documentation commit with a new commit; never reset or force-push shared history. No original branch/PR was deleted, no main merge, release, or deployment was performed.
