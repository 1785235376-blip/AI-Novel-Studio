# Milestone M0 — current V2 inventory and frozen baseline

## Result

**M0 engineering inventory: complete for the audited 4350a61 source, pending its
own documentation commit. Overall V2: incomplete. CI: PARTIAL_CI_CAPACITY.**

This stage identifies original owners, maps the supplied blueprint, fixes the
evidence baseline and defines the safe next implementation seam. It does not
reopen the old independent review or claim a new product/runtime test pass.
Historical **39 PARTIAL + F00 INTEGRATED**, independent review **BLOCKED**, remain.

M1 implementation is proceeding separately. Its minimum image loop is not claimed
complete here; full Storage Manager, typed relationships, video entry, Graph and
later Studios remain broader milestones even if that first loop later passes.

## 1. Source and requirement identity

| Item | Verified identity / boundary |
|---|---|
| Repository | `1785235376-blip/AI-Novel-Studio` |
| Only development branch | `feature/v2-narrative-platform` |
| M0 starting/audited HEAD | `4350a61fb9f61acccb845fef96b24b9b1275bbd3` |
| Audited source tree | `a05d33f75c5af6f26171d6370c0efeb13a68619d` |
| PR | [47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47), open, Draft, unmerged; read at 2026-10-09 11:44 UTC |
| PR test merge | `e0c7a4657ffbc3119a3b98384bcee5ebf0c5eea1`; same tree as audited branch HEAD |
| PR base at audit | `fed2404c8e30b44061b7139dced45b7f3301601c` |
| Remote preflight | Parent integration task fetched/checked the remote at 11:38 UTC; direct PR read and local `git rev-parse HEAD` independently agree |
| Requirement source 1 | `AI_NOVEL_STUDIO_V2_MASTER_ROADMAP(1).txt`, supplied 2026-10-09; fully read 904 lines, 71,777 bytes, no unread remainder |
| Requirement source 2 | `DOT_V2_START_INSTRUCTIONS(1).txt`, supplied 2026-10-09; fully read 28 lines, 2,945 bytes, no unread remainder |
| Execution environment | Existing dot cloud Linux repository; no user Windows access, GPU/model execution or personal paid API |
| M0 end/commit identity | To be recorded by the integrating parent when the three-document milestone is committed; no invented end SHA |

The supplied SHA is an observation point, not permission to reset future work.
The workspace was clean at the initial audit. Later M1 source/UI/test edits are
concurrent next-stage work and are not included in this M0 source verdict.

Read inputs included `AGENTS.md`, current README and V2 development report,
repository UI skill/design system/protected surfaces, V1 freeze, old matrix and
rollback records, Local Interop protocol/security/Desktop mapping, actual owner
source, representative existing tests, the final PR body and terminal CI record.
No parent-local attachment copy was assumed; both authoritative attachments were
read directly. No external model catalog claim substitutes for repository code.

## 2. Deliverables and coverage

M0 owns only these new root documents:

1. [AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md](AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md):
   325 capability/gate rows, requirement §§1–29 plus appendix boundaries,
   26 linked original-owner/evidence groups.
2. [AI_NOVEL_STUDIO_V2_ARCHITECTURE.md](AI_NOVEL_STUDIO_V2_ARCHITECTURE.md):
   actual write owners, permitted adapters, distinct graph semantics, M1
   cross-entry fencing, storage limitations, migration/rollback.
3. This milestone report: exact-source CI/freeze ledger, static verification and
   next-stage acceptance requirements.

The integrating M0 documentation commit also includes the four required
companion documents (UI/UX review, local model integration, milestone history,
and Windows acceptance plan), plus the approved narrow Design System request
and its changelog entry. These describe later work and its observed checkpoints;
they do not include or claim verification of the concurrent M1 implementation.

| Matrix classification | Rows | Interpretation |
|---|---:|---|
| EXISTS | 47 | Bounded source implementation or exact current audit artifact exists |
| PARTIAL | 196 | Original implementation reusable, broader requirement incomplete |
| MISSING | 60 | Requested contract/surface absent at audited owner seam |
| BLOCKED | 7 | Explicit unavailable authority / later high-risk scope |
| LOCAL_REQUIRED | 15 | Actual target-machine/native/model/two-product acceptance |

