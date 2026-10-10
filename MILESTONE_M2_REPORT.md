# M2 Creative Graph / Basic Canvas — M2-A Integration Report

**Status: M2 PARTIAL / bounded M2-A checkpoint. Latest evidence update: 2026-10-09 14:07 UTC.**

Current terminal evidence: integrated owner File **1,490 passed / 1,098 skipped**;
real PostgreSQL 17.11 **1,457 passed / 1,131 skipped**, normal shutdown;
full frontend **1,923 passed / 8 existing skips**;
TypeScript/Vite/token build **PASS**; complete CI infrastructure plus catalog
**279 passed**. Their source maps agree and were stable. Collection is **10,178
nodes, inventory only**. The written manifest and browser collection are now verified as inventory only;
all selected local integrated checks are now terminal. §7 records their receipts;
§4 preserves explicitly timed development evidence without substituting it for
the current results.

M2-A adds a bounded typed manual graph and local rule execution through the
original WorkflowRun host. It does not meet the full roadmap M2 gate: no graph
image generation/media conversion, JobManager/provider execution, general
multimodal adapters or full professional infinite-canvas experience is established.
Integrated File, frontend, build and infrastructure/catalog checks are now
verified as summarized above, including actual PostgreSQL. Current M2 hosted
and actual browser/visual acceptance remain unexecuted. These verified local checks do not make the missing
full-roadmap capabilities complete.

## 1. Identity and preserved boundaries

- Repository/branch: `1785235376-blip/AI-Novel-Studio`, `feature/v2-narrative-platform`;
  [Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47).
- Published M1 baseline HEAD: `57986cb13d452731baf82bbc242bfc79f9cfd145`, tree
  `7b06f7eb213893ec41e4ded14810b82b070b7dc7`. M1 remains **PARTIAL**; publication
  does not erase its storage/preset/browser gaps or first hosted failures.
- M2 implementation end SHA/tree: **UNCOMMITTED / NOT RECORDED**. Development
  receipts bind dirty source maps, not a hypothetical published M2 commit.
- Requirements re-read from the supplied roadmap: §§7.1–7.4, 8, M2 in §24 and
  §25. Its engineering order is not a required user novel-to-video pipeline.
- Original Project/Asset/WorkflowRun/Job/Model owners remain authoritative.
  Intent/preset is nonbinding; graph, Director and Tutor are optional. No model
  inference, paid fallback, user Windows execution, merge or release is asserted.
- The 325-row M0 inventory and historical `PARTIAL_CI_CAPACITY`,
  `39 PARTIAL + F00 INTEGRATED`, independent-review `BLOCKED` remain preserved.
  M12 remains **USER_APPROVAL_REQUIRED / LOCAL_REQUIRED / NOT_RUN**.

## 2. Implemented source slice

### 2.1 Closed typed definitions and independent graph persistence

`app/creative/graph_models.py` defines a closed registry of seven version-1 node
kinds: `text_input`, `text_reference`, `draft_prepare`, `manual_transform`,
`director_note`, `human_review`, `asset_reference`. Current port types are only
`TEXT`, `DIRECTOR_NOTES`, `DRAFT`, `ASSET_REF`. Strict schemas reject extra fields,
coerced revisions, unknown definitions/ports, duplicate IDs/edges, multiple edges
into a single-input port, type mismatch and cycles. Original
`V1CapabilityService._workflow_order` supplies DAG ordering. No user-supplied
plugin code, dynamic executable registration or arbitrary output submission exists.

`CreativeGraphService` in `app/creative/graph.py` reuses
`CreativeProjectStore`/original scoped persistence. New bounded collections are
`creative_graph_definitions_v2` and `creative_graph_runs_v2`. Graphs are
**actor-private within the exact project/scope/incarnation**. Same project access
does not expose another actor's graph. Creation supports a bounded request ID;
save uses current positive version/CAS and original history updates. Reads validate
stored schema/digests and recheck current owner/authority before returning data.

An empty graph can be saved independently, with no chapter, Director or model.
It cannot execute an empty selection. Required inputs may be incomplete while
authoring; preflight explains blockers before any run admission. Save never
creates a run automatically. There is no new project database or asset owner.

