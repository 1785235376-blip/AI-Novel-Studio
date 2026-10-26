# Studio V2 backend integration handoff — 2026-10-26

Status: **PARTIAL — backend File/Mock chain verified; frontend execution integration blocked.**

The actual chain is saved Storyboard shot → original image request → reviewed
Production preview → explicit queue/execute → private image candidate → explicit
human review → original shot binding → process restart and persisted read.
Both `/api` and `/api/v1` execute this chain against original `app.main:app`
in separate Windows processes over real loopback HTTP. Only the local image
provider HTTP endpoint returns a deterministic synthetic PNG. **This is a Mock
chain, not real AI generation or model-quality acceptance.**

## Sources and ownership

- Repository: `1785235376-blip/AI-Novel-Studio`.
- Fixed backend start: `ffe1937911cff32d4ebd4770b350674627501d3a`, tree
  `447bfefcee8393b9b0907fe7daff2d5b044709da`.
- Delivery branch: `work/studio-backend-integration-20261026`.
- User-confirmed frontend: `work/hermia-theme-dualcanvas-20261026`, now published
  at `03e8034a41adc18ab0e32a35688e6ec2ff889d9f`, tree
  `ebbffb2f8938f80b98df8ab779eec34a0014b706`. A final pre-upload read found the
  new ref after the earlier unavailable checkpoint. Both specified parent code
  points are verified ancestors. Actual-source contracts and browser inspection
  were then rerun; prior parent-only evidence was not relabeled.
- Published parent code references: i18n `5e279fb65073468cd94b59936378af70a94eddb0`
  (review descendant `048c5ebb3cedb138dcef15bbfc5e9f4be8c92760`) and default-uw-port
  `2ed4c99cd2360179c6b9593f457bb3ff1c8d0c69`
  (review descendant `34eb95c7f247e90168b27f96e33e6feacd80fc8d`).
  Earlier selection of either parent as the intended target is superseded.
- Three explicitly configured `gpt-6-astra` work units handled contracts,
  implementation and independently written counterexamples in separate
  worktrees. The coordinating chat did not claim a tool-driven model switch.
- Existing Graph, Director, Storyboard, Asset, ImageJob, Review, Timeline and
  Authorization owners remain authoritative. No new scheduler, task database,
  permission system or asset version store was created. Frontend/SDK,
  TaskCenter collaboration cursor and audio immutable-history sources are unchanged.

## Implemented changes

1. **Queue authority commit fence.** The original ImageJob mutation callback
   rechecks authority after waiting for the queue owner and before persistence.
   A revoked session cannot leave a newly queued row behind a rejected request.
2. **Reviewed Storyboard source lease.** Document-backed standalone image admission
   holds original source/asset/project leases through original queue publication,
   and rechecks actor, scope, incarnation and exact source. A changed or recreated
   shot cannot be admitted using stale reviewed input.
3. **Windows Asset index durability.** Staged SQLite is reopened non-truncating
   with a writable handle before `fsync`; original atomic publication remains.
4. **Windows Asset source signatures.** Native `FILE_BASIC_INFO.ChangeTime`
   replaces Python 3.11 Windows creation-time `st_ctime` in the existing six-field
   signature. Metadata-only, no-follow handles check type, reparse attributes and
   path/handle identity and always close. Native API errors refuse the query.
   Windows disposable index format advances once; source assets and cursor keys
   are not rewritten. Linux retains its original stat signature and index format.
5. **Reproducible isolated runner and acceptance tests.** Each invocation isolates
   HOME, USERPROFILE, XDG, APPDATA, LOCALAPPDATA, PROJECT_ROOT, data and temp paths.
   External network is blocked; loopback remains available for Windows socketpair
   and the actual HTTP test. No packages or models were installed.

The original Windows regression fixtures now close SQLite corruption-test
connections explicitly and preserve bytes on intentional same-size edits.
Their SQL, fault injection and correctness assertions are retained. Original
failing results, subsequent counterexamples and corrected results are preserved.

## Existing interfaces exercised

Let `C=/api/novels/{id}/experimental/creative` and
`P=/api/projects/{id}/studio/production`. The `/api/v1` aliases are also tested.

| Interface | Actual behavior verified |
| --- | --- |
| `C/documents`, `C/documents/{doc}/storyboard` | Original document creation and exact source/shot pins, persisted reopen |
| `POST C/documents/{doc}/shots/{shot}/image-request` | Prepare exact command only; no model or queue execution |
| `GET P/providers`, `PUT /api/asset-providers/{provider}` | Original configuration read/validate/save and registry refresh; invalid save preserves prior config |
| `POST P/preview`, `POST P/jobs` | Reviewed digest, exact command/source/provider binding, original request-ID idempotency |
| `GET P/jobs`, `GET P/jobs/image/{job}` | Authorized query/recovery without execution; existing filter/paging contract retained |
| `POST P/jobs/image/{job}/execute` | Explicit original executor; stale CAS/source/configuration refused |
| `GET P/jobs/image/{job}/candidate` | Real private PNG bytes; revoked reads refused |
| `POST P/jobs/image/{job}/review` | Explicit digest-checked original asset promotion, duplicate/concurrent review safe |
| `POST C/documents/{doc}/shots/{shot}/image-binding` | Explicit current document/shot CAS, original approved asset reference, single winning concurrent binding |
| `POST P/jobs/image/{job}/reconcile` | Unknown provider outcome remains UNKNOWN; no automatic resend or false failure |
| `GET /api/projects/{id}/studio/assets` | Windows cold/warm queries, source/index mutation detection, preserved old index on failed flush |

