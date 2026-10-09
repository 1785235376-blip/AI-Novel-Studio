# M1 Project Intent / Storage / Asset Core — Integration Report

**Current checkpoint: M1 PARTIAL, 2026-10-09 13:20 UTC. Full M1 acceptance remains open.**

- Implemented: neutral project entry, nonbinding intent/preset metadata, independent external image/video/audio import and original-byte export, original-owner asset/version/provenance, typed read-only Chapter/Screenplay references, descriptive relationships and bounded storage admission. The final V2 adapter rejects corrupt/coerced asset version counters without modifying the permissive legacy owner.
- Latest tested implementation: final focused File and real PostgreSQL 17.11 checks each **215 passed / 186 opposite-profile skips**; final API catalog **3 passed** and coverage infrastructure **174 passed**, all with identical unchanged-source maps. Matching PG log confirms normal shutdown. Final collection is **9,823 nodes, inventory only**. The corruption reproduction remains **FAIL: 7 failed / 7 skipped / 150 deselected**. Exact evidence is in §11.
- Earlier larger File **1,047 / 954 skips**, PG **1,011 / 987 skips**, frontend **1,773 / 8 existing skips**, catalog-check and corrected build successes remain bound to their own **pre-final-guard snapshots** (§10). They are not full current-tree regression proof. Final catalog generation retains **2,077 operations, M1 +34 / −0** with a new backend fingerprint.
- Separate M0 terminal CI: **push Cloud FAILURE / PR Cloud CANCELLED**, including PR aggregate failures despite PG execution success. No rerun, timeout change or trace-access workaround; historical evidence remains intact.
- Browser acceptance is **BLOCKED locally / NOT_RUN on hosted current M1**; new screenshots/geometry are unverified. Full Storage Manager paths/migration/recovery, general cache cleanup/limits, global reservation and running-job low-space pause, plus applied preset layouts, remain missing or partial. Full M1 stays **PARTIAL**, with only bounded minimum-path closure.
- Baseline HEAD is `0df2640c4c1a2d3052bb0a84d14445744d04046f`; the implementation end SHA/tree and publication receipt are **NOT YET RECORDED**. No published M1 SHA or CI success is asserted. Exact event-bound results belong to the forthcoming [PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) receipt.
- Safe nondependent M2/M3 work may continue while the missing storage/preset/browser guarantees remain explicit dependencies. User Windows/M12 remains **USER_APPROVAL_REQUIRED / LOCAL_REQUIRED / NOT_RUN**.

### Preserved initial report, 12:35 UTC

**Initial status: PARTIAL / IN_PROGRESS; draft integration report, not full M1 acceptance.**

Evidence cutoff for the initial report: **2026-10-09 12:35 UTC**. The minimum independent-image path has actual backend and frontend-unit evidence for earlier uncommitted snapshots. The latest relationships/storage work has a failed File integration run and source-bound frontend/build successes; its remaining verification and the new browser journeys are not complete. Full Storage Manager semantics remain substantially unimplemented.

## 1. Identity, scope and unchanged historical records

| Item | Exact identity / boundary |
| --- | --- |
| Repository / branch | `1785235376-blip/AI-Novel-Studio` / `feature/v2-narrative-platform` |
| PR | [47, Draft](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47); no merge or release |
| Foundation / first M1 test HEAD | `4350a61fb9f61acccb845fef96b24b9b1275bbd3` |
| Current documentation-baseline HEAD | `0df2640c4c1a2d3052bb0a84d14445744d04046f` |
| M1 implementation end commit/tree | **UNCOMMITTED / NOT YET RECORDED** |
| Current-source hosted M1 CI | **NOT_RUN**; no new hosted result is asserted |
| User Windows / GPU / model / paid API | **NOT_RUN / LOCAL_REQUIRED**; M12 is **USER_APPROVAL_REQUIRED** |

The M0 [feature matrix](AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md), [architecture](AI_NOVEL_STUDIO_V2_ARCHITECTURE.md) and [audit report](MILESTONE_M0_REPORT.md) remain the original source-bound inventory. Their rows are **not rewritten by this report**. The requirement mapping below records the subsequent M1 delta, including remaining gaps.

Historical Foundation result remains **PARTIAL_CI_CAPACITY**: [PR Cloud 37907528214](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528214) succeeded; [push Cloud 37907521986](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907521986) was cancelled under original File/PostgreSQL capacity limits and its strict aggregates refused incomplete evidence. Historical **39 PARTIAL + F00 INTEGRATED** and independent review **BLOCKED** remain unchanged. Existing failed receipts and screenshots are not deleted, rewritten or reclassified by M1.

Requirements were re-read directly from the supplied 2026-10-09 roadmap: §§3.1–3.3, 4.2, 5, M1 in §24 and Appendix C. Appendix C prioritizes one minimum image loop; it does **not** reduce the full M1 requirement to that single loop.

## 2. Implemented slice and original owners

### 2.1 Neutral entry and advisory preferences

`app/creative/workspace_api.py` delegates blank creation to the original project-creation owner. It adds explicit neutral activation and scope-aware reads/writes under server-owned `narrative_production_v2`. Original actor/project/branch authority is checked before work and again before releasing results or private errors. Current incarnation is captured and rechecked; intent is never an authorization input.

`IndependentWorkspaceService` in `app/creative/workspace.py` stores presentation metadata in existing Creative scope documents. Multiple `CreativeIntent` values, custom text and a `WorkspacePreset` are defined by `workspace_models.py`, with strict bounded inputs, CAS and limited preference history. Empty intent is valid. An explicit server-side `NEUTRAL_STUDIO` entry receipt, rather than zero chapters or a client hint, determines neutral presentation.

`frontend/src/creative/BlankProjectEntry.tsx`, `IndependentStudioWorkspace.tsx`, `studioClient.ts`, `frontend/src/App.tsx` and `frontend/src/novel/EntryExperience.tsx` provide the entry/consumer. IMAGE, VIDEO, AUDIO and ASSETS reuse a manual asset workspace. Original navigation remains available. Shared mode uses original eligible scope selection rather than fabricating a local branch. Browser resume hints are subordinate to fresh server authority.

**Preset limitation:** the inspected implementation saves a preference; it does not apply a preset-specific initial layout or construct a graph. The label must say so until a real layout mapping exists. This is PARTIAL against CORE-04, not a completed workspace-template engine.

### 2.2 Independent binary assets and provenance

The new service accepts bounded external `image`, `video` and `audio` uploads. Real media inspection runs before persistence; filename/MIME claims are not accepted as proof of valid media. Existing `AssetLibraryService` remains the binary, metadata, ID, version, digest, recoverable deletion and parent-lineage owner. Limits at this snapshot: **25 MiB per asset, 1,000 assets and 512 MiB recorded assets including trash per scope**. This is a bounded import slice, not a high-volume video library.

`AssetLibraryService.project_scope` and `CreativeProjectStore.owner_lease` bind new assets to the actual project incarnation and exact scope/branch, including branch `None`. The binding is server-only. Original APIs cannot read newly bound assets without the corresponding adapter lease; old unbound records are not silently adopted into the new view. Default-off/V1 mode hides new-origin records while retaining data. This preserves one owner rather than building a second asset inventory.

The browser upload and `EXTERNAL_IMPORT` declaration are **two separate writes**. File save may succeed while the provenance declaration fails. UI distinguishes that state and offers declaration-only retry, avoiding a repeat upload. License defaults to `UNSPECIFIED`; an author declaration is not legal verification. No AI generation, job or chapter is required for this manual path.

Download returns original verified bytes, original format, digest/version headers and a safe filename. It is not a transcode/export-format implementation. `source_job_id` assets deliberately require a later adapter rather than being presented as fully supported by this manual-only entry. Existing unbound assets and all generated kinds are not thereby a unified new Studio catalog.

