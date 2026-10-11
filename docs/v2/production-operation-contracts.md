# M4–M9 production operation contracts

`GET /api/projects/{nid}/studio/production-contracts` is a read-only catalog of
existing owner interfaces and prospective V2 interface requirements. Actual
independent media/timeline commands now have their own original-owner execution
path; see [production execution](production-execution.md). The original
parent router also supplies the existing `/api/v1` alias. This endpoint cannot
dispatch an action, submit a provider result, create a job, start a runtime,
inspect credentials, resolve availability, or grant permission. Action paths
are descriptive metadata; clients must not turn them into execution links.

The parent injects its original `invoke` closure. Its feature flag, actor/project
scope, permission rechecks and project-incarnation guard remain authoritative.
The view requires only `domain.read`, calls the existing workspace
`service.project(nid, scope)` to verify the actual owner, and requires an
explicitly activated `NEUTRAL_STUDIO` entry. It does not activate a project.
Other entries return `409 CREATIVE_STUDIO_ACTIVATION_REQUIRED`. No actor ID,
principal, session token, provider secret or project-incarnation value is
returned. Public scope is limited to the original mode/novel/workspace/project/
storyline/branch IDs; the catalog rejects a project/scope mismatch.

## Versioned response

`app/creative/production_contracts.py` defines strict, bounded Pydantic response
models. Unknown fields and nonconforming catalog/operation/action records are
rejected. No arbitrary executable registration is accepted.

| Field | Meaning |
| --- | --- |
| `contract`, `schema_version` | `studio-production-operation-contracts/1`, integer `1` |
| `project_id`, `scope`, `studio_entry_kind` | Original authorized project/public scope; `NEUTRAL_STUDIO` |
| `advisory_only`, `execution_authority` | Always `true`, `false` |
| `acceptance_sequence` | Exactly M4 → M5 → M6 → M7 → M8 → M9 |
| `acceptance_evidence` | `NOT_EVALUATED_BY_THIS_ENDPOINT`; a GET is not an acceptance run |
| `operations[].capability_status` | `EXISTING_OWNER_CONTRACT` or `RESERVED_INTERFACE`; route presence is not runtime availability |
| `operations[].acceptance_status` | `LOCAL_REQUIRED`; does not erase historical partial evidence or promote a milestone |
| `operations[].execution_available` | Always `false` in this advisory catalog |
| `owner`, `actions` | Actual source owner and existing API metadata; reserved operations have `null` owner and no actions |
| `blocked_reasons` | Remaining Graph media adapters, capability limits and ordered Windows product acceptance boundaries |
| `*_requirements`, `limitations` | Original input/source/version/asset/review obligations and precise gaps |
| `interface_schemas` | Seven bounded, strict JSON Schemas generated only from this module's prospective interface models |
| `interface_contracts` | Per-operation references to source/intent/result/rights/timing/track schema keys; not legacy dispatch payloads |

Each action supplies a local ID, HTTP method, canonical `/api` path, existing
permission name, actual request-body schema reference or `null`, exact owner method and original-host
session requirement. `execution_grant` is always `false`. The `/api/v1` alias
does not weaken original authorization. Input schema names describe original
interfaces; this catalog does not accept those payloads or resolve/import
media-provider modules. Legacy media endpoints retain their conditional
collaboration guards and original egress policies; they must not be used to
bypass trusted packaged V2 DesktopHost authentication.

Each action's bounded `conditions` includes the actual original permission and
source-binding boundary. Missing client CAS on legacy media actions is exposed.
The distinct independent execution API uses `MediaCommand`/`MediaCreate` and
exact job/source CAS without changing legacy request bodies or claiming that
legacy paths gained those checks. Its required Host, original execution/cloud
policies and permissions are revalidated separately from this catalog.

Independent execution also inherits cloud privacy through original immutable
Studio Asset sources and proven legacy parent snapshots, revalidating their
original owner/version/digest. Direct and indirect CreativeDocuments require
original CLOUD_ALLOWED. Traversal is bounded at 64 identity nodes, depth 16 and
200MiB of assets; missing proofs, unsupported old chapter proofs, extra parents,
cycles, stale snapshots or exceeded limits fail closed. Author license/operation
declarations do not grant cloud permission. These are actual execution guards,
not authority created by reading this advisory catalog.

