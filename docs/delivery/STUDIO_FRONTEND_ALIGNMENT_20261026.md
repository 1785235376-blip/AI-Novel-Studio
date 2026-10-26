# Studio frontend/backend alignment, 2026-10-26

Status: **TARGET PROVISIONAL; PARTIAL; no frontend acceptance claim**.
The user explicitly rejected the initially selected `048c5ebb` frontend:
"你使用的前端是错误的，bot做了个新的，更友好的". All earlier claims that
`048c5ebb` was the intended frontend are superseded; original evidence is retained.
The stronger candidate is the newer default-shell integration `34eb95c7` below,
supported by actual default entry code and the coordinator's read-only recovery
of the earlier bot handoff referring to ancestor `f7174b6b`. Exact user target
confirmation remains pending. This report does not assert browser, PostgreSQL,
external-model, GPU, or product acceptance.

## Fixed sources and ownership

- Backend baseline: `ffe1937911cff32d4ebd4770b350674627501d3a`.
- Provisional remote frontend: `origin/work/hermia-default-uw-port-20261025`,
  `34eb95c7f247e90168b27f96e33e6feacd80fc8d`, commit time
  `2026-10-26 10:14:02 +0800`; includes `f7174b6b` identity-pending/default
  drawer work and `2ed4c99c` follow-up fixes. This is a separate branch from
  `work/hermia-default-ui-i18n-20261025`, whose `048c5ebb` target was rejected.
- The candidate ref contains `work/hermia-fe-contracts-20261025` at
  `3e72db70f6270e4f27d21647b229e6cf0d2c1b32` and
  `work/hermia-loop-u4-20261025` at
  `a0a56101a58ebdd210b996402b617d09b13b2d6e`: each pair's `git merge-base`
  equals the corresponding older head. Its merge-base with `048c5ebb` is
  `73819989d1c7764cd78ffb279afa954d98a37af8`; timestamp alone is insufficient
  to choose the user-facing target. Both candidate refs were fetched read-only;
  no branch checkout/reset or frontend merge occurred.
- Candidate frontend `studioProductionClient.ts` Git blob:
  `1d4036653297a0379faabc56ebcfbbf66c392068`; backend baseline's different
  frontend client blob: `660d1b2921cab32a073d2d32281649abdef21671`.
  The candidate's Production client is byte-identical to the old `048c5ebb`
  client. Both Storyboard client blobs are also identical:
  `132d234b40cab1950ebb2baae74f28c7ea3e199a`. This preserves the specific wire
  findings, not the superseded target-selection or UI-acceptance claims.
- Read first: repository `AGENTS.md`,
  `docs/delivery/HERMIA_CAPABILITY_LEDGER_20261022.md`, selected frontend
  `docs/delivery/INTERFACE_COVERAGE.md` and
  `docs/delivery/HERMIA_UNIFIED_LOOP_CONTRACTS_20261025.md`, backend
  `docs/delivery/HERMIA_BACKEND_CONTRACTS_20261025.md`.
- The historical capability ledger is source inventory, not proof of current
  runtime completion. The old interface gap list is superseded where actual
  newer callers and backend contracts below demonstrate otherwise.
- This unit owns only this report and
  `tests/test_studio_frontend_alignment_v2.py`. No frontend, SDK, TaskCenter
  cursor/collaboration, audio history owner, permissions, model runtime,
  dependencies, or protected checkout was modified.

## Actual provisional frontend callers and wire contracts

All frontend paths in this table are under `frontend/src` at `34eb95c7`.
`studio` means `/api/projects/{projectId}/studio`.