### 2.3 Typed, read-only source bridge and descriptive relationship graph

`app/creative/workspace_relationships.py` stores bounded versioned declarations in reserved original asset metadata, `asset_relationships_v2`; it creates no relationship database, scheduler or prose copy. It supports `SOURCE_OF`, `DERIVED_FROM`, `REFERENCES`, `USED_IN`, `ALTERNATE_VERSION`, `APPROVED_FOR` and `LINKED_CONTEXT`, with actor/time/reason and exact target kind/ID/version/digest.

- **ASSET:** reads the currently authorized original asset owner, including lifecycle state.
- **CHAPTER:** reads the original scope-specific Chapter owner, checks project/branch and hidden/secret state, and returns a title/version/content digest. It does not return or overwrite manuscript body.
- **SCREENPLAY:** reads `lineage.media.screenplays`, the original screenplay owner, with exact project/branch and hidden/secret filtering. It uses `edit_version` and a canonical digest excluding `version_history`. It does not claim that every separate creative-document model is interchangeable with this owner.
- The reference catalog explicitly returns `read_only: true`, `content_copied: false`; unavailable sources are redacted. Link projections distinguish `CURRENT`, `STALE`, `DELETED`, `UNAVAILABLE`. Stored source versions are not silently advanced.
- Relation writes require the asset's current positive integer version; target version/digest are checked again before commit. `APPROVED_FOR` creation requires `domain.review`, not just intent or write permission, and remains a declaration rather than a rights grant.
- `SOURCE_OF`/`DERIVED_FROM` may describe only an already recorded original parent relation. They cannot invent generation provenance. Removal creates a tombstone; active incoming asset declarations and original parent links protect deletion through the new lifecycle path.
- The graph projection is explicitly `ASSET_RELATIONSHIPS`, `executable: false`, `knowledge_graph: false`, `automatic_regeneration: false`. Its current UI is a descriptive list/overview in `AssetRelationshipsPanel.tsx`, not an infinite node editor or M2 execution graph.
- Limits include 100 relation records per asset, including tombstones, and bounded reference indexes. This is not an unlimited knowledge/asset graph or garbage collector.

These are inspected implementation contracts. The first combined File run was **FAIL** (§5); no full current-source backend acceptance is inferred from this description.

## 3. Requirement-to-code gap assessment

M0 IDs identify the unchanged baseline rows. “Implemented slice” below means code exists and, where stated, has the specific receipts in §5; it does not promote the entire old row or all current code to PASS.

| Roadmap / M0 rows | Current code delta | Remaining requirement and honest status |
| --- | --- | --- |
| §§1.1, 3.1; CORE-01/08/10, START-08 | Original project owner plus explicit neutral entry/activation; manual asset workspace does not create chapters. | Backend image path has prior receipts; actual complete current browser/free-entry path still **NOT_RUN**. Independent creative tools beyond import/export remain later Studio scope. |
| §§1.2, 3.1; CORE-03, START-07 | Multiple/empty/custom intents and changeable preset metadata with strict CAS. | Basic preference implementation exists; layout recommendation/application and broader first-project capability guidance **PARTIAL**. |
| §1.2; CORE-04 | Preset is stored without restricting modules/assets or executing tasks. | Preset-specific initial layout and editable suggested graph are **MISSING** from this slice. Preserving nonbinding semantics is necessary but not full preset implementation. |
| §3.2; CORE-11/12/13, IMAGE-05 | Original binary identity/digest/version; decoded image/video/audio import; EXTERNAL_IMPORT/license projection; original-byte export. | Prior real-media File/PG owner roundtrips exist. New browser image/video proof, complete cross-kind field parity, generated-asset integration and full format export remain **PARTIAL**. |
| §3.2; CORE-18/19 | Incarnation/scope/feature fencing in the original asset owner; metadata redaction; same-slug and old-route regressions. | Tested in earlier core snapshots; relationship/storage changes and final integrated tree require rerun. Legacy data adoption remains deliberately absent. |
| §§3.2–3.3; CORE-15/16/20/21 | Seven descriptive types, current target projection and read-only original Chapter/Screenplay references. | Code exists; newer File integration not yet green and PostgreSQL/browser still pending at cutoff. Full relation graph UX/scalability and future asset types **PARTIAL**. |
| §3.2; CORE-17 | CAS trash/restore, dependency rejection and relation tombstones. | No general retention/purge manager; no directory/cache physical cleanup through Studio. **PARTIAL**. |
| §§3.1, 4.2; CORE-09, START-09 | Existing roots are consumed; download chooses the browser's configured/user-selected destination. | No per-project default export-directory preference, directory picker/configuration contract or category relocation UX. **PARTIAL**. |
| §5; STORE-01/02/10 | Packaging already separates installation/durable/runtime/cache roots; models remain external references. New storage response reports those owner categories. | Category labels do not establish configurable physical path separation or safe relocation of high-volume media. Full policy/UI **PARTIAL**. |
| §5; STORE-03 | Active/trash original recorded-byte counts for the current scope; quotas count trash. | Not total project disk occupancy: DB, metadata/history, proxies, caches, temporary media and filesystem allocation are not all measured. Existing unbound assets are excluded from this new fenced view. **PARTIAL**. |
| §5; STORE-04/09 | New bounded asset-filesystem free-space admission, 64 MiB reserve, upload-byte estimate and 507 errors. | Only import admission; no complete task render/proxy/model estimate, running-job low-space pause/resume or guaranteed cross-owner reservation. New negative tests require corrected-source rerun. **PARTIAL**. |
| §5; STORE-05 | Import quotas exist; original portable-cache records have their own bounds. | Cache/proxy/thumbnail size limits and generalized eviction/reclaim policy are not implemented here. **PARTIAL**. |
| §5; STORE-06 | Original `PortableProjectsService.storage/cleanup` already supplies exact preview-digest/confirmation for verified unused portable export cache. | Preserve this bounded existing capability; it is not wired as full neutral Studio cleanup and must not be broadened to models or arbitrary project files. M0 EXISTS row remains unchanged in its original narrow scope. |
| §5; STORE-07/08 | Original atomic writes, backups and portable relink/recovery are reusable. | Verified directory-copy migration, reference switching, interruption journal, rollback/restart recovery and cleanup of old copies are **not implemented by the new admission adapter**. **PARTIAL overall; new full manager missing**. |
| M1 gate / GATE-M1 | Minimum manual core implemented in uncommitted code; real media/unit evidence accumulated. | Full M1 remains **PARTIAL**: storage/preset gaps plus exact final-source backend/browser/visual/regression and commit/CI evidence outstanding. |

## 4. Storage Manager boundary in detail

### What `StudioStorageAdmission` actually does

`app/creative/storage_admission.py` calls `shutil.disk_usage(workspace.assets.root)`. It subtracts a fixed **64 MiB** reserve and exposes an import allowance capped by remaining project quota. Invalid/unknown disk readings fail closed. Import checks the incoming decoded byte length before creation, then rechecks a positive remaining reserve after staging rather than counting staged bytes twice. `ENOSPC` is mapped to a private 507 failure through the existing API envelope. The original asset owner removes only a newly allocated uncommitted binary on write failure; a committed record survives an ambiguous later error for idempotent recovery.

It accepts **no client filesystem path**. Its `paths` object consists of owner/category descriptors, not selected directories. It explicitly reports no external-model scan, no automatic cleanup and no automatic migration. This is a safe admission adapter, not a Storage Manager.

At the initial inspection, the project-storage UI displayed asset/trash counts and owner/category wording but not admission state/available bytes/reserve. A display correction is in progress at this snapshot; any later code and result must be recorded as a new snapshot. Rendering a free-space value does not complete relocation/cleanup semantics.

### Existing owners to extend, not duplicate

