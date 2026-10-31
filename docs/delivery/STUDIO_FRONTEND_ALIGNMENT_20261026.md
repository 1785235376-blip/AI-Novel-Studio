# Studio frontend/backend alignment, 2026-10-26

Status: **ACTUAL TARGET SOURCE VERIFIED; wire compatibility PARTIAL**.
Final target source is now published at
`03e8034a41adc18ab0e32a35688e6ec2ff889d9f`, tree
`ebbffb2f8938f80b98df8ab779eec34a0014b706`. This supersedes the temporary
source-unavailable state below. Formal image-node command parsing is
**FRONTEND_BLOCKED**; the new dual canvas is explicitly a local draft UI with
no generation/execution HTTP caller. This unit does not claim browser acceptance.
Earlier selection of `048c5ebb` is superseded; original evidence is retained.
The confirmed actual target is
**`work/hermia-theme-dualcanvas-20261026`**, created from the i18n branch and
merging default-uw-port. It was initially unavailable, so earlier target tests
were correctly NOT_RUN at that checkpoint. It has since been fetched and read
at the exact SHA above. Neither `048c5ebb` nor `34eb95c7` is the final target.
Prior target choices and their browser-acceptance applicability remain superseded;
their evidence is retained rather than relabeled as final-target runs.

## Fixed sources and ownership

- Backend baseline: `ffe1937911cff32d4ebd4770b350674627501d3a`.
- Actual target: `origin/work/hermia-theme-dualcanvas-20261026` at
  `03e8034a41adc18ab0e32a35688e6ec2ff889d9f`; parent
  `f8d76863792335babf30fa47d030989c6482e5d7`. Git merge-base with each
  user-specified code parent below equals that parent, proving both are included.
  Actual default `App.tsx` and SDK callers were read from this target, not inferred
  from the parents. Target Production and Storyboard client blobs match the
  source-reviewed hashes below.
- Published parent reference: `origin/work/hermia-default-uw-port-20261025`,
  `34eb95c7f247e90168b27f96e33e6feacd80fc8d`, commit time
  `2026-10-26 10:14:02 +0800`; includes `f7174b6b` identity-pending/default
  drawer work and `2ed4c99c` follow-up fixes. This is a separate parent branch from
  `work/hermia-default-ui-i18n-20261025`, whose `048c5ebb` target was rejected.
- User-specified published parent code points, verified from Git objects:
  `5e279fb65073468cd94b59936378af70a94eddb0` (i18n) and
  `2ed4c99cd2360179c6b9593f457bb3ff1c8d0c69` (default-uw-port).
  `048c5ebb` and `34eb95c7` are their respective review-only descendants;
  those parent snapshots were insufficient until the actual target was fetched.
- The published uw-port ref contains `work/hermia-fe-contracts-20261025` at
  `3e72db70f6270e4f27d21647b229e6cf0d2c1b32` and
  `work/hermia-loop-u4-20261025` at
  `a0a56101a58ebdd210b996402b617d09b13b2d6e`: each pair's `git merge-base`
  equals the corresponding older head. Its merge-base with `048c5ebb` is
  `73819989d1c7764cd78ffb279afa954d98a37af8`; timestamp alone is insufficient
  to choose the user-facing target. Both candidate refs were fetched read-only;
  no branch checkout/reset or frontend merge occurred.
- Both user-specified parent code points' `studioProductionClient.ts` Git blob:
  `1d4036653297a0379faabc56ebcfbbf66c392068`; backend baseline's different
  frontend client blob: `660d1b2921cab32a073d2d32281649abdef21671`.
  Both remote review descendants retain that Production client blob.
  All four Storyboard client blobs are also identical:
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

## Actual confirmed target callers and wire contracts

All frontend paths in this table are under `frontend/src` at confirmed target
`03e8034a`. The new UI changes were compared against the published uw-port parent.
`studio` means `/api/projects/{projectId}/studio`.
Creative Storyboard documents use a separate root:
`/api/novels/{projectId}/experimental/creative`. In the published parent,
`creative/client.ts` constructs that root and passes it to
`createStoryboardClient` at line 81; the backend `app/creative/api.py` declares
the matching `/novels/{nid}/experimental/creative` router prefix. Production jobs
remain under the Studio root. The backend also mounts `/api/v1` aliases; the
source-reviewed frontend calls shown here use `/api`.