These counts are **not percentages of product completion** and are not test
counts. Multiple rows intentionally reference one owner. A test filename only
locates verification source; it does not establish full coverage of that row.
Appendix future expansions are tracked as a separate deferred boundary, not
silently added to the current V2 acceptance denominator.

## 3. Decisions that change the implementation plan

### Project / Asset / Storage

- Project remains `RepositoryBundle.novels` and existing File/PostgreSQL/collab
  lifecycle. A neutral adapter may call it without creating a chapter; exposing
  the legacy storage name does not justify forcing a Novel user journey.
- `CreativeProjectStore` is an incarnation-fenced view, not a project registry.
  File owns a removable UUID marker; PostgreSQL uses the current novel UUID.
- `AssetLibraryService` is the binary, metadata-version and parent-DAG owner.
  `ProductionLineageService` already supports an `EXTERNAL_IMPORT` declaration
  with no chapter source. Do not create another mutable asset index/version/DAG.
- New V2 assets need owner-level server-owned incarnation/origin constraints.
  New-route filtering alone leaves old downloads/exports/trash/derivatives able
  to bypass the intended boundary. Legacy unbound assets retain their historical
  behavior; new views must not silently adopt them after slug reuse.
- Preserve lock ordering. Existing lineage guards run while holding the asset
  lock; current Creative scope transactions use scope → owner. The proposed M1
  asset → owner lease must not call ExperimentalStore, media/change-impact reads
  or another scope transaction while held. Lightweight lineage projections are
  acceptable only when all such transitive reads are excluded and tested.
- `WindowsPackagingPaths` already separates installation/runtime/cache/durable
  user roots. `PortableProjectsService.storage/cleanup` already measures scoped
  categories and confirms only verified reproducible export-cache cleanup.
  A complete quota/free-space/migration manager does not yet exist.

### Graph / Job / Models / Interop

- Extend `V1CapabilityService`'s workflow host. DeclarativeAgents already reuses it
  through `_ScopedOriginalWorkflowHost`; a new graph must not introduce another
  scheduler. `app/workflow.py` is a disabled legacy synthetic fixture, and
  VisualTextWorkflow is read-only.
- Asset provenance graph, executable Creative Workflow Graph and World/Research
  Knowledge Graph retain separate semantics. A reference is not a rights grant.
- Existing task center projects original author/media/workflow owners. Reusing
  JobManager does not mean all current modality jobs already share one queue.
- ImageInfiniteCanvas is a reference board. ProductionTimeline/VideoTimeline are
  planning surfaces. Neither proves typed graph execution or a real multi-track
  NLE. Existing FFmpeg assembly is bounded video-only review output.
- Extend ModelCenter/Discovery/HardwareInventory/Runtime/Broker/Vault. Discovery,
  registration, enablement, inference and quality are distinct observations.
- PoemSeed Local Interop `1.0` and stable product IDs remain authoritative.
  QingJian remains optional Observer/Advisor/Tutor; a future slot adds no control,
  memory-write, paid-execution or automatic outbound permission.

## 4. Exact 4350a61 hosted CI ledger

The current PR body was read directly and agrees with the existing terminal
summary. Five original attempt-1 workflows naturally reached terminal state:
**4 SUCCESS / 1 CANCELLED**. Across them: **23 successful jobs, 2 cancelled,
2 failed**. No M0 rerun, cancellation, timeout change or GitHub mutation occurred.

| Workflow / event | Result | Exact evidence |
|---|---|---|
| Cloud CI / pull_request | SUCCESS | [37907528214](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528214) |
| Local Interop V1 / pull_request | SUCCESS | [37907528323](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528323) |
| Shared R123 / pull_request | SUCCESS | [37907528200](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528200) |
| Cloud CI / push | CANCELLED | [37907521986](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907521986) |
| Local Interop V1 / push | SUCCESS | [37907522007](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907522007) |

### PR complete proof, not a substitute for push

Actual PR checkout/event was `e0c7a4657ffbc3119a3b98384bcee5ebf0c5eea1` with the
same audited tree. Both strict aggregate gates accepted exact same-event/run/
attempt backend and original TCP receipts.