- `app/packaging/paths.py`: `WindowsPackagingPaths` owns established app/user-data/runtime/cache/config/log/backup separation and destructive-path checks. Its current resolution is not a general user-selectable per-project root manager.
- `app/experimental/portable_projects.py`: `PortableProjectsService.storage` reports explicitly authorized categories; `cleanup` accepts a current preview digest, selected eligible records and confirmation, then removes only verified reproducible export cache. Manuscript, assets, history, trash and recovery inputs remain protected.
- `AssetLibraryService` owns asset bytes and metadata. New mutable root/index/version ownership must not be duplicated in the M1 adapter.

### Conditions still needed for full storage acceptance

1. Define category/path preferences and authoritative owner integration, including existing-project behavior, safe defaults, user selection and export-directory semantics. Reject roots, traversal, symlink/junction escapes, unsupported/network locations and overlapping destructive scopes as appropriate.
2. Produce a migration **preview**, identifying source/destination, exact owned file set, estimated temporary duplication, free space, protected/external paths, reference updates, permissions and approval. A category label is not this preview.
3. Implement verified copying and digests before switching references, with concurrency fences and a durable state machine for interrupted copy, commit, recovery and rollback. Preserve the original data until successful verification and separately authorized cleanup; do not move/copy external model weights by default.
4. Provide bounded cache/proxy policy, accurate quota/occupancy units and exact cleanup preview/confirmation through original owners. A trash record is not automatically disposable; referenced results and recovery inputs require protection.
5. Connect estimated disk demand and low-space pause/resume to applicable original Job/executor owners; distinguish recoverable pause, failed import and unknown upstream. No implicit paid fallback or job replay.
6. Verify on File and real PostgreSQL as applicable, with injected failures before/after copy/reference commit, source mutation, concurrent jobs, permission revocation, disk exhaustion and restart. User Windows filesystem behavior remains separate **LOCAL_REQUIRED**.

No migration is performed or claimed by this report. Safe follow-on planning can proceed while completing the minimum asset path; the full M1 label remains PARTIAL until requirements are explicitly implemented/verified or the user changes scope.

## 5. Actual receipts read and verified

For each JSON below, the original log was read, its SHA256 was recomputed and matched `log_sha256`, and `sources_changed_during_check:false` was confirmed. This report preparation did not execute new tests. These receipts describe **uncommitted source snapshots**: their recorded HEAD is a baseline, and their before/after source maps identify the actual tested inputs.

### 5.1 Earlier core and UI slices

| Receipt / UTC interval | Actual outcome | Exact interpretation |
| --- | --- | --- |
| [core File first](docs/delivery/v2-development/stage-m1-core-file-first.json), [log](docs/delivery/v2-development/stage-m1-core-file-first.log), 12:03:08–12:03:33 | **FAIL**, exit 1; 10 failed / 95 passed / 105 skipped / 2 errors | Includes new fixture attempts to mutate frozen Settings and authorization/fixture failures. Original failed receipt is retained; no blanket assertion that all failures were product or all were harmless. |
| [core File corrected](docs/delivery/v2-development/stage-m1-core-file-corrected.json), [log](docs/delivery/v2-development/stage-m1-core-file-corrected.log), 12:04:56–12:05:20 | **PASS**, exit 0; 107 passed / 107 opposite-profile skips | First bounded File core proof; not later relationship/storage code. |
| [core PostgreSQL](docs/delivery/v2-development/stage-m1-core-postgres-first.json), [log](docs/delivery/v2-development/stage-m1-core-postgres-first.log), 12:06:03–12:06:40 | **PASS**, exit 0; 109 passed / 109 opposite-profile skips | Real disposable PostgreSQL **17.11**, checked with actual `SELECT version()` in the [runtime receipt](docs/delivery/v2-development/stage-m1-core-postgres-first-postgres-runtime.json). Not a fake PG adapter. |
| [focused frontend](docs/delivery/v2-development/stage-m1-frontend-first.json), [log](docs/delivery/v2-development/stage-m1-frontend-first.log), 12:13:00–12:13:08 | **PASS**, 123 tests / 11 files | Unit/DOM tests for entry/assets/shell/scope/resume; not a browser screenshot or live E2E result. |
| [build first](docs/delivery/v2-development/stage-m1-build-first.json), [log](docs/delivery/v2-development/stage-m1-build-first.log), 12:13:01–12:13:18 | **FAIL**, exit 1 | New test used unsupported `exact` option in `ByRoleOptions`; TypeScript stopped before later chained build/token steps. |
| [build corrected](docs/delivery/v2-development/stage-m1-build-corrected.json), [log](docs/delivery/v2-development/stage-m1-build-corrected.log), 12:17:46–12:18:26 | **PASS**, exit 0 | TypeScript + Vite + token guard (43 files); large-chunk warning remains. |
| [frontend full](docs/delivery/v2-development/stage-m1-frontend-full.json), [log](docs/delivery/v2-development/stage-m1-frontend-full.log), 12:17:45–12:18:38 | **PASS**, 1,644 passed / 8 existing skips; 242 files passed / 2 skipped | Full unit suite for that snapshot, not final M1 source after later edits. |

Core File and PostgreSQL commands both selected `tests/test_v2_independent_workspace.py` and `tests/test_v2_independent_workspace_api.py`; each used its own isolated `--basetemp` recorded verbatim in its JSON. Fixtures mark File/PostgreSQL cases separately, accounting for opposite-profile skips. The two runs had different total counts/snapshots and are not combined into one invented unique coverage total.

Core tests include **real decoded synthetic PNG, actual FFmpeg-produced MP4 and PCM WAV** owner import→provenance→service reopen→original-byte export with no chapters. Missing decoders are asserted as a failed prerequisite rather than skipped. Mounted HTTP tests cover the independent image path, aliases, CAS, current identity/revocation and original-route fencing. A separate fresh Python-process reopen test exists in the executed core files; that is distinct from a browser refresh. Synthetic media and real decoders do not establish model generation or production image/video quality.

### 5.2 New relationships/storage checkpoint

| Receipt / UTC interval | Actual outcome | Boundary |
| --- | --- | --- |
| [combined File first](docs/delivery/v2-development/stage-m1-relationships-storage-file-first.json), [log](docs/delivery/v2-development/stage-m1-relationships-storage-file-first.log), 12:32:31–12:33:50 | **FAIL**, exit 1; 177 passed / 179 opposite-profile skips / 2 failed | Both failures are new `test_mounted_low_space_is_507_no_private_path_or_partial_import` API aliases. The asserted error-envelope shape differs from the existing canonical response. Assertion correction and new run pending at cutoff; this receipt remains FAIL. |
| [relationships frontend first](docs/delivery/v2-development/stage-m1-relationships-frontend-first.json), [log](docs/delivery/v2-development/stage-m1-relationships-frontend-first.log), 12:32:33–12:33:32 | **PASS**, 1,718 passed / 8 existing skips; 245 files passed / 2 skipped | Actual full unit suite for its stable source snapshot. Subsequent draft/resume race fixes are outside that result. |
| [relationships build first](docs/delivery/v2-development/stage-m1-relationships-build-first.json), [log](docs/delivery/v2-development/stage-m1-relationships-build-first.log), 12:32:35–12:33:15 | **PASS**, exit 0 | TypeScript + Vite + token guard (43 files); App 830.87 kB and ExperimentalWorkbench 628.01 kB trigger the existing >500 kB chunk warning. |

The new combined backend command is:

```sh
python -m pytest tests/test_v2_independent_workspace.py tests/test_v2_independent_workspace_api.py tests/test_v2_asset_relationships.py tests/test_v2_storage_admission.py -q --basetemp=.runtime/v2-checks/stage-m1-relationships-storage-file-first/pytest
```

