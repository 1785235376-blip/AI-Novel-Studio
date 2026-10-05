# R4/R5/UX bounded engineering delivery

## Identity and baseline

- Repository: [1785235376-blip/AI-Novel-Studio](https://github.com/1785235376-blip/AI-Novel-Studio)
- Branch: `work/post-v1-r4-r5-ux`; [Draft PR39](https://github.com/1785235376-blip/AI-Novel-Studio/pull/39), base `work/post-v1-feature-forward-r3`.
- Start/parent: released R3 `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b`, tree `19180ad00035b9eda2baf0795ea947ea943b7e1f`.
- Frozen V1 PR37 remains `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0`. No backport, merge, release or deployment.
- Verified engineering source: `bf0ec2b09ef03187536f0e9a677142e3e915aa44`, tree `b54040210916fc5a76bc94b79d7ab923d2647cfe`. The subsequent final commit changes only delivery documents/evidence; its exact remote SHA and exact-head CI are recorded in PR39, avoiding a self-referential commit hash.
- Actual engineering model: gpt-6-astra. [Official commit index](COMMIT_INDEX.md).

## Actual scope and status

[The forty-package matrix](FEATURE_MATRIX.md) records F00, A01–A13, B01–B10 and U01–U16 separately, including actual implemented capability, reuse/dependencies, UI/API entry points and remaining scope. Every applicable package has a real bounded author workflow. Native/model/adapter boundaries stay PARTIAL rather than becoming forty “fully complete” checkmarks.

The engineering loops cover original writing/recovery/resume/search/tasks, reviewed source/privacy-aware requests, original Draft/Diff/Accept, graph/knowledge/budget/lineage/revision, manual production/read/export workflows, isolated no-key onboarding, and local reviewed collaboration/fork/sync. They are usable deterministic workflows, not a substitute for the unconfigured real-model portions. **Engineering loop tested; real model effect awaits acceptance.** Unregistered model families/adapters and unsupported branch manuscript sources remain unavailable and cannot complete those real tasks merely because a diagnostic or contract exists.

Default-OFF exact flags, dependency checks, V1 server-force-OFF, isolated future data, original source/version/actor/branch/permission/privacy/final-dispatch checks and human approval remain. Templates/workflows are untrusted data; executable plugin policy remains DENY_ALL.

## Layered verification at the exact engineering source

[PR CI 37372638988](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37372638988) finished **SUCCESS across all five lanes**, attempt 4. The merge checkout tree was independently verified equal to the head tree.

| Layer | Actual result | Boundary |
|---|---|---|
| Frontend unit/types/build/tokens | 981 passed, 6 optional HTTP skipped; types/build/token guard passed | Large App chunk warning retained: 634.90 kB; deferred workbench 477.48 kB |
| File backend | 3,409 passed, 1,044 expected skips, 301.73 s | The skipped PG-only/platform cases are not File passes |
| Real two-process TCP sync | 1 passed, 13.24 s | Actual separate local processes, not TestClient/mock transport; no cloud deployment |
| Real PostgreSQL 16 | 3,411 passed, 1,042 expected skips, 633.69 s | Zero skipped marked-PG contract; zero failures/errors; 1,009 explicit PG parameter cases all executed |
| Hosted Chromium | 35 R4 + 2 business + 9 geometry + 7 R3 + 1 immutable-export = 54 passed, none skipped | Synthetic data; mock model output explicitly labelled |
| Native Windows build/package lanes | Both successful | Compile/contracts/unsigned internal package smoke, not interactive user acceptance |

Queued jobs that did not execute and the interrupted PG attempt remain historical failures. The PG runner shutdown at 63% produced no complete test receipt; only the later successful retry establishes PG acceptance. No assertion was removed, no golden changed, and no skipped or cancelled lane was counted as passed.

## Observed defects repaired

- Inherited File project delete/lazy-read ghost resurrection: reproduced independently, repaired with shared lifecycle coordination and separate backport-candidate evidence. Frozen branches untouched.
- Current-authority recovery, future-origin feature gating and acceptance/terminal settlement defects reported before the review block: implemented fixes with retained regressions. These fixes do not close independent review.
- Broker reservation/cancellation versus final dispatch: exact bound state-transition repair; stale unrelated transitions remain rejected.
- Actual frontend regressions: accessible request/source and task-region names; fresh original project/source fixtures; workspace chrome occupying the editor row; sidebar-toggle interception of Save/export controls. Real content, history, pointer-hit and downloaded-output assertions now pass.

[Corrected original screenshots and receipts](evidence/browser-bf0ec2b0/README.md) show visible prose, intact recovery buttons and the unchanged shell at 1280/1366/1440/1920. Five unedited PNGs were directly inspected. [Historical failures](EDITOR_CHROME_REPAIR.md) remain documented. The current visual handoff is the original root [OPUS_UI_HANDOFF.md](../../../OPUS_UI_HANDOFF.md), not a duplicate.

U13 100k/500k/1m Han: 30-sample input-render proxy p95 **26.3/36.8/48.0 ms**; warm browser-to-File-search p95 **66.5/200.2/373.9 ms**. Raw source/method/host data are retained. These are not physical keyboard/display or native Windows IME measurements.

## Unaccepted boundaries and next checkpoint

The second-slice independent follow-up review is **BLOCKED** by the recorded platform response. It was not retried, rephrased or routed through another reviewer/tool. Implementation tests and this engineering report are not an independent all-clear. [Exact status](SECOND_SLICE_REVIEW_STATUS.md).

Native interactive Windows/WebView2/IME/screenreader/multi-monitor, real GPU/text/image/TTS/translation quality, target NLE/EPUB-reader/RenPy acceptance, automatic cloud transport, unregistered model adapters and branch-specific manuscript writers remain NOT_RUN/unavailable as specified in [KNOWN_LIMITATIONS](KNOWN_LIMITATIONS.md). No paid provider, private credential or real manuscript was used.

The immediate delivery checkpoint is exact CI on the documentation/evidence successor. The next acceptance work is a supported independent-review route and explicitly authorized real native/model/target-app environments. This delivery does not authorize deployment or automatic local runtime edits.

## Separate recommendations

[NEXT_UX_PRIORITIES.md](NEXT_UX_PRIORITIES.md) distinguishes unfinished acceptance gates, useful improvements to existing features, and genuinely new candidates. Prioritize incremental search, precise source provenance and budgeted variant reservations, reviewed asset/portable-project maintenance, and real branch adapters. New candidates are opt-in local usability measurements, target-application publication rehearsal and an author-controlled comparison notebook. These are recommendations only, not an additional open-ended implementation wave.
