# Wave 1 U03 structured search refinement

Status: source implementation complete; local File/API/unit checks pass. Hosted PostgreSQL and browser execution remain pending.

The existing workspace search now includes organization/civilization, semantic ability and legacy world rules, original graph records, original assets, and owner-bound workflow definitions. Readers call the original services under current project/branch/actor permissions and feature gates. Legacy rules use the original `payload.statement`. Search retains only allowlisted titles, aliases, tags and safe metadata, with a digest of the complete original row for freshness. Private/hidden/archived rows disappear, and nonindexed body edits invalidate a prior result.

Resolving a result preserves the original record ID and owner. Existing World, Graph, legacy Rule, Asset and Workflow panels focus that exact record and report missing sources. They do not create, approve, execute or reconstruct records. Targeted assets use an opaque authority-specific query observer so an earlier session's in-flight list cannot reappear; World and Graph observers drop older client results. Original graph scene filters and result epochs remain intact.

Revision model task navigation verifies the original generation ID, origin, chapter, project and base version, then opens its original chapter and existing revision owner. Dirty/conflicted drafts, new input during validation, changed scope, cancelled navigation and feature revocation stop the switch. It never opens an unrelated generic draft or starts another model job.

## Verification

- Backend: `../interop-test-venv/bin/python -m pytest tests/test_post_interop_structured_search.py tests/test_r4_incremental_search.py tests/test_r4_incremental_search_mounted.py -m 'not postgres_backend_only' -q` — 21 passed, 20 PostgreSQL cases deselected. The new module contributes 10 passed and 10 PostgreSQL cases. Both `/api` and `/api/v1` are exercised with real synthetic File sources and original permission services.
- Frontend: exact installed pnpm 10.6.5, Vitest across `AppWorkspaceResume`, `StructuredSearchNavigation`, `WorldPanel`, `WorkspaceSearch`, `StoryGraphPanel`, `AssetLibraryPanel`, `WorkflowPanel`, `WorkflowScopeGuards`, `StoryDatabase` — 88 passed. Existing assertions remain intact. The new structured navigation module contributes 12 tests; App adds five revision-owner cases.
- TypeScript: `tsc -b --pretty false` passed.
- UI design token guard and `git diff --check` passed. No CSS, shell geometry or design tokens changed.
- Hosted browser fixture authored at `frontend/tests/e2e/r4-structured-search.spec.ts`; `playwright test --config playwright.r4.config.ts r4-structured-search.spec.ts --list` discovers two tests. These exercise exact source focus, no generation/approval/workflow execution, original data preservation and 1366/1440/1920 widths.
- Browser/visual execution: NOT_RUN locally because of the existing platform prohibition on Chrome. No local browser retry was attempted. PostgreSQL: NOT_RUN without an authorized test DSN. These are pending hosted evidence, not claimed passes.

## Source handoff

No stage, commit or push performed by this worker. Files owned here:

- `app/experimental/search_sources.py`
- `app/experimental/ux.py` search-only additions; task-origin changes are the U08 worker's shared edits
- `frontend/src/App.tsx`
- `frontend/src/AppWorkspaceResume.test.tsx`
- `frontend/src/experimental/WorkspaceSearch.tsx`
- `frontend/src/experimental/uxClient.ts`
- `frontend/src/experimental/useRequestedRecord.ts`
- `frontend/src/experimental/StructuredSearchNavigation.test.tsx`
- `frontend/src/experimental/WorldPanel.tsx`
- `frontend/src/experimental/StoryGraphPanel.tsx` requested-record additions only; preserve Wave 2 scene/epoch changes
- `frontend/src/novel/AssetLibraryPanel.tsx`
- `frontend/src/novel/StoryDatabase.tsx`
- `frontend/src/novel/WorkflowPanel.tsx`
- `frontend/tests/e2e/r4-structured-search.spec.ts`
- `tests/test_post_interop_structured_search.py`
- This report and its adjacent JSON manifest

Composition wiring in `app/experimental/api.py` was already restored. The root owns the shared `ExperimentalWorkbench.tsx` wiring for `world_record` and `graph_record` requested IDs. Preserve those integrated edits when checkpointing.