Actual byte bounds are decimal, not KiB:

| Bound | Current value / scope |
| --- | --- |
| Nodes / edges | 16 / 40 per graph |
| Definition / output | 96,000 serialized UTF-8 bytes per graph definition / 64,000 per typed output |
| Collection counts | 25 graphs / 100 runs per scope across its records, not unlimited per actor |
| History / serialized storage | 20 history entries per record; 2,000,000 bytes per record; 8,000,000 bytes across graph/run collections |
| Text / Director note | 8,000 characters / 4,000 characters |
| Position / zoom | Coordinates ±100,000; zoom 0.35–2.5 |

These are defensive finite bounds, not a large-graph performance benchmark or a
full Storage Manager quota/reservation/cleanup implementation.

### 2.2 Preflight, original WorkflowRun host and manual/local outputs

`graph_execution.py` projects selected target nodes plus their upstream dependency
closure onto `_ScopedOriginalWorkflowHost`, reusing original transitions for
advance, trigger, claim, completion, pause/resume, cancellation and human review.
The adapter is a trusted, closed local implementation through `run_trusted_local`:

- Text input/reference passes author-supplied text.
- `draft_prepare` uses existing `execute_local_recipe_node` to organize that text.
  This is rule-based preparation, not creative adaptation or model generation.
- `manual_transform` returns the author's explicitly supplied result.
- Optional Director note is carried as reference material; local rules do not
  claim to interpret it or synthesize different prose. Multiple notes can exist;
  compatible output fan-out is allowed. No mandatory Director is introduced.
- `human_review` requires current run CAS, node ID and exact output digest.
  Approve/reject routes require original `domain.review`, distinct from write.
  Review never writes original chapters/assets or grants permission to a provider.

Run creation binds actor, scope, incarnation, graph version/definition, selected
closure and the reviewed preflight digest. It persists **QUEUED**, then a separate
explicit execute action drives bounded local transitions; no background worker,
parallel scheduler, JobManager dispatch or external model/provider call is added.
Outputs are revalidated against their closed port schemas and original execution
receipt; source drift/corruption rejects continued adoption. Stale, failed,
rejected and cancelled results are redacted as implemented, with no automatic retry.

Run timeout is taken from the original `WorkflowRunIn` default, currently
**3,600 seconds**, established at admission; queue execution, pause/resume and
review do not reset the admission deadline. Trusted local node budget is
**5 seconds**. These are application runtime contracts, separate from unchanged
CI job/test budgets. Source currently exposes `timeout_seconds` and `deadline_at`;
frontend types, decoder and run panel include them and have the full-unit/build
receipts in §7; actual PostgreSQL is verified in §7.5. Browser execution remains open.

### 2.3 Deliberately narrow reviewed-result cache

Cache keys bind project incarnation, exact scope, actor, graph ID/version,
execution digest, adapter version, node definition/version/parameters and inputs.
Only a previous **SUCCEEDED**, reviewed run in the **same graph version** can
supply a matching, digest-verified local node output; the node must be an ancestor
covered by its successful review. A disconnected unreviewed branch is not made
reviewed by a different branch's approval. Human approval itself is never cached
or replayed: each new review node requires fresh exact-output approval.

This is `SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY`. It does not supply binary-media
cache, cross-version descendant-only invalidation, cross-actor reuse, provider
receipt reconciliation or automatic model retries. Any saved graph version change
makes an old run stale, even when only presentation metadata changed. It is more
conservative than the roadmap's eventual incremental execution cache.

### 2.4 External asset references are display-only

An `asset_reference` stores original asset ID/version/digest/kind, checks the
original fenced asset owner outside scope transactions and projects
`CURRENT / STALE / UNAVAILABLE`. Unavailable binding parameters are redacted and
the graph becomes read-only. Persisted external references cannot yet be removed
or rebound; moving/disabling their nodes does not delete the original assets.

