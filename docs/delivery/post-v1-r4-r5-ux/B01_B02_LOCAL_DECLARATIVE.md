# B01/B02 local declarative tools checkpoint

## Status and real user actions

- B01 **EXTEND / PARTIAL**: a real local catalog with eight offline original synthetic examples across planning, character brief, screenplay brief, storyboard brief, review brief and Workflow. Preview type/version/dependencies/author/license/provenance and the actual declarative structure; favorite, bounded JSON import preflight, install/update diff, copy into project-owned IDs, edit the independent copy, compare catalog updates, explicitly overwrite an edited copy, inspect history, restore as a new version, and uninstall without deleting instances.
- Planning copies use the original `PlanningTemplateIn` contract and `PlanningService.TEMPLATES` collection; they are selectable by existing planning tools. Workflow copies create B02 definitions and can run the deterministic closed loop below. Character/screenplay/storyboard/review copies are editable local brief data, **not** direct writes into world/character, screenplay, or media services. They are clearly labeled in UI.
- B02 **EXTEND / PARTIAL**: form-based purpose/role prompt, finite scalar input/output schemas, registered tools and broker model names, required review, steps/time/output/zero-cost bounds; editable nodes and edges; real server DAG validation; version/digest-reviewed test input; explicit queue → execute local nodes → review → reviewed artifact. Original executor node outputs and engine transitions persist and survive reload/restart.
- B02 deterministic execution is **REAL_RUNTIME_VERIFIED** in the tests listed below: shipped original local rule functions actually transform synthetic input. It is not a Mock model. Semantic/model quality is **NOT_RUN**. Role prompts are stored declarations and are not interpreted by local rules.
- The B02 original-executor extension below now supports one explicitly reviewed, bounded local TEXT node through the original author/broker/JobManager path. `CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED` remains fail-closed only on hosts without that composition. Cloud/paid routes and arbitrary adapters remain unavailable. Synthetic protocol execution is verified separately from genuine model quality, which stays **NOT_RUN**.

## Architecture and integration

- Exact features: `template_library_v2`; `declarative_agents_v2` requires explicitly enabled `model_broker_v2`, `agent_team_recipes`, and `media_adapter_registry`. A06 retains its own `author_context_inspector_v2` dependency. No wildcard enablement. The lead owns registration/composition and workbench navigation.
- Factories: `TemplateLibraryService(..., planning=..., enabled_features=...)` and `create_template_library_router`; `DeclarativeAgentsService(..., sources=writing_focus_service, broker=...)` and `create_declarative_agents_router`.
- Routes: `/novels/{nid}/experimental/template-library` and `/novels/{nid}/experimental/declarative-agents`, mounted under both `/api` and `/api/v1`.
- Panels: `TemplateLibraryPanel` / `DeclarativeAgentsPanel`, with captured `ExperimentalClient` and no new shell/CSS/token system. B01 accepts an optional original feature-navigation callback.
- Reused: original R3 planning examples/schema/store, original Workflow recipes, original `V1CapabilityService._workflow_order`, `_advance_workflow_run`, approval/rejection/pause/resume/cancel/timeout algorithms, and A06 read-only actual model registry. No engine algorithm was copied.
- Small shared seam `ff640b5`: optional trusted `workflow_dispatch_guard` immediately before an original node dispatch, outside the node-error catcher. Ordinary V1 hosts with no hook keep their existing behavior. This is optional extension infrastructure, not a claim that a V1 fix was backported.
- `_ScopedOriginalWorkflowHost` supplies only restricted in-memory persistence to that original executor. Each requested action commits the updated run and all original transition receipts atomically in the existing experimental scope store. It cannot call project snapshots, quality gates, agent-task dispatch or arbitrary node configurations. No original public legacy Workflow endpoint can bypass the B02 feature gates because B02 records are not inserted into the legacy public workflow registry.
- Supported graph subset is a rooted DAG, max 16 nodes, with every branch joined before one explicit manual gate and the single terminal reviewed artifact. The original engine executes dependency-ready nodes serially. Conditional routing, implicit output wiring and parallel execution remain outside the subset.

