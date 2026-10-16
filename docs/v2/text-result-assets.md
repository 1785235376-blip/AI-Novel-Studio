# M4-B: private graph text-result assets

This document describes the implemented `creative-graph-text-asset/1` contract.
It extends the local-text execution slice in [ai-execution.md](ai-execution.md)
with two-phase archival and review projection. It is an implementation reference,
not an independent security audit or evidence that a historical **BLOCKED**
acceptance decision has been resolved. Verification commands, retained failures
and acceptance status belong in `MILESTONE_M4B_REPORT.md`.

Real-model inference and quality verification remain **NOT_RUN**. API providers
remain **RESERVED**, without execution or cloud fallback. LM Studio remains
blocked by `LMSTUDIO_LOCALITY_UNVERIFIED` before transport; its protocol codecs
do not establish an executable route. See
[model-provider-contracts.md](model-provider-contracts.md).

## Scope and unchanged user workflow

The current UI includes successful-result storage in the existing explicit
model-dispatch action. After the server advertises `result_storage`,
`GraphModelExecutionPanel` automatically sends `archive_result: true`. Its
existing dispatch preview discloses that a successful result will be stored as
a private, pending-review text asset and that review does not write manuscript
text. There is no additional archive button, storage checkbox or required user
action. The existing exact-input/model consent and, when applicable, synthetic
adapter consent still precede dispatch. The existing human-review action still
decides whether the proposal is approved or rejected.

HTTP compatibility is deliberately different from that UI default:

- `archive_result` is optional and defaults to `false` in `ModelDispatch`.
  Older clients that omit it retain the original unarchived execution contract.
- The server accepts actual JSON booleans only. Strings, numbers, null, arrays
  and objects are invalid. The current typed frontend client supports omission
  or the literal `true`; it does not expose an explicit-false UI control.
- Archival intent is recorded with the original job admission. Repeating a
  dispatch reads the already-admitted run; it does not opt an old job into
  archival, change its recorded intent or launch another job.
- All four existing flags remain required:
  `ai_execution_v2`, `narrative_production_v2`, `model_broker_v2` and
  `author_context_inspector_v2`. Their default-off and V1 acceptance override
  behavior is unchanged.

Archival neither publishes the result nor applies it. `actor_private: true`,
`applied: false`, `quality_verification: "NOT_RUN"` and
`automatic_model_retry: false` are explicit response invariants. Approval retains
the same private owner. There are no manuscript, chapter, Canon or model-catalog
writes, and no new model installation, launch, credential or paid-provider path.

## Two phases, with original owners

`GraphTextAssets` is a bounded reconciliation adapter. It introduces no durable
queue, asset database, review state machine or execution authority. Durable
state remains with the original graph/scope store, `WorkflowRun`, `JobManager`,
`ModelBroker` ledger and `AssetLibraryService`.

### Phase 1: completed result to private DRAFT asset

1. Explicit dispatch records one original job identity and a
   `model_asset_intent` on the original graph run. Intent contains the contract,
   job ID, admission `source_run_version` and reviewed preview digest.
2. Original worker execution and broker terminal accounting complete. A provider
   response or a text string alone cannot authorize archival. The in-memory job
   must match its persisted original record, have `status`, `execution_outcome`
   and `terminal_hook_status` all equal to `COMPLETED`, and retain the expected
   operation, origin, provider/model and graph bindings. The matching original
   reservation must belong to the actor/job, be dispatched and be `SETTLED` at
   `actual_microusd: 0` with `job_status: COMPLETED`.
3. An authorized single-run read or existing model refresh checks current source,
   route and storage authority. While the workflow is still `RUNNING`, it may
   call the original asset owner's server-only `create_text_result` helper.
   The first asset metadata commit contains complete source/model metadata,
   private ownership and a `DRAFT` review record at asset version **1**.
4. Only after that asset exists and its original bytes are verified may the
   original workflow accept the model-node completion and expose its
   `MODEL_PROPOSAL` at the existing human-review boundary.