This is a **read-only metadata binding**, not an original AssetLibrary parent,
provenance or dependency edge. Original soft-delete/restore remains owned by the
asset service; a graph reference may consequently become STALE/UNAVAILABLE. M1's
descriptive relationship/original parent-DAG deletion protection is unchanged and
is **not automatically extended to every graph reference**. No graph-aware strong
delete guard, cross-owner atomic input CAS, generated-asset lineage or Asset Save
publication is claimed in M2-A.

Selected execution closures containing an asset reference are blocked with
`CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED`. A disconnected reference
need not block a separate selected local-text component, but selecting the whole
enabled graph includes it. There is no safe atomic asset-input execution seam yet,
no image/video/audio transform and no graph Asset Save/Export/Timeline output
adapter. This boundary avoids nested original-asset/scoped-store locks and stale
external adoption. It must not be marketed as working image generation merely
because an image reference is visible on the canvas.

### 2.5 Exact routes and frontend consumer

`graph_api.py` is composed through the existing Studio invocation boundary in
`workspace_api.py`/`app/experimental/api.py`. The closed route surface includes
catalog/list/create/get/save, preflight, run list/create/get and six actions
execute/approve/reject/cancel/pause/resume, under existing `/api` and `/api/v1`
mounts. Read uses `domain.read`, mutation `domain.write`, review `domain.review`.
Exact method/path admission, server feature/V1 gates, session revocation,
incarnation and private-response/error checks remain required. No intent grants
access. The generated receipt in §7.1 measures the final mounted catalog delta.

`IndependentStudioWorkspace.tsx` now offers optional material/graph content in the
same shell. `studioGraphClient.ts` validates current owner/scope, fixed catalog,
strict IDs/versions, output/provenance and redacted states. `useStudioGraphEditor`
provides explicit create/save/reopen, inspector, typed port selection, conflict
review and in-memory undo/redo bounded to 50 snapshots. Original asset preview
uses the existing inspector rather than copying files.

`GraphCanvas.tsx` and `graphCanvasGeometry.ts` implement actual positioned nodes
and SVG edges, pointer drag, pan/zoom, marquee/multiselect, keyboard selection,
arrow movement, delete and Escape. Interrupted gestures cancel on blur, lost
capture, source/owner change or readonly/busy transitions. Changes are draft edits,
not implicit graph execution. Ports are selected via buttons/forms, not connected
by drag gestures. No MiniMap, grouping, copy/paste, template import/export,
autosaved persistent draft, large-graph virtualization or complete professional
Director Console/Tutor slot is established by this slice.

## 3. Requirement-to-current-code gaps

| Roadmap / baseline IDs | Current M2-A slice | Requirement still open |
| --- | --- | --- |
| §7.1; GRAPH-01 | One bounded graph contract and Studio consumer over original WorkflowRun host. | Shared multimodal adapters and ordinary/professional views of the same executable graph remain partial; a material/graph toggle is not complete dual-mode authoring. |
| §7.2; GRAPH-02/03/07 | Positioned nodes, pan/zoom, marquee, keyboard movement, typed port validation and form-based connection. | Drag-to-connect/highlight/converter suggestions, native-browser/a11y/geometry proof and fuller error focus/navigation. |
| §7.2; GRAPH-04/05/06/09 | In-memory undo/redo, explicit node/edge deletion with original-asset protection. | Command search, graph copy/paste, groups/notes/collapse/MiniMap/alignment, templates and impact preview. |
| §7.2; GRAPH-08 | Explicit persisted graph CAS save/reopen and visible unsaved/conflict state. | Persistent draft autosave and crash/reload/disconnect recovery. In-memory draft preservation and before-unload warning do not guarantee recovery after reload. |
| §7.2; GRAPH-10 | Defensive 16-node/40-edge bounds. | Large-graph virtualization/LOD and measured performance; a finite cap is not performance acceptance. |
| §7.3; GRAPH-11/12/14/15 | Text, Director-note, draft and display-only asset ports; local rules/manual output. | Image/video/audio/3D/camera/pose/depth/model/timeline type contracts and real processing/output adapters. |
| §7.3; GRAPH-13/16; §8 | Optional note node, local execution without Director, exact human review. | Professional Director Console, workflow proposals, controls/budget/conditions and disconnected Tutor placeholder. |
| §7.4; GRAPH-17/18/19 | Selected closure preflight and sequential original-host execution with zero external calls. | JobManager/Model capability admission, meaningful provider cost/privacy/resources, bounded concurrency, VRAM queue/unload and long-running storage reservation/pause. |
| §7.4; GRAPH-20/21/22 | Same-version reviewed local cache, explicit pause/resume/cancel, node states and original deadline. | Cross-version descendant invalidation, binary cache/cleanup, actual provider cancellation/accounting, explicit safe retry and complete progress/resource UI. |
| §24 GATE-M2 | A useful independent empty/manual graph foundation. | **PARTIAL**: full gate's independent image generation/material conversion cannot run through these nodes; asset-version display invalidation is not executable source replacement. Final integrated tests/browser and missing adapters remain required. |

