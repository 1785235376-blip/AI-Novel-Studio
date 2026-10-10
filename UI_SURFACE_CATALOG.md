# UI Surface Catalog

Source-derived companion to [Final Product Surface Map](FINAL_PRODUCT_SURFACE_MAP.md). Actual mounted [API_CATALOG.json](API_CATALOG.json) / [API_CATALOG.md](API_CATALOG.md) plus [API_CATALOG_DETAIL.json.gz](API_CATALOG_DETAIL.json.gz) and [API_OPENAPI.json.gz](API_OPENAPI.json.gz) is authoritative for generated routes; tests/test_surface_api_catalog.py checks source-bound consistency only; `/api[/v1]` denotes the two existing aliases. No endpoint inventory entry is a test-execution claim. Complete schema fields/lifecycle/state/test mapping lives in [JSON](UI_SURFACE_CATALOG.json).

## Write

### U02 · Loss-resistant editing and visible save state

Page: Write → Manuscript / Save and recovery; ENGINEERING_UI.

Components: [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/ui/SaveControls.tsx`](frontend/src/ui/SaveControls.tsx), [`frontend/src/ConflictDialog.tsx`](frontend/src/ConflictDialog.tsx), [`frontend/src/RevisionPanel.tsx`](frontend/src/RevisionPanel.tsx).

Authority: [`frontend/src/drafts.ts`](frontend/src/drafts.ts), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/ui/SaveControls.tsx`](frontend/src/ui/SaveControls.tsx), [`app/autosave/durable.py`](app/autosave/durable.py), [`app/api.py`](app/api.py).

Original ChapterService/current document is durable authority; local draft is a separate recoverable editing buffer. Save uses chapter version and conflict preserves local text.