| Consumer / source | Request and response contract | Backend owner / boundary |
| --- | --- | --- |
| `rebuild/canvas/DualStack.tsx`, mounted by `rebuild/image/ImageRebuild.tsx` and `rebuild/video/VideoRebuild.tsx` in Pro mode | No generation/execution HTTP call. Lower-to-upper explicit confirmation copies a local graph snapshot using `readCanvasGraph` / `writeCanvasGraph`. UI explicitly declares generation/execution unavailable | Local draft editing only; no server asset, queue, reviewed result or graph execution is created by this UI. A backend image-chain PASS does not close this frontend handoff gap |
| `App.tsx:191-192,2162`, `workspace/defaultui/DefaultTasksDrawer.tsx:32-37` | Default entry stays `LegacyApp` and mounts the new tasks/results/history drawer; `?uw=1` remains an opt-in alternate. Drawer constructs clients only for a real actor and complete collaboration scope | User-facing default integration, not proof that local placeholder identities may access collaboration; no identity means no reads |
| `workspace/tasks/useLiveTasks.ts:31` | Actual default-drawer feed calls TaskCenter `readTasks` plus Production `list` and `get`; uses original session/branch headers and retires late-response leases | Existing read routes; Production pagination SDK is not used by this feed |
| `workspace/integration/useUnifiedLoop.ts:20,40-42` | Result target exists only when selected command has `canvas_return`; asset reads call `sc.assets(false)`, history/restore use existing `graphs.canvasViews` | No new execution owner. No target capsule means the drawer shows a gap rather than inventing an adoption target |
| `creative/useStoryboardProductionController.ts:160`, `creative/studioStoryboardClient.ts:23` | POST `/api/novels/{projectId}/experimental/creative/documents/{id}/shots/{shot}/image-request`; `expected_version`, `shot_version`, `shot_digest`, explicit operation/provider/model/request ID/parameters; response `shot_pin` must equal the requested document/shot snapshot | Original Storyboard service; produces reviewed input, not an executed job |
| `creative/studioProductionClient.ts` `preview/create` | POST `studio/production/preview` with command; POST `/jobs` with command and `reviewed_preview_digest`; create uses original request ID as idempotency key | Original Production owner and ImageJobService; preview does not dispatch |
| Same client's `get/execute/refresh/cancel/reconcile/review/candidate` | `GET /jobs/{owner}/{id}`; actions POST exact `expected_version` and `expected_request_digest`; review adds `reviewed_output_digest`; candidate reads bytes from `/candidate`; backend refresh route is specifically `/jobs/video/{id}/refresh` | Original job lifecycle; candidate is not a reviewed asset; later manual review and Storyboard binding remain separate |
| `creative/studioStoryboardClient.ts:22`, `useStoryboardProductionController.ts` `bind` / exact-image flow | POST `/api/novels/{projectId}/experimental/creative/documents/{id}/shots/{shot}/image-binding` with current document/shot versions/digest and `asset_id/version/digest/kind`; response advances document exactly one version and preserves the shot | Original Storyboard image-binding owner; no alternate adoption store |
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
execution gate requiring `ai_execution_v2`, `narrative_production_v2`,
`model_broker_v2`, and `author_context_inspector_v2`. Production rechecks trusted Host
session, model-host binding, scope and permission before and after its callback.
Preview uses `domain.read`; create/execute/cancel/reconcile use `domain.write`;
review uses `domain.review`. Test fixtures retain those
mounted guards and configure original temporary File owners. A disabled Studio
feature returns 404 rather than an empty successful task list. Invalid Production
query returns 422 with `EXPERIMENTAL_INVALID` /
`STUDIO_PRODUCTION_QUERY_INVALID`, without echoing private input. Stale Canvas
restore returns 409 and does not overwrite current content.

The actual image-request response parser requires the closed envelope
`contract/shot_pin/command/automatic_dispatch/model_called/output_policy/product_acceptance`:
contract `studio-storyboard-image-request/1`, both automatic/model booleans false,
output policy `PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW`, acceptance
`LOCAL_REQUIRED`. Its command has `allow_cloud=false`, a request ID of 1..100
allowed identifier characters, and a `CREATIVE_DOCUMENT` source matching the
document snapshot; this is not a `canvas_image_node` or invented shot-command
field. Production preview/create returns the existing preview/job contracts;
candidate bytes carry original `X-Asset-SHA256`, `X-Asset-Version`, media type,
and `Cache-Control: no-store`. Host absence/binding errors remain 403
`CREATIVE_MODEL_HOST_REQUIRED` / `CREATIVE_MODEL_HOST_BINDING_REQUIRED`;
original owner CAS conflicts are sanitized to 409
`STUDIO_PRODUCTION_VERSION_CONFLICT` with current version. Source-reviewed
frontend parsing never turns a capability hint into an authorization grant.