The JSON records the actual interpreter and full isolated environment. Build command is `cd frontend && node node_modules/typescript/bin/tsc -b && node node_modules/vite/bin/vite.js build && node ../scripts/check_ui_design_tokens.mjs`. Full frontend command is `cd frontend && node node_modules/vitest/vitest.mjs run`. Focused frontend paths/arguments are retained in its original JSON rather than reconstructed as a different run.

### 5.3 Why earlier PASS cannot certify the current tree

A read-only comparison at 12:34 UTC found the earlier core receipts each recorded **1,612 inputs** but differed from the current tree at **14 recorded paths**, with the new relationship/storage source and tests absent from those maps. The 12:18 frontend/build receipts recorded **1,617 inputs** and differed at **10 recorded paths**, with storage admission and new backend suites absent. This is source inventory evidence, not a test rerun. Counts are a timestamped observation, not a promise about later edits.

Further fixes are in progress at this snapshot for asynchronous overview/resume selection overwriting drafts, review-only capability display and admission visibility. New tests/results must bind to the fixed source. Do not label an unexecuted correction as verified simply because the previous full unit run passed.

## 6. Verification still required

| Gate | Status at cutoff | Required next evidence |
| --- | --- | --- |
| Corrected combined relationships/storage File run | **NOT_RUN** | New independent receipt; retain the 2-failure original. |
| Current combined real PostgreSQL | **NOT_RUN** | Actual runtime identity plus all applicable relationship/storage/current core cases, correct profile skips. |
| Post-race-fix full frontend and build/token | **NOT_RUN** | Current source-stable receipts after all UI edits. |
| `v2-independent-studio-live.spec.ts` | **NOT_RUN** | Real isolated File/API/Vite/Chromium path, file-picker image upload, correct project/asset reopen and byte-verified download, no model/chapter mutations. |
| `v2-asset-relationships-live.spec.ts` | **NOT_RUN** | Real UI typed references, stale/CAS and optional-link behavior; no mock response substituted. |
| Independent video file-picker/reopen/export | **NOT_RUN at browser level** | Specific executed browser case and real MP4 byte/metadata proof; owner-level tests alone are not this UI proof. |
| Existing V2 browser and protected DS geometry | **NOT_RUN for integrated M1** | Existing suites plus affected entry/caller tests; no blanket snapshot updates. |
| Four-size visual review | **NOT_RUN** | Actual neutral empty/imported/error screenshots at 1366×768, 1440×900, 1920×1080, 2560×1440, visually inspected; retain compact regression. |
| Full applicable backend/regression/native/Interop gates | **NOT_RUN for final M1** | Exact final-tree evidence; old 4350 CI is historical only. |
| Full Storage Manager migration/cache/path policy | **MISSING/PARTIAL implementation** | Owners, API/UI, actual safe migration/cleanup/recovery and tests, not only an admission response. |
| Final commit/push/Draft PR/hosted M1 checks | **PENDING** | Actual end SHA/tree and separate push/PR run/attempt terminal results. |
| User Windows installation/GPU/models | **LOCAL_REQUIRED / NOT_RUN** | Explicit M12 authorization followed by package-bound actual execution. |

## 7. UI and safety acceptance boundaries

The only approved protected-shell extension remains the optional ContextBar noun in the [change request](docs/ui/design_system_change_request_v2_project_label.md): default `小说：`, explicit current neutral route `项目：`, unchanged geometry/tokens/tab order. This report grants no new design permission and no visual PASS. The original [UI review](AI_NOVEL_STUDIO_V2_UI_UX_REVIEW.md) remains a prior snapshot; append actual M1 images/results when obtained.

Current scope does not include a model download/launch, paid provider, generalized graph execution, pixel editor, actual I2V generation, real NLE or Tutor-control capability. Relationships are optional; independence means the manual asset path works without linking a chapter, screenplay or Director. No-modeled media import is a real useful slice, but not the entirety of Image or Video Studio.

Rollback requires preserving the existing V1 profile and new origin-bound records. Disabling V2 hides its records without deleting them. An older binary that does not understand new optional fences must not be pointed at the same unreviewed new-data profile and presumed safe. No frozen V1/RC1 history or user data is modified by this documentation work.

## 8. Next honest milestone decision

First obtain corrected current-source File/PostgreSQL/frontend/browser/visual evidence and record the minimum independent-image delivery precisely, including failures and screenshots. Preserve video-owner evidence while adding its distinct UI acceptance. Continue the authorized roadmap with the same original owners; use the requirement gaps above to implement Storage Manager and preset semantics instead of silently declaring them deferred-complete.

**Current conclusion: M1 has a substantial bounded implementation and real partial verification, but full M1 is not complete.** No stage-end SHA, all-green CI, user-Windows result or release readiness is asserted.

## 9. Addendum — integrated checkpoint and separate M0 CI observation

Added **2026-10-09 12:44 UTC**. Sections 1–8 remain the **12:35 UTC snapshot**; their pending statuses and earlier failures are not rewritten. This addendum records subsequent actual outcomes. **Full M1 remains PARTIAL.**

### 9.1 Integrated local runs, 12:40–12:42 UTC

All four `stage-m1-integrated-*` JSON receipts were read and each corresponding original log SHA256 independently recomputed. All matched; all report `sources_changed_during_check:false`. Each records baseline HEAD `0df2640c4c1a2d3052bb0a84d14445744d04046f` plus an identical **1,629-input source map**, identifying the tested uncommitted M1 tree rather than attributing its code to the documentation-only commit.

The SHA256 of that map, serialized as sorted-key compact JSON (`sort_keys=True`, separators `(',', ':')`), is `5e977272de13ee2fda9b64d3054615c5e60b8e819809f6a705db639e025c616a` for all four runs. This confirms their recorded source agreement; it is not an end commit, final feature-coverage manifest or evidence that later edits were tested.

| Actual receipt / UTC interval | Outcome | Scope and preserved limit |
| --- | --- | --- |
| [Integrated File](docs/delivery/v2-development/stage-m1-integrated-file.json), [original log](docs/delivery/v2-development/stage-m1-integrated-file.log), 12:40:09–12:41:34 | **PASS**, exit 0; **184 passed / 179 opposite-profile skips**, 1 warning, pytest 82.08 s | Core + relationships + storage + Studio CI contracts, **including 3 browser-job infrastructure guard tests** from `.github/ci/test_v2_browser_job.py`. The 184 count is not wholly product-runtime tests or a browser execution. |
| [Integrated PostgreSQL](docs/delivery/v2-development/stage-m1-integrated-postgres.json), [original log](docs/delivery/v2-development/stage-m1-integrated-postgres.log), 12:40:15–12:42:02 | **PASS**, exit 0; **181 passed / 179 opposite-profile skips**, 1 warning, pytest 102.01 s | Same five product/Studio-CI files, without the three additional browser-job infrastructure cases. Actual disposable **PostgreSQL 17.11** verified by the [runtime probe receipt](docs/delivery/v2-development/stage-m1-integrated-postgres-postgres-runtime.json). Not mock PostgreSQL. |
| [Integrated frontend](docs/delivery/v2-development/stage-m1-integrated-frontend.json), [original log](docs/delivery/v2-development/stage-m1-integrated-frontend.log), 12:40:11–12:41:18 | **FAIL**, exit 1; **1 failed / 1,769 passed / 8 existing skips**; 1 failed / 247 passed / 2 skipped files | One newly authored overbroad inspector-text assertion failed, described below. The full frontend run remains FAIL; its many passes do not make it green. |
| [Integrated build](docs/delivery/v2-development/stage-m1-integrated-build.json), [original log](docs/delivery/v2-development/stage-m1-integrated-build.log), 12:40:12–12:40:58 | **PASS**, exit 0; TypeScript, Vite and **43-file** token guard | Existing chunk-size warning persists: App **834.34 kB**, ExperimentalWorkbench **628.01 kB**. Compile/token success is not a screenshot, accessibility or live-browser approval. |

