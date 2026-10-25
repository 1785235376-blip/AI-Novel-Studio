# Interface coverage (frontend view of existing backend/SDK) [HERMIA-FE-20261025]
Evidence type: static source read of a167022b (no live API calls).

| Area | Client / file:line | Endpoints | Gaps |
|---|---|---|---|
| Identity | api.ts:173 `api.bootstrap`; App.tsx:484-502 actor; store.ts collaboration scope {workspaceId,projectId,storylineId,branchId} | bootstrap | App.tsx:397-401 placeholder `local-author`; Novel has no incarnation/created_at → server id reuse after delete undetectable; no explicit project-instance field (we derive ws/storyline/branch) |
| Project delete | api.ts:160 adminDeleteProject | DELETE | no tombstone/event; client relies on new id |
| M3 Task center | taskcenter/taskCenterClient.ts:63,92-155 | GET /api/novels/{nid}/experimental/workspace/tasks?q=&failed_only=, cancel, inbox, review item/batch | **no pagination**; cost always `state:'UNKNOWN'` (taskCenterContract.ts:200-204) |
| M7 Video / M8 Audio / M5 Image production | creative/studioProductionClient.ts:337 base /api/projects/{id}/studio/production | jobs create (reviewed_preview_digest), list (≤1000, no paging), get, execute/refresh/cancel/reconcile/review (expected_version+request_digest), candidate blob, timelines | list capped at 1000; owners image/audio/video/timeline |
| M9 Graph runs | creative/studioGraphClient.ts:869,1228-1411 | catalogs, modelCapabilities(:1282), graph CRUD, preflight, runs, model/media preview/dispatch/refresh, executeMedia/reconcileMedia/reviewMedia, mediaCandidate(:1407) | capability is per-model only |
| Canvas history | creative/studioCanvasViewClient.ts:64-122 | list/get/create/save, history(:103), restore(:104) | — |

**Second-media candidate:** audio (m8.audio.* has the widest owner+op coverage via production client); video (m7.video.*) as fallback.

## Gap list (consolidated at f178ff84) [HERMIA-FE-20261025 M10]
| Id | Gap | Status |
|---|---|---|
| G-AUD-1 | GET /jobs: no owner/operation filter, no paging (≤1000) — studioProductionClient.ts:647-649 | 受阻 (backend) — UI filters locally, shows gap text |
| G-AUD-2 | get(owner,id) owner-generic | covered |
| G-AUD-3 | candidate(job) returns unvalidated Blob | mitigated in UI (kind + blob.type audio/*) |
| G-AUD-4 | audio canvas_return only for LOCAL_FFMPEG trim | 部分实现 — others say "没有记录作品位置" |
| G-AUD-5 | history/restore canvas-level only | 受阻 (backend) |
| G-AUD-6 | review(job) owner-generic | reused |
| G-AUD-7 | cost always UNKNOWN | shown as "未知" |
| G-TC-1 | Task center has no pagination | 受阻 (backend) |
| G-ID-1 | No project incarnation → same-id recreation undetectable | 受阻; relies on new server id |
| G-PURGE-1 | Cold-start purge (project deleted while closed) | 部分实现, documented; needs server signal |
| G-U1-1 | resetAll not in UI | 部分实现 (P2) |
| G-UI-1 | Compare mode is sequential, not a real split | 部分实现 |
| G-A11Y-1 | axe color-contrast (rail) and aria-required-children (empty 章节 list under mock) | pre-existing, recorded, not fixed |