M1 storage migration, cache cleanup/limits, global reservation and running-job
low-space pause gaps remain blockers for dependent graph/media operations.
Graph metadata limits do not silently implement those missing semantics.

## 4. Development receipts actually read — historical 13:50 UTC snapshot

All linked original logs were read and SHA256 recomputed against their JSON
receipts. These separate runs are not summed into a final product test count.
Only the stated before/after source stability applies; HEAD alone identifies the
published M1 baseline, not the uncommitted graph implementation.

| Receipt / UTC interval | Actual result | Evidence boundary |
| --- | --- | --- |
| [Initial schema contracts](docs/delivery/v2-development/dev-m2-graph-contracts-first.json), 13:34:49–13:34:54 | **PASS**, 213 passed, 3.15 s; source-stable | Strict-contract development subset. |
| [First File invocation](docs/delivery/v2-development/dev-m2-graph-file-first.json), 13:37:14 | **FAIL**, exit 1; selected interpreter had `No module named pytest` | No product test executed; original failure retained. |
| [Corrected File invocation](docs/delivery/v2-development/dev-m2-graph-file-corrected.json), 13:37:32–13:37:39 | **PASS**, 21 passed / 21 deselected, 4.85 s; source-stable | Prepared project interpreter; File persistence/execution only. Deselection is not PostgreSQL execution. |
| [File hardening](docs/delivery/v2-development/dev-m2-graph-file-hardening.json), 13:40:41–13:40:50 | **PASS execution**, 241 passed / 28 deselected, 5.69 s; **source drift recorded** | `sources_changed_during_check:true`, input map 1,654→1,655. Preserve result as development evidence; no source-stable final claim. |
| [Original-deadline File](docs/delivery/v2-development/dev-m2-original-deadline-file.json), 13:48:30–13:48:39 | **PASS**, 257 passed / 44 PostgreSQL variants deselected, 5.78 s; source-stable | Contracts/persistence/local execution timing subset; no PG execution in this run. Later actual PG result is in §7.5. |
| [First mounted API File](docs/delivery/v2-development/stage-m2-api-first-file.json), 13:36:06–13:36:16 | **PASS**, 16 passed / 16 opposite-profile skips, 7.62 s; source-stable | Predates additional review-permission and late-incarnation cases. Not final mounted API or PostgreSQL proof. |
| [M1 additive-media contracts](docs/delivery/v2-development/stage-m1-ci-additive-media-contracts.json), 13:42:20–13:42:38 | **PASS**, 121 passed, 16.11 s; source-stable | Separate CI/media prerequisite and unchanged TCP contract selection; not graph/browser execution. |

Focused frontend development counts (45 client, 25 canvas, 9 geometry) were
reported before final integration and are not used as a substitute for the now
verified **1,923-pass full frontend**, build and catalog/collection receipts in §7.
The table above preserves each earlier subset and its own source identity.
Actual PG is now verified in §7.5; hosted/browser evidence and real screenshot
review remain open; no screenshot was inspected.

## 5. New M1 hosted failures and additive correction remain separate