## Data, permission, privacy and recovery

- Existing additive `ExperimentalStore` metadata only; no migration, manuscript change, startup scan, runtime installation or background listener. New collections are scoped catalog/favorites/copies/definitions/runs under the existing experimental schema.
- Every authoring/run/copy is bound to the current actor, project and full branch scope. The routers recheck exact flags and current authority; mutations recheck immediately before commit. The original per-node dispatch hook and approval persistence checks revalidate current actor/scope/feature/source and definition digest/version.
- Input can be explicit text or one currently visible branch-safe chapter, with the displayed expected source version required. Later source changes or revocation make the run stale; historical source/output is withheld from its API projection. No fallback to base manuscript when branch sources are unavailable.
- All derived run material stays `LOCAL_ONLY`. Pure local nodes remain deterministic proposal transformations. An explicit model node uses only the exact reviewed original author/broker execution; registered names and role prompt text cannot grant network, tools or a provider.
- CAS conflicts preserve frontend form input. Later responses are fenced against scope unmount and form/run selection epochs. StrictMode mount performs reads only. No automatic node execution, prompt interpretation, retry or mutation occurs on reopen.
- Explicit cancel, pause, resume and bounded-snapshot retry reuse original state algorithms where applicable. Retry never selects a new model or source. Finished pure node receipts are retained. The finite local work is synchronous; cancellation is observed between actions and current-authority checks, not claimed to preempt arbitrary external code.
- Runtime timeout is the original persisted wall-clock deadline and includes waiting for manual review after explicit execution starts. A next action persists the original timeout result; there is no background timer. No claiming a sleeping process continuously monitors deadlines.
- Template imports accept only strict bounded JSON, max 128,000 bytes, bounded tree depth/counts and typed content. No ZIP decompression, path resolution, screenshot file fetch, SVG/HTML rendering or remote download. Paths/install scripts/unknown keys/code node types are rejected before store changes. `Python` / `JavaScript` / `shell` / dynamic import extensions remain `DENY_ALL`.
- Catalog upgrades do not overwrite any project copies. Copy updates require preview digest and explicit overwrite of edited copies. Revert creates a new version and keeps the old history. The catalog copy and its already-instantiated planning/Agent target are deliberately independent: editing/updating/reverting the library copy never overwrites a target modified in its original editor; a fresh copy creates a fresh target. This distinction is visible beside each linked ID.
- Uninstall affects only the installed local catalog record. Instantiated work and copy history remain. Bundled offline originals remain discoverable after uninstalling an installed override.

## SDK

`app/experimental/declarative_adapter_sdk.py` contains versioned host capability/request/receipt dataclasses, a typed protocol, and a shipped original local-recipe adapter. `examples/declarative_agents/trusted_local_host.py` runs only synthetic offline text. Contract tests exercise actual transformation, bounded input/output, explicit one transient retry, pre/post cancellation, timeout discard and refusal of network/manuscript-apply capabilities.

This SDK is trusted-host-only infrastructure. There is no adapter import string, dynamic loader, package installer or arbitrary HTTP registration. Cooperative timeout/cancellation fences do not constitute an arbitrary-code sandbox. Real third-party/GPU/Windows/provider conformance is **NOT_RUN**.

## Verification receipt

Current local focused commands, using the authorized isolated `../r2-run.sh` harness:

