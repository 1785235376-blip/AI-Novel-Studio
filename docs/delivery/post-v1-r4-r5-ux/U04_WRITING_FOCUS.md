# U04 writing focus, source references and inspiration drafts

Status: **IMPLEMENTED / CONTRACT_VERIFIED** for the scoped services and consumer UI below. Editor/shell composition is owned by the integration checkpoint. Browser geometry, hosted execution, real PostgreSQL and final acceptance must be recorded by that checkpoint; this document does not claim them. U04 as a whole remains **PARTIAL** for the explicitly listed boundaries.

## Reuse and user journey

- `WritingFocusPanel` operates on the existing TipTap editor through typed callbacks. It does not instantiate an editor, save prose, replace the document or grant AI-edit permissions.
- Author/project/workspace/storyline/branch-scoped column width, font size, line height and paragraph emphasis use the existing `ExperimentalStore`, `DomainService`, row history and optimistic versions. Focus itself is transient host UI state, not a saved document mutation.
- `WritingReferenceRail` displays existing character/location records and chapter text as read-only source projections beside the existing editor. At most six pin identities/digests are saved, not duplicate entities or a parallel research store. Refresh rechecks sources; changed/hidden/missing cards stop displaying their content and require the author to repin or remove them.
- Existing chapter reference pins also serve as chapter-start bookmarks. The panel offers explicit save/update/open actions and current-version recovery. The open endpoint rechecks chapter identity/digest/version before requesting existing editor navigation; it never silently repins a changed source.
- Chapter/scene overview reuses `ChapterTree` chapter IDs and the existing StoryDatabase `scenes` dataset. Current-chapter or bounded whole-project cards show real scene title, purpose, conflict and outcome, with an entry back to the existing StoryDatabase for edits. No duplicate chapter, scene or bookmark collection is created.
- Inspiration capture creates owner-private project/branch drafts. These records are absent from Canon, manuscript and model context paths. Optional chapter linkage captures the actual saved chapter ID/version/digest. Local input is retained after error/conflict and when a pending save completes after more typing. It is not an offline durable draft before a successful server save; the UI says so.
- Notes can be edited with CAS, archived and restored. Creation has a stable capture key for bounded safe replay. A newer input receives a new key. No permanent delete is offered.
- Explicit copy requires selecting an existing active planning node and field, seeing before/after text and checking a review acknowledgement. The server binds the preview to note version, target version/content, source digests and ancestor versions. The result is a `PlanningService` **REVIEW** proposal, created atomically with the note's copy receipt. It does not change the target node, approve planning, modify Canon or add an AI context selection. Repeating the same committed preview returns its existing receipt.

## Integration contract

`WritingFocusPanel` accepts `client`, optional `chapter`, `flags`, `focusActive`, `onFocusChange(active)`, `onPreferencesChange(preferences)`, `onReferencesChange()` and `onNavigate(WorkspaceNavigation)`. It exports the `WritingFocusPreferences` type and `defaultWritingPreferences`.

`WritingReferenceRail({ client, revision })` should be a sibling of the existing `ChapterEditor` inside `.writing-focus-split`. Increment `revision` after `onReferencesChange`. Do not change the editor's key or conditionally remount it to enable focus. Keep save controls, conflict/error notices and the shell status visible. Collapse the existing inspector using its existing consumer contract, and restore its prior collapsed state on exit.

Use `.writing-focus-editor` and `--writing-column-width`, `--writing-font-size`, `--writing-line-height` on the existing editor. Paragraph emphasis is DOM-only via `.writing-paragraph-focus` and `data-writing-active` / `data-writing-inactive`; no document node attributes or marks are persisted. Focus buttons prevent mouse-down from collapsing the editor selection. There is no global keyboard listener. The note textarea supports Ctrl/Command+Enter only outside composition; ordinary Enter remains text input.

The composition root registers `WritingFocusService(store, novel_service, chapter_service, planning=planning_service)` with `create_writing_focus_router(service, authorize, require_flag)` under the server-owned `writing_focus_v2` feature. Planning targets/preview/copy additionally require `advanced_planning_v2`.

## Authority and privacy

Every route runs the existing authorization resolver with `domain.read` or `domain.write`. Mutations check current feature flags and reauthorize the original captured session/branch immediately before committing; a changed actor/scope aborts the transaction. Request bodies cannot supply actor, permissions, Canon state, AI context inclusion or arbitrary preference fields.

