# Execution, data, and single-authority contracts (V2)

Version: `ENG-2026.10.19-r1`. This document records the contracts that already own a domain in
the tree at `a072cf90`. It is a **constraint document for future work**, not a new API.

## 1. Single authoritative owner map (do not create a second one)

| Domain | Authority (source of truth) | Storage / schema owner | Rules that must keep holding |
| --- | --- | --- | --- |
| Novel, chapters, versions, V1.X records | Existing V1.X services/repositories | `database/migrations/001_initial.sql` + V1.X repository code; File backend mirrors it | V1 manifest, protected records, RC1 history unchanged |
| Project / scope / membership / actor | Existing project + collaboration scope owners | migrations `012`, `014`, `015`; `app/services/collaboration_scope_service.py` | Project incarnation, scope, actor and branch authority are checked on every write |
| Creative documents (screenplay, director notes, storyboard, prompts, drafts) | `app/creative/service.py::CreativeService` | Creative document store; one versioned row with retained history | Every write uses expected `{version, digest}` CAS and appends a revision; no side-channel metadata writes |
| Assets (image/audio/video/3D/reference) | `app/services/asset_library_service.py` (+ `app/asset_lifecycle_api.py`) | Immutable asset bytes + CAS metadata + revisions | Content-addressed, immutable bytes; derived artifacts pin an exact source version/digest; soft delete only |
| Asset relationships / lineage | `app/creative/workspace_relationships.py`, experimental lineage (A09) | Relationship records (from/to, scope, target version/digest) | Relationship is a fact, not an execution ticket; no cross-project reads |
| Creative Graph (nodes, edges, layout) | `app/creative/graph.py`, `graph_models.py`, `graph_api.py` | Graph snapshot/document owner; schema 1 unchanged | Typed ports; cycles prohibited by default; node deletion never deletes reviewed assets |
| Graph execution / model boundary | `app/creative/graph_execution.py`, `graph_media_execution.py`, `ai_execution.py` | WorkflowRun + JobManager state | Original WorkflowRun owns dependencies/review; one model node per selected run; review gate required |
| Jobs / task queue | `app/jobs.py::JobManager` (single queue) | Job records; terminal hook + ledger settlement | No parallel queue may be introduced; a successful provider response alone is not a completion |
| Review / approval | `app/review.py`, `app/services/finding_review_service.py`, `app/services/import_review_service.py` | Review records bound to exact output digest | Human review permission (`domain.review`), exact source + output digest; review never mutates manuscript automatically |
| Model Center / providers / local discovery | `app/model_center/*` + provider registry | Provider/model configuration records | Read-only discovery by default; detection never enables execution; provider runtime snapshot has no execution authority |
| Model broker / routing / budget | `app/experimental/model_broker.py` (+ `model_broker_api.py`) | Broker preview/admission/ledger receipts | Exact route selection, price/license/admission checks; fail closed on ambiguity |
| Timeline / NLE | `app/studio_timeline_edit.py`, `studio_timeline_schema.py`, `studio_timeline_render.py`, `timeline_transfer.py` | Timeline document + render receipts | Real FFmpeg execution only; OTIO/SRT/VTT loss must be reported, never hidden |
| Export / delivery | `app/export_job_service.py`, `export_snapshot_authority.py`, `export_resource_snapshot.py` | Export manifest + snapshot authority | Export binds exact source versions; missing/relinked resources are explicit |
| Migrations | `database/migrations/*.sql` | Ordered migrations 001–020 (current) | Append-only; no ad-hoc `CREATE TABLE` in feature code; downgrade/backup documented |
| Experimental capability registry | `app/experimental/capabilities.py` + `flags.py` | Server-owned flags and dependencies | No wildcard enable; clients cannot invent capabilities; availability computed server-side |
| Host identity / packaging | `app/packaging/*`, `app/runtime.py` | Host profile / token binding | Host authority binds registry/bootstrap instance, not a bare token string |
| Local interop | `app/local_interop/*`, `contracts/local-interop/v1/*` | Stable v1 contracts | Never alter stable IDs; versioned extensions only |

Forbidden: a second Project/Asset/Job/Provider/Model Center/Timeline authority, a second scheduler,
a second asset filesystem layout, or a "generic write API" that bypasses an owner's CAS.

## 2. DTO / schema rules

- Server models are explicit Pydantic `StrictModel` (extra fields rejected) in the owning module;
  clients cannot submit endpoints, credentials, executable paths or provider results.
- Versioned envelopes carry an explicit `schema_version` (for example `creative-graph-model/1`)
  and stay backward compatible; new required fields are a new version, not a silent change.
- Writes to versioned owners use `expected_version` (+ digest where the owner provides one, e.g.
  `CreativeService` expected `{version, digest}`). A stale write returns a conflict; it never
  overwrites newer content.
- IDs are server-generated opaque strings; slugs are presentation aliases, not identity. A deleted
  and recreated project keeps distinct incarnation so late jobs cannot attach to a same-slug
  replacement.
- Timestamps are UTC ISO-8601; durations are integer seconds/milliseconds explicitly named.
- Unknown fields in stored production documents are preserved where the owner is append-only
  history; lossy transformations must report what was dropped.

