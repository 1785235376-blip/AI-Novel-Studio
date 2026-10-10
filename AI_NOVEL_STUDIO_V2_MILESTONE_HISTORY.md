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

## 8. M2-A development checkpoint — 2026-10-09 13:50 UTC

M1 checkpoint publication is now the baseline
`57986cb13d452731baf82bbc242bfc79f9cfd145`, tree
`7b06f7eb213893ec41e4ded14810b82b070b7dc7`; M1 remains **PARTIAL**. M2-A is
**IN_PROGRESS / PARTIAL**, with end SHA/tree **UNCOMMITTED / NOT RECORDED**.
Earlier ledger sections retain their time-bound source/publication statements.

Implemented slice: actor-private typed graph definitions over original scope
persistence; empty independent graph/CAS; original WorkflowRun local text/manual
execution, optional Director note, exact review and same-version reviewed-ancestor
cache; initial real node canvas/inspector/run consumer. Bounds are 16 nodes/40
edges, 96,000/64,000 decimal bytes, 25 graphs/100 runs/20 history. Original
3,600-second deadline begins at admission without queued-execute reset; node
budget 5 seconds. No new provider, JobManager or model execution is present.

External graph references are metadata rather than original lineage/dependency
edges: original soft-delete/restore remains authoritative; stale/unavailable
projection, saved binding restrictions and blocked atomic input execution are
explicit. No graph-wide strong deletion guard, generated-asset lineage or Asset
Save publication is claimed. Full canvas, multimodal adapters, M1 storage/preset
semantics and the full M2 image-generation/material-conversion gate remain open.

[M2 report](MILESTONE_M2_REPORT.md) preserves separate development receipts:
213 contract passes; wrong-interpreter failure before pytest; corrected File
21 passed/21 deselected; 241 passed/28 deselected **with recorded source drift**;
latest deadline File **257 passed/44 PG deselected**; earlier mounted API **16
passed/16 skips**, before later auth cases. These are not final integrated totals.
Actual PG, full frontend/build, browser/visual and current-M2 hosted checks remain
pending. No authored test or schema is counted as executed product acceptance.

### 8.1 Published M1 hosted failures carried into the correction

[Detailed correction record](docs/delivery/v2-development/M1_CI_MEDIA_COMPATIBILITY_FIX.md):
push **37936615942** and PR **37936623135**, attempt 1, each have the protected
V2-job invariant failure (**101 passed/1 failed**); actual TCP execution was not
reached. Both browser jobs also retain **8 live failures/4 passes**, geometry
**8 passes**; first relationship timeout is unproven, then closed-context cleanup
left a synthetic project and later empty-server guards failed. No failure is erased.

The approved repair restores the old 7-case live job/config unchanged and adds
an explicit new media job for 5 independent cases; graph cases are additional.
Inventory migration is collection-only. The separate source-stable additive-media
contract selection has **121 passed**, not hosted/browser success. Artifact
**11618169199** is **403 TRACE_ACCESS_BLOCKED**, bytes unavailable, no alternate
route or trace inspection. Cloud terminal metadata is still pending at this
checkpoint; Interop/Shared success does not repair these failures. M12 remains
**USER_APPROVAL_REQUIRED / LOCAL_REQUIRED / NOT_RUN**.

### 8.2 Terminal local checks appended at 13:55 UTC

Full frontend **1,923 passed / 8 existing skips**, TypeScript/Vite/token **PASS**,
and complete infrastructure/catalog **279 passed** now have terminal, agreeing
source-stable receipts. That 279 includes all 276 infrastructure tests, including
the original 102 TCP harness, plus 3 catalog tests. Mounted API File **20/20**
belongs to its earlier source. Catalog now has **2,107 operations, M2 +30/−0**.
Collection review records **10,178 nodes**, original 9,151 order/skips preserved,
**INVENTORY_ONLY**. Written manifest and integrated File/real-PG completion are
still pending. Exact evidence is appended in [M2 report](MILESTONE_M2_REPORT.md);
no final M2 SHA, hosted/browser PASS or full-stage completion is asserted.