The seven `interface_schemas` keys are `source-snapshot/1`,
`provider-reference/1`, `rights-requirements/1`, `timing-requirements/1`,
`track-requirements/1`, `operation-intent/1` and `media-result/1`.
They describe future bounded interfaces with `additionalProperties: false`:

- A source snapshot has an exact ID/kind/version/SHA256 digest and is explicitly
  reference-only. `ASSET` also requires its original `asset_kind` (`text`,
  `image`, `video` or `audio`); non-asset sources forbid that field. Text is
  included because the original GraphTextAssets owner creates text assets.
  The original owner must revalidate every claimed snapshot before execution.
- A provider reference binds exact route/provider/model and optional workflow
  digests, requires original-owner revalidation and prohibits automatic fallback.
- Rights contain bounded license/consent receipt references; a caller's claim
  is never authority, and verification remains ORIGINAL_OWNER_REQUIRED.
- Timing uses explicit integer timebase/start/duration and bounded playback
  rate. Tracks bind stable IDs/order/type, a source snapshot and timing, with
  bounded gain/mute settings and a required owner adapter. At most eight tracks
  are described; those prospective fields do not implement or authorize a
  mixer. The actual bounded timeline renderer accepts its own closed millisecond
  DTO through the original owner, not this prospective envelope.
- Intent fields have bounded prompt/negative prompt, seed, dimensions/frame
  rate/duration/strength/voice/speech rate/output profile; at most 32 source
  references and eight tracks. No URL, credential or arbitrary executable code
  is accepted by these models. Intent is proposal-only with no authority.
- A result shape binds output ID/kind/version/digest, original source snapshots,
  receipt/job references, rights/timing/tracks and explicit human-review state.
  ORIGINAL_OWNER_REAL requires original job and receipt references; the schema
  cannot manufacture that evidence. It is not a provider-result submission API.

These future interface requirements do not retrofit legacy request models or
claim that every existing owner accepts the strict new envelopes. The catalog
never accepts intent/result/rights payloads and never returns fabricated results.
The `input_schema` field separately identifies the actual legacy/current API
request-body model. GET downloads have no body schema and use `null`; their
exact existing query/path requirements are included in action `conditions`.
Original gaps remain in the operation's requirements and limitations.

## Executable shape consistency, without execution authority

The prospective models now implement cross-field validators, rather than only
publishing field names. These are bounded in-memory shape checks, not a new
job, receipt owner, provider call or source authorization layer. No endpoint
accepts the new envelopes. The seven schema keys and 22 operation IDs remain
unchanged; operation IDs are a closed `Literal` set in contract version 1.

- Identity references reject blank-only strings and control characters without
  normalizing the identity. Sources are indexed by `(kind, id)`, matching the
  original collection namespaces. Duplicate entries and conflicting versions,
  digests or asset kinds for one identity are rejected. Different source kinds
  may retain the same opaque ID. This does not look up an asset or check scope.
- VIDEO and AUDIO tracks reference same-kind ASSET snapshots; CAPTION tracks
  reference CAPTION documents. Non-audio tracks cannot claim a nonzero audio
  gain. Every track snapshot must exactly match a declared source snapshot,
  including version/digest/asset kind. Track IDs and `order` values are unique.
  Arrays may be unsorted, order gaps are valid, the same source may be reused,
  and tracks may overlap. No unavailable multi-track renderer is inferred.
- Timebase is ticks per second as in the original subtitle owner. `Fraction`
  arithmetic checks the declared end tick and limits interval duration to one
  day, using the original OTIO exchange's per-track duration boundary; it
  does not cap absolute placement in seconds to one day. Equivalent
  unreduced rational timebases are accepted. If a parent interval is supplied,
  each track's placement must fit it even when timebases differ. Playback rate
  remains a bounded planning hint; it does not manufacture a measured source
  duration, trim range, audio alignment or renderer support.
- Width and height must be supplied together or both omitted. Empty sources,
  missing provider references and omitted timing remain possible for manual or
  blank proposals. A populated track must still name its exact source.
  These checks do not retrofit stricter bodies onto legacy owner endpoints.
