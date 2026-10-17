# Studio V2 continuation checkpoint — 2026-10-17

## Director conflict comparison (18:27 UTC)

The original Director Console now displays a paginated read-only comparison of local author input and the explicitly inspected server candidate before discard/adoption. It compares title/source settings, visual targets, scene order/content/dialogue, director notes and authored evidence through an explicit field allowlist. Unknown metadata is excluded; long excerpts are bounded and rendered as escaped text. No merge, save, authority change or unknown-request resolution is inferred from equality. The existing discard consent and source/CAS owner remain unchanged.

Focused director-draft-comparison-r1:5 new checks plus12 original console regressions and TypeScript PASS. This also type-checks the final storyboard timing allocator. Full suite/build/browser/inventory remain deferred.

## Storyboard pacing tools (18:24 UTC)

Original CreativeCanvas now supports per-scene/all-shot duration previews, uniform duration and exact-total weighted allocation, explicit local apply and one-step undo. Integer seconds stay within the original 1–600 limits; saturated shares redistribute, ties use authored order, and an unchanged total preserves existing durations. Shot IDs/order, continuity, director links, media and timeline stay untouched. Existing Save remains the sole persistence owner; source/draft/busy/scene changes retire pending actions and undo.

Final targeted receipt storyboard-timing-focused-r3:17 PASS. Prior r2:16 PASS and TypeScript PASS; r3 refined bounded allocation and its tests, with broader type/build verification deferred to the next consolidated check. r1 failed only because the new test used the wrong existing Save button label; corrected test selector, preserved runtime and failed evidence. No live browser or backend persistence claim for this new authoring increment.

## Canvas dependency inspection (18:20 UTC)

Added an upstream/downstream inspector directly to the original GraphCanvas. It traverses existing authored edges, shows shortest hop distance and exact port connections, supports direct-only filtering and paginated results, includes disabled nodes, and selects existing nodes without rewriting the graph or invoking execution. Iterative traversal handles cycles/dangling edges and a 5,000-node synthetic chain without recursion. Owner/draft/selection/busy changes retire old selection callbacks. This is authored-graph inspection, not an execution authorization or runtime impact guarantee.

Focused r1: nine new checks plus two original node-navigation checks and TypeScript PASS. Final r2: ten targeted checks including the actual read-only GraphCanvas mount PASS. Original save owner was not invoked by read-only dependency selection. Browser/full suite/build and canonical inventory reconciliation remain deferred.

## Subtitle literal find/replace (18:17 UTC)

Added local subtitle text find/replace with full before/after preview, explicit consent, bounded literal Unicode replacement, and one-step local undo. Existing timing, speaker/media bindings and historical restoration provenance remain; persistence uses the existing Save and CAS owner. Source/authority/draft changes retire stale actions, and unfinished split inputs pause replacement. No new network action or backend owner.

Focused receipt caption-text-replace-focused-r1: 14 new checks plus 31 existing offset regressions, and TypeScript PASS. Final receipt r2: 15 focused checks and TypeScript PASS after ensuring unchanged IME/no-op input still rerenders revision controls. No full suite, production rebuild, browser acceptance or source-inventory refresh was claimed; deferred to consolidated testing per user direction.

## Feature-first cadence and multiple source references (18:07 UTC)

User explicitly prioritizes completing functionality before consolidated full testing. Retain focused checks and critical safety/save regressions; defer repeated broad suites, packaging and coverage source refresh. Current fully reconciled inventory is c03b369, not proof of later source hashes.

The planning-source fork now optionally updates all older same-source references after listing their versions and explicit renewed consent. Current/unrelated references stay unchanged; no automatic write/run. A true retained-consent RED was fixed using synchronous live consent/preview fences. Focused42 UI checks plus TypeScript pass; raw receipts graph-planning-fork-consent-red-r1, consent-green-r1 and multiple-focused-r1 retain chronology. Full regression and production rebuild are deferred, not passed.

## Explicit updated-source Graph fork (17:49 UTC)