The [M1 compatibility correction record](docs/delivery/v2-development/M1_CI_MEDIA_COMPATIBILITY_FIX.md)
is the detailed evidence authority. Published M1 `57986cb` changed a protected
V2 browser job by adding FFmpeg setup; original TCP self-tests correctly failed
**101 passed / 1 failed** on both [push 37936615942](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37936615942)
and [PR 37936623135](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37936623135),
attempt 1. The actual TCP product command was **NOT_REACHED**. Earlier local 174
infrastructure tests had omitted this separate 102-case harness. No old assertion
or protected job hash is weakened to hide that gap.

The approved correction restores the old job and original live configuration
exactly, retaining its 7 original live cases and separate 8 geometry cases. A
visibly additive independent-media job/config owns the 5 new M1 cases and explicit
FFmpeg prerequisites; future M2 graph cases are additional inventory. The
[M1 collection migration](docs/delivery/v2-development/m1-media-inventory-migration.json)
records 12 = 7 + 5, exact union/no overlap, **collection only**. A successful new
job cannot substitute for the old one. Original budgets/retries/assertions and
old failures remain unchanged.

Separate M1 browser logs retain **8 live failures / 4 passes**, with geometry
**8 passes**. First new relationship journey timed out at 180 seconds; attempted
cleanup used a closed request context, leaving a confirmed synthetic project and
causing seven later original empty-server guards to fail. The first functional
timeout's cause remains unproven; readiness assertions and isolated `afterEach`
cleanup are fixture hardening, not an established diagnosis or browser success. No forced clicks,
sleeps, old assertion changes or rerun-to-green is represented as acceptance.

New artifact **11618169199** is explicitly
[TRACE_ACCESS_BLOCKED](docs/delivery/v2-development/m1-browser-artifact-access-blocked.json):
HTTP **403 scope_violation**, bytes not materialized, no alternative retrieval,
no trace/screenshot inspection. This is distinct from the earlier blocked M0
artifact. At this checkpoint Cloud CI remains pending with known nonpasses;
reported Interop/Shared successes do not repair TCP or browser failures. Exact
terminal metadata must be appended before claiming a whole event outcome.

## 6. Required next integrated acceptance

1. Retain the verified same-source File and real PostgreSQL results, their
   profile exclusions and matching server shutdown evidence. These 33-file
   selections do not replace current-revision full hosted backend coverage.
2. Verify the exact admission deadline through queued execution, review,
   pause/resume and corrupt timing metadata; prove the original timeout is never
   refreshed. Test current frontend deadline decoding/rendering against real API.
3. Retain the actual full frontend/build/token, catalog and reviewed additive
   inventory receipts in §7; bind publication to the final source without changing
   historical errors/drift. Any later source change requires a fresh receipt.
4. Execute real-browser independent empty graph → typed edits → save/reopen →
   no-Director local run → exact human review; invalid edges, selected closure,
   revoked scope, stale CAS, uncertain response, draft protection and interruption
   must remain visible. Inspect actual screenshots and keyboard/geometry before
   visual PASS. Current local Chromium limitation remains a blocker, not success.
5. Run old protected browser and additive media/graph jobs independently. Obtain
   exact event/run/attempt outcomes without discarding the M1 first failures or
   bypassing blocked artifact access.
6. Keep unimplemented adapters, full canvas/Tutor features and M1 storage
   dependencies explicitly partial/blocked. M2-A can be delivered as a bounded
   slice without claiming full GATE-M2 or authorizing M12.

## 7. Integrated checkpoint receipts — 2026-10-09 13:55 UTC

This addendum supersedes earlier pending statements only for its identified
terminal checks. Full M2 remains **PARTIAL**. The File and written inventory
updates appear in §§7.2–7.3 and actual PostgreSQL in §7.5. Hosted/browser
acceptance remains unexecuted and is not inferred from local successes.