Missing collaboration source adapters fail closed. Base manuscript/entity records are never silently substituted for branch evidence. Injected readers must return the matching branch ID. Local character/location projection uses a fixed descriptive-field allowlist and excludes hidden/private/secret rows; arbitrary source metadata and secrets are not rendered. API/UI never render external HTML.

No network/provider/model calls, background scans, process launches, credentials or settings changes are introduced. Reads are bounded (50 reference results, 12,000 characters per card, 100 recent notes per requested archive state). Older notes remain in the scoped store. Pins and references are refreshed manually, not by a hidden polling loop.

The feature uses additive collections in the existing experimental scope document/table; no new SQL migration and no legacy-data conversion. Turning the feature off retains inaccessible experimental data. V1 acceptance-mode/default-off enforcement remains in the central feature authority.

## Endpoints

Under `/api/novels/{nid}/experimental/writing-focus`:

- `GET/PUT /preferences`: versioned author-scoped preferences and pins
- `GET /references`, `GET /pins`: current authorized read-only projections
- `GET /overview`: bounded read-only existing chapter/scene projection
- `POST /bookmarks/open`: source-checked chapter-start navigation, explicit current-version recovery
- `GET/POST /notes`, `PUT /notes/{id}`: draft listing, capture and edit
- `POST /notes/{id}/archive`, `/restore`: recoverable transitions
- `GET /planning-targets`: active existing planning nodes
- `POST /notes/{id}/planning/preview`, `/copy`: reviewed copy into existing planning proposals

## Focused verification at source checkpoint

- `../r2-run.sh python -m pytest tests/test_r4_writing_focus.py -q`: **15 passed**, **15 skipped**. File persistence/restart, owner/scope isolation, branch fail-closed, CAS concurrency, corruption recovery, pin source changes, reference projection, archive/restore, creation replay, reviewed-copy atomicity/replay, stale/oversized preview, current authorization, flag revocation, existing scene projection and bookmark recovery passed. PostgreSQL parameters skipped because this focused invocation did not provide `TEST_POSTGRES_DATABASE_URL`; they are not mock-PostgreSQL passes.
- `../r2-run.sh bash -c 'cd frontend && pnpm exec vitest run src/experimental/WritingFocusPanel.test.tsx'`: **13 passed**. StrictMode, captured requests, A → B → A stale callbacks, preference conflicts, pending-input preservation, IME/repeated-submit suppression, explicit reviewed copy, preview invalidation, reference error/stale states, chapter bookmark navigation, scene overview and late chapter A → B → A response fencing.
- TypeScript build and existing UI token lint passed during focused development. The token lint currently scans shared UI only; source review confirmed new CSS uses existing colors/spacing and domain prose choices.
- An incidental full frontend run at the shared working-tree checkpoint showed **683 passed / 6 skipped / 1 failed**, with `AuditGenerationScope.test.tsx` failing on an old generation response after chapter navigation. This is reported to the integrator and is not disguised as an aggregate pass.
- No model-quality, Windows/WebView2, real hardware, real credentials or user acceptance claim is made.

## Explicit remaining U04 boundaries

- Existing word-count, writing-goal and save/conflict status are reused by the host. A new independent goal tracker is intentionally not created.
- Bookmark/overview reconciliation: ChapterTree already provides the authoritative chapter list and selection; StoryDatabase already provides real scene CRUD and links. The narrow U04 entry now reuses both, adding chapter-start bookmarks through existing U04 pins and read-only chapter/scene cards. WorkspaceTools' older `pinned_chapter_ids` resume metadata had no author-facing pin controls; it remains unchanged rather than introducing another synced bookmark source. Paragraph-position bookmarks are not claimed.
- Explicit per-paragraph AI-edit locks remain a tracked dependency on **A11/U05 acceptance enforcement**: the future acceptance path must reject edits to locked ranges, version/rebase those ranges and require clear manual unlock. Visual paragraph emphasis is not that enforcement and is labeled accordingly; no OS file-protection claim is made.
- Moving notes into chapter prose is not provided. The supported reviewed path is copy into existing planning proposals, with the source note retained.
- Missing collaboration reference adapters and real browser/PG evidence remain separate boundaries until the integration checkpoint supplies and verifies them.