Source3c977f1 adds inspected-version consent for a STALE Director/Storyboard node, preparing a separate unsaved graph with only that pin updated. Original graph/history and other author content remain unchanged; original Save/create and UNKNOWN behavior retain ownership.450UI checks, TS/build/token and separate real File/PG full-process fork/restart checks pass on identical final sources.32new tests, no backend/original-test changes. Four prior backend packages reread, not rebuilt. Read CANVAS_PLANNING_SOURCE_FORK.md and delivery/v2-development/graph-planning-fork-20261017/README.md. Coverage source inventory reconciled: all 17,647 backend rows unchanged, 2,730 source entries; exactly two existing runtime changes and four additions. Three equal collections and45original CI self-tests pass; see delivery/v2-development/graph-planning-fork-inventory-20261017/README.md.

## Real PostgreSQL full-process persistence (17:30 UTC)

The original PostgreSQL wrapper and full app lifecycle passed the same manual Director → Graph save → complete app restart → exact readback → stale-source flow. Fresh database v2_director_native_app_20261017_r1,20original migrations, original bootstrap/branch authority, no injected service/mock. Both app PIDs and PG stopped. Actual PG app correctly withholds independent model-review advertisement; that lifecycle remains File-only. See delivery/v2-development/director-full-process-postgres-20261017-r1/README.md.

## Original full-process persistence (17:28 UTC)

Native Linux source-run app in packaged-trust mode completed actual startup → original one-shot bootstrap → branch-scoped manual Director/Graph save → full process shutdown/restart → fresh-session exact readback → stale source labeling. No service rebinding, development registry or response mocks; no model requested. Both owned processes stopped and original-runner source hashes stayed exact. See delivery/v2-development/director-full-process-20261017-r3/README.md. This is not browser, Windows installer or live-model acceptance.

## Native Director → Graph persistence (17:20 UTC)

Four native HTTP cases across both app prefixes now cover exact reviewed-DRAFT pin → Graph create/Save/CAS → fresh-owner reopen, optional explicit planning run and stale-source labels without repinning or a second model call. Final related scope58 PASS /5PGdeselected; forcedTS/build/token PASS. Runtime/UI sources unchanged from29df291; no browser/live-model or full release claim. See delivery/v2-development/director-application-graph-20261017/README.md. Canonical inventory: 17,647 rows / 2,726 sources; four File cases added, all prior rows and source bytes preserved; three exact collections and45CIselftests PASS.

## Application host closure (17:05 UTC)

Source 29df291 explicitly mounts original versioned Director adapters. Scoped final gates: 556 File, 235 real PostgreSQL, 399 frontend, TS/build/token and 87 PUBLIC checks pass with identical final source snapshots. Two native TCP cases pass with fixture model responses; private pending review remains File-only. Browser/live model/full V2 acceptance remain open. Read DIRECTOR_APPLICATION_HOST_PROGRESS.md and delivery/v2-development/director-application-host-20261017/README.md. Coverage inventory refreshed: 17,643 rows / 2,725 source entries; all prior 17,617 rows retained, 24 File + 2 PG added; three identical collections and 45 CI self-tests pass. See delivery/v2-development/director-application-inventory-20261017/README.md.

User approved the fixed fourteen-commit archive through 4684577 at 17:03 UTC. Upload completed at b00b9aa3a94e6aace2bf14b62b7b3bfa7e3dbf52; eight files were read back from the remote and verified byte-for-byte. Later source/evidence is not part of that payload.

## Current inventory / recovery point (16:21 UTC)

Integrated V2 inventory: 17,617 rows, 2,723 source entries; SHA256 `cd2993426017f31058878d1d662e719479b131be17a0fc856cd7304313db735d`. Three original-generator raw collections match; all previous 17,505 complete rows and classifications remain exact, with 56 File + 56 PG cases added. 45 original CI self-tests passed. Read `delivery/v2-development/director-research-inventory-20261017/README.md`. This supersedes earlier inventory counts only, not the runtime acceptance boundaries.

Next substantive Director gap: the application host still does not mount the versioned independent model adapter by default; private pending storage remains File-only. Do not label that production end-to-end feature finished from constructor opt-in tests. Continue using original owners and actual host/session authority, and keep unsupported backends fail-closed. The fixed fourteen-commit archive request through 4684577 remains pending and unchanged.

## Integrated Research follow-up (16:15 UTC)

