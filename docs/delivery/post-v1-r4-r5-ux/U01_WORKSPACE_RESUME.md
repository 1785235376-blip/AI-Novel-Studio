# U01: recover the original workspace

Status: IMPLEMENTED / INTEGRATED / CONTRACT_VERIFIED. Hosted browser and real PostgreSQL verification for this delta remain NOT_RUN locally. No model quality claim or user acceptance claim.

## Closed loop

- The enabled current-project entry reads the actor/scope-private server workspace and shows its last chapter and stopping note. Reopening is explicit. The editor re-reads the exact original chapter authority before applying an anchor or layout.
- The local-author File workspace remembers only the selected project ID under a mode/actor-specific browser key. A fresh original project-list response must contain that exact ID before it can be selected on reopening. Authenticated and scoped sessions cannot consume this hint; they retain the existing scoped selection/bootstrap path. A missing or damaged hint leaves an explicit project picker, never silently falls back to the first or a similar branch.
- A local project-switch action preserves the current buffer by refusing to leave a dirty, saving, conflicting, unhydrated or composing chapter. Existing target drafts also block workspace restoration; they remain available through the original chapter/draft recovery controls.
- Search text, type/current-chapter filters, task query/failed-only filter, density and panel section persist in the same versioned private workspace metadata. Inputs typed during a delayed initial read survive it. Layout reset changes only workspace presentation metadata and the current view.
- Reference split visibility and focus state are real App consumers. The checkpoint stores a version pointer to U04's original preference/pin authority, never reference bodies or a duplicate pin list. Changed preference versions preserve current settings; stale/unreadable pins continue to use U04's existing recovery cards.
- Saving a workspace captures at most 50 original unresolved authority/task-ID references. Reading it rechecks original services and current scope before displaying IDs/status. Ready text-generation drafts remain pending review. Completed/accepted states are read live; restoring never creates, retries, cancels or accepts a job. Partial/unavailable sources are visibly qualified.
- Source-version changes, account/project/branch changes, A→B→A navigation, section dismissal, IME, newer typing and stopping-note/split/filter edits fence delayed responses. U07's exact original-generation AbortSignal/source checks and U08 controls remain intact.

## Verification

- Focused backend File suite: 57 passed, 55 real-PostgreSQL cases deselected. Includes both mounted `/api` and `/api/v1`, original JobManager projection, U04 preferences/pins, CAS, version changes, corrupt legacy layouts, revocation and bounded capture.
- Focused frontend suite: 143 passed across 10 files, including original task navigation, broker recovery, draft/IME/conflict recovery, revision history, workspace filters, U04, Workbench and AppShell regression contracts.
- TypeScript project build, Vite production build and design-token guard passed. Vite retains the existing large-App-chunk warning. Playwright collected all five workspace journeys without launching a browser.
- A hosted Chromium journey in `frontend/tests/e2e/r4-workspace.spec.ts` creates two real File projects, selects the actual non-first inventory entry, persists filters and original reference split state, reloads, explicitly restores the exact chapter, and checks missing-project recovery without model execution.
- Local Chromium launch remains blocked by the known platform EPERM limitation and was not retried. The new hosted journey and browser geometry/visual assertions must run in the hosted workflow; authoring/collection is not browser execution.

## Honest boundaries

- Browser storage can be unavailable or cleared. Only the project-selection hint uses it; the server workspace remains recoverable after explicitly selecting the project. No new token storage was introduced.
- Reference and reading-state capture points to the original tool's saved version. Unsaved reading previews are not a second persisted preference store. The checkpoint deliberately will not roll back later pin changes.
- Task snapshots are bounded, source-dependent and manually refreshed. Missing older records require their original tools. No executor or execution authorization is inferred from a remembered ID.
- Cross-scope discovery is not a new permission authority. Existing branch chapter adapters still determine which scoped manuscript sources can be reopened.
