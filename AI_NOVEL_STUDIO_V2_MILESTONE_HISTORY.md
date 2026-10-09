# V2 Milestone History

Ledger initialized: 2026-10-09 UTC from the supplied V2 Master Roadmap/start instructions and actual repository/evidence inspection. This is the **new M0→M12 staged program**, extending the existing Foundation. It does not retroactively rename earlier work as completed milestones.

## 1. Identity and recording rules

- Repository: `1785235376-blip/AI-Novel-Studio`.
- Only development branch: `feature/v2-narrative-platform`.
- [PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) remains Draft. No merge, tag, Release, production deployment or user-Windows execution is authorized by this ledger.
- Observed local HEAD for this review: `4350a61fb9f61acccb845fef96b24b9b1275bbd3`. There are concurrent, uncommitted M1 source changes; HEAD alone does not identify that working tree.
- Baseline source tree: `a05d33f75c5af6f26171d6370c0efeb13a68619d`; historical PR merge checkout: `e0c7a4657ffbc3119a3b98384bcee5ebf0c5eea1`, same tree.
- Existing [V1 freeze](V1_SCOPE_FREEZE.md), RC1 assets, source manifests, stable IDs, privacy/scope/CAS and original owner contracts remain protected. New stage evidence must not overwrite their historical identities.

Use `EXISTS / PARTIAL / MISSING / BLOCKED / LOCAL_REQUIRED` for feature inventory. Use `PASS / PARTIAL / FAIL / BLOCKED / NOT_RUN / LOCAL_REQUIRED` for execution results, with separate milestone state and execution level. `IN_PROGRESS` and `PENDING` below are scheduling states, not extra test outcomes. A plan, authored test, route label, schema or source hash is not a product PASS.

Every completed stage must append its start/end commits and tree hashes, changed owners/paths, feature matrix delta, commands and exit codes, exact test counts, skipped-test justification, environment/runtime/backend, source stability, screenshots/visual review, CI event/run/attempt, known gaps and next step. A stage commit may land before hosted execution completes, but its CI then remains pending. Preserve failed attempts alongside subsequent fixes. Never combine push/PR or different source identities into one successful run.

## 2. Immutable historical conclusions

The older post-Interop conclusion remains **39 PARTIAL + F00 INTEGRATED**, and the historical independent review remains **BLOCKED**. This staged development does not reopen, complete or replace that review. Sources: [post-Interop matrix](POST_INTEROP_FEATURE_MATRIX.md), [R4/R5 continuation](POST_INTEROP_R4_R5_CONTINUATION_REPORT.md), [Shared R123 evidence explanation](docs/delivery/shared-r123-repair/README.md), and [V2 Foundation report](AI_NOVEL_STUDIO_V2_FINAL_DEVELOPMENT_REPORT.md).

Shared R123 success means its evidence workflow ran successfully, including the intended historical RED reproduction; it is not a new independent product-review approval.

## 3. Foundation history before the new roadmap

| Identity / evidence | Actual result | Preserved limit |
| --- | --- | --- |
| Earlier Foundation changes and lifecycle fixes; [evidence index](docs/delivery/v2-development/cloud-v2-evidence-index.md) | Existing creative documents, provenance/review/CAS, Local AI environment metadata, optional director model path and five-mode workspace developed and tested in recorded snapshots. | These are bounded Foundation capabilities, not all independent Studios or M0–M12 completion. |
| `fe4d250`; [terminal receipt](docs/delivery/v2-development/ci-fe4d250-terminal.json) | Earlier failed/cancelled CI and lifecycle/browser defects retained. | Later green checks do not erase this run or make its NOT_REACHED steps pass. |
| `99e3c63`; [terminal receipt](docs/delivery/v2-development/ci-99e3c63-terminal.json) | Five workflows: 3 success / 2 failure. V2 live 5 passed / 2 failed per event; mocked 5/5. PR File pytest completed but TCP step hit the original cap; aggregates rejected. | Real screenshots and logs preserve reopen/empty-draft and timeline-layering defects. |
| Subsequent source fixes; [UI recovery receipt](docs/delivery/v2-development/creative-recovery-99e3c63-20261009.json), [TCP budget record](docs/delivery/v2-development/ci-tcp-budget-20261009/README.md) | Local frontend 1,567 passed / 8 existing skips; infrastructure 276 passed; original TCP 2 passed. Source inventory and unchanged original test ordering recorded separately. | Local proofs have their own source fingerprints; they are not hosted results by implication. |
| `4350a61fb9f61acccb845fef96b24b9b1275bbd3`; runs below | Final Foundation hosted result **PARTIAL_CI_CAPACITY**. | PR full success and push capacity cancellation coexist. No automatic release eligibility. |