File/PG profile results remain separate; their opposite-profile skips do not represent native-model tests that ran. Both preserve the existing Starlette/httpx deprecation warning. The linked runtime receipt establishes the actual running server/version. The matching test-owned PostgreSQL log was separately inspected and confirms a controlled fast shutdown, completed checkpoint and final shutdown after the test receipt finished. This is the current run's log, not the older shared server log.

Shutdown evidence: `.runtime/v2-checks/stage-m1-integrated-postgres/postgres.log`, full-file SHA256 `2bd677cd7f615b6fe7c6a01a8ba6c2a4bf778a4cb67da2e02eb90cafda5d33f2`. Relevant exact lines:

```text
2026-10-09 12:42:02.304 UTC [9] LOG:  received fast shutdown request
2026-10-09 12:42:02.309 UTC [10] LOG:  shutting down
2026-10-09 12:42:02.311 UTC [10] LOG:  checkpoint complete: wrote 120 buffers (2.9%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.002 s, sync=0.001 s, total=0.002 s; sync files=81, longest=0.001 s, average=0.000 s; distance=1121 kB, estimate=1121 kB; lsn=0/576E050, redo lsn=0/576E050
2026-10-09 12:42:02.314 UTC [9] LOG:  database system is shut down
```

Exact File selection recorded in its receipt:

```sh
python -m pytest tests/test_v2_independent_workspace.py tests/test_v2_independent_workspace_api.py tests/test_v2_asset_relationships.py tests/test_v2_storage_admission.py tests/test_v2_studio_ci.py .github/ci/test_v2_browser_job.py -q --basetemp=.runtime/v2-checks/stage-m1-integrated-file/pytest
```

The PostgreSQL command selects the same five `tests/` files, omits `.github/ci/test_v2_browser_job.py`, and uses its own `.runtime/v2-checks/stage-m1-integrated-postgres/pytest` base. Actual interpreter, isolated environment and runtime identity remain in the original JSON. Frontend/build commands are the full commands already described in §5.2; they were executed anew under these receipt identities.

The two earlier low-space error-envelope assertions now have a subsequent successful combined execution. The original [2-failure File receipt](docs/delivery/v2-development/stage-m1-relationships-storage-file-first.json) is retained as FAIL; it is not edited to match this later result.

### 9.2 Newly failing frontend assertion: evidence and planned correction

The only integrated frontend failure is:

`frontend/src/creative/IndependentStudioReadFences.test.tsx` → `ignores delayed recovery after the author explicitly selects a different asset and starts a draft`.

Its line 61 checks that the **entire inspector text** excludes `source.png`. The actual failure output still identifies `target.png` as the selected asset, includes asset ID `target`, and preserves the newer relationship draft. `source.png · v2` legitimately appears as a selectable parent in the existing provenance form. An assertion against all descendant text therefore cannot determine selected-asset identity.

The planned correction is to assert the selected asset's identity-specific heading/ID/preview and retained draft, while allowing the legitimate provenance-parent option. At this addendum cutoff that correction and its full-suite rerun remain **pending**. No assertion is removed merely to hide a runtime regression, no complete race-behavior PASS is inferred from a failure stopping before later assertions, and the original failing receipt remains intact.

### 9.3 Actual M0 documentation-commit CI failure is a different identity

The new M0 documentation commit is `0df2640c4c1a2d3052bb0a84d14445744d04046f`, tree `f800c0e8a6d920e8836a027707c8078c5a8421f2`. Its hosted results are separate from both the earlier `4350a61` historical CI and the uncommitted M1 local checks above. M0's hosted checkout does not include the concurrent M1 implementation.

The persisted [first browser-failure record](docs/delivery/v2-development/m0-push-browser-first-failure.json) and [original job log](docs/delivery/v2-development/m0-ci-logs/push-v2-browser-job.log) bind the failed push to [run 37928438685, job 113812940144, attempt 1](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928438685/job/113812940144).

- Existing V2 live suite: **6 passed / 1 failed**. The first real File authoring case exceeded its original **180,000 ms** test timeout while waiting for `POST director-proposals/{proposal.id}/review` after a native double-click. The log reports the pending `page.waitForResponse` and eventual page/context/browser closure; it does not reveal the complete underlying browser state.
- Existing mocked/geometry suite: **8 passed / 0 failed**. This result does not cancel the independent live failure.
- Artifact `11615127270`, size **9,074,009 bytes**, metadata digest `43ac1e673dea6d4a0c82c956e6e9228f78aacf9898732f1ece08eed6a3352fb0`: download returned **HTTP 403 Forbidden**, status **TRACE_ACCESS_BLOCKED**.
- **No trace, artifact screenshot or error-context file was inspected.** The artifact digest is metadata, not a downloaded-byte verification. No alternate route around the denial was attempted; no rerun, force-click, timeout increase or baseline update was used to eliminate the failure.
- The saved job log was actually read; its independently computed SHA256 is `8e9397395a83f66fc3605d3830cb5c3e8f386b6413ecb585633b224a33601a94`. The failure-record JSON SHA256 is `132b20a8bfbbcafec2a2adc5e232b6804110de678f1f07cdcf5d0144cdd481ff`.

Source inspection shows `clickTwice` uses the real browser `locator.dblclick({ delay: 10 })` and `mutate` installs its response waiter before invoking the action. A **fast-response interaction with the native double-click is a hypothesis for a separate controlled reproduction**. It is **not an established cause of this CI failure** without the blocked trace or independent reproduction. Do not state that the network response definitely arrived, that the DOM definitely changed between clicks, or that the product/test is exonerated.

At the **12:43 UTC observation**, M0 CI additionally had: [PR Cloud 37928446079](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928446079) **File cancelled at the original 20-minute cap, V2 browser passed**; [push Cloud 37928438685](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928438685) **File passed, V2 live 6/7 with geometry 8/8**; **PostgreSQL still pending**. Both are original attempt 1 for the M0 source identity above. This is a partial monitoring checkpoint, not a terminal all-workflows summary. PR success cannot repair the failed push browser case, push File cannot replace PR's cancelled File proof, and local PostgreSQL success cannot complete either hosted PostgreSQL run. Exact terminal metadata remains to be recorded.

### 9.4 Updated outstanding gates

The bounded current-checkpoint backend contract suites now have File and real PostgreSQL PASS, and the integrated build/token checks pass. The integrated frontend is still FAIL pending the identity-specific assertion correction and rerun. Subsequent source changes require their own source-bound results.

The actual independent-image file-picker/reopen/export browser journey remains **NOT_RUN** at this cutoff. A separate real MP4 file-picker case is being authored to prove external video import/reopen/original-byte export; it is also **NOT_RUN**. Earlier decoded MP4 service tests do not substitute for that UI journey. Relationship browser acceptance, actual new-state screenshot review, final regression/commit/M1 hosted CI and the full Storage Manager/preset implementation gaps in §§3–4 remain open.

The observed M0 hosted failure and capacity cancellation remain visible while independent authorized M1 work continues. Once its minimum independent path is actually verified and recorded, nondependent M2/M3 work can proceed under the roadmap; storage migration/cleanup gaps must explicitly block operations that depend on them. That sequencing does not make full M1 complete. **Neither the integrated local successes nor a later corrected test may relabel a historical failure, complete full M1, authorize M12, or establish release readiness.**

## 10. M1 as-built checkpoint — owner regression, corrected UI and inventory

Recorded **2026-10-09 13:00 UTC**. This section supersedes earlier pending statements only for the checks identified below; §§1–9 preserve their original time-bound observations. Stage status is still **PARTIAL**, with no committed/published M1 end identity yet.

### 10.1 Receipt verification and source identity