Historical exact-location inspection is integrated with existing Director and Audio owners at b7eddfc. Primary checks: 526 File, 233 real PostgreSQL, 399 UI, forced TypeScript/production build/token guard, and 87 original PUBLIC packaging checks passed. Four actual archives were read against current runtime source; before/after origin and all final gate source hashes match. Scope and limits: `delivery/v2-development/director-research-integration-20261017/README.md`. Inventory reconciliation is pending. This later work is outside the fixed fourteen-commit upload request.

## Native Creative follow-up (15:46 UTC)

227 original Creative / Graph / supported Director PostgreSQL cases passed (712 deselected), on a third fresh database with unchanged original tests and source hashes. Persistence, restart, deletion/recreation and authority scopes are covered; the separate private Director pending repository remains File-only. See `delivery/v2-development/creative-current-native-20261017/README.md`. This later evidence is excluded from the fixed pending upload candidate.

## Native Audio follow-up (15:42 UTC)

198 original PostgreSQL Audio cases passed (409 deselected) on a second fresh database, covering the original Audio modules and listing owner. Original tests and product code were unchanged; source hashes matched throughout and the owned server stopped. See `delivery/v2-development/audio-current-native-20261017/README.md`. This evidence remains outside the fixed pending fourteen-commit archive.

## Native P0 follow-up (15:34 UTC)

Without changing the code or original tests at 4684577, real PostgreSQL 17.11 passed 38 P0 retirement/incarnation tests and File passed 43. A new empty disposable database received the 20 original migrations; its exact live identity was checked and the owned server stopped successfully. Actual persisted authority/bindings, same-public-ID recreation, positive new users, create/link rollback and generation isolation were exercised. See `delivery/v2-development/p0-current-native-20261017/README.md`. This supersedes the earlier lack of fresh PG proof for this P0 scope only; it does not make the File-only Director pending lifecycle PG-capable or establish complete V2 acceptance.


## Latest Audio diagnostic closure (15:16 UTC)

Source fix `313051c`, evidence `25742db`: the five previously recorded Audio-listing diagnostic failures are resolved in their unchanged original tests. Matching-owner listing retains specific bounded shape/source errors while get/execution/review preserve hash-first admission. Valid-shape tampering still fails and stored bytes are unchanged. See `AUDIO_LISTING_DIAGNOSTIC_PRECEDENCE.md`; the historical unresolved Audio bullet below is superseded by this scoped result, not a globally green claim.

Verification scopes: 79 listing/integrity/MP3-compatibility checks, 231 contract/API checks, 117 CPU-media/Audio-API checks, fresh TypeScript/build/token checks and 87 PUBLIC package checks passed. PostgreSQL exclusions remain explicit in each receipt. Two actual wheels and two sdists match all current included source bytes. Frontend source remains equal to the preceding 332-test Director checkpoint; that UI test scope was reused, not rerun.

Canonical V2 is now 17,505 rows / 2,718 sources, SHA256 `80251092a5d769650dd2e2000625e2560ad1bdc776b54792898ca37d30419e4c`. Three raw collections match, with all prior 17,498 full rows/order/classes unchanged and seven new File-only rows. See `delivery/v2-development/audio-listing-inventory-20261017/README.md`. Collection is not execution.

All post-17c6500 work remains local. The approved archive through 17c6500 is verified remotely at de872b5; a later read found zero Actions runs for that archive commit, intentionally skipped and not a CI pass. No main or PR branch was changed.


## Latest serial Director continuation (14:55 UTC)

The earlier integrated baseline below remains historical. New work is on `work/dot-director-transport-20261017`, source `bcf2dbf` with its runtime evidence at `3e90ee6`; it has not been merged into the prior integration branch or PR branches.

Read `DIRECTOR_MODEL_TRANSPORT_PROGRESS.md` and `DIRECTOR_MODEL_CLIENT_PROGRESS.md` first. The original-owner versioned lifecycle, strict transport client, capability-gated original proposal-panel integration, uncertain-review preservation, exact adopted-DRAFT reopening and immutable Graph pin handoff are implemented candidates. Production application route activation is still off; actual browser, live-model and PostgreSQL acceptance remain open. The old transport-missing bullets below are superseded by those two detailed records, not by a full completion claim.

