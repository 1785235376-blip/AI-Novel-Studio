# Post-Interop continuation target (2026-10-06)

Current development is Draft [PR43](https://github.com/1785235376-blip/AI-Novel-Studio/pull/43), branch `work/post-interop-r4-r5-ux-continuation`, stacked on frozen PR42 `e58c72b04182cd374af092314386b90f8250a173`. Current feature and journey evidence is in `POST_INTEROP_FEATURE_MATRIX.md`, `UX_ACCEPTANCE_MATRIX.md` and `docs/delivery/post-interop-continuation/`. Earlier handoff sections retain their historical scope; appended Post-Interop wave sections describe the current pages/components/APIs/state/permissions and non-breakable behavior. No final visual redesign or full product acceptance is claimed. Historical independent review stays BLOCKED; this work does not replace it.

---

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

## Shared R1/R2/R3 repair handoff (independent PR40)

Feature additions are paused for the supplied c6f2126 findings. Follow `docs/delivery/shared-r123-repair/` and the exact PR40 head/CI. Original reproduction scripts and failing observations are preserved; Python3.12.9 hosted baseline runs 37402995698/37403004721 explicitly reproduced all three defects on untouched c6f2126.

Preserve these shared contracts during later UI work:
- A valid Host session is identity only. Original project reads/writes/review routes still require the current project's membership and NOVEL permission. Lists and counts are filtered before serialization. Project-global manuscript sources must not silently substitute for an unsupported branch source.
- SSE authority belongs to each observer. Session/membership/scope/feature/project changes close that observer before further private body output. Closing or revoking one observer must not cancel a shared job or another authorized observer. The last ASGI send-boundary check does not recall bytes already sent.
- Reject is completed-draft review. Executing/settling states return409 and do not cancel/truncate the draft. Cancellation remains a separate action. Do not display an optimistic REJECTED state after a409. Preserve durable SETTLING, completed accounting, reconciliation-required/unknown-use and acceptance-uncertain states; never hide an unresolved budget hold.

No visual redesign was authorized in this repair. Keep all original assertions and evidence, 39 PARTIAL plus F00 INTEGRATED, real model/GPU/native/target-app NOT_RUN, and historical independent follow-up review BLOCKED. Implementation regression does not close that historical review. PR37/38 remain frozen; backport candidates require separate approval and regression.

## Local Interop V1 UI supplement · 2026-10-06

This supplement applies to the separate Interop development branch based on shared repair checkpoint `2c5b4e2f43c50318d9c1eeea487f68c2d66f7b42`. The older PR37/38/39 sections above are historical; this work does not change those frozen branches or append Interop to PR40.

### Functional entry and boundaries

- `frontend/src/interop/LocalTutorIntegration.tsx` supplies one “问助手” action through the existing AppShell status slot across NOVEL and the other module workspaces. The existing Settings panel and AI Control settings open the same integration dialog. AppShell, ModuleSwitcher, tokens and protected shell dimensions are unchanged.
- Opening Studio does not discover or connect a Tutor. Opening the dialog reads only local host status. The host rollout flag `local_tutor_interop_v1` and per-user opt-in are separate; both default OFF, and V1 Acceptance Mode remains forced OFF. The standalone flag does not accidentally enable unrelated Experimental Workbench navigation.
- File-only mode does not invent a principal or project permission. A trusted workspace session is required for the bridge; ordinary file-mode writing remains available.
- The connection form is explicitly a development loopback reference endpoint. Detected product display name, negotiated capabilities, protocol and permission limitations are visible. Synthetic peers show `MOCK_ONLY`. Real Tutor Desktop and Windows Named Pipe integration stay `LOCAL_REQUIRED`.
- App/page identity, task/error/model/runtime metadata are preselected; content defaults to `NONE`. Selection, current chapter and additional explicitly selected chapters are initially unchecked and require separate preview/confirmation. Other chapter choices are metadata-only, individually selected, limited to four, and bounded again by the host. There is no whole-project auto-fetch.
- TipTap publishes the actual selection plus Unicode-codepoint offsets using the existing document anchor semantics (single newline between text blocks, hard breaks preserved). Existing ProseMirror positions remain unchanged. Content choices require a saved current source, with chapter version and selected offsets validated by the host; unsaved input, composition, changed selection or source version invalidates consent.
- Diagnostic field choices are removable. Both the sanitized DiagnosticCapsule and its mandatory, metadata-only protocol context envelope are displayed before sending; no hidden project/chapter context is added.
- Guidance is plain read-only text with steps, warnings, inert evidence locators, optional model recommendations and explicit evidence verification. It cannot write prose, change settings, accept generation output, execute a model or follow a locator. Handoff buttons first ask the host to authorize the exact target; only then can the existing module/feature route change. Task handoffs display only the host-authorized bounded task receipt and never enter Generation Review or fetch a prompt/output.
- Close/Escape, cancel, repeated clicks, timeout, user/session/scope/project/chapter/feature changes and master-switch OFF invalidate pending work. Pending calls are aborted and cancelled by request ID, including connects before a session exists. Late-created sessions are disconnected. No old reply can populate a newer request.

### API and maintenance map

- `frontend/src/interop/client.ts`: captured session/branch headers, fixed same-origin `/api/local-interop` endpoints, redirect rejection, typed errors, cancellation; no direct browser request to a Tutor endpoint and no token in URL.
- `contracts/local-interop/v1/protocol.ts`: generated shared protocol DTOs, consumed without private product imports.
- The outer `session_id` is the Studio host authorization handle. `/connect.protocol_session_id` is the peer protocol session ID; nested TutorGuidance and VerifierResult must match that distinct ID. Both outer and nested request/session identities are checked.
- A typed protocol error body is rejected even when HTTP headers already report 200, covering host revocation at the response-send boundary.
- `frontend/src/interop/navigation.ts`: explicit product-independent feature allowlist and exact current-scope guard. Cross-project navigation cannot expand scope in V1. Existing chapter draft/conflict protection is preserved before a chapter change.
- `frontend/src/interop/localTutor.css`: domain dialog styling uses existing tokens and shared Button/Panel/Badge/StatusMessage primitives; no new palette or protected shell redesign.

### Verification and honest remaining boundary

- DONE: focused DOM/client/editor checks cover default OFF, acceptance OFF, captured headers, metadata-only consent, actual Unicode selections, explicit additional sources, diagnostic removals/envelope, read-only rendering, explicit handoff, cancellation/repeat/close/focus, bridge OFF while pending, stale receipts, expiry, changed scope/source and typed revocation frames.
- MOCK_ONLY / CONTRACT_VERIFIED: `tests/localInteropRealHost.test.ts` runs the actual frontend TypeScript client against a real isolated Studio app and independent Synthetic Tutor subprocess over loopback. It verifies separate host/wire identities, metadata NONE, exact Unicode selection, guidance, diagnostic envelope, host-evidence UNKNOWN, authorized handoff, unchanged manuscript/version and revoked-session denial. Run with `LOCAL_INTEROP_REAL_HOST_TEST=1 INTEROP_PYTHON=python pnpm exec vitest run tests/localInteropRealHost.test.ts --pool=forks --maxWorkers=1 --minWorkers=1`. It is deliberately opt-in and skipped in the default suite.
- BLOCKED / NOT_RUN locally: seven real-process Playwright flows and viewport/focus checks in `tests/e2e/local-interop.spec.ts`; Chromium aborts before test execution because its process-singleton IPC socket is not permitted in this executor, including one approved retry. There are no local screenshot approvals or golden-baseline updates.
- Hosted verification command: `INTEROP_PYTHON=python pnpm exec playwright test --config playwright.interop.config.ts`, after ordinary Python/frontend dependencies and `pnpm exec playwright install --with-deps chromium`. Do not set a system Chromium path in CI. The config creates fresh synthetic HOME/XDG/project/data directories, starts loopback-only Studio `8051`, Synthetic Tutor `8052` and Vite `5251`, and enables only this experimental feature. Results are under `frontend/test-results/local-interop/` and `frontend/test-results/local-interop.xml`.
- LOCAL_REQUIRED: actual Tutor Desktop binaries/source, Windows per-user Named Pipe ACL/runtime and real Desktop cross-product integration. HTTP reference or Synthetic Tutor success is not Desktop integration evidence.

Final local UI receipts at source freeze: TypeScript application build and the separately typechecked Interop Playwright config/test/client integration test passed; Vite production build passed with the existing large-chunk advisory; UI token guard passed (42 shared UI files) plus new domain token/layout guard passed. Full Vitest: **173 files passed, 2 skipped; 1081 tests passed, 7 skipped**. The opt-in real frontend-client/Studio/Synthetic-Tutor roundtrip passed separately (**1/1**). Seven browser flows remain locally **BLOCKED before browser launch / NOT_RUN**; hosted results must be recorded separately against the published commit.

### Consent correction: ongoing metadata events

The initial connection behavior allowed metadata events before a distinct standing-sharing confirmation. The corrective Interop revision removes that path: connection now authorizes handshake/liveness only, and the UI rejects a connection receipt that already carries an event grant.

- Ongoing state sharing has an independent, initially unchecked choice on every connection/reconnection. The user chooses categories, reviews the exact metadata capsule and scope, then explicitly confirms a single-use `/events/preview` receipt through `/events/subscribe`. A one-shot Ask or diagnostic confirmation never creates standing permission.
- The active panel shows the host-acknowledged category allowlist. Explicit Stop calls `/events/unsubscribe`, invalidates pending event previews and waits for an inactive receipt; errors remain visibly unconfirmed. Cancelled/failed subscription attempts explicitly revoke uncertain grants as well as cancelling the originating request. Dismissing an unconfirmed preview, changing its field choices or leaving that preview invalidates its server receipt.
- Diagnostic preview pauses any ongoing subscription before returning the minimized diagnostic and visible protocol envelope. `event_subscription_paused: true` is required before displaying a successful preview. Sending diagnostics never resumes events. The UI explains that information already sent cannot be recalled.
- Closing, reconnecting or changing identity/scope still uses the existing disconnect fence; source changes invalidate sharing consent. No R1/R2/R3 editor, generation or protected-shell implementation was changed by this correction.
- New DOM/client and real frontend-client/Studio/Synthetic-Tutor regressions verify zero events before separate consent and after one-shot Ask, exact event-field omissions, explicit stop, diagnostic pause/no-resume, canceled grants, stale preview rejection and reconnect default-OFF. Two additional real-process browser regressions bring the authored Interop browser suite to nine; local Chromium remains BLOCKED/NOT_RUN and was not retried for this correction.

Consent-correction source-freeze receipts: **173 Vitest files passed, 2 skipped; 1094 tests passed, 7 skipped**. Focused Interop DOM/client checks: **46/46 passed**. Actual frontend-client → isolated Studio → independent Synthetic Tutor consent roundtrip: **1/1 passed**. Application and Interop test/config typechecks, production build, shared/domain token guards and diff checks passed. The production build retains the existing large-chunk advisory. Nine authored browser flows await hosted execution; no local browser retry or visual-baseline update was performed for this correction.

### Revocation truth-state correction and hosted browser setup

Disconnect now retains an unconfirmed revocation handle, disables new sharing/connection attempts, and displays `UNKNOWN` until a matching `DISCONNECTED` receipt arrives. Failed or ambiguous receipts stay unconfirmed and offer retry. Master OFF keeps its acknowledgment-controlled checkbox and `UNKNOWN` until the host settings/status receipt confirms the disabled gate; a separate disconnect acknowledgment does not falsely claim that master OFF succeeded. A late disconnect failure cannot undo a newer acknowledged OFF.

Close waits for revocation. If acknowledgment fails, the panel remains with a warning and an explicitly labeled “仅关闭面板（撤销未确认）” dismissal; closing a panel is not a promise that the Studio host shut down. Browser/process loss still cannot prove immediate remote revocation. This correction adds no lease, UI-liveness transport, App/editor change or protected-shell redesign.

Hosted `ba69b12` push and its PR merge checkout executed all 64 original browser checks, 1094 unit tests (7 optional skips), and the real TypeScript-client roundtrip successfully. All nine new Interop browser cases failed at their initial master-toggle setup because Playwright `check()` requires an immediate checked state, while that switch correctly waits for the host acknowledgment. The new test helper now clicks once, checks the successful `/settings` receipt, then retains the checked-state assertion. No original assertion or golden was removed, and no local Chromium retry was attempted.

Local source-freeze verification for the truth-state/setup correction: **173 Vitest files passed, 2 skipped; 1102 tests passed, 7 skipped**; focused Interop DOM/client **54/54** passed. Application and test/config TypeScript, Vite production build, token guards and diff checks passed. A successor hosted run is required to verify the nine Interop browser flows beyond setup.

### Hosted modal-focus correction

On `a1b42cf` and its identical-tree PR merge checkout, both frontend jobs passed 1102 unit tests (7 optional skips), all 64 original browser tests, the real-client roundtrip, and eight of nine Interop browser flows. The sole remaining failure was Escape dismissal after an unavailable Tutor: disabling the async connect button can move native browser focus to `document.body`, outside the dialog's existing key handler.

A body-focus Escape regression reproduced the defect before repair. The modal now captures Escape/Tab only when focus has escaped its active subtree, retaining existing in-dialog handlers, acknowledgment-based disconnect, focus restoration and cleanup. The hosted dismissal assertion remains unchanged. Final local verification: **1104 passed, 7 skipped** across the full unit suite; focused Interop **56/56**; TypeScript/build/token/diff checks passed. No local Chromium retry, baseline rewrite, transport/socket change or shell redesign was made. A new hosted run is still required to verify the repaired ninth flow.

## Post-Interop Wave1 UX checkpoint

Existing Editor/SaveControls now preserve corrupt local draft bytes before overwrite and distinguish offline draft from backend persistence. Keep explicit recovery export/reset, source CAS and durable acknowledgement truth. Existing WorkspaceTools aggregates original generation/import/team/image/media/audio/video/export/workflow/review owners; cancellation uses a current owner/state receipt. Unknown cost/progress remains unknown. Preserve current-scope exact IDs, dirty-buffer navigation guards, unavailable-action reasons, independent cancellation and no automatic model retry. Import/Teams/Review Inbox target props are owner-filtered; Media/Voice/Audiobook target forwarding integrates in Wave4. Source add/pin and further entity catalogs remain an active refinement. APIs: existing experimental `/ux` routes plus scoped task-cancel and original-owner readers. Server flags remain existing default-OFF gates; V1 forced OFF. No protected shell/token redesign.

## Post-Interop Wave3 models and research

Existing ModelBroker/Benchmark panels add policy and evidence controls without new state authorities. Keep explicit cloud fallback, unknown prices, exact current-route/evidence receipts and source-change invalidation. Existing ResearchLibrary adds original-file replacement, retained history/private restore/export, note edit/delete and citation repair. Restore creates a fresh private version; stale citations never silently rebind. Existing EmbeddingPanel uses scoped original source pickers and an explicitly selected original ModelCenter registration, with cancel/rebuild/invalidate/remove. No provider remains NOT_CONFIGURED; real transport contract evidence is not semantic model quality. Keep independent cancellation and old-response/scope fences. Default-OFF/server V1 gates and the original shell/tokens remain unchanged. Fresh final-source browser/geometry evidence remains required after reconstruction.

## Post-Interop Wave2 and native source inspector

Preserve optional exact scene IDs, Chapter/Scene timeline ordering, separate epistemic labels and author-versus-character context isolation. Simulator results remain proposals. Style deterministic counts must never become calibrated literary-quality scores. Style and original-history comparison model runs need exact source previews, explicit provider/price/consent, original job cancellation/recovery and separate human review; direct whole-manuscript Accept stays forbidden. Intentional Judge findings collapse without losing review history or existing revision-task references.

The existing AuthorRequestPreview/Controls source picker stores only original IDs/version/digest pointers. Add/remove/pin/exclude changes invalidate receipts. Actual adapter-facing context shows citations, truncation reason and provider/locality; hidden or revoked sources cannot reappear from persisted jobs. Exact structured search targets remain scope/session/version-bound and preserve dirty editor drafts. Keep current unavailable-target and explicit retry messaging, and never dispatch a model during navigation. Existing server default-OFF/V1 gates and shell/tokens remain unchanged.

## Post-Interop Wave4 media and production

Keep original MediaPanel source pickers, cover/storyboard revision/CAS/history, explicit fixture-versus-registered route choice and source-stale labels. Cancellation stays independent of pending execute; navigation only selects the original authorized task/plan. Missing character references must leave independent work visible while prohibiting stale queue/approval. Brief edits retain reference identities, so explain fresh-brief recovery if the original source cannot be restored.

Director suggestions are transparent source-local review aids, not inferred camera geometry or creative-quality scores. Production assurance labels remain independent; measured audio frames are segment evidence only, with unknown speaker/alignment review explicit. OTIO loss acknowledgements remain required. Preserve existing Panel/Button/Field/StatusMessage primitives, tokens, layout order, scope invalidation and default-OFF/server V1 gates; final visual redesign remains a later handoff.

## Post-Interop Wave5 extended creation

TranslationMemoryPanel remains inside the original edition owner. Keep exact source/target-version identity, locked-term reasons, explicit memory reuse and history-restore confirmation; literal drift checks are not translation quality. Comic image briefs/appearance references remain distinct from storyboard review, with approved asset versions and scene lineage visible. InteractiveStoryHistory restores through current original references and CAS, never stale content.

SharedUniversePanel remains within ProjectForksPanel: selected immutable snapshot contents, explicit target work pin, source drift, incoming read-only pin view and human repin/release. Privacy withdrawal must withhold old content without silently merging or mutating target manuscript/Canon. WriterRoom presence stays explicitly unavailable while asynchronous assignment/comments/proposals remain usable. Templates expose version/compatibility and denied permissions; SDK previews never execute imported code. Preserve source-change invalidation, private draft cleanup, default-OFF/server V1 fences and existing shared design tokens/primitives. No final visual redesign is included.

## Exact original model-task reopening

Task Center uses the additive owner_navigation pointer while retaining the legacy source shape. Simulator/Judge/declarative panels select only the matching authorized original job receipt; translation shows the exact original receipt without overwriting dirty segment input. Opening its original segment is a separate action. Missing, withheld or out-of-window tasks remain unavailable instead of selecting unrelated output, and navigation never executes a model. Keep chapter/source scope fences and existing50-edition/50-run bounded translation visibility explicit.

## Browser contract compatibility correction

Retain the inherited production evidence label “确定性协议可复现” and its separate explanation that determinism is established only for synthetic protocols, never arbitrary GPU/model bytes. Source-based controls and fixtures must use the authoritative versioned chapter read, including its exact Markdown heading/whitespace and Unicode offsets. Asset links keep the original required project query; do not weaken permission checks to accommodate missing navigation inputs.