| Consumer / source | Request and response contract | Backend owner / boundary |
| --- | --- | --- |
| `App.tsx:191-192,2162`, `workspace/defaultui/DefaultTasksDrawer.tsx:32-37` | Default entry stays `LegacyApp` and mounts the new tasks/results/history drawer; `?uw=1` remains an opt-in alternate. Drawer constructs clients only for a real actor and complete collaboration scope | User-facing default integration, not proof that local placeholder identities may access collaboration; no identity means no reads |
| `workspace/tasks/useLiveTasks.ts:31` | Actual default-drawer feed calls TaskCenter `readTasks` plus Production `list` and `get`; uses original session/branch headers and retires late-response leases | Existing read routes; Production pagination SDK is not used by this feed |
| `workspace/integration/useUnifiedLoop.ts:20,40-42` | Result target exists only when selected command has `canvas_return`; asset reads call `sc.assets(false)`, history/restore use existing `graphs.canvasViews` | No new execution owner. No target capsule means the drawer shows a gap rather than inventing an adoption target |
| `creative/useStoryboardProductionController.ts:160`, `creative/studioStoryboardClient.ts:23` | POST `studio/documents/{id}/shots/{shot}/image-request`; `expected_version`, `shot_version`, `shot_digest`, explicit operation/provider/model/request ID/parameters; response command must retain the selected shot pin | Original Storyboard service; produces reviewed input, not an executed job |
| `creative/studioProductionClient.ts` `preview/create` | POST `studio/production/preview` with command; POST `/jobs` with command and `reviewed_preview_digest`; create uses original request ID as idempotency key | Original Production owner and ImageJobService; preview does not dispatch |
| Same client's `get/execute/refresh/cancel/reconcile/review/candidate` | `GET /jobs/{owner}/{id}`; actions POST exact `expected_version` and `expected_request_digest`; review adds `reviewed_output_digest`; candidate reads bytes from `/candidate` | Original job lifecycle; candidate is not a reviewed asset; later manual review and Storyboard binding remain separate |
| `creative/studioStoryboardClient.ts:22`, `useStoryboardProductionController.ts` `bind` / exact-image flow | POST image-binding with current document/shot versions/digest and `asset_id/version/digest/kind`; response advances document exactly one version and preserves the shot | Original Storyboard image-binding owner; no alternate adoption store |
| `workspace/UnifiedWorkspacePreview.tsx:150-178`, `workspace/state/projectIncarnation.ts` | GET `studio`; require matching `project.id`, printable nonempty `project.incarnation` <=200 chars; different incarnation retires owned UI geometry | Original File project incarnation; failed reads are not deletion evidence |
| `creative/studioCanvasViewClient.ts:80-122`, `workspace/history/restoreFlow.ts` | History has current incarnation/version/digest and ascending version snapshots; restore posts current CAS pins plus selected historical version/digest | Existing CanvasView metadata history; no binary restoration or execution authority |
| `creative/studioProductionClient.ts:677-692` | `listPage` sends optional owner/operation plus limit 1..100, offset 0..1,000,000; envelope requires total/limit/offset/has_more together, `has_more = offset + limit < total`, out-of-range page empty | Existing query adapter; response pagination is not a stable snapshot or storage index |
| `creative/studioProductionClient.ts:706-718` | Raw timeline history GET; restore POST exactly `expected_version`, `reviewed_timeline_digest`, `restore_version`, `restore_digest` | Existing timeline metadata history, not an audio asset binary archive |

The actual non-test source contains **no callers** of `listPage`,
`timelineHistoryRaw`, or `timelineRestoreRaw` beyond their definitions. Their
SDK presence and backend availability do not close the UI integration gaps.
TaskCenter's selected client has opt-in offset paging and a single fallback on
422 `EXPERIMENTAL_INVALID`; its separately owned cursor work was read only.

Feature/authority mapping remains original: Studio requires
`narrative_production_v2`; model Production routes additionally call the original
execution gate (including `ai_execution_v2`). Production rechecks trusted Host
session, model-host binding, scope and permission before and after its callback.
Preview uses `domain.read`; create uses `domain.write`. Test fixtures retain those
mounted guards and configure original temporary File owners. A disabled Studio
feature returns 404 rather than an empty successful task list. Invalid Production
query returns 422 with `EXPERIMENTAL_INVALID` /
`STUDIO_PRODUCTION_QUERY_INVALID`, without echoing private input. Stale Canvas
restore returns 409 and does not overwrite current content.

## P1 provisional-frontend incompatibility: formal image-node provenance

At provisional frontend `creative/studioProductionClient.ts:376`, `job()` parses all
Production list, get and action responses. Its exact command-key allowlist at
line **426** excludes `canvas_image_node`. The fixed backend legitimately emits
this field for formal image-node jobs, binding project incarnation, canvas and
node identity. Consequently one such visible job causes the old frontend's
entire list parse to reject; ordinary image commands without that capsule pass
the inspected command-key boundary.