Latest frozen gates: 275 backend passed / 97 PostgreSQL-only deselected; 332 frontend tests across 24 files; forced TypeScript, production build and token checks passed; 87 PUBLIC packaging checks and actual readback of two wheels/two sdists passed. Browser startup is blocked in this cloud executor; separate-agent quota remains unavailable while direct serial work continues.

Canonical V2 inventory now has 17,498 rows and 2,717 source entries, SHA256 `330e3294dad5cde853c7068382e9fa2fa310969a7fc44a800cf3be1d6efb970e`. All prior 17,425 row dictionaries/order/classes remain exact; 73 new File-only rows were added. Three original-generator collections match. Forty-five original coverage/runner self-tests passed. This is inventory, not 17,498 passing tests. See `delivery/v2-development/director-model-inventory-20261017/README.md`.

The explicitly approved archive through `17c6500` was appended to the public archive branch at `de872b5` and all eight payload files were remotely read back byte-for-byte. Later client/panel commits and their four newer packages have not been uploaded under that fixed earlier approval. No main/PR merge, force push, Release or paid call occurred. Older source commits remain in their Git bundle, not direct archive branch history.

Completed owned test fixtures and disposable PUBLIC build copies were compacted into verified recoverable local archives. Original code, Git history, raw logs, package archives and checksums remain preserved.


## Status and scope

This is an additive progress record, not a replacement for frozen product decisions or historical acceptance reports. The original A/B/U feature matrix must not be promoted wholesale to COMPLETE from these slices. Public release remains unaccepted.

Local development branch: `work/dot-v2-integration-wave3-20261017`.

Latest integrated source checkpoint: `f4a6fed15cc52c0323e73f5e410e184c42bb5200`.
Its supplemental evidence is committed at `4d6bbe985994c7a679d17bfddd600658a358bc76`.
Inventory and all original-runner origin receipts are committed at `11b3f022dc0561f093bf6a93599066c08009e442`.
No remote push, main merge, release or tag was performed.

Read-only remote verification at 2026-10-17 10:47 UTC found:

- main: `fed2404c8e30b44061b7139dced45b7f3301601c`
- Draft PR #47: `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3`
- Draft PR #48: `58bbaad11360330d51f49fc2bb78a955a26469f0`

Recheck remote refs before any later submission. Do not assume these remain current.

## Newly verified slices

| Slice | Source commit | Proven boundary |
| --- | --- | --- |
| Private durable Director pending review | `18df9d05bd6956ddb88b7fce2c4028ee6100f255` | Explicit fresh-authorized historical-result preparation, persisted parsed candidates, restart/review, original DIRECTOR DRAFT adoption. Existing live deadlines and public redaction preserved. |
| Caption timing-offset preview | `b5ab297c4f49a7743aa2dbf89af9781242e06687` | Exact bounded tick arithmetic, selected/all-cue preview, explicit local apply/undo, original Save/CAS and File restart/SRT/VTT paths. |
| Interactive node removal | `97b3cf3b8587855ce02458c5d5d9cfb0ae0825d2` | Explicit removal of a non-entry, unreferenced node, preserved original content/pins, original review/export and File restart. |
| Authored comic panel duplication | `e8219aa16db3492050364df019b1ac2b36ab46f8` | Explicit placement, fresh IDs, preserved references/crop/style, original history/save/review, actual no-text pixels and ZIP verification. |
| Reviewed Director canvas handoff | `a557889b473f0b2976369a0805115fcd02ee8a56` | Explicit original-owner pin verification and one-shot insertion through the existing Graph owner; ordinary Graph Save remains separate. No automatic edge, schema upgrade, or private transport activation. |

The existing rule-assisted SCREENPLAY → reviewed DRAFT → exact Graph pin → File restart loop was already implemented. Do not rebuild it or describe Graph persistence as missing.

The new additive `tests/test_wave3_pending_director_canvas_bridge.py` extends the proof to private durable pending review, human-edited DRAFT, saved position/viewport/presentation and actual reconstructed File owners. It checks unchanged Jobs/ledger, no Graph runs, and rejection of the original source Storyboard as a falsely derived downstream document.

## Acceptance evidence