### 8.3 Integrated File update, 13:59 UTC

[Original-owner File](docs/delivery/v2-development/stage-m2-integrated-owner-file.json)
finished **PASS: 1,490 passed / 1,098 skipped**, 299.01 seconds. It selects 33
original-owner/M1/M2/media-contract files; it is not the full backend manifest.
The stable 1,660-input map matches frontend/build/279-check evidence. Real PG
remains pending; no profile combination, browser PASS or full M2 completion is
inferred. Exact log/source binding is in [M2 report](MILESTONE_M2_REPORT.md).

### 8.4 Written inventory update, 14:01 UTC

[Manifest review](docs/delivery/v2-development/stage-m2-manifest-change-review.json)
and [independent recollection/write](docs/delivery/v2-development/stage-m2-manifest-written.json)
verify **10,178 nodes = M1 9,823 + 355**, preserved old order/skips/external gates,
and actual manifest SHA256
`acefe60873bd452ff663b254cb4c25a910c99dcb140732171105b7ba0b687d62`.
The frozen manifest remains unchanged. [Actual browser collection](docs/delivery/v2-development/m2-browser-inventory-review.json)
retains all prior 12 cases: **7 original + 8 independent (5 M1 + 3 M2)**, no overlap.
Both are **inventory only**; no browser launched or full backend execution inferred.
Real PG completion remains pending at this observation.

### 8.5 Final local M2-A checkpoint, 14:07 UTC

[Actual PG receipt](docs/delivery/v2-development/stage-m2-integrated-owner-postgres.json)
finished **1,457 passed / 1,131 skipped**, 830.19 s, real 17.11 and matching normal
shutdown. It shares the stable 1,660-input map with File **1,490/1,098**, frontend
**1,923/8**, build/token and **279** infrastructure/catalog checks. All selected
local checks are terminal; earlier PG-pending entries remain time-bound history.
Catalog 2,107 (+30/−0), written 10,178-node inventory and 7+8 browser collection
retain their separate execution levels. Full M2 stays **PARTIAL**.

M1 hosted PG jobs are still pending alongside known TCP/browser nonpasses; exact
terminal history will be a separate receipt. M2 hosted/browser remains **NOT_RUN**,
local browser blocked, no visual approval. The actual end SHA will be bound in
PR47 after publication, not invented inside its own commit. Full graph/model/media,
canvas/Tutor and inherited storage gaps remain; M12 still requires user approval.

## 9. Published M2-A and M3-A development checkpoint — 2026-10-09 14:44 UTC

Published parent is now HEAD `99c43b6892038233c390be2ae61acb669163d0b5`, tree
`69d69ffe71838263069d164a0a07b39b5f4a4333`, on Draft PR 47. Earlier M2 end-SHA and
hosted-pending statements remain the historical observations at their stated times.
M2 stays PARTIAL; publication does not close its full graph/media/storage gates.