Task parameters remain in each exact command; shared provider settings use their
existing configuration owner and binding digest. Preview exposes the selected
command, sources, provider and execution recipe before confirmation. Configuration
drift invalidates that reviewed preview or blocks later dispatch. Shared template
editing, fan-out analysis and arbitrary internal cloud workflow control are not
new capabilities of this slice. Reads, previews, configuration changes, candidate
inspection, refresh and reopen never adopt results or automatically execute.

## Recovery and unsupported boundaries

- Duplicate create returns the original request receipt. A lost create response is
  recovered by reading the original queue, including after reconstructing owners.
- A pending execute is observable; concurrent execute does not send twice.
  Provider connection loss after send remains `UNKNOWN`; reopening/reconciling
  does not resend. Check the original job before any explicit new request.
- Conflicting source/shot/document/configuration changes require rereading current
  versions and a new explicit preview/confirmation. Revocation requires renewed
  authority. No private source or filesystem details are returned as recovery hints.
- Private candidates do not overwrite adopted assets. Approval interruption can be
  reconciled by the original promotion receipt; arbitrary old-file restoration is
  not implemented. Project-ID recreation and actor/branch isolation are retained.
- File keyed generation remains **off by default**. Its original 49-case regression
  runs separately; unsupported keyed cancel/retry remains refused.
- The confirmed frontend still has a strict parser which rejects formal
  `canvas_image_node` provenance. The explicit actual-target wire probe fails;
  this is **FRONTEND_BLOCKED**, never passing compatibility. Preserve backend
  provenance and port the existing typed binding validation into the frontend.
  The new `DualStack.tsx` currently changes only local drafts and exposes no
  HTTP execution caller. It must be explicitly connected to the existing
  owners by its frontend owner; adding speculative backend routes would not
  connect these local controls.
  See [frontend source mapping](STUDIO_FRONTEND_ALIGNMENT_20261026.md).
- No real model/GPU, PostgreSQL, cloud executor, packaged installer or Actions run
  is claimed. Existing POSIX SIGKILL cases are skipped on Windows. A real Windows
  symlink probe is skipped because privilege 1314 is unavailable; synthetic
  reparse-flag failure checks do not prove real reparse acceptance.
- The browser did create/save/reload a synthetic canvas against the backend using
  the earlier parent checkout. This is retained as **superseded parent evidence**
  and does not count as intended frontend or browser creative-chain acceptance.
- On actual `03e8034a`, the browser created a synthetic project through the
  backend, entered IMAGE professional mode, displayed both stacked canvases,
  and verified dark/light appearance. The page explicitly states local-only
  draft/no synchronization and generation/execution unavailable. This is a
  verified frontend/backend entry and an observed integration blocker, not a
  completed browser generation/review/writeback chain. Four unchanged frontend
  test files (DualStack, ImageDualGate, VideoDualGate, themeCanvasTokens) passed
  22 tests using already installed dependencies. Screenshots are in the evidence.

## Reproduction and evidence

Use installed Python 3.11+ and the existing repository dependencies. No installation
is part of the commands. Each invocation gets a unique isolated runtime directory.

```text
python scripts/run_studio_backend_tests.py -q tests/test_studio_backend_integration_v2.py tests/test_studio_integration_independent_v2.py tests/test_studio_process_reopen_v2.py
python scripts/run_studio_backend_tests.py -q tests/test_studio_frontend_alignment_v2.py
python scripts/run_studio_backend_tests.py -q tests/test_file_keyed_activation.py
python scripts/run_studio_backend_tests.py -q tests/test_studio_asset_query.py tests/test_studio_asset_query_indexed.py tests/test_asset_query_index_recovery.py tests/test_asset_query_windows_signature.py tests/test_asset_index_publication_independent_v2.py
```

The confirmed frontend test deliberately retains one strict expected failure; it is
never counted as passing compatibility. Run it with `--runxfail` to reproduce the
target mismatch. No test uses sleep to manufacture a concurrent interleaving;
startup readiness polling is separate from barrier/event-controlled race tests.

Logs/JUnit, including failed and interrupted attempts, are in
[delivery evidence](evidence/studio-backend-integration-20261026/).
Local paths/username and JUnit hostnames are normalized, outcomes unchanged.
[Source hashes](evidence/studio-backend-integration-20261026/SOURCE_SHA256.txt)
cover all changed application, test and runner files. Final test receipts and
freeze/publication details are recorded in the evidence index. Overlapping runs
must not be added into a unique total.

GraphFlow `gf_read` was used before exploration. This session exposes only
`gf_read/gf_edit/gf_exec/gf_macro`, so the requested old `graphflow_context/plan/index`
cannot be invoked; no successful reindex is claimed.