| Actual terminal receipt / UTC interval | Outcome | Scope |
| --- | --- | --- |
| [API authority File](docs/delivery/v2-development/stage-m2-api-authority-file.json), 13:50:04–13:50:17 | **PASS**, exit 0; **20 passed / 20 opposite-profile skipped**, 9.16 s | Includes subsequent mounted review/late-incarnation cases. Earlier source snapshot; not PG execution. |
| [Full frontend](docs/delivery/v2-development/stage-m2-full-frontend.json), 13:52:25–13:53:38 | **PASS**, exit 0; **1,923 passed / 8 existing skips**, 256 passed / 2 skipped files | Full unit suite including new graph/canvas/run/deadline consumers. No actual browser or visual verdict. |
| [Build](docs/delivery/v2-development/stage-m2-build.json), 13:52:27–13:53:18 | **PASS**, exit 0; TypeScript, Vite **2,021 modules**, token guard **43 files** | Existing chunk warnings retained: App **886.52 kB**, ExperimentalWorkbench **628.01 kB**. No baseline refresh or warning suppression. |
| [Complete infrastructure and catalog](docs/delivery/v2-development/stage-m2-complete-infrastructure-catalog.json), 13:52:29–13:53:00 | **PASS**, exit 0; **279 passed**, 25.40 s | **276 CI infrastructure** cases, including the previously omitted unchanged **102 TCP** tests, plus **3 catalog** checks. This is not 279 product/browser tests. |

All four receipt log hashes were independently recomputed and match; before/after
maps agree and all report `sources_changed_during_check:false`. Full frontend,
build and complete infrastructure/catalog share **1,660 inputs**, compact
sorted-key map SHA256
`b9027a7bd48ed71eb7d733d0c91e894601046682e0a0972898641bf391b8f4bc`.
The API-authority run has its own earlier map
`0f748364b70682c7f9f53c4dd439f244a123708f2ffd31137825f46e31371641`.
All reference M1 baseline HEAD `57986cb13d452731baf82bbc242bfc79f9cfd145`, not a
published M2 end commit. Tests changing in later source require fresh binding.

### 7.1 Actual catalog and collection, with distinct baselines

The [catalog-generation receipt](docs/delivery/v2-development/catalog-71e64caab517.json),
13:51:21 UTC, binds isolated staged tree
`71e64caab5176d08ce959a0200753a82b0ff1f85`; all four catalog output hashes match.
Application source fingerprint is
`320dfff4a919037b544a3662d719001f4e145545925600870993e972be4d9944`.
Direct comparison with the M1 catalog gives **2,107 current operations, +30 / −0**:
15 logical graph operations under both mounted API prefixes. This is distinct
from the catalog's cumulative older starting baseline and not a published SHA.

The [independent collection review](docs/delivery/v2-development/stage-m2-collection-review.json),
13:54:15 UTC, exited 0 with **10,178 collected nodes**, **9,151 original baseline
nodes preserved in order**, **1,027 additions** relative to that frozen baseline,
and unchanged historical skips. Frozen manifest SHA256 remains
`6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.
It explicitly says **INVENTORY_ONLY / tests_executed:false**. The later actual
additive review/written-manifest receipt and verified hash are in §7.3; neither
collection establishes full execution or reopens historical independent review.

### 7.2 Integrated original-owner File terminal receipt — 13:59 UTC observation

[Integrated owner File](docs/delivery/v2-development/stage-m2-integrated-owner-file.json),
**13:52:22–13:57:27 UTC**, is **PASS**, exit 0: **1,490 passed / 1,098 skipped**,
1 existing warning, pytest **299.01 seconds**. The exact command selects 33 files
covering original assets/media/lineage, project/shared authority, existing workflow
and declarative execution/job boundaries, M1 contracts, M2 graphs and the additive
media prerequisite contracts. It is a broad selected regression, **not all 10,178
collected backend nodes** and not a browser execution.

The original log hash was independently recomputed and matches
`4c4342cb2589671f7653768c5a534ba2bb468d7387b27d38b279cfc460b1c2d9`.
Its before/after 1,660-input maps agree, `sources_changed_during_check:false`, and
match the full frontend/build/279-check map in §7 exactly. Baseline HEAD is still
M1 `57986cb`; no M2 end SHA is inferred. PostgreSQL was pending at this
13:59 observation and subsequently completed with its own result and controlled
shutdown in §7.5; File does not substitute for that separate evidence.

### 7.3 Final written inventory and actual browser collection, 14:01 UTC

The [explicit additive manifest review](docs/delivery/v2-development/stage-m2-manifest-change-review.json)
at 13:59:54 UTC compares published M1 **9,823** nodes to **10,178**, **355 added**:
40 mounted API, 213 schema, 66 graph execution, 22 graph persistence, 2 independent
media-job and 12 media-prerequisite cases. It preserves prior node order,
historical skips and external gates. Review describes the allowed new-M1 fixture
changes separately from unchanged protected legacy tests/assertions/CI self-tests.
It is **not full-suite execution or historical independent-review approval**.

The [written manifest receipt](docs/delivery/v2-development/stage-m2-manifest-written.json),
14:00:19 UTC, independently recollected **10,178 nodes**, zero collection errors,
original 9,151 frozen nodes in order, historical skips unchanged, and
`tests_executed:false`. The actual `.github/ci/coverage_manifest_v2.json.gz` digest
was recomputed and matches
`acefe60873bd452ff663b254cb4c25a910c99dcb140732171105b7ba0b687d62`.
The frozen manifest digest remains
`6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.
The prior **1,027 additions** is measured from 9,151; the **355** is measured
from M1 9,823. They must not be conflated or labelled executed totals.