| Profile | Collected | Passed | Exact allowed skips | Boundary |
|---|---:|---:|---:|---|
| File, original single-process order | 9,449 | 6,190 | 3,259 | Complete strict gate |
| Real PostgreSQL, original two shards | 9,449 | 6,159 | 3,290 | Complete strict gate; not monolithic PG interaction equivalence |

Original TCP: 2 passed. Profiles/overlapping suites are not summed as unique
product cases. [File proof](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528214/artifacts/11606498200)
and [PostgreSQL proof](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528214/artifacts/11606314045)
remain distinct receipts.

### Push incomplete proof retained

| Producer | Terminal / limit | Actual partial observations |
|---|---|---|
| [File 113744478179](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907521986/job/113744478179) | CANCELLED, original 20-minute cap | 6,100 phase-complete passes, 3,229 skips, 1 setup-only node, 119 unstarted; complete=false, no terminal backend.xml |
| [PostgreSQL shard 0 113744478577](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907521986/job/113744478577) | CANCELLED, original 55-minute cap | 3,040 phase-complete passes, 1,588 skips, 1 setup-only, 83 assigned unstarted; complete=false, no terminal backend.xml |
| PostgreSQL shard 1 | SUCCESS | 3,059 passed / 1,678 skips across 4,737 assigned; other 4,712 nodes are original shard deselection |
| Original TCP | SUCCESS | 2 original tests; does not compensate for unfinished backend producers |
| Both aggregate gates | FAILURE, fail closed | Execution precondition rejected cancelled producers; TCP join and coverage reconciliation NOT_REACHED |

Existing diagnosis: File setup about 83 s versus PR 75 s; 9,288 matching nodes
had the same pass/skip pattern, with push slower in 119 of 128 comparable windows
(median ratio 1.296). PostgreSQL shard 0 spent about 603 s installing media tools
and 2,629 s in pytest. This is capacity evidence, not proof of a newly introduced
functional regression or of a guaranteed fix within the unchanged caps.

### Other bounded successes

- Each event's original frontend: 1,567 passed / 8 existing opt-in skips; all
  original browser groups reached successful terminal results.
- Each event's V2 browser: live 7/7, mocked 8/8; no failures/skips/retries. These
  cover current creative planning/reopen/hit-test behavior, not future graph/NLE.
- Each Interop event: File and real PostgreSQL each 345 passed / 68 exact skips,
  with strict reconciliation and Windows pipe evidence.
- Four hosted Windows jobs succeeded in their bounded scope: original 59
  native/packaging cases plus 3 V2 fixtures per event, embedded Python 3.12.9,
  PostgreSQL 16.15, pgcrypto, UTF-8, dump/restore and packaged-import smoke.
- These hosted Windows results are **not** user Windows installation, real GPU,
  model quality, desktop IME/high-DPI, or two-product final acceptance.

The older committed [development report](AI_NOVEL_STUDIO_V2_FINAL_DEVELOPMENT_REPORT.md)
is explicitly an earlier timestamped snapshot. The final PR body and terminal
ledger supplement it; this audit does not rewrite old failed/cancelled evidence.

### Terminal evidence identity

- Existing local summary: `.runtime/github-4350a61-monitor/terminal-summary.json`.
  SHA256 `c6b3ff60195fcb559e99b4c405bc6083854b82b8b3e316dae13471ea53b5332b`,
  independently recomputed in this audit.
- Existing evidence archive: 4,502,164 bytes, 102 members, 27 job logs;
  SHA256 `53b26cb5454b408ecd954d774f363175ada7c2ab7c644f833c51ce872e8a01ff`.
  Archive identity is taken from the terminal ledger, not newly reexecuted tests.
- Existing preservation record: 9,151 original nodes retained in order; 9,449
  current nodes; 1,661 source inputs; original skip maps/external gates unchanged.
- Source preservation is not execution. Receipt IDs, events, attempts and actual
  checkout SHA remain separate. Neither this documentation nor a future rerun
  can relabel the cancelled push as complete.

## 5. Frozen and protected baseline

The original V1 acceptance remains tied to Draft PR 37 and commit
`1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0`; this is distinct from the current V2
audit HEAD. Existing RC1 packages, their source identity, user data and historical
release evidence are not regenerated or modified by M0.

