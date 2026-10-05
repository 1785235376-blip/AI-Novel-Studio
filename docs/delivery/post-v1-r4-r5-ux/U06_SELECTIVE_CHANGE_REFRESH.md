# U06 · Evidence-bound change impact and selective refresh

## Status and usable scope

EXTEND; deterministic implementation and integration are present. Contract tests pass for File storage and both production API aliases. Selected cover and storyboard refresh now also reaches currently validated/enabled original local A1111 and supported ComfyUI checkpoint routes through the existing media registry bridge. Real routes require the current broker and explicit estimates. Generation remains an explicit action, with no automatic approval. Video/audio/subtitle refresh and model-inferred impact remain separate unsupported coordinators; real image quality is NOT_RUN.

The experimental workbench tab **修改影响与更新** lets an authorized author:

1. Choose a current chapter, stable character ID, accessible world record, or asset.
2. Inspect exact recorded dependencies and their original/current source versions. Current character labels follow stable IDs; manuscript-wide replacement is not performed.
3. Distinguish stale references, references with no recorded source version, and unknown/unrecorded impact. There is no fabricated comprehensive graph or inferred edge count.
4. Lock a satisfactory outcome using optimistic concurrency. The original outcome is not modified or approved.
5. Select stale supported task nodes, then explicitly preflight their current source snapshots, permissions, privacy, adapter identity, bounded candidate counts and known cost.
6. Prepare new copied briefs and original-domain media tasks atomically, without dispatching. Prepare retries use a stable actor-bound idempotency key.
7. Execute each selected new task explicitly through `MediaService.execute`, or cancel it. Output stays `PENDING_REVIEW` in the original media review flow. Original tasks/results and unrelated nodes remain unchanged.
8. Reload or reopen to find the same durable tasks. Failed/cancelled/stale tasks require a new preflight and new task; no automatic retry occurs.

## Reused authorities and exact coverage

- StoryGraphService/WorldService world records and their source/entity/semantic bindings, including chapter references and knowledge events when that extension is enabled.
- PlanningService nodes, parent links and its authorized proposal projection, only when planning is enabled. Disabled/stale A01 simulator proposals are omitted by the original planning provenance validator.
- AssetLibraryService's existing asset DAG through ProductionLineageService. No parallel asset registry is created.
- MediaService briefs and tasks, with exact source snapshots.
- ScreenplayService scene source versions, shots, storyboard references and recorded motion start/end references. HTTP URLs and unrecorded frame relationships are not inferred.
- AudiobookV2Service plans, bound audio assets, subtitle views and mix proposals. Subtitle entries are views over an existing plan, not invented exported files.
- Existing production-manifest export views. Arbitrary files previously exported outside these owners are unknown.

Nodes whose recorded source/ancestor is inaccessible are omitted as a whole, including their IDs, labels and counts. A10 `research_sources` records and their dependants are always excluded from this author-wide projection because U06 does not invoke A10's current-actor source projector. Knowledge records disappear when their own flag is disabled.

Read-only collaborators cannot use this author-omniscient projection: all routes require `domain.write`, matching the existing story graph author catalog. The UI provides an explicit unavailable/permission state rather than a misleading empty graph.

## API, flags and persistence

- Exact default-OFF flag: `change_impact_v2`
- Required runtime dependencies: `temporal_story_graph_v2`, `asset_lineage_v2`; the temporal graph retains its existing world dependency.
- Optional source owners retain their own flags; enabling U06 does not enable them.
- API: `/api/novels/{nid}/experimental/change-impact` and `/api/v1/novels/{nid}/experimental/change-impact`
- Routes: `GET sources`, `POST query`, `PUT locks`, `POST preflights`, `POST preflights/{id}/prepare`, `GET refreshes`, `POST refreshes/{id}/execute`, `POST refreshes/{id}/cancel`.
- New isolated ExperimentalStore collections: `change_impact_locks_v2`, `change_impact_preflights_v2`, `change_impact_refreshes_v2`. They use the existing File/PG scope document schema; no historical migration is rewritten.
- Copied briefs/tasks/proposals remain in the original isolated media collections and carry a validated U06 ownership marker. The marker is checked before CAS errors, generic lists, previews, queue, dispatch, retries and reviews. Malformed ownership fails closed.
- V1 acceptance forces U06 OFF. With U06 OFF and ordinary media ON, U06-owned derivative rows are hidden and cannot execute/retry/review through generic media paths. Ordinary media and A13 records without a U06 marker retain their original behavior.

## Dispatch, budget and cancellation