[Actual Playwright collection](docs/delivery/v2-development/m2-browser-inventory-review.json),
14:00:44 UTC, records **7 original live + 8 independent live** cases, the latter
**5 moved M1 + 3 new M2**. All prior 12 cases and original order are retained,
with no overlap between jobs. The three graph cases are the real independent
save/reopen/local-review journey plus default-off and V1 acceptance gating.
Receipt hashes for both list outputs and both configs were independently matched.
The original config retains SHA256
`dbbf62ee540feed65c69e7cd1a16d732220c240b0b016b868de24e91bfc14a36`.
This is **INVENTORY_ONLY / browser_launched:false**, not 15 passed browser tests.
Existing eight mocked/geometry cases remain their separate protected suite.

### 7.4 First relationship timeout: bounded diagnostic limits

Further read-only inspection does not establish a first-timeout cause. The M1
PNG fixture was structurally inspected as 79 bytes, 16×16 RGB8, valid CRCs and
784 decompressed scanline bytes with filter 0 and no trailing bytes; its independently recomputed
SHA256 is `bbf50397081aaa4ba4380df594df76605d8d9be77ebeec568dcee20ed8c9362c`.
That initial step was **byte/structure inspection only**; the later actual
cloud-decoder receipt is recorded below. Neither step is browser execution. The lineage response predicate matches the route; forms begin clean
and the original inspector-ID readiness helper follows list refresh. The logs do
not identify the first stalled wait or HTTP failure. Generic readiness is therefore
**not an established root cause**; no stronger causal claim is made. Existing
readiness/cleanup changes remain fixture hardening pending real execution.
**TRACE_ACCESS_BLOCKED** is unchanged.

The [reporter-restoration record](docs/delivery/v2-development/m2-inventory-reporter-restoration.json)
retains a collection side effect: Playwright `--list` wrote the configured old
`cloud-v2-creative-browser/junit.xml` and `results.json` reporter paths. Both were
restored from published HEAD. A separate read-only check confirmed each current
file is **byte-identical to HEAD** and matches its recorded original digest;
M2 inventory remains in dedicated new files. No browser launched and no historical
result was replaced by the collection output.

A later [actual cloud decoder receipt](docs/delivery/v2-development/stage-m1-relationship-png-decoder.json),
**14:03:54 UTC**, now verifies that the existing `app.media_files.inspect_image`
path decodes those exact bytes as **16×16 image/png, validation DECODED**, exit 0.
Its [original log](docs/delivery/v2-development/stage-m1-relationship-png-decoder.log)
SHA256 and unchanged-source map were checked. This establishes current-cloud
FFprobe/FFmpeg decoding, so structural corruption is not supported by this
fixture evidence. It is still **not hosted browser or Windows execution**, does
not identify the blocked first wait, and does not establish the M1 timeout cause
or a successful end-to-end journey.

### 7.5 Integrated PostgreSQL and final local checkpoint, 14:07 UTC