- Combined backend at `db6487b5eab7340433426fefcb5499122ec3d881`: 1,799 passed, two genuine font-dependent skips, 697 PostgreSQL-marked cases excluded.
- Independent combined subset: 357 passed, one applicable font skip, 196 PostgreSQL-marked cases excluded; 366 UI tests across 15 files.
- Initial combined UI: 1,587 passed across 96 files; forced TypeScript, production build, token guard and 87 actual PUBLIC packaging tests passed. Two wheels and two sdists were inspected independently.
- After the frontend-only handoff merge: fresh combined UI passed 1,667 tests across 104 files, plus forced TypeScript, production build, token guard and origin/source checks.
- That supplement did not rerun backend or packaging tests. It verified 1,478 backend/Python/test-fixture/infrastructure paths byte-identical to the accepted backend checkpoint and rechecked the retained actual archive payloads, inventories and wheel RECORD hashes against current inputs.
- The handoff itself separately passed the same 169-test UI scope in primary and independent executions.

Counts describe their documented scopes and overlap; do not add them together or claim every repository test passed.

Evidence entry points:

- `delivery/v2-development/director-pending-20261017/report.md`
- `CAPTION_TIMING_OFFSET.md`
- `INTERACTIVE_REMOVAL_HANDOFF.md`
- `delivery/v2-development/comic-duplicate-primary-handoff/HANDOFF.md`
- `handoff/DIRECTOR_REVIEWED_CANVAS_HANDOFF.md`
- `delivery/v2-development/parallel-integration-wave3-20261017/complete-index.json`
- `delivery/v2-development/parallel-integration-wave3-canvas-supplement-20261017/complete-index.json`
- `delivery/v2-development/parallel-integration-wave3-inventory-20261017/README.md`

The new bridge initially expected APPROVED in the legacy public projection. The corrected test separately asserts public MODEL_UNAVAILABLE and persisted raw APPROVED. This preserved the original privacy contract; it was not a runtime fix. The failed receipt and a separate pre-Python launcher-path failure are retained.

## Inventory closure

The unchanged original collection tool collected 17,425 rows and 2,691 source entries. All 17,289 predecessor row dictionaries, ordering and classifications remain exact. The 136 added rows classify as 119 File and 17 PostgreSQL; collection is not test execution.

Canonical V2 SHA-256: `6a94abca1ad6fe835e1ad483774b1fbfb660b6e599a69a2b48533ee2141abb77`.
All three raw collections have SHA-256 `8489499d82e9ebeeeb6ae455dbd7ee7659f2a9ae56ef5b2b563f579d082984a3`.
Frozen V1 and protected existing sources, tests, fixtures, documents and PUBLIC packaging definition remain unchanged by reconciliation.

## Remaining limits and next core work

1. Independent Director model preview/dispatch/status/cancellation/pending-review/adoption still has no complete authorized public transport. Private File acceptance and the public rule/manual canvas handoff do not establish that end-to-end UI lifecycle.
2. Keep legacy private-marker/history redaction intact. Any next transport must use fresh Request-derived Host authority, current scope/incarnation/source/policy checks, strict allowlisted responses, explicit actions and original coordinator/proposal/Job owners. Status/reopen must never dispatch or restore execution authority.
3. Add safe same-owner cancellation and exact uncertain-review/adoption reconciliation before calling the public lifecycle complete. Do not expose raw private proposal records merely to obtain an APPROVED status.
4. Independent model binding currently supports the constrained independent STORYBOARD shape. Direct independent SCRIPT and lineage-bearing derived Storyboards need separate contract work; do not loosen ancestry validation implicitly.
5. The source Storyboard is an ancestor of its reviewed Director. It cannot automatically be the downstream Storyboard of a `director_plan` edge. Use a genuinely derived document through the original owner when that workflow is implemented.
6. PostgreSQL durability/locking, browser geometry and actual UI end-to-end behavior, Windows installation/upgrade, real model quality, cloud/provider behavior and target applications remain outside these gates.
7. Five prior Audio-listing diagnostic-precedence failures remain unresolved and excluded from passing combined scopes. Preserve immutable-body guards and original tests; do not call the repository globally green.
8. Rendered Unicode comic acceptance remains blocked by the unavailable original pinned font. No substitute font or mocked successful rendering was used.

Continue from verified commits and exact evidence, not old summaries. Preserve existing work and failed raw logs; do not reset worktrees or force-push. Resource expansion, paid calls and destructive cleanup are not implied by this checkpoint.
