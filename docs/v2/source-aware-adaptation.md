# Source-aware screenplay adaptation (TEXT-13, bounded first slice)

Status: **PARTIAL**. One saved chapter, or an exact substring selected from that
saved chapter, may become a private model proposal. Multi-chapter ranges and
AssetLibrary archival are follow-on work; generated proposal storage is not
misrepresented as the Asset system.

## Existing owners

CreativeProjectStore owns the proposal and the adopted CreativeDocument.
AuthorPreparer supplies the original scoped author request; ModelRouter and
ModelBroker select and reserve the explicitly reviewed, licensed, zero-cost
local text route; the original JobManager performs one bounded execution.
Generation repositories retain the typed proposal/incarnation binding. There
is no additional provider registry, queue, graph, manuscript or asset owner.

A new `CREATIVE_ADAPTATION_V1` binding is distinct from a Creative Graph run.
It must never be represented as a fabricated graph/run/node provenance tuple.

## API and lifecycle

Both existing `/api` and `/api/v1` novel experimental Creative routers expose:

- `GET/POST adaptation-proposals`: private list or explicit saved-source creation.
- `GET adaptation-proposals/model-routes`: original verified local route catalog.
- `GET adaptation-proposals/{id}`: current source/actor-bound receipt.
- `POST .../{id}/preview`: exact route and source preview, no inference.
- `POST .../{id}/dispatch`: exact version/digest confirmation; one original job.
- `POST .../{id}/refresh`: observe original job and settled zero-cost receipt.
- `POST .../{id}/review`: human-edited scenes/report create one separate screenplay.
- `POST .../{id}/cancel`: durable cancellation before best-effort worker cancellation.

All proposal routes require the existing host session, actor/project scope and
current domain authority. Capabilities identify a missing trusted Host session
without disabling ordinary manual Creative editing. Local credentials remain
in the existing explicit session owner, not a new authentication flow. Feature flags remain default-off. The browser never
selects synthetic routes; contracts must opt into synthetic transport explicitly.
Only exact LocalTextAdapter routes or explicitly allowed test routes are admitted.
API/cloud adapters, tools and silent cloud fallback are not introduced.

Preview shows the actual complete prompt, parameters, source and route. Selection
uses `SELECTION_ONLY` with automatic context, style and plan references disabled.
Execution has the original finite 180-second deadline and a 128,000-byte output
bound. Storage headroom is checked before reservation/inference using serialized
proposal/history bytes; prompts are not silently truncated.

## Output and review

Strict JSON contains stable-ID scenes plus a linked difference report. Change
kinds are scene splitting, visualization, dialogue, omission and inference.
Non-inference changes quote exact substrings of the selected source. Duplicate
keys/IDs, unknown fields, nonfinite values, invalid scene links and foreign quotes
are rejected. The host, not model output, supplies chapter links.

Valid output still requires human quality review. The reviewer can edit scene
headings/actions/dialogue and report notes, then explicitly adopt the current
proposal version/output digest. Adoption creates a SCREENPLAY v1 and updates the
proposal in the same Creative store transaction. The source novel, chapter and
Canon are unchanged. Provenance records model identity, actual prompt/parameters,
route/request/output digests, original job/reservation and the reviewed report.
The report describes this adopted version; later screenplay edits are not
silently certified as source-faithful.

## Failure, privacy and recovery boundaries

Authority, project incarnation, source version/digest/privacy, route identity,
license, budget version, job identity, callback identity and bounds are rechecked
at admission/dispatch/result/review. Slow model calls do not hold store transactions.
Generic generation acceptance/stream endpoints hide these private proposal jobs;
Broker observation is metadata-only. A cancellation, late callback, stale source
or unconfirmed settlement cannot adopt a screenplay.

SETTLING is pending, not a discarded success; refresh observes the published job
once before reading settlement. Pending refresh does not consume proposal history.
A missing live execution authority after restart currently hides output and marks
its receipt unavailable. No automatic model replay is allowed. Durable, idempotent
AssetLibrary archival/recovery is explicitly still missing in this first slice.

The panel preserves unsaved review edits through stage changes and uncertain
writes, requires explicit discard, and drops late identity callbacks. Optional
model flags being off do not prevent a valid private draft from reopening.

## Verification interpretation

Mock/contract execution exercises the real router, reservation, JobManager and
File/PostgreSQL stores with a synthetic transport. It is not real-model inference
or an adaptation-quality assessment. Browser execution is separately tracked;
local Chromium remains blocked by the previously recorded OS launch error.
See `MILESTONE_M4_ADAPTATION_REPORT.md` for exact source-bound results and inherited
hosted failures. The historical independent security review remains BLOCKED.

### Host request binding

Every private adaptation route captures the same original Host authority used by
Creative Graph. Token validity alone is insufficient: the current registry,
binding generation and session principal must remain the captured identity at
admission, return, provider completion and review. Same-token re-registration
invalidates the old operation. Forwarded/non-loopback or wrong-Origin requests
and nonpackaged collaboration-only sessions cannot establish Host authority.
Capabilities expose `HOST_SESSION_REQUIRED` without mounting private reads when
that provenance is unavailable; manual Creative editing remains usable.