## Confirmed-target compatibility failure: formal image-node provenance

At confirmed target `creative/studioProductionClient.ts:376`, `job()` parses all
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
5e279fb6 / 2ed4c99c and their review descendants have the identical validator blob.
Confirmed target 03e8034a retains the identical validator blob and rejection.
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

### Historical provisional run, now superseded as target evidence

After fetching and inspecting `34eb95c7`, an intermediate contract revision was
labeled `PROVISIONAL_DEFAULT_UW_PORT`. The subsequent user confirmation of the
unpublished branch supersedes that provisional selection as well as `048c5ebb`.
The inspected Production/Storyboard client
blobs are identical across these refs, while default App and drawer consumers
are different as mapped above. No frontend file was modified or merged.

Rerun with a fresh per-invocation settings/data root:
`10 passed, 1 xfailed, 3 warnings in 8.65s`.
Evidence: `.runtime/frontend-provisional-34eb95c7.log` and
`.runtime/frontend-provisional-34eb95c7-results.xml`.
The expected failure is now retained as **PARENT_REFERENCE_ONLY**, not an
actual-target failure or product PASS. This is a backend wire regression run against source-reviewed constraints;
the complete TypeScript parser, default drawer UI and browser were not executed.
At that checkpoint the test module recorded the confirmed branch, `FRONTEND_TARGET_SHA=None`,
`NOT_AVAILABLE_NOT_RUN`, and both published parent SHAs. Its named expected
failure is `test_published_parent_frontends_admit_formal_image_node_job_command`.
That metadata/name correction changed no production logic; unchanged tests were
not rerun merely to relabel evidence. The pending action was to fetch the bot's
actual published SHA and inspect its real callers before new target verification.
The final section below records that later source retrieval and wire run.
Prior browser work must not be relabeled as final-target acceptance.

### Final actual-target source and wire verification — supersedes pending state

Remote target `03e8034a41adc18ab0e32a35688e6ec2ff889d9f` was fetched after the
pending checkpoint. Its tree is `ebbffb2f8938f80b98df8ab779eec34a0014b706`;
both user-specified source parents are verified ancestors. Source reads confirm
the current default App drawer, the new Image/Video Pro `DualStack`, and the
unchanged strict Production and Storyboard validators. The new canvas code
copies local snapshots only and declares generation/execution unavailable.

Test metadata is now bound to the exact actual SHA with
`SOURCE_VERIFIED_WIRE_CHECKS_ONLY` and `CONFIRMED_TARGET_WIRE_CONTRACT`.
The named regression is
`test_confirmed_frontend_admits_formal_image_node_job_command`.
Executed in this unit's baseline-derived backend worktree with only the separately
reported Asset portability repair; the coordinator's merged-backend and actual
browser results remain separate evidence:

```text
python scripts/run_studio_backend_tests.py -q tests/test_studio_frontend_alignment_v2.py
10 passed, 1 xfailed, 3 warnings in 11.03s

python scripts/run_studio_backend_tests.py -q --runxfail tests/test_studio_frontend_alignment_v2.py::test_confirmed_frontend_admits_formal_image_node_job_command
1 failed, 3 warnings in 4.84s
AssertionError: Confirmed frontend 03e8034a41adc18ab0e32a35688e6ec2ff889d9f rejects original backend command fields: ['canvas_image_node']
```

Retained evidence: `.runtime/frontend-confirmed-03e8034a.log`,
`.runtime/frontend-confirmed-03e8034a-results.xml`,
`.runtime/frontend-confirmed-03e8034a-failure.log`, and
`.runtime/frontend-confirmed-03e8034a-failure.xml`.
The strict expected failure is a confirmed-target **wire blocker**, not a pass.
No production authority or frontend file was changed to hide it. Earlier
unavailable/provisional sections above record chronology, not current status.