The exact built-in `MockImageWorkflowAdapter` retains its `SYNTHETIC_PROTOCOL_ONLY` path. `RegisteredLocalImageWorkflowAdapter` projects only exact original `LocalImageAdapter` registrations for enabled A1111 and the shipped ComfyUI checkpoint workflow. No family-name discovery installs executable code. Real routes run one image per task and reject reference-image conditioning. Both cover and storyboard refresh use the original current-source preparers. Stored storyboard shot snapshots are exact dependency edges; an old screenplay scene still requires its original source to be brought current first.

Current chapter/character/asset bindings, the original task fingerprint, lock version, actor/scope, adapter configuration, environment identity and current chapter privacy state are bound to preflight. They are rechecked at prepare, final dispatch and result acceptance. A newer source cannot be marked current by an old callback.

If the existing model broker is enabled, U06 reuses its preview, reservation, final-dispatch guard and terminal settlement. A budget change blocks the old preview. Cancellation can recover a reservation committed before its pointer checkpoint. Without that broker, only the known-zero synthetic executor is available. Real preflight costs are estimates; absent actual billing stays `UNKNOWN_UPSTREAM` and must be explicitly reconciled before new work. They are never silently zeroed.

The copied brief/task/pointer are one scope transaction. Partial preparation rolls back. Cancellation invalidates the existing media execution token; late output is discarded. No direct Canon/manuscript write, arbitrary replacement adapter, output approval or second executor exists.

## Explicit unsupported paths

- Video, TTS, subtitles, reference-conditioned images, arbitrary ComfyUI graphs and arbitrary exports have no U06 executor. Their recorded impact and locks remain useful. Local-image quality/GPU performance remain unverified even though supported original routes are wired.
- No text-based whole-manuscript rename or semantic impact inference runs.
- Existing task preparation cannot queue from a U06-owned copied brief; it requires a fresh U06 preflight.
- A13 capture now calls the U06 coordinator's current origin checks and records the exact refresh/preflight binding. Replay preserves that origin, validates it again and keeps U06-owned derivatives hidden when U06 is off. Missing/currently inaccessible origin authority still blocks capture or replay.
- Full literary quality, real model cost/quality, Windows/IME/native GPU, complete external export dependency discovery and user aesthetic acceptance are NOT_RUN or outside this checkpoint.

## Earlier synthetic-checkpoint receipt · 2026-10-05

Executed through the isolated repository runner:

```text
python -m pytest tests/test_r4_change_impact.py tests/test_r4_change_impact_mounted.py tests/test_r4_production_lineage.py tests/test_r3_media_workflows.py -q -m file_backend_only --disable-warnings
51 passed; 53 deselected; 1 warning
```

The 53 deselected cases are not passes. Real PostgreSQL parameterizations are authored for CI, but no local PostgreSQL endpoint is configured. U06's direct File/real-PG fixture has 15 cases per backend; mounted tests cover both `/api` and `/api/v1` using the existing real authorization/session stack. PostgreSQL execution is NOT_RUN locally.

Focused frontend verification:

```text
pnpm exec vitest run src/experimental/ChangeImpactPanel.test.tsx
8 passed
pnpm exec tsc -b --pretty false
PASS on the latest combined tree. An earlier concurrent App.tsx:1354 TS2345 was reported to the composition owner and resolved before this rerun.
pnpm run lint
UI token guard PASS
```

UI cases cover exact selection, explicit preflight/prepare without auto-dispatch, versioned locks, uncertain-response retry with the same idempotency key, unsupported/empty states, cancellation while dispatch awaits, StrictMode/unmount/client-scope fencing, late preflight suppression, and permission/read-only states.

Authored real API/browser journey: `frontend/tests/e2e/r4-change-impact.spec.ts` (J11). Playwright collection finds one test. It covers a changed chapter, related selected/locked tasks, an unrelated task, new source snapshots, pending-review output, unchanged originals/manuscript, cancellation, reload and three desktop viewport screenshots. Local browser/visual/geometry execution is NOT_RUN because Chromium launch EPERM was already confirmed by the lead; no local retry or screenshot claim is made. Hosted CI must execute it before browser PASS can be reported.

No paid API, actual model, downloaded weights, credentials, production deployment, frozen R2/R3 edit, push, merge or release is part of this owned checkpoint.

## UI handoff

New consumers: `ChangeImpactPanel.tsx`, typed `changeImpactClient.ts`, and the workbench tab supplied by the composition owner. They reuse `Panel`, `Button`, `Badge`, `StatusMessage`, shared fields/action/resource hooks and existing experimental layout classes. No tokens, AppShell geometry or protected primitives change. The canonical NOVEL reference and DS-v1.0 rules were reviewed.

Preserve explicit selection, lock state, pending-review status, source-version evidence, unknown-impact wording, permission/retry states and independent cancel availability when styling. Do not turn prepare into execute, remove late-response fencing or claim that protocol wiring proves real-model quality. See [registered local-media receipt](REGISTERED_LOCAL_MEDIA.md) for the later implementation and verification.