The following original JSON receipts and logs were read, their log SHA256 values independently recomputed and matched, and their before/after source maps compared. All report `sources_changed_during_check:false` with baseline HEAD `0df2640c4c1a2d3052bb0a84d14445744d04046f`. Baseline HEAD is not the tested implementation's end commit.

| Receipt / UTC execution interval | Actual terminal outcome | Coverage / limit |
| --- | --- | --- |
| [Owner regression File](docs/delivery/v2-development/stage-m1-owner-regression-file.json), [log](docs/delivery/v2-development/stage-m1-owner-regression-file.log), 12:46:54–12:50:52 | **PASS**, exit 0; **1,047 passed / 954 skipped**, 1 warning; pytest **232.85 s** | Selected original asset/lifecycle/safety/media/lineage, shared-authority/generation, project lifecycle and V2 suites; includes 3 browser-job infrastructure guards. Not the complete backend manifest and not a browser run. |
| [Owner regression PostgreSQL](docs/delivery/v2-development/stage-m1-owner-regression-postgres.json), [log](docs/delivery/v2-development/stage-m1-owner-regression-postgres.log), 12:46:56–12:58:21 | **PASS**, exit 0; **1,011 passed / 987 skipped**, 1 warning; pytest **678.29 s** | Same selected product files, excluding the 3 additional infrastructure guards. [Runtime probe](docs/delivery/v2-development/stage-m1-owner-regression-postgres-postgres-runtime.json) establishes actual loopback **PostgreSQL 17.11**. Profile skips stay separate; no summing these runs as unique test coverage. |
| [API catalog check](docs/delivery/v2-development/stage-m1-api-catalog.json), [log](docs/delivery/v2-development/stage-m1-api-catalog.log), 12:52:33–12:52:39 | **PASS**, exit 0; **3 passed**, 3.78 s | `tests/test_surface_api_catalog.py`; source/catalog consistency, not proof all mounted operations were exercised. |
| [Director fast-receipt RED](docs/delivery/v2-development/stage-m1-director-fast-receipt-red.json), [log](docs/delivery/v2-development/stage-m1-director-fast-receipt-red.log), 12:45:01–12:45:03 | **FAIL**, exit 1; **1 failed / 2 passed** | Controlled jsdom fast-receipt reproduction, preserved below. |
| [Director fast-receipt GREEN](docs/delivery/v2-development/stage-m1-director-fast-receipt-green.json), [log](docs/delivery/v2-development/stage-m1-director-fast-receipt-green.log), 12:46:53–12:46:58 | **PASS**, exit 0; **45 passed / 4 files** | New fast-receipt tests plus existing Director panel/model controls/Creative workspace units. It is not inspection of the blocked M0 browser trace. |
| [Full frontend](docs/delivery/v2-development/stage-m1-final-frontend.json), [log](docs/delivery/v2-development/stage-m1-final-frontend.log), 12:47:05–12:48:09 | **PASS**, exit 0; **1,773 passed / 8 existing skips**, 249 passed / 2 skipped files | Includes identity-specific delayed-recovery regression, truthful preset/storage/reviewer states and Director correction. Earlier integrated frontend FAIL remains intact. |
| [Final build first attempt](docs/delivery/v2-development/stage-m1-final-build.json), [log](docs/delivery/v2-development/stage-m1-final-build.log), 12:47:07–12:47:39 | **FAIL**, exit 1 | Two newly authored `getByRole` calls in `AIDirectorFastReceipt.test.tsx` used unsupported `exact` options. TypeScript stopped; Vite and token steps were **NOT_REACHED**. Runtime unit success did not make this build green. |
| [Corrected build](docs/delivery/v2-development/stage-m1-final-build-corrected.json), [log](docs/delivery/v2-development/stage-m1-final-build-corrected.log), 12:58:36–12:59:16 | **PASS**, exit 0 | TypeScript → Vite → **43-file** token guard. Chunk-size warning remains, including App **834.38 kB**; no warning suppression or visual-baseline refresh. |
| [Corrected full frontend](docs/delivery/v2-development/stage-m1-final-frontend-corrected.json), [log](docs/delivery/v2-development/stage-m1-final-frontend-corrected.log), 12:58:37–12:59:34 | **PASS**, exit 0; **1,773 passed / 8 existing skips**, 249 passed / 2 skipped files | Terminal receipt, not a prediction from a running check. Does not replace outstanding real-browser/visual acceptance. |

Owner File/PG, API-catalog check, Director GREEN and the first final frontend/build share **1,630 source inputs**, compact sorted-key map SHA256 `4a7bec648cf9ddf3604317a53cd93877f5e76913e86e322c54ba9c4cdef26d69`. Corrected build/frontend share **1,630 inputs**, map SHA256 `189bffdff6471d36c9ef81d3bdff10c184fc154e89f448e005a0bea5954eb548`. Comparing those maps finds exactly one changed path: `frontend/src/creative/AIDirectorFastReceipt.test.tsx`. No backend application source changed between these recorded maps. The RED source map is different and is retained with its own receipt. These facts establish source relationships; none supplies a final Git commit or a full-suite verdict.

The owner regression commands enumerate 19 `tests/` files in the linked JSON; File additionally selects `.github/ci/test_v2_browser_job.py`. Each uses its own isolated data root and `--basetemp`; actual interpreter, mock-provider/offline settings and command are preserved. Backend skips are profile-conditioned exclusions, not silently passed Windows/model checks. The existing Starlette/httpx deprecation warning remains visible.

The **matching owner-regression** PostgreSQL log, `.runtime/v2-checks/stage-m1-owner-regression-postgres/postgres.log`, was inspected after completion; SHA256 `2723239882c483c3cf885d4b250cabf064c93af6ea65758e189098b8d6a30987`. It records:

```text
2026-10-09 12:58:21.884 UTC [9] LOG:  received fast shutdown request
2026-10-09 12:58:21.891 UTC [10] LOG:  shutting down
2026-10-09 12:58:21.892 UTC [10] LOG:  checkpoint complete: wrote 156 buffers (3.8%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.001 s, sync=0.001 s, total=0.001 s; sync files=63, longest=0.001 s, average=0.000 s; distance=3992 kB, estimate=18832 kB; lsn=0/7ABD130, redo lsn=0/7ABD130
2026-10-09 12:58:21.896 UTC [9] LOG:  database system is shut down
```

### 10.2 UI correction and preserved browser uncertainty

The new fast-receipt unit reproduction resolves the first proposal response and React state **before** delivering the second pointer activation (`detail:2`). Its RED output created `proposal-1` and `proposal-2`, then reviewed `proposal-2` instead of the original expected proposal. `AIDirectorPanel.tsx` now ignores multi-click continuation for preparation while preserving keyboard activation (`detail:0`), later independent single clicks (`detail:1`), in-flight locking and explicit human review. GREEN verifies first-proposal identity and edited review content along with adjacent behavior.

This establishes a controlled **unit-level product defect and correction**. It does **not** establish the inaccessible M0 CI trace's exact cause, native browser event timing or final browser resolution. The original M0 live failure remains FAIL, its artifact access remains **TRACE_ACCESS_BLOCKED (403)**, and no trace has been inspected. The browser test's native double-click, response waiters, original timeouts and original evidence must stay intact for a later actual run.

`IndependentStudioWorkspace.tsx` now keeps delayed asset recovery/refresh from replacing a newer selection or relationship/provenance draft, uses authority-scoped readers, displays reviewer-only versus read-only capability, and labels presets as **saved preferences only**. Storage display distinguishes `READY`, `LOW_SPACE_OR_QUOTA` and `UNAVAILABLE`; saved assets remain readable/exportable when import admission fails. `AssetRelationshipsPanel.tsx` preserves optional, read-only source projections and backend review authority. The corrected full suite supplies unit evidence for these states. No actual image/video browser screenshot, geometry PASS or native accessibility result is asserted.