The stable idempotency key is derived from the contract, project incarnation,
scope, actor, run and recorded intent. It identifies the same archived output
across retries; it is not a second execution key or a client-supplied asset ID.
The generated filename is `graph-{run_id}.txt`, with `kind: "text"` and
`media_type: "text/plain"`.

### Phase 2: original review to asset review metadata

The existing approve/reject endpoint first verifies the current archive and
then invokes the original workflow action with its run-version and exact
review-output digest checks. The workflow decision is the authority. Its
durable history supplies a receipt containing run ID/version, review node,
reviewer/time, raw output digest and reviewed-output digest.

`AssetLibraryService.review_text_result` projects that decision with an
asset-version compare-and-swap (CAS). In the normal flow the same asset changes
from `DRAFT` v1 to **APPROVED v2** or **REJECTED v2**. It records the prior DRAFT
version and, for approval, `approved_at`. Approval is projected when the original
run is `SUCCEEDED` with `reviewed: true`; an intermediate approval in a run with
more work is not itself that terminal decision. An exact repeated projection is
idempotent, including a retry using the immediately preceding asset version;
a different final decision is not a new review transition. Approval does not
remove private ownership, and `promote_owned` cannot publish a text-result asset.

These versions must not be confused:

- The run's `version` is the original workflow CAS version used by dispatch,
  refresh and review requests.
- `source.source_run_version` identifies the original archival admission; it
  does not change to the later review version.
- `asset_output.version` is the original asset owner's metadata/review version.
  The v1-to-v2 transition does **not** edit text content or create a second text
  revision. M4-B provides no text-content edit/version-history API.
- `asset_output.sha256` and `source.output_digest` hash the exact UTF-8 result
  bytes. `reviewed_output_digest` binds the original review context and draft;
  it is a different digest and must not be substituted for the byte hash.

## HTTP field contract

Both mounted aliases use the same behavior: `/api` and `/api/v1`, followed by
`/projects/{project}/studio`. Existing session, branch, actor, permission and
current host-authority checks apply. Responses use the existing private
`Cache-Control: no-store` and `X-Content-Type-Options: nosniff` route wrapper.

| Endpoint suffix | Request and result |
| --- | --- |
| GET `/graphs/model-capabilities` | Adds `result_storage: {contract: "creative-graph-text-asset/1", available: true, owner: "AssetLibraryService", actor_private: true, automatic_model_retry: false}`. This advertises the feature, not available quota or a successful archive. Requires `domain.read`. |
| POST `/graph-runs/{run}/model/dispatch` | `{expected_version, reviewed_preview_digest, archive_result?}`. Existing exact preview and one-job admission remain authoritative. Archival opt-in normally returns `asset_output.state: "PENDING"`; dispatch does not wait for archival. Requires `domain.write`. |
| GET `/graph-runs/{run}` | Existing authorized run read, with at most one eligible reconciliation attempt. May archive a completed result or finish review projection. Requires `domain.read`; its archival side effects are bounded to the previously recorded intent/decision. |
| POST `/graph-runs/{run}/model/refresh` | `{expected_version}` uses the existing refresh operation and current run CAS. May reconcile the same result immediately, without a new model call. Requires `domain.write`. |
| POST `/graph-runs/{run}/approve` or `/reject` | `{expected_version, node_id, reviewed_output_digest}` uses the existing original review action; no asset ID, provider result or proposed review state is accepted. Requires `domain.review`. |
| GET `/graphs/{graph}/runs` | Lists with reconciliation disabled. It is not a bulk archival trigger and must not be treated as proof of a current archive. Open the individual run for its reconciled result. |

For opted-in runs, `asset_output` has the common fields `contract`, `state`,
`asset_id`, `version`, `actor_private`, `applied`, `quality_verification` and
`automatic_model_retry`.

