# Post-Interop R4/R5 UX continuation

## Current source delivery

Draft [PR43](https://github.com/1785235376-blip/AI-Novel-Studio/pull/43) deepens the original owners across Waves0–5. It retains F00 INTEGRATED and39 PARTIAL; this is engineering continuation, not a release or complete real-model/native product acceptance. Current per-feature and UX journey evidence is in `POST_INTEROP_FEATURE_MATRIX.md/json` and `UX_ACCEPTANCE_MATRIX.md`; original requirement traceability is in `docs/delivery/post-interop-continuation/TASK_REGISTER.json`.

The source-specific staged receipts below were produced before publication. Exact final SHA/tree, commit/file list and terminal hosted results are supplied in the final PR43 verification receipt and user TXT/JSON delivery without changing the tested source afterward. A checkpoint’s pending or cancelled result is never promoted into a final pass. Read those exact-source receipts together with this implementation report.

## Wave 0: initial checkpoint, not completion

Actual implementation/analysis model: **gpt-6-astra**.
Repository: `1785235376-blip/AI-Novel-Studio`.
New branch: `work/post-interop-r4-r5-ux-continuation`.
Stacked base: `work/local-interop-desktop-prep` (PR42).
Starting SHA: `e58c72b04182cd374af092314386b90f8250a173`.
Starting tree: `af584605316fded96e36947cf96b15c1efd12c07`.

Live GitHub checks on 2026-10-06 at 15:02 UTC confirm all six historical PRs remain open Drafts, unmerged, with the following heads. All 25 branch tips were inspected; no newer directly related continuation was present.

| PR | Head | Base |
|---|---|---|
| 37 | `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0` | main |
| 38 | `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b` | PR37 branch |
| 39 | `c6f2126115b52e17839d48efea091dc21ec08c61` | PR38 branch |
| 40 | `2c5b4e2f43c50318d9c1eeea487f68c2d66f7b42` | PR39 branch |
| 41 | `bcd60afb96cc69bdfd81db619cb0121d8712f074` | PR40 branch |
| 42 | `e58c72b04182cd374af092314386b90f8250a173` | PR41 branch |

## Existing owners first

The inherited product has real bounded services and UI, not just schemas. This continuation checks and deepens those existing workflows. A separate current matrix preserves the historical F00 INTEGRATED +39 PARTIAL classifications. Final delivery must name actual completed journeys and remaining boundaries rather than relabel every capability DONE.

Wave1 prioritizes durable save/recovery, workspace and review recovery, scoped entity search, authoritative tasks, request context, selection CAS and local diagnostics. Wave2 continues creation intelligence; Wave3 model/research/vector boundaries; Wave4 media production; Wave5 extended creation, version-pinned sharing and declarative workflows. Each integrated wave gets its own commit and push.

## Invariants

- Frozen PR37–42 heads, old acceptance packages and historical matrices are not edited.
- PR40 project authority, SSE revocation and generation terminal/rejection semantics remain.
- PoemSeed Local Interop 1.0 is frozen. Original 37 shared files retain SHA-256 manifest `77c1f82f0aec0ef385d95cacf6fe04530b83fb62d2403bc7341cbe6bf19c858c`.
- Original project/manuscript/model/task/asset/permission owners remain unique.
- Experimental flags default OFF; server V1 acceptance mode forces OFF.
- Only additive schema changes, with migration/upgrade/rollback and File/PostgreSQL parity evidence. No real user data profile is used.
- No paid API, private credentials, local model/runtime installation, real manuscript, production service, release, merge or deployment. Official pinned development/test dependencies are permitted and used.
- Historical independent follow-up audit remains BLOCKED and is not restarted or replaced.

## Verification at this checkpoint

This commit contains baseline/current-delivery documentation only. No new runtime acceptance is claimed. The inherited PR42 baseline reports 6,799 collected backend cases, File one-process and PostgreSQL two deterministic shards; original assertions, skip provenance, bounded caps, separate TCP gate, Interop, frontend, browser and Windows checks must remain. New tests require an explicit reviewed inventory expansion. All applicable tests will run on the final source. Real local models/GPU/native Windows and third-party target acceptance remain NOT_RUN or LOCAL_REQUIRED.

## Retained immutable-baseline observation

The Wave0 [Shared R123 evidence run 37485233196](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37485233196) is **FAILURE**, not green. Its unchanged reproduction runs the old `c6f2126` source. The `/api` running-reject case returned REJECTED without cancellation, then reported in-memory/HTTP COMPLETED while the immediately read durable record was still REJECTED; `/api/v1` observed both COMPLETED. Both retained the old truncated output. The original script polls unlocked memory before reading persistence, exposing the already recorded pre-fix race. Official artifact 11422284134 was downloaded through the supported route and its ZIP SHA-256 `3fd66d8c3c10e57ea8062f388705406972c3336d82b889addd10729b47a8caed` verified. The original scripts, wrapper assertion, historical evidence and this failure remain unchanged, with no retry to obtain green. Final corrected-source memory/durable/SSE regression must be assessed separately; this is not an independent-audit restart or closure.

## Wave1 implementation checkpoint

The first runtime wave deepens existing save/recovery and workspace owners. It adds corruption-preserving local draft export, honest offline save behavior, real original-owner cancellation receipts, audio/video/review task projection, version-fenced original entity navigation and explicit local-AI error guidance. Exact original task IDs are retained; retries open the original domain UI and never dispatch a model automatically. Media-specific review target forwarding completes with Wave4. The optional scene author server path completes with Wave2.

Local evidence:20 new mounted File cases (20 marked PG counterparts await hosted execution),92 related backend regressions,167 focused UI cases and5 composition cases passed in overlapping suites. TypeScript and token checks passed for the integration workspace. These are focused checks, not final-source full acceptance. The strict complete inventory is expanded only after independent exact-staged-tree collections and review; all original nodes/skip maps/assertions stay. See `docs/delivery/post-interop-continuation/WAVE_1_UX.md` and JSON.

Wave1 isolated staged code tree `59f34b859221babea16c6c974dfe0ebb2554666d` independently passed TypeScript, the complete frontend unit suite (**1167 passed /8 inherited opt-in skips**) and20 new mounted File cases. Two separate full collections matched6839 ordered nodes, retaining all6799 original nodes in their original relative order and adding40 File/PG cases. No original backend test/source digest or skip map changed. The final wave commit additionally includes only the reviewed inventory/evidence update; hosted execution remains pending.

## Executor recovery and independent Wave3 checkpoint

At15:42UTC the cloud executor key changed and its filesystem reverted to an older snapshot. Published Wave0/Wave1 were preserved remotely; uncommitted later work and test environments were unavailable. The permitted recovery infrastructure commit `4d736c0d14bdcd12d0ad3cc7146553971654620b` changes only a read-only source-preservation workflow. [Official source recovery run37490550329](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37490550329) produced two bounded source-only artifacts. ZIP/part/bundle hashes and exact source/tree were checked; restored Git fsck and clean-tree checks passed. No private credentials, untracked notes or raw logs were bundled.

Uncommitted features were reconstructed from retained source/edit commands against the verified published checkout. Earlier local counts do not verify reconstructed bytes. Official pinned Python dependencies and the existing OFL font were restored through normal approved commands; no package network restriction was bypassed. Fresh Wave3 backend contracts passed276 cases with97 unchanged backend-profile skips. Its front-end and complete final-source CI must be rerun.

Wave3 is an independent ready slice published while the Wave2 opinion and Wave1 context/search refinements continue. It adds broker policy/consent constraints, truthful benchmark evidence/human review, durable Research history and citation repair, and an original-Model-Center-bound Ollama embedding adapter. The adapter's actual loopback HTTP test uses synthetic vectors: actual models, semantic quality and GPU acceptance remain NOT_RUN. Missing providers remain NOT_CONFIGURED; keyword lookup is never described as embedding search. Research remains separate from Canon. This checkpoint does not complete the overall task.

Fresh isolated Wave3 code tree `8a0f4952e61f40c2f52cb6f156f607a9d6c9298d` passed TypeScript and the complete frontend suite:1175 passed/8 inherited opt-in skips. Its three new backend suites passed29 cases with22 PG variants deselected. Two independent complete collections matched6890 nodes, preserving all6839 prior nodes and adding51. Original backend test digests and skip maps remain unchanged. This is new post-recovery evidence, not reuse of the unavailable old workspace. The wave commit adds the reviewed inventory/receipt; full final-source hosted verification remains pending.

## Wave2 and remaining core UX closure

The original simulator/graph/mind pipeline now uses chapter/scene ordering and separates knowledge, belief, intent and other mind claims. Style measurements are source-local, while optional local-model opinions use the original author/broker/job lifecycle and quoted evidence. Revision comparison pins original Version A/B history; imported declarations and executed model-derived interpretations have distinct provenance. Judge intentional decisions remain suppressed across unchanged exact evidence, with explicit reopen and original WriterRoom revision-task creation. No generated opinion writes Canon or manuscript.

The existing Context Inspector now supports original Chapter/Canon/StoryGraph/Research pointer-only add/pin/exclude/preview. Exact source/digest/actor/branch/privacy checks repeat at final dispatch and when reading persisted output after restart. Character-only mode cannot gain these author-only references. Global search adds original organization/rule/graph/asset/workflow definitions and accurate current-owner navigation; model tasks reopen their exact original analysis/comparison without replay.

Fresh focused creation:417 backend passes and4 task-link passes in overlapping scopes,71 React passes and successful type/build/token checks. U08 and structured-search suites are separate focused receipts, not an additive unique-test total. No pre-reset result verifies this source. A new negative review found disabled Research hid independent vector indexes; this checkpoint fixes only that typed source-flag case, keeping direct access and global authorization fail-closed, with fresh71 backend/5UI targeted passes. Other identified P2 fixes accompany their owning media/translation waves. Full final-source inherited/new File, PostgreSQL, browser and Windows CI remains required.

Fresh isolated staged code tree `04c0cd285757fb04d8917d95828421ad7a76c963` passed the complete frontend suite (**1222 passed /8 inherited opt-in skips**), TypeScript, and214 new/affected backend cases (198 PG cases deselected for hosted execution). Two independent complete collections matched7262 nodes, preserving all6890 preceding nodes and relative order and adding372. Existing skip maps remain unchanged; the only preceding test digest updated is this continuation’s workspace suite, which adds exact original model-owner cases without altering prior assertions. This commit also contains the reviewed inventory and this receipt; final-source full hosted execution remains pending.

## Wave4 media and production checkpoint

The existing Director, Cover/Storyboard, Asset Library/Lineage, Production Manifest, Audiobook, Voice Direction and OTIO owners gain scoped source selection, versioned briefs and typography, explicit shot-grammar review suggestions, measured-frame audio receipts and independent production assurance labels. Original queues retain cancellation and late-result fences; task links target current authorized media/audio records without dispatch. OTIO imports/exports disclose unsupported camera/action/dialogue/sound metadata and preserve separate timeline/source timing.

A fresh negative review found missing original cover characters could hide unrelated work. Both brief and generated-candidate read paths now classify only the exact recognized missing-character error as stale. Candidate lists, comparison and Inbox remain readable; stale generation/approval remain denied, unrelated candidate promotion works, and permission/configuration errors propagate. Independent review reproduced the original failure and verified the complete corrected flow. Existing cover revision preserves source identities, so a removed reference requires restoring that source or creating a fresh brief.

No model/media quality or third-party NLE acceptance is inferred from synthetic candidates and generated WAV fixtures. Measured segment boundaries do not imply ASR, word alignment or lip synchronization. Production traceability, current replay preflight, approximate reproduction, synthetic determinism and actual byte comparison remain separate claims. No SQL migration or new authority/flag framework is introduced. Full final-source hosted verification remains pending.

Fresh isolated Wave4 code tree `ac967d2a769b76c61bfb60ba01e12c0a2ca4ebc1` passed TypeScript, the complete frontend suite (**1231 passed /8 inherited opt-in skips**) and24 new File cases (20 PG variants deferred). Two independent complete collections matched7306 nodes, adding44 while preserving every prior node, source digest and skip map. The final checkpoint adds the reviewed inventory and engineering receipts. This is still a checkpoint, not final-source full acceptance.

## Wave5 extended creation checkpoint

Existing Translation Workspace adds exact accepted-segment memory, source/version-bound reuse, locked terms and original edition history/restore. Character/place/world terminology stays explicit; overlapping aliases wholly inside the preferred spelling do not create false drift. Literal terminology checks do not establish semantic omission detection or translation quality. Existing Comics/Webtoon retains its distinct panels, bubbles, vertical layout and scene references, adding image briefs and approved version-pinned appearance assets with export lineage.

Existing Interactive Story gains current-source history restore and archived-entity visibility fences. Shared Universe lives in the existing structured-forks owner: immutable selected original character/location/relationship and approved world-record snapshots, explicit target-work version pins/repin/release/history, drift disclosure and permission/privacy withholding. Source edits do not mutate another work. Existing Fork/Compare/Conflict/Human Merge remains structured-only; no automatic manuscript merge. WriterRoom remains asynchronous comments, assignments and proposals; Presence explicitly reports NOT_IMPLEMENTED and does not impersonate realtime editing.

The original Template Library gains declarative Novel/Genre/World/Agent/Story-Structure categories alongside existing ones, compatibility/version/permission manifests and explicit bounded instantiation. The original SDK keeps executable third-party extensions DENY_ALL and rejects unsupported capabilities/runtime schemas. No marketplace or production cloud service is introduced. These are original-owner application, storage and contract flows, not real translation/artwork/model/native-engine acceptance.

## Upgrade and rollback scope

No SQL migration or historical migration edit is introduced by this continuation. New metadata/collections use the existing File/PostgreSQL experimental store and original source owners. Old documents default absent optional fields; dedicated upgrade/restart cases exercise old scene-less graph/mind, revision/history, style and Judge records. History is append-only where the owner already supports it; restore creates a new current version after original source/permission/CAS checks. Before downgrade, export and preserve the existing store and source history; older strict schemas may reject new enum/grammar/template records, so do not silently rewrite history or open active new-form edits with an older executable. Real user V1 data and irreversible migrations were never used. Native upgrade/downgrade and real production datasets remain NOT_RUN.

### Task Center exact original model-result continuation

Original simulator, Judge, translation and declarative model jobs now expose an additive owner-navigation pointer while preserving their legacy source projection. Existing panels locate the authorized original job receipt and never replay it. Translation opens the exact edition/segment receipt read-only before an explicit segment switch, preserving dirty inputs. Absent or source-withheld receipts remain unavailable; bounded original translation lists may exclude older jobs beyond the latest 50 editions and 50 runs per edition. New backend/DOM coverage and an actual hosted Judge navigation/reload/no-replay journey accompany this change.

### Verification discipline and retained failures

All 37 frozen Interop files match the original manifest; 153 strict coverage-infrastructure self-tests pass freshly. No historical PR42 test file, original migration, CI timeout, skip map or assertion is edited. Backend inventory expansion retains every preceding node and relative order through two independent complete collections. PostgreSQL remains exactly two deterministic SHA-256 node-ID shards with independent union/source/outcome/JUnit/run/attempt proof; File remains one process plus its separate two-process TCP gate.

The d18e874 hosted checkpoint passed unit/build/token/geometry and several earlier browser groups, but the new U08 source-picker browser case failed while locating a native select with an exact label-text query. Later checkpoint supersession cancelled the run; the observed failure is retained and is not dismissed as cancellation. The correction uses the existing exact accessible combobox selector, preserving citation, exclusion, stale-source and zero-dispatch assertions and the original timeout. Only final-source hosted results can verify the corrected complete journey. Earlier partial/cancelled runs are not final acceptance.

Fresh isolated Wave5/core-task code tree `ba7265a3a4dcf0d411799974570979414df2d70d` passed TypeScript, design tokens, the complete frontend suite (**1259 passed /8 inherited opt-in skips**) and101 new File/pure backend cases (77 PG variants deferred). Two independent complete collections matched7484 nodes:178 added in this checkpoint and685 added since PR42, retaining every preceding node and relative order. No old source digest or skip map changed in this expansion. The U08 new-browser selector correction is independently collected and requires actual hosted execution. Full File/PostgreSQL/browser/native acceptance is recorded separately after actual execution, not inferred from this staged subset.

## Retained hosted-browser correction checkpoint

The superseded Wave4 PR run37498190450 recorded seven completed R4 failures before later cancellation. Its official compact archive11429826185 was independently downloaded and SHA-256 verified; these are genuine observed failures, not cancellation-only noise. Beyond the U08 selector fix already included in c12f9b6, new fixtures assumed the File creation response contained a version and that submitted plain text was the saved Markdown. They now read the original GET baseline, calculate Unicode selection offsets against that exact text, and preserve full source equality instead of trimming whitespace. The new asset fixture now supplies the required original project query; wrong-project denial is asserted. A matching new task-reopen assumption was repaired preventatively from the established API contract.

The only application change is restoring the original production determinism label expected by an unchanged inherited browser test, while retaining the separate synthetic-only explanation. Two new mounted regressions add8 File/PG cases, and two React cases guard the old label and truth boundary. Exact staged correction tree `ef025078c13034916a696380398ce7606e71be7b` passed1261 frontend cases/8 inherited opt-in skips, TypeScript/tokens and57 affected backend cases/44 PG deselected. Two complete collections match7492 nodes, retaining all preceding nodes/order/skips; only two continuation-owned test files gain cases. No old assertion, test timeout, database/API behavior or original permission guard is weakened. Actual corrected browser and final-source full CI still require hosted terminal evidence. See `BROWSER_CORRECTION_RECEIPT.json`.

The [mounted API catalog](docs/delivery/post-interop-continuation/API_CATALOG.md) compares real registered schemas and source against PR42:56 added logical operations with both aliases (112 method/path entries), zero removals, and73 existing source/schema-affected operations. Schema inspection is not endpoint execution or a security/creative-quality acceptance claim; actual flags and original authority remain binding.

The complete c12f9b6 R4 runs were terminal failures, not cancelled: each recorded49 passed,10 failure elements and4 error elements across63 cases. U08 passed after its selector correction. Two further new Wave5 fixtures waited for the backend origin while the actual UI posted through its frontend proxy; the uncaptured owned project then appeared in inherited clean-store checks. The corrected helper matches the exact POST path and owned title, records the returned ID before later assertions, settles response capture after a failed click and quiesces before deleting only owned IDs. Original inherited isolation assertions remain unchanged.

The c12f9b6 hosted File run executed5107 passed/2377 skips and both TCP cases, but its strict coverage guard correctly rejected29 noncanonical opposite-profile skip reasons. The new tests had reused an old fixture’s early missing-DSN skipif. A continuation-only marked wrapper now delegates that unchanged original rig body while allowing the original canonical profile gate to run first. No old fixture/conftest, skip map, coverage checker, PostgreSQL gate or assertion changes. All29 offending skip identities and their File counterparts were checked; the existing outcome checker reports zero errors, and applicable PostgreSQL variants gain no skip. Full new-source hosted verification remains required.

After both final fixture corrections, exact staged tree `709614fc6b13fca1764fb715278692848096f633` passed the complete frontend suite1261/8, TypeScript/tokens and105 affected backend cases with85 canonical opposite-profile setup skips. Two complete collections retain7492 nodes; only continuation-owned test source digests and the added fixture-helper digest change. Every PR42 backend/browser test file remains byte-identical. A full original strict File harness check and fresh final-source hosted execution are separate receipts, not inferred from this subset.