- `python -m pytest tests/test_r5_declarative_templates.py tests/test_r5_declarative_mounted.py tests/test_declarative_workflow_host_seam.py tests/test_r2_workflow_execution.py -q -m 'not postgres_backend_only'`: **54 passed, 41 deselected**, 2026-10-05. Includes original-host compatibility, actual original node execution, SDK, real File persistence, both composed API prefixes, real collaboration roles, exact OFF/V1/dependency gates, current source/graph fences, output limits, timeout/restart, CAS concurrency and atomic late-revocation rollback. The earlier test-only failures (wrong expectation of the planning endpoint envelope; collaboration V1 middleware returning its existing `501 COLLABORATION_ROUTE_NOT_ENABLED`) were corrected to assert actual documented boundaries and rerun; implementation guards were not weakened.
- `pnpm exec vitest run src/experimental/DeclarativeTemplatePanels.test.tsx`: **6 passed**, actual React + captured-authority HTTP contract doubles; not browser/runtime model evidence.
- `pnpm exec tsc -b` and `pnpm run lint`: **PASS**; token guard checked 42 files. A concurrent unrelated literal-type failure was reported to and fixed by the lead. `git diff --check` and owned Python compile checks also passed.
- Real PostgreSQL parameter cases are tagged `postgres_backend_only` and use `TEST_POSTGRES_DATABASE_URL`. **NOT_RUN locally**: no authorized local PostgreSQL endpoint. The hosted gate must execute the real cases with no skips; do not report local deselection as PG pass.
- `frontend/tests/e2e/r4-declarative-templates.spec.ts` is an authored real React + File API journey on the dedicated R4 broker profile, `5182/8022`. No `page.route` or fake API responses. It exercises catalog copy into original planning, uninstall preservation, real Workflow node output/manual review, reload, unchanged manuscript and stale-source rejection, and emits screenshots. **NOT_RUN locally**: known Chromium `EPERM`; no launch retry. `pnpm exec playwright test --config playwright.r4.config.ts --list r4-declarative-templates.spec.ts` successfully discovered the one authored journey without launching a browser. Hosted CI must provide a fresh actual result before a browser PASS is claimed.

## Remaining boundaries / next checkpoint

- Catalog preview is a safe rendered structure. Uploaded/template-provider screenshot assets and remote catalog synchronization are not implemented. Hosted browser screenshots are verification evidence, not auto-downloaded catalog content.
- Character/screenplay/storyboard/review brief integration into those original authoring services is a next increment; no claim that every catalog type has a complete domain-materialization flow.
- Conditional/multi-model/parallel DAG execution, arbitrary JSON Schema, cloud custom-agent dispatch, third-party adapters, remote market/accounts/payments/downloads and code extensions are outside the supported subset. Rooted branch editing and one bound local model node are covered by the extension below.
- Real PG/browser CI results, actual model/GPU, native Windows/IME/screen-reader and user aesthetic acceptance remain separately unverified until measured.
- Lead publishes and records the combined final SHA/Draft PR. No merge, release, deployment, frozen PR37 modification or remote-market publication was performed here.

## B02 original-executor extension, 2026-10-05

This section supersedes the earlier connected-chain/custom-model blocker for
this increment. The wider catalog/domain-materialization boundaries above are
unchanged.

### Implemented supported loop

- A rooted branching DAG now executes through the unchanged original Workflow
  topological engine. It requires one root, one terminal reviewed artifact, one
  manual gate that dominates that artifact, and every branch joined before the
  gate. The engine executes branches serially in topological order. Edges are
  execution dependencies; nodes read the same reviewed input. Conditional
  branches, output-variable wiring and parallel execution are not advertised.
- An explicitly authored `agent_task` node can bind one actual registered local
  TEXT route per run. The original engine's deferred node, trigger, claim and
  complete methods own its state machine. A new trusted coordinator composes
  `AuthorPreparer`, A06 preview/reserve/dispatch/finalize, and the exact original
  `JobManager.start_prepared` object. It contains no provider implementation,
  prompt assembler, independent scheduler, executable loader or model fallback.
- The user saves a graph and reviewed test input, executes to the deferred node,
  previews the exact adapter-facing request plus broker decision, explicitly
  launches it, refreshes the original receipt, then approves the manual review
  node. Each step is a separate visible action. Mounting/reopening the panel is
  read-only. Synthetic routes are labeled protocol-only; literary quality stays
  `NOT_RUN` even after successful execution.