## 3. Graph contract

- Ports and node definitions are typed and server-reported. Graph schema 1 is unchanged; adding a
  model node (e.g. `text_generate`) promotes the graph to schema 2 and requires the explicit
  `ai_execution_v2` (plus dependencies) opt-in.
- At most one model node per admitted run; its selected output path must include an explicit
  human-review node; a model selection without the review gate is not executable.
- Invalid edges, type mismatches, disconnected required inputs and default cycles are rejected
  before dispatch.
- Node deletion does not delete already-reviewed assets. Removing a node/view never pretends prior
  outputs succeeded differently.
- Asset version changes invalidate dependent cached results (stale) rather than silently reusing
  old input; cache keys include exact source version/digest.
- Local/manual outputs cannot forge `MODEL_PROPOSAL` provenance.

## 4. Job / review / timeline state machines

JobManager is the single queue. Observed statuses and terminal sets at this SHA include
`QUEUED`, `PREPARING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED` and the
acceptance-family statuses `ACCEPTED`/`ACCEPTING`/`ACCEPTANCE_UNCERTAIN`/`REJECTED`;
`UNKNOWN_UPSTREAM` / generation settlement recovery are explicit uncertainty states.
`transient_fields` (prepared invocations, guards) are never reconstructed from persisted JSON
after restart.

Rules:

1. **Claim before work.** A short transaction records the claim and one job ID before enqueueing;
   model I/O never runs inside the graph scope transaction, and the existing scope→project lock
   order is retained.
2. **Terminal hook + settlement before output.** A completed provider call is insufficient: the job
   must reach a durable terminal hook and the ledger must settle (known zero cost for local routes)
   before output can reach review.
3. **UNKNOWN / no automatic replay.** Missing or ambiguous admission/upstream state is retained as
   UNKNOWN with the hold intact; nothing is retried automatically where a duplicate paid call is
   possible. A stored `model_called: false` while a job is admitted/unknown is not proof that no
   call ran.
4. **Cancellation is cooperative.** A blocked external process may finish later; its late output
   cannot become an accepted draft. Cancel transitions are persisted before acknowledgement.
5. **Idempotency.** Retries must carry the same idempotency key and reuse the original job/result
   when the outcome is known; a new retry is an explicit new job linked to the original.
6. **Recovery is explicit.** Restart recovery either marks recoverable work FAILED with a recovery
   code or keeps it UNKNOWN for manual reconciliation; it never replays silently.
7. **Review** binds exact source versions + output digest; approval does not apply text to
   manuscript/canon/assets and generic generation URLs cannot expose or apply graph jobs.
8. **Timeline** edits are versioned documents; render/export jobs are ordinary jobs and must leave
   artifacts verifiable by ffprobe plus hashes. Missing/offline media is an explicit state.

## 5. Atomicity, concurrency, and cross-module writes

- File backend: mutations that span records use the workspace mutation coordinator
  (`app/repositories/file/mutation_coordinator.py`) and atomic writes (`app/atomic_write*` /
  Windows atomic-write handling) so a crash cannot leave a half-written project.
- PostgreSQL: multi-row writes stay inside one transaction; locks follow the established
  scope→project→record order to avoid deadlocks.
- Cross-module flows are choreographed by IDs and explicit receipts, not by reaching into another
  owner's files. An asset is published by the asset owner; a job by the job owner.
- Deployment/backup/restore: `scripts/backup.ps1`, `scripts/restore.ps1`,
  `scripts/migrate.ps1`, `docs/backup_restore.md` are the operational owners; tests must prove
  restart readback and restore, not only write success.

## 6. Error layering and observability

- HTTP 4xx/5xx carry a stable machine `code` (e.g. `EXPERIMENTAL_FEATURE_DISABLED`,
  `COMIC_PIXEL_LIMIT_16000000`, `GENERATION_SETTLEMENT_RECOVERY_REQUIRED`). Never return raw
  exception text, absolute user paths, tokens or provider payloads.
- Errors distinguish: validation, permission/scope, stale CAS, missing capability, disabled feature,
  resource/budget, uncertain upstream, environment unavailable, and internal failure.
- Durable receipts record: actor/scope, exact input versions/digests, route/model/runtime,
  timestamps, bounded resource facts, output digests and terminal state. Receipts are evidence, not
  a second source of truth for content.
- Logs are redacted and bounded; provider API keys never enter logs, commits or receipts.
- Diagnostics must say what is NOT proven (e.g. `inference_status: NOT_RUN`,
  `windows_acceptance: NOT_RUN`, `COMPONENT_FOUND_NOT_VERIFIED`).

## 7. Capability flag discipline

- All experimental surfaces are server-owned and default-off; `EXPERIMENTAL_FEATURES` cannot be
  wildcard-expanded, and package dependencies are enforced by `flags.py`.
- Enabling a surface requires its declared dependencies; disabling any dependency disables the
  surface transitively.
- A feature that is registered but not integrated must report `PENDING` / disabled reason rather
  than pretending availability. `INTEGRATED` in the capability registry still means
  contract-level integration, not product acceptance.
- V1 acceptance mode (`V1_ACCEPTANCE_MODE=1`) overrides all V2 flags off.
