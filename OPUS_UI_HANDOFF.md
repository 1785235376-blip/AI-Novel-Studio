# Opus UI handoff · R2 engineering candidate

Repository: `1785235376-blip/AI-Novel-Studio` · branch `work/dot-astra-v1-rc-r2` · Draft PR [#37](https://github.com/1785235376-blip/AI-Novel-Studio/pull/37).

This is the functional/interaction handoff. The current tree is still undergoing final integration. Use the PR head and `git rev-parse HEAD` to identify the exact revision; final-SHA receipts are published in the PR and `docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md`. No merge, release or production deployment is approved.

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