| `state` | Meaning and additional fields |
| --- | --- |
| `PENDING` | No archive is being asserted by this response, including an in-flight job or non-reconciling read. `asset_id` and `version` are null. It is not proof that no stored asset exists. |
| `INCOMPLETE` | Archival/accounting/current-source reconciliation could not establish usable output. IDs/versions are null; `reason` is a bounded code, currently `ARCHIVE_RECONCILIATION_REQUIRED` or `TERMINAL_ACCOUNTING_RECONCILIATION_REQUIRED`. |
| `NO_ACCEPTED_RESULT` | The run is failed or cancelled. IDs/versions are null. This is not a deletion receipt for any earlier private storage. |
| `DRAFT`, `APPROVED`, `REJECTED` | Supplies the asset ID/version, `sha256`, byte `size`, `kind`, `media_type`, `created_at`, `updated_at`, `provider_id`, `model_id`, `parameters` and `source`. Rejection preserves the private archival receipt while the original run view hides draft text. |

`parameters` contains `max_output_tokens`, `temperature: 0`, `synthetic` and
`quality_verification: "NOT_RUN"`. `source` contains:

- `schema_version: 1` and `contract: "creative-graph-text-asset/1"`
- `graph_id`, `graph_version`, `graph_digest`, `run_id`, `source_run_version`
- `model_node_id`, `job_id`, `input_digest`, `output_digest`, `preview_digest`
- `produced_at`, taken from the original completed-settlement ledger timestamp.
  JobManager notification `updated_at` can advance after terminal accounting; it
  is still checked for current durable/in-memory consistency but is not an
  immutable asset-origin timestamp.

The asset receipt carries provenance and status, not a second text body or a
download URL. The original run's authorized review/node outputs remain the text
surface. Raw private asset binding, origin and review fields are stripped by the
legacy asset public projection. The generic/manual Studio asset views do not
discover these actor-private text results. No new text-asset endpoint is added.

## Recovery, restart and failure boundaries

Recovery is request-driven. There is no background retry queue or guarantee of
progress while nobody reads the run. A normal eligible read makes at most one
attempt. After a caught reconciliation failure, subsequent reads of that same
project/scope/actor/incarnation/run are suppressed for **two seconds**. The
in-memory cooldown map holds at most **100 keys** and is reset on process
restart. This limits immediate repeat attempts, not the lifetime number of
attempts. Existing explicit refresh can retry immediately and is not governed
by the read cooldown. There is no model replay in either path.

The two phases intentionally do not form a cross-owner atomic transaction:

| Interruption or failure | Result and bounded recovery |
| --- | --- |
| Asset write fails before metadata commits | The caught failure removes the operation's unindexed binary when no metadata exists. The original completed job remains durable. A later eligible read/refresh may create the one asset. |
| Metadata commits, then the caller observes a write error | The committed asset/bytes are retained. The same idempotency key finds it on retry, without another model call or a second asset. |
| Asset commits, then workflow completion fails | The run can remain `RUNNING` with a private DRAFT v1 already stored. Reopen/read/refresh verifies that asset and completes the original workflow boundary. |
| Original approve/reject commits, then asset review projection fails | The action can return an error although the workflow decision is durable. A later individual run read projects that saved decision once to the same asset. Repeating the model call is neither necessary nor allowed. |
| Process restarts after durable completion and settlement | Reconciliation can use the persisted original job and ledger with current authorization. It does not reconstruct `request_authorization`, a prepared invocation, worker closure or historical dispatch consent. |
| Completion, admission or terminal accounting is missing/uncertain | No successful archive is inferred. Unknown admission retains the original job identity/unknown-no-replay receipt. Incomplete terminal accounting leaves the result masked; this adapter does not repair the ledger or rerun the worker. |
| Asset missing/deleted/corrupt after workflow advancement | Review/read fails closed. Creation is allowed only while the run is `RUNNING`; the adapter does not silently replace a missing archive after advancement, resurrect a deleted asset or rewrite corrupt bytes. |
| Quota, low-space, current-source or route checks fail | The durable job may remain available for later authorized reconciliation, but recovery requires the underlying condition to become valid. The adapter does not delete other data or choose a different route. |