The following hashes were computed from **4350a61 Git blobs** and compared with
the current files at 12:03 UTC; all listed files were byte-identical. This is a
precise sampled protected-file check, not a claim to have independently rerun
every historical 763-file preservation assertion or inspected user data.

| Path | 4350a61 SHA256 |
|---|---|
| `.github/ci/coverage_manifest.json.gz` | `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262` |
| `V1_SCOPE_FREEZE.md` | `6a9ebd169158490e055a37c8e7a59386a6e57f963baa1140988c7ae7e574c50e` |
| `POST_INTEROP_FEATURE_MATRIX.md` | `e040a905ee531203dd8834a2b9926865debba8d1f2be6ef23f5b003eb51aa9c4` |
| `POST_INTEROP_R4_R5_CONTINUATION_REPORT.md` | `19b59b9ed5bfe9918cbc759ce5fcb5469a38dc7fbc722505956513c280b55cd0` |
| `LOCAL_INTEROP_PROTOCOL_V1.md` | `3e8eab0163d1fce0d16818c9b93c1e1c8cb84fdc365ff1dfca722ecdc9257a4b` |
| `LOCAL_INTEROP_SECURITY.md` | `8de1e9198685e2a238cacffa1d5b363f96fff4b88ad419cd4315ed89a810b8e2` |
| `docs/ui/design_system.md` | `99f9579e83ef37cc0546debf3f1f39ba70f19bf8482573b9efac40647dfc635d` |
| `docs/ui/protected_ui_surfaces.md` | `f18731a7d58dc65e66836abca6e8d40b04aeb25ae475f3a83a74b6f248c1099b` |
| `.github/ci/postgres_gate.py` | `d18ee804595ab98f8aec4c25745a7961e65a36755e318c8f4f257663b4358a8c` |
| `.github/ci/suite_coverage.py` | `570892af0975c125868710e250eb7f30cc5e51ba7cbef9429a3b0f8f10238da7` |
| `.github/ci/coverage_reconcile.py` | `f097904d51cc21cb6f1ce8dcc688f692cf89bdd473f3952605eba3b1ae02e66a` |
| `tests/test_r5_offline_sync_tcp.py` | `46cbe9c0b7cc2a6c0d7a57d0d1a970c8732466fb061480eae8f2209f48ae890e` |
| `tests/test_windows_portable_entry.py` | `9f0d2d5f78a44e54a0fcc00925dc6d67038060408d3bd44753461ca57152fe1f` |
| `docs/delivery/functional-surface-freeze/SOURCE_PRESERVATION.json` | `07b2eb295d93aa4d7130473080aa0c576b9e2eac75d3756f36ef113928cb0502` |
| `release/version.json` | `1fde3763efd2feaa03bff73ba0d7a6db7bd5eee3da42fbf59c0f34770e1105ed` |
| `packaging/windows-runtime-inputs.json` | `7a6717c3508dbf0bef5853ab4cdfcaa2c8f0f14fe75fbc6507190ff722206e58` |

The V2 extension manifest at the audit HEAD has SHA256
`df72d854d942b0759b9d02229c33523bb1dd11470dd95c5c12a405a73c9a66ab`.
It is an additive current-source manifest, not permission to edit the original
frozen manifest. Future additions need explicit source-bound extension evidence.
The baseline's `tests/test_windows_portable_entry.py` already contains the
recorded `-B` before `-I` launcher expectation migration from `1b7ff50`; its
historical frozen hash was
`d100e27589fb45cb921c13a82a83a911485fef1c0ed82a1e50eb5efc94f24799`.
That existing exception is not a new M0 edit or historical audit approval.

The complete protected path/exception ledger remains
[SOURCE_PRESERVATION.json](docs/delivery/functional-surface-freeze/SOURCE_PRESERVATION.json),
with its historical starting/current identities. This report does not collapse
those identities into the M0 SHA. Stable Interop contract source, old migration
history, release inputs and V1 acceptance mode must remain valid after M1.

## 6. Actual M0 checks and non-execution