- Purpose and role prompt are visible user-level author instructions. They do
  not replace host instructions or grant tools. Manual text is included in those
  instructions with `source_mode=NONE`, no automatic context, no references and
  no manuscript tail. A current chapter is required as the original author-job
  version/permission anchor but its text is not included in this mode. Explicit
  chapter input uses the actual branch-safe source and saved/version-checked
  selection; unsupported branch-author combinations fail closed.
- Model dispatch is restricted to `LOCAL_ONLY`, known zero reservation and no
  automatic retry. Existing original model registration and A06 pricing/budget
  decisions still apply. A real local route without a current known zero price
  cannot dispatch. Cloud, paid reservations, multiple model nodes and unknown
  adapters are rejected; selecting a route does not install/enable anything.

### Bounds, receipts and recovery

The host first commits the original Workflow claim, then reserves the original
A06 ledger, then starts the prepared original job once. A durable execution ID
prevents a replacement after any uncertain admission. A missing process/job or
lost start/settlement receipt remains `UNKNOWN_NO_AUTOMATIC_REPLAY`; its original
ledger hold remains available to the existing broker recovery UI. Replaying the
same dispatch request returns that original binding and never executes again.
An already-admitted model run cannot use local retry. A new reviewed run is an
explicit new request and remains subject to the original unresolved-budget
policy.

The optional original JobManager fields `generation_max_output_bytes` and
`generation_deadline` are trusted server fields, ignored by ordinary generate
payloads. The coordinator binds them to the persisted Workflow run. Admission
validates them; actual send, every streamed delta and completion recheck them.
UTF-8 bytes are counted; full completion text is checked independently rather
than added to streamed text a second time. A bound failure discards incomplete
output, sets a truthful failure code and cooperatively signals cancellation.
The original provider may still be blocked until it cooperates; no forced
preemption or background wall-clock cancellation is claimed. A06 retains its
original conservative upstream settlement semantics.

Current graph/source/anchor, actor/scope, exact author request, route identity,
price and budget are checked before dispatch. The original author authorization
must still be present and valid before completed output enters Workflow review;
process restart does not recreate that closure or silently accept old output.
A changed source hides historical input, model preview and node output. Explicit
cancellation makes the durable run non-dispatchable before cooperatively
stopping its original job. The existing broker cancellation/reconciliation
recovery remains available when generation features are disabled.

`declarative_agent` is a trusted persisted original generation origin, requiring
B02 + A06 + author flags. Both normal and persisted-reload legacy generation
acceptance reject it with `DECLARATIVE_DRAFT_ONLY`. Manual Workflow approval
creates reviewed draft material only, with original job and request provenance;
it never writes manuscript or Canon.

The SDK adds an opaque bound-model receipt and trusted-host protocol documenting
these obligations. `run_trusted_local` retains its no-network pure-adapter
contract; no SDK import string or third-party installation endpoint was added.

### Verification for this increment

Actual local results are recorded in the accompanying completion receipt. New
contracts are `tests/test_r5_declarative_model.py` (real composed File / opted-in
PG, both API prefixes) and `tests/test_r5_declarative_job_bounds.py` (trusted
JobManager bounds, persistence and acceptance). They cover actual original
synthetic execution, exact NONE/selection input, one ledger/job under repeated
and concurrent admission, source/budget drift, unknown admission, restart,
output limits, cancellation, rooted branches and review dominance. The React
suite now covers explicit exact-model approval, disabled in-flight pause,
unknown receipts and late responses after a captured scope changes.

`frontend/tests/e2e/r4-declarative-model.spec.ts` is a real React + File API
journey on the existing isolated broker profile. It contains no `page.route`
response mock and calls only the shipped synthetic protocol provider. It takes
exact-request and reviewed-output screenshots, reloads durable results and
verifies unchanged manuscript and legacy-apply rejection. Browser launch is
**NOT_RUN locally** because of the established Chromium EPERM restriction; the
parent must obtain hosted execution/screenshots. Real PostgreSQL is also
**NOT_RUN locally**; tagged cases are collected for the hosted PG gate. Genuine
model/GPU quality, Windows, IME and user visual acceptance remain **NOT_RUN**.