The write cleanup above describes handled exceptions, not a claim of complete
filesystem garbage collection after arbitrary process termination. There is no
new orphan scanner or cross-store rollback mechanism. Likewise, a cancelled run
does not become approved and this adapter does not delete an already-stored
private DRAFT as part of cancellation.

On a caught read-reconciliation failure, the response has `stale: true`,
`review: null`, null output for every node, null model preview and an
`INCOMPLETE` receipt. Internal exception text and stored text are not included
in that receipt. Authorization failures still deny the request rather than
being converted into successful reconciliation responses. Explicit refresh and
review may return their existing errors instead of the read's masked response;
callers must reread before assuming which original-owner commit completed.

## Current authority, provenance and storage bounds

Every usable projection depends on current authority as well as durable facts:

- Run and asset access are fenced by the exact actor, project, branch/scope and
  actual project incarnation. Recreating a project with the same public slug
  does not adopt its old run or asset. File ownership uses the existing
  incarnation marker; PostgreSQL uses the project owner's UUID.
- Current graph version/digest, node/input/preview bindings, original job
  identity and source receipt must still agree. Current route registration,
  enablement, fingerprint, locality and required license evidence are checked;
  stored success alone does not authorize reading after those facts change.
- The source lease keeps an unchanged snapshot in the original raw scope owner,
  followed by the existing asset-to-project lease. It rejects nested/reversed
  acquisition and source mutations. Model work is not performed under this
  archival persistence lease, and slow route observations occur before it.
- Guards are rechecked at asset commit and review boundaries. Permission,
  session, host, feature or source revocation cannot be replaced with stored
  consent. Asset bytes are verified for size/hash and against the original job
  output. Provenance changes, ambiguous identity or a deleted asset are errors.
- New archival text is nonempty UTF-8 without NUL bytes, at most **32,000 bytes**,
  and must satisfy the existing model draft port's **8,000-character** limit.
  Source/model metadata is bounded to **16,000 encoded bytes**. Graph execution
  retains its 1–2,048 output-token and at-most-180-second invocation bounds.
- Admission uses the existing **1,000-asset / 512 MiB** quota for the exact bound
  project scope. Its server-only aggregate includes retained/deleted assets and
  other actors' private or currently feature-hidden bytes in that scope; such
  bytes cannot disappear from admission merely because the requester cannot
  list them. Other scopes, old incarnations and legacy unbound assets remain
  separate.
- Existing disk admission preserves a **64 MiB** safety reserve, checks incoming
  bytes and rechecks availability at commit. It is an observation, not a disk
  reservation or an automatic cleanup facility. Original graph bounds remain
  25 graphs, 100 runs, 20 history entries, 2,000,000 bytes per record and
  8,000,000 bytes per graph/run scope collection. Unchanged receipt reads do not
  consume additional run history.

## Verification map and limitations

The implementation references are `app/creative/text_assets.py`,
`ai_execution.py`, `graph.py`, `graph_api.py`, `project_store.py` and the original
`app/services/asset_library_service.py`. UI behavior and receipt validation live
in `GraphModelExecutionPanel`, `GraphTextAssetSummary` and the Studio graph
text-asset types/client contract.

`tests/test_v2_graph_text_assets.py` covers original-owner DRAFT/approval,
completed-job restart without reconstructed closures, archive write failures
before/after metadata commit, both inter-owner commit gaps, rejection,
corruption masking, stale workflow CAS, commit-time revocation, private views
and incomplete terminal accounting. `tests/test_v2_graph_text_assets_api.py`
covers mounted dispatch/read/review, strict booleans, private response headers,
revocation and masked storage failure followed by original refresh. The focused
asset-owner, frontend contract/component and browser-fixture tests are separate
evidence surfaces; merely having a test does not establish that its latest run
passed or that a browser launched.

This document does not certify Windows/GPU behavior, real-model quality,
independent security review, a hosted CI run, or all failure interleavings.
Reconciliation remains dependent on valid original durable owners and a current
authorized route/source. Text editing, asset publication/export UI, automatic
ledger repair, cloud execution and manuscript/Canon application are outside
this bounded M4-B contract.