Abort pending navigation, preserve dirty/IME draft, export corrupted bytes, explicitly reopen recovery, restore creates a new revision. Browser storage removal and never-persisted keystrokes remain outside the recovery guarantee.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| DELETE | `/api[/v1]/chapters/{chapter_id}` | [delete_chapter](app/api.py#L1282) | domain.write |
| GET | `/api[/v1]/chapters/{chapter_id}` | [chapter](app/api.py#L1238) | domain.read |
| PUT | `/api[/v1]/chapters/{chapter_id}` | [update_chapter](app/api.py#L1246) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/archive` | [archive_chapter](app/api.py#L1260) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/duplicate` | [duplicate_chapter](app/api.py#L1293) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/chapters/{chapter_id}/history` | [chapter_history](app/api.py#L1313) | domain.read |
| POST | `/api[/v1]/chapters/{chapter_id}/history/{version}/restore` | [restore_chapter](app/api.py#L1321) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/move` | [move_chapter](app/api.py#L1308) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/rename` | [rename_chapter](app/api.py#L1297) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/restore-archive` | [restore_archived_chapter](app/api.py#L1271) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/export` | [export_audiobook_chapter](app/api.py#L2705) | domain.read |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/queue` | [queue_audiobook_chapter](app/api.py#L2584) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/queue-segments` | [queue_audiobook_segments](app/api.py#L2598) | domain.write |
| GET | `/api[/v1]/novels/{nid}/chapters` | [chapters](app/api.py#L1230) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/chapters` | [create_chapter](app/api.py#L1234) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/chapters/archived` | [archived_chapters](app/api.py#L1232) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/chapters/{chapter_id}/knowledge-base/review` | [create_chapter_knowledge_review](app/api.py#L2006) | domain.write |
| GET | `/api[/v1]/novels/{nid}/chapters/{cid}/privacy` | [get_source_privacy](app/api.py#L3705) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/chapters/{cid}/privacy` | [set_source_privacy](app/api.py#L3715) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/revisions` | [screenplay_revisions](app/api.py#L2190) | Original access helper/default/middleware; see source |

Navigation: CORE_MANUSCRIPT, FS_BRANCH, U01, A11. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U01 · Resume the previous workspace

Page: Write → Continue Working / Workspace resume; ENGINEERING_UI.

Components: [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx).

Authority: [`app/experimental/ux.py`](app/experimental/ux.py), [`frontend/src/store.ts`](frontend/src/store.ts), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`app/experimental/ux_api.py`](app/experimental/ux_api.py), [`frontend/src/experimental/uxClient.ts`](frontend/src/experimental/uxClient.ts), [`frontend/src/ui/scopeLabels.ts`](frontend/src/ui/scopeLabels.ts).

Actor/project/scope-bound resume row stores chapter/version/anchor, layout, reference pointers and original unfinished-task IDs. Resolve rechecks original target authority before navigation. Shared selected-owner labels use supplied nonblank names or exact known IDs; a selected branch without metadata is never called mainline/default storyline. Missing owner IDs stay unselected; local mainline labels apply only to an actual unscoped local manuscript.

CAS save/reset-layout; persisted history; explicit reopen or open-current; dirty/IME/target-draft guards. Restart reads existing pointers and never dispatches a model.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/commands` | [commands](app/experimental/ux_api.py#L77) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/commands/resolve` | [resolve_command](app/experimental/ux_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/export` | [export](app/experimental/ux_api.py#L216) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/preview` | [preview](app/experimental/ux_api.py#L211) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [interaction](app/experimental/ux_api.py#L50) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [save_interaction](app/experimental/ux_api.py#L56) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/history` | [interaction_history](app/experimental/ux_api.py#L61) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/reset` | [reset_interaction](app/experimental/ux_api.py#L72) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/restore` | [restore_interaction](app/experimental/ux_api.py#L67) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [resume](app/experimental/ux_api.py#L88) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [save_resume](app/experimental/ux_api.py#L93) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume/history` | [history](app/experimental/ux_api.py#L103) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/reset-layout` | [reset](app/experimental/ux_api.py#L110) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/resolve` | [resume_resolve](app/experimental/ux_api.py#L98) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/search` | [search](app/experimental/ux_api.py#L172) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/cancel` | [cancel](app/experimental/ux_api.py#L185) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/rebuild` | [rebuild](app/experimental/ux_api.py#L181) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/resolve` | [resolve](app/experimental/ux_api.py#L189) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/tasks` | [tasks](app/experimental/ux_api.py#L199) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/tasks/{authority}/{task_id}/cancel` | [cancel_task](app/experimental/ux_api.py#L205) | Original access helper/default/middleware; see source |

Navigation: U02, U03, U04, U07, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U03 · Search, commands and recents

Page: Write → Global search / Recents; ENGINEERING_UI.

Components: [`frontend/src/experimental/WorkspaceSearch.tsx`](frontend/src/experimental/WorkspaceSearch.tsx), [`frontend/src/ui/FeatureLauncher.tsx`](frontend/src/ui/FeatureLauncher.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx).

Authority: [`app/experimental/ux.py`](app/experimental/ux.py), [`app/experimental/search_sources.py`](app/experimental/search_sources.py), [`frontend/src/experimental/WorkspaceSearch.tsx`](frontend/src/experimental/WorkspaceSearch.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/ui/FeatureLauncher.tsx`](frontend/src/ui/FeatureLauncher.tsx), [`app/experimental/ux_api.py`](app/experimental/ux_api.py).

Literal lexical search over original authorized identities; current-source revision is resolved before exact owner navigation. Search is distinct from vector/hybrid retrieval.

Bounded paging, request cancellation and cache invalidation; cancel aborts lookup, not the source job; restart rebuilds/reads current authorized projections. Unknown or withdrawn targets are withheld.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/commands` | [commands](app/experimental/ux_api.py#L77) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/commands/resolve` | [resolve_command](app/experimental/ux_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/export` | [export](app/experimental/ux_api.py#L216) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/preview` | [preview](app/experimental/ux_api.py#L211) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [interaction](app/experimental/ux_api.py#L50) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [save_interaction](app/experimental/ux_api.py#L56) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/history` | [interaction_history](app/experimental/ux_api.py#L61) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/reset` | [reset_interaction](app/experimental/ux_api.py#L72) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/restore` | [restore_interaction](app/experimental/ux_api.py#L67) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [resume](app/experimental/ux_api.py#L88) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [save_resume](app/experimental/ux_api.py#L93) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume/history` | [history](app/experimental/ux_api.py#L103) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/reset-layout` | [reset](app/experimental/ux_api.py#L110) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/resolve` | [resume_resolve](app/experimental/ux_api.py#L98) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/search` | [search](app/experimental/ux_api.py#L172) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/cancel` | [cancel](app/experimental/ux_api.py#L185) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/rebuild` | [rebuild](app/experimental/ux_api.py#L181) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/resolve` | [resolve](app/experimental/ux_api.py#L189) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/tasks` | [tasks](app/experimental/ux_api.py#L199) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/tasks/{authority}/{task_id}/cancel` | [cancel_task](app/experimental/ux_api.py#L205) | Original access helper/default/middleware; see source |

Navigation: FS_SEMANTIC, FS_INTERACTION, U07, A04, A10. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U08 · Context and privacy inspector

Page: Write → Context inspector / Cost and privacy preview; ENGINEERING_UI.

Components: [`frontend/src/novel/AiContextPreviewPanel.tsx`](frontend/src/novel/AiContextPreviewPanel.tsx), [`frontend/src/novel/AuthorRequestPreviewPanel.tsx`](frontend/src/novel/AuthorRequestPreviewPanel.tsx), [`frontend/src/novel/AuthorRequestControls.tsx`](frontend/src/novel/AuthorRequestControls.tsx), [`frontend/src/novel/AuthorSourceItems.tsx`](frontend/src/novel/AuthorSourceItems.tsx), [`frontend/src/novel/SourcePrivacyControl.tsx`](frontend/src/novel/SourcePrivacyControl.tsx), [`frontend/src/useScopedRequestConsent.tsx`](frontend/src/useScopedRequestConsent.tsx).

Authority: [`app/author_context_sources.py`](app/author_context_sources.py), [`app/author_request.py`](app/author_request.py), [`app/experimental/author_context_api.py`](app/experimental/author_context_api.py), [`app/jobs.py`](app/jobs.py), [`frontend/src/novel/AuthorSourceItems.tsx`](frontend/src/novel/AuthorSourceItems.tsx), [`frontend/src/novel/AuthorRequestPreviewPanel.tsx`](frontend/src/novel/AuthorRequestPreviewPanel.tsx), [`app/api.py`](app/api.py).

The actual request builder and digest-bound source/version/privacy/route preflight own prompt preview; source pointers are resolved, never trusted inline payloads.

Preview cancellation is read-only; dispatch repeats current source/permission checks; stale preview requires re-review. Restart requires fresh preflight; unknown usage/cost remains unknown.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/agents/{agent_id}/context-preview` | [agent_context_preview](app/api.py#L962) | domain.read |
| POST | `/api[/v1]/audio/generate` | [generate_audio](app/api.py#L2514) | domain.write |
| GET | `/api[/v1]/context-preview` | [context_preview](app/api.py#L1567) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generate/{operation}` | [generate](app/api.py#L1404) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generate/{operation}/variants` | [generate_variants](app/api.py#L1439) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/generation-groups/{group_id}` | [generation_group](app/api.py#L1457) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/generation/{jid}` | [generation](app/api.py#L1467) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/accept` | [accept](app/api.py#L1550) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/cancel` | [cancel](app/api.py#L1516) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/generation/{jid}/events` | [events](app/api.py#L1474) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/reject` | [reject](app/api.py#L1561) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/retry` | [retry_generation](app/api.py#L1524) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/harness/context` | [harness_context](app/api.py#L887) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/harness/context-contract` | [harness_context_contract](app/api.py#L859) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/images/generate` | [generate_image](app/api.py#L2430) | domain.write |
| GET | `/api[/v1]/novels/{nid}/chapters/{cid}/privacy` | [get_source_privacy](app/api.py#L3705) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/chapters/{cid}/privacy` | [set_source_privacy](app/api.py#L3715) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/privacy` | [motion_privacy_review](app/api.py#L3690) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/privacy` | [update_motion_privacy](app/api.py#L3695) | domain.write |

Navigation: CORE_GENERATION, A06, A05, A10, FS_CANON. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U04 · Focus, reference split and inspiration

Page: Write → Focus / Reference split / Inspiration; ENGINEERING_UI.

Components: [`frontend/src/experimental/WritingFocusPanel.tsx`](frontend/src/experimental/WritingFocusPanel.tsx), [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx).

Authority: [`app/experimental/writing_focus.py`](app/experimental/writing_focus.py), [`frontend/src/experimental/WritingFocusPanel.tsx`](frontend/src/experimental/WritingFocusPanel.tsx), [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`app/experimental/writing_focus_api.py`](app/experimental/writing_focus_api.py).

Existing editor remains single prose authority; focus preferences/reference pins are scoped metadata; inspiration is an independent private draft until explicit planning proposal creation.

Preference/pin versions, history and current source checks; cancel retains unsaved editor; restart resolves original references. Paragraph emphasis is not an AI write lock.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/novels/{nid}/experimental/writing-focus/bookmarks/open` | [open_bookmark](app/experimental/writing_focus_api.py#L48) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writing-focus/notes` | [notes](app/experimental/writing_focus_api.py#L57) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writing-focus/notes` | [create_note](app/experimental/writing_focus_api.py#L62) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/writing-focus/notes/{note_id}` | [edit_note](app/experimental/writing_focus_api.py#L67) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writing-focus/notes/{note_id}/planning/copy` | [copy_to_planning](app/experimental/writing_focus_api.py#L85) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writing-focus/notes/{note_id}/planning/preview` | [preview_copy](app/experimental/writing_focus_api.py#L81) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writing-focus/notes/{note_id}/{action}` | [transition](app/experimental/writing_focus_api.py#L72) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writing-focus/overview` | [overview](app/experimental/writing_focus_api.py#L52) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writing-focus/pins` | [pins](app/experimental/writing_focus_api.py#L43) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writing-focus/planning-targets` | [targets](app/experimental/writing_focus_api.py#L77) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writing-focus/preferences` | [preferences](app/experimental/writing_focus_api.py#L28) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/writing-focus/preferences` | [save_preferences](app/experimental/writing_focus_api.py#L33) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writing-focus/references` | [references](app/experimental/writing_focus_api.py#L38) | Original access helper/default/middleware; see source |

Navigation: U02, U01, FS_PLANNING, A11. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U05 · Selection assistant and partial accept

Page: Write → Selection assistant / Partial accept; ENGINEERING_UI.

Components: [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx), [`frontend/src/experimental/RevisionIntelligencePanel.tsx`](frontend/src/experimental/RevisionIntelligencePanel.tsx).

Authority: [`app/experimental/revision_intelligence.py`](app/experimental/revision_intelligence.py), [`app/services/generation_service.py`](app/services/generation_service.py), [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx), [`app/experimental/revision_intelligence_api.py`](app/experimental/revision_intelligence_api.py), [`app/api.py`](app/api.py).

Same selection/proposal and original generation owners as A11; saved version, UTF-16 range and paragraph locks bind edits.

Cancel preserves current text; explicit partial accept/reject, fresh preview and rebase. Restart recovers original job/proposal rather than applying a whole candidate.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/audio/generate` | [generate_audio](app/api.py#L2514) | domain.write |
| DELETE | `/api[/v1]/chapters/{chapter_id}` | [delete_chapter](app/api.py#L1282) | domain.write |
| GET | `/api[/v1]/chapters/{chapter_id}` | [chapter](app/api.py#L1238) | domain.read |
| PUT | `/api[/v1]/chapters/{chapter_id}` | [update_chapter](app/api.py#L1246) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/archive` | [archive_chapter](app/api.py#L1260) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/duplicate` | [duplicate_chapter](app/api.py#L1293) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/chapters/{chapter_id}/history` | [chapter_history](app/api.py#L1313) | domain.read |
| POST | `/api[/v1]/chapters/{chapter_id}/history/{version}/restore` | [restore_chapter](app/api.py#L1321) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/move` | [move_chapter](app/api.py#L1308) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/rename` | [rename_chapter](app/api.py#L1297) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/restore-archive` | [restore_archived_chapter](app/api.py#L1271) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generate/{operation}` | [generate](app/api.py#L1404) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generate/{operation}/variants` | [generate_variants](app/api.py#L1439) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/generation-groups/{group_id}` | [generation_group](app/api.py#L1457) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/generation/{jid}` | [generation](app/api.py#L1467) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/accept` | [accept](app/api.py#L1550) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/cancel` | [cancel](app/api.py#L1516) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/generation/{jid}/events` | [events](app/api.py#L1474) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/reject` | [reject](app/api.py#L1561) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/retry` | [retry_generation](app/api.py#L1524) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/images/generate` | [generate_image](app/api.py#L2430) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/export` | [export_audiobook_chapter](app/api.py#L2705) | domain.read |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/queue` | [queue_audiobook_chapter](app/api.py#L2584) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/queue-segments` | [queue_audiobook_segments](app/api.py#L2598) | domain.write |
| GET | `/api[/v1]/novels/{nid}/chapters` | [chapters](app/api.py#L1230) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/chapters` | [create_chapter](app/api.py#L1234) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/chapters/archived` | [archived_chapters](app/api.py#L1232) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/chapters/{chapter_id}/knowledge-base/review` | [create_chapter_knowledge_review](app/api.py#L2006) | domain.write |
| GET | `/api[/v1]/novels/{nid}/chapters/{cid}/privacy` | [get_source_privacy](app/api.py#L3705) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/chapters/{cid}/privacy` | [set_source_privacy](app/api.py#L3715) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/catalog` | [catalog](app/experimental/revision_intelligence_api.py#L53) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons` | [comparisons](app/experimental/revision_intelligence_api.py#L69) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons` | [save_comparison](app/experimental/revision_intelligence_api.py#L74) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons-model/catalog` | [model_catalog](app/experimental/revision_intelligence_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/preview` | [compare](app/experimental/revision_intelligence_api.py#L63) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}` | [comparison](app/experimental/revision_intelligence_api.py#L80) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}` | [edit_comparison](app/experimental/revision_intelligence_api.py#L85) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/cancel` | [model_cancel](app/experimental/revision_intelligence_api.py#L128) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/dispatch` | [model_dispatch](app/experimental/revision_intelligence_api.py#L118) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/opinions/{oid}/{action}` | [model_review](app/experimental/revision_intelligence_api.py#L133) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/preview` | [model_preview](app/experimental/revision_intelligence_api.py#L113) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/refresh` | [model_refresh](app/experimental/revision_intelligence_api.py#L123) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/review` | [review_comparison](app/experimental/revision_intelligence_api.py#L91) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/locks` | [locks](app/experimental/revision_intelligence_api.py#L178) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/locks/unlock` | [unlock_block](app/experimental/revision_intelligence_api.py#L184) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/milestones` | [milestones](app/experimental/revision_intelligence_api.py#L190) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/milestones` | [milestone](app/experimental/revision_intelligence_api.py#L195) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/original-versions` | [versions](app/experimental/revision_intelligence_api.py#L58) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/proposals` | [proposals](app/experimental/revision_intelligence_api.py#L138) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/proposals` | [create](app/experimental/revision_intelligence_api.py#L154) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/proposals/{rid}` | [proposal](app/experimental/revision_intelligence_api.py#L143) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/proposals/{rid}/apply` | [apply](app/experimental/revision_intelligence_api.py#L166) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/proposals/{rid}/preview` | [preview](app/experimental/revision_intelligence_api.py#L160) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/proposals/{rid}/rebase` | [rebase](app/experimental/revision_intelligence_api.py#L172) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/selection` | [selection](app/experimental/revision_intelligence_api.py#L148) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/revisions` | [screenplay_revisions](app/api.py#L2190) | Original access helper/default/middleware; see source |

Navigation: A11, CORE_GENERATION, U02. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U15 · Writing goals and controlled notices

Page: Write → Writing goals / Session / Notices; ENGINEERING_UI.

Components: [`frontend/src/experimental/WritingSessionPanel.tsx`](frontend/src/experimental/WritingSessionPanel.tsx), [`frontend/src/novel/NovelOverviewPanel.tsx`](frontend/src/novel/NovelOverviewPanel.tsx).

Authority: [`app/experimental/writing_sessions.py`](app/experimental/writing_sessions.py), [`frontend/src/experimental/WritingSessionPanel.tsx`](frontend/src/experimental/WritingSessionPanel.tsx), [`frontend/src/novel/NovelOverviewPanel.tsx`](frontend/src/novel/NovelOverviewPanel.tsx), [`app/experimental/writing_sessions_api.py`](app/experimental/writing_sessions_api.py).

Original source/session goal counters and controlled in-app notices; no OS/background/external notification service.

Explicit start/stop/review preferences; persistent session state and source measurements; no duplicate notice on reopening. Restart reads original session.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/writing-sessions` | [overview](app/experimental/writing_sessions_api.py#L20) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writing-sessions` | [start](app/experimental/writing_sessions_api.py#L23) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writing-sessions/notices` | [notices](app/experimental/writing_sessions_api.py#L35) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writing-sessions/notices/acknowledge` | [acknowledge](app/experimental/writing_sessions_api.py#L38) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writing-sessions/preferences/notices` | [preferences](app/experimental/writing_sessions_api.py#L29) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/writing-sessions/preferences/notices` | [save_preferences](app/experimental/writing_sessions_api.py#L32) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/writing-sessions/{sid}` | [update](app/experimental/writing_sessions_api.py#L26) | Original access helper/default/middleware; see source |

Navigation: U01, U07, CORE_MANUSCRIPT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### B05 · Multilingual revisions and terminology

Page: Write → Translation / Memory / Terminology; ENGINEERING_UI.

Components: [`frontend/src/experimental/MultilingualEditionsPanel.tsx`](frontend/src/experimental/MultilingualEditionsPanel.tsx), [`frontend/src/experimental/LanguageTranslationPanel.tsx`](frontend/src/experimental/LanguageTranslationPanel.tsx), [`frontend/src/experimental/TranslationMemoryPanel.tsx`](frontend/src/experimental/TranslationMemoryPanel.tsx).

Authority: [`app/experimental/multilingual_editions.py`](app/experimental/multilingual_editions.py), [`app/experimental/multilingual_translation.py`](app/experimental/multilingual_translation.py), [`frontend/src/experimental/MultilingualEditionsPanel.tsx`](frontend/src/experimental/MultilingualEditionsPanel.tsx), [`frontend/src/experimental/TranslationMemoryPanel.tsx`](frontend/src/experimental/TranslationMemoryPanel.tsx), [`app/experimental/multilingual_editions_api.py`](app/experimental/multilingual_editions_api.py).

Original edition/segment owner retains source version, language and reviewed translation-memory exact matches; terminology and locked preferred terms are explicit rules.

Per-segment save/review/source refresh/history/restore and original translation job cancel; reuse creates DRAFT, never silent retranslation. Restart resolves exact edition/run.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/language-editions` | [editions](app/experimental/multilingual_editions_api.py#L40) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions` | [create](app/experimental/multilingual_editions_api.py#L50) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/language-editions/catalog` | [catalog](app/experimental/multilingual_editions_api.py#L35) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/language-editions/translation/routes` | [translation_routes](app/experimental/multilingual_editions_api.py#L109) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}` | [edition](app/experimental/multilingual_editions_api.py#L45) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/export` | [export](app/experimental/multilingual_editions_api.py#L95) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/export-preview` | [export_preview](app/experimental/multilingual_editions_api.py#L90) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/refresh` | [refresh_sources](app/experimental/multilingual_editions_api.py#L85) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/refresh-preview` | [refresh_preview](app/experimental/multilingual_editions_api.py#L80) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/rules` | [add_rule](app/experimental/multilingual_editions_api.py#L70) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/rules/{rid}/review` | [review_rule](app/experimental/multilingual_editions_api.py#L75) | domain.review |
| PUT | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/segments/{sid}` | [save_segment](app/experimental/multilingual_editions_api.py#L55) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/segments/{sid}/preview` | [preview_segment](app/experimental/multilingual_editions_api.py#L60) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/segments/{sid}/review` | [review_segment](app/experimental/multilingual_editions_api.py#L65) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/segments/{sid}/translation-preview` | [translation_preview](app/experimental/multilingual_editions_api.py#L119) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/segments/{sid}/{action}` | [segment_memory_history](app/experimental/multilingual_editions_api.py#L131) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/translations` | [translations](app/experimental/multilingual_editions_api.py#L114) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/language-editions/{eid}/translations/{rid}/{action}` | [translation_action](app/experimental/multilingual_editions_api.py#L124) | Original access helper/default/middleware; see source |

Navigation: U07, FS_REVIEW, CORE_EXPORT, FS_CANON. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_MANUSCRIPT · Project / Chapter tree / Authoritative manuscript

Page: Write → Project / Chapter tree / Authoritative manuscript; ENGINEERING_UI.

Components: [`frontend/src/novel/ChapterTree.tsx`](frontend/src/novel/ChapterTree.tsx), [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/RevisionPanel.tsx`](frontend/src/RevisionPanel.tsx).

Authority: [`app/services/novel_service.py`](app/services/novel_service.py), [`app/services/chapter_service.py`](app/services/chapter_service.py), [`app/chapter_identity.py`](app/chapter_identity.py), [`app/document.py`](app/document.py), [`app/api.py`](app/api.py), [`app/collaboration_api.py`](app/collaboration_api.py).

Mainline ChapterRepository owns prose, chapter identity/order and revision history; branch authority is FS_BRANCH. Save and restore require original version; conflict retains draft; archive/delete/move use original recovery rules.

Native Windows IME/power-loss acceptance is separate; no snapshot proves native behavior.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| DELETE | `/api[/v1]/chapters/{chapter_id}` | [delete_chapter](app/api.py#L1282) | domain.write |
| GET | `/api[/v1]/chapters/{chapter_id}` | [chapter](app/api.py#L1238) | domain.read |
| PUT | `/api[/v1]/chapters/{chapter_id}` | [update_chapter](app/api.py#L1246) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/archive` | [archive_chapter](app/api.py#L1260) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/duplicate` | [duplicate_chapter](app/api.py#L1293) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/chapters/{chapter_id}/history` | [chapter_history](app/api.py#L1313) | domain.read |
| POST | `/api[/v1]/chapters/{chapter_id}/history/{version}/restore` | [restore_chapter](app/api.py#L1321) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/move` | [move_chapter](app/api.py#L1308) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/rename` | [rename_chapter](app/api.py#L1297) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/chapters/{chapter_id}/restore-archive` | [restore_archived_chapter](app/api.py#L1271) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/audit` | [audit](app/collaboration_api.py#L206) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/bootstrap` | [bootstrap](app/collaboration_api.py#L146) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters` | [chapter_list](app/collaboration_api.py#L177) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters` | [chapter_create](app/collaboration_api.py#L184) | domain.write |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/revisions` | [revisions](app/collaboration_api.py#L215) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/revisions/{version}` | [revision_detail](app/collaboration_api.py#L223) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/snapshots` | [snapshots](app/collaboration_api.py#L232) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/snapshots/{snapshot_id}` | [snapshot_detail](app/collaboration_api.py#L238) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/generations/{generation_id}/snapshot` | [generation_snapshot](app/collaboration_api.py#L247) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/members` | [members](app/collaboration_api.py#L162) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/permissions` | [permissions](app/collaboration_api.py#L172) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/story-database/{resource}` | [story_database](app/collaboration_api.py#L195) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/text-runtime-diagnostics` | [text_runtime_diagnostics](app/collaboration_api.py#L157) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/visual-text-workflow` | [visual_text_workflow](app/collaboration_api.py#L152) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels` | [novels](app/api.py#L1211) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels` | [create_novel](app/api.py#L1214) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/novels/{nid}` | [delete_novel](app/api.py#L1225) | domain.write |
| GET | `/api[/v1]/novels/{nid}` | [get_novel](app/api.py#L1221) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}` | [update_novel](app/api.py#L1223) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/export` | [export_audiobook_chapter](app/api.py#L2705) | domain.read |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/queue` | [queue_audiobook_chapter](app/api.py#L2584) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/queue-segments` | [queue_audiobook_segments](app/api.py#L2598) | domain.write |
| GET | `/api[/v1]/novels/{nid}/chapters` | [chapters](app/api.py#L1230) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/chapters` | [create_chapter](app/api.py#L1234) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/chapters/archived` | [archived_chapters](app/api.py#L1232) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/chapters/{chapter_id}/knowledge-base/review` | [create_chapter_knowledge_review](app/api.py#L2006) | domain.write |
| GET | `/api[/v1]/novels/{nid}/chapters/{cid}/privacy` | [get_source_privacy](app/api.py#L3705) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/chapters/{cid}/privacy` | [set_source_privacy](app/api.py#L3715) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/revisions` | [screenplay_revisions](app/api.py#L2190) | Original access helper/default/middleware; see source |

Navigation: U02, U01, FS_BRANCH, CORE_GENERATION, FS_STORY_DATABASE. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_GENERATION · AI writing / Draft-Diff-Accept / Recovery

Page: Write → AI writing / Draft-Diff-Accept / Recovery; ENGINEERING_UI.

Components: [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx), [`frontend/src/novel/GenerationRecoveryPicker.tsx`](frontend/src/novel/GenerationRecoveryPicker.tsx), [`frontend/src/novel/GenerationWorkflowTimeline.tsx`](frontend/src/novel/GenerationWorkflowTimeline.tsx), [`frontend/src/generationRecovery.ts`](frontend/src/generationRecovery.ts).

Authority: [`app/services/generation_service.py`](app/services/generation_service.py), [`app/jobs.py`](app/jobs.py), [`app/generation_stream.py`](app/generation_stream.py), [`app/api.py`](app/api.py), [`app/experimental/author_context_api.py`](app/experimental/author_context_api.py).

Original JobManager generation attempt, provider/model and captured source/branch remain authority. Preview/dispatch/stream/cancel/recover/review/apply are distinct; late output never applies. Accept uses original document CAS.

Real model/quality/GPU NOT_RUN; unknown paid attempt is not retried automatically; review-owned model tasks cannot be accepted wholesale as prose.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/audio/generate` | [generate_audio](app/api.py#L2514) | domain.write |
| POST | `/api[/v1]/generate/{operation}` | [generate](app/api.py#L1404) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generate/{operation}/variants` | [generate_variants](app/api.py#L1439) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/generation-groups/{group_id}` | [generation_group](app/api.py#L1457) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/generation/{jid}` | [generation](app/api.py#L1467) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/accept` | [accept](app/api.py#L1550) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/cancel` | [cancel](app/api.py#L1516) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/generation/{jid}/events` | [events](app/api.py#L1474) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/reject` | [reject](app/api.py#L1561) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/generation/{jid}/retry` | [retry_generation](app/api.py#L1524) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/images/generate` | [generate_image](app/api.py#L2430) | domain.write |
| GET | `/api[/v1]/novels/{nid}/audiobook/jobs` | [list_audiobook_jobs](app/api.py#L2616) | domain.read |
| POST | `/api[/v1]/novels/{nid}/audiobook/jobs/consume` | [consume_audiobook_jobs](app/api.py#L2684) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/jobs/{job_id}/cancel` | [cancel_audiobook_job](app/api.py#L2654) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/jobs/{job_id}/execute` | [execute_audiobook_job](app/api.py#L2663) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/jobs/{job_id}/retry` | [retry_audiobook_job](app/api.py#L2645) | domain.write |
| GET | `/api[/v1]/novels/{nid}/audiobook/jobs/{job_id}/subtitles.{format}` | [audiobook_job_subtitles](app/api.py#L2633) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/author-context/generate` | [generate](app/experimental/author_context_api.py#L378) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/author-context/generate-variants` | [generate_variants](app/experimental/author_context_api.py#L443) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/author-context/preview` | [preview](app/experimental/author_context_api.py#L341) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/author-context/preview-variants` | [preview_variants](app/experimental/author_context_api.py#L415) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/author-context/sources` | [sources](app/experimental/author_context_api.py#L323) | domain.read |

Navigation: U08, U07, FS_REVIEW, A11. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_BRANCH · Branch manuscript / Fork / Compare / Human merge

Page: Write → Branch manuscript / Fork / Compare / Human merge; ENGINEERING_UI.

Components: [`frontend/src/experimental/BranchManuscriptPanel.tsx`](frontend/src/experimental/BranchManuscriptPanel.tsx), [`frontend/src/experimental/ProjectForksPanel.tsx`](frontend/src/experimental/ProjectForksPanel.tsx).

Authority: [`app/services/branch_manuscript_service.py`](app/services/branch_manuscript_service.py), [`app/repositories/branch_manuscript.py`](app/repositories/branch_manuscript.py), [`app/experimental/branch_manuscript_composition.py`](app/experimental/branch_manuscript_composition.py), [`app/manuscript_sources.py`](app/manuscript_sources.py), [`app/services/export_snapshot_authority.py`](app/services/export_snapshot_authority.py), [`app/application/collaboration_service.py`](app/application/collaboration_service.py), [`app/application/persistence.py`](app/application/persistence.py), [`app/repositories/postgres/generation.py`](app/repositories/postgres/generation.py), [`app/experimental/branch_manuscript_api.py`](app/experimental/branch_manuscript_api.py), [`frontend/src/ui/scopeLabels.ts`](frontend/src/ui/scopeLabels.ts).

Original BranchManuscriptService scoped repository owns actual independent rich prose, immutable chapter identity/version/order/history and receipts. Mainline remains ChapterService. Registered generation/context/GET/SSE/export and Local Interop source readers re-resolve the real branch owner even for retained old IDs; no mainline fallback or marker-only inference. Interop uses frozen-compatible scope-bound wire labels and live exact-owner reverse lookup; only an authorized editor handoff returns native IDs. Shared selected-owner labels use supplied nonblank names or exact known IDs; a selected branch without metadata is never called mainline/default storyline. Missing owner IDs stay unselected; local mainline labels apply only to an actual unscoped local manuscript.

Create/save/restore/archive/tombstone/move; confirmed fork, rich-block three-way compare, human merge and original-owner recovery. Branch transaction/journal is atomic; mainline uncertain write requires exact receipt reconciliation. Durable capacity ceilings fail before commit without silently evicting histories. Shared branch inbox is read-only with exact original review route; counterpart access is rechecked and cancellation stays in the original CAS/read+review endpoint. Collaboration retry needs fresh author preview; restart never dispatches automatically.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/catalog` | [catalog](app/experimental/branch_manuscript_api.py#L134) | domain.write, domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/chapters` | [chapters](app/experimental/branch_manuscript_api.py#L145) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/chapters` | [create](app/experimental/branch_manuscript_api.py#L151) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/chapters/{cid}` | [chapter](app/experimental/branch_manuscript_api.py#L156) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/chapters/{cid}` | [save](app/experimental/branch_manuscript_api.py#L161) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/chapters/{cid}/archive/{action}` | [archive](app/experimental/branch_manuscript_api.py#L176) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/chapters/{cid}/delete` | [delete](app/experimental/branch_manuscript_api.py#L181) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/chapters/{cid}/history` | [history](app/experimental/branch_manuscript_api.py#L166) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/chapters/{cid}/move` | [move](app/experimental/branch_manuscript_api.py#L186) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/chapters/{cid}/restore` | [restore](app/experimental/branch_manuscript_api.py#L171) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/compare` | [compare](app/experimental/branch_manuscript_api.py#L228) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/forks/preview` | [fork_preview](app/experimental/branch_manuscript_api.py#L216) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/forks/{rid}/apply` | [fork_apply](app/experimental/branch_manuscript_api.py#L222) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/merges` | [propose](app/experimental/branch_manuscript_api.py#L234) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/merges/{rid}/apply` | [merge_apply](app/experimental/branch_manuscript_api.py#L257) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/merges/{rid}/recovery` | [recovery](app/experimental/branch_manuscript_api.py#L264) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/merges/{rid}/review` | [merge_review](app/experimental/branch_manuscript_api.py#L245) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/records` | [records](app/experimental/branch_manuscript_api.py#L191) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/sources` | [sources](app/experimental/branch_manuscript_api.py#L207) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/branch-manuscript/{kind}/{rid}/cancel` | [cancel](app/experimental/branch_manuscript_api.py#L270) | domain.review |

Navigation: CORE_MANUSCRIPT, CORE_GENERATION, B09, FS_REALTIME, FS_REVIEW, U07, CORE_ADAPTATION, CORE_INTEROP. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Story

### A04 · Temporal semantic story graph

Page: Story → Semantic Story Graph; ENGINEERING_UI.

Components: [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx).

Authority: [`app/experimental/world.py`](app/experimental/world.py), [`app/experimental/story_graph.py`](app/experimental/story_graph.py), [`app/experimental/story_graph_api.py`](app/experimental/story_graph_api.py), [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx), [`app/experimental/world_api.py`](app/experimental/world_api.py).

Typed original-ID concepts/relations/knowledge events share WorldService records and reviewed graph index; temporal Chapter/Scene boundaries, evidence and source digests control projection.

Edit/review/archive/reopen/history and recompute are versioned; stale relations and forget tombstones suppress invalid knowledge. Pure query/recompute has no fictional background task; cancelled UI reads discard results.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/catalog` | [catalog](app/experimental/story_graph_api.py#L50) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/story-graph/character-context` | [context](app/experimental/story_graph_api.py#L117) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/query` | [query](app/experimental/story_graph_api.py#L110) | domain.read, domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/records` | [records](app/experimental/story_graph_api.py#L55) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/story-graph/records` | [create](app/experimental/story_graph_api.py#L60) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}` | [read](app/experimental/story_graph_api.py#L65) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}` | [edit](app/experimental/story_graph_api.py#L70) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}/history` | [history](app/experimental/story_graph_api.py#L76) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}/impact` | [impact](app/experimental/story_graph_api.py#L81) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}/{action}` | [action](app/experimental/story_graph_api.py#L92) | domain.write, domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/world/canon` | [canon](app/experimental/world_api.py#L60) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/character-state` | [character_state](app/experimental/world_api.py#L70) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/continuity` | [continuity](app/experimental/world_api.py#L65) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records` | [records](app/experimental/world_api.py#L28) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/world/records` | [create_record](app/experimental/world_api.py#L34) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}` | [record](app/experimental/world_api.py#L39) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}` | [edit_record](app/experimental/world_api.py#L44) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}/history` | [history](app/experimental/world_api.py#L49) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}/{action}` | [review](app/experimental/world_api.py#L54) | domain.review, domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/schema` | [schema](app/experimental/world_api.py#L22) | Original access helper/default/middleware; see source |

Navigation: A05, FS_PLANNING, FS_CANON, U03, U06, FS_STORY_DATABASE. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### A05 · Character knowledge and mind state

Page: Story → Character Mind / Viewpoint; ENGINEERING_UI.

Components: [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx), [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx).

Authority: [`app/experimental/story_graph.py`](app/experimental/story_graph.py), [`app/experimental/character_author_context.py`](app/experimental/character_author_context.py), [`app/experimental/author_context_api.py`](app/experimental/author_context_api.py), [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx), [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx), [`app/experimental/story_graph_api.py`](app/experimental/story_graph_api.py).

Same reviewed knowledge-event owner as Story Graph. Author facts, known facts, beliefs, false beliefs, secrets, goals, fears, values, emotion, intent and relationship state remain distinct.

History/CAS/review and stale tombstones come from A04; query abort does not change knowledge. Restart resolves current temporal sources; character-only request rejects author-only additions.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/catalog` | [catalog](app/experimental/story_graph_api.py#L50) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/story-graph/character-context` | [context](app/experimental/story_graph_api.py#L117) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/query` | [query](app/experimental/story_graph_api.py#L110) | domain.read, domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/records` | [records](app/experimental/story_graph_api.py#L55) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/story-graph/records` | [create](app/experimental/story_graph_api.py#L60) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}` | [read](app/experimental/story_graph_api.py#L65) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}` | [edit](app/experimental/story_graph_api.py#L70) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}/history` | [history](app/experimental/story_graph_api.py#L76) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}/impact` | [impact](app/experimental/story_graph_api.py#L81) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/story-graph/records/{rid}/{action}` | [action](app/experimental/story_graph_api.py#L92) | domain.write, domain.review |

Navigation: A04, A01, U08, CORE_GENERATION, FS_STORY_DATABASE. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### A01 · Bounded story simulation

Page: Story → Story Simulator; ENGINEERING_UI.

Components: [`frontend/src/experimental/StorySimulatorPanel.tsx`](frontend/src/experimental/StorySimulatorPanel.tsx).

Authority: [`app/experimental/story_simulator.py`](app/experimental/story_simulator.py), [`app/experimental/story_simulator_model.py`](app/experimental/story_simulator_model.py), [`frontend/src/experimental/StorySimulatorPanel.tsx`](frontend/src/experimental/StorySimulatorPanel.tsx), [`app/experimental/story_simulator_api.py`](app/experimental/story_simulator_api.py).

Bounded hypothetical routes/step outcomes retain current Scene/character/world/Canon/knowledge/constraint fingerprints; model suggestions use original jobs.

Explicit step/cancel/select/save; source/CAS and reviewed-candidate digest; history persists; restart reads state and never advances itself. Saved route becomes a planning proposal only.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/story-simulator/catalog` | [catalog](app/experimental/story_simulator_api.py#L25) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/context` | [context](app/experimental/story_simulator_api.py#L30) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs` | [runs](app/experimental/story_simulator_api.py#L35) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs` | [create](app/experimental/story_simulator_api.py#L45) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs/{rid}` | [run](app/experimental/story_simulator_api.py#L40) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs/{rid}/cancel` | [cancel](app/experimental/story_simulator_api.py#L55) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs/{rid}/model/cancel` | [model_cancel](app/experimental/story_simulator_api.py#L96) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs/{rid}/model/dispatch` | [model_dispatch](app/experimental/story_simulator_api.py#L81) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs/{rid}/model/preview` | [model_preview](app/experimental/story_simulator_api.py#L76) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs/{rid}/model/refresh` | [model_refresh](app/experimental/story_simulator_api.py#L86) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs/{rid}/model/select` | [model_select](app/experimental/story_simulator_api.py#L91) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs/{rid}/save` | [save](app/experimental/story_simulator_api.py#L60) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/story-simulator/runs/{rid}/step` | [step](app/experimental/story_simulator_api.py#L50) | Original access helper/default/middleware; see source |

Navigation: A04, A05, FS_PLANNING, U07, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_CREATION · Creation workbench / Structured plans / Review threads

Page: Story → Creation workbench / Structured plans / Review threads; ENGINEERING_UI.

Components: [`frontend/src/novel/CreationWorkbenchPanel.tsx`](frontend/src/novel/CreationWorkbenchPanel.tsx), [`frontend/src/novel/AIPlanningPanel.tsx`](frontend/src/novel/AIPlanningPanel.tsx).

Authority: [`app/services/creation_workbench_service.py`](app/services/creation_workbench_service.py), [`app/creation_workbench_api.py`](app/creation_workbench_api.py).

Original creation record, PLAN/STYLE source version/digests, immutable history and CAS; explicit DRAFT/APPROVED/ARCHIVED transitions. Review threads preserve current/stale/missing anchors and explicit reopen.

A plan or STYLE approval does not itself alter Canon or prose; generative results remain reviewed proposals.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/creation-records` | [records](app/creation_workbench_api.py#L34) | domain.read |
| POST | `/api[/v1]/novels/{nid}/creation-records` | [create](app/creation_workbench_api.py#L39) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/creation-records/{rid}` | [update](app/creation_workbench_api.py#L44) | domain.write |
| POST | `/api[/v1]/novels/{nid}/creation-records/{rid}/{action}` | [transition](app/creation_workbench_api.py#L49) | domain.write |
| GET | `/api[/v1]/novels/{nid}/creation-reference-data` | [reference_data](app/creation_workbench_api.py#L29) | domain.read |
| GET | `/api[/v1]/novels/{nid}/review-threads` | [comments](app/creation_workbench_api.py#L54) | domain.read |
| POST | `/api[/v1]/novels/{nid}/review-threads` | [create_comment](app/creation_workbench_api.py#L59) | domain.write |
| POST | `/api[/v1]/novels/{nid}/review-threads/{rid}/{action}` | [comment_action](app/creation_workbench_api.py#L64) | domain.write |

Navigation: FS_PLANNING, A02, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_PLANNING · Layered planning / Proposals / Templates

Page: Story → Layered planning / Proposals / Templates; ENGINEERING_UI.

Components: [`frontend/src/experimental/PlanningPanel.tsx`](frontend/src/experimental/PlanningPanel.tsx), [`frontend/src/novel/StoryPlanningWorkspace.tsx`](frontend/src/novel/StoryPlanningWorkspace.tsx), [`frontend/src/experimental/PromotionRecovery.tsx`](frontend/src/experimental/PromotionRecovery.tsx).

Authority: [`app/experimental/planning.py`](app/experimental/planning.py), [`app/services/ai_planning_service.py`](app/services/ai_planning_service.py), [`app/experimental/planning_api.py`](app/experimental/planning_api.py), [`app/ai_planning_api.py`](app/ai_planning_api.py).

Graph/node levels and links use original Chapter/Character/Scene identities, expected node/proposal version and source fingerprint. Generate candidates through explicit adapter; compare/review/history/restore are current-source fenced.

Bounded synchronous planning generation has no invented persistent task; absent real planning adapter remains NOT_CONFIGURED/MOCK_ONLY as reported. Restore creates another review proposal.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/novels/{nid}/experimental/planning/generate` | [generate](app/experimental/planning_api.py#L81) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/planning/graphs` | [graphs](app/experimental/planning_api.py#L36) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/planning/graphs` | [create_graph](app/experimental/planning_api.py#L41) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/planning/graphs/{gid}` | [graph](app/experimental/planning_api.py#L46) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/planning/graphs/{gid}/{action}` | [transition_graph](app/experimental/planning_api.py#L61) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/planning/nodes` | [create_node](app/experimental/planning_api.py#L51) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/planning/nodes/{node_id}` | [edit_node](app/experimental/planning_api.py#L56) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/planning/nodes/{node_id}/{action}` | [transition_node](app/experimental/planning_api.py#L66) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/planning/proposals` | [proposals](app/experimental/planning_api.py#L86) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/planning/proposals` | [create_proposal](app/experimental/planning_api.py#L91) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/planning/proposals/compare` | [compare](app/experimental/planning_api.py#L96) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/planning/proposals/{pid}` | [proposal](app/experimental/planning_api.py#L101) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/planning/proposals/{pid}/history` | [history](app/experimental/planning_api.py#L106) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/planning/proposals/{pid}/restore` | [restore](app/experimental/planning_api.py#L111) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/planning/proposals/{pid}/{action}` | [review](app/experimental/planning_api.py#L116) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/planning/templates` | [templates](app/experimental/planning_api.py#L71) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/planning/templates` | [create_template](app/experimental/planning_api.py#L76) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/planning-runs` | [runs](app/ai_planning_api.py#L28) | domain.read |
| POST | `/api[/v1]/novels/{nid}/planning-runs` | [create](app/ai_planning_api.py#L33) | domain.write |
| GET | `/api[/v1]/novels/{nid}/planning-runs/{rid}` | [get](app/ai_planning_api.py#L42) | domain.read |
| POST | `/api[/v1]/novels/{nid}/planning-runs/{rid}/cancel` | [cancel](app/ai_planning_api.py#L47) | domain.write |
| POST | `/api[/v1]/novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft` | [save](app/ai_planning_api.py#L52) | domain.write |

Navigation: A01, A04, CORE_CREATION, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_CANON · Canon / Evidence / Pending decisions

Page: Story → Canon / Evidence / Pending decisions; ENGINEERING_UI.

Components: [`frontend/src/novel/StoryDatabase.tsx`](frontend/src/novel/StoryDatabase.tsx), [`frontend/src/experimental/WorldPanel.tsx`](frontend/src/experimental/WorldPanel.tsx), [`frontend/src/experimental/InboxPanel.tsx`](frontend/src/experimental/InboxPanel.tsx), [`frontend/src/novel/PendingCanonReviewPanel.tsx`](frontend/src/novel/PendingCanonReviewPanel.tsx), [`frontend/src/novel/pendingCanonReviewClient.ts`](frontend/src/novel/pendingCanonReviewClient.ts).

Authority: [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/services/canon_service.py`](app/services/canon_service.py), [`app/services/pending_canon_review_service.py`](app/services/pending_canon_review_service.py), [`app/services/lore_service.py`](app/services/lore_service.py), [`app/experimental/world.py`](app/experimental/world.py), [`app/repositories/file/canon.py`](app/repositories/file/canon.py), [`app/repositories/postgres/canon.py`](app/repositories/postgres/canon.py), [`app/api.py`](app/api.py), [`app/pending_canon_review_api.py`](app/pending_canon_review_api.py), [`app/experimental/world_api.py`](app/experimental/world_api.py).

Original pending-Canon and approved Canon repositories remain project/mainline authority. Current source snapshot and candidate digest bind explicit preview, reason, human confirmation, expected version and operation ID; branch-only authority never grants project Canon access. Research cannot auto-promote.

Terminal approve/reject is idempotent and opposite transitions conflict. File prepared journal plus deterministic fact receipts supports explicit recover/cancel-before-commit; PostgreSQL facts and decision use one transaction. Missing legacy provenance is explicit; unknown source cannot be approved. History remains after source removal while source bytes are withheld. Exact-final-head tests pending.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/world/canon` | [canon](app/experimental/world_api.py#L60) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/character-state` | [character_state](app/experimental/world_api.py#L70) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/continuity` | [continuity](app/experimental/world_api.py#L65) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records` | [records](app/experimental/world_api.py#L28) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/world/records` | [create_record](app/experimental/world_api.py#L34) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}` | [record](app/experimental/world_api.py#L39) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}` | [edit_record](app/experimental/world_api.py#L44) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}/history` | [history](app/experimental/world_api.py#L49) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}/{action}` | [review](app/experimental/world_api.py#L54) | domain.review, domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/schema` | [schema](app/experimental/world_api.py#L22) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/lore/evidence` | [list_lore_evidence](app/api.py#L3368) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/evidence` | [create_lore_evidence](app/api.py#L3385) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/lore/proposals` | [list_lore_proposals](app/api.py#L3399) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/proposals` | [create_lore_proposal](app/api.py#L3429) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/proposals/{proposal_id}/approve` | [approve_lore_proposal](app/api.py#L3443) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/proposals/{proposal_id}/approve-memory` | [approve_lore_memory](app/api.py#L3465) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/proposals/{proposal_id}/reject` | [reject_lore_proposal](app/api.py#L3454) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/world-rules` | [list_world_rules](app/api.py#L3407) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/world-rules` | [create_world_rule](app/api.py#L3417) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/pending-canon` | [pending](app/api.py#L1570) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/pending-canon/{pid}/approve` | [approve](app/api.py#L1573) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/pending-canon/{pid}/reject` | [reject_pending](app/api.py#L1576) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/pending-canon/review` | [list_pending](app/pending_canon_review_api.py#L27) | domain.read |
| POST | `/api[/v1]/projects/{project_id}/pending-canon/{pending_id}/cancel-recovery` | [cancel](app/pending_canon_review_api.py#L59) | domain.review |
| POST | `/api[/v1]/projects/{project_id}/pending-canon/{pending_id}/preview` | [preview](app/pending_canon_review_api.py#L34) | domain.read |
| POST | `/api[/v1]/projects/{project_id}/pending-canon/{pending_id}/recover` | [recover](app/pending_canon_review_api.py#L50) | domain.review |
| POST | `/api[/v1]/projects/{project_id}/pending-canon/{pending_id}/review` | [review](app/pending_canon_review_api.py#L41) | domain.review |

Navigation: FS_REVIEW, A04, FS_CONTINUITY, A10. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_FORESHADOWING · Foreshadowing / Narrative progress

Page: Story → Foreshadowing / Narrative progress; ENGINEERING_UI.

Components: [`frontend/src/novel/StoryDatabase.tsx`](frontend/src/novel/StoryDatabase.tsx), [`frontend/src/novel/StoryRecordVersionEditor.tsx`](frontend/src/novel/StoryRecordVersionEditor.tsx), [`frontend/src/novel/StoryPlanningWorkspace.tsx`](frontend/src/novel/StoryPlanningWorkspace.tsx), [`frontend/src/novel/ContinuityCheckPanel.tsx`](frontend/src/novel/ContinuityCheckPanel.tsx), [`frontend/src/novel/FindingReviewPanel.tsx`](frontend/src/novel/FindingReviewPanel.tsx).

Authority: [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/services/novel_service.py`](app/services/novel_service.py), [`app/services/narrative_state_service.py`](app/services/narrative_state_service.py), [`app/services/narrative_finding_service.py`](app/services/narrative_finding_service.py), [`app/services/finding_review_service.py`](app/services/finding_review_service.py), [`app/services/narrative_proposal_service.py`](app/services/narrative_proposal_service.py), [`app/narrative.py`](app/narrative.py), [`app/narrative_detection.py`](app/narrative_detection.py), [`app/repositories/story_record_versions.py`](app/repositories/story_record_versions.py), [`app/repositories/file/novel.py`](app/repositories/file/novel.py), [`app/repositories/postgres/novel.py`](app/repositories/postgres/novel.py), [`app/api.py`](app/api.py), [`app/story_record_api.py`](app/story_record_api.py), [`app/finding_review_api.py`](app/finding_review_api.py).

Original foreshadowing row receives private version/source/provenance/history/feedback metadata; original narrative event/proposal identity stays distinct. Versioned editor save binds expected digest and version; narrative findings use source-bound original FindingReviewService, not a Judge substitute.

Retained 20-version history, restore to new version, explicit stale-source refresh, snapshot-bound feedback and actor/project/record local draft recovery. Legacy saves advance opted-in version/history; flag OFF retains legacy editor. Branch headers cannot access project-global rows. Exact source navigation retains dirty/IME/new-navigation guards; synchronous cancel never rolls back a committed save. Native controls remain disabled through SAVE/RESTORE/FEEDBACK and authoritative query settlement. The first allowed post-settlement edit is synchronously persisted under the returned digest/version for explicit local recovery; no accepted keystroke is silently ignored during a busy state. Explicit labels match visible text independently of prefilled values/options.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/story-records/catalog` | [catalog](app/story_record_api.py#L69) | domain.write, domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}` | [get](app/story_record_api.py#L83) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}` | [save](app/story_record_api.py#L88) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}/feedback` | [feedback](app/story_record_api.py#L111) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}/restore` | [restore](app/story_record_api.py#L105) | domain.write |
| GET | `/api[/v1]/novels/{nid}/foreshadowing/reminders` | [foreshadowing_reminders](app/api.py#L1340) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/foreshadowing/{foreshadowing_id}` | [upsert_foreshadowing](app/api.py#L1338) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/chapter-progress` | [list_chapter_progress](app/api.py#L3142) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/chapter-progress` | [record_chapter_progress](app/api.py#L3135) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/character-goals` | [list_character_goals](app/api.py#L3122) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/character-goals` | [create_character_goal](app/api.py#L3118) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/character-goals/{item_id}` | [get_character_goal](app/api.py#L3124) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/character-goals/{item_id}/transition` | [transition_character_goal_api](app/api.py#L3128) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/checks` | [check_narrative_findings](app/api.py#L3202) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/expectations` | [create_narrative_expectation](app/api.py#L3190) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/findings` | [list_narrative_findings](app/api.py#L3210) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/findings/{finding_id}` | [get_narrative_finding](app/api.py#L3213) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/findings/{finding_id}/resolve` | [resolve_narrative_finding](app/api.py#L3218) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/foreshadowing` | [create_narrative_foreshadowing](app/api.py#L3093) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/foreshadowing/{item_id}/transition` | [transition_narrative_foreshadowing](app/api.py#L3187) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/mysteries` | [list_mysteries](app/api.py#L3105) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/mysteries` | [create_mystery](app/api.py#L3101) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/mysteries/{item_id}` | [get_mystery](app/api.py#L3107) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/mysteries/{item_id}/transition` | [transition_mystery_api](app/api.py#L3111) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/proposals` | [list_narrative_proposals](app/api.py#L3156) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/proposals` | [create_narrative_proposal](app/api.py#L3150) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/proposals/{proposal_id}` | [get_narrative_proposal](app/api.py#L3160) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/proposals/{proposal_id}/accept` | [accept_narrative_proposal](app/api.py#L3164) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/proposals/{proposal_id}/reject` | [reject_narrative_proposal](app/api.py#L3174) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/narrative/state` | [narrative_state](app/api.py#L3098) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/threads` | [create_narrative_thread](app/api.py#L3088) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/narrative/threads/{thread_id}/transition` | [transition_narrative_thread](app/api.py#L3184) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/{kind}/review-checks` | [check_findings](app/finding_review_api.py#L31) | domain.write |
| GET | `/api[/v1]/projects/{project_id}/{kind}/review-findings` | [list_findings](app/finding_review_api.py#L24) | domain.read |
| GET | `/api[/v1]/projects/{project_id}/{kind}/review-findings/{finding_id}` | [detail](app/finding_review_api.py#L41) | domain.read |
| GET | `/api[/v1]/projects/{project_id}/{kind}/review-findings/{finding_id}/evidence` | [evidence](app/finding_review_api.py#L55) | domain.read |
| GET | `/api[/v1]/projects/{project_id}/{kind}/review-findings/{finding_id}/history` | [history](app/finding_review_api.py#L48) | domain.read |
| POST | `/api[/v1]/projects/{project_id}/{kind}/review-findings/{finding_id}/review` | [review](app/finding_review_api.py#L62) | domain.review |
| POST | `/api[/v1]/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}/narrative/mysteries/{item_id}/transition` | [scoped_mystery_transition](app/api.py#L1095) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}/narrative/proposals/{proposal_id}/accept` | [scoped_proposal_accept](app/api.py#L1105) | Original access helper/default/middleware; see source |

Navigation: FS_CONTINUITY, FS_PLANNING, CORE_MANUSCRIPT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_TIMELINE · Story timeline / World chronology

Page: Story → Story timeline / World chronology; ENGINEERING_UI.

Components: [`frontend/src/novel/StoryDatabase.tsx`](frontend/src/novel/StoryDatabase.tsx), [`frontend/src/novel/StoryRecordVersionEditor.tsx`](frontend/src/novel/StoryRecordVersionEditor.tsx), [`frontend/src/novel/WorldTimelineView.tsx`](frontend/src/novel/WorldTimelineView.tsx), [`frontend/src/experimental/WorldPanel.tsx`](frontend/src/experimental/WorldPanel.tsx).

Authority: [`app/services/novel_service.py`](app/services/novel_service.py), [`app/experimental/world.py`](app/experimental/world.py), [`app/narrative.py`](app/narrative.py), [`app/lore/continuity.py`](app/lore/continuity.py), [`app/repositories/file/continuity.py`](app/repositories/file/continuity.py), [`app/repositories/postgres/continuity.py`](app/repositories/postgres/continuity.py), [`app/repositories/story_record_versions.py`](app/repositories/story_record_versions.py), [`app/repositories/file/novel.py`](app/repositories/file/novel.py), [`app/repositories/postgres/novel.py`](app/repositories/postgres/novel.py), [`app/api.py`](app/api.py), [`app/story_record_api.py`](app/story_record_api.py), [`app/experimental/world_api.py`](app/experimental/world_api.py).

Original Timeline row identity/public serialization remains authority; private version/source/provenance/history metadata adds expected-digest + expected-version CAS. World HISTORY is a separate reviewed chronology projection, and story time is distinct from media rational time.

File atomic original-row replacement and PostgreSQL project/source locks; 20-version history, restore to new current version, current/stale/unlinked sources, terminal snapshot-bound feedback. Legacy saves advance opted-in history. Explicit draft/conflict recovery and exact source navigation retain manuscript dirty/IME guards; project-only authorization rejects branch headers. Continuity Timeline evidence uses the same original table through a narrow public-ID/storage-ID adapter: UUID events retain keys, opaque IDs use deterministic UUIDv5, public project IDs resolve as slugs, and same-owner retries are append-only. Collision, ambiguity or inconsistent/foreign owner metadata is rejected without rewrite. Native controls remain disabled through SAVE/RESTORE/FEEDBACK and authoritative query settlement. The first allowed post-settlement edit is synchronously persisted under the returned digest/version for explicit local recovery; no accepted keystroke is silently ignored during a busy state. Explicit labels match visible text independently of prefilled values/options.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/story-records/catalog` | [catalog](app/story_record_api.py#L69) | domain.write, domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}` | [get](app/story_record_api.py#L83) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}` | [save](app/story_record_api.py#L88) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}/feedback` | [feedback](app/story_record_api.py#L111) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}/restore` | [restore](app/story_record_api.py#L105) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/canon` | [canon](app/experimental/world_api.py#L60) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/character-state` | [character_state](app/experimental/world_api.py#L70) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/continuity` | [continuity](app/experimental/world_api.py#L65) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records` | [records](app/experimental/world_api.py#L28) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/world/records` | [create_record](app/experimental/world_api.py#L34) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}` | [record](app/experimental/world_api.py#L39) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}` | [edit_record](app/experimental/world_api.py#L44) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}/history` | [history](app/experimental/world_api.py#L49) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}/{action}` | [review](app/experimental/world_api.py#L54) | domain.review, domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/schema` | [schema](app/experimental/world_api.py#L22) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/timeline/{event_id}` | [upsert_timeline_event](app/api.py#L1336) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/world-rules` | [list_world_rules](app/api.py#L3407) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/world-rules` | [create_world_rule](app/api.py#L3417) | Original access helper/default/middleware; see source |

Navigation: FS_CONTINUITY, A04, CORE_MANUSCRIPT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_STORY_DATABASE · Characters / Locations / Relationships / World rules

Page: Story → Characters / Locations / Relationships / World rules; ENGINEERING_UI.

Components: [`frontend/src/novel/StoryDatabase.tsx`](frontend/src/novel/StoryDatabase.tsx), [`frontend/src/novel/StoryRecordVersionEditor.tsx`](frontend/src/novel/StoryRecordVersionEditor.tsx), [`frontend/src/novel/WorldBuildingDashboard.tsx`](frontend/src/novel/WorldBuildingDashboard.tsx), [`frontend/src/novel/WorldRelationshipGraph.tsx`](frontend/src/novel/WorldRelationshipGraph.tsx).

Authority: [`app/services/novel_service.py`](app/services/novel_service.py), [`app/services/lore_service.py`](app/services/lore_service.py), [`app/repositories/structured_cas.py`](app/repositories/structured_cas.py), [`app/repositories/story_record_versions.py`](app/repositories/story_record_versions.py), [`app/repositories/file/novel.py`](app/repositories/file/novel.py), [`app/repositories/postgres/novel.py`](app/repositories/postgres/novel.py), [`app/repositories/postgres/serialization.py`](app/repositories/postgres/serialization.py), [`app/api.py`](app/api.py), [`app/story_record_api.py`](app/story_record_api.py).

Original Character/Location/Relationship rows now share the existing five-kind StoryRecord version owner with Timeline/Foreshadowing. Flag-ON current project editors require exact digest and version; original IDs, sparse public shape, opaque imported fields and privacy survive guarded edits/history/restore. World-rule proposal review retains its original separate owner.

Original File project lock/atomic replacement and PostgreSQL original-row transaction/CAS; 20 retained snapshots, restore to new current version, terminal source-bound feedback and explicit stale-source refresh. Relationships pin exact Character/Timeline identities; exact known Character location pins its digest, historical free text remains unlinked. Owner-keyed local draft/conflict recovery excludes secrets. Legacy OFF/component-only callbacks and historical direct clients remain compatible, advancing existing version metadata. Project Story authority rejects branch-only scope. Native controls remain disabled through SAVE/RESTORE/FEEDBACK and authoritative query settlement. The first allowed post-settlement edit is synchronously persisted under the returned digest/version for explicit local recovery; no accepted keystroke is silently ignored during a busy state. Explicit labels match visible text independently of prefilled values/options.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/novels/{nid}/characters/consistency-check` | [character_consistency_check](app/api.py#L3060) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/characters/{character_id}` | [upsert_character](app/api.py#L1332) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/characters/{character_id}/evolution` | [character_evolution_for_character](app/api.py#L3299) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/characters/{character_id}/evolution` | [create_character_evolution_for_character](app/api.py#L3304) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/characters/{character_id}/memories` | [list_memories_for_character](app/api.py#L3497) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/story-records/catalog` | [catalog](app/story_record_api.py#L69) | domain.write, domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}` | [get](app/story_record_api.py#L83) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}` | [save](app/story_record_api.py#L88) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}/feedback` | [feedback](app/story_record_api.py#L111) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/story-records/{kind}/{rid}/restore` | [restore](app/story_record_api.py#L105) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/locations/{location_id}` | [upsert_location](app/api.py#L1334) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/lore/evidence` | [list_lore_evidence](app/api.py#L3368) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/evidence` | [create_lore_evidence](app/api.py#L3385) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/lore/proposals` | [list_lore_proposals](app/api.py#L3399) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/proposals` | [create_lore_proposal](app/api.py#L3429) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/proposals/{proposal_id}/approve` | [approve_lore_proposal](app/api.py#L3443) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/proposals/{proposal_id}/approve-memory` | [approve_lore_memory](app/api.py#L3465) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/lore/proposals/{proposal_id}/reject` | [reject_lore_proposal](app/api.py#L3454) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/relationships/{relationship_id}` | [upsert_relationship](app/api.py#L1344) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/world-rules` | [list_world_rules](app/api.py#L3407) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/world-rules` | [create_world_rule](app/api.py#L3417) | Original access helper/default/middleware; see source |

Navigation: FS_TIMELINE, FS_FORESHADOWING, FS_CANON, A05, A04, U02. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_UNIVERSE · Shared Universe / Selected snapshots

Page: Story → Shared Universe / Selected snapshots; ENGINEERING_UI.

Components: [`frontend/src/experimental/SharedUniversePanel.tsx`](frontend/src/experimental/SharedUniversePanel.tsx).

Authority: [`app/experimental/project_forks.py`](app/experimental/project_forks.py), [`app/experimental/structured_forks.py`](app/experimental/structured_forks.py), [`app/experimental/project_forks_api.py`](app/experimental/project_forks_api.py).

Original fork service immutable selected Character/Location/Organization/Rule/Timeline snapshots and explicit Main/Sequel/Prequel/Side Story pins; source/target authority and privacy checked.

CAS pin/update/release/history, readonly incoming references; source edits never auto-repin. Restore/reuse requires fresh original-source permission. No separate Canon or implicit author context.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/catalog` | [catalog](app/experimental/project_forks_api.py#L53) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/merges/{mid}/recovery` | [recovery](app/experimental/project_forks_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/merges/{mid}/restore` | [restore](app/experimental/project_forks_api.py#L88) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/preflight` | [preflight](app/experimental/project_forks_api.py#L63) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/records` | [records](app/experimental/project_forks_api.py#L58) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/catalog` | [structured_catalog](app/experimental/project_forks_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/merges/{mid}/recovery` | [structured_recovery](app/experimental/project_forks_api.py#L128) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/merges/{mid}/restore` | [structured_restore](app/experimental/project_forks_api.py#L133) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/preflight` | [structured_preflight](app/experimental/project_forks_api.py#L108) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/records` | [structured_records](app/experimental/project_forks_api.py#L103) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/{rid}/apply` | [structured_apply](app/experimental/project_forks_api.py#L123) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/{rid}/compare` | [structured_compare](app/experimental/project_forks_api.py#L118) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/{rid}/create` | [structured_create](app/experimental/project_forks_api.py#L113) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/catalog` | [universe_catalog](app/experimental/project_forks_api.py#L146) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/incoming` | [universe_incoming](app/experimental/project_forks_api.py#L191) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/incoming/{source_nid}/{pin_id}` | [universe_incoming_snapshot](app/experimental/project_forks_api.py#L196) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pin-preview` | [universe_pin_preview](app/experimental/project_forks_api.py#L171) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pins` | [universe_pins](app/experimental/project_forks_api.py#L166) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pins` | [universe_pin](app/experimental/project_forks_api.py#L176) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pins/{rid}/history` | [universe_pin_history](app/experimental/project_forks_api.py#L186) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pins/{rid}/release` | [universe_release](app/experimental/project_forks_api.py#L181) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/snapshot-preview` | [universe_snapshot_preview](app/experimental/project_forks_api.py#L156) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/snapshots` | [universe_snapshots](app/experimental/project_forks_api.py#L151) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/snapshots` | [universe_create_snapshot](app/experimental/project_forks_api.py#L161) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/{rid}/apply` | [apply](app/experimental/project_forks_api.py#L78) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/{rid}/compare` | [compare](app/experimental/project_forks_api.py#L73) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/{rid}/create` | [create](app/experimental/project_forks_api.py#L68) | Original access helper/default/middleware; see source |

Navigation: B09, A04, FS_CANON. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_ADAPTATION · Adaptation / Blueprint / Screenplay draft

Page: Story → Adaptation / Blueprint / Screenplay draft; ENGINEERING_UI.

Components: [`frontend/src/novel/AdaptationPanel.tsx`](frontend/src/novel/AdaptationPanel.tsx), [`frontend/src/novel/ScreenplayPipelinePanel.tsx`](frontend/src/novel/ScreenplayPipelinePanel.tsx), [`frontend/src/novel/PipelineStatusPanel.tsx`](frontend/src/novel/PipelineStatusPanel.tsx), [`frontend/src/novel/ConstraintImportPreview.tsx`](frontend/src/novel/ConstraintImportPreview.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx).

Authority: [`app/services/adaptation_service.py`](app/services/adaptation_service.py), [`app/services/screenplay_service.py`](app/services/screenplay_service.py), [`app/experimental/adaptation_projection.py`](app/experimental/adaptation_projection.py), [`app/repositories/adaptation_versions.py`](app/repositories/adaptation_versions.py), [`app/repositories/file/novel.py`](app/repositories/file/novel.py), [`app/repositories/postgres/novel.py`](app/repositories/postgres/novel.py), [`app/api.py`](app/api.py), [`app/adaptation_api.py`](app/adaptation_api.py).

Original NovelRepository adaptation_proposals owns revision/history and immutable source rich-document snapshots. Original endpoints delegate to the same adaptation router; explicit project versus branch authority never substitutes mainline. Source-bound drafts capture target version/digest and reviewed draft binding.

Reserved target identities and durable write-intent/checkpoint before materialization; apply uses reviewed target version, including legacy flow. Cancel/recover are explicit flag-gated actions; uncertain writes require provable receipt reconciliation and are never replayed. Real model dispatch is NOT_CONFIGURED until original JobManager/broker admission. Original Task/Review projections carry exact proposal/task/source/target bindings and no generic mutations; App revalidates the exact task with namespace/epoch/abort/dirty guards before opening the existing panel. Capacity ceilings and terminal reserves are explicit; exact-head execution pending. Blueprint editing and proposal commands remain locked through both mutation and authoritative refresh; duplicate requests are suppressed. Errors release the barrier while preserving local conflict text, without silent rebase. Explicit blueprint labels remain exact when prefilled.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/adaptations` | [listing](app/adaptation_api.py#L95) | domain.read |
| POST | `/api[/v1]/novels/{nid}/adaptations` | [create](app/adaptation_api.py#L100) | domain.write |
| GET | `/api[/v1]/novels/{nid}/adaptations/catalog` | [catalog](app/adaptation_api.py#L83) | domain.read, domain.write, domain.review |
| POST | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/actions/{action}` | [action](app/adaptation_api.py#L171) | domain.write |
| POST | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/approve` | [approve](app/adaptation_api.py#L111) | domain.review |
| PUT | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/blueprint` | [blueprint](app/adaptation_api.py#L106) | domain.write |
| GET | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/history` | [history](app/adaptation_api.py#L166) | domain.read |
| POST | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/materialize` | [materialize](app/adaptation_api.py#L116) | domain.write |
| GET | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}` | [task_detail](app/adaptation_api.py#L150) | domain.read |
| POST | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/actions/{action}` | [task_action](app/adaptation_api.py#L176) | domain.write |
| POST | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/apply` | [apply](app/adaptation_api.py#L142) | domain.write |
| POST | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/generate` | [generate](app/adaptation_api.py#L129) | domain.write |
| POST | `/api[/v1]/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/review` | [review](app/adaptation_api.py#L136) | domain.review |
| GET | `/api[/v1]/novels/{nid}/screenplays` | [screenplays](app/api.py#L2178) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays` | [create_screenplay](app/api.py#L2182) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/approve` | [approve_screenplay](app/api.py#L2188) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks` | [create_asset_tasks](app/api.py#L2876) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/cleanup` | [cleanup_asset_tasks](app/api.py#L2889) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/recover` | [recover_asset_tasks](app/api.py#L2885) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/stats` | [screenplay_asset_task_stats](app/api.py#L2893) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}` | [update_asset_task](app/api.py#L2878) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}/execute` | [execute_asset_task](app/api.py#L2880) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}/retry` | [retry_asset_task](app/api.py#L2883) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/assets` | [plan_assets](app/api.py#L2870) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/assets/approve` | [approve_assets](app/api.py#L2872) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/assets/{asset_id}` | [update_asset](app/api.py#L2874) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks` | [create_motion_tasks](app/api.py#L2222) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets` | [list_motion_asset_imports](app/api.py#L2845) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets/retry` | [retry_failed_motion_asset_imports](app/api.py#L2849) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}` | [update_motion_task](app/api.py#L2775) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/asset-reference` | [motion_asset_reference](app/api.py#L2834) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/callback` | [motion_callback](app/api.py#L2812) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/cancel` | [cancel_motion_task](app/api.py#L2789) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/execute` | [execute_motion_task](app/api.py#L2786) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/frame-history` | [motion_frame_history](app/api.py#L2858) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/frames` | [update_motion_frames](app/api.py#L2778) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [motion_asset_import_status](app/api.py#L2841) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [import_motion_asset](app/api.py#L2838) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/download` | [download_motion_asset](app/api.py#L2852) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/retry` | [retry_motion_asset_import](app/api.py#L2855) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/privacy` | [motion_privacy_review](app/api.py#L3690) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/privacy` | [update_motion_privacy](app/api.py#L3695) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/provider` | [update_motion_provider](app/api.py#L2783) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/remote-id` | [set_remote_motion_task_id](app/api.py#L2824) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/result` | [attach_motion_result](app/api.py#L2809) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/result-history` | [motion_result_history](app/api.py#L2830) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/retry` | [retry_motion_task](app/api.py#L2792) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/sync` | [sync_motion_task](app/api.py#L2827) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/pipeline-advance` | [advance_screenplay_pipeline](app/api.py#L2866) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/pipeline-advance-until-gate` | [advance_screenplay_pipeline_until_gate](app/api.py#L2868) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/pipeline-status` | [screenplay_pipeline_status](app/api.py#L2864) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/revise` | [revise_screenplay](app/api.py#L2192) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/revisions` | [screenplay_revisions](app/api.py#L2190) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/scenes/{scene_id}` | [update_screenplay_scene](app/api.py#L2186) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/shots` | [plan_screenplay_shots](app/api.py#L2194) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/shots/approve` | [approve_screenplay_shots](app/api.py#L2196) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/shots/{shot_id}` | [update_screenplay_shot](app/api.py#L2198) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/storyboard` | [plan_storyboard](app/api.py#L2200) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/storyboard/approve` | [approve_storyboard](app/api.py#L2202) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/storyboard/{card_id}` | [update_storyboard](app/api.py#L2204) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions` | [plan_transitions](app/api.py#L2206) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/approve` | [approve_transitions](app/api.py#L2208) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}` | [update_transition](app/api.py#L2210) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/motion-prompt` | [motion_prompt](app/api.py#L2216) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/motion-prompt` | [save_motion_prompt](app/api.py#L2219) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/prompt` | [transition_prompt](app/api.py#L2212) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/suggestion` | [transition_suggestion](app/api.py#L2214) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/visual-continuity` | [visual_continuity](app/api.py#L2862) | Original access helper/default/middleware; see source |

Navigation: FS_BRANCH, CORE_MANUSCRIPT, FS_REVIEW, U07, CORE_SCREENPLAY. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Review

### U06 · Change impact and selective refresh

Page: Review → Change Impact / Selective refresh; ENGINEERING_UI.

Components: [`frontend/src/experimental/ChangeImpactPanel.tsx`](frontend/src/experimental/ChangeImpactPanel.tsx), [`frontend/src/experimental/MediaPanel.tsx`](frontend/src/experimental/MediaPanel.tsx).

Authority: [`app/experimental/media.py`](app/experimental/media.py), [`app/experimental/media_api.py`](app/experimental/media_api.py), [`app/experimental/change_impact.py`](app/experimental/change_impact.py), [`frontend/src/experimental/MediaPanel.tsx`](frontend/src/experimental/MediaPanel.tsx), [`frontend/src/experimental/ChangeImpactPanel.tsx`](frontend/src/experimental/ChangeImpactPanel.tsx), [`app/experimental/change_impact_api.py`](app/experimental/change_impact_api.py).

Original dependency graph and selected media brief/manifest owners; lock, source digest, preflight and expected version bind narrowly selected refresh.

Prepare/execute/cancel per original task; token/late-result fence, persisted refresh records and explicit owner recovery. Image refresh is not a generic video/audio executor.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| PUT | `/api[/v1]/novels/{nid}/experimental/change-impact/locks` | [lock](app/experimental/change_impact_api.py#L37) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/change-impact/preflights` | [preflight](app/experimental/change_impact_api.py#L42) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/change-impact/preflights/{rid}/prepare` | [prepare](app/experimental/change_impact_api.py#L47) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/change-impact/query` | [query](app/experimental/change_impact_api.py#L30) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/change-impact/refreshes` | [refreshes](app/experimental/change_impact_api.py#L52) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/change-impact/refreshes/{rid}/cancel` | [cancel](app/experimental/change_impact_api.py#L64) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/change-impact/refreshes/{rid}/execute` | [execute](app/experimental/change_impact_api.py#L59) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/change-impact/sources` | [sources](app/experimental/change_impact_api.py#L23) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/adapters` | [adapters](app/experimental/media_api.py#L26) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/catalog` | [catalog](app/experimental/media_api.py#L31) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [briefs](app/experimental/media_api.py#L36) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [create_cover](app/experimental/media_api.py#L41) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs/{rid}` | [update_cover](app/experimental/media_api.py#L46) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals` | [proposals](app/experimental/media_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/compare` | [compare](app/experimental/media_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/preview` | [preview](app/experimental/media_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/{action}` | [review](app/experimental/media_api.py#L114) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [storyboard_briefs](app/experimental/media_api.py#L52) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [create_storyboard](app/experimental/media_api.py#L57) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs/{rid}` | [update_storyboard](app/experimental/media_api.py#L62) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [tasks](app/experimental/media_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [queue](app/experimental/media_api.py#L73) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks/{rid}/{action}` | [task_action](app/experimental/media_api.py#L78) | domain.write |

Navigation: A04, A09, A13, CORE_IMAGES, FS_PLANNING. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### A02 · Style metrics and drift

Page: Review → Style DNA / Drift / Opinions; ENGINEERING_UI.

Components: [`frontend/src/experimental/StyleAnalysisPanel.tsx`](frontend/src/experimental/StyleAnalysisPanel.tsx), [`frontend/src/experimental/StyleAnalysisModelPanel.tsx`](frontend/src/experimental/StyleAnalysisModelPanel.tsx).

Authority: [`app/experimental/style_analysis.py`](app/experimental/style_analysis.py), [`app/experimental/style_analysis_model.py`](app/experimental/style_analysis_model.py), [`frontend/src/experimental/StyleAnalysisPanel.tsx`](frontend/src/experimental/StyleAnalysisPanel.tsx), [`frontend/src/experimental/StyleAnalysisModelPanel.tsx`](frontend/src/experimental/StyleAnalysisModelPanel.tsx), [`app/experimental/style_analysis_api.py`](app/experimental/style_analysis_api.py).

Original STYLE creation record plus immutable analysis receipt, exact source ranges and deterministic metrics. Model opinions retain original jobs and reviewed evidence.

CAS profile/opinion review, model cancel/refresh and stored history; source changes make analysis stale. Ignore/reopen is supported; it is not cross-run intentional dedup.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/style-analysis/analyses` | [analyses](app/experimental/style_analysis_api.py#L48) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/style-analysis/analyses` | [analyze](app/experimental/style_analysis_api.py#L52) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/style-analysis/analyses/{rid}` | [analysis](app/experimental/style_analysis_api.py#L56) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/cancel` | [model_cancel](app/experimental/style_analysis_api.py#L84) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/dispatch` | [model_dispatch](app/experimental/style_analysis_api.py#L76) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/preview` | [model_preview](app/experimental/style_analysis_api.py#L72) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/refresh` | [model_refresh](app/experimental/style_analysis_api.py#L80) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/style-analysis/analyses/{rid}/opinions/{opinion_id}/review` | [review_opinion](app/experimental/style_analysis_api.py#L88) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/style-analysis/catalog` | [catalog](app/experimental/style_analysis_api.py#L28) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/style-analysis/model/catalog` | [model_catalog](app/experimental/style_analysis_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/style-analysis/profiles` | [create](app/experimental/style_analysis_api.py#L32) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/style-analysis/profiles/{rid}` | [edit](app/experimental/style_analysis_api.py#L36) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/style-analysis/profiles/{rid}/preview` | [preview](app/experimental/style_analysis_api.py#L40) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/style-analysis/profiles/{rid}/{action}` | [transition](app/experimental/style_analysis_api.py#L44) | domain.review |

Navigation: CORE_CREATION, U08, U07, A11. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### A03 · Evidence-based narrative judge

Page: Review → Narrative Judge / Finding review; ENGINEERING_UI.

Components: [`frontend/src/experimental/NarrativeJudgePanel.tsx`](frontend/src/experimental/NarrativeJudgePanel.tsx), [`frontend/src/experimental/NarrativeJudgeModelPanel.tsx`](frontend/src/experimental/NarrativeJudgeModelPanel.tsx), [`frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx`](frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx).

Authority: [`app/experimental/narrative_judge.py`](app/experimental/narrative_judge.py), [`app/experimental/narrative_judge_model.py`](app/experimental/narrative_judge_model.py), [`app/experimental/writer_room.py`](app/experimental/writer_room.py), [`frontend/src/experimental/NarrativeJudgePanel.tsx`](frontend/src/experimental/NarrativeJudgePanel.tsx), [`frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx`](frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx), [`app/experimental/narrative_judge_api.py`](app/experimental/narrative_judge_api.py).

Evidence-bound deterministic findings and separate model advice; accept/ignore/intentional decisions use exact evidence keys and retain reason/review history.

Same-evidence intentional suppression and explicit reopen; source version/CAS; model cancel/refresh; create original WriterRoom revision task. Approval never applies manuscript or Canon.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/narrative-judge/catalog` | [catalog](app/experimental/narrative_judge_api.py#L27) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/narrative-judge/findings/{rid}/review` | [review](app/experimental/narrative_judge_api.py#L47) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/narrative-judge/findings/{rid}/revision-task` | [revision_task_catalog](app/experimental/narrative_judge_api.py#L59) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/narrative-judge/findings/{rid}/revision-task` | [revision_task](app/experimental/narrative_judge_api.py#L64) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/narrative-judge/model/catalog` | [model_catalog](app/experimental/narrative_judge_api.py#L78) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/narrative-judge/runs` | [runs](app/experimental/narrative_judge_api.py#L32) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/narrative-judge/runs` | [create](app/experimental/narrative_judge_api.py#L42) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/narrative-judge/runs/{rid}` | [run](app/experimental/narrative_judge_api.py#L37) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/narrative-judge/runs/{rid}/model/cancel` | [model_cancel](app/experimental/narrative_judge_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/narrative-judge/runs/{rid}/model/dispatch` | [model_dispatch](app/experimental/narrative_judge_api.py#L88) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/narrative-judge/runs/{rid}/model/preview` | [model_preview](app/experimental/narrative_judge_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/narrative-judge/runs/{rid}/model/refresh` | [model_refresh](app/experimental/narrative_judge_api.py#L93) | Original access helper/default/middleware; see source |

Navigation: B08, FS_REVIEW, U07, A11, FS_CONTINUITY. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### A11 · Revision intelligence and partial changes

Page: Review → Revision Intelligence / Comparison; ENGINEERING_UI.

Components: [`frontend/src/experimental/RevisionIntelligencePanel.tsx`](frontend/src/experimental/RevisionIntelligencePanel.tsx), [`frontend/src/experimental/RevisionComparisonModelPanel.tsx`](frontend/src/experimental/RevisionComparisonModelPanel.tsx).

Authority: [`app/experimental/revision_intelligence.py`](app/experimental/revision_intelligence.py), [`app/experimental/revision_intelligence_model.py`](app/experimental/revision_intelligence_model.py), [`app/experimental/revision_intelligence_api.py`](app/experimental/revision_intelligence_api.py), [`frontend/src/experimental/RevisionIntelligencePanel.tsx`](frontend/src/experimental/RevisionIntelligencePanel.tsx), [`frontend/src/experimental/RevisionComparisonModelPanel.tsx`](frontend/src/experimental/RevisionComparisonModelPanel.tsx).

Original ChapterService history and rich-document version/range/digest own comparison; model opinions, partial proposals, locks and milestones reference those originals.

Compare/review/rebase/partial apply uses original CAS and exact preview; stale acceptance denied. Cancel model through original job; restart keeps proposal/history and needs revalidation.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/catalog` | [catalog](app/experimental/revision_intelligence_api.py#L53) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons` | [comparisons](app/experimental/revision_intelligence_api.py#L69) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons` | [save_comparison](app/experimental/revision_intelligence_api.py#L74) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons-model/catalog` | [model_catalog](app/experimental/revision_intelligence_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/preview` | [compare](app/experimental/revision_intelligence_api.py#L63) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}` | [comparison](app/experimental/revision_intelligence_api.py#L80) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}` | [edit_comparison](app/experimental/revision_intelligence_api.py#L85) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/cancel` | [model_cancel](app/experimental/revision_intelligence_api.py#L128) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/dispatch` | [model_dispatch](app/experimental/revision_intelligence_api.py#L118) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/opinions/{oid}/{action}` | [model_review](app/experimental/revision_intelligence_api.py#L133) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/preview` | [model_preview](app/experimental/revision_intelligence_api.py#L113) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/model/refresh` | [model_refresh](app/experimental/revision_intelligence_api.py#L123) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/comparisons/{rid}/review` | [review_comparison](app/experimental/revision_intelligence_api.py#L91) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/locks` | [locks](app/experimental/revision_intelligence_api.py#L178) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/locks/unlock` | [unlock_block](app/experimental/revision_intelligence_api.py#L184) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/milestones` | [milestones](app/experimental/revision_intelligence_api.py#L190) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/milestones` | [milestone](app/experimental/revision_intelligence_api.py#L195) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/original-versions` | [versions](app/experimental/revision_intelligence_api.py#L58) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/proposals` | [proposals](app/experimental/revision_intelligence_api.py#L138) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/proposals` | [create](app/experimental/revision_intelligence_api.py#L154) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/revisions/proposals/{rid}` | [proposal](app/experimental/revision_intelligence_api.py#L143) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/proposals/{rid}/apply` | [apply](app/experimental/revision_intelligence_api.py#L166) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/proposals/{rid}/preview` | [preview](app/experimental/revision_intelligence_api.py#L160) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/proposals/{rid}/rebase` | [rebase](app/experimental/revision_intelligence_api.py#L172) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/revisions/selection` | [selection](app/experimental/revision_intelligence_api.py#L148) | Original access helper/default/middleware; see source |

Navigation: U05, CORE_MANUSCRIPT, U02, U07, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U11 · Reading, proofreading and publishing checks

Page: Review → Reader / Proofreading / Export preflight; ENGINEERING_UI.

Components: [`frontend/src/experimental/ReaderPreflightPanel.tsx`](frontend/src/experimental/ReaderPreflightPanel.tsx), [`frontend/src/novel/ExportPanel.tsx`](frontend/src/novel/ExportPanel.tsx).

Authority: [`app/experimental/reader_preflight.py`](app/experimental/reader_preflight.py), [`app/services/export_job_service.py`](app/services/export_job_service.py), [`frontend/src/experimental/ReaderPreflightPanel.tsx`](frontend/src/experimental/ReaderPreflightPanel.tsx), [`frontend/src/novel/ExportPanel.tsx`](frontend/src/novel/ExportPanel.tsx), [`app/experimental/reader_preflight_api.py`](app/experimental/reader_preflight_api.py).

Read/proof/source snapshot and publish/export checks remain advisory until original export owner is explicitly invoked.

Versioned preflight/history/current-source checks; cancel discards bounded read; restart regenerates current preflight. Native publishing/layout acceptance stays NOT_RUN.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/novels/{nid}/experimental/reader-preflight/annotations` | [annotate](app/experimental/reader_preflight_api.py#L35) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/reader-preflight/check` | [check](app/experimental/reader_preflight_api.py#L41) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/reader-preflight/ignore` | [ignore](app/experimental/reader_preflight_api.py#L38) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/reader-preflight/open` | [open_anchor](app/experimental/reader_preflight_api.py#L32) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/reader-preflight/proof` | [proof](app/experimental/reader_preflight_api.py#L29) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/reader-preflight/read` | [read](app/experimental/reader_preflight_api.py#L26) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/reader-preflight/settings` | [settings](app/experimental/reader_preflight_api.py#L20) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/reader-preflight/settings` | [save](app/experimental/reader_preflight_api.py#L23) | Original access helper/default/middleware; see source |

Navigation: CORE_EXPORT, A03, A11, U16. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_CONTINUITY · Continuity / Evidence / Author feedback

Page: Review → Continuity / Evidence / Author feedback; ENGINEERING_UI.

Components: [`frontend/src/novel/ContinuityCheckPanel.tsx`](frontend/src/novel/ContinuityCheckPanel.tsx), [`frontend/src/novel/FindingReviewPanel.tsx`](frontend/src/novel/FindingReviewPanel.tsx), [`frontend/src/novel/findingReviewClient.ts`](frontend/src/novel/findingReviewClient.ts), [`frontend/src/experimental/WorldPanel.tsx`](frontend/src/experimental/WorldPanel.tsx).

Authority: [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/services/continuity_finding_service.py`](app/services/continuity_finding_service.py), [`app/services/finding_review_service.py`](app/services/finding_review_service.py), [`app/lore/continuity.py`](app/lore/continuity.py), [`app/lore/continuity_engine.py`](app/lore/continuity_engine.py), [`app/lore/continuity_rules.py`](app/lore/continuity_rules.py), [`app/repositories/file/continuity.py`](app/repositories/file/continuity.py), [`app/repositories/postgres/continuity.py`](app/repositories/postgres/continuity.py), [`app/experimental/world.py`](app/experimental/world.py), [`app/api.py`](app/api.py), [`app/finding_review_api.py`](app/finding_review_api.py), [`app/experimental/world_api.py`](app/experimental/world_api.py).

Original continuity finding repository owns source-bound deterministic checks and OPEN/RESOLVED/INTENTIONAL decisions. Exact chapter owner/version/digest, facts digest and finding fingerprint bind feedback/reason/history; changed evidence becomes REVIEW_REQUIRED and identical source preserves intentional suppression. Stored Timeline facts retain opaque public IDs while the original persistence adapter resolves real project-slug ownership and UUID storage keys; no unrelated Story row or foreign payload is adopted.

Expected review version, operation ID and human confirmation; exact historical evidence snapshot verified before navigation. Reopen/feedback remain available on stale rows; resolve/intentional require current evidence. File coordination and PostgreSQL locks; history bounded at 100. Synchronous check cancellation discards an uncommitted result, restart rereads original decisions. No Canon auto-write.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/novels/{nid}/continuity/scan-chapter` | [scan_chapter_continuity](app/api.py#L2940) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/canon` | [canon](app/experimental/world_api.py#L60) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/character-state` | [character_state](app/experimental/world_api.py#L70) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/continuity` | [continuity](app/experimental/world_api.py#L65) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records` | [records](app/experimental/world_api.py#L28) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/world/records` | [create_record](app/experimental/world_api.py#L34) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}` | [record](app/experimental/world_api.py#L39) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}` | [edit_record](app/experimental/world_api.py#L44) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}/history` | [history](app/experimental/world_api.py#L49) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/world/records/{rid}/{action}` | [review](app/experimental/world_api.py#L54) | domain.review, domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/world/schema` | [schema](app/experimental/world_api.py#L22) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/visual-continuity` | [visual_continuity](app/api.py#L2862) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/world-rules` | [list_world_rules](app/api.py#L3407) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/world-rules` | [create_world_rule](app/api.py#L3417) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/continuity/checks` | [continuity_checks](app/api.py#L2929) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/continuity/findings` | [continuity_findings](app/api.py#L3070) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/projects/{project_id}/continuity/findings/{finding_id}` | [continuity_finding](app/api.py#L3077) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/continuity/findings/{finding_id}/resolve` | [resolve_continuity_finding](app/api.py#L3083) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/projects/{project_id}/{kind}/review-checks` | [check_findings](app/finding_review_api.py#L31) | domain.write |
| GET | `/api[/v1]/projects/{project_id}/{kind}/review-findings` | [list_findings](app/finding_review_api.py#L24) | domain.read |
| GET | `/api[/v1]/projects/{project_id}/{kind}/review-findings/{finding_id}` | [detail](app/finding_review_api.py#L41) | domain.read |
| GET | `/api[/v1]/projects/{project_id}/{kind}/review-findings/{finding_id}/evidence` | [evidence](app/finding_review_api.py#L55) | domain.read |
| GET | `/api[/v1]/projects/{project_id}/{kind}/review-findings/{finding_id}/history` | [history](app/finding_review_api.py#L48) | domain.read |
| POST | `/api[/v1]/projects/{project_id}/{kind}/review-findings/{finding_id}/review` | [review](app/finding_review_api.py#L62) | domain.review |

Navigation: FS_FORESHADOWING, FS_TIMELINE, A03, CORE_MANUSCRIPT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_REVIEW · Unified review inbox

Page: Review → Unified review inbox; ENGINEERING_UI.

Components: [`frontend/src/experimental/InboxPanel.tsx`](frontend/src/experimental/InboxPanel.tsx), [`frontend/src/novel/AgentResultReview.tsx`](frontend/src/novel/AgentResultReview.tsx), [`frontend/src/RevisionPanel.tsx`](frontend/src/RevisionPanel.tsx).

Authority: [`app/experimental/inbox.py`](app/experimental/inbox.py), [`app/experimental/legacy_inbox.py`](app/experimental/legacy_inbox.py), [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/experimental/adaptation_projection.py`](app/experimental/adaptation_projection.py), [`app/experimental/review_adapter_projection.py`](app/experimental/review_adapter_projection.py), [`app/experimental/inbox_api.py`](app/experimental/inbox_api.py), [`frontend/src/experimental/uxClient.ts`](frontend/src/experimental/uxClient.ts).

Read-through original-domain ReviewBinding with source, original ID, revision, permission, risk and allowed actions. Batch is explicitly restricted and does not invent missing selection/review consent.

Unversioned legacy gates and shared branch-manuscript projections remain read-only exact-owner links; branch cancellation/review stays in the original scope/version/read+review endpoint and rechecks counterpart access. Finding/Canon generic Inbox navigation is FORMAL_TARGET_ONLY with manual original-panel route and no exact-open control. Adaptation Task/Review keeps exact original proposal/task/source/target pointers and no generic mutation; actual opening revalidates owner/source/target. Research/visual adapter receipt projections retain original creator/source permissions; navigation is FORMAL_SOURCE_ONLY with no rendered exact-open control or generic approval. Original detail must supply actual review evidence. Current forbidden/missing feature is unavailable, not an empty success. Restart rereads owners.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| Client/storage or composed adapter | Original owner contract | [`app/experimental/inbox.py`](app/experimental/inbox.py), [`app/experimental/legacy_inbox.py`](app/experimental/legacy_inbox.py), [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py) | Original authority; no invented server route |

Navigation: U07, A03, A11, FS_BRANCH, FS_PROCESSING, FS_CANON, FS_CONTINUITY, CORE_ADAPTATION, FS_RESEARCH_VISION, FS_VISUAL. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Research

### A10 · Layered research library

Page: Research → Library / Source / Notes / Citations; ENGINEERING_UI.

Components: [`frontend/src/experimental/ResearchLibraryPanel.tsx`](frontend/src/experimental/ResearchLibraryPanel.tsx), [`frontend/src/novel/ResearchPanel.tsx`](frontend/src/novel/ResearchPanel.tsx), [`frontend/src/experimental/EmbeddingPanel.tsx`](frontend/src/experimental/EmbeddingPanel.tsx).

Authority: [`app/experimental/research_library.py`](app/experimental/research_library.py), [`app/experimental/research_extract.py`](app/experimental/research_extract.py), [`app/experimental/embeddings.py`](app/experimental/embeddings.py), [`app/experimental/research_library_api.py`](app/experimental/research_library_api.py), [`frontend/src/experimental/ResearchLibraryPanel.tsx`](frontend/src/experimental/ResearchLibraryPanel.tsx), [`frontend/src/experimental/EmbeddingPanel.tsx`](frontend/src/experimental/EmbeddingPanel.tsx).

Original source bytes and source ID/version/digest own TXT/Markdown/DOCX/text PDF/web capture/image metadata; notes and citations link exact current paragraphs.

Replace/restore/privacy/revoke/delete invalidates citations/indexes/analysis. Owner recovery can inspect only erased INVALIDATED vector receipts when the actor owns both original Research source and index in the exact current scope; former shared readers remain denied and queries stay blocked. Original source archive/history and authorized byte recovery retain their own permission checks. Research remains LOCAL_ONLY; setting drafts cannot auto-promote to Canon.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/jobs` | [analysis_jobs](app/experimental/research_library_api.py#L214) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/jobs` | [create_analysis](app/experimental/research_library_api.py#L222) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/jobs/{rid}` | [analysis_job](app/experimental/research_library_api.py#L218) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/jobs/{rid}/{action}` | [analysis_action](app/experimental/research_library_api.py#L226) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/status` | [analysis_status](app/experimental/research_library_api.py#L210) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/citation` | [citation](app/experimental/research_library_api.py#L156) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/context-preview` | [context](app/experimental/research_library_api.py#L161) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/note-repairs` | [note_repairs](app/experimental/research_library_api.py#L175) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/notes` | [notes](app/experimental/research_library_api.py#L166) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/notes` | [note](app/experimental/research_library_api.py#L171) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/research-library/notes/{rid}` | [edit_note](app/experimental/research_library_api.py#L180) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/notes/{rid}/delete` | [delete_note](app/experimental/research_library_api.py#L184) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/notes/{rid}/history` | [note_history](app/experimental/research_library_api.py#L188) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/search` | [search](app/experimental/research_library_api.py#L151) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/setting-drafts` | [drafts](app/experimental/research_library_api.py#L193) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/setting-drafts` | [adopt](app/experimental/research_library_api.py#L198) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/setting-drafts/{rid}/{action}` | [review](app/experimental/research_library_api.py#L202) | domain.write, domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources` | [sources](app/experimental/research_library_api.py#L85) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources-archive` | [archive](app/experimental/research_library_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/sources/fetch-webpage` | [import_web](app/experimental/research_library_api.py#L94) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/sources/import` | [import_file](app/experimental/research_library_api.py#L90) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}` | [source](app/experimental/research_library_api.py#L124) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}` | [edit](app/experimental/research_library_api.py#L138) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/backrefs` | [backrefs](app/experimental/research_library_api.py#L146) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/file` | [replace_file](app/experimental/research_library_api.py#L116) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/history` | [source_history](app/experimental/research_library_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/history/{version}/original` | [historical_original](app/experimental/research_library_api.py#L108) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/original` | [original](app/experimental/research_library_api.py#L129) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/restore` | [restore_source](app/experimental/research_library_api.py#L120) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/{action}` | [transition](app/experimental/research_library_api.py#L142) | Original access helper/default/middleware; see source |

Navigation: FS_SEMANTIC, FS_RESEARCH_VISION, FS_IMPORT, U08, FS_CANON. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_IMPORT · Manuscript import / Import health / Extraction

Page: Research → Manuscript import / Import health / Extraction; ENGINEERING_UI.

Components: [`frontend/src/novel/NovelImportPanel.tsx`](frontend/src/novel/NovelImportPanel.tsx), [`frontend/src/experimental/ImportPanel.tsx`](frontend/src/experimental/ImportPanel.tsx).

Authority: [`app/services/import_review_service.py`](app/services/import_review_service.py), [`app/services/import_apply_service.py`](app/services/import_apply_service.py), [`app/import_parsers.py`](app/import_parsers.py), [`app/experimental/imports.py`](app/experimental/imports.py), [`app/api.py`](app/api.py), [`app/experimental/imports_api.py`](app/experimental/imports_api.py).

Original parser/source digest and versioned knowledge review, chunk/import candidate records. Preview health reports unsupported/empty/bad input; selected apply uses original data owners and partial-apply journal.

Cancel stops future work, not already committed selected candidates. Recover reads exact apply journal and never replays committed writes; real OCR/Vision goes through FS_RESEARCH_VISION.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/novels/import` | [import_novel](app/api.py#L1901) | domain.write |
| POST | `/api[/v1]/novels/{nid}/image-generations/import` | [import_generated_image](app/api.py#L2740) | domain.write |
| GET | `/api[/v1]/novels/{nid}/import/knowledge-base/review` | [list_import_knowledge_reviews](app/api.py#L1989) | domain.read |
| POST | `/api[/v1]/novels/{nid}/import/knowledge-base/review` | [review_import_knowledge](app/api.py#L1946) | domain.write |
| GET | `/api[/v1]/novels/{nid}/import/knowledge-base/review/{review_id}` | [get_import_knowledge_review](app/api.py#L2017) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/import/knowledge-base/review/{review_id}` | [update_import_knowledge_review](app/api.py#L2025) | domain.write |
| POST | `/api[/v1]/novels/{nid}/import/knowledge-base/review/{review_id}/ai-analyze` | [ai_analyze_import_knowledge](app/api.py#L2072) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets` | [list_motion_asset_imports](app/api.py#L2845) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets/retry` | [retry_failed_motion_asset_imports](app/api.py#L2849) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [motion_asset_import_status](app/api.py#L2841) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [import_motion_asset](app/api.py#L2838) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/download` | [download_motion_asset](app/api.py#L2852) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/retry` | [retry_motion_asset_import](app/api.py#L2855) | domain.write |
| POST | `/api[/v1]/novels/{nid}/speech-generations/import` | [import_generated_speech](app/api.py#L2719) | domain.write |

Navigation: A10, FS_REVIEW, CORE_MANUSCRIPT, U14. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_SEMANTIC · Semantic / Hybrid retrieval and indexes

Page: Research → Semantic / Hybrid retrieval and indexes; ENGINEERING_UI.

Components: [`frontend/src/experimental/EmbeddingPanel.tsx`](frontend/src/experimental/EmbeddingPanel.tsx).

Authority: [`app/experimental/embeddings.py`](app/experimental/embeddings.py), [`app/experimental/vector_index.py`](app/experimental/vector_index.py), [`app/experimental/embeddings_api.py`](app/experimental/embeddings_api.py).

Existing EmbeddingProvider and persisted index/vector owner; bounded exact cosine and weighted reciprocal-rank fusion with live lexical scores. Query and hybrid-query require domain.read plus current index/source visibility, while mutations retain domain.write; read-only permission does not bypass source privacy or branch scope. Character/Story/Research/Asset source version/digest and index version are pinned.

Create/edit/rebuild/invalidate/remove/cancel; atomic publication checks token/source/provider/permission. After Research delete/revoke, only an actor who owns both source and index may inspect retained INVALIDATED receipts in the exact scope, under current feature authority; every stored vector must be erased and is never returned. Former shared readers remain denied; invalidated query remains blocked. Interrupted BUILDING requires explicit cancel/invalidate/rebuild. Missing embedding provider stays NOT_CONFIGURED; synthetic vectors MOCK_ONLY.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/hybrid-query` | [hybrid_query](app/experimental/embeddings_api.py#L99) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes` | [indexes](app/experimental/embeddings_api.py#L62) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes` | [create](app/experimental/embeddings_api.py#L67) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes/{rid}` | [edit](app/experimental/embeddings_api.py#L73) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes/{rid}/records` | [records](app/experimental/embeddings_api.py#L79) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes/{rid}/{action}` | [action](app/experimental/embeddings_api.py#L84) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/providers` | [providers](app/experimental/embeddings_api.py#L56) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/query` | [query](app/experimental/embeddings_api.py#L94) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/sources` | [sources](app/experimental/embeddings_api.py#L50) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/status` | [status](app/experimental/embeddings_api.py#L45) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks` | [visual_checks](app/experimental/embeddings_api.py#L109) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks` | [create_visual_check](app/experimental/embeddings_api.py#L124) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks/{rid}` | [visual_check](app/experimental/embeddings_api.py#L114) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks/{rid}/selection` | [visual_selection](app/experimental/embeddings_api.py#L119) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks/{rid}/{action}` | [visual_action](app/experimental/embeddings_api.py#L130) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/profiles` | [profiles](app/experimental/embeddings_api.py#L104) | Original access helper/default/middleware; see source |

Navigation: U03, A10, FS_VISUAL, CORE_MODELS. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_RESEARCH_VISION · OCR / Scanned PDF / Image / Chart / Table

Page: Research → OCR / Scanned PDF / Image / Chart / Table; FORMAL_UI_SURFACE_CONTRACT.

Components: [`frontend/src/experimental/ResearchLibraryPanel.tsx`](frontend/src/experimental/ResearchLibraryPanel.tsx).

Authority: [`app/experimental/research_vision.py`](app/experimental/research_vision.py), [`app/experimental/review_adapter_jobs.py`](app/experimental/review_adapter_jobs.py), [`app/experimental/review_adapter_projection.py`](app/experimental/review_adapter_projection.py), [`app/experimental/research_library.py`](app/experimental/research_library.py), [`app/experimental/research_library_api.py`](app/experimental/research_library_api.py).

Original Research source ID/version/original digest and typed page/bbox/table-block result; private durable analysis review receipt and derived citation digest. Original bytes remain intact.

Create/run/cancel/invalidate/recover/review uses bounded original receipts with reserved terminal/recovery/invalidation capacity and token fences. Repeated terminal cancel/invalidate is idempotent; revoked-source responses omit request/lineage/results. Reads retain original Research domain.write plus source/creator visibility. Tasks/Review project original receipts; cancel delegates original owner write+CAS, no generic approval/retry. FORMAL_SOURCE_ONLY target, no rendered exact-open control. Real admission NOT_CONFIGURED/MOCK_ONLY; no durable worker or restart replay.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/jobs` | [analysis_jobs](app/experimental/research_library_api.py#L214) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/jobs` | [create_analysis](app/experimental/research_library_api.py#L222) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/jobs/{rid}` | [analysis_job](app/experimental/research_library_api.py#L218) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/jobs/{rid}/{action}` | [analysis_action](app/experimental/research_library_api.py#L226) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/analysis/status` | [analysis_status](app/experimental/research_library_api.py#L210) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/citation` | [citation](app/experimental/research_library_api.py#L156) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/context-preview` | [context](app/experimental/research_library_api.py#L161) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/note-repairs` | [note_repairs](app/experimental/research_library_api.py#L175) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/notes` | [notes](app/experimental/research_library_api.py#L166) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/notes` | [note](app/experimental/research_library_api.py#L171) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/research-library/notes/{rid}` | [edit_note](app/experimental/research_library_api.py#L180) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/notes/{rid}/delete` | [delete_note](app/experimental/research_library_api.py#L184) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/notes/{rid}/history` | [note_history](app/experimental/research_library_api.py#L188) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/search` | [search](app/experimental/research_library_api.py#L151) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/setting-drafts` | [drafts](app/experimental/research_library_api.py#L193) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/setting-drafts` | [adopt](app/experimental/research_library_api.py#L198) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/setting-drafts/{rid}/{action}` | [review](app/experimental/research_library_api.py#L202) | domain.write, domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources` | [sources](app/experimental/research_library_api.py#L85) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources-archive` | [archive](app/experimental/research_library_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/sources/fetch-webpage` | [import_web](app/experimental/research_library_api.py#L94) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/sources/import` | [import_file](app/experimental/research_library_api.py#L90) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}` | [source](app/experimental/research_library_api.py#L124) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}` | [edit](app/experimental/research_library_api.py#L138) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/backrefs` | [backrefs](app/experimental/research_library_api.py#L146) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/file` | [replace_file](app/experimental/research_library_api.py#L116) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/history` | [source_history](app/experimental/research_library_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/history/{version}/original` | [historical_original](app/experimental/research_library_api.py#L108) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/original` | [original](app/experimental/research_library_api.py#L129) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/restore` | [restore_source](app/experimental/research_library_api.py#L120) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/research-library/sources/{rid}/{action}` | [transition](app/experimental/research_library_api.py#L142) | Original access helper/default/middleware; see source |

Navigation: A10, FS_SEMANTIC, U07, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Production

### A13 · Production manifest and controlled replay

Page: Production → Production manifest / Controlled replay; ENGINEERING_UI.

Components: [`frontend/src/experimental/ProductionLineagePanel.tsx`](frontend/src/experimental/ProductionLineagePanel.tsx).

Authority: [`app/experimental/production_lineage.py`](app/experimental/production_lineage.py), [`app/experimental/media.py`](app/experimental/media.py), [`frontend/src/experimental/ProductionLineagePanel.tsx`](frontend/src/experimental/ProductionLineagePanel.tsx), [`app/experimental/production_lineage_api.py`](app/experimental/production_lineage_api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py).

Same manifest and original media execution owners as A09; traceability, preflight replayability, approximate reproduction and measured byte equality are distinct.

Explicit source/configuration/permission/version revalidation; cancel belongs to original replay task. Restart does not rerun; missing hashes/configuration require user action.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/media/adapters` | [adapters](app/experimental/media_api.py#L26) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/catalog` | [catalog](app/experimental/media_api.py#L31) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [briefs](app/experimental/media_api.py#L36) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [create_cover](app/experimental/media_api.py#L41) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs/{rid}` | [update_cover](app/experimental/media_api.py#L46) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals` | [proposals](app/experimental/media_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/compare` | [compare](app/experimental/media_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/preview` | [preview](app/experimental/media_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/{action}` | [review](app/experimental/media_api.py#L114) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [storyboard_briefs](app/experimental/media_api.py#L52) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [create_storyboard](app/experimental/media_api.py#L57) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs/{rid}` | [update_storyboard](app/experimental/media_api.py#L62) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [tasks](app/experimental/media_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [queue](app/experimental/media_api.py#L73) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks/{rid}/{action}` | [task_action](app/experimental/media_api.py#L78) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/production/assets` | [assets](app/experimental/production_lineage_api.py#L68) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/production/assets/{aid}` | [asset](app/experimental/production_lineage_api.py#L73) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/production/assets/{aid}/impact` | [impact](app/experimental/production_lineage_api.py#L83) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/production/assets/{aid}/lineage` | [annotate](app/experimental/production_lineage_api.py#L78) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/production/manifests` | [manifests](app/experimental/production_lineage_api.py#L88) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/production/manifests` | [capture](app/experimental/production_lineage_api.py#L93) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/production/manifests/{rid}/export` | [export](app/experimental/production_lineage_api.py#L103) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/production/manifests/{rid}/preflight` | [preflight](app/experimental/production_lineage_api.py#L98) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/production/manifests/{rid}/replay` | [replay](app/experimental/production_lineage_api.py#L108) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/production/replays` | [replays](app/experimental/production_lineage_api.py#L113) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/production/replays/{rid}/cancel` | [cancel](app/experimental/production_lineage_api.py#L123) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/production/replays/{rid}/execute` | [execute](app/experimental/production_lineage_api.py#L118) | domain.write |

Navigation: A09, CORE_IMAGES, U16, U07. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### A08 · Camera grammar and scene direction

Page: Production → Screenplay / Director / Shots; ENGINEERING_UI.

Components: [`frontend/src/experimental/DirectorPanel.tsx`](frontend/src/experimental/DirectorPanel.tsx), [`frontend/src/novel/DirectorShotCard.tsx`](frontend/src/novel/DirectorShotCard.tsx), [`frontend/src/novel/DirectorShotList.tsx`](frontend/src/novel/DirectorShotList.tsx), [`frontend/src/novel/ScreenplayPanel.tsx`](frontend/src/novel/ScreenplayPanel.tsx).

Authority: [`app/experimental/director.py`](app/experimental/director.py), [`app/services/screenplay_service.py`](app/services/screenplay_service.py), [`frontend/src/experimental/DirectorPanel.tsx`](frontend/src/experimental/DirectorPanel.tsx), [`frontend/src/novel/DirectorShotCard.tsx`](frontend/src/novel/DirectorShotCard.tsx), [`app/experimental/director_api.py`](app/experimental/director_api.py).

Original screenplay/Scene/Shot authority and reviewed director proposals; camera grammar/rhythm are declared metadata checks, not cinematic quality proof.

Versioned screenplay edit and proposal review, source-current history/restore; cancel preserves draft. Restart uses original proposals and never dispatches media automatically.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/director/catalog` | [catalog](app/experimental/director_api.py#L38) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/director/compare` | [compare](app/experimental/director_api.py#L50) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/director/plans` | [plans](app/experimental/director_api.py#L42) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/director/plans` | [create](app/experimental/director_api.py#L46) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/director/plans/{rid}/{action}` | [action](app/experimental/director_api.py#L54) | domain.review |

Navigation: CORE_SCREENPLAY, CORE_IMAGES, CORE_VIDEO, A12, B06. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### A12 · OTIO and NLE exchange

Page: Production → Timeline / OTIO exchange; ENGINEERING_UI.

Components: [`frontend/src/experimental/TimelineExchangePanel.tsx`](frontend/src/experimental/TimelineExchangePanel.tsx), [`frontend/src/novel/VideoTimeline.tsx`](frontend/src/novel/VideoTimeline.tsx).

Authority: [`app/experimental/timeline_exchange.py`](app/experimental/timeline_exchange.py), [`app/industry_export_formats.py`](app/industry_export_formats.py), [`frontend/src/experimental/TimelineExchangePanel.tsx`](frontend/src/experimental/TimelineExchangePanel.tsx), [`app/experimental/timeline_exchange_api.py`](app/experimental/timeline_exchange_api.py).

Original OTIO timeline and exact rational media time; supported track/clip/transition schema and media identity are retained, unsupported fields reported.

Explicit preview/import/export/review with source/version fences; cancel discards synchronous result; repeat from reviewed current snapshot. Real NLE import/export NOT_RUN.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/timeline-exchange/catalog` | [catalog](app/experimental/timeline_exchange_api.py#L22) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/timeline-exchange/from-screenplay` | [screenplay](app/experimental/timeline_exchange_api.py#L34) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/timeline-exchange/import` | [import_file](app/experimental/timeline_exchange_api.py#L30) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/timeline-exchange/records` | [records](app/experimental/timeline_exchange_api.py#L26) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/timeline-exchange/records/{rid}/file` | [file](app/experimental/timeline_exchange_api.py#L38) | domain.read |

Navigation: CORE_VIDEO, CORE_ASSETS, B04, CORE_EXPORT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### B03 · Voice direction and speaker attribution

Page: Production → Voice direction / Attribution / Audiobook; ENGINEERING_UI.

Components: [`frontend/src/experimental/AudiobookPanel.tsx`](frontend/src/experimental/AudiobookPanel.tsx), [`frontend/src/experimental/VoiceDirectionPanel.tsx`](frontend/src/experimental/VoiceDirectionPanel.tsx), [`frontend/src/novel/AudiobookManifestPanel.tsx`](frontend/src/novel/AudiobookManifestPanel.tsx), [`frontend/src/novel/SpeechSynthesisPanel.tsx`](frontend/src/novel/SpeechSynthesisPanel.tsx), [`frontend/src/novel/DirectorVoiceToolbar.tsx`](frontend/src/novel/DirectorVoiceToolbar.tsx).

Authority: [`app/experimental/audiobook.py`](app/experimental/audiobook.py), [`app/experimental/voice_direction.py`](app/experimental/voice_direction.py), [`app/audio_production_store.py`](app/audio_production_store.py), [`frontend/src/experimental/AudiobookPanel.tsx`](frontend/src/experimental/AudiobookPanel.tsx), [`frontend/src/experimental/VoiceDirectionPanel.tsx`](frontend/src/experimental/VoiceDirectionPanel.tsx), [`app/experimental/audiobook_api.py`](app/experimental/audiobook_api.py), [`app/experimental/voice_direction_api.py`](app/experimental/voice_direction_api.py).

Original voice mapping, character/scene/utterance/emotion and audio/TTS jobs; unknown speaker remains NEEDS_REVIEW. Measured WAV frames and original mix proposal own timing.

Per-segment review/CAS/source versions, job cancel and explicit original-owner recovery. Bounded PCM mix is synchronous; restart does not generate or mix automatically.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/audiobook/capabilities` | [capabilities](app/experimental/audiobook_api.py#L25) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/audiobook/mappings` | [mappings](app/experimental/audiobook_api.py#L40) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/audiobook/mappings` | [mapping](app/experimental/audiobook_api.py#L45) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/audiobook/mixes` | [mixes](app/experimental/audiobook_api.py#L105) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/audiobook/mixes/{rid}/{action}` | [mix_review](app/experimental/audiobook_api.py#L111) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/audiobook/plans` | [plans](app/experimental/audiobook_api.py#L50) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/audiobook/plans` | [plan](app/experimental/audiobook_api.py#L55) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/audiobook/plans/{rid}/duration-manifest` | [duration](app/experimental/audiobook_api.py#L83) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/audiobook/plans/{rid}/segments/{sid}` | [segment](app/experimental/audiobook_api.py#L60) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/audiobook/plans/{rid}/segments/{sid}/audio` | [audio](app/experimental/audiobook_api.py#L66) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/audiobook/plans/{rid}/subtitles` | [subtitles](app/experimental/audiobook_api.py#L88) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/audiobook/plans/{rid}/tracks` | [track](app/experimental/audiobook_api.py#L72) | domain.write |
| DELETE | `/api[/v1]/novels/{nid}/experimental/audiobook/plans/{rid}/tracks/{tid}` | [remove_track](app/experimental/audiobook_api.py#L77) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/audiobook/plans/{rid}/{action}` | [action](app/experimental/audiobook_api.py#L93) | domain.write, domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/audiobook/profiles` | [profiles](app/experimental/audiobook_api.py#L30) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/audiobook/profiles` | [profile](app/experimental/audiobook_api.py#L35) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/voice-direction/catalog` | [catalog](app/experimental/voice_direction_api.py#L47) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/voice-direction/jobs` | [jobs](app/experimental/voice_direction_api.py#L79) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/voice-direction/jobs/{jid}/approve` | [approve](app/experimental/voice_direction_api.py#L127) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/voice-direction/jobs/{jid}/audio` | [audio](app/experimental/voice_direction_api.py#L116) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/voice-direction/jobs/{jid}/cancel` | [cancel](app/experimental/voice_direction_api.py#L100) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/voice-direction/jobs/{jid}/execute` | [execute](app/experimental/voice_direction_api.py#L93) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/voice-direction/jobs/{jid}/retry` | [retry](app/experimental/voice_direction_api.py#L109) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/voice-direction/mixes/{rid}/audio` | [mix_audio](app/experimental/voice_direction_api.py#L55) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/voice-direction/plans/{rid}/mix` | [mix](app/experimental/voice_direction_api.py#L51) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/voice-direction/plans/{rid}/queue` | [queue](app/experimental/voice_direction_api.py#L75) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/voice-direction/plans/{rid}/reorder` | [reorder](app/experimental/voice_direction_api.py#L71) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/voice-direction/plans/{rid}/segments/{sid}` | [edit](app/experimental/voice_direction_api.py#L63) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/voice-direction/plans/{rid}/segments/{sid}/lock` | [lock](app/experimental/voice_direction_api.py#L67) | domain.write |

Navigation: CORE_AUDIO, FS_PROCESSING, B04, U07, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### B04 · Subtitle editing and timeline

Page: Production → Subtitles / Caption timeline; ENGINEERING_UI.

Components: [`frontend/src/experimental/SubtitleTimelinePanel.tsx`](frontend/src/experimental/SubtitleTimelinePanel.tsx).

Authority: [`app/experimental/subtitle_timeline.py`](app/experimental/subtitle_timeline.py), [`app/experimental/voice_direction.py`](app/experimental/voice_direction.py), [`frontend/src/experimental/SubtitleTimelinePanel.tsx`](frontend/src/experimental/SubtitleTimelinePanel.tsx), [`app/experimental/subtitle_timeline_api.py`](app/experimental/subtitle_timeline_api.py).

Original caption cue rows, rational timebase and measured source audio/video duration own manual/measured timing and SRT/WebVTT exports.

CAS/save/review/history and stale-source refusal; cancel discards synchronous edits/results, persisted caption reopened after restart. ASR/alignment/burn-in handled by FS_PROCESSING.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/catalog` | [catalog](app/experimental/subtitle_timeline_api.py#L19) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/catalog` | [processing_catalog](app/experimental/subtitle_timeline_api.py#L41) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/tasks` | [processing_tasks](app/experimental/subtitle_timeline_api.py#L44) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/tasks` | [queue_processing](app/experimental/subtitle_timeline_api.py#L47) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/tasks/{rid}/file` | [processing_file](app/experimental/subtitle_timeline_api.py#L54) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/tasks/{rid}/{action}` | [processing_action](app/experimental/subtitle_timeline_api.py#L50) | domain.review, domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records` | [records](app/experimental/subtitle_timeline_api.py#L22) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records` | [create](app/experimental/subtitle_timeline_api.py#L25) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records/{rid}` | [update](app/experimental/subtitle_timeline_api.py#L28) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records/{rid}/cues/{cid}/merge` | [merge](app/experimental/subtitle_timeline_api.py#L34) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records/{rid}/cues/{cid}/split` | [split](app/experimental/subtitle_timeline_api.py#L31) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records/{rid}/file.{format}` | [download](app/experimental/subtitle_timeline_api.py#L37) | domain.read |

Navigation: FS_PROCESSING, B03, A12, CORE_VIDEO. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### B06 · Comic and Webtoon layouts

Page: Production → Comics / Webtoon; ENGINEERING_UI.

Components: [`frontend/src/experimental/ComicLayoutsPanel.tsx`](frontend/src/experimental/ComicLayoutsPanel.tsx).

Authority: [`app/experimental/comic_layouts.py`](app/experimental/comic_layouts.py), [`app/services/asset_library_service.py`](app/services/asset_library_service.py), [`frontend/src/experimental/ComicLayoutsPanel.tsx`](frontend/src/experimental/ComicLayoutsPanel.tsx), [`app/experimental/comic_layouts_api.py`](app/experimental/comic_layouts_api.py).

Same approved AssetLibrary/reference identity and original Scene/Shot links; panel order, bubbles, page/vertical exports and source digests are explicit.

Versioned layout/edit/review/export/history with asset approval/hash fences; cancel synchronous render/discard, restart reopens persisted layout. Professional art/font/print quality NOT_RUN.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/comic-layouts/catalog` | [catalog](app/experimental/comic_layouts_api.py#L54) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/comic-layouts/images/{aid}` | [image](app/experimental/comic_layouts_api.py#L62) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/comic-layouts/images/{aid}/approve` | [approve_image](app/experimental/comic_layouts_api.py#L66) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/comic-layouts/records` | [records](app/experimental/comic_layouts_api.py#L58) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/comic-layouts/records` | [create](app/experimental/comic_layouts_api.py#L70) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/comic-layouts/records/{rid}` | [update](app/experimental/comic_layouts_api.py#L74) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/comic-layouts/records/{rid}/approve` | [approve](app/experimental/comic_layouts_api.py#L82) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/comic-layouts/records/{rid}/export` | [export](app/experimental/comic_layouts_api.py#L94) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/comic-layouts/records/{rid}/preflight` | [preflight](app/experimental/comic_layouts_api.py#L78) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/comic-layouts/records/{rid}/restore` | [restore](app/experimental/comic_layouts_api.py#L86) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/comic-layouts/records/{rid}/segments/{index}` | [preview](app/experimental/comic_layouts_api.py#L90) | domain.read |

Navigation: CORE_ASSETS, FS_VISUAL, A08, CORE_EXPORT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### B07 · Interactive narrative export

Page: Production → Interactive Story / Visual Novel; ENGINEERING_UI.

Components: [`frontend/src/experimental/InteractiveStoryPanel.tsx`](frontend/src/experimental/InteractiveStoryPanel.tsx), [`frontend/src/experimental/InteractiveStoryHistory.tsx`](frontend/src/experimental/InteractiveStoryHistory.tsx), [`frontend/src/experimental/InteractiveStoryPreview.tsx`](frontend/src/experimental/InteractiveStoryPreview.tsx).

Authority: [`app/experimental/interactive_story.py`](app/experimental/interactive_story.py), [`app/experimental/planning.py`](app/experimental/planning.py), [`frontend/src/experimental/InteractiveStoryPanel.tsx`](frontend/src/experimental/InteractiveStoryPanel.tsx), [`frontend/src/experimental/InteractiveStoryHistory.tsx`](frontend/src/experimental/InteractiveStoryHistory.tsx), [`app/experimental/interactive_story_api.py`](app/experimental/interactive_story_api.py).

Original planning-node adaptation rows, typed conditions/variables/routes/endings and bounded reachability own review/playback/export.

Version/digest/source-current review, export preview, history/restore and stale refusal. Cancel pure bounded export discards response; no engine run or deploy on resume/restart.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories` | [stories](app/experimental/interactive_story_api.py#L34) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories` | [create](app/experimental/interactive_story_api.py#L49) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories/catalog` | [catalog](app/experimental/interactive_story_api.py#L29) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories/engine-contract` | [engine_contract](app/experimental/interactive_story_api.py#L39) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}` | [story](app/experimental/interactive_story_api.py#L44) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}` | [save](app/experimental/interactive_story_api.py#L54) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/export` | [service.export](app/experimental/interactive_story_api.py#L70) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/export-preview` | [service.export_preview](app/experimental/interactive_story_api.py#L69) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/history` | [service.revisions](app/experimental/interactive_story_api.py#L71) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/preview` | [service.preview](app/experimental/interactive_story_api.py#L66) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/refresh` | [service.refresh](app/experimental/interactive_story_api.py#L68) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/refresh-preview` | [service.refresh_preview](app/experimental/interactive_story_api.py#L67) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/restore-revision` | [service.restore_revision](app/experimental/interactive_story_api.py#L72) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/review` | [service.review](app/experimental/interactive_story_api.py#L65) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/review-preview` | [service.review_preview](app/experimental/interactive_story_api.py#L64) | domain.review |

Navigation: FS_ENGINES, FS_PLANNING, A04, CORE_EXPORT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_IMAGES · Image / Cover / Storyboard / Character reference / Edit / Multi-reference

Page: Production → Image / Cover / Storyboard / Character reference / Edit / Multi-reference; ENGINEERING_UI.

Components: [`frontend/src/novel/ImageGenerationPanel.tsx`](frontend/src/novel/ImageGenerationPanel.tsx), [`frontend/src/novel/ImageQueuePanel.tsx`](frontend/src/novel/ImageQueuePanel.tsx), [`frontend/src/novel/ImageInfiniteCanvas.tsx`](frontend/src/novel/ImageInfiniteCanvas.tsx), [`frontend/src/novel/ImageTaskInspector.tsx`](frontend/src/novel/ImageTaskInspector.tsx), [`frontend/src/experimental/MediaPanel.tsx`](frontend/src/experimental/MediaPanel.tsx), [`frontend/src/novel/AssetTaskExecutionPanel.tsx`](frontend/src/novel/AssetTaskExecutionPanel.tsx), [`frontend/src/novel/VisionAnalysisPanel.tsx`](frontend/src/novel/VisionAnalysisPanel.tsx), [`frontend/src/novel/VisualTextWorkflow.tsx`](frontend/src/novel/VisualTextWorkflow.tsx).

Authority: [`app/services/image_job_service.py`](app/services/image_job_service.py), [`app/asset_providers.py`](app/asset_providers.py), [`app/experimental/media.py`](app/experimental/media.py), [`app/api.py`](app/api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py).

Original image jobs, assets and versioned media briefs own actual provider dispatch, attempts, source references and human acceptance. Qwen-Image/FLUX/FLUX.2 schema availability is distinct from executable configuration.

Single-image bridge rejects unsupported reference conditioning; edit/multi-reference schemas do not mean actual adapter support. Real image quality NOT_RUN; configured route/credential/license gates remain.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/images/edits` | [edit_image](app/api.py#L2447) | domain.write |
| POST | `/api[/v1]/images/generate` | [generate_image](app/api.py#L2430) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/adapters` | [adapters](app/experimental/media_api.py#L26) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/catalog` | [catalog](app/experimental/media_api.py#L31) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [briefs](app/experimental/media_api.py#L36) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [create_cover](app/experimental/media_api.py#L41) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs/{rid}` | [update_cover](app/experimental/media_api.py#L46) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals` | [proposals](app/experimental/media_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/compare` | [compare](app/experimental/media_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/preview` | [preview](app/experimental/media_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/{action}` | [review](app/experimental/media_api.py#L114) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [storyboard_briefs](app/experimental/media_api.py#L52) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [create_storyboard](app/experimental/media_api.py#L57) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs/{rid}` | [update_storyboard](app/experimental/media_api.py#L62) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [tasks](app/experimental/media_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [queue](app/experimental/media_api.py#L73) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks/{rid}/{action}` | [task_action](app/experimental/media_api.py#L78) | domain.write |
| GET | `/api[/v1]/novels/{nid}/image-generations` | [list_image_generations](app/api.py#L2530) | domain.read |
| POST | `/api[/v1]/novels/{nid}/image-generations/import` | [import_generated_image](app/api.py#L2740) | domain.write |
| GET | `/api[/v1]/novels/{nid}/image-jobs` | [list_image_jobs](app/api.py#L2390) | domain.read |
| POST | `/api[/v1]/novels/{nid}/image-jobs` | [create_image_job](app/api.py#L2395) | domain.write |
| POST | `/api[/v1]/novels/{nid}/image-jobs/{job_id}/accept` | [accept_image_job](app/api.py#L2424) | domain.write |
| POST | `/api[/v1]/novels/{nid}/image-jobs/{job_id}/cancel` | [cancel_image_job](app/api.py#L2414) | domain.write |
| POST | `/api[/v1]/novels/{nid}/image-jobs/{job_id}/execute` | [execute_image_job](app/api.py#L2408) | domain.write |
| POST | `/api[/v1]/novels/{nid}/image-jobs/{job_id}/retry` | [retry_image_job](app/api.py#L2419) | domain.write |
| GET | `/api[/v1]/novels/{nid}/media-tasks` | [list_media_tasks](app/api.py#L2621) | domain.read |

Navigation: CORE_ASSETS, FS_VISUAL, A09, U07, CORE_VIDEO. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_SCREENPLAY · Screenplay / Scene / Shot authoring

Page: Production → Screenplay / Scene / Shot authoring; ENGINEERING_UI.

Components: [`frontend/src/novel/ScreenplayPanel.tsx`](frontend/src/novel/ScreenplayPanel.tsx), [`frontend/src/novel/MultimodalDirectorWorkspace.tsx`](frontend/src/novel/MultimodalDirectorWorkspace.tsx), [`frontend/src/novel/BindingManifestPanel.tsx`](frontend/src/novel/BindingManifestPanel.tsx).

Authority: [`app/services/screenplay_service.py`](app/services/screenplay_service.py), [`app/repositories/screenplay_versions.py`](app/repositories/screenplay_versions.py), [`app/api.py`](app/api.py).

Original branch-bound screenplay source, approval revision and independent edit_version CAS. Scene/shot/storyboard/transition changes preserve current source and immutable history.

Explicit restore creates a new draft and re-review. Cancellation/navigation preserves unsaved intent; no automatic downstream image/video production.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/screenplays` | [screenplays](app/api.py#L2178) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays` | [create_screenplay](app/api.py#L2182) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/approve` | [approve_screenplay](app/api.py#L2188) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks` | [create_asset_tasks](app/api.py#L2876) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/cleanup` | [cleanup_asset_tasks](app/api.py#L2889) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/recover` | [recover_asset_tasks](app/api.py#L2885) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/stats` | [screenplay_asset_task_stats](app/api.py#L2893) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}` | [update_asset_task](app/api.py#L2878) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}/execute` | [execute_asset_task](app/api.py#L2880) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}/retry` | [retry_asset_task](app/api.py#L2883) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/assets` | [plan_assets](app/api.py#L2870) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/assets/approve` | [approve_assets](app/api.py#L2872) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/assets/{asset_id}` | [update_asset](app/api.py#L2874) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks` | [create_motion_tasks](app/api.py#L2222) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets` | [list_motion_asset_imports](app/api.py#L2845) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets/retry` | [retry_failed_motion_asset_imports](app/api.py#L2849) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}` | [update_motion_task](app/api.py#L2775) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/asset-reference` | [motion_asset_reference](app/api.py#L2834) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/callback` | [motion_callback](app/api.py#L2812) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/cancel` | [cancel_motion_task](app/api.py#L2789) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/execute` | [execute_motion_task](app/api.py#L2786) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/frame-history` | [motion_frame_history](app/api.py#L2858) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/frames` | [update_motion_frames](app/api.py#L2778) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [motion_asset_import_status](app/api.py#L2841) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [import_motion_asset](app/api.py#L2838) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/download` | [download_motion_asset](app/api.py#L2852) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/retry` | [retry_motion_asset_import](app/api.py#L2855) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/privacy` | [motion_privacy_review](app/api.py#L3690) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/privacy` | [update_motion_privacy](app/api.py#L3695) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/provider` | [update_motion_provider](app/api.py#L2783) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/remote-id` | [set_remote_motion_task_id](app/api.py#L2824) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/result` | [attach_motion_result](app/api.py#L2809) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/result-history` | [motion_result_history](app/api.py#L2830) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/retry` | [retry_motion_task](app/api.py#L2792) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/sync` | [sync_motion_task](app/api.py#L2827) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/pipeline-advance` | [advance_screenplay_pipeline](app/api.py#L2866) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/pipeline-advance-until-gate` | [advance_screenplay_pipeline_until_gate](app/api.py#L2868) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/pipeline-status` | [screenplay_pipeline_status](app/api.py#L2864) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/revise` | [revise_screenplay](app/api.py#L2192) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/revisions` | [screenplay_revisions](app/api.py#L2190) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/scenes/{scene_id}` | [update_screenplay_scene](app/api.py#L2186) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/shots` | [plan_screenplay_shots](app/api.py#L2194) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/shots/approve` | [approve_screenplay_shots](app/api.py#L2196) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/shots/{shot_id}` | [update_screenplay_shot](app/api.py#L2198) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/storyboard` | [plan_storyboard](app/api.py#L2200) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/storyboard/approve` | [approve_storyboard](app/api.py#L2202) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/storyboard/{card_id}` | [update_storyboard](app/api.py#L2204) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions` | [plan_transitions](app/api.py#L2206) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/approve` | [approve_transitions](app/api.py#L2208) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}` | [update_transition](app/api.py#L2210) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/motion-prompt` | [motion_prompt](app/api.py#L2216) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/motion-prompt` | [save_motion_prompt](app/api.py#L2219) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/prompt` | [transition_prompt](app/api.py#L2212) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/suggestion` | [transition_suggestion](app/api.py#L2214) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/visual-continuity` | [visual_continuity](app/api.py#L2862) | Original access helper/default/middleware; see source |

Navigation: A08, CORE_IMAGES, CORE_VIDEO. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_VIDEO · Video / Motion / Assembly / Post

Page: Production → Video / Motion / Assembly / Post; ENGINEERING_UI.

Components: [`frontend/src/novel/MotionTaskWorkspace.tsx`](frontend/src/novel/MotionTaskWorkspace.tsx), [`frontend/src/novel/MotionPrivacyPanel.tsx`](frontend/src/novel/MotionPrivacyPanel.tsx), [`frontend/src/novel/VideoAssemblyPanel.tsx`](frontend/src/novel/VideoAssemblyPanel.tsx), [`frontend/src/novel/VideoTaskInspector.tsx`](frontend/src/novel/VideoTaskInspector.tsx), [`frontend/src/novel/MotionTaskBatchControls.tsx`](frontend/src/novel/MotionTaskBatchControls.tsx).

Authority: [`app/services/video_assembly_service.py`](app/services/video_assembly_service.py), [`app/asset_providers.py`](app/asset_providers.py), [`app/media_frames.py`](app/media_frames.py), [`app/experimental/media.py`](app/experimental/media.py), [`app/api.py`](app/api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py).

Original motion/video task and source frame assets own T2V/I2V/start-end/continuation; MiniMax H3/Wan/LTX/SeedVR2/RIFE are explicit adapter family schemas, not automatic runtime detection.

No production GPU/model quality evidence. Unsupported operation remains ADAPTER_REQUIRED/NOT_CONFIGURED. Bounded silent review assembly is not audio mastering; cancel/recovery uses original attempts.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/media/adapters` | [adapters](app/experimental/media_api.py#L26) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/catalog` | [catalog](app/experimental/media_api.py#L31) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [briefs](app/experimental/media_api.py#L36) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [create_cover](app/experimental/media_api.py#L41) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs/{rid}` | [update_cover](app/experimental/media_api.py#L46) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals` | [proposals](app/experimental/media_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/compare` | [compare](app/experimental/media_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/preview` | [preview](app/experimental/media_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/{action}` | [review](app/experimental/media_api.py#L114) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [storyboard_briefs](app/experimental/media_api.py#L52) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [create_storyboard](app/experimental/media_api.py#L57) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs/{rid}` | [update_storyboard](app/experimental/media_api.py#L62) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [tasks](app/experimental/media_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [queue](app/experimental/media_api.py#L73) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks/{rid}/{action}` | [task_action](app/experimental/media_api.py#L78) | domain.write |
| GET | `/api[/v1]/novels/{nid}/media-tasks` | [list_media_tasks](app/api.py#L2621) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks` | [create_motion_tasks](app/api.py#L2222) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets` | [list_motion_asset_imports](app/api.py#L2845) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets/retry` | [retry_failed_motion_asset_imports](app/api.py#L2849) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}` | [update_motion_task](app/api.py#L2775) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/asset-reference` | [motion_asset_reference](app/api.py#L2834) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/callback` | [motion_callback](app/api.py#L2812) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/cancel` | [cancel_motion_task](app/api.py#L2789) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/execute` | [execute_motion_task](app/api.py#L2786) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/frame-history` | [motion_frame_history](app/api.py#L2858) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/frames` | [update_motion_frames](app/api.py#L2778) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [motion_asset_import_status](app/api.py#L2841) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [import_motion_asset](app/api.py#L2838) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/download` | [download_motion_asset](app/api.py#L2852) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/retry` | [retry_motion_asset_import](app/api.py#L2855) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/privacy` | [motion_privacy_review](app/api.py#L3690) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/privacy` | [update_motion_privacy](app/api.py#L3695) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/provider` | [update_motion_provider](app/api.py#L2783) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/remote-id` | [set_remote_motion_task_id](app/api.py#L2824) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/result` | [attach_motion_result](app/api.py#L2809) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/result-history` | [motion_result_history](app/api.py#L2830) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/retry` | [retry_motion_task](app/api.py#L2792) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/sync` | [sync_motion_task](app/api.py#L2827) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/motion-prompt` | [motion_prompt](app/api.py#L2216) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/motion-prompt` | [save_motion_prompt](app/api.py#L2219) | domain.write |
| GET | `/api[/v1]/video-callback/security` | [video_callback_security](app/api.py#L2328) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/video-providers` | [video_providers](app/api.py#L2225) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/video-providers/{provider_id}/config` | [delete_video_provider_config](app/api.py#L2294) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/video-providers/{provider_id}/config` | [get_video_provider_config](app/api.py#L2309) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/video-providers/{provider_id}/config` | [configure_video_provider](app/api.py#L2278) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/video-providers/{provider_id}/credential-status` | [video_provider_credential_status](app/api.py#L2317) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/video-providers/{provider_id}/health` | [video_provider_health](app/api.py#L2311) | Original access helper/default/middleware; see source |

Navigation: CORE_SCREENPLAY, A12, CORE_AUDIO, FS_PROCESSING. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_AUDIO · Audio / TTS / BGM / Ambience / SFX

Page: Production → Audio / TTS / BGM / Ambience / SFX; ENGINEERING_UI.

Components: [`frontend/src/novel/AudioGenerationPanel.tsx`](frontend/src/novel/AudioGenerationPanel.tsx), [`frontend/src/novel/AudioTaskInspector.tsx`](frontend/src/novel/AudioTaskInspector.tsx), [`frontend/src/novel/SpeechSynthesisPanel.tsx`](frontend/src/novel/SpeechSynthesisPanel.tsx), [`frontend/src/novel/AudiobookManifestPanel.tsx`](frontend/src/novel/AudiobookManifestPanel.tsx).

Authority: [`app/services/audiobook_service.py`](app/services/audiobook_service.py), [`app/audio_production_store.py`](app/audio_production_store.py), [`app/audio_providers.py`](app/audio_providers.py), [`app/api.py`](app/api.py).

Original source-linked audio/TTS attempts and verified binary media. Character voice, emotion/dialogue attribution remain B03; sound design is original audio track input, never a second provider queue.

Real voice/music/ambience quality NOT_RUN; original privacy/reference-voice permission required. Unknown or stale attempts are explicit; no automatic resynthesis after restart.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/audio/generate` | [generate_audio](app/api.py#L2514) | domain.write |
| GET | `/api[/v1]/audio/providers` | [list_audio_providers](app/api.py#L2489) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/audio/providers/{provider_id}` | [remove_audio_provider](app/api.py#L2504) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/audio/providers/{provider_id}` | [configure_audio_provider](app/api.py#L2497) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/audio-production/settings` | [audio_production_settings](app/api.py#L2543) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/audio-production/settings` | [audio_production_settings_update](app/api.py#L2549) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/export` | [export_audiobook_chapter](app/api.py#L2705) | domain.read |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/queue` | [queue_audiobook_chapter](app/api.py#L2584) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/queue-segments` | [queue_audiobook_segments](app/api.py#L2598) | domain.write |
| GET | `/api[/v1]/novels/{nid}/audiobook/jobs` | [list_audiobook_jobs](app/api.py#L2616) | domain.read |
| POST | `/api[/v1]/novels/{nid}/audiobook/jobs/consume` | [consume_audiobook_jobs](app/api.py#L2684) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/jobs/{job_id}/cancel` | [cancel_audiobook_job](app/api.py#L2654) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/jobs/{job_id}/execute` | [execute_audiobook_job](app/api.py#L2663) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/jobs/{job_id}/retry` | [retry_audiobook_job](app/api.py#L2645) | domain.write |
| GET | `/api[/v1]/novels/{nid}/audiobook/jobs/{job_id}/subtitles.{format}` | [audiobook_job_subtitles](app/api.py#L2633) | domain.read |
| GET | `/api[/v1]/novels/{nid}/audiobook/manifest` | [audiobook_manifest](app/api.py#L2555) | domain.read |
| GET | `/api[/v1]/novels/{nid}/audiobook/mix-plan` | [audiobook_mix_plan](app/api.py#L2575) | domain.read |
| GET | `/api[/v1]/novels/{nid}/speech-generations` | [list_speech_generations](app/api.py#L2537) | domain.read |
| POST | `/api[/v1]/novels/{nid}/speech-generations/import` | [import_generated_speech](app/api.py#L2719) | domain.write |
| POST | `/api[/v1]/speech/synthesize` | [synthesize_speech](app/api.py#L2468) | domain.write |

Navigation: B03, B04, FS_PROCESSING, CORE_ASSETS. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_EXPORT · Export / History / Snapshot preflight

Page: Production → Export / History / Snapshot preflight; ENGINEERING_UI.

Components: [`frontend/src/novel/ExportPanel.tsx`](frontend/src/novel/ExportPanel.tsx).

Authority: [`app/services/export_job_service.py`](app/services/export_job_service.py), [`app/services/export_snapshot_authority.py`](app/services/export_snapshot_authority.py), [`app/manuscript_sources.py`](app/manuscript_sources.py), [`app/export_formats.py`](app/export_formats.py), [`app/industry_export_formats.py`](app/industry_export_formats.py), [`app/api.py`](app/api.py).

Original immutable snapshot job/history and captured resources own exports. Branch snapshots include exact owner/scope/version/document digest and never project datasets/outline. Historical branch-labelled artifacts without valid branch evidence require independent PROJECT access and are filtered before pagination; artifact bytes are not rewritten.

Explicit cancel/retry/recovery uses original job; export download is not proof a target app accepted it. Cancel cannot recall already downloaded bytes; restart never exports current mutable source under an old job.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/agent-jobs/export.csv` | [export_agent_jobs](app/api.py#L988) | domain.read |
| GET | `/api[/v1]/exports` | [list_exports](app/api.py#L1650) | domain.read |
| POST | `/api[/v1]/exports` | [create_export](app/api.py#L1685) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/exports/{job_id}` | [get_export](app/api.py#L1846) | domain.read |
| POST | `/api[/v1]/exports/{job_id}/cancel` | [cancel_export](app/api.py#L1753) | domain.write |
| GET | `/api[/v1]/exports/{job_id}/download` | [download_export](app/api.py#L1810) | domain.read |
| POST | `/api[/v1]/exports/{job_id}/retry` | [retry_export](app/api.py#L1775) | domain.write |
| POST | `/api[/v1]/novels/{nid}/audiobook/chapters/{chapter_id}/export` | [export_audiobook_chapter](app/api.py#L2705) | domain.read |
| GET | `/api[/v1]/novels/{nid}/export` | [export_novel](app/api.py#L1578) | Original access helper/default/middleware; see source |

Navigation: U11, U14, A12, FS_ENGINES, B05. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_PROCESSING · ASR / Forced alignment / Burn-in adapters

Page: Production → ASR / Forced alignment / Burn-in adapters; FORMAL_UI_SURFACE_CONTRACT.

Components: [`frontend/src/experimental/SubtitleTimelinePanel.tsx`](frontend/src/experimental/SubtitleTimelinePanel.tsx).

Authority: [`app/experimental/subtitle_processing.py`](app/experimental/subtitle_processing.py), [`app/experimental/subtitle_timeline.py`](app/experimental/subtitle_timeline.py), [`app/experimental/subtitle_timeline_api.py`](app/experimental/subtitle_timeline_api.py).

SubtitleTimelineService owns exact caption/media/source digest, rational timing and private processing attempt with claim/epoch/version/history; no second task queue.

Queue/execute/cancel/recover/resume/approve/reject/reviewed download. Atomic cue update only after review; original task/review projections. Real ASR/alignment model admission NOT_CONFIGURED; burn-in trusted adapter/real rendering NOT_RUN. Formal UI contract.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/catalog` | [catalog](app/experimental/subtitle_timeline_api.py#L19) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/catalog` | [processing_catalog](app/experimental/subtitle_timeline_api.py#L41) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/tasks` | [processing_tasks](app/experimental/subtitle_timeline_api.py#L44) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/tasks` | [queue_processing](app/experimental/subtitle_timeline_api.py#L47) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/tasks/{rid}/file` | [processing_file](app/experimental/subtitle_timeline_api.py#L54) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/processing/tasks/{rid}/{action}` | [processing_action](app/experimental/subtitle_timeline_api.py#L50) | domain.review, domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records` | [records](app/experimental/subtitle_timeline_api.py#L22) | domain.read |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records` | [create](app/experimental/subtitle_timeline_api.py#L25) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records/{rid}` | [update](app/experimental/subtitle_timeline_api.py#L28) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records/{rid}/cues/{cid}/merge` | [merge](app/experimental/subtitle_timeline_api.py#L34) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records/{rid}/cues/{cid}/split` | [split](app/experimental/subtitle_timeline_api.py#L31) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/subtitle-timeline/records/{rid}/file.{format}` | [download](app/experimental/subtitle_timeline_api.py#L37) | domain.read |

Navigation: B04, B03, CORE_VIDEO, FS_REVIEW, U07. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_ENGINES · Godot / Ren'Py export adapters

Page: Production → Godot / Ren'Py export adapters; ENGINEERING_UI.

Components: [`frontend/src/experimental/InteractiveStoryPanel.tsx`](frontend/src/experimental/InteractiveStoryPanel.tsx).

Authority: [`app/experimental/interactive_story.py`](app/experimental/interactive_story.py), [`app/experimental/interactive_story_api.py`](app/experimental/interactive_story_api.py).

Shipped EngineExportAdapter validators/file exporters stay under original reviewed InteractiveStoryService bundle. Godot data schema and Ren'Py bounded text/menu subset retain source IDs and deterministic checksums.

Source/current review and expected version before export-preview/export. Bounded synchronous export cancellation discards response; explicit regeneration on restart. No engine launch/install. Actual Godot/Ren'Py acceptance NOT_RUN.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories` | [stories](app/experimental/interactive_story_api.py#L34) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories` | [create](app/experimental/interactive_story_api.py#L49) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories/catalog` | [catalog](app/experimental/interactive_story_api.py#L29) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories/engine-contract` | [engine_contract](app/experimental/interactive_story_api.py#L39) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}` | [story](app/experimental/interactive_story_api.py#L44) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}` | [save](app/experimental/interactive_story_api.py#L54) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/export` | [service.export](app/experimental/interactive_story_api.py#L70) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/export-preview` | [service.export_preview](app/experimental/interactive_story_api.py#L69) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/history` | [service.revisions](app/experimental/interactive_story_api.py#L71) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/preview` | [service.preview](app/experimental/interactive_story_api.py#L66) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/refresh` | [service.refresh](app/experimental/interactive_story_api.py#L68) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/refresh-preview` | [service.refresh_preview](app/experimental/interactive_story_api.py#L67) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/restore-revision` | [service.restore_revision](app/experimental/interactive_story_api.py#L72) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/review` | [service.review](app/experimental/interactive_story_api.py#L65) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/review-preview` | [service.review_preview](app/experimental/interactive_story_api.py#L64) | domain.review |

Navigation: B07, CORE_EXPORT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Assets

### A09 · Asset lineage and derived relationships

Page: Assets → Lineage / Provenance; ENGINEERING_UI.

Components: [`frontend/src/experimental/ProductionLineagePanel.tsx`](frontend/src/experimental/ProductionLineagePanel.tsx), [`frontend/src/novel/AssetInspector.tsx`](frontend/src/novel/AssetInspector.tsx).

Authority: [`app/services/asset_library_service.py`](app/services/asset_library_service.py), [`app/experimental/production_lineage.py`](app/experimental/production_lineage.py), [`app/experimental/media.py`](app/experimental/media.py), [`frontend/src/experimental/ProductionLineagePanel.tsx`](frontend/src/experimental/ProductionLineagePanel.tsx), [`app/experimental/production_lineage_api.py`](app/experimental/production_lineage_api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py).

Original AssetLibraryService/DAG retains observed model/provider/workflow/input/parent hashes and source Scene/Shot/version evidence.

Inspect and explicit lineage/replay preflight; request cancellation leaves original asset intact. Restart rereads current asset authority; unknown historical provenance remains unknown.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/media/adapters` | [adapters](app/experimental/media_api.py#L26) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/catalog` | [catalog](app/experimental/media_api.py#L31) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [briefs](app/experimental/media_api.py#L36) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [create_cover](app/experimental/media_api.py#L41) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs/{rid}` | [update_cover](app/experimental/media_api.py#L46) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals` | [proposals](app/experimental/media_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/compare` | [compare](app/experimental/media_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/preview` | [preview](app/experimental/media_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/{action}` | [review](app/experimental/media_api.py#L114) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [storyboard_briefs](app/experimental/media_api.py#L52) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [create_storyboard](app/experimental/media_api.py#L57) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs/{rid}` | [update_storyboard](app/experimental/media_api.py#L62) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [tasks](app/experimental/media_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [queue](app/experimental/media_api.py#L73) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks/{rid}/{action}` | [task_action](app/experimental/media_api.py#L78) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/production/assets` | [assets](app/experimental/production_lineage_api.py#L68) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/production/assets/{aid}` | [asset](app/experimental/production_lineage_api.py#L73) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/production/assets/{aid}/impact` | [impact](app/experimental/production_lineage_api.py#L83) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/production/assets/{aid}/lineage` | [annotate](app/experimental/production_lineage_api.py#L78) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/production/manifests` | [manifests](app/experimental/production_lineage_api.py#L88) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/production/manifests` | [capture](app/experimental/production_lineage_api.py#L93) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/production/manifests/{rid}/export` | [export](app/experimental/production_lineage_api.py#L103) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/production/manifests/{rid}/preflight` | [preflight](app/experimental/production_lineage_api.py#L98) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/production/manifests/{rid}/replay` | [replay](app/experimental/production_lineage_api.py#L108) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/production/replays` | [replays](app/experimental/production_lineage_api.py#L113) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/production/replays/{rid}/cancel` | [cancel](app/experimental/production_lineage_api.py#L123) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/production/replays/{rid}/execute` | [execute](app/experimental/production_lineage_api.py#L118) | domain.write |

Navigation: CORE_ASSETS, A13, FS_VISUAL, U06, B06. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U14 · Portable project, relink and safe cleanup

Page: Assets → Portable projects / Storage health / Relink; ENGINEERING_UI.

Components: [`frontend/src/experimental/PortableProjectsPanel.tsx`](frontend/src/experimental/PortableProjectsPanel.tsx).

Authority: [`app/experimental/portable_projects.py`](app/experimental/portable_projects.py), [`app/backup_restore.py`](app/backup_restore.py), [`app/services/asset_library_service.py`](app/services/asset_library_service.py), [`frontend/src/experimental/PortableProjectsPanel.tsx`](frontend/src/experimental/PortableProjectsPanel.tsx), [`app/experimental/portable_projects_api.py`](app/experimental/portable_projects_api.py).

Original backup/import/apply and AssetLibrary owners; scoped portable manifests and journals are orchestration, not second project or asset authority.

Preflight missing/corrupt resources, relink exact hashes, explicit repair/recover, CAS/current-reference checks and restart journals. Selected bundles are not complete Canon/history backups.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/portable-projects/catalog` | [catalog](app/experimental/portable_projects_api.py#L44) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/portable-projects/cleanup` | [cleanup](app/experimental/portable_projects_api.py#L89) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/portable-projects/export` | [export](app/experimental/portable_projects_api.py#L54) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/portable-projects/import-preflight` | [import_preflight](app/experimental/portable_projects_api.py#L64) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/portable-projects/records` | [records](app/experimental/portable_projects_api.py#L49) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/portable-projects/records/{rid}/file` | [file](app/experimental/portable_projects_api.py#L58) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/portable-projects/records/{rid}/relink` | [relink](app/experimental/portable_projects_api.py#L80) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/portable-projects/records/{rid}/restore` | [restore](app/experimental/portable_projects_api.py#L70) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/portable-projects/relink-preflight` | [relink_preflight](app/experimental/portable_projects_api.py#L74) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/portable-projects/storage` | [storage](app/experimental/portable_projects_api.py#L84) | Original access helper/default/middleware; see source |

Navigation: CORE_ASSETS, FS_IMPORT, CORE_EXPORT, B10. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_ASSETS · Asset library / References / Integrity

Page: Assets → Asset library / References / Integrity; ENGINEERING_UI.

Components: [`frontend/src/novel/AssetLibraryPanel.tsx`](frontend/src/novel/AssetLibraryPanel.tsx), [`frontend/src/novel/AssetInspector.tsx`](frontend/src/novel/AssetInspector.tsx), [`frontend/src/novel/VisualReferencePanel.tsx`](frontend/src/novel/VisualReferencePanel.tsx), [`frontend/src/novel/AuthenticatedMedia.tsx`](frontend/src/novel/AuthenticatedMedia.tsx), [`frontend/src/novel/EntityAssetPanel.tsx`](frontend/src/novel/EntityAssetPanel.tsx), [`frontend/src/ui/AssetWorkspaceRoute.tsx`](frontend/src/ui/AssetWorkspaceRoute.tsx).

Authority: [`app/services/asset_library_service.py`](app/services/asset_library_service.py), [`app/asset_lifecycle_api.py`](app/asset_lifecycle_api.py), [`app/media_files.py`](app/media_files.py), [`app/services/v1_capability_service.py`](app/services/v1_capability_service.py), [`app/api.py`](app/api.py).

Unique original AssetLibrary owner, authenticated media bytes, asset version/SHA-256, provenance, approval and recoverable lifecycle. Appearance profiles reuse original visual-memory records.

Asset relink/repair goes through U14 current manifest and exact hashes; missing bytes are not approved from metadata. Original provider result/review states remain distinct.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/asset-providers` | [asset_providers](app/api.py#L1118) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/asset-providers/{provider_id}` | [asset_provider_config_delete](app/api.py#L1147) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/asset-providers/{provider_id}` | [asset_provider_config_set](app/api.py#L1138) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/asset-tasks/worker/config` | [asset_task_worker_config](app/api.py#L2922) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/asset-tasks/worker/config` | [update_asset_task_worker_config](app/api.py#L2924) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/assets/{asset_id}` | [delete_asset](app/api.py#L1894) | domain.write |
| GET | `/api[/v1]/assets/{asset_id}` | [get_asset](app/api.py#L1880) | domain.read |
| GET | `/api[/v1]/assets/{asset_id}/derivatives` | [asset_derivatives](app/api.py#L3354) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/assets/{asset_id}/derivatives` | [create_asset_derivative](app/api.py#L3359) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/assets/{asset_id}/download` | [download_asset](app/api.py#L1887) | domain.read |
| POST | `/api[/v1]/novels/{nid}/asset-tasks/claim` | [claim_asset_tasks](app/api.py#L2895) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/asset-tasks/dispatch` | [dispatch_asset_tasks](app/api.py#L2897) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/asset-tasks/recover` | [recover_all_asset_tasks](app/api.py#L2887) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/asset-tasks/stats` | [asset_task_stats](app/api.py#L2891) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/asset-tasks/timeout` | [timeout_asset_tasks](app/api.py#L2899) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/asset-tasks/worker/run-once` | [run_asset_task_worker](app/api.py#L2901) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/asset-tasks/worker/start` | [start_asset_task_worker](app/api.py#L2909) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/asset-tasks/worker/status` | [asset_task_worker_status](app/api.py#L2920) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/asset-tasks/worker/stop` | [stop_asset_task_worker](app/api.py#L2918) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/asset-trash` | [trash](app/asset_lifecycle_api.py#L51) | domain.read |
| GET | `/api[/v1]/novels/{nid}/assets` | [list_assets](app/api.py#L1866) | domain.read |
| POST | `/api[/v1]/novels/{nid}/assets` | [upload_asset](app/api.py#L1856) | domain.write |
| GET | `/api[/v1]/novels/{nid}/assets/{asset_id}/references` | [references](app/asset_lifecycle_api.py#L64) | domain.read |
| POST | `/api[/v1]/novels/{nid}/assets/{asset_id}/restore` | [restore](app/asset_lifecycle_api.py#L58) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks` | [create_asset_tasks](app/api.py#L2876) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/cleanup` | [cleanup_asset_tasks](app/api.py#L2889) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/recover` | [recover_asset_tasks](app/api.py#L2885) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/stats` | [screenplay_asset_task_stats](app/api.py#L2893) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}` | [update_asset_task](app/api.py#L2878) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}/execute` | [execute_asset_task](app/api.py#L2880) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}/retry` | [retry_asset_task](app/api.py#L2883) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/assets` | [plan_assets](app/api.py#L2870) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/assets/approve` | [approve_assets](app/api.py#L2872) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/assets/{asset_id}` | [update_asset](app/api.py#L2874) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets` | [list_motion_asset_imports](app/api.py#L2845) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets/retry` | [retry_failed_motion_asset_imports](app/api.py#L2849) | domain.write |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/asset-reference` | [motion_asset_reference](app/api.py#L2834) | domain.read |
| GET | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [motion_asset_import_status](app/api.py#L2841) | domain.read |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset` | [import_motion_asset](app/api.py#L2838) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/download` | [download_motion_asset](app/api.py#L2852) | domain.write |
| POST | `/api[/v1]/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/retry` | [retry_motion_asset_import](app/api.py#L2855) | domain.write |
| GET | `/api[/v1]/novels/{nid}/visual-memory` | [visual_memory](app/api.py#L3312) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/visual-memory` | [create_visual_memory](app/api.py#L3317) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/novels/{nid}/visual-memory/{memory_id}` | [delete_visual_memory](app/api.py#L3347) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/visual-memory/{memory_id}` | [get_visual_memory](app/api.py#L3336) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/visual-memory/{memory_id}` | [update_visual_memory](app/api.py#L3341) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/visual-reference-search` | [search](app/asset_lifecycle_api.py#L102) | domain.read |
| GET | `/api[/v1]/novels/{nid}/visual-references` | [list_references](app/asset_lifecycle_api.py#L70) | domain.read |
| POST | `/api[/v1]/novels/{nid}/visual-references` | [create_reference](app/asset_lifecycle_api.py#L81) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/visual-references/{memory_id}` | [update_reference](app/asset_lifecycle_api.py#L88) | domain.write |
| POST | `/api[/v1]/novels/{nid}/visual-references/{memory_id}/approve` | [approve_reference](app/asset_lifecycle_api.py#L95) | domain.write |

Navigation: U14, A09, FS_VISUAL, CORE_IMAGES, CORE_VIDEO. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_VISUAL · Visual Identity / Similarity / Drift

Page: Assets → Visual Identity / Similarity / Drift; FORMAL_UI_SURFACE_CONTRACT.

Components: [`frontend/src/novel/VisualReferencePanel.tsx`](frontend/src/novel/VisualReferencePanel.tsx), [`frontend/src/novel/VisualContextPanel.tsx`](frontend/src/novel/VisualContextPanel.tsx).

Authority: [`app/experimental/visual_identity.py`](app/experimental/visual_identity.py), [`app/experimental/embeddings.py`](app/experimental/embeddings.py), [`app/experimental/review_adapter_jobs.py`](app/experimental/review_adapter_jobs.py), [`app/experimental/review_adapter_projection.py`](app/experimental/review_adapter_projection.py), [`app/services/v1_capability_service.py`](app/services/v1_capability_service.py), [`app/experimental/embeddings_api.py`](app/experimental/embeddings_api.py), [`app/api.py`](app/api.py).

Appearance profile projects original approved CHARACTER visual-memory reference, appearance_version, clothing/hair/body/accessories and asset digest. Comparison adds only review receipt, never another profile store.

Pinned candidate plus approved current references, target IMAGE/VIDEO and explicit threshold require review before selection. Bounded receipt admission reserves terminal/recovery/invalidation capacity; restart never replays, cancel/recover fence tokens, source-revoked responses omit old request/lineage/results. Task/Review are original-owner read-through projections; creator/read visibility and write+CAS cancellation remain distinct. FORMAL_SOURCE_ONLY target, no rendered exact-open control. Real image embedding NOT_CONFIGURED/NOT_RUN.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/hybrid-query` | [hybrid_query](app/experimental/embeddings_api.py#L99) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes` | [indexes](app/experimental/embeddings_api.py#L62) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes` | [create](app/experimental/embeddings_api.py#L67) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes/{rid}` | [edit](app/experimental/embeddings_api.py#L73) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes/{rid}/records` | [records](app/experimental/embeddings_api.py#L79) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/indexes/{rid}/{action}` | [action](app/experimental/embeddings_api.py#L84) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/providers` | [providers](app/experimental/embeddings_api.py#L56) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/query` | [query](app/experimental/embeddings_api.py#L94) | domain.read |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/sources` | [sources](app/experimental/embeddings_api.py#L50) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/status` | [status](app/experimental/embeddings_api.py#L45) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks` | [visual_checks](app/experimental/embeddings_api.py#L109) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks` | [create_visual_check](app/experimental/embeddings_api.py#L124) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks/{rid}` | [visual_check](app/experimental/embeddings_api.py#L114) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks/{rid}/selection` | [visual_selection](app/experimental/embeddings_api.py#L119) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/checks/{rid}/{action}` | [visual_action](app/experimental/embeddings_api.py#L130) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/embeddings/visual-identity/profiles` | [profiles](app/experimental/embeddings_api.py#L104) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/visual-memory` | [visual_memory](app/api.py#L3312) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/visual-memory` | [create_visual_memory](app/api.py#L3317) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/novels/{nid}/visual-memory/{memory_id}` | [delete_visual_memory](app/api.py#L3347) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/visual-memory/{memory_id}` | [get_visual_memory](app/api.py#L3336) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/visual-memory/{memory_id}` | [update_visual_memory](app/api.py#L3341) | Original access helper/default/middleware; see source |

Navigation: CORE_ASSETS, CORE_IMAGES, CORE_VIDEO, B06, FS_SEMANTIC, U07, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Collaboration

### B08 · Writer room and team review

Page: Collaboration → Writer Room / Assignments / Comments; ENGINEERING_UI.

Components: [`frontend/src/experimental/WriterRoomPanel.tsx`](frontend/src/experimental/WriterRoomPanel.tsx), [`frontend/src/CollaborationPanels.tsx`](frontend/src/CollaborationPanels.tsx).

Authority: [`app/experimental/writer_room.py`](app/experimental/writer_room.py), [`app/services/creation_workbench_service.py`](app/services/creation_workbench_service.py), [`app/experimental/inbox.py`](app/experimental/inbox.py), [`frontend/src/experimental/WriterRoomPanel.tsx`](frontend/src/experimental/WriterRoomPanel.tsx), [`app/experimental/writer_room_api.py`](app/experimental/writer_room_api.py).

Original comments, revision assignments and review target identities; finishing an assignment does not approve or apply that target.

CAS/edit/status/review/reopen; retained task and comment history, source-anchor stale state; async room snapshots are not realtime coediting.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room` | [overview](app/experimental/writer_room_api.py#L42) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/catalog` | [catalog](app/experimental/writer_room_api.py#L52) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/chapters/{cid}` | [chapter](app/experimental/writer_room_api.py#L57) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/comments` | [comments](app/experimental/writer_room_api.py#L89) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/comments` | [comment](app/experimental/writer_room_api.py#L94) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/comments/{rid}` | [comment_action](app/experimental/writer_room_api.py#L98) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/conflicts` | [conflicts](app/experimental/writer_room_api.py#L72) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/index` | [index](app/experimental/writer_room_api.py#L62) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/notices` | [notices](app/experimental/writer_room_api.py#L67) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/packages/download` | [download](app/experimental/writer_room_api.py#L107) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/packages/preview` | [preview](app/experimental/writer_room_api.py#L102) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/presence-contract` | [presence_contract](app/experimental/writer_room_api.py#L47) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime` | [realtime_contract](app/experimental/writer_room_api.py#L144) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/operations` | [realtime_prepare](app/experimental/writer_room_api.py#L172) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/operations/{rid}` | [realtime_operation](app/experimental/writer_room_api.py#L178) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/operations/{rid}/actions` | [realtime_action](app/experimental/writer_room_api.py#L183) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/participants` | [realtime_presence](app/experimental/writer_room_api.py#L149) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/participants` | [realtime_join](app/experimental/writer_room_api.py#L154) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/participants/{rid}/actions` | [realtime_transition](app/experimental/writer_room_api.py#L160) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/participants/{rid}/cursor` | [realtime_cursor](app/experimental/writer_room_api.py#L166) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/tasks` | [create](app/experimental/writer_room_api.py#L77) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/writer-room/tasks/{rid}` | [update](app/experimental/writer_room_api.py#L81) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/tasks/{rid}/transition` | [transition](app/experimental/writer_room_api.py#L85) | domain.review, domain.write |

Navigation: FS_REALTIME, FS_BRANCH, FS_REVIEW, A03, U07. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### B09 · Project fork and merge

Page: Collaboration → Project Fork / Human Merge / Shared Universe; ENGINEERING_UI.

Components: [`frontend/src/experimental/ProjectForksPanel.tsx`](frontend/src/experimental/ProjectForksPanel.tsx), [`frontend/src/experimental/StructuredForksPanel.tsx`](frontend/src/experimental/StructuredForksPanel.tsx), [`frontend/src/experimental/SharedUniversePanel.tsx`](frontend/src/experimental/SharedUniversePanel.tsx).

Authority: [`app/experimental/project_forks.py`](app/experimental/project_forks.py), [`app/experimental/structured_forks.py`](app/experimental/structured_forks.py), [`app/experimental/world.py`](app/experimental/world.py), [`frontend/src/experimental/ProjectForksPanel.tsx`](frontend/src/experimental/ProjectForksPanel.tsx), [`frontend/src/experimental/SharedUniversePanel.tsx`](frontend/src/experimental/SharedUniversePanel.tsx), [`app/experimental/project_forks_api.py`](app/experimental/project_forks_api.py).

Original selected project/structured source snapshots, target CAS and explicit per-work universe pins; immutable snapshots never become another Canon owner.

Fork/compare/conflict/human merge, source/target authorization/deletion/privacy checks, history/release and explicit recovery. No auto-repin or implicit model-context injection.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/catalog` | [catalog](app/experimental/project_forks_api.py#L53) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/merges/{mid}/recovery` | [recovery](app/experimental/project_forks_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/merges/{mid}/restore` | [restore](app/experimental/project_forks_api.py#L88) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/preflight` | [preflight](app/experimental/project_forks_api.py#L63) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/records` | [records](app/experimental/project_forks_api.py#L58) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/catalog` | [structured_catalog](app/experimental/project_forks_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/merges/{mid}/recovery` | [structured_recovery](app/experimental/project_forks_api.py#L128) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/merges/{mid}/restore` | [structured_restore](app/experimental/project_forks_api.py#L133) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/preflight` | [structured_preflight](app/experimental/project_forks_api.py#L108) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/records` | [structured_records](app/experimental/project_forks_api.py#L103) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/{rid}/apply` | [structured_apply](app/experimental/project_forks_api.py#L123) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/{rid}/compare` | [structured_compare](app/experimental/project_forks_api.py#L118) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/structured/{rid}/create` | [structured_create](app/experimental/project_forks_api.py#L113) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/catalog` | [universe_catalog](app/experimental/project_forks_api.py#L146) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/incoming` | [universe_incoming](app/experimental/project_forks_api.py#L191) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/incoming/{source_nid}/{pin_id}` | [universe_incoming_snapshot](app/experimental/project_forks_api.py#L196) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pin-preview` | [universe_pin_preview](app/experimental/project_forks_api.py#L171) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pins` | [universe_pins](app/experimental/project_forks_api.py#L166) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pins` | [universe_pin](app/experimental/project_forks_api.py#L176) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pins/{rid}/history` | [universe_pin_history](app/experimental/project_forks_api.py#L186) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/pins/{rid}/release` | [universe_release](app/experimental/project_forks_api.py#L181) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/snapshot-preview` | [universe_snapshot_preview](app/experimental/project_forks_api.py#L156) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/snapshots` | [universe_snapshots](app/experimental/project_forks_api.py#L151) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/universe/snapshots` | [universe_create_snapshot](app/experimental/project_forks_api.py#L161) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/{rid}/apply` | [apply](app/experimental/project_forks_api.py#L78) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/{rid}/compare` | [compare](app/experimental/project_forks_api.py#L73) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/project-forks/{rid}/create` | [create](app/experimental/project_forks_api.py#L68) | Original access helper/default/middleware; see source |

Navigation: FS_BRANCH, FS_UNIVERSE, CORE_MANUSCRIPT, FS_CANON, B10. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### B10 · Offline synchronization foundation

Page: Collaboration → Offline exchange / Reconciliation; ENGINEERING_UI.

Components: [`frontend/src/experimental/OfflineSyncPanel.tsx`](frontend/src/experimental/OfflineSyncPanel.tsx).

Authority: [`app/experimental/offline_sync.py`](app/experimental/offline_sync.py), [`app/experimental/portable_projects.py`](app/experimental/portable_projects.py), [`frontend/src/experimental/OfflineSyncPanel.tsx`](frontend/src/experimental/OfflineSyncPanel.tsx), [`app/experimental/offline_sync_api.py`](app/experimental/offline_sync_api.py).

Original selected-source outbox/inbox/channel and diff3 review; manual local exchange is not production cloud or a second manuscript system.

CAS/checkpoint/import/review/cancel/recover with ambiguous outcome reconciliation; restart keeps journal and requires explicit action.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/catalog` | [catalog](app/experimental/offline_sync_api.py#L58) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels` | [open_channel](app/experimental/offline_sync_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/queue` | [queue](app/experimental/offline_sync_api.py#L88) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/receive` | [receive](app/experimental/offline_sync_api.py#L93) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/revoke` | [revoke](app/experimental/offline_sync_api.py#L73) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/selection` | [change_selection](app/experimental/offline_sync_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/selection/preview` | [preview_selection](app/experimental/offline_sync_api.py#L78) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/inbox/{mid}/apply` | [apply](app/experimental/offline_sync_api.py#L118) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/inbox/{mid}/recovery` | [recovery](app/experimental/offline_sync_api.py#L126) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/inbox/{mid}/review` | [review](app/experimental/offline_sync_api.py#L113) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/outbox/{mid}` | [inspect](app/experimental/offline_sync_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/outbox/{mid}/delivery` | [delivery](app/experimental/offline_sync_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/outbox/{mid}/export` | [export](app/experimental/offline_sync_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/production` | [production_contract](app/experimental/offline_sync_api.py#L139) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/devices` | [production_device](app/experimental/offline_sync_api.py#L149) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/devices/{rid}/revoke` | [production_revoke](app/experimental/offline_sync_api.py#L154) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/manifests` | [production_manifest](app/experimental/offline_sync_api.py#L159) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/manifests/{rid}` | [production_manifest_detail](app/experimental/offline_sync_api.py#L164) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/records` | [production_records](app/experimental/offline_sync_api.py#L144) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/transfers` | [production_transfer](app/experimental/offline_sync_api.py#L169) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/transfers/{rid}/actions` | [production_action](app/experimental/offline_sync_api.py#L174) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/records` | [records](app/experimental/offline_sync_api.py#L63) | Original access helper/default/middleware; see source |

Navigation: FS_SYNC, B09, U14, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_COLLAB · Workspace / Membership / Permissions

Page: Collaboration → Workspace / Membership / Permissions; ENGINEERING_UI.

Components: [`frontend/src/WorkspaceManagement.tsx`](frontend/src/WorkspaceManagement.tsx), [`frontend/src/PermissionManagement.tsx`](frontend/src/PermissionManagement.tsx), [`frontend/src/CollaborationPanels.tsx`](frontend/src/CollaborationPanels.tsx).

Authority: [`app/services/collaboration_scope_service.py`](app/services/collaboration_scope_service.py), [`app/services/authorization_service.py`](app/services/authorization_service.py), [`app/collaboration_admin.py`](app/collaboration_admin.py), [`app/application/collaboration_service.py`](app/application/collaboration_service.py), [`app/collaboration_api.py`](app/collaboration_api.py), [`app/api.py`](app/api.py), [`frontend/src/ui/scopeLabels.ts`](frontend/src/ui/scopeLabels.ts).

Trusted session/current membership and workspace/project/storyline/branch scope remain authority; roles or hidden controls in browser are never grants. Original audit and revision-CAS boundaries retained. Shared selected-owner labels use supplied nonblank names or exact known IDs; a selected branch without metadata is never called mainline/default storyline. Missing owner IDs stay unselected; local mainline labels apply only to an actual unscoped local manuscript.

Missing branch document is unavailable, never mainline fallback. Revocation ends current access; reconnect reauthorizes. Administrative operations preserve their original confirmations/recovery semantics.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/audit` | [audit](app/collaboration_api.py#L206) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/bootstrap` | [bootstrap](app/collaboration_api.py#L146) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters` | [chapter_list](app/collaboration_api.py#L177) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters` | [chapter_create](app/collaboration_api.py#L184) | domain.write |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/revisions` | [revisions](app/collaboration_api.py#L215) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/revisions/{version}` | [revision_detail](app/collaboration_api.py#L223) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/snapshots` | [snapshots](app/collaboration_api.py#L232) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/snapshots/{snapshot_id}` | [snapshot_detail](app/collaboration_api.py#L238) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/generations/{generation_id}/snapshot` | [generation_snapshot](app/collaboration_api.py#L247) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/members` | [members](app/collaboration_api.py#L162) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/permissions` | [permissions](app/collaboration_api.py#L172) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/story-database/{resource}` | [story_database](app/collaboration_api.py#L195) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/text-runtime-diagnostics` | [text_runtime_diagnostics](app/collaboration_api.py#L157) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/visual-text-workflow` | [visual_text_workflow](app/collaboration_api.py#L152) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/plugins/{plugin_id}/permissions` | [set_plugin_permissions](app/api.py#L3568) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/workspaces` | [list_workspaces](app/api.py#L1052) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workspaces` | [create_workspace](app/api.py#L1049) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/workspaces/{workspace_id}/projects/{project_id}/storylines` | [list_storylines](app/api.py#L1070) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workspaces/{workspace_id}/projects/{project_id}/storylines` | [create_storyline](app/api.py#L1062) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches` | [list_branches](app/api.py#L1081) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches` | [create_branch](app/api.py#L1075) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}` | [get_branch](app/api.py#L1086) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}/narrative/mysteries/{item_id}/transition` | [scoped_mystery_transition](app/api.py#L1095) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}/narrative/proposals/{proposal_id}/accept` | [scoped_proposal_accept](app/api.py#L1105) | Original access helper/default/middleware; see source |

Navigation: FS_BRANCH, FS_REALTIME, B08, FS_SYNC. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_REALTIME · Realtime protocol / Presence / Co-edit inspector

Page: Collaboration → Realtime protocol / Presence / Co-edit inspector; FORMAL_UI_SURFACE_CONTRACT.

Components: [`frontend/src/experimental/WriterRoomPanel.tsx`](frontend/src/experimental/WriterRoomPanel.tsx).

Authority: [`app/experimental/writer_room_realtime.py`](app/experimental/writer_room_realtime.py), [`app/experimental/writer_room.py`](app/experimental/writer_room.py), [`app/experimental/writer_room_api.py`](app/experimental/writer_room_api.py).

WriterRoomService.realtime participant lease/session, cursor-selection/document-version and strict-CAS edit operation. Actual synthetic callback push is distinct from snapshot HTTP list.

Join/heartbeat/disconnect/reconnect/leave/revoke/prepare/apply/cancel/inspect-recovery/adopt/close-without-replay. Restart disconnects leases. Production transport NOT_CONFIGURED; no OT/CRDT or deployed coediting claim.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room` | [overview](app/experimental/writer_room_api.py#L42) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/catalog` | [catalog](app/experimental/writer_room_api.py#L52) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/chapters/{cid}` | [chapter](app/experimental/writer_room_api.py#L57) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/comments` | [comments](app/experimental/writer_room_api.py#L89) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/comments` | [comment](app/experimental/writer_room_api.py#L94) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/comments/{rid}` | [comment_action](app/experimental/writer_room_api.py#L98) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/conflicts` | [conflicts](app/experimental/writer_room_api.py#L72) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/index` | [index](app/experimental/writer_room_api.py#L62) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/notices` | [notices](app/experimental/writer_room_api.py#L67) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/packages/download` | [download](app/experimental/writer_room_api.py#L107) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/packages/preview` | [preview](app/experimental/writer_room_api.py#L102) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/presence-contract` | [presence_contract](app/experimental/writer_room_api.py#L47) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime` | [realtime_contract](app/experimental/writer_room_api.py#L144) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/operations` | [realtime_prepare](app/experimental/writer_room_api.py#L172) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/operations/{rid}` | [realtime_operation](app/experimental/writer_room_api.py#L178) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/operations/{rid}/actions` | [realtime_action](app/experimental/writer_room_api.py#L183) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/participants` | [realtime_presence](app/experimental/writer_room_api.py#L149) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/participants` | [realtime_join](app/experimental/writer_room_api.py#L154) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/participants/{rid}/actions` | [realtime_transition](app/experimental/writer_room_api.py#L160) | domain.read |
| PUT | `/api[/v1]/novels/{nid}/experimental/writer-room/realtime/participants/{rid}/cursor` | [realtime_cursor](app/experimental/writer_room_api.py#L166) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/tasks` | [create](app/experimental/writer_room_api.py#L77) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/writer-room/tasks/{rid}` | [update](app/experimental/writer_room_api.py#L81) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/writer-room/tasks/{rid}/transition` | [transition](app/experimental/writer_room_api.py#L85) | domain.review, domain.write |

Navigation: B08, FS_BRANCH, CORE_MANUSCRIPT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_SYNC · Production sync / Manifest / Device / Checkpoint

Page: Collaboration → Production sync / Manifest / Device / Checkpoint; FORMAL_UI_SURFACE_CONTRACT.

Components: [`frontend/src/experimental/OfflineSyncPanel.tsx`](frontend/src/experimental/OfflineSyncPanel.tsx).

Authority: [`app/experimental/offline_sync_production.py`](app/experimental/offline_sync_production.py), [`app/experimental/offline_sync.py`](app/experimental/offline_sync.py), [`app/experimental/offline_sync_api.py`](app/experimental/offline_sync_api.py).

Original OfflineSync outbox/inbox plus device epoch, manifest/change-set/rich delta/object metadata/transfer checkpoints. Only local/synthetic transport/encryption seam; no production cloud claims.

Register/revoke/seal/prepare/dispatch/cancel/resume and original diff3 review. Explicit copy boundary, current permission/source/device checks. Branch sync NOT_CONFIGURED and denied instead of mainline fallback. Formal inspector contract.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/catalog` | [catalog](app/experimental/offline_sync_api.py#L58) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels` | [open_channel](app/experimental/offline_sync_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/queue` | [queue](app/experimental/offline_sync_api.py#L88) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/receive` | [receive](app/experimental/offline_sync_api.py#L93) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/revoke` | [revoke](app/experimental/offline_sync_api.py#L73) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/selection` | [change_selection](app/experimental/offline_sync_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/channels/{rid}/selection/preview` | [preview_selection](app/experimental/offline_sync_api.py#L78) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/inbox/{mid}/apply` | [apply](app/experimental/offline_sync_api.py#L118) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/inbox/{mid}/recovery` | [recovery](app/experimental/offline_sync_api.py#L126) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/inbox/{mid}/review` | [review](app/experimental/offline_sync_api.py#L113) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/outbox/{mid}` | [inspect](app/experimental/offline_sync_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/outbox/{mid}/delivery` | [delivery](app/experimental/offline_sync_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/outbox/{mid}/export` | [export](app/experimental/offline_sync_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/production` | [production_contract](app/experimental/offline_sync_api.py#L139) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/devices` | [production_device](app/experimental/offline_sync_api.py#L149) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/devices/{rid}/revoke` | [production_revoke](app/experimental/offline_sync_api.py#L154) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/manifests` | [production_manifest](app/experimental/offline_sync_api.py#L159) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/manifests/{rid}` | [production_manifest_detail](app/experimental/offline_sync_api.py#L164) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/records` | [production_records](app/experimental/offline_sync_api.py#L144) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/transfers` | [production_transfer](app/experimental/offline_sync_api.py#L169) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/offline-sync/production/transfers/{rid}/actions` | [production_action](app/experimental/offline_sync_api.py#L174) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/offline-sync/records` | [records](app/experimental/offline_sync_api.py#L63) | Original access helper/default/middleware; see source |

Navigation: B10, U14, FS_REVIEW. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Models

### U09 · Local AI diagnostic and setup guidance

Page: Models → Local AI diagnostics / Workflow inspection; ENGINEERING_UI.

Components: [`frontend/src/ui/LocalAiDiscovery.tsx`](frontend/src/ui/LocalAiDiscovery.tsx), [`frontend/src/experimental/WorkflowInspectionPanel.tsx`](frontend/src/experimental/WorkflowInspectionPanel.tsx), [`frontend/src/novel/RuntimeDiagnostics.tsx`](frontend/src/novel/RuntimeDiagnostics.tsx).

Authority: [`app/model_center/discovery.py`](app/model_center/discovery.py), [`app/model_center/discovery_probes.py`](app/model_center/discovery_probes.py), [`app/experimental/local_ai_inspection.py`](app/experimental/local_ai_inspection.py), [`frontend/src/ui/LocalAiDiscovery.tsx`](frontend/src/ui/LocalAiDiscovery.tsx), [`frontend/src/experimental/WorkflowInspectionPanel.tsx`](frontend/src/experimental/WorkflowInspectionPanel.tsx), [`app/experimental/local_ai_inspection_api.py`](app/experimental/local_ai_inspection_api.py), [`app/model_center/discovery_api.py`](app/model_center/discovery_api.py).

Original Model Center detect, validate, register, explicit enable and launch boundaries; passive Comfy workflow inspection does not execute imported code.

Abort/late-result fences, explicit retry and redacted diagnostic export. Restart rereads configured local runtime; missing hardware, node, model, license and adapter remain explicit.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/model-center/local-ai` | [snapshot](app/model_center/discovery_api.py#L23) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/candidates/{candidate_id}/register` | [register](app/model_center/discovery_api.py#L39) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/candidates/{candidate_id}/validate` | [validate](app/model_center/discovery_api.py#L37) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/model-center/local-ai/registrations/{registration_id}` | [remove](app/model_center/discovery_api.py#L47) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/model-center/local-ai/registrations/{registration_id}` | [configure](app/model_center/discovery_api.py#L41) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/registrations/{registration_id}/disable` | [disable](app/model_center/discovery_api.py#L45) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/registrations/{registration_id}/enable` | [enable](app/model_center/discovery_api.py#L43) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/runtimes` | [add_runtime](app/model_center/discovery_api.py#L33) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/model-center/local-ai/runtimes/{runtime_id}` | [edit_runtime](app/model_center/discovery_api.py#L35) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/scan` | [scan](app/model_center/discovery_api.py#L25) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/local-ai/scan/{scan_id}` | [get_scan](app/model_center/discovery_api.py#L27) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/scan/{scan_id}/cancel` | [cancel](app/model_center/discovery_api.py#L29) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/model-center/local-ai/settings` | [settings](app/model_center/discovery_api.py#L31) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/local-ai/workflow-inspections` | [metadata](app/experimental/local_ai_inspection_api.py#L31) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/local-ai/workflow-inspections/inspect` | [inspect](app/experimental/local_ai_inspection_api.py#L37) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/local-ai/workflow-inspections/reports` | [reports](app/experimental/local_ai_inspection_api.py#L46) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/local-ai/workflow-inspections/reports` | [save](app/experimental/local_ai_inspection_api.py#L52) | domain.write |

Navigation: CORE_MODELS, A06, A07, U12, FS_SDK. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### A06 · Explainable model broker

Page: Models → Model routing / Preflight / Cost preview; ENGINEERING_UI.

Components: [`frontend/src/experimental/ModelBrokerPanel.tsx`](frontend/src/experimental/ModelBrokerPanel.tsx).

Authority: [`app/experimental/model_broker.py`](app/experimental/model_broker.py), [`app/experimental/model_broker_api.py`](app/experimental/model_broker_api.py), [`app/experimental/provider_profiles.py`](app/experimental/provider_profiles.py), [`app/model_center/service.py`](app/model_center/service.py), [`frontend/src/experimental/ModelBrokerPanel.tsx`](frontend/src/experimental/ModelBrokerPanel.tsx).

Original route, model identity, policy, budget/admission and explicit fallback approval own dispatch; unknown cost and quality are not inferred.

Version/source/route preview digest; cancel and original job recovery; never retry an ambiguous paid attempt automatically. Restart requires current route and reviewed preflight.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| PUT | `/api[/v1]/novels/{nid}/experimental/model-broker/budget` | [budget](app/experimental/model_broker_api.py#L121) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/model-broker/generate` | [generate](app/experimental/model_broker_api.py#L139) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/model-broker/history` | [history](app/experimental/model_broker_api.py#L133) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/model-broker/jobs/{reservation_id}` | [job](app/experimental/model_broker_api.py#L195) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/model-broker/jobs/{reservation_id}/cancel` | [cancel](app/experimental/model_broker_api.py#L207) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/model-broker/ledger/{reservation_id}/reconcile` | [reconcile](app/experimental/model_broker_api.py#L184) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/model-broker/preview` | [preview](app/experimental/model_broker_api.py#L114) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/model-broker/price` | [price](app/experimental/model_broker_api.py#L127) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/model-broker/status` | [status](app/experimental/model_broker_api.py#L103) | Original access helper/default/middleware; see source |

Navigation: CORE_MODELS, A07, U08, U16, CORE_GENERATION. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### A07 · Model benchmark and capability evidence

Page: Models → Benchmarks / Capability evidence; ENGINEERING_UI.

Components: [`frontend/src/experimental/ModelBenchmarkPanel.tsx`](frontend/src/experimental/ModelBenchmarkPanel.tsx).

Authority: [`app/experimental/model_benchmark.py`](app/experimental/model_benchmark.py), [`app/experimental/model_benchmark_api.py`](app/experimental/model_benchmark_api.py), [`app/model_center/discovery.py`](app/model_center/discovery.py), [`frontend/src/experimental/ModelBenchmarkPanel.tsx`](frontend/src/experimental/ModelBenchmarkPanel.tsx).

Catalog claims, detection, contract fixtures, measured benchmark records and human output review are separate evidence types tied to exact runtime/model/output identities.

Explicit run/cancel/review with retained records; missing GPU/model configuration stays unavailable. Restart reads receipts, never manufactures throughput, VRAM or quality.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/comparisons` | [compare](app/experimental/model_benchmark_api.py#L114) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/comparisons/{rid}/vote` | [vote](app/experimental/model_benchmark_api.py#L121) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/evidence/import` | [import_evidence](app/experimental/model_benchmark_api.py#L95) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/evidence/{rid}/invalidate` | [invalidate](app/experimental/model_benchmark_api.py#L108) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/evidence/{rid}/review` | [review_evidence](app/experimental/model_benchmark_api.py#L102) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/profiles` | [profiles](app/experimental/model_benchmark_api.py#L57) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/runs` | [start](app/experimental/model_benchmark_api.py#L79) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/runs/{rid}/{action}` | [run_action](app/experimental/model_benchmark_api.py#L85) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/sets` | [create](app/experimental/model_benchmark_api.py#L65) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/sets/{rid}` | [update](app/experimental/model_benchmark_api.py#L72) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/model-benchmarks/status` | [status](app/experimental/model_benchmark_api.py#L47) | Original access helper/default/middleware; see source |

Navigation: CORE_MODELS, A06, U09. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_MODELS · Model Center / Provider configuration

Page: Models → Model Center / Provider configuration; ENGINEERING_UI.

Components: [`frontend/src/ui/ModelCenter.tsx`](frontend/src/ui/ModelCenter.tsx), [`frontend/src/ui/AiControlCenter.tsx`](frontend/src/ui/AiControlCenter.tsx), [`frontend/src/ui/MediaProviderSettings.tsx`](frontend/src/ui/MediaProviderSettings.tsx), [`frontend/src/novel/DeepSeekCredentialControl.tsx`](frontend/src/novel/DeepSeekCredentialControl.tsx).

Authority: [`app/model_center/service.py`](app/model_center/service.py), [`app/model_center/domain.py`](app/model_center/domain.py), [`app/model_center/discovery.py`](app/model_center/discovery.py), [`app/model_center/runtime_profiles.py`](app/model_center/runtime_profiles.py), [`app/credential_vault.py`](app/credential_vault.py), [`app/model_center/api.py`](app/model_center/api.py), [`app/model_center/discovery_api.py`](app/model_center/discovery_api.py).

Original Model Center registration/selection, runtime/profile identity and host/OS credential vault. Detect, validate, register, enable, launch and configured capability remain separate actions.

Runtime/GPU/license/provider quality requires LOCAL_REQUIRED/NOT_RUN evidence. UI must not store secrets or auto-install/unlock unsupported model families.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/model-center/health` | [health](app/model_center/api.py#L143) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/local-ai` | [snapshot](app/model_center/discovery_api.py#L23) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/candidates/{candidate_id}/register` | [register](app/model_center/discovery_api.py#L39) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/candidates/{candidate_id}/validate` | [validate](app/model_center/discovery_api.py#L37) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/model-center/local-ai/registrations/{registration_id}` | [remove](app/model_center/discovery_api.py#L47) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/model-center/local-ai/registrations/{registration_id}` | [configure](app/model_center/discovery_api.py#L41) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/registrations/{registration_id}/disable` | [disable](app/model_center/discovery_api.py#L45) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/registrations/{registration_id}/enable` | [enable](app/model_center/discovery_api.py#L43) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/runtimes` | [add_runtime](app/model_center/discovery_api.py#L33) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/model-center/local-ai/runtimes/{runtime_id}` | [edit_runtime](app/model_center/discovery_api.py#L35) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/scan` | [scan](app/model_center/discovery_api.py#L25) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/local-ai/scan/{scan_id}` | [get_scan](app/model_center/discovery_api.py#L27) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/local-ai/scan/{scan_id}/cancel` | [cancel](app/model_center/discovery_api.py#L29) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/model-center/local-ai/settings` | [settings](app/model_center/discovery_api.py#L31) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/models` | [models](app/model_center/api.py#L68) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/models/{model_id}` | [model](app/model_center/api.py#L74) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/pipelines` | [pipelines](app/model_center/api.py#L140) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/runtimes` | [runtimes](app/model_center/api.py#L81) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/runtimes/{runtime_id}` | [runtime_detail](app/model_center/api.py#L85) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/runtimes/{runtime_id}/capabilities` | [runtime_capabilities](app/model_center/api.py#L135) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/runtimes/{runtime_id}/configuration` | [runtime_configuration](app/model_center/api.py#L113) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/model-center/runtimes/{runtime_id}/configuration` | [update_runtime_configuration](app/model_center/api.py#L118) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/runtimes/{runtime_id}/diagnostics` | [runtime_diagnostics](app/model_center/api.py#L125) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/model-center/runtimes/{runtime_id}/logs` | [runtime_logs](app/model_center/api.py#L130) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/runtimes/{runtime_id}/start` | [start_runtime](app/model_center/api.py#L102) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/runtimes/{runtime_id}/stop` | [stop_runtime](app/model_center/api.py#L107) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/model-center/runtimes/{runtime_id}/validate` | [validate_runtime](app/model_center/api.py#L89) | Original access helper/default/middleware; see source |

Navigation: U09, A06, A07, FS_SEMANTIC. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Tasks

### U07 · Unified task center and honest progress

Page: Tasks → Unified task center; ENGINEERING_UI.

Components: [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`frontend/src/experimental/ExperimentalWorkbench.tsx`](frontend/src/experimental/ExperimentalWorkbench.tsx).

Authority: [`app/experimental/ux.py`](app/experimental/ux.py), [`app/experimental/author_task_projection.py`](app/experimental/author_task_projection.py), [`app/experimental/workspace_task_owners.py`](app/experimental/workspace_task_owners.py), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`frontend/src/experimental/ExperimentalWorkbench.tsx`](frontend/src/experimental/ExperimentalWorkbench.tsx), [`app/experimental/adaptation_projection.py`](app/experimental/adaptation_projection.py), [`app/experimental/review_adapter_projection.py`](app/experimental/review_adapter_projection.py), [`app/experimental/ux_api.py`](app/experimental/ux_api.py), [`frontend/src/experimental/uxClient.ts`](frontend/src/experimental/uxClient.ts).

Read-through TaskReader projection retains original authority and task IDs. Cancel/retry/review are routed to the original owner, never another queue.

Owner-specific cancel states and version/revision guard; cancelled lookups do not cancel jobs. Retry/resume requires original preflight/consent, unknown attempts are reconciled rather than replayed. Restart rereads owners.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/commands` | [commands](app/experimental/ux_api.py#L77) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/commands/resolve` | [resolve_command](app/experimental/ux_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/export` | [export](app/experimental/ux_api.py#L216) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/preview` | [preview](app/experimental/ux_api.py#L211) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [interaction](app/experimental/ux_api.py#L50) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [save_interaction](app/experimental/ux_api.py#L56) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/history` | [interaction_history](app/experimental/ux_api.py#L61) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/reset` | [reset_interaction](app/experimental/ux_api.py#L72) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/restore` | [restore_interaction](app/experimental/ux_api.py#L67) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [resume](app/experimental/ux_api.py#L88) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [save_resume](app/experimental/ux_api.py#L93) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume/history` | [history](app/experimental/ux_api.py#L103) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/reset-layout` | [reset](app/experimental/ux_api.py#L110) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/resolve` | [resume_resolve](app/experimental/ux_api.py#L98) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/search` | [search](app/experimental/ux_api.py#L172) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/cancel` | [cancel](app/experimental/ux_api.py#L185) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/rebuild` | [rebuild](app/experimental/ux_api.py#L181) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/resolve` | [resolve](app/experimental/ux_api.py#L189) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/tasks` | [tasks](app/experimental/ux_api.py#L199) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/tasks/{authority}/{task_id}/cancel` | [cancel_task](app/experimental/ux_api.py#L205) | Original access helper/default/middleware; see source |

Navigation: CORE_GENERATION, FS_REVIEW, A01, A02, A03, A11, FS_BRANCH, FS_PROCESSING, CORE_ADAPTATION, FS_RESEARCH_VISION, FS_VISUAL. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U16 · Safe batch preflight

Page: Tasks → Safe batch / Cost preflight; ENGINEERING_UI.

Components: [`frontend/src/experimental/SafeBatchesPanel.tsx`](frontend/src/experimental/SafeBatchesPanel.tsx).

Authority: [`app/experimental/safe_batches.py`](app/experimental/safe_batches.py), [`app/experimental/safe_batch_contracts.py`](app/experimental/safe_batch_contracts.py), [`frontend/src/experimental/SafeBatchesPanel.tsx`](frontend/src/experimental/SafeBatchesPanel.tsx), [`app/experimental/safe_batch_voice.py`](app/experimental/safe_batch_voice.py), [`app/experimental/safe_batches_api.py`](app/experimental/safe_batches_api.py).

Original owner-specific admission, source/config/budget/approval/settlement constraints; finite supported batch kinds only.

Prepare/execute/cancel with per-item identity and receipts; explicit retry from original owner, no silent replay or route upgrades. Unknown paid cost holds execution.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/safe-batches` | [batches](app/experimental/safe_batches_api.py#L33) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/safe-batches/catalog` | [catalog](app/experimental/safe_batches_api.py#L29) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/safe-batches/preflight` | [preflight](app/experimental/safe_batches_api.py#L37) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/approve-media` | [approve](app/experimental/safe_batches_api.py#L73) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/approve-voice` | [approve_voice](app/experimental/safe_batches_api.py#L65) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/confirm` | [confirm](app/experimental/safe_batches_api.py#L40) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/dispatch-next` | [dispatch](app/experimental/safe_batches_api.py#L43) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/items/{index}/audio` | [audio](app/experimental/safe_batches_api.py#L60) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/items/{index}/file` | [download](app/experimental/safe_batches_api.py#L55) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/proposals/{pid}/preview` | [preview](app/experimental/safe_batches_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/reconcile` | [reconcile](app/experimental/safe_batches_api.py#L52) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/retry-failed` | [retry](app/experimental/safe_batches_api.py#L49) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/safe-batches/{rid}/stop` | [stop](app/experimental/safe_batches_api.py#L46) | domain.write |

Navigation: A06, U07, CORE_IMAGES, B03, U11. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### B02 · Custom agents and workflow SDK

Page: Tasks → Agent SDK / Workflow SDK; ENGINEERING_UI.

Components: [`frontend/src/experimental/DeclarativeAgentsPanel.tsx`](frontend/src/experimental/DeclarativeAgentsPanel.tsx), [`frontend/src/novel/WorkflowPanel.tsx`](frontend/src/novel/WorkflowPanel.tsx), [`frontend/src/novel/AgentQueuePanel.tsx`](frontend/src/novel/AgentQueuePanel.tsx).

Authority: [`app/experimental/declarative_agents.py`](app/experimental/declarative_agents.py), [`app/experimental/declarative_model.py`](app/experimental/declarative_model.py), [`app/experimental/declarative_adapter_sdk.py`](app/experimental/declarative_adapter_sdk.py), [`frontend/src/experimental/DeclarativeAgentsPanel.tsx`](frontend/src/experimental/DeclarativeAgentsPanel.tsx), [`app/experimental/declarative_agents_api.py`](app/experimental/declarative_agents_api.py).

Declarative role/prompt/input/output/capability/runtime/review schema and rooted workflow dependencies use original JobManager and trusted shipped adapters.

Preflight/definition CAS/test/run/human gates/cancel/model refresh and bounded retry; no arbitrary executable plugins, persistent access grant or automatic replay.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/declarative-agents/catalog` | [catalog](app/experimental/declarative_agents_api.py#L25) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/declarative-agents/definitions` | [definitions](app/experimental/declarative_agents_api.py#L31) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/definitions` | [create](app/experimental/declarative_agents_api.py#L34) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/declarative-agents/definitions/{rid}` | [save](app/experimental/declarative_agents_api.py#L37) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/definitions/{rid}/runs` | [test](app/experimental/declarative_agents_api.py#L40) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/preflight` | [preflight](app/experimental/declarative_agents_api.py#L28) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs` | [runs](app/experimental/declarative_agents_api.py#L43) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}` | [run](app/experimental/declarative_agents_api.py#L46) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}/model/dispatch` | [model_dispatch](app/experimental/declarative_agents_api.py#L70) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}/model/preview` | [model_preview](app/experimental/declarative_agents_api.py#L64) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}/model/refresh` | [model_refresh](app/experimental/declarative_agents_api.py#L76) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}/{action}` | [transition](app/experimental/declarative_agents_api.py#L49) | domain.review, domain.write |

Navigation: FS_SDK, A06, U07, FS_REVIEW, B01. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_AUTOMATION · Original Agent / Workflow execution

Page: Tasks → Original Agent / Workflow execution; ENGINEERING_UI.

Components: [`frontend/src/novel/AgentActivityCenter.tsx`](frontend/src/novel/AgentActivityCenter.tsx), [`frontend/src/novel/AgentJobDetail.tsx`](frontend/src/novel/AgentJobDetail.tsx), [`frontend/src/novel/AgentTeamPanel.tsx`](frontend/src/novel/AgentTeamPanel.tsx), [`frontend/src/novel/AgentQueuePanel.tsx`](frontend/src/novel/AgentQueuePanel.tsx), [`frontend/src/novel/WorkflowPanel.tsx`](frontend/src/novel/WorkflowPanel.tsx), [`frontend/src/novel/WorkflowInspector.tsx`](frontend/src/novel/WorkflowInspector.tsx), [`frontend/src/experimental/TeamsPanel.tsx`](frontend/src/experimental/TeamsPanel.tsx), [`frontend/src/ui/WorkflowWorkspaceRoute.tsx`](frontend/src/ui/WorkflowWorkspaceRoute.tsx).

Authority: [`app/services/agent_job_service.py`](app/services/agent_job_service.py), [`app/workflow_api.py`](app/workflow_api.py), [`app/workflow.py`](app/workflow.py), [`app/api.py`](app/api.py).

Original persisted agent/job/Workflow definition and node states remain the execution authority; the declarative SDK and task/review centers are adapters over them.

Queued/running/waiting-approval/paused/completed/failed/cancelled/review/apply stay distinct. Original cancel/resume/checkpoint/retry and authorization fences survive UI changes; no generic task-center replay.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/agent-jobs` | [list_agent_jobs](app/api.py#L1020) | domain.read |
| POST | `/api[/v1]/agent-jobs` | [create_agent_job](app/api.py#L969) | domain.write |
| GET | `/api[/v1]/agent-jobs/audit` | [agent_job_audit](app/api.py#L997) | domain.read |
| GET | `/api[/v1]/agent-jobs/audit.csv` | [export_agent_job_audit](app/api.py#L1008) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/agent-jobs/export.csv` | [export_agent_jobs](app/api.py#L988) | domain.read |
| GET | `/api[/v1]/agent-jobs/{job_id}` | [get_agent_job](app/api.py#L1015) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/agent-jobs/{job_id}/apply` | [apply_agent_job](app/api.py#L1045) | domain.write |
| POST | `/api[/v1]/agent-jobs/{job_id}/cancel` | [cancel_agent_job](app/api.py#L1033) | domain.write |
| POST | `/api[/v1]/agent-jobs/{job_id}/execute` | [execute_agent_job](app/api.py#L1025) | domain.write |
| POST | `/api[/v1]/agent-jobs/{job_id}/retry` | [retry_agent_job](app/api.py#L1037) | domain.write |
| POST | `/api[/v1]/agent-jobs/{job_id}/review` | [review_agent_job](app/api.py#L1041) | domain.review |
| POST | `/api[/v1]/agent-jobs/{job_id}/start` | [start_agent_job](app/api.py#L1029) | domain.write |
| GET | `/api[/v1]/agent-queue` | [queue](app/workflow_api.py#L162) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/agent-queue/{run_id}/{node_id}/execute` | [execute_agent](app/workflow_api.py#L175) | domain.write |
| POST | `/api[/v1]/agent-queue/{run_id}/{node_id}/sync` | [sync_agent](app/workflow_api.py#L195) | domain.write |
| POST | `/api[/v1]/agent/chat` | [agent_chat](app/api.py#L924) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/agents` | [agents](app/api.py#L818) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/agents/{agent_id}/context-preview` | [agent_context_preview](app/api.py#L962) | domain.read |
| GET | `/api[/v1]/workflow-runs/{run_id}` | [run](app/workflow_api.py#L139) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workflow-runs/{run_id}/nodes/{node_id}/approve` | [approve](app/workflow_api.py#L144) | domain.review |
| POST | `/api[/v1]/workflow-runs/{run_id}/nodes/{node_id}/reject` | [reject](app/workflow_api.py#L150) | domain.review |
| POST | `/api[/v1]/workflow-runs/{run_id}/nodes/{node_id}/trigger-agent` | [trigger](app/workflow_api.py#L156) | domain.write |
| POST | `/api[/v1]/workflow-runs/{run_id}/retry` | [retry](app/workflow_api.py#L209) | domain.write |
| POST | `/api[/v1]/workflow-runs/{run_id}/{action}` | [transition](app/workflow_api.py#L217) | domain.write |
| GET | `/api[/v1]/workflows` | [workflows](app/workflow_api.py#L90) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workflows` | [create_workflow](app/workflow_api.py#L103) | domain.write |
| GET | `/api[/v1]/workflows/recipes` | [recipes](app/workflow_api.py#L78) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workflows/recipes/{recipe_id}` | [create_recipe](app/workflow_api.py#L84) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/workflows/{workflow_id}` | [workflow](app/workflow_api.py#L114) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/workflows/{workflow_id}/runs` | [runs](app/workflow_api.py#L119) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/workflows/{workflow_id}/runs` | [create_run](app/workflow_api.py#L128) | domain.write |

Navigation: . State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Settings

### F00 · Foundation, reuse and dependency registry

Page: Settings → Capabilities and feature dependencies; ENGINEERING_UI.

Components: [`frontend/src/ui/CapabilityStatusCenter.tsx`](frontend/src/ui/CapabilityStatusCenter.tsx), [`frontend/src/ui/CapabilityRoadmapPanel.tsx`](frontend/src/ui/CapabilityRoadmapPanel.tsx), [`frontend/src/experimental/DeferredExperimentalWorkbench.tsx`](frontend/src/experimental/DeferredExperimentalWorkbench.tsx), [`frontend/src/experimental/experimentalNavigation.tsx`](frontend/src/experimental/experimentalNavigation.tsx), [`frontend/src/experimental/shared.tsx`](frontend/src/experimental/shared.tsx), [`frontend/src/main.tsx`](frontend/src/main.tsx), [`frontend/src/ui/CapabilityPlaceholder.tsx`](frontend/src/ui/CapabilityPlaceholder.tsx), [`frontend/src/ui/DesignSystemFixture.tsx`](frontend/src/ui/DesignSystemFixture.tsx), [`frontend/src/ui/ModulePlaceholders.tsx`](frontend/src/ui/ModulePlaceholders.tsx), [`frontend/src/ui/ModuleWorkspaceRoutes.tsx`](frontend/src/ui/ModuleWorkspaceRoutes.tsx), [`frontend/src/ui/moduleRegistry.tsx`](frontend/src/ui/moduleRegistry.tsx).

Authority: [`app/experimental/flags.py`](app/experimental/flags.py), [`app/experimental/store.py`](app/experimental/store.py), [`app/experimental/api.py`](app/experimental/api.py), [`app/experimental/capabilities.py`](app/experimental/capabilities.py), [`frontend/src/experimental/api.ts`](frontend/src/experimental/api.ts), [`frontend/src/ui/scopeLabels.ts`](frontend/src/ui/scopeLabels.ts).

Discovery schema v2 preserves legacy features and exposes all RUNTIME_FLAGS through runtime_features plus surface_features. New flags require explicit opt-in and dependencies; frontend normalizes runtime_features. Discovery does not imply provider availability; V1 acceptance mode disables opt-in. Shared selected-owner labels use supplied nonblank names or exact known IDs; a selected branch without metadata is never called mainline/default storyline. Missing owner IDs stay unselected; local mainline labels apply only to an actual unscoped local manuscript.

No external execution or mutation: cancel is request abort; restart rereads host configuration. Original forty-package inventory remains unchanged.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/experimental/capabilities` | [capabilities](app/experimental/api.py#L12) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/experimental/features` | [features](app/experimental/api.py#L8) | Original access helper/default/middleware; see source |

Navigation: . State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U12 · Actionable errors and private diagnostic export

Page: Settings → Diagnostic preview / Export; ENGINEERING_UI.

Components: [`frontend/src/novel/RuntimeDiagnostics.tsx`](frontend/src/novel/RuntimeDiagnostics.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`frontend/src/Health.tsx`](frontend/src/Health.tsx).

Authority: [`app/experimental/ux.py`](app/experimental/ux.py), [`app/experimental/ux_api.py`](app/experimental/ux_api.py), [`app/runtime_diagnostics.py`](app/runtime_diagnostics.py), [`frontend/src/novel/RuntimeDiagnostics.tsx`](frontend/src/novel/RuntimeDiagnostics.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx).

Allowlisted bounded diagnostics from original task/configuration authorities; preview digest binds export and excludes private source bytes, credentials and raw logs.

Cancel discards download; regenerate a current preview after source/authority change. No automatic upload or replay. Restart requires fresh preview.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/commands` | [commands](app/experimental/ux_api.py#L77) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/commands/resolve` | [resolve_command](app/experimental/ux_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/export` | [export](app/experimental/ux_api.py#L216) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/preview` | [preview](app/experimental/ux_api.py#L211) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [interaction](app/experimental/ux_api.py#L50) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [save_interaction](app/experimental/ux_api.py#L56) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/history` | [interaction_history](app/experimental/ux_api.py#L61) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/reset` | [reset_interaction](app/experimental/ux_api.py#L72) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/restore` | [restore_interaction](app/experimental/ux_api.py#L67) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [resume](app/experimental/ux_api.py#L88) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [save_resume](app/experimental/ux_api.py#L93) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume/history` | [history](app/experimental/ux_api.py#L103) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/reset-layout` | [reset](app/experimental/ux_api.py#L110) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/resolve` | [resume_resolve](app/experimental/ux_api.py#L98) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/search` | [search](app/experimental/ux_api.py#L172) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/cancel` | [cancel](app/experimental/ux_api.py#L185) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/rebuild` | [rebuild](app/experimental/ux_api.py#L181) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/resolve` | [resolve](app/experimental/ux_api.py#L189) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/tasks` | [tasks](app/experimental/ux_api.py#L199) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/tasks/{authority}/{task_id}/cancel` | [cancel_task](app/experimental/ux_api.py#L205) | Original access helper/default/middleware; see source |

Navigation: U07, U09. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U10 · Scenario onboarding and progressive disclosure

Page: Settings → First Run / Onboarding / Practice project; ENGINEERING_UI.

Components: [`frontend/src/novel/EntryExperience.tsx`](frontend/src/novel/EntryExperience.tsx), [`frontend/src/novel/FirstUsePanel.tsx`](frontend/src/novel/FirstUsePanel.tsx), [`frontend/src/novel/SampleJourneyGuide.tsx`](frontend/src/novel/SampleJourneyGuide.tsx), [`frontend/src/ui/FeatureLauncher.tsx`](frontend/src/ui/FeatureLauncher.tsx).

Authority: [`app/experimental/first_use.py`](app/experimental/first_use.py), [`frontend/src/novel/EntryExperience.tsx`](frontend/src/novel/EntryExperience.tsx), [`frontend/src/ui/FeatureLauncher.tsx`](frontend/src/ui/FeatureLauncher.tsx), [`app/experimental/first_use_api.py`](app/experimental/first_use_api.py).

OriginalFirstUseAuthorities create through original local or workspace project/chapter owners. One actor/workspace receipt precedes each non-idempotent create.

Skip/reopen and explicit recover; interrupted create stays UNKNOWN until evidence resolves it. No automatic duplicate sample, model call or consent. Native installer/first-run acceptance is LOCAL_REQUIRED.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/experimental/first-use/sample` | [read](app/experimental/first_use_api.py#L15) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/experimental/first-use/sample` | [start](app/experimental/first_use_api.py#L21) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/experimental/first-use/sample/recover` | [recover](app/experimental/first_use_api.py#L26) | Original access helper/default/middleware; see source |

Navigation: CORE_MANUSCRIPT, U01, CORE_EXPORT, CORE_MODELS. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### U13 · Chinese input, accessibility and scale

Page: Settings → Accessibility / Input / Scale; ENGINEERING_UI.

Components: [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/ui/AppShell.tsx`](frontend/src/ui/AppShell.tsx), [`frontend/src/ui/primitives.tsx`](frontend/src/ui/primitives.tsx), [`frontend/src/experimental/WorkspaceInteractionPanel.tsx`](frontend/src/experimental/WorkspaceInteractionPanel.tsx).

Authority: [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/ui/AppShell.tsx`](frontend/src/ui/AppShell.tsx).

Semantic controls, labelled fields, focus return, IME-safe editing and scoped interaction preferences; native screen-reader and physical-input performance are separate acceptance layers.

Retain dirty/IME buffers and focus on cancel; persisted keyboard/reduced-motion/announcement preferences use FS_INTERACTION CAS/history. No global keyboard interception in text input.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| Client/storage or composed adapter | Original owner contract | [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/ui/AppShell.tsx`](frontend/src/ui/AppShell.tsx) | Original authority; no invented server route |

Navigation: FS_INTERACTION, U02, U01. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### B01 · Declarative template library

Page: Settings → Template Library; ENGINEERING_UI.

Components: [`frontend/src/experimental/TemplateLibraryPanel.tsx`](frontend/src/experimental/TemplateLibraryPanel.tsx).

Authority: [`app/experimental/template_library.py`](app/experimental/template_library.py), [`app/experimental/declarative_agents.py`](app/experimental/declarative_agents.py), [`frontend/src/experimental/TemplateLibraryPanel.tsx`](frontend/src/experimental/TemplateLibraryPanel.tsx), [`app/experimental/template_library_api.py`](app/experimental/template_library_api.py).

Local strict declarative packages and independent project instances; import/copy do not grant permissions or execute code.

Version/compatibility checks, compare/update/revert/history, recoverable uninstall; cancel preview/import is explicit; restart reads persisted copies.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/template-library` | [catalog](app/experimental/template_library_api.py#L20) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/template-library/install` | [install](app/experimental/template_library_api.py#L26) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/template-library/instances` | [instances](app/experimental/template_library_api.py#L35) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/template-library/instances` | [copy](app/experimental/template_library_api.py#L38) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/template-library/instances/{rid}` | [edit](app/experimental/template_library_api.py#L41) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/template-library/instances/{rid}/compare` | [compare](app/experimental/template_library_api.py#L44) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/template-library/instances/{rid}/history` | [history](app/experimental/template_library_api.py#L50) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/template-library/instances/{rid}/revert` | [revert](app/experimental/template_library_api.py#L53) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/template-library/instances/{rid}/update` | [update](app/experimental/template_library_api.py#L47) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/template-library/packages/{pid}/favorite` | [favorite](app/experimental/template_library_api.py#L29) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/template-library/packages/{pid}/uninstall` | [uninstall](app/experimental/template_library_api.py#L32) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/template-library/preview` | [preview](app/experimental/template_library_api.py#L23) | Original access helper/default/middleware; see source |

Navigation: FS_PLANNING, B02, CORE_CREATION. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_SDK · Model / Import / Export Adapter SDK

Page: Settings → Model / Import / Export Adapter SDK; ENGINEERING_UI.

Components: [`frontend/src/novel/PluginManagerPanel.tsx`](frontend/src/novel/PluginManagerPanel.tsx), [`frontend/src/novel/PluginInspector.tsx`](frontend/src/novel/PluginInspector.tsx), [`frontend/src/experimental/DeclarativeAgentsPanel.tsx`](frontend/src/experimental/DeclarativeAgentsPanel.tsx).

Authority: [`app/experimental/declarative_adapter_sdk.py`](app/experimental/declarative_adapter_sdk.py), [`app/experimental/declarative_agents.py`](app/experimental/declarative_agents.py), [`app/experimental/media.py`](app/experimental/media.py), [`app/experimental/imports.py`](app/experimental/imports.py), [`app/experimental/interactive_story.py`](app/experimental/interactive_story.py), [`app/plugin_package_manager.py`](app/plugin_package_manager.py), [`app/plugin_contracts.py`](app/plugin_contracts.py), [`app/plugin_capability_policy.py`](app/plugin_capability_policy.py), [`app/experimental/declarative_agents_api.py`](app/experimental/declarative_agents_api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py), [`app/experimental/imports_api.py`](app/experimental/imports_api.py), [`app/experimental/interactive_story_api.py`](app/experimental/interactive_story_api.py), [`app/plugin_management_api.py`](app/plugin_management_api.py).

Strict finite schemas and trusted shipped adapter seams: model generation, bounded import extraction, pure export; Agent/Workflow execution remains B02 original JobManager.

Executable third-party plugin policy remains DENY_ALL. Sandbox/capability/file/network/runtime isolation/trust-signature are prerequisites, not implemented permissions. Cancel/recovery stays with actual owner; registry metadata never permits execution.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/declarative-agents/catalog` | [catalog](app/experimental/declarative_agents_api.py#L25) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/declarative-agents/definitions` | [definitions](app/experimental/declarative_agents_api.py#L31) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/definitions` | [create](app/experimental/declarative_agents_api.py#L34) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/declarative-agents/definitions/{rid}` | [save](app/experimental/declarative_agents_api.py#L37) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/definitions/{rid}/runs` | [test](app/experimental/declarative_agents_api.py#L40) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/preflight` | [preflight](app/experimental/declarative_agents_api.py#L28) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs` | [runs](app/experimental/declarative_agents_api.py#L43) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}` | [run](app/experimental/declarative_agents_api.py#L46) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}/model/dispatch` | [model_dispatch](app/experimental/declarative_agents_api.py#L70) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}/model/preview` | [model_preview](app/experimental/declarative_agents_api.py#L64) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}/model/refresh` | [model_refresh](app/experimental/declarative_agents_api.py#L76) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/declarative-agents/runs/{rid}/{action}` | [transition](app/experimental/declarative_agents_api.py#L49) | domain.review, domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories` | [stories](app/experimental/interactive_story_api.py#L34) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories` | [create](app/experimental/interactive_story_api.py#L49) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories/catalog` | [catalog](app/experimental/interactive_story_api.py#L29) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories/engine-contract` | [engine_contract](app/experimental/interactive_story_api.py#L39) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}` | [story](app/experimental/interactive_story_api.py#L44) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}` | [save](app/experimental/interactive_story_api.py#L54) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/export` | [service.export](app/experimental/interactive_story_api.py#L70) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/export-preview` | [service.export_preview](app/experimental/interactive_story_api.py#L69) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/history` | [service.revisions](app/experimental/interactive_story_api.py#L71) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/preview` | [service.preview](app/experimental/interactive_story_api.py#L66) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/refresh` | [service.refresh](app/experimental/interactive_story_api.py#L68) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/refresh-preview` | [service.refresh_preview](app/experimental/interactive_story_api.py#L67) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/restore-revision` | [service.restore_revision](app/experimental/interactive_story_api.py#L72) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/review` | [service.review](app/experimental/interactive_story_api.py#L65) | domain.review |
| POST | `/api[/v1]/novels/{nid}/experimental/interactive-stories/{sid}/review-preview` | [service.review_preview](app/experimental/interactive_story_api.py#L64) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/media/adapters` | [adapters](app/experimental/media_api.py#L26) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/catalog` | [catalog](app/experimental/media_api.py#L31) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [briefs](app/experimental/media_api.py#L36) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs` | [create_cover](app/experimental/media_api.py#L41) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/cover-briefs/{rid}` | [update_cover](app/experimental/media_api.py#L46) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals` | [proposals](app/experimental/media_api.py#L98) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/compare` | [compare](app/experimental/media_api.py#L103) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/preview` | [preview](app/experimental/media_api.py#L108) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/proposals/{rid}/{action}` | [review](app/experimental/media_api.py#L114) | domain.review |
| GET | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [storyboard_briefs](app/experimental/media_api.py#L52) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs` | [create_storyboard](app/experimental/media_api.py#L57) | domain.write |
| PUT | `/api[/v1]/novels/{nid}/experimental/media/storyboard-briefs/{rid}` | [update_storyboard](app/experimental/media_api.py#L62) | domain.write |
| GET | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [tasks](app/experimental/media_api.py#L68) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks` | [queue](app/experimental/media_api.py#L73) | domain.write |
| POST | `/api[/v1]/novels/{nid}/experimental/media/tasks/{rid}/{action}` | [task_action](app/experimental/media_api.py#L78) | domain.write |
| POST | `/api[/v1]/plugin-packages/install` | [install](app/plugin_management_api.py#L38) | Original access helper/default/middleware; see source |
| DELETE | `/api[/v1]/plugin-packages/{plugin_id}` | [remove](app/plugin_management_api.py#L50) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/plugin-packages/{plugin_id}/rollback` | [rollback](app/plugin_management_api.py#L44) | Original access helper/default/middleware; see source |

Navigation: B02, CORE_MODELS, FS_IMPORT, CORE_EXPORT. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### FS_INTERACTION · Command Palette / Keyboard / Accessibility preferences

Page: Settings → Command Palette / Keyboard / Accessibility preferences; ENGINEERING_UI.

Components: [`frontend/src/experimental/WorkspaceInteractionPanel.tsx`](frontend/src/experimental/WorkspaceInteractionPanel.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx).

Authority: [`app/experimental/workspace_interaction.py`](app/experimental/workspace_interaction.py), [`app/experimental/ux.py`](app/experimental/ux.py), [`app/experimental/ux_api.py`](app/experimental/ux_api.py).

Actor/project/scope-bound preference row and command revision. Finite commands resolve original workspace sections with dirty guard and never dispatch tasks; keyboard bindings are tool-local.

CAS save/history/restore/reset, corruption RECOVERY_REQUIRED disables keyboard; explicit reset. Read-only command resolve can be cancelled; restart rereads preferences; typing/IME/repeat do not invoke commands. Global app-wide customizable palette remains outside this bounded implementation.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/commands` | [commands](app/experimental/ux_api.py#L77) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/commands/resolve` | [resolve_command](app/experimental/ux_api.py#L83) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/export` | [export](app/experimental/ux_api.py#L216) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/diagnostics/preview` | [preview](app/experimental/ux_api.py#L211) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [interaction](app/experimental/ux_api.py#L50) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/interaction` | [save_interaction](app/experimental/ux_api.py#L56) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/history` | [interaction_history](app/experimental/ux_api.py#L61) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/reset` | [reset_interaction](app/experimental/ux_api.py#L72) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/interaction/restore` | [restore_interaction](app/experimental/ux_api.py#L67) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [resume](app/experimental/ux_api.py#L88) | Original access helper/default/middleware; see source |
| PUT | `/api[/v1]/novels/{nid}/experimental/workspace/resume` | [save_resume](app/experimental/ux_api.py#L93) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/resume/history` | [history](app/experimental/ux_api.py#L103) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/reset-layout` | [reset](app/experimental/ux_api.py#L110) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/resume/resolve` | [resume_resolve](app/experimental/ux_api.py#L98) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/search` | [search](app/experimental/ux_api.py#L172) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/cancel` | [cancel](app/experimental/ux_api.py#L185) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/rebuild` | [rebuild](app/experimental/ux_api.py#L181) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/search/resolve` | [resolve](app/experimental/ux_api.py#L189) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/novels/{nid}/experimental/workspace/tasks` | [tasks](app/experimental/ux_api.py#L199) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/novels/{nid}/experimental/workspace/tasks/{authority}/{task_id}/cancel` | [cancel_task](app/experimental/ux_api.py#L205) | Original access helper/default/middleware; see source |

Navigation: U01, U03, U07, U12, U13. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

### CORE_INTEROP · Frozen PoemSeed Local Interop 1.0

Page: Settings → Frozen PoemSeed Local Interop 1.0; ENGINEERING_UI.

Components: [`frontend/src/interop/entry.tsx`](frontend/src/interop/entry.tsx), [`frontend/src/interop/DesktopIntegrationDetails.tsx`](frontend/src/interop/DesktopIntegrationDetails.tsx), [`frontend/src/interop/LocalTutorIntegration.tsx`](frontend/src/interop/LocalTutorIntegration.tsx).

Authority: [`app/local_interop/api.py`](app/local_interop/api.py), [`app/local_interop/transport.py`](app/local_interop/transport.py), [`app/local_interop/host.py`](app/local_interop/host.py), [`app/local_interop/desktop.py`](app/local_interop/desktop.py), [`app/local_interop/provider.py`](app/local_interop/provider.py), [`app/local_interop/chapter_ids.py`](app/local_interop/chapter_ids.py), [`frontend/src/interop/client.ts`](frontend/src/interop/client.ts), [`frontend/src/interop/chapterIds.ts`](frontend/src/interop/chapterIds.ts).

Frozen PoemSeed 1.0 schemas/public fields/product IDs/opaque-ID alphabet remain compatible. Original InteropContextProvider resolves the registered branch manuscript via CollaborationReadService; empty/disabled/revoked branches never borrow mainline. One Host and original consent/session authorities remain. Native incompatible chapter IDs use full scope-bound SHA-256 wire labels, not a second editable store or authority.

Reverse wire lookup enumerates live exact-scope owner rows and rejects missing/archive/tombstone/collision; only explicit authorized editor handoff returns validated native identity. Response-body context/source/selection/handoff and queued event frames recheck owner/consent. Host restart invalidates sessions; no alias registry or mainline fallback for registered production branches. Actual native Desktop LOCAL_REQUIRED, browser/real PostgreSQL hosted-pending; synthetic Tutor remains MOCK_ONLY. Frozen public protocol objects remain unchanged.

| Method | Path | Source handler | Permission evidence |
|---|---|---|---|
| POST | `/api[/v1]/local-interop/ask` | [ask](app/local_interop/api.py#L244) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/cancel` | [cancel](app/local_interop/api.py#L320) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/case/approve` | [case_approve](app/local_interop/api.py#L275) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/case/preview` | [case_preview](app/local_interop/api.py#L271) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/connect` | [connect](app/local_interop/api.py#L230) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/context/preview` | [context_preview](app/local_interop/api.py#L235) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/local-interop/context/sources` | [context_sources](app/local_interop/api.py#L239) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/diagnostics/preview` | [diagnostic_preview](app/local_interop/api.py#L249) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/diagnostics/share` | [diagnostic_share](app/local_interop/api.py#L253) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/disconnect` | [disconnect](app/local_interop/api.py#L336) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/disconnect-revoke` | [disconnect_revoke](app/local_interop/api.py#L332) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/discovery` | [discovery](app/local_interop/api.py#L225) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/local-interop/events` | [events](app/local_interop/api.py#L293) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/events/pause` | [event_pause](app/local_interop/api.py#L328) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/events/preview` | [event_preview](app/local_interop/api.py#L279) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/local-interop/events/stream` | [events_stream](app/local_interop/api.py#L300) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/events/subscribe` | [event_subscribe](app/local_interop/api.py#L283) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/events/unsubscribe` | [event_unsubscribe](app/local_interop/api.py#L289) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/handoff` | [handoff](app/local_interop/api.py#L263) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/local-interop/models` | [models](app/local_interop/api.py#L267) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/permissions/revoke` | [permission_revoke](app/local_interop/api.py#L324) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/settings` | [settings](app/local_interop/api.py#L221) | Original access helper/default/middleware; see source |
| GET | `/api[/v1]/local-interop/status` | [status](app/local_interop/api.py#L212) | Original access helper/default/middleware; see source |
| POST | `/api[/v1]/local-interop/verify` | [verify](app/local_interop/api.py#L258) | Original access helper/default/middleware; see source |

Navigation: FS_BRANCH, CORE_MANUSCRIPT, U01, U07. State contract: all shared states, with owner-specific scope/CAS/cancel/recovery semantics above. Verification: PENDING exact final head.

## Complete frontend TSX component inventory

Includes shared infrastructure, fixtures and host components; this is not a count of independent pages.

| Source | Surface ownership | Kind |
|---|---|---|
| [`frontend/src/App.tsx`](frontend/src/App.tsx) | U02, U01, U03, U04, CORE_MANUSCRIPT, CORE_ADAPTATION | SHARED_INFRASTRUCTURE |
| [`frontend/src/CollaborationPanels.tsx`](frontend/src/CollaborationPanels.tsx) | B08, CORE_COLLAB | DOMAIN_COMPONENT |
| [`frontend/src/ConflictDialog.tsx`](frontend/src/ConflictDialog.tsx) | U02 | DOMAIN_COMPONENT |
| [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx) | U02, U04, U13, U05, CORE_MANUSCRIPT | DOMAIN_COMPONENT |
| [`frontend/src/Health.tsx`](frontend/src/Health.tsx) | U12 | DOMAIN_COMPONENT |
| [`frontend/src/PermissionManagement.tsx`](frontend/src/PermissionManagement.tsx) | CORE_COLLAB | DOMAIN_COMPONENT |
| [`frontend/src/RevisionPanel.tsx`](frontend/src/RevisionPanel.tsx) | U02, CORE_MANUSCRIPT, FS_REVIEW | DOMAIN_COMPONENT |
| [`frontend/src/WorkspaceManagement.tsx`](frontend/src/WorkspaceManagement.tsx) | CORE_COLLAB | DOMAIN_COMPONENT |
| [`frontend/src/experimental/AudiobookPanel.tsx`](frontend/src/experimental/AudiobookPanel.tsx) | B03 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/BranchManuscriptPanel.tsx`](frontend/src/experimental/BranchManuscriptPanel.tsx) | FS_BRANCH | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ChangeImpactPanel.tsx`](frontend/src/experimental/ChangeImpactPanel.tsx) | U06 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ComicLayoutsPanel.tsx`](frontend/src/experimental/ComicLayoutsPanel.tsx) | B06 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/DeclarativeAgentsPanel.tsx`](frontend/src/experimental/DeclarativeAgentsPanel.tsx) | B02, FS_SDK | DOMAIN_COMPONENT |
| [`frontend/src/experimental/DeferredExperimentalWorkbench.tsx`](frontend/src/experimental/DeferredExperimentalWorkbench.tsx) | F00 | SHARED_INFRASTRUCTURE |
| [`frontend/src/experimental/DirectorPanel.tsx`](frontend/src/experimental/DirectorPanel.tsx) | A08 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/EmbeddingPanel.tsx`](frontend/src/experimental/EmbeddingPanel.tsx) | A10, FS_SEMANTIC | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ExperimentalWorkbench.tsx`](frontend/src/experimental/ExperimentalWorkbench.tsx) | U07 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ImportPanel.tsx`](frontend/src/experimental/ImportPanel.tsx) | FS_IMPORT | DOMAIN_COMPONENT |
| [`frontend/src/experimental/InboxPanel.tsx`](frontend/src/experimental/InboxPanel.tsx) | FS_CANON, FS_REVIEW | DOMAIN_COMPONENT |
| [`frontend/src/experimental/InteractiveStoryHistory.tsx`](frontend/src/experimental/InteractiveStoryHistory.tsx) | B07 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/InteractiveStoryPanel.tsx`](frontend/src/experimental/InteractiveStoryPanel.tsx) | B07, FS_ENGINES | DOMAIN_COMPONENT |
| [`frontend/src/experimental/InteractiveStoryPreview.tsx`](frontend/src/experimental/InteractiveStoryPreview.tsx) | B07 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/LanguageTranslationPanel.tsx`](frontend/src/experimental/LanguageTranslationPanel.tsx) | B05 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/MediaPanel.tsx`](frontend/src/experimental/MediaPanel.tsx) | U06, CORE_IMAGES | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ModelBenchmarkPanel.tsx`](frontend/src/experimental/ModelBenchmarkPanel.tsx) | A07 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ModelBrokerPanel.tsx`](frontend/src/experimental/ModelBrokerPanel.tsx) | A06 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/MultilingualEditionsPanel.tsx`](frontend/src/experimental/MultilingualEditionsPanel.tsx) | B05 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/NarrativeJudgeModelPanel.tsx`](frontend/src/experimental/NarrativeJudgeModelPanel.tsx) | A03 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/NarrativeJudgePanel.tsx`](frontend/src/experimental/NarrativeJudgePanel.tsx) | A03 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx`](frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx) | A03 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/OfflineSyncPanel.tsx`](frontend/src/experimental/OfflineSyncPanel.tsx) | B10, FS_SYNC | DOMAIN_COMPONENT |
| [`frontend/src/experimental/PlanningPanel.tsx`](frontend/src/experimental/PlanningPanel.tsx) | FS_PLANNING | DOMAIN_COMPONENT |
| [`frontend/src/experimental/PortableProjectsPanel.tsx`](frontend/src/experimental/PortableProjectsPanel.tsx) | U14 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ProductionLineagePanel.tsx`](frontend/src/experimental/ProductionLineagePanel.tsx) | A09, A13 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ProjectForksPanel.tsx`](frontend/src/experimental/ProjectForksPanel.tsx) | B09, FS_BRANCH | DOMAIN_COMPONENT |
| [`frontend/src/experimental/PromotionRecovery.tsx`](frontend/src/experimental/PromotionRecovery.tsx) | FS_PLANNING | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ReaderPreflightPanel.tsx`](frontend/src/experimental/ReaderPreflightPanel.tsx) | U11 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/ResearchLibraryPanel.tsx`](frontend/src/experimental/ResearchLibraryPanel.tsx) | A10, FS_RESEARCH_VISION | DOMAIN_COMPONENT |
| [`frontend/src/experimental/RevisionComparisonModelPanel.tsx`](frontend/src/experimental/RevisionComparisonModelPanel.tsx) | A11 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/RevisionIntelligencePanel.tsx`](frontend/src/experimental/RevisionIntelligencePanel.tsx) | A11, U05 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/SafeBatchesPanel.tsx`](frontend/src/experimental/SafeBatchesPanel.tsx) | U16 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/SharedUniversePanel.tsx`](frontend/src/experimental/SharedUniversePanel.tsx) | B09, FS_UNIVERSE | DOMAIN_COMPONENT |
| [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx) | A04, A05 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/StorySimulatorPanel.tsx`](frontend/src/experimental/StorySimulatorPanel.tsx) | A01 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/StructuredForksPanel.tsx`](frontend/src/experimental/StructuredForksPanel.tsx) | B09 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/StyleAnalysisModelPanel.tsx`](frontend/src/experimental/StyleAnalysisModelPanel.tsx) | A02 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/StyleAnalysisPanel.tsx`](frontend/src/experimental/StyleAnalysisPanel.tsx) | A02 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/SubtitleTimelinePanel.tsx`](frontend/src/experimental/SubtitleTimelinePanel.tsx) | B04, FS_PROCESSING | DOMAIN_COMPONENT |
| [`frontend/src/experimental/TeamsPanel.tsx`](frontend/src/experimental/TeamsPanel.tsx) | CORE_AUTOMATION | DOMAIN_COMPONENT |
| [`frontend/src/experimental/TemplateLibraryPanel.tsx`](frontend/src/experimental/TemplateLibraryPanel.tsx) | B01 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/TimelineExchangePanel.tsx`](frontend/src/experimental/TimelineExchangePanel.tsx) | A12 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/TranslationMemoryPanel.tsx`](frontend/src/experimental/TranslationMemoryPanel.tsx) | B05 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/VoiceDirectionPanel.tsx`](frontend/src/experimental/VoiceDirectionPanel.tsx) | B03 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/WorkflowInspectionPanel.tsx`](frontend/src/experimental/WorkflowInspectionPanel.tsx) | U09 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/WorkspaceInteractionPanel.tsx`](frontend/src/experimental/WorkspaceInteractionPanel.tsx) | U13, FS_INTERACTION | DOMAIN_COMPONENT |
| [`frontend/src/experimental/WorkspaceSearch.tsx`](frontend/src/experimental/WorkspaceSearch.tsx) | U03 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx) | U01, U07, U12, FS_INTERACTION | DOMAIN_COMPONENT |
| [`frontend/src/experimental/WorldPanel.tsx`](frontend/src/experimental/WorldPanel.tsx) | FS_CANON, FS_CONTINUITY, FS_TIMELINE | DOMAIN_COMPONENT |
| [`frontend/src/experimental/WriterRoomPanel.tsx`](frontend/src/experimental/WriterRoomPanel.tsx) | B08, FS_REALTIME | DOMAIN_COMPONENT |
| [`frontend/src/experimental/WritingFocusPanel.tsx`](frontend/src/experimental/WritingFocusPanel.tsx) | U04 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/WritingSessionPanel.tsx`](frontend/src/experimental/WritingSessionPanel.tsx) | U15 | DOMAIN_COMPONENT |
| [`frontend/src/experimental/experimentalNavigation.tsx`](frontend/src/experimental/experimentalNavigation.tsx) | F00 | SHARED_INFRASTRUCTURE |
| [`frontend/src/experimental/shared.tsx`](frontend/src/experimental/shared.tsx) | F00 | SHARED_INFRASTRUCTURE |
| [`frontend/src/interop/DesktopIntegrationDetails.tsx`](frontend/src/interop/DesktopIntegrationDetails.tsx) | CORE_INTEROP | DOMAIN_COMPONENT |
| [`frontend/src/interop/LocalTutorIntegration.tsx`](frontend/src/interop/LocalTutorIntegration.tsx) | CORE_INTEROP | DOMAIN_COMPONENT |
| [`frontend/src/interop/entry.tsx`](frontend/src/interop/entry.tsx) | CORE_INTEROP | DOMAIN_COMPONENT |
| [`frontend/src/main.tsx`](frontend/src/main.tsx) | F00 | SHARED_INFRASTRUCTURE |
| [`frontend/src/novel/AIPlanningPanel.tsx`](frontend/src/novel/AIPlanningPanel.tsx) | CORE_CREATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/AdaptationPanel.tsx`](frontend/src/novel/AdaptationPanel.tsx) | CORE_ADAPTATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/AgentActivityCenter.tsx`](frontend/src/novel/AgentActivityCenter.tsx) | CORE_AUTOMATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/AgentJobDetail.tsx`](frontend/src/novel/AgentJobDetail.tsx) | CORE_AUTOMATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/AgentQueuePanel.tsx`](frontend/src/novel/AgentQueuePanel.tsx) | B02, CORE_AUTOMATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/AgentResultReview.tsx`](frontend/src/novel/AgentResultReview.tsx) | FS_REVIEW | DOMAIN_COMPONENT |
| [`frontend/src/novel/AgentTeamPanel.tsx`](frontend/src/novel/AgentTeamPanel.tsx) | CORE_AUTOMATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/AiContextPreviewPanel.tsx`](frontend/src/novel/AiContextPreviewPanel.tsx) | U08 | DOMAIN_COMPONENT |
| [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx) | A05, U05, CORE_GENERATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/AssetInspector.tsx`](frontend/src/novel/AssetInspector.tsx) | A09, CORE_ASSETS | DOMAIN_COMPONENT |
| [`frontend/src/novel/AssetLibraryPanel.tsx`](frontend/src/novel/AssetLibraryPanel.tsx) | CORE_ASSETS | DOMAIN_COMPONENT |
| [`frontend/src/novel/AssetTaskExecutionPanel.tsx`](frontend/src/novel/AssetTaskExecutionPanel.tsx) | CORE_IMAGES | DOMAIN_COMPONENT |
| [`frontend/src/novel/AudioGenerationPanel.tsx`](frontend/src/novel/AudioGenerationPanel.tsx) | CORE_AUDIO | DOMAIN_COMPONENT |
| [`frontend/src/novel/AudioTaskInspector.tsx`](frontend/src/novel/AudioTaskInspector.tsx) | CORE_AUDIO | DOMAIN_COMPONENT |
| [`frontend/src/novel/AudiobookManifestPanel.tsx`](frontend/src/novel/AudiobookManifestPanel.tsx) | B03, CORE_AUDIO | DOMAIN_COMPONENT |
| [`frontend/src/novel/AuthenticatedMedia.tsx`](frontend/src/novel/AuthenticatedMedia.tsx) | CORE_ASSETS | DOMAIN_COMPONENT |
| [`frontend/src/novel/AuthorRequestControls.tsx`](frontend/src/novel/AuthorRequestControls.tsx) | U08 | DOMAIN_COMPONENT |
| [`frontend/src/novel/AuthorRequestPreviewPanel.tsx`](frontend/src/novel/AuthorRequestPreviewPanel.tsx) | U08 | DOMAIN_COMPONENT |
| [`frontend/src/novel/AuthorSourceItems.tsx`](frontend/src/novel/AuthorSourceItems.tsx) | U08 | DOMAIN_COMPONENT |
| [`frontend/src/novel/BindingManifestPanel.tsx`](frontend/src/novel/BindingManifestPanel.tsx) | CORE_SCREENPLAY | DOMAIN_COMPONENT |
| [`frontend/src/novel/ChapterTree.tsx`](frontend/src/novel/ChapterTree.tsx) | CORE_MANUSCRIPT | DOMAIN_COMPONENT |
| [`frontend/src/novel/ConstraintImportPreview.tsx`](frontend/src/novel/ConstraintImportPreview.tsx) | CORE_ADAPTATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/ContinuityCheckPanel.tsx`](frontend/src/novel/ContinuityCheckPanel.tsx) | FS_CONTINUITY, FS_FORESHADOWING | DOMAIN_COMPONENT |
| [`frontend/src/novel/CreationWorkbenchPanel.tsx`](frontend/src/novel/CreationWorkbenchPanel.tsx) | CORE_CREATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/DeepSeekCredentialControl.tsx`](frontend/src/novel/DeepSeekCredentialControl.tsx) | CORE_MODELS | DOMAIN_COMPONENT |
| [`frontend/src/novel/DirectorShotCard.tsx`](frontend/src/novel/DirectorShotCard.tsx) | A08 | DOMAIN_COMPONENT |
| [`frontend/src/novel/DirectorShotList.tsx`](frontend/src/novel/DirectorShotList.tsx) | A08 | DOMAIN_COMPONENT |
| [`frontend/src/novel/DirectorVoiceToolbar.tsx`](frontend/src/novel/DirectorVoiceToolbar.tsx) | B03 | DOMAIN_COMPONENT |
| [`frontend/src/novel/EntityAssetPanel.tsx`](frontend/src/novel/EntityAssetPanel.tsx) | CORE_ASSETS | DOMAIN_COMPONENT |
| [`frontend/src/novel/EntryExperience.tsx`](frontend/src/novel/EntryExperience.tsx) | U10 | DOMAIN_COMPONENT |
| [`frontend/src/novel/ExportPanel.tsx`](frontend/src/novel/ExportPanel.tsx) | U11, CORE_EXPORT | DOMAIN_COMPONENT |
| [`frontend/src/novel/FindingReviewPanel.tsx`](frontend/src/novel/FindingReviewPanel.tsx) | FS_CONTINUITY, FS_FORESHADOWING | DOMAIN_COMPONENT |
| [`frontend/src/novel/FirstUsePanel.tsx`](frontend/src/novel/FirstUsePanel.tsx) | U10 | DOMAIN_COMPONENT |
| [`frontend/src/novel/GenerationRecoveryPicker.tsx`](frontend/src/novel/GenerationRecoveryPicker.tsx) | CORE_GENERATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/GenerationWorkflowTimeline.tsx`](frontend/src/novel/GenerationWorkflowTimeline.tsx) | CORE_GENERATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/ImageGenerationPanel.tsx`](frontend/src/novel/ImageGenerationPanel.tsx) | CORE_IMAGES | DOMAIN_COMPONENT |
| [`frontend/src/novel/ImageInfiniteCanvas.tsx`](frontend/src/novel/ImageInfiniteCanvas.tsx) | CORE_IMAGES | DOMAIN_COMPONENT |
| [`frontend/src/novel/ImageQueuePanel.tsx`](frontend/src/novel/ImageQueuePanel.tsx) | CORE_IMAGES | DOMAIN_COMPONENT |
| [`frontend/src/novel/ImageTaskInspector.tsx`](frontend/src/novel/ImageTaskInspector.tsx) | CORE_IMAGES | DOMAIN_COMPONENT |
| [`frontend/src/novel/MotionPrivacyPanel.tsx`](frontend/src/novel/MotionPrivacyPanel.tsx) | CORE_VIDEO | DOMAIN_COMPONENT |
| [`frontend/src/novel/MotionTaskBatchControls.tsx`](frontend/src/novel/MotionTaskBatchControls.tsx) | CORE_VIDEO | DOMAIN_COMPONENT |
| [`frontend/src/novel/MotionTaskWorkspace.tsx`](frontend/src/novel/MotionTaskWorkspace.tsx) | CORE_VIDEO | DOMAIN_COMPONENT |
| [`frontend/src/novel/MultimodalDirectorWorkspace.tsx`](frontend/src/novel/MultimodalDirectorWorkspace.tsx) | CORE_SCREENPLAY | DOMAIN_COMPONENT |
| [`frontend/src/novel/NovelImportPanel.tsx`](frontend/src/novel/NovelImportPanel.tsx) | FS_IMPORT | DOMAIN_COMPONENT |
| [`frontend/src/novel/NovelOverviewPanel.tsx`](frontend/src/novel/NovelOverviewPanel.tsx) | U15 | DOMAIN_COMPONENT |
| [`frontend/src/novel/PendingCanonReviewPanel.tsx`](frontend/src/novel/PendingCanonReviewPanel.tsx) | FS_CANON | DOMAIN_COMPONENT |
| [`frontend/src/novel/PipelineStatusPanel.tsx`](frontend/src/novel/PipelineStatusPanel.tsx) | CORE_ADAPTATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/PluginInspector.tsx`](frontend/src/novel/PluginInspector.tsx) | FS_SDK | DOMAIN_COMPONENT |
| [`frontend/src/novel/PluginManagerPanel.tsx`](frontend/src/novel/PluginManagerPanel.tsx) | FS_SDK | DOMAIN_COMPONENT |
| [`frontend/src/novel/ResearchPanel.tsx`](frontend/src/novel/ResearchPanel.tsx) | A10 | DOMAIN_COMPONENT |
| [`frontend/src/novel/RuntimeDiagnostics.tsx`](frontend/src/novel/RuntimeDiagnostics.tsx) | U09, U12 | DOMAIN_COMPONENT |
| [`frontend/src/novel/SampleJourneyGuide.tsx`](frontend/src/novel/SampleJourneyGuide.tsx) | U10 | DOMAIN_COMPONENT |
| [`frontend/src/novel/ScreenplayPanel.tsx`](frontend/src/novel/ScreenplayPanel.tsx) | A08, CORE_SCREENPLAY | DOMAIN_COMPONENT |
| [`frontend/src/novel/ScreenplayPipelinePanel.tsx`](frontend/src/novel/ScreenplayPipelinePanel.tsx) | CORE_ADAPTATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/SourcePrivacyControl.tsx`](frontend/src/novel/SourcePrivacyControl.tsx) | U08 | DOMAIN_COMPONENT |
| [`frontend/src/novel/SpeechSynthesisPanel.tsx`](frontend/src/novel/SpeechSynthesisPanel.tsx) | B03, CORE_AUDIO | DOMAIN_COMPONENT |
| [`frontend/src/novel/StoryDatabase.tsx`](frontend/src/novel/StoryDatabase.tsx) | FS_CANON, FS_FORESHADOWING, FS_TIMELINE, FS_STORY_DATABASE | DOMAIN_COMPONENT |
| [`frontend/src/novel/StoryPlanningWorkspace.tsx`](frontend/src/novel/StoryPlanningWorkspace.tsx) | FS_PLANNING, FS_FORESHADOWING | DOMAIN_COMPONENT |
| [`frontend/src/novel/StoryRecordVersionEditor.tsx`](frontend/src/novel/StoryRecordVersionEditor.tsx) | FS_FORESHADOWING, FS_TIMELINE, FS_STORY_DATABASE | DOMAIN_COMPONENT |
| [`frontend/src/novel/VideoAssemblyPanel.tsx`](frontend/src/novel/VideoAssemblyPanel.tsx) | CORE_VIDEO | DOMAIN_COMPONENT |
| [`frontend/src/novel/VideoTaskInspector.tsx`](frontend/src/novel/VideoTaskInspector.tsx) | CORE_VIDEO | DOMAIN_COMPONENT |
| [`frontend/src/novel/VideoTimeline.tsx`](frontend/src/novel/VideoTimeline.tsx) | A12 | DOMAIN_COMPONENT |
| [`frontend/src/novel/VisionAnalysisPanel.tsx`](frontend/src/novel/VisionAnalysisPanel.tsx) | CORE_IMAGES | DOMAIN_COMPONENT |
| [`frontend/src/novel/VisualContextPanel.tsx`](frontend/src/novel/VisualContextPanel.tsx) | FS_VISUAL | DOMAIN_COMPONENT |
| [`frontend/src/novel/VisualReferencePanel.tsx`](frontend/src/novel/VisualReferencePanel.tsx) | CORE_ASSETS, FS_VISUAL | DOMAIN_COMPONENT |
| [`frontend/src/novel/VisualTextWorkflow.tsx`](frontend/src/novel/VisualTextWorkflow.tsx) | CORE_IMAGES | DOMAIN_COMPONENT |
| [`frontend/src/novel/WorkflowInspector.tsx`](frontend/src/novel/WorkflowInspector.tsx) | CORE_AUTOMATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/WorkflowPanel.tsx`](frontend/src/novel/WorkflowPanel.tsx) | B02, CORE_AUTOMATION | DOMAIN_COMPONENT |
| [`frontend/src/novel/WorldBuildingDashboard.tsx`](frontend/src/novel/WorldBuildingDashboard.tsx) | FS_STORY_DATABASE | DOMAIN_COMPONENT |
| [`frontend/src/novel/WorldRelationshipGraph.tsx`](frontend/src/novel/WorldRelationshipGraph.tsx) | FS_STORY_DATABASE | DOMAIN_COMPONENT |
| [`frontend/src/novel/WorldTimelineView.tsx`](frontend/src/novel/WorldTimelineView.tsx) | FS_TIMELINE | DOMAIN_COMPONENT |
| [`frontend/src/ui/AiControlCenter.tsx`](frontend/src/ui/AiControlCenter.tsx) | CORE_MODELS | DOMAIN_COMPONENT |
| [`frontend/src/ui/AppShell.tsx`](frontend/src/ui/AppShell.tsx) | U13 | SHARED_INFRASTRUCTURE |
| [`frontend/src/ui/AssetWorkspaceRoute.tsx`](frontend/src/ui/AssetWorkspaceRoute.tsx) | CORE_ASSETS | DOMAIN_COMPONENT |
| [`frontend/src/ui/CapabilityPlaceholder.tsx`](frontend/src/ui/CapabilityPlaceholder.tsx) | F00 | SHARED_INFRASTRUCTURE |
| [`frontend/src/ui/CapabilityRoadmapPanel.tsx`](frontend/src/ui/CapabilityRoadmapPanel.tsx) | F00 | DOMAIN_COMPONENT |
| [`frontend/src/ui/CapabilityStatusCenter.tsx`](frontend/src/ui/CapabilityStatusCenter.tsx) | F00 | DOMAIN_COMPONENT |
| [`frontend/src/ui/DesignSystemFixture.tsx`](frontend/src/ui/DesignSystemFixture.tsx) | F00 | TEST_FIXTURE |
| [`frontend/src/ui/FeatureLauncher.tsx`](frontend/src/ui/FeatureLauncher.tsx) | U03, U10 | DOMAIN_COMPONENT |
| [`frontend/src/ui/LocalAiDiscovery.tsx`](frontend/src/ui/LocalAiDiscovery.tsx) | U09 | DOMAIN_COMPONENT |
| [`frontend/src/ui/MediaProviderSettings.tsx`](frontend/src/ui/MediaProviderSettings.tsx) | CORE_MODELS | DOMAIN_COMPONENT |
| [`frontend/src/ui/ModelCenter.tsx`](frontend/src/ui/ModelCenter.tsx) | CORE_MODELS | DOMAIN_COMPONENT |
| [`frontend/src/ui/ModulePlaceholders.tsx`](frontend/src/ui/ModulePlaceholders.tsx) | F00 | SHARED_INFRASTRUCTURE |
| [`frontend/src/ui/ModuleWorkspaceRoutes.tsx`](frontend/src/ui/ModuleWorkspaceRoutes.tsx) | F00 | SHARED_INFRASTRUCTURE |
| [`frontend/src/ui/SaveControls.tsx`](frontend/src/ui/SaveControls.tsx) | U02 | DOMAIN_COMPONENT |
| [`frontend/src/ui/WorkflowWorkspaceRoute.tsx`](frontend/src/ui/WorkflowWorkspaceRoute.tsx) | CORE_AUTOMATION | DOMAIN_COMPONENT |
| [`frontend/src/ui/moduleRegistry.tsx`](frontend/src/ui/moduleRegistry.tsx) | F00 | SHARED_INFRASTRUCTURE |
| [`frontend/src/ui/primitives.tsx`](frontend/src/ui/primitives.tsx) | U13 | SHARED_INFRASTRUCTURE |
| [`frontend/src/useScopedRequestConsent.tsx`](frontend/src/useScopedRequestConsent.tsx) | U08 | DOMAIN_COMPONENT |