### 3.1 Exact `4350a61` hosted terminal state

Observation cutoff: **2026-10-09 09:47:44 UTC**. All original workflows reached natural terminal at **attempt 1**, with no monitor rerun/cancellation or relaxed time limits. Totals: **4 success / 1 cancelled workflows; 23 success / 2 cancelled / 2 failure jobs**.

| Event / run | Terminal result | Scope |
| --- | --- | --- |
| [PR Cloud 37907528214](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528214) | **SUCCESS** | File, both PostgreSQL shards, independent TCP, both strict aggregates, frontend, V2 browser and bounded Windows jobs. |
| [Push Cloud 37907521986](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907521986) | **CANCELLED** | File and PostgreSQL shard 0 reached existing 20/55-minute caps; both aggregate preconditions failed closed. |
| [PR Local Interop 37907528323](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528323) | **SUCCESS** | Original File/PostgreSQL contracts and Windows `MOCK_ONLY` pipe reference. |
| [Push Local Interop 37907522007](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907522007) | **SUCCESS** | Separate push event and receipts; not joined to PR evidence. |
| [Shared R123 37907528200](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528200) | **SUCCESS** | Historical RED reproduction evidence workflow, not independent review clearance. |

PR's complete profiles each collected **9,449 nodes**: File **6,190 passed / 3,259 approved skips**; PostgreSQL two deterministic shards **6,159 passed / 3,290 approved skips**. Independent real loopback TCP **2 passed**. Both PR aggregates validated same-run/attempt checkout/tree/dependencies/source identity and immutable evidence copies with the original reconciler. Counts across profiles, duplicated aggregates and independent TCP are not summed as unique product tests. Two PG shards are not claimed to equal a monolithic single-process interaction order.

Push File partial progress was **6,100 passed / 3,229 skipped**, 1 setup-only and 119 unstarted; push PG shard 0 was **3,040 passed / 1,588 skipped**, 1 setup-only and 83 unstarted of 4,712 assigned nodes. Neither produced complete terminal JUnit. Push PG shard 1 and TCP succeeded, but aggregate join/reconciliation were **NOT_REACHED** because execution preconditions failed. The cause recorded is capacity/time-limit cancellation; a specific underlying performance root cause was not proven.

Each event's frontend recorded **1,567 passed / 8 existing opt-in skips**, build/type/token and original browser groups passed. Each V2 suite recorded **7 live passed (3 HTTP + 4 UI), 8 mocked passed**, no failures/skips/retries. These tests do not establish infinite canvas, full NLE, real inference, or all new roadmap requirements.

Each Interop event/profile recorded **345 passed / 68 approved skips, 413 nodes**. Hosted Windows checks covered **59 native/packaging contracts + 3 V2 environment fixtures**, fresh unsigned internal packaging and embedded Python **3.12.9** / PostgreSQL **16.15** UTF-8/dump-restore smoke. Interactive user desktop, GPU/model and two real production applications remain outside that evidence.

