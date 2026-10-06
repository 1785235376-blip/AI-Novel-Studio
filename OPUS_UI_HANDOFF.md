# Opus UI handoff · R4/R5/UX experimental continuation

Current target: `1785235376-blip/AI-Novel-Studio` · branch `work/post-v1-r4-r5-ux` · Draft PR [#39](https://github.com/1785235376-blip/AI-Novel-Studio/pull/39), stacked on PR38 parent `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b`.

The R2 sections below retain historical evidence and protected functional contracts. Current scope, new UI entry points and verification boundaries are in the R4/R5/UX functional supplement at the end and `docs/delivery/post-v1-r4-r5-ux/`. PR37 at `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0` remains its original frozen acceptance object. This follow-on handoff does not modify that branch or package. No merge, release or production deployment is approved.

## Start and verify

- Python 3.12, dependencies from `pyproject.toml` constrained by `.github/ci/python-constraints.txt`.
- Frontend: Node 22.14+ (CI 22.14.0; local work 24.19.0), pnpm **10.6.5**. In `frontend`: `pnpm install --frozen-lockfile`, `pnpm test`, `pnpm build`, `pnpm lint`.
- Use a new isolated runtime directory through `NOVEL_DATA_PATH`, `PROJECT_ROOT`, isolated HOME/XDG variables, `STORAGE_BACKEND=file`, `MOCK_PROVIDER=true`, `ENABLE_CLOUD=false`, memory test vault. Never use a real manuscript/database/credential profile for screenshots.
- Browser checks: `pnpm exec playwright test --config playwright.visual.config.ts --grep 'shell geometry|compact desktop' --update-snapshots=none`; business flows use `playwright.r2.config.ts` and `playwright.export.config.ts`. All data is synthetic. Mock execution is visibly labeled and is not a real provider test.
- `scripts/prepare_pdf_font.py --output <fresh build directory>` prepares pinned OFL CJK font material; it is a build step, not a frontend theme/font replacement.

## Directory and navigation map

The app is a React/TypeScript/Vite desktop-oriented application, with TipTap for prose. `/` is the app; NOVEL/IMAGE/VIDEO use state-driven `ModuleWorkspaceRoutes`, not independent app shells. `/ui-fixture` is deterministic visual-test data, never production data.

| Surface | Entry and files | Stable service boundary |
|---|---|---|
| Shared shell | `frontend/src/ui/AppShell.tsx`, `ModuleWorkspaceRoutes.tsx`, `ModuleSwitcher.tsx`, `FeatureLauncher.tsx` | One shared NOVEL/IMAGE/VIDEO shell |
| Manuscript | `App.tsx`, `Editor.tsx`, `drafts.ts`, `collaborationGuards.ts`, `RevisionPanel.tsx`, `ConflictDialog.tsx` | Versioned chapter save, explicit revision restore, preserved local conflict draft |
| Writing | `novel/AiWritingPanel.tsx`, `AiContextPreviewPanel.tsx`, `GenerationWorkflowTimeline.tsx` | Generation job/SSE, Draft/Diff/Accept, variant identity, actual execution mode and usage |
| Source privacy | `novel/SourcePrivacyControl.tsx` | Current chapter version + SHA-256 + branch review; edits/revocation invalidate future egress |
| Plans and world records | `novel/CreationWorkbenchPanel.tsx`, `creationWorkbench.css` | `/creation-records`, `/creation-reference-data`; DRAFT/APPROVED/ARCHIVED, immutable history and CAS |
| Review comments | Same workbench, “评论与审核” | `/review-threads`; OPEN/RESOLVED, explicit reopen, server actor and CURRENT/STALE/MISSING anchors |
| Knowledge review | `NovelImportPanel.tsx`, `importRecovery.ts` | Versioned persistent candidates, explicit cloud excerpt confirmation, source-policy gate, partial-apply journal |
| Story data | `StoryDatabase.tsx`, `WorldBuildingDashboard.tsx`, `StoryPlanningWorkspace.tsx` | Existing characters/locations/rules/timeline/foreshadowing/narrative contracts |
| Screenplay | `ScreenplayPanel.tsx`, `screenplay.css`, director components | Branch-bound screenplay, approved revision fork, scene/shot edits, independent edit-version CAS |
| Exports | `ExportPanel.tsx`, `export.css` | Immutable snapshot job/history, scope reauthorization, integrity and queue-owned artifact |
| Images | `ImageQueuePanel.tsx`, `ImageGenerationPanel.tsx`, `ImageInfiniteCanvas.tsx` | Durable task attempts, real parameter mapping, explicit image acceptance |
| Assets/references | `AssetLibraryPanel.tsx`, `VisualReferencePanel.tsx`, `AuthenticatedMedia.tsx` | Scoped authenticated bytes, SHA-256, recoverable deletion, reference/lineage metadata; lexical search only |
| Video | `MotionTaskWorkspace.tsx`, `MotionPrivacyPanel.tsx`, `VideoAssemblyPanel.tsx`, `VideoTimeline.tsx` | Scoped frame assets; prompt/provider/model review; bounded silent review MP4, not finished audio/video mastering |
| Audio | `AudioGenerationPanel.tsx`, `AudiobookManifestPanel.tsx`, `SpeechSynthesisPanel.tsx` | Captured chapter/voice versions, segmented queues, verified binary audio and manifests |
| Agents/workflows | `WorkflowPanel.tsx`, `AgentQueuePanel.tsx`, `AgentJobDetail.tsx`, `AgentResultReview.tsx` | Worker state is authoritative; enqueue ≠ success; review ≠ apply |
| Plugins | `PluginManagerPanel.tsx`, `PluginInspector.tsx` | Declarative package management; executable plugins remain disabled |
| Model/settings | `ui/ModelCenter.tsx`, `AiControlCenter.tsx`, `MediaProviderSettings.tsx` | Actual capability/credential/runtime state; Host/OS vault remains authoritative |

## Design system and component ownership

Read `AGENTS.md`, `.codex/skills/ai-novel-studio-ui/SKILL.md`, `docs/ui/design_system.md`, `protected_ui_surfaces.md` and `visual_baseline.md` before editing.

`frontend/src/ui/tokens.css` and shared `primitives.tsx` define the existing DS-v1.0 light design. Reuse Button, Badge, Panel, StatusMessage, EmptyState and dialogs. Root shell, switcher, sidebars, inspector shell, status bar, tokens and global primitives are protected. A system-level change requires the repository's Design System Change Request. No new palette, shell, editor stack or global typography has been authorized in R2.

Domain spacing and controls must use existing tokens. Token `--border-default` already contains width/style/color; do not wrap it in a second border shorthand. `--space-1/2/3/4/6/8/10/12` are the existing scale.

## State and request contracts

- `frontend/src/api.ts` is the API boundary; `store.ts` holds active project/chapter/model/scope, plus ephemeral selected style/plot IDs. Credentials do not belong in this store.
- TanStack Query owns server cache. A query key must include project, branch and an opaque session identity where needed. Never put a token into a URL, persisted cache, log or screenshot.
- Auto-loading export/screenplay/workbench requests use an explicitly captured `CollaborationContext` override. A parent effect may still hold the previous global context during a child mount; never assume a remount alone fixes request headers.
- Scope/project/session changes must invalidate stale responses, progress timers, local selections and previews. Unmount and abort fences are business behavior.
- Conflict responses preserve unsaved input. `expected_version`/`edit_version`, source versions, hashes, job IDs and attempt tokens must survive UI refactors.
- Every surface needs loading, empty, success, error, unauthorized, missing configuration, cancellation/retry and conflict states as applicable. Do not replace actionable failures with a success badge.
- Source-policy controls authorize only the exact reviewed chapter revision; changing a policy cannot retract bytes already sent. Queued requests recheck current policy before dispatch.
- Reviewed plans remain distinct from approved Canon and manuscript. History restore creates a new draft version and requires fresh review.
- Import acceptance may stop after some independently committed candidates. Its journal reports completed/total/applied; the UI must not report whole-review success or silently rerun already completed writes.

## Protected behavior

1. AI output is Draft until the user explicitly reviews and Accepts; no auto-writing from a success callback.
2. Backend trusted identity/permission checks decide access. Client roles, hidden buttons, task IDs and `enabled` fields are not authority.
3. Sensitive source policy is fail-closed; missing policy never becomes cloud permission.
4. Original source assets and approved screenplay versions remain recoverable. Preview/download URLs carry no session or provider key.
5. Job submission, remote acceptance, completed result, user approval and domain application are distinct states. Cancellation fences late results and side effects.
6. Retry is explicit; ambiguous paid requests are not silently replayed or routed elsewhere.
7. CSV/Fountain/DOCX/resource packages render captured snapshots, not later edited project content.
8. Production mock execution is forbidden; development stand-ins remain explicitly labeled.
9. Third-party plugin execution stays `execution_supported=false` / `DENY_ALL` until target-platform sandbox/trust evidence exists.
10. Existing `/api` and `/api/v1` aliases stay compatible, with explicit 409/428 preconditions for new version protection.

## Screenshots and visual limits

Canonical design references: `docs/ui/reference/*.png`. They are design guidance, not screenshot goldens.

Committed screenshots are in `docs/delivery/dot-astra-rc-r2/evidence/screenshots/` with an exact-source/run/artifact/SHA256 `manifest.json`. `export-recovery-{1366x768,1440x900,1920x1080}.png` records the real File-backend browser journey with synthetic text and explicitly mocked model output. `local-ai-{1366,1440,1920}.png` records actual browser rendering against synthetic runtime/hardware API fixtures, including deliberate PARTIAL and unavailable capability states; it is not real Windows/GPU discovery. All six were opened and inspected. The writing-goal inspector fields now use a scoped token grid and have three-viewport containment/non-overlap assertions. Independently scrollable panes may be captured at the download position.

The exact-source hosted runs are in TEST_RESULTS. Local cloud Chromium remains blocked by the OS socket restriction; hosted Chromium actually executed the business/geometry checks. Do not relabel unit/API tests as visual acceptance or update goldens merely to silence failures.

Known visual follow-up: long workbench forms need visual polish, screenplay editing controls are compact, histories can be dense, and media inspectors need consistent spacing at smaller desktop sizes. Functional inputs/actions must remain discoverable and scrollable. Native Windows WebView2 and Chinese IME/paste/undo require user-machine acceptance.

## Safe Opus scope

Under the subsequent user's visual-design authorization: improve spacing, alignment, hierarchy, labels, responsive domain layout, focus and accessibility within the existing component contracts. Keep domain tests and data behavior. Backend schemas, source permissions, identity, credential handling, migration/recovery, task state machines and provider dispatch are engineering boundaries, not visual-cleanup targets.

Outstanding backend/provider/native verification remains listed in the readiness matrix; it is not silently reassigned to Opus.


## Local AI Discovery supplement

Model Center now consumes LocalAiDiscovery. Improve hierarchy and token spacing only; preserve separate Detect, Validate, Register, explicit Enable and task-only Launch, unknown/partial evidence, protected local paths, auth lockout, cancellation/late-response guards, license review and registration-only deletion. Declared, metadata-verified, workflow and real inference evidence must remain distinct. See LOCAL_AI_DISCOVERY.md and LOCAL_AI_WINDOWS_ACCEPTANCE.md.


## Revision and native-package additions

- Live `RevisionHistory` includes chapter version in its cache key and uses opaque per-scope observer IDs. Captured API context and authority epochs fence late list/detail/restore results across actor/session/project/workspace/storyline/branch changes, including A→B→A. StrictMode effect replay must not invalidate an otherwise current pending request. Preserve `AppRevisionHistory.test.tsx` and the independent replay controls.
- Restore updates the existing chapter cache/hydration path, preserving newer dirty buffers and persistent conflicts. Do not reintroduce unconditional `location.reload()` or clear local drafts on a late response.
- Native Windows package/Python/PostgreSQL smoke is a separate tested layer. Interactive WebView2, OS-vault, IME, installer/upgrade/uninstall and real-model acceptance remain distinct NOT_RUN gates. See `docs/R2_WINDOWS_BASE_INPUTS.md` and the exact-head receipts.

## Post-V1 R3 Experimental workbench (2026-10-05)

This section belongs to PR #38 only. The PR #37 / 1ad947e V1 acceptance package and visual evidence remain frozen. Do not fold R3 into V1 acceptance requirements.

Entry: an optional Experimental group in the existing FeatureLauncher, inside the existing NOVEL panel contract. It is absent when the server feature allowlist is empty or V1_ACCEPTANCE_MODE=true. Feature discovery is session-keyed and uses the captured authenticated session; the browser cannot enable flags.

Functional panels reuse the current tokens/primitives/shell:
- Planning: graph/node hierarchy, structured fields, custom theories, Mock multi-proposals, compare, approve/reject, archive, history and explicit version recovery
- Long-book import: bounded chunk processing, pause/resume/retry, exact source evidence, item/batch review and explicit checkpointed commit
- World/characters: typed candidate records, reviewed experimental Canon, deterministic continuity findings and chapter-state queries
- Unified Inbox: domain/status/search/stale filters, original-domain review actions, honest unavailable/read-only domains, safe batch receipts
- Agent teams: eight roles, four recipes, explicit execution/recovery and human review; contract-only output is labelled
- Media: adapter definitions versus runnable implementations, cover/storyboard briefs, explicit Mock task execution, compare and reviewed asset lineage
- Embeddings: NOT_CONFIGURED by default; indexes and status never imply lexical search is an embedding
- Audiobook: attribution/voice mapping, emotion/style, ordered segments, measured-versus-unknown duration, track slots and review

Preserve these distinctions in any later visual design: REVIEW/PENDING_REVIEW versus APPROVED; STALE versus current; VERSION_CONFLICT versus failed save; NEEDS_REVIEW attribution; ADAPTER_REQUIRED family versus runnable adapter; NOT_CONFIGURED versus MOCK_ONLY; APPROVING/RESUME_APPROVAL versus source-changed reconciliation. Never turn a successful generation task into implicit Canon or asset approval.

Planning retains edited fields when a selected node changes version. Its explicit comparison/rebase control updates the save baseline only after the user chooses to keep the draft; it does not submit or discard edits. Interrupted media/audio approval exposes its existing asset checkpoint and cannot be rejected as though no promotion occurred.

No final aesthetic redesign, AppShell geometry change, golden-image rewrite or new token system is part of R3. New browser tests are separate from inherited R2 tests. Screenshot claims must refer to successful hosted runs; local Chromium failed to launch in the cloud executor, so authored screenshot calls alone are not visual evidence.

See POST_V1_FEATURE_MATRIX.md and POST_V1_FEATURE_FORWARD_REPORT.md for exact scope, actual verification and remaining limits.

Known inherited engineering defect: File project deletion can race lazy chapter-document readers, producing DirectoryNotEmpty or recreating a deleted project. R3 browser teardown isolates disposable fixtures; it does not fix application deletion concurrency. Preserve this distinction and defer the production shared-fix/backport candidate to the subsequent authorized engineering branch. See docs/delivery/post-v1-r3/KNOWN_INHERITED_DEFECTS.md.

R3 visual evidence: docs/delivery/post-v1-r3/screenshots/ contains eight actual hosted-Chromium screenshots from implementation SHA 20cd2679ee104702529962202ce4b9d894bffc89, run 37321369458, artifact 11350881328, with file digests/dimensions/provenance in manifest.json. All eight were opened and inspected. Planning comparison visibly expands both ending values; history/Inbox/audio preserve explicit reviewed states; media previews are tiny synthetic Mock color fixtures, not quality evidence. Three desktop sizes retain scroll position (heading partly above its scrollport; lower controls below smaller viewports); no serious overlap or horizontal clipping was observed. The 1920×1080 capture is the clearest overall functional handoff reference.

## R4 / R5 / UX functional integration

The successor work lives on `work/post-v1-r4-r5-ux`, Draft PR39, from exact released R3 `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b`. PR37 remains frozen. Read `docs/delivery/post-v1-r4-r5-ux/FEATURE_MATRIX.json` and current exact-source receipts before making a readiness claim.

- `writing_recovery_v2`: existing editor/save toolbar distinguishes volatile draft, verified browser journal and backend acknowledgement; TXT recovery, durable conflicts and retained-generation chooser remain explicit. Unverified or denied task recovery cannot expose an Accept-ready cached result.
- `workspace_tools_v2`: existing global Search/Ctrl+K reaches `WorkspaceToolsPanel`; resume/search/task/diagnosis/scenario sections use real APIs. Search and saved anchors use EDITOR_TEXT_CODEPOINT, with hardBreak newline and Unicode-safe mapping. Late dismissed/superseded responses cannot navigate.
- `writing_focus_v2`: `WritingFocusPanel` and readonly `WritingReferenceRail` reuse the existing TipTap/editor instance and inspector collapse. Preferences change display only; paragraph emphasis is not an AI-edit lock. Inspiration stays a private draft; copying creates a reviewed planning proposal, never automatic Canon/manuscript changes.
- `local_ai_workflow_inspector_v2`: imported Comfy API JSON is passive untrusted data. Host session and project authority are separate. DENY_ALL remains unconditional; registry observation does not enable arbitrary execution. Preserve unknown/missing/runtime/permission states and redacted summary export.
- `author_context_inspector_v2`: actual single-route request preflight, digest-bound generation and final authorization/source/context checks share one builder. It is not a literary-quality proof. Keep the exact payload/context/unknown-token/omission boundaries visible. Legacy metadata preview is labelled advisory; variants do not pretend to have an individual verified preview.
- `temporal_story_graph_v2` / `character_mind_v2`: typed existing-ID graph and reviewed knowledge events expose author and character views. A filtered query alone does not prove main-generation secret exclusion; keep that separate integration boundary in the matrix until its exact request capture passes.

Every new mode needs loading, empty, permission/configuration missing, conflict/stale, in-progress and recovery states. Do not simplify away draft durability, source versions, missing adapters, history, privacy or consent. One shared shell/tokens/framework remains. The optional search/focus consumer contract is documented in `docs/ui/change_requests/r4_workspace_search.md`.

Screenshots and actual hosted browser/PG/native evidence for this successor are pending its exact integration CI. Existing R3/R2 screenshots retain their own provenance. Native Windows IME, screen readers, actual GPU/model quality, target editors and user acceptance remain separate NOT_RUN layers; CSS zoom is labelled simulation, not native OS zoom.


---

## R4/R5/UX functional supplement — current experimental continuation

Target: Draft PR39, `work/post-v1-r4-r5-ux`, stacked on frozen R3 `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b`. This is the current functional supplement in the original handoff; it does not alter the frozen PR37 acceptance package.

Read AGENTS.md, the repository UI skill and DS-v1.0. Keep one AppShell, original TipTap editor, shared tokens/primitives and captured collaboration context. This handoff is for later visual polish; it is not authority to redesign the shell or weaken business behavior.

## Current real entry points

- App editor: visible draft/save/recovery states, explicit archived conflict resolution, composition-safe updates, focus/reference rail, exact selection and paragraph AI locks.
- Existing experimental workbench: resume/search/tasks/diagnostics, workflow inspection, graph/character viewpoint, model route/benchmark, asset lineage/replay, style/judge, selective change refresh, bounded simulator, research library and partial revision panels.
- Original writing inspector: shared actual request preview and final dispatch authority, explicit character viewpoint, style choice and trusted partial-only generation binding.
- Existing history and Draft/Diff/Accept remain the final action surfaces. The new revision panel uses the same document CAS path; it cannot silently accept an entire generation.

Each panel has current loading, empty, missing-dependency, error and review states. Preserve source versions, actor/scope-bound clients, abort/late-response fences, expected-version tokens and pending/accepted distinctions. Do not replace disabled explanations with empty buttons.

## Layout and accessibility constraints

The feature-OFF editor wrapper uses `display: contents`; focus split alone creates a grid. This prevents an invisible editor row from intercepting legacy panel actions. Preserve keyboard names, focus return, status live regions, IME composition buffers and manual-merge cache monotonicity. Reference content remains read-only.

New functional panels are intentionally dense and may need spacing, grouping and navigation polish within the design system. The number of experimental tabs is a known discoverability cost; later grouping should retain searchable, testable feature access rather than add top-level menus.

## Evidence and outstanding checks

WAVE_2_3_CHECKPOINT.md records exact local source and tests. Hosted browser checks run `playwright.r4.config.ts` with synthetic isolated projects and exact flags; actual model quality and native desktop interaction are separate. U13's backend performance receipt is scoped to its recorded older source/method and is not a browser latency claim. Raw browser measurements are now explicitly written into compact CI artifacts.

The blocked second-slice independent review is documented in SECOND_SLICE_REVIEW_STATUS.md. Functional tests do not imply audit closure or user acceptance. No new visual goldens were accepted merely to make tests pass.

### Production, reading and language extension

The subsequent pinned source adds ReaderPreflightPanel, WritingSessionPanel and the existing task-center notice addon; DirectorPanel and TimelineExchangePanel; VoiceDirectionPanel and SubtitleTimelinePanel; PortableProjectsPanel and SafeBatchesPanel; TemplateLibraryPanel, DeclarativeAgentsPanel and MultilingualEditionsPanel. All use captured ExperimentalClient authority and the existing workbench. See WAVE_4_5_CHECKPOINT.md for exact local validation and pending hosted checks.

Navigation metadata now lives in experimentalNavigation.tsx. DeferredExperimentalWorkbench loads the optional workbench only when an enabled entry opens; its own loading/error/retry boundary must not unmount the prose editor or resubmit jobs. Keep current source/version/permission fences, readable unavailable states, exact integer/rational time, approved asset identity and per-segment human review intact during later visual polish.

### All-forty runtime and request/recovery controls

The next immutable runtime is `d2390d12cea037aa848b769d1f87822922832258` (full hosted results pending). ComicLayoutsPanel, InteractiveStoryPanel, WriterRoomPanel, ProjectForksPanel and OfflineSyncPanel now have actual service/API wiring. Preserve explicit approved-media review, exact source/version receipts, original CAS/checkpoint recovery and uncertain-state reconciliation; exports are bounded supported formats, not claims of external engine/NLE quality.

Workbench search filters only currently enabled Chinese labels and stable feature identities locally. Typing never switches the active panel, resets drafts or calls a search API. Clear/focus and IME behavior must survive visual changes.

Original writing, broker and revision consumers share AuthorRequestControls. Reduced source modes physically remove dependent context bundles/references; UI preview carries the exact request body sent at dispatch. Local 2–3 variants each have a reviewed original job ID, receipt and recovery state. Broker-budgeted/cloud groups remain unavailable. Do not replace these controls with an independent summary that disagrees with the actual request.

U07 now projects existing author jobs and opens their exact original Draft/Diff/Accept without requiring broker enablement. Dismissed/superseded navigation cannot open a late result; aborting that lookup never cancels the job. Preserve unsaved chapters, current authorization and origin feature gates. U01 full reference-layout restoration and U10 isolated first-use sample work remain tracked separately from this pin.

### Restored workspace and first-use sample extension

U01 now persists search/task filters and original U04 preference/reference pointers, plus bounded unresolved task IDs. Only the original services resolve those pointers. The local project-ID hint is checked against a fresh original project inventory, never consumed by authenticated/scoped sessions, and never contains credentials or manuscript. Keep missing/corrupt/stale explanations, dirty/IME/target-draft fences and late-response cancellation visible. “切换本机作品” must preserve unsaved work.

U10 adds FirstUsePanel inside the existing entry experience and SampleJourneyGuide inside the original inspector stack, not an extra workspace grid row. Explicit sample creation uses original local/scoped authorities and durable stage receipts; uncertain creation is not retried automatically. Opening refreshes the original project list before selection so the title and U01 hint are authoritative. The guide uses actual saved chapter versions and original export navigation; it does not mark reopening/download complete merely from a click. Preserve skip/reopen, manual-writing availability and disabled adapter explanations.

Final full-suite and hosted results must be read from the exact delivery checkpoint, not inferred from these descriptions. Independent review remains BLOCKED.

### Verified screenshots, then the editor-chrome correction

[UX_JOURNEYS.md](docs/delivery/post-v1-r4-r5-ux/UX_JOURNEYS.md) now indexes actual executed paths and [retained synthetic screenshots/measurements](docs/delivery/post-v1-r4-r5-ux/evidence/browser-1d1b9756/README.md), with source/job/artifact checksums. They are historical 1d1b9756 output, not automatically visual acceptance. In particular, the U10 1366 image exposed prose clipping caused by an extra resume grid item despite a passing typing/save journey.

Keep `.novel-workspace-chrome` as the first grid item, containing save/resume/volatile notices; preserve the original editor second row and original panel third row. Full stopping notes stay in the existing workspace editor; only the banner preview ellipsizes. The named original-task-center landmark distinguishes it from notices containing the same task ID. New geometry checks require actual visible/hit-testable manuscript text at all three desktop sizes, not merely a present `.ProseMirror` or unchanged outer shell. See EDITOR_CHROME_REPAIR.md. Never remove these checks or hide an error/recovery action to obtain a cleaner screenshot.

### Keep save and recovery actions reachable

The actual 038c322d browser run passed visible manuscript geometry but exposed the original sidebar-edge toggle covering Save/export actions. The consumer repair groups shrinkable title/count/goal metadata, wraps intact original SaveControls, and reserves the existing toggle footprint with design tokens. Keep the shared toggle position and interactive area unchanged. Do not replace the repair with a forced click, hidden toggle, removed recovery button or horizontally scrolling chrome. Hosted geometry checks now verify action rectangles and pointer-hit ownership in real failed-save/conflict states at 1280/1366/1440/1920. Exact hosted results remain in the delivery checkpoint.

### Corrected current-source browser receipt

Source `bf0ec2b0`, exact tree `b5404021`, passed all **54 hosted browser cases** (35 R4 + 2 business + 9 geometry + 7 R3 + 1 export), plus 981 frontend unit tests and types/build/token checks. The original Save and conflict-draft download paths now pass actual pointer dispatch at the preserved shell sizes. See [corrected writing/recovery screenshots](docs/delivery/post-v1-r4-r5-ux/evidence/browser-bf0ec2b0/README.md): all five original PNGs were directly inspected; do not use the old clipped historical image as the current design reference.

Preserve the current consumer chrome grouping, metadata/control wrapping and token-based toggle reserve. The warnings and conflict controls are intentional. New styling must pass visible-prose and action-hit checks, keep original Draft/Diff/Accept and source/privacy guards, and retain disabled-state explanations. Model/GPU/native interactive Windows and the separately blocked independent review remain unverified.

## 2026-10-05 original-scope refinement

Functional continuation preserves the existing shell/tokens and regular/advanced/focus state. U03 adds scope/filter/paging/cancel/rebuild controls plus authorized cross-project navigation guarded against dirty/IME/save/recovery state. U08 adds exact identified-source include/exclude/pin controls; preview consent is invalidated on every source change, and excluded derivatives are absent at final dispatch. Portable maintenance shows expected/candidate hashes, conflicts and current storage evidence. Batch actions now use original image/audio admission and explicit reconciliation; satisfied items do not reserve again. Structured fork merge remains field-by-field review attached to an owned manuscript fork.

The next staging wave adds explicit model route, preview, consent, dispatch, refresh/cancel and review-only adoption for simulator, Judge, translation and declarative workflow panels. Original task-center entries return to their owning review tool, never the generic manuscript Accept action. Media controls distinguish synthetic from registered-local routes, observed model identity, unknown costs and missing reference-image support. Audio assembly preserves per-segment pauses and exposes measured preview/export. These are functional additions, not permission to remove missing-model/error/unknown/stale/approval notices. Exact new hosted screenshots are pending; earlier screenshots remain source-specific.

## Reconciled verified runtime 4e476ce: current handoff

Both exact push/PR runs passed all five lanes. Current frontend1,045 PASS, hosted64 browser cases passed, realPG1,344 marked contracts passed. The ten unedited representative screenshots in docs/delivery/post-v1-r4-r5-ux/evidence/refinement-4e476ce are source- and hash-labelled; twelve original captures were directly inspected. Some images show normal scrolled panels and pre-approval disabled controls. Do not treat screenshots as a substitute for exact request/permission assertions or model-quality evidence.

The observed single-request App receipt forwarding defect is repaired. Preserve fourth-argument receipt forwarding and the enabled-inspector missing-receipt refusal; never visually bypass consent or fall back to legacy generation after exclusion review. Search navigation keeps exact current-project response/version barriers, dirty-buffer fences and explicit stale-source recovery. Registered simulator/Judge/translation/declarative output remains draft-only and opens its owning review tool. Real-local media remains broker-admitted with unknown actual billing held honestly. B03 mix output is measured PCM and separately reviewed. B09 supported entity merge attaches to an owned manuscript fork; B10 branch metadata is not manuscript ownership.

All established shell/token/height contracts remain; no full visual rewrite is requested. Advanced evidence may be made easier to scan, but cannot lose privacy/source/version/actor/budget/unknown-state details. Actual native Windows, screenreader, model quality and target-app acceptance remain separate. Independent follow-up review remains BLOCKED; UI regression does not close it. Read the latest PR39 head for the documentation/evidence successor exact CI.