[Integrated owner PostgreSQL](docs/delivery/v2-development/stage-m2-integrated-owner-postgres.json),
**13:52:24–14:06:21 UTC**, is **PASS**, exit 0: **1,457 passed / 1,131 skipped**,
1 existing warning, pytest **830.19 seconds**. It runs the same 33 selected files
as File, against actual disposable PostgreSQL **17.11**, established by the
[SQL runtime probe](docs/delivery/v2-development/stage-m2-integrated-owner-postgres-postgres-runtime.json).
The original log hash was recomputed and matches
`2e259eda2f24b3c89cb3739014da7c58a4d8c4f02a32f7b39372fe0f5e360f0d`.
Before/after maps agree with `sources_changed_during_check:false` and exactly
match the 1,660-input map shared by File, full frontend, build and 279-check
infrastructure/catalog execution. The profiles remain separate; neither skips
nor the union is relabelled full 10,178-node backend execution.

The matching server log
`.runtime/v2-checks/stage-m2-integrated-owner-postgres/postgres.log` was inspected;
SHA256 `5c8ef3118eace32ff59da078fc62249318109a09cae84c2d682278d14d706f4a`.
It records fast shutdown request **14:06:22.085 UTC**, completed shutdown
checkpoint **14:06:22.093**, and **database system is shut down** at
**14:06:22.097**. No earlier server log is substituted for this run.

**Final local checkpoint:** File **1,490/1,098 skips**, PG **1,457/1,131 skips**,
frontend **1,923/8 existing skips**, TypeScript/Vite/43-file token **PASS**,
infrastructure/catalog **279 PASS**, catalog **2,107 operations (+30/−0)**,
reviewed/written backend inventory **10,178 nodes**, browser inventory **7 original
+ 8 independent**, all with the evidence-level limitations above. No local
browser launched; no new screenshot/geometry was approved. Full M2 remains
**PARTIAL** because its missing adapters/canvas/Tutor/storage-dependent requirements
are not completed by successful bounded tests.

At this freeze, M1 hosted runs still have pending PG jobs alongside the known
TCP/browser failures. Their exact eventual terminal metadata belongs in a
separate historical receipt; no terminal workflow conclusion is invented here.
Current M2 hosted execution is **NOT_RUN** until publication and actual jobs.
The checkpoint's final SHA is intentionally not self-referenced: source/tree-bound
receipts accompany the commit and [PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47)
will bind the actual published SHA afterward. No Windows/M12, merge or release
is authorized by this checkpoint.
# M1 terminal CI supplement — 2026-10-09 14:16 UTC

The preceding M1 runs have now ended naturally. The exact event/run/attempt,
job timings, per-shard execution counts, strict aggregate failures and preserved
log digests are in [m1-ci-terminal.json](docs/delivery/v2-development/m1-ci-terminal.json).
No running test was interrupted or rerun for publication.

- Push Cloud `37936615942`: **FAIL**. File execution: 6,378 passed / 3,445 skipped.
  PostgreSQL shard 0: 3,199 passed / 1,709 skipped; shard 1: 3,148 passed /
  1,767 skipped. Both backend aggregates rejected the failed TCP prerequisite.
- PR Cloud `37936623135`: **FAIL**. File was cancelled at its original 20-minute
  job budget, without a complete result. PostgreSQL shard 0 and shard 1 completed
  with the same respective counts; both aggregates rejected the cancelled
  execution matrix and failed TCP prerequisite. Push File success does not
  replace PR File cancellation.
- Both events retain the 101-pass/1-fail TCP self-test result and 8-fail/4-pass
  live-browser result. Actual TCP product cases were not reached. Separate
  geometry checks passed 8 each. The first browser timeout remains unconfirmed.
- Interop push `37936615943` and PR `37936623050`, Shared R1/R2/R3 PR
  `37936623058`, both frontend jobs and both pairs of Windows native/package
  jobs succeeded. Windows user acceptance remains LOCAL_REQUIRED / NOT_RUN.

These are M1-source results, not M2 execution proof. M2 local results remain bound
to the unchanged 1,660-input map above; M2 hosted/browser execution awaits its
own published revision. Both old and additive browser jobs must pass independently.