Push run **37943398984** and PR run **37943412489** are separate events. Original
V2 workflow/geometry and TCP jobs were observed passing in both; independent-media
jobs each finished **6 PASS / 2 FAIL**. The saved PR media log records merge SHA
`7f0d911549b04e8dbb7cf078316ad74c42095449` with the same tree, rather than the push
commit. Exact-label failures at `关联目标` / `已保存创作图` are retained in both raw
logs. A narrow nine-attribute production label correction has new unit RED
**3 FAIL / 1 PASS**, then **4 PASS** and **47 PASS** nearby; hosted revalidation is
pending. No old browser selector, timeout or golden was weakened. Local browser
remains blocked and denied artifact routes were not retried. These findings and
verified log hashes are recorded in [M3 report §6](MILESTONE_M3_REPORT.md#6-separate-m2-hosted-finding-and-correction-under-development).

Current M3-A implements host-private discovery authorization plus V2 bounded
preview/consent through existing owners. Entire production discovery, including
cached reads with V2 off, now requires actual current Host authority. This
intentional compatibility/security tightening does not change the shared Model
Center collaboration helper. Scope discloses configured/registered GGUF and
executable metadata and existing stale-registration safety persistence; consent
is not inference or a pure-observation guarantee. Existing scanner/cancel/deadline
and separate Register/Enable/dispatch lifecycle remain authoritative.

Development history is retained: host-cache reproduction **4 FAIL** → correction
**23 PASS**; initial scope **27 PASS**; legacy cancellation **1 FAIL / 158 PASS** →
legacy/scope **186 PASS**; host-authority matrix **296 PASS**; mounted onboarding
**14 PASS**; mutation guards **223 PASS**; service hardening **209 PASS**; mounted
precommit **23 PASS**; newest service concurrency/replay **215 PASS**. Logs/hashes
were checked against their receipts. Source maps were stable within each run but
differed between runs (1,662–1,671 inputs), with overlapping selections; no aggregate
or final-source pass is asserted.

M3 source is not frozen; end SHA/tree remain UNCOMMITTED / NOT RECORDED. Final
integrated File/real-PG/full frontend/build/catalog/manifest and hosted/browser
proof are pending. Full M3 model-component validation/profiles/real inference,
complete install guidance and optional API consent/budget remain PARTIAL. Actual
user Windows/GPU stays LOCAL_REQUIRED / NOT_RUN; M12 still requires authorization.

### 9.1 Planning hardening checkpoint, 14:55 UTC

M3 preview/confirmation planning adds a fixed **5-second cooperative budget**,
per-operation authority/deadline checks and at-most-50-ms existing-owner lock waits.
`planning_budget_seconds` / `LOCAL_AI_SCOPE_BUDGET_REACHED` expose this admission
bound; scan 45 seconds and receipt TTL 120 seconds remain unchanged. No new preview
or scan admission follows revoked/over-budget planning. OS calls already in flight
are not forcibly interrupted.

The **14:51:47–14:51:59** [planning receipt](docs/delivery/v2-development/m3-scope-planning-dev-01.json)
finished **224 PASS** (65 new scope + 159 existing selected cases), with the raw
log hash verified. It records **source drift, 1,673 → 1,674 inputs**, solely the
concurrent addition of `tests/test_v2_discovery_browser_fixture.py`; service-owned
files stayed stable. This is retained as development evidence, not final-source
PASS. Source freeze still awaits the original HTTP/File/UI, original-session,
synthetic-discovery-only hosted acceptance input. No browser execution, real model,
paid API or user Windows result is implied. Full M3 remains PARTIAL.

### 9.2 Frozen-source terminal-check update, 15:05 UTC

Source froze at 15:01 UTC with **1,676 inputs**, canonical map SHA256
`aefdbfd9884879ab2e17b42754c8ae7cbb6ecd54de4b8e192c9b158e6fe22259`.
Verified stable agreeing receipts now establish frontend **1,981 PASS / 8 existing
skips**, TypeScript/Vite/45-file token **PASS**, infrastructure/catalog **279 PASS**
and corrected current-discovery catalog-owner regression **3 PASS**. Generation
from staged tree `8cbb5bc7af09e7d40165312e64b13c0175d5792a` yields **2,111
operations (+4/−0)** and app source fingerprint
`6a6bfbc80bf2ee2f5d6f536f6d038cf43ec25c92ec357b5aee768a04dbfa83e7`.
The stale shared-helper annotation is corrected narrowly; other owner metadata
and the actual shared Model Center authorization contract are preserved.

Independent recollection and manifest write are now terminal at **10,335 nodes =
10,178 + 157**, preserving every old published node/order/test/gate/skip contract.
Written manifest SHA is
`498c3059954528fc4db2676b3aedce8bed6fff3b758f55f45bb943bebaebe36a`;
this remains INVENTORY_ONLY. Actual browser listing preserves **7 original + 11
independent** cases and adds three synthetic-discovery M3 cases; no browser was
launched. [M3 report §9](MILESTONE_M3_REPORT.md#9-source-freeze-and-terminal-local-checks--2026-10-09-1505-utc)
retains exact receipt/log hashes and large-chunk warnings. Selected 52-file File
and actual PostgreSQL 17.11 integration are still running. Published M3 identity,
hosted/browser revalidation and full M3/user-Windows/model gates remain pending.

### 9.3 Integrated File result, 15:08 UTC

At 15:07:32 UTC, the [52-file selected owner File integration](docs/delivery/v2-development/stage-m3-integrated-owner-file.json)
finished **2,082 PASS / 1,099 skips / 1 warning**, 310.49 s. Its stable 1,676-input
map matches the frozen frontend/build/catalog receipts, and raw log SHA256 is
`a36f7980a53bafc66b1067c5b9359c24bba2c4268183f936c67d95c26bc253d0`.
Skips retain 1,098 opposite-profile cases and the existing real Windows-native
acceptance case. This does not execute the full 10,335-node manifest, browser or
Windows/model acceptance. Actual PostgreSQL remains running; full M3 stays PARTIAL.

### 9.4 Published-M2 terminal record and first M3 PG failure, 15:20 UTC

[M2 terminal manifest](docs/delivery/v2-development/m2-ci-terminal.json), SHA256
`f69554807ecf8e43b291eaa42ae81ef902baf807a85cbabfa7dd6e93cbee325a`,
records all five workflows naturally terminal, without rerun/cancellation by the
agent. All 29 saved logs were hash/byte-verified. Both Cloud events FAIL: File jobs
cancelled at the 20-minute budget with no complete test count; all four PG execution
shards succeeded but both strict aggregates failed their prerequisite. Per event,
frontend is 1,923 unit PASS / 8 skips, **104 browser PASS + 2 separate real-client
PASS**; original V2 is 7 live + 8 geometry PASS, independent media 6 PASS / 2 FAIL,
TCP 2 original + 102 harness PASS. Windows package/contracts and MOCK_ONLY Local
Interop passes retain their stated scope. Shared R123 workflow success reproduces
three historical RED defects on `c6f2126`, not current-head acceptance. M2 remains
PARTIAL; exact push/merge identities and counts are in [M3 report §10](MILESTONE_M3_REPORT.md#10-terminal-published-m2-hosted-record--2026-10-09-1520-utc).

The first M3 real-PG 52-file integration finished at 15:15:57 UTC **FAIL: 2 failed /
2,047 passed / 1,132 skipped**, 811.97 s. Two unchanged original workflow API tests
failed at missing create-response `id`; source maps remain stable at 1,676 inputs.
Verified raw log SHA is
`c754654a4221918105b75c1b23a56c748749ebc0569d20487ad01690e74eb0cf`.
PG 17.11 SQL is verified; normal stop and diagnosis remain pending. A brief
evidence-upload transport interruption recovered on the same executor without
restarting this original test run or moving the branch. The failure is retained,
not converted to PASS by the successful File/UI checks. Full M3 remains PARTIAL.

### 9.5 Confirmed PG harness isolation issue, 15:24 UTC

The two first-PG failures are now traced to reused test data: SQL shows both
fixed-title rows created at 14:04:35 UTC during M2; the unchanged original API
correctly returns 409. The first diagnostic's unused-import failure is retained,
and the corrected diagnostic proves the conflict. Normal original-run shutdown
is verified at 15:15:57 UTC. [M3 report §11.1](MILESTONE_M3_REPORT.md#111-confirmed-reused-database-cause-and-normal-shutdown-1524-utc)
records hashes and exact evidence. A narrow runner-only fresh-database mode and
new isolation tests are being prepared, preserving existing data and original
assertions/titles. New source freeze and complete selected checks are required;
the first failed run and prior 1,676-input results remain historical, not rewritten.

### 9.6 Fresh-source File and local-check checkpoint, 15:42 UTC

After the runner-only fresh-database correction, current receipts bind **1,677
inputs**, map SHA256
`964ad4a0c317f43d65e2aa8793d6f87b5e6630b977ee269803c42c6248fd143f`.
The **complete selected 53-file File owner range** is **2,109 PASS / 1,099 skips**,
317.00 s; it is not all **10,362** product nodes. Freshly rerun frontend is
**1,981 PASS / 8 existing skips**, build/45-file token PASS, infrastructure/catalog
**279 PASS** and browser collection **7 original + 11 independent, inventory only**.
All these maps and logs were verified, rather than borrowing initial-source runs.

Fresh smoke reruns the original two failed tests unchanged: **2 PASS**, with
actual PG 17.11 database OID 31259, empty-before-migration proof, all 20 original
SQL files, normal stop and retained data. Runner/helper regressions are **32 PASS**;
the first integration failure remains preserved. New written inventory is
**10,362 = 10,335 + 27**, SHA256
`bc15318b92cae0ee7a3c581321de95f3577c684b0ced26daf9f7228ccda57715`,
with old tests/gates/order/skips intact. Catalog stays **2,111 operations (+4/−0)**
and application source is unchanged. Exact fresh receipt/source/log hashes are in
[M3 report §12](MILESTONE_M3_REPORT.md#12-fresh-database-correction-and-current-source-checks--1542-utc).
The complete fresh PG owner run is still pending. M3 stays PARTIAL; full-product
hosted CI awaits publication, and browser/user-Windows/inference proof is separate.

### 9.7 Final local M3-A checkpoint, 15:47 UTC

The fresh real PostgreSQL 17.11 run is now **PASS: 2,076 passed / 1,132 skipped**,
831.24 s, with the same stable **1,677-input** map as File **2,109/1,099**, full
frontend **1,981/8**, passing build/45-file token and **279** infrastructure/catalog
checks. Actual fresh DB OID **32129**, empty-before-migration proof, all 20 original
SQL hashes, retained data and normal shutdown at 15:45:46 UTC were verified.
[M3 report §13](MILESTONE_M3_REPORT.md#13-final-local-m3-a-checkpoint--1547-utc)
contains exact current receipts/log hashes and publication identity rules.

This completes the **selected 53-file owner range**, not full-product execution
of all **10,362** manifest nodes. Catalog 2,111 (+4/−0), written manifest and 7+11
browser collection retain their separate inventory level. Earlier failed attempts,
including the diagnosed reused-database run and M2 hosted failures, remain intact.
M3-A is a publishable **PARTIAL** checkpoint. Exact end SHA/tree will be bound via
PR 47's publication receipt, not self-embedded or replaced with the M2 parent.
New-SHA full-product hosted CI and M3 browser/visual results remain pending; actual
user Windows, real inference/quality and full M3 model/API gates remain open.

## 10. M3-B file-observation continuation — 2026-10-09

Published M3-A HEAD `9851bdd2d692df983664bc8f4597fbc05c0e2ceb`, tree
`cd6989a19e5fd5e2400f2325fe696cae03d8eda7`, is the parent of the new metadata
reuse slice. [M3-B report](MILESTONE_M3B_REPORT.md) preserves its own source maps,
first fixture/UI/full-frontend failures and subsequent verification receipts.
Its publication SHA/tree will be recorded through PR 47 rather than self-embedded.
All earlier milestone conclusions remain historical, including M2 hosted failure.
M3-B browser evidence must come from its own published source; M3-A's 11-case
independent hosted result cannot cover the new twelfth case. Full M3 stays PARTIAL.

The first 1,682-input attempt finished File 2,125/1,099 and real PG 2,092/1,132,
while full frontend failed one existing Agent selection race. The separate
[1,688-input correction checkpoint](MILESTONE_M3B_REPORT.md#12-corrected-source-freeze-and-terminal-frontend-checks--1634-utc)
retains that history and verifies new full frontend 2,040/8, build/49-file token,
279 infrastructure and 7+14 browser inventory. Corrected backend outcomes are
recorded only when terminal in the main report.

At **16:46 UTC**, [final local M3-B](MILESTONE_M3B_REPORT.md#12-corrected-source-freeze-and-terminal-frontend-checks--1634-utc)
records the complete selected 56-file File **2,127 PASS / 1,099 skips** and fresh
real PG **2,094 PASS / 1,132 skips**, with the same stable 1,688-input map and
normal PG stop. Written inventory is 10,380, not full-product execution. Older
[M3-A hosted CI](MILESTONE_M3B_REPORT.md#6-terminal-published-m3-a-hosted-record-separate-from-m3-b)
is terminal full-Cloud FAIL: File cancellation blocks mandatory joins despite
all four passing PG shards. New M3-B hosted/browser acceptance remains pending.

## 11. M3-C workflow-prerequisite continuation — 2026-10-09

Parent is published M3-B `c386b0608ae92d18c351b5cb6e367380808a45cf`, tree
`2ec6365e1f1f183f029c9f0a94d040d134e22b47`. [M3-C report](MILESTONE_M3C_REPORT.md)
contains current source-bound execution results and retained failures. Its
publication SHA/tree will be bound by PR 47 after commit. Full M3 remains PARTIAL.

The replacement cloud workspace recovered all 1,688 published source digests,
restored locked dependencies and verified a fresh real PostgreSQL 17.11 lifecycle.
M3-B terminal CI is preserved separately: both Cloud events FAIL, File incomplete,
strict joins NOT_REACHED after failed execution prerequisites, independent media
11 PASS / 3 FAIL; push frontend later groups incomplete while PR completed them.
Two additive M3-B journey assumptions were corrected with deterministic mounted
regressions, without altering product UI, original M3-A tests or time/skip policy.

M3-C reads existing scan node/loader advertisements and separate unknown catalogue
component requirements. It does not complete installed-component compatibility,
inference, install/API workflows or user Windows acceptance. No merge/release.

Current-source frontend is 2,110 PASS / 8 existing skips; type/build and 52-file
token guard pass. Final File owner selection is 2,216 PASS / 1,099 existing
profile skips. The latest recovery completes the same selected real-PG range:
2,183 PASS / 1,132 existing profile skips, 1056.58 seconds, unchanged
1,696-input source map. Its new empty database, all 20 original migrations,
normal shutdown and retained data are verified. Both earlier session-lost attempts
remain INCOMPLETE with no final counts or proven normal shutdown; their separate
databases, runtime receipts and logs are preserved. See the
[recovery verification](docs/delivery/v2-development/stage-m3c-owner-recovery-verification.json).
These selected checks are not full-product hosted CI or browser acceptance.
The separately generated 10,469-node V2 inventory retains all 10,380 prior nodes
and adds 89; original frozen manifests and strict CI gates are unchanged.

## 12. M4 AI Execution Layer — 2026-10-10

The user's current six-module AI Execution Layer instruction supersedes the
older M4 Text/Screenplay/Agents label for this milestone. Published M3-C
`0bf79fb2d3b8be3ff7c3034371c4bc7642500d44` is the verified parent.
[M4 report](MILESTONE_M4_REPORT.md) and [execution contract](docs/v2/ai-execution.md)
record the bounded schema-2 local-text node, original ModelBroker/WorkflowRun/
JobManager/TextModelNode composition, actionable explicit API/UI journey and
proposal-only review. Model Center and Creative Core remain the original owners.

The APIProvider interface is reserved and nonexecuting. No paid API, automatic
runtime installation/start, cloud fallback, large Image/Video feature or real
model benchmark is included. Mock/contract and real-thread results are not real
inference quality. Final source-bound checks and exact publication identity are
recorded only when available in the M4 report and PR 47.

M3-C's push Cloud passed complete strict joins, while its PR Cloud hit the
original File capacity cap and both joins rejected incomplete prerequisites.
That inherited **PARTIAL_PR_CI_CAPACITY**, full-M3 PARTIAL, earlier failed receipts
and historical independent-audit **BLOCKED** remain unchanged. This round's code
checks are engineering verification, not a replacement independent audit.

The final bounded M4 checkpoint source `4bdd2488…44d4` has a complete 13-file
M4/adjacent-owner File result of 485 pass / 368 existing skips and fresh real-PG
result of 484 pass / 369 existing skips, normal shutdown. Full frontend is
2,164 pass / 8 existing skips; build/token and 279 infrastructure checks pass.
Earlier 79-file results and failures retain their own source identity and are
not promoted to final-tree aggregate acceptance. Browser collection is inventory
only; actual hosted CI is pending the new publication SHA. Full M4 is PARTIAL.