Historical preservation record: frozen manifest SHA256 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`; V2 source manifest SHA256 `df72d854d942b0759b9d02229c33523bb1dd11470dd95c5c12a405a73c9a66ab`, **1,661 source inputs**. Original **9,151-node** ordering, skip maps and external gates were preserved. The known launcher expectation migration in commit `1b7ff50a7e64742916bc64730df884cea819b379` only adds `-B` before `-I` in `tests/test_windows_portable_entry.py`; it is not an independent historical audit approval.

The terminal summary was read and its full SHA256 verified as `c6b3ff60195fcb559e99b4c405bc6083854b82b8b3e316dae13471ea53b5332b`. Public run URLs above are the reproducible CI entry points. Private diagnostic paths, machine inventories and artifact archives are not copied into this document. The existing committed Foundation report remains a timestamped pre-final snapshot; this ledger adds the terminal facts without rewriting it.

## 4. New staged program at this snapshot

The entire 904-line roadmap and 28-line start instructions were read from the current supplied taskpack. The current authorized work is real cloud engineering through successive safe stages, not a new request for every small step. M1–M3 shared owners integrate serially; later independent owners may proceed in bounded parallel only after their prerequisites are stable.

| Stage | State / inventory | Existing owner or foothold | Gate still required |
| --- | --- | --- | --- |
| **M0** audit/freeze/baseline | **Inventory complete; documentation publication pending** | 325 source-bound rows, actual owner map, migration/rollback, exact CI ledger and 16 protected hashes. | Record the documentation commit and its separate hosted state; source inspection is not a rerun of all tests. |
| **M1** intent/storage/assets | **IN_PROGRESS / PARTIAL** | Original Project owner, `AssetLibraryService`, creative scope/incarnation and production lineage; new neutral adapters under active integration. | Blank project → external image → independent version/provenance → save/reopen → export with no chapter/model; File/PG/auth/CAS/UI proof. Full storage migration/cache cleanup remains separately scoped. |
| **M2** shared typed graph/canvas | **PENDING / PARTIAL footholds** | Existing planning/declarative/workflow and Job owners; no claim their schemas equal the new generic engine. | Shared typed ports, graph persistence, safe local execution/cache, normal/pro views, optional Director and disconnected Tutor placeholder. |
| **M3** local models/onboarding/API | **PENDING / PARTIAL** | Existing HardwareInventory, LocalDiscovery, Model Center, RuntimeRegistry/identities, Broker/Vault. | Safe reuse and component validation, trusted non-default discovery, no-model onboarding, conditional install/API consent and exact adapter execution evidence. |
| **M4** Text/Screenplay/Agents | **PENDING / PARTIAL** | V1 chapter/version/context/Agent owners and creative screenplay/director proposals. | Independent text entry plus real adaptation proposals and actual format export; model quality remains local-required when no approved runtime exists. |
| **M5** Image Studio | **PENDING / PARTIAL** | Existing image/media providers and assets. | Shared canvas, actual compatible T2I/I2I/edit path, mask/version workflow and independent encoded exports; unsupported capabilities stay blocked. |
| **M6** Director/Storyboard | **PENDING / PARTIAL** | Creative scene/shot/director documents and review. | Independent media/idea starting points, optional multi-target Director node and professional shot views/reference versioning. |
| **M7** Video/Previs/API | **PENDING / PARTIAL contracts** | Existing media adapters/jobs/video planning. | Real capability-specific T2V/I2V/V2V route; separate image/video/3D reference contracts, authentic status/output and consent. |
| **M8** Audio Studio | **PENDING / PARTIAL** | Existing audio providers/production/voice/subtitle owners. | Independent import/listen/trim/export, supported TTS, waveform/timing and rights-aware voice profiles. |
| **M9** real multitrack NLE | **PENDING; required interactive NLE MISSING** | Planning timeline and timeline-exchange contracts are reusable, not NLE completion. | External media, ≥2 video + ≥2 audio + subtitle tracks, real edit/preview/render, media validation and reopen equivalence. |
| **M10** 3D/Research/Delivery/Tutor | **PENDING / PARTIAL footholds** | Existing research, export/package and Local Interop owners. | Supported independent 3D reference inspection, source/license delivery, dockable Tutor and permission-controlled Studio-side interoperability. |
| **M11** cross-module/regression/RC | **PENDING** | Current regression infrastructure and Foundation evidence. | Five independent journeys plus optional chains, performance/recovery and exact candidate-source full applicable gates. Historical capacity remains visible. |
| **M12** user Windows acceptance | **PENDING / LOCAL_REQUIRED**, authorization **USER_APPROVAL_REQUIRED** | Candidate packaging and native fixtures. | User explicitly opens the stage, then real installation/GPU/model/IME/DPI/windows/two-app checks. No execution is authorized now. |

Refer to the stage-specific [architecture](AI_NOVEL_STUDIO_V2_ARCHITECTURE.md), [UI review](AI_NOVEL_STUDIO_V2_UI_UX_REVIEW.md), [model integration](AI_NOVEL_STUDIO_V2_LOCAL_MODEL_INTEGRATION.md) and [Windows plan](AI_NOVEL_STUDIO_V2_WINDOWS_ACCEPTANCE_PLAN.md). The separately maintained feature matrix must retain sub-capability evidence rather than treating this scheduling table as a complete inventory.

### 4.1 M1 integration record, not a completion receipt

- Start HEAD: `4350a61fb9f61acccb845fef96b24b9b1275bbd3`.
- End SHA/tree: **UNCOMMITTED / UNKNOWN**, to be filled only after the actual stage commit.
- Scope: neutral project activation/preferences and bounded manual assets, using original project/asset/lineage owners; independent no-model image path is the first acceptance target.
- Observed in-progress paths: `app/creative/workspace.py`, `workspace_models.py`, `workspace_api.py`, `app/services/asset_library_service.py`, `app/creative/project_store.py`, `app/experimental/production_lineage.py`, frontend Studio client/entry integration and the narrowly approved AppShell noun.
- Protected UI change: [recorded approval](docs/ui/design_system_change_request_v2_project_label.md); default novel text preserved, neutral noun explicitly selected. No blanket shell redesign or baseline refresh.
- Focused cloud File/API check at 12:03 UTC: **FAIL**, 95 passed / 105 opposite-profile skips / 10 failed / 2 teardown errors. The failures found omitted exact collaboration-route admission and a new fixture attempting to mutate frozen Settings. Both were corrected without changing original test assertions.
- Corrected focused File/API check at 12:05 UTC: **PASS**, 107 passed / 107 opposite-profile skips. Genuine PostgreSQL **17.11** focused check at 12:06 UTC: **PASS**, 109 passed / 109 opposite-profile skips, with real owner UUID/JSONB/SQL identity checks. The PostgreSQL snapshot also adds missing-incarnation corruption cases. These are separately fingerprinted uncommitted worktree results, not tests of this docs-only M0 commit; their original logs/receipts will accompany the M1 code commit. Both recorded unchanged source hashes during execution. They are not full-product or all-M1 acceptance.
- Current-source frontend/browser/visual results: **NOT_RUN**. Authored UI tests are not counted as executed cases.
- Current-source hosted CI: **NOT_RUN**; no successor commit/run is asserted here.
- Native Windows, GPU, real models and paid API: **NOT_RUN / LOCAL_REQUIRED**; M12 requires separate user approval.
- Next update: append actual stage report and commit/test/CI identities after implementation and verification. Do not replace `4350a61` historical outcomes with the new results.

## 5. Conditions for moving to the next stage

1. Confirm the current-source minimal path and its negative tests; preserve required default-off/V1 behavior and original data owners.
2. Record unresolved scope as PARTIAL or blocked with exact reason, not a future-tense claim of completion. A model/hardware block need not stop unrelated manual capability development.
3. Commit only authorized V2 work; push only the existing development branch and update Draft PR truthfully. New hosted runs remain separate from local evidence and prior failures.
4. Continue the next safe dependency-bound task. No automatic Windows execution, fee, destructive migration, permission expansion or release follows from reaching a milestone.

## 6. Appended M1 checkpoint — 2026-10-09 13:00 UTC

Sections 1–5 remain their earlier time-bound ledger. **M1 remains PARTIAL**; this
records a useful as-built slice, not a full-stage completion or release receipt.
The [M1 report](MILESTONE_M1_REPORT.md) contains the complete requirement delta,
original commands/logs, source maps, failed attempts and outstanding gates.

| Identity / scope | Recorded state |
| --- | --- |
| Original engineering start | `4350a61fb9f61acccb845fef96b24b9b1275bbd3` |
| M0 documentation baseline | `0df2640c4c1a2d3052bb0a84d14445744d04046f`, tree `f800c0e8a6d920e8836a027707c8078c5a8421f2` |
| M1 implementation end SHA/tree | **UNCOMMITTED / UNKNOWN** at this checkpoint; forthcoming exact PR47 publication receipt required |
| As-built minimum slice | Neutral original-owner project entry, nonbinding preferences, independent manual image/video/audio assets, original ID/version/provenance/export, typed read-only Chapter/Screenplay bridge, descriptive relationships, bounded import storage admission and shared-shell consumer |
| Full M1 blockers | Applied presets; configurable paths/export destination; full occupancy/cache limits/preview-confirm cleanup; verified reference/copy migration with interruption recovery; running-job low-space pause/resume; actual browser/visual and published-source CI evidence |

### 6.1 Subsequent local evidence, without erasing earlier attempts

- [Original-owner File regression](docs/delivery/v2-development/stage-m1-owner-regression-file.json): **PASS**, 1,047 passed / 954 skipped, 232.85 s; includes 3 browser-job infrastructure guard tests.
- [Original-owner PG regression](docs/delivery/v2-development/stage-m1-owner-regression-postgres.json): **PASS**, 1,011 passed / 987 skipped, 678.29 s, actual PostgreSQL 17.11. Matching own-run log ends in normal shutdown at 12:58:21 UTC. These are selected regressions, not complete backend execution.
- [API catalog check](docs/delivery/v2-development/stage-m1-api-catalog.json): **PASS**, 3 tests. [Generation receipt](docs/delivery/v2-development/catalog-25061dfa7a78.json) hashes match all four catalog outputs; 2,077 operations, M1-only **+34 / −0** relative to M0. Its staged tree is not the final published commit.
- Director fast-receipt reproduction retains **RED: 1 failed / 2 passed**, then **GREEN: 45 passed**. It demonstrates and fixes a controlled unit-level defect; the blocked historical browser trace's exact cause remains unestablished.
- First final frontend: **PASS**, 1,773 passed / 8 existing skips. First final build: **FAIL**, two invalid options in the new Director test; TypeScript stopped before build/token execution. Both receipts remain intact.
- [Corrected final build](docs/delivery/v2-development/stage-m1-final-build-corrected.json): **PASS**, TypeScript/Vite/43-file token guard, existing chunk warning retained. [Corrected full frontend](docs/delivery/v2-development/stage-m1-final-frontend-corrected.json): **PASS**, 1,773 passed / 8 existing skips. Each finished with unchanged source; corrected source maps agree and differ from owner regression only in that new test file.
- [Independent collection review](docs/delivery/v2-development/stage-m1-collection-review.json): **INVENTORY_ONLY**, no tests executed; 9,809 collected, original 9,151 preserved in order, 658 additions relative to the frozen baseline and historical skips unchanged. It does not reopen historical independent review.
- Actual new image/video browser import/reopen/export, relationship browser acceptance, screenshot/geometry review and current M1 hosted CI are **pending / NOT_RUN** at this cutoff. Service roundtrips and jsdom do not replace them.

### 6.2 Separate M0 hosted checkpoint and next safe work

[Persisted observation, 12:49:12 UTC](docs/delivery/v2-development/m0-ci-checkpoint-1249.json):
M0 PR Cloud **37928446079** has File/frontend cancellations, browser/TCP/native
successes, PG shard 1 success and shard 0 pending; M0 push Cloud **37928438685**
has File/frontend/TCP/native successes, live-browser failure and both PG shards
pending. Push V2 live is **6 passed / 1 failed**, geometry **8 passed**. The first
failure archive records **403 TRACE_ACCESS_BLOCKED**; no trace inspected, no
rerun and no timeout change. This is an incomplete M0 observation, not M1 CI.

Safe, nondependent M2/M3 work may proceed from this documented bounded checkpoint.
The minimum independent path still needs its actual browser receipt; missing
storage/preset semantics remain explicit blockers for dependent operations rather
than deferred-complete requirements. Keep original Project/Asset/Job/Model owners,
optional connections and no-model manual use. Historical **PARTIAL_CI_CAPACITY**,
**39 PARTIAL + F00 INTEGRATED**, independent review **BLOCKED**, and M12
**USER_APPROVAL_REQUIRED / LOCAL_REQUIRED / NOT_RUN** remain unchanged. No end SHA,
all-green CI, Windows-user acceptance, merge or release is invented by this ledger.

## 7. Final M1 metadata-guard checkpoint

After the 13:00 snapshot, V2's original-owner adapter gained a strict positive
integer revision guard; legacy asset metadata semantics are unchanged. The
seven-value File corruption reproduction is retained as **FAIL: 7 failed / 7
opposite-profile skipped / 150 deselected**. Final focused File and real PG 17.11
each have **215 passed / 186 opposite-profile skipped**, stable source maps and
matching normal PostgreSQL shutdown. Exact commands and source/log evidence are
in [M1 report §11](MILESTONE_M1_REPORT.md#11-final-metadata-guard-delta-and-bounded-m1-closure).

The larger owner regressions and frontend/build in §6 remain successful at their
own **pre-final-guard snapshots**; they are not current-tree full regression.
[Final catalog regeneration](docs/delivery/v2-development/catalog-80d041f1ef1c.json)
retains **2,077 operations, M1 +34/−0**, with backend fingerprint
`a06abe220e300bad702981085001c7bd0259ba6d81a519bb3f855c1f8db56292`.
Final API catalog check is **3 passed**; coverage infrastructure **174 passed**.
[Actual final inventory](docs/delivery/v2-development/stage-m1-version-guard-collection-written.json)
is **9,823 nodes**, **14 new** since 9,809, with original 9,151 ordered nodes and
historical skips preserved; `tests_executed:false`. Written manifest hash is
`3e86bfabbdcb2c494968cf89d6efdd3ff2cc10edf921fa47f6a9669474dfce9f`.
Earlier inventory/CI checkpoints remain historical.

M1 is **PARTIAL / bounded minimum-path closure**. Local browser **BLOCKED**;
hosted current-M1 browser **NOT_RUN**; actual screenshot/geometry review remains
unverified. Storage migration, general cache cleanup, global reservation/job
pause and applied preset gaps persist and block dependent operations. Safe
nondependent M2/M3 may continue. Baseline stays `0df2640c4c1a2d3052bb0a84d14445744d04046f`;
final published M1 SHA/tree is not yet recorded. Historical review classifications
and M12 **USER_APPROVAL_REQUIRED / LOCAL_REQUIRED / NOT_RUN** remain unchanged.

### 7.1 M0 terminal record, distinct from current M1

[Observed 13:17 UTC](docs/delivery/v2-development/m0-ci-terminal.json), all attempt 1:
PR Cloud **37928446079 CANCELLED**, with File/frontend cancellations and both
strict backend aggregates failed despite successful PG shard execution; push
Cloud **37928438685 FAILURE**, with failed V2 browser and successful File/PG
execution plus aggregates. PR Interop **37928446071**, push Interop **37928438655**
and Shared R123 **37928446211** are **SUCCESS**, with their original fixture/RED
boundaries. No rerun, timeout change or silent replacement of failures occurred.
The M0 trace is still **403 TRACE_ACCESS_BLOCKED**, uninspected.

Local browser carries the preserved prior Chromium `process_singleton_posix.cc:297`
socket permission denial and `SIGABRT`; no new M1 local browser attempt occurred.
Current M1 hosted execution remains **NOT_RUN** until an actual published revision
and event-bound receipt exist. This ledger grants no Windows execution or release.

The [13:21 aggregate excerpts](docs/delivery/v2-development/m0-ci-aggregate-log-excerpts.json)
record cancelled execution/successful TCP inputs in both PR fail-closed
aggregates. Push same-run joins reconcile **9,449 nodes per profile**:
File **6,190 passed / 3,259 skips**, PG **6,159 passed / 3,290 skips**, original
TCP **2 passed**. These remain M0-only counts, not final M1 execution; the excerpts
are not complete downloaded artifacts or proof of monolithic PG equivalence.