- Results use the same source/track consistency checks. A declared job needs
  its owner receipt digest, ORIGINAL_OWNER_REAL needs both, and a claimed
  ORIGINAL_OWNER_REVIEWED state needs a receipt digest. Manual or structured
  results are not forced to declare a real-model job. Structured derivation
  does require a parent source. The references only constrain shape; they do
  not prove receipt existence, settlement, review, rights or actual execution.
- When declared, MIME type and byte count must appear together and agree with
  the output kind. Timeline/caption MIME names match the existing OTIO and
  SRT/VTT download owners. Text/image outputs cannot carry tracks; audio and
  caption outputs cannot claim other track kinds. These are prospective
  output-shape requirements, not media-byte inspection or current NLE support.

The original anchors are `app/creative/graph_models.py:AssetParameters`,
`app/creative/text_assets.py:GraphTextAssets`,
`app/experimental/subtitle_timeline.py:Timebase`/`Cue`/`_validate`,
`app/experimental/timeline_exchange.py:seconds`/native rational conversion and
its one-day per-track duration limit, plus `VideoAssemblyService.create`'s original
asset-kind/version/hash and measured-trim checks. The new models do not import
those owners. Owner-specific limits (such as ten-minute video-only assembly),
current-source CAS, authentication and actual source-duration checks stay with
the original owners and must be revalidated by any future adapter.

JSON Schema exposes strict fields, the closed operation enum and the new asset
kind field. Pydantic cross-field validators also enforce the consistency rules
above; JSON Schema alone does not encode or establish all of those rules.
Future UI or owner integration must validate the complete envelope and then
revalidate original authority and source facts. Reading schema metadata is
neither that validation nor product acceptance. This phase has not executed
these models or any tests, by the current instruction.

## Existing owners and reserved interfaces

| Milestone / operation IDs | Current owner and operation boundary |
| --- | --- |
| M4 `m4.text.generate` | `CreativeGraphNodeRuntime` preview/dispatch/refresh and original graph approve/reject. One schema-2 local TEXT node, original Broker/JobManager consent/settlement, guarded request digest and GraphTextAssets archival remain authoritative. |
| M5 `m5.image.generate`, `m5.image.edit` | `ImageJobService` create/execute/accept with attempt-token/request/egress guards and validated actual image import. Legacy APIs have no client `expected_version`; their accept action is not V2 graph review/settlement. |
| M5 `m5.image.t2i`, `m5.image.i2i` | Independent `ProductionExecutionService` commands on original `ImageJobService`; explicit preview/queue/execute/read/reconcile/review with trusted Host, exact source/job CAS and private candidates. ComfyUI I2I accepts one image and no width/height; A1111 multi-reference semantics are unverified. Graph adapters remain unconnected. |
| M6 `m6.director.propose`, `m6.director.model` | `DirectorProposalService` structured proposal/review and `DirectorModelCoordinator` original reviewed local-model phases. Source document version/digest and reviewed output remain required. Rule-assisted provenance stays `model_called=false`. |
| M6 `m6.storyboard.derive` | `CreativeService.derive` copies source structure into an editable typed ShotCard draft, binds parent version/digest and calls no model/renderer. Derivation does not itself approve the input or result; missing visual decisions remain blank. |
| M7 `m7.video.plan` | `CreativeService.derive` from STORYBOARD to PRODUCTION/VideoPlan; this is timing/content planning with `model_called=false`. |
| M7 `m7.video.generate` | Original `ScreenplayService` motion-task execute/sync/download owner, source frames/privacy digest/attempt token and validated downloaded video. It has no client version body or unified V2 graph settlement adapter. |
| M7 `m7.video.t2v`, `m7.video.i2v`, `m7.video.v2v` | Independent commands use original VideoProvider capability/route checks and VideoAssemblyService actor/scope/incarnation job persistence, exact source CAS and private review. Refresh only queries an already saved remote task; UNKNOWN is not redispatched. This does not enable Graph media nodes. |
| M8 `m8.audio.speech` | Independent MediaCommand on the original branch/actor AudiobookStore/AudiobookService, original guarded TTS Provider dispatch and exact source/job binding. The legacy chapter path keeps its original remote/experimental source rules. Async incomplete output retains the original remote receipt as UNKNOWN; no audio polling protocol is implemented. |
| M8 `m8.audio.import` | Existing independent workspace manual audio Asset input. Import validates media and saves the asset/version/hash; it does not automatically declare lineage. Source declaration is a separate explicit `annotate` change; the current UI writes `EXTERNAL_IMPORT`. Declaration failure retains the imported asset and retries only the declaration. Import is not generated audio or review approval. |
| M8 `m8.audio.music`, `m8.audio.effects`, `m8.audio.trim` | MUSIC/SFX dispatch through the configured original AudioProvider on the original audio owner. Trim is local-only, one exact audio Asset snapshot and measured range, at most 120 seconds, original FFmpeg to validated WAV. All outputs remain private until explicit review; async audio without completed bytes stays UNKNOWN. |
| M9 `m9.video.assemble` | Existing `VideoAssemblyService` FFmpeg trim/concat preview, 1–30 clips/≤10 minutes, fixed 640×360/24FPS/video-only. Input asset hashes are recorded; post-render source CAS and a review endpoint are absent. |
| M9 `m9.timeline.exchange` | Existing `TimelineExchangeService` bounded OTIO snapshots, source/version/hash rechecks and explicit lossy-conversion acknowledgement. No external-media read, rendering or packaged-media export. Resolve/Premiere round trips remain NOT_RUN. |
| M9 `m9.subtitle.edit` | Existing `SubtitleTimelineService` manual versioned cue create/update/split/merge and SRT/VTT output. ASR, automatic alignment and burn-in are not inferred. |
| M9 `m9.timeline.multitrack` | Versioned original scoped timeline document and explicit VideoAssemblyService local review render: at most 8 VIDEO/AUDIO tracks (4 of each), 30 clips, 10 minutes, 1920×1080/60FPS, bounded video placement/overlay, audio gain/mute/mix and manual captions. Exact source/timeline CAS, private candidate and original AssetLibrary promotion remain required. This is not full NLE, ASR or high-quality master export. |