### 10.3 API surface and independent collection inventory

The [catalog generation receipt](docs/delivery/v2-development/catalog-25061dfa7a78.json) binds an isolated generation to staged tree `25061dfa7a78b4d0567d8c8853c7b1a2f9cba6d2`; it is **not** a published end commit. All four recorded output hashes match the current catalog files. The current mounted catalog contains **2,077 method/path operations**. A direct comparison with the M0 documentation-baseline catalog gives **34 additions / 0 removals**: 17 logical operations under both `/api` and `/api/v1`. These cover blank creation, neutral activation, overview/preferences, manual assets/download/lineage/lifecycle, storage admission, references and relationships. The catalog's own cumulative `added:244` compares against its older `starting_sha`, not this M1-only delta; do not confuse those baselines.

The [independent collection review](docs/delivery/v2-development/stage-m1-collection-review.json), recorded 12:59:15 UTC, is explicitly **INVENTORY_ONLY**, `tests_executed:false`. Collection exited 0 with **9,809 nodes**, **9,151 original baseline nodes preserved in order**, **658 additional nodes**, and unchanged historical skips. Frozen manifest SHA256 is `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`. The 658 additions are relative to that frozen baseline, not all newly authored during M1. The documented earlier `tests/test_windows_portable_entry.py` `-B` launcher-expectation migration remains identified by its original commit and purpose. Inventory and retained historical migration do not grant independent-review approval or prove those nodes executed.

### 10.4 M0 hosted observation at 12:49 UTC, still separate

The persisted [12:49:12 UTC checkpoint](docs/delivery/v2-development/m0-ci-checkpoint-1249.json) is **IN_PROGRESS_WITH_NONPASS** for M0 HEAD `0df2640c4c1a2d3052bb0a84d14445744d04046f`, PR merge checkout `09cc0edc25fad8f82377650a504beb65af99c0bf`, tree `f800c0e8a6d920e8836a027707c8078c5a8421f2`.

- [PR Cloud 37928446079](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928446079): File and frontend jobs **CANCELLED**; V2 browser, original File TCP, Windows contracts/package and PG shard 1 **SUCCESS**; PG shard 0 **IN_PROGRESS**.
- [Push Cloud 37928438685](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928438685): File, frontend, original File TCP and Windows contracts/package **SUCCESS**; V2 browser **FAILURE**; both PG shards **IN_PROGRESS**.

These are original attempt-1 job observations, not terminal workflow conclusions. §9.3 preserves the failed push's live **6 passed / 1 failed**, geometry **8 passed** and blocked trace. There was no rerun or timeout change. Hosted native package success remains fixture/package evidence, not execution on the user's Windows installation, GPU or models. Later terminal metadata must append to this record without overwriting it.

### 10.5 Checkpoint decision and explicit dependency blocks

The minimum independent path is implemented and has real decoded-media owner roundtrips plus current source-bound backend/frontend-unit evidence. Its **actual browser acceptance is still pending**, including external PNG and MP4 file-picker → save/reopen → original-byte export, default-off/V1 behavior, relationship references, dirty-state recovery and reviewed screenshots. No minimum-path browser PASS is claimed.

The architecture and feature matrix receive an **append-only M1 delta**, leaving the M0 inventory and its 325 rows unchanged. The stage may proceed to safe, nondependent M2/M3 contract work with this checkpoint recorded; that sequencing is not full M1 completion. Before dependent features can proceed, implement and test:

1. Real configurable project/model/cache/export paths and default export destination; owner-preserving reference/copy migration with verification, journal, interruption recovery and rollback.
2. Complete category occupancy and enforceable cache/proxy/thumbnail limits; preview-and-confirm cleanup restricted to verifiably safe owned outputs, without external model deletion.
3. Task-sized disk admission/reservation and actual running-job low-space pause/resume semantics. Current import preflight/reserve/507 handling is insufficient for long-running generation/render jobs.
4. Applied, editable preset layouts/suggestions that preserve all modules, permissions and data and never execute implicitly.
5. Actual current browser/visual acceptance and exact final commit/tree, publication and separate hosted CI event/attempt receipts. Selected local regressions do not replace full applicable stage gates.

Full M1 remains **PARTIAL**. Historical `PARTIAL_CI_CAPACITY`, `39 PARTIAL + F00 INTEGRATED`, independent-review `BLOCKED`, and M12 `USER_APPROVAL_REQUIRED / LOCAL_REQUIRED / NOT_RUN` remain unchanged.

## 11. Final metadata-guard delta and bounded M1 closure

This addendum follows the 13:00 UTC checkpoint. Sections 1–10 remain historical
snapshots, including their failures, source identities and then-current pending
states. M1 is **PARTIAL**, not a full Storage Manager or completed independent
Studio product. There is no final published M1 SHA at this documentation cutoff.

### 11.1 Strict V2 version boundary and actual RED/GREEN evidence

`app/creative/workspace.py::IndependentWorkspaceService._row` now rejects a
record unless `type(version) is int` and `version >= 1`, raising
`CREATIVE_ASSET_VERSION_INVALID`. This prevents boolean, string, float, zero,
negative or missing counters from becoming authoritative V2 CAS versions. The
check is in the V2 adapter; the permissive legacy `AssetLibraryService` behavior
was not rewritten. No automatic metadata coercion, repair or owner mutation is
performed on read.

The new parametrized regression covers `True`, `False`, `0`, `-1`, `"1"`, `1.0`
and `None` under both File and PostgreSQL profiles. For each value it checks
single-asset read, original-byte download, asset listing and ASSET reference
catalog, requiring the exact error and unchanged original files.

| Actual receipt / UTC interval | Outcome and scope |
| --- | --- |
| [Corrupt-version RED](docs/delivery/v2-development/stage-m1-corrupt-version-red.json), [log](docs/delivery/v2-development/stage-m1-corrupt-version-red.log), 13:12:03–13:12:10 | **FAIL**, exit 1; **7 failed / 7 opposite-profile skipped / 150 deselected**. All seven active File variants failed because the adapter did not raise. The unchanged test source and failure remain preserved. |
| [Final guard File](docs/delivery/v2-development/stage-m1-version-guard-file.json), [log](docs/delivery/v2-development/stage-m1-version-guard-file.log), 13:12:57–13:13:50 | **PASS**, exit 0; **215 passed / 186 opposite-profile skipped**, 1 warning, pytest **49.15 s**. Seven selected files cover M1 core/API/relationships/storage/CI plus original asset library/lifecycle. |
| [Final guard PostgreSQL](docs/delivery/v2-development/stage-m1-version-guard-postgres.json), [log](docs/delivery/v2-development/stage-m1-version-guard-postgres.log), 13:12:58–13:14:17 | **PASS**, exit 0; **215 passed / 186 opposite-profile skipped**, 1 warning, pytest **74.36 s**. Same selected files, actual **PostgreSQL 17.11**, verified by its [own runtime probe](docs/delivery/v2-development/stage-m1-version-guard-postgres-postgres-runtime.json). |

All three original log SHA256 values were recomputed and matched their receipts;
all before/after source maps agree and `sources_changed_during_check:false`.
Both GREEN runs share 1,630 inputs, compact sorted-key map SHA256
`19a276bb73db11733cd0fba197dc127160e97c59687e26add405c61464ddd03b`.
Their baseline HEAD remains `0df2640c4c1a2d3052bb0a84d14445744d04046f`;
that HEAD is not the uncommitted tested implementation. At 13:17 UTC every
recorded source digest still matched the working tree. This is bounded source
verification, not a Git end identity or a full regression result.

Compared with the corrected frontend/build source map from §10, exactly two
recorded paths changed: `app/creative/workspace.py` and
`tests/test_v2_independent_workspace.py`. The larger original-owner regressions
and 1,773-test frontend PASS therefore remain **pre-final-guard evidence**. No
claim that those complete selections were rerun against the final guard is made.
The two final 215-test profile results may not be relabelled full backend coverage.