| Check | Command / method | Outcome and execution level |
|---|---|---|
| Local source identity | `git rev-parse HEAD`, `git status --short` | Audited 4350a61; initially clean; later M1 work explicitly excluded |
| Remote identity / PR state | Read current PR 47 metadata/body | Same HEAD/tree observation; Draft/open/unmerged |
| Authoritative requirements | Direct full content read; no unread remainder | 904 + 28 lines reviewed |
| Owner inventory | Source reads, symbol inspection, representative test-source reads | Static evidence only; no new product PASS |
| Matrix coverage/count | Read the written matrix and count unique capability rows/status values | 325 rows, five permitted status classes |
| Local document links | Resolve relative Markdown link targets for the three owned documents | PASS: no missing target; see §9 |
| Protected sample bytes | SHA256 of `git show 4350a61:<path>` compared to file bytes | All 16 listed baseline files unchanged at recorded observation |
| Terminal summary digest | SHA256 of preserved JSON | Matches final PR body |
| New backend / PostgreSQL / frontend / browser / Windows tests | Not invoked by M0 inventory worker | **NOT_RUN in M0**; prior source-bound CI is §4, not new execution |
| Model/API/GPU or user Windows | Not invoked | **NOT_RUN / LOCAL_REQUIRED**, paid API outside current authority |

No source, test, workflow, source catalog, manifest, old report, package or user
data was changed by this M0 inventory work. Only the three listed new documents
were written. The integrating task owns serialized stage commits and any
authorized follow-on runtime implementation.

## 7. Testable next-stage failure list

| Failure / risk | Required M1/M2 regression; current status |
|---|---|
| Same public slug after delete/recreate | New V2 assets remain unavailable through new and original APIs; current binary binding gap **MISSING at M0** |
| Legacy branch `None` wildcard | New bound assets require exact branch including None; no accidental cross-branch adoption |
| Flag disable / V1 acceptance mode | Hide all new origin-bound bytes/metadata/derivations even via legacy endpoints; preserve records |
| Forged client provenance / incarnation / version | Reject; server captures current owner and measured digest/version |
| Concurrent create/import/retry | Idempotent exact request; different request conflicts; orphan cleanup only for owned unsuccessful import |
| Revoke/delete during import/export | Recheck before commit/response; no late private-content leak or silent success |
| Asset→owner versus scope→owner deadlock | Two-client/process File and real PG tests; no nested scope read in asset lease |
| Corrupt image, fake MIME, oversized payload, changed bytes | Bounded decode/validation and exact digest failure; no filename-only success |
| Stale dependency, trash/restore, missing source | Explain blocked/stale references; no silent rewriting of historical outputs |
| Model-free blank project / intent switch | No created chapter, no hidden mandatory Novel UI, no model launch or lost asset/permission |
| Save/reopen/export | Real independent-process/HTTP reopen and browser flow; identical original image digest |
| Unknown create/write receipt | Preserve uncertainty, reconcile; never title-match/adopt or automatically replay |
| Old binary ignores new optional origin fence | Preserve separate V1 profile / verified backup; code rollback alone is not safe downgrade |
| Future graph model/rights/port/cache errors | Typed ports, cycle rejection, explicit conversions, exact source/permission cache identity; M2 scope |

## 8. Immediate handoff and stopping boundaries

Proceed with the authorized M1 minimum image path on the original branch:
neutral blank creation, advisory intent/preset, existing asset-owner import,
server provenance/revision, restart/reopen and independently verified download.
Record real File/PG/UI/browser results, failures and screenshots against the
actual M1 source. Do not mark the full M1 storage/relationship/video scope complete
merely because one image slice passes.

Then continue the roadmap's safe dependency order. Shared owners require serial
integration. Any later CI optimization must preserve strict coverage/order/
skip/source truth and retain the original push capacity failure as history.

Keep PR Draft. No merge, force push, release/tag, production deployment, user's
Windows execution, personal API spending, broad filesystem scanning, automatic
model download or unapproved protected-shell redesign is authorized by M0.

## 9. Final documentation validation

At 2026-10-09 12:06 UTC, a local Python read-only document check resolved every
relative Markdown target, counted 325 unique capability IDs, verified every
status against the five-value vocabulary, and checked trailing whitespace:
**zero issues**. The status totals match §2. `git diff --check --` for the three
paths returned exit 0; because these files were then untracked, the independent
Python whitespace check is the substantive check of their new contents.

This is document integrity evidence, not a runtime test. The integrating parent
records the documentation commit SHA and its actual publication/check status;
prior 4350a61 CI cannot become that new commit's CI result by implication.