The finite original graph's seven default node definitions remain unchanged.
`asset_reference` execution remains blocked until an original atomic input-owner
adapter exists. `TaskRequirement` still recognizes its original text/image/video
types, and the graph ModelRouter still authorizes only reviewed local TEXT.
Independent music/audio/trim commands do not widen that execution allowlist.
Existing media `SUCCEEDED` is not renamed to Router `SETTLED`, and an asset ID or
provider URL is not an archival, review or real-model receipt.

The catalog keeps the same closed 22 operation IDs. Its current replacements
describe the nine independent media/trim commands and bounded multitrack owner
as `EXISTING_OWNER_CONTRACT`, yet `execution_available=false` and every
`execution_grant=false` remain fixed in this advisory response. Actual commands
use `studio-production-preview/1`, `studio-production-job/1` and original
`studio-execution-recipe/1` metadata; only their separate guarded routes may
execute. Public job/recipe JSON is a checked owner projection, not fabricated
provider output or milestone evidence.

## Acceptance and source preservation

M5–M9 framework contracts may be developed together. Actual Windows/GPU/model
acceptance still follows the repository milestone gates in order. No operation
in this response has been accepted by reading the catalog. Existing NOT_RUN,
LOCAL_REQUIRED, PARTIAL and BLOCKED evidence remains source-bound, including
original a40df PostgreSQL failures and cancelled/incomplete CI shards.

The V1 manifest, F00 INTEGRATED + 39 PARTIAL accounting, independent-review
BLOCKED status, frozen assets and PoemSeed Local Interop 1.0 semantics remain
unchanged. The eight current-catalog/V2-inventory/receipt files in separate
repair commit `776286f` describe the earlier `5ed1cbee` snapshot. They do not cover
these new execution routes/files. After verification resumes, explicitly
synchronize the current catalog and independent V2 inventory with the original
helpers and source-bound receipts; do not alter the frozen V1 manifest.

This implementation phase deliberately runs no tests, collect-only, typecheck,
build, CI rerun, database operation, Runtime startup or model invocation, per
the current user instruction: **NOT_RUN — USER_DEFERRED**. M4 remains PARTIAL,
M5–M9 remain LOCAL_REQUIRED and QingJian work is paused. Static implementation
review is not acceptance.