The executable probe obtains a real original QUEUED job via mounted
preview/create/get, then applies the source-reviewed frozen allowlist. Its
failure is:

```text
Historical 048c5ebb probe: rejects original backend command fields: ['canvas_image_node']
34eb95c7 has the identical validator blob; provisional-target probe uses that SHA.
```

This probe is a wire-contract reproduction, not execution of the complete
TypeScript parser or a browser. A separate passing test proves backend list/get
retain the original capsule and incarnation. **Do not strip the provenance,
filter the job away, permit arbitrary fields, or downgrade backend authority.**

Minimal frontend-owner follow-up: port the already present backend-baseline
client's typed optional `canvas_image_node` and strict binding validation into
the newer frontend branch. Reference `ffe19379` client line 30 (typed field),
line 496 (allowlist), and its existing `canvasImageNodeInCommand`,
`sameCanvasImageNode`, prompt digest and job-binding checks. Preserve newer
frontend paging/i18n changes; do not replace that whole file or merge either
frontend tree wholesale. Re-run actual selected-client and browser tests after
the owner integrates the port. This backend-only unit cannot close that work.

## Executed verification and retained failures

The following initial run numbers belong to the superseded `048c5ebb` target.
They retain backend HTTP regression value, but do not prove acceptance of the
user's intended new frontend. See the subsequent provisional-target rerun below.

The coordinating unit reported M0 PASS before this unit ran tests. Its isolated
runner was copied temporarily, untracked, without installation. It configures
File/Mock, separate settings/data/temp roots and blocks external sockets while
allowing local loopback. Real provider/model execution did not occur.

```text
python scripts/run_studio_backend_tests.py -q tests/test_studio_frontend_alignment_v2.py
10 passed, 1 xfailed, 3 warnings in 10.23s

python scripts/run_studio_backend_tests.py -q --runxfail tests/test_studio_frontend_alignment_v2.py::test_selected_frontend_admits_formal_image_node_job_command
1 failed, 3 warnings in 4.62s
```

The strict xfail is **FRONTEND_BLOCKED**, never a passing compatibility case.
The 10 passing cases cover identity recreation, actual ordinary image
preview/create/list paging, sanitized query rejection, feature-off refusal,
Canvas CAS restore/history, unchanged audio timeline/asset boundary, and formal
node provenance retention. They are not the whole backend suite or evidence of
frontend UI closure. Audio received only an existing-boundary regression probe.

Local evidence lives in this unit's `.runtime/studio-frontend-alignment/`:
`alignment-with-provenance.log`, `alignment-final.log`, and
`frontend-blocked-original-failure.log`. The coordinator must retain these with
final evidence before bounded cleanup. An initial development run had
8 passed / 1 fixture-assumption failure / 1 xfailed: the preexisting synthetic
`seed_audio` helper deliberately writes `command=null`, so it could not test
frontend command validation. That test was replaced with actual ordinary image
preview/create requests; this was not a backend repair or hidden product failure.

GraphFlow `gf_read` was used before exploration. The configured server exposes
`gf_read/gf_exec/gf_edit/gf_macro`, not the instructed old
`graphflow_context/plan/index`; no old-name index success is claimed.

### Provisional target correction verification

After fetching and inspecting `34eb95c7`, the frozen test contract was relabeled
with that SHA and `PROVISIONAL_DEFAULT_UW_PORT`. Its former `048c5ebb` SHA is
explicitly retained as superseded. The inspected Production/Storyboard client
blobs are identical across these refs, while default App and drawer consumers
are different as mapped above. No frontend file was modified or merged.

Rerun with a fresh per-invocation settings/data root:
`10 passed, 1 xfailed, 3 warnings in 8.65s`.
Evidence: `.runtime/frontend-provisional-34eb95c7.log` and
`.runtime/frontend-provisional-34eb95c7-results.xml`.
The expected failure remains a **provisional frontend blocker**, not product
PASS. This is a backend wire regression run against source-reviewed constraints;
the complete TypeScript parser, default drawer UI and browser were not executed.
It does not finalize the user's target selection.