Matching PostgreSQL log:
`.runtime/v2-checks/stage-m1-version-guard-postgres/postgres.log`, SHA256
`fcec4dc5c50a48533f10001d1a835ed1f27833ab5bbec770d227e8cdbc110bcf`.
It records the fast shutdown request at **13:14:17.974 UTC**, shutdown checkpoint
completion at **13:14:17.979**, and **database system is shut down** at
**13:14:17.981**. This is the final guard run's own log, not an older shared or
owner-regression log.

### 11.2 Regenerated catalog and final inventory boundary

The [final catalog generation receipt](docs/delivery/v2-development/catalog-80d041f1ef1c.json)
is dated **13:13:14 UTC**, isolated staged tree
`80d041f1ef1cf040e7a7f395e62a917806ebebaa`. All four recorded output hashes were
checked against the current files and match. The current application source
fingerprint is
`a06abe220e300bad702981085001c7bd0259ba6d81a519bb3f855c1f8db56292`.
The mounted catalog remains **2,077 operations**, **34 additions / 0 removals**
relative to the M0 documentation baseline. This staged-tree receipt is not a
published end commit. The earlier 3-test catalog PASS is retained at its own
pre-guard fingerprint; regeneration alone is not a fresh test execution.

The subsequent [final catalog check](docs/delivery/v2-development/stage-m1-version-guard-api-catalog.json),
13:18:08–13:18:14 UTC, is **PASS: 3 passed**, exit 0, 3.61 s. The
[final coverage-infrastructure check](docs/delivery/v2-development/stage-m1-version-guard-coverage-infrastructure.json),
13:19:03–13:19:07 UTC, is **PASS: 174 passed**, exit 0, 4.16 s. Both original logs
were read and hashes recomputed; both have unchanged 1,630-input maps identical
to the final guard runs. These are catalog/infrastructure checks, not an additional
177 product-runtime or browser cases.

The actual [final independent collection](docs/delivery/v2-development/stage-m1-version-guard-collection-review.json)
at 13:17:57 UTC exited 0 with **9,823 nodes**, original **9,151** retained in order,
**672 additions** relative to the frozen baseline and unchanged historical skips.
The [explicit additive review](docs/delivery/v2-development/stage-m1-version-guard-manifest-review-decision.json)
identifies **14 additions since 9,809**, exactly seven File and seven PostgreSQL
corruption variants; prior published/working nodes stay ordered and the protected
test/gate diff from M0 is empty. Its note preserves an initial ad-hoc review-script
assertion using an incorrect node-name prefix, corrected after inspecting the
actual returned names; no product-test or coverage assertion changed.

The [written inventory receipt](docs/delivery/v2-development/stage-m1-version-guard-collection-written.json),
13:19:02 UTC, records `.github/ci/coverage_manifest_v2.json.gz` SHA256
`3e86bfabbdcb2c494968cf89d6efdd3ff2cc10edf921fa47f6a9669474dfce9f`,
independently matched to the actual file. The frozen baseline remains
`6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.
All collection receipts say **INVENTORY_ONLY / tests_executed:false**. The earlier
9,809 count and its older written hash remain historical; neither count establishes
full execution, skip-free coverage or independent-review approval.

### 11.3 Remaining acceptance and release boundary

Actual local M1 browser acceptance is **BLOCKED**; current-M1 hosted browser
execution is **NOT_RUN**. The prior [cloud browser launch log](docs/delivery/v2-development/cloud-v2-creative-browser-run.log)
records `process_singleton_posix.cc:297`, `socket() failed: Operation not permitted (1)`
and termination with `SIGABRT`. Its recomputed SHA256 is
`24782d6a3e3a8611e2b0f65031f0005eae1b6a381da3c8051651fbac3eac85ee`.
This is a preserved environment blocker from a prior cloud launch, **not a new
M1 browser attempt or a current-source test result**. No new local attempt was
made. No actual new M1 screenshot was inspected and no new visual/geometry PASS
is asserted. Image/video service roundtrips and
frontend units establish only their own levels of the minimum path.

Full storage migration with recovery, general cache cleanup/limits, complete path
configuration/occupancy, global reservation and running-job low-space pause/resume
remain missing or partial. Presets still only store preferences. Safe nondependent
M2/M3 contracts may proceed without making those gaps complete or exposing
operations that require their absent guarantees. No Windows user execution,
model inference, paid fallback, merge or release follows from this closure.

### 11.4 Exact M0 terminal outcomes, observed 13:17 UTC

The [persisted terminal record](docs/delivery/v2-development/m0-ci-terminal.json)
was read in full; SHA256
`1c16f301b30490ac50d3f11da7abd8b3993720d5b179b77d10588671e5398009`.
All five runs are completed original **attempt 1**, head
`0df2640c4c1a2d3052bb0a84d14445744d04046f`. This supersedes the pending statuses
in the earlier 12:43/12:49 observations for **M0 only**, retaining those snapshots.

| Event / exact run | Terminal result | Distinct job-level evidence |
| --- | --- | --- |
| [PR Cloud 37928446079](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928446079) | **CANCELLED** | File execution and frontend **CANCELLED**; both PG execution shards, original TCP, V2 browser and native contracts/package **SUCCESS**. Strict [File aggregate 113830882073](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928446079/job/113830882073) and [PG aggregate 113830882074](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928446079/job/113830882074) both **FAILURE**. Successful PG shard execution does not override a failed aggregate; terminal metadata alone does not establish its diagnostic cause. |
| [Push Cloud 37928438685](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928438685) | **FAILURE** | [V2 browser 113812940144](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928438685/job/113812940144) **FAILURE**; File, both PG shards, TCP, frontend, native contracts/package and both strict backend aggregates **SUCCESS**. Its live 6-pass/1-failure and geometry 8-pass evidence remain in §9.3. |
| [PR Local Interop 37928446071](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928446071) | **SUCCESS** | File, PG and Windows current-user pipe reference **SUCCESS**; pipe remains explicitly `MOCK_ONLY`. |
| [Push Local Interop 37928438655](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928438655) | **SUCCESS** | File, PG and Windows current-user pipe reference **SUCCESS**, separate from PR. |
| [Shared R123 37928446211](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37928446211) | **SUCCESS** | Intended original c6f2126 RED reproduction succeeded as evidence collection; independent historical review remains **BLOCKED**. |

The M0 push artifact remains **TRACE_ACCESS_BLOCKED (403)**; no alternate
retrieval or trace inspection occurred. There was no rerun or timeout change.
No combination of different event successes erases either Cloud conclusion.
These are M0 documentation-commit terminal results, not current M1 hosted proof;
user Windows/GPU/model acceptance remains unexecuted and separately gated.

Subsequently read [aggregate log excerpts](docs/delivery/v2-development/m0-ci-aggregate-log-excerpts.json),
observed **13:21 UTC**, narrow that terminal interpretation: both PR aggregate
inputs were `EXECUTION_RESULT: cancelled` and `TCP_RESULT: success`, so they
failed closed despite successful PG shard jobs. Both push aggregates logged
same-run/attempt TCP joins and reconciliation of **9,449 unique collected nodes
per profile**, File **6,190 passed / 3,259 skips**, PG **6,159 passed / 3,290 skips**,
and **2 original TCP tests passed**. These are **M0-source** execution counts,
not the new 9,823-node M1 inventory. Sharded coverage does not establish monolithic
PG interaction equivalence. The persisted source is explicitly excerpts, not
complete logs or locally downloaded artifacts; no new artifact was downloaded
for this review. Neither this backend success nor PR browser success removes
the push live-browser failure or the PR cancelled conclusion.
