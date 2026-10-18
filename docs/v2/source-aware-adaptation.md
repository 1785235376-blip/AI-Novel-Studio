# Source-aware screenplay adaptation (TEXT-13, bounded chapter/archive slices)

Status: **PARTIAL**. One saved chapter or its exact saved substring, and a bounded
ordered selection of 2–16 complete saved chapters, may become a private model
proposal and an automatically archived private TextAsset. Larger inputs,
per-chapter partial selections in the ordered mode, cross-chapter merged scenes,
and full real-model quality acceptance remain follow-on work. The original
AssetLibrary owns every new admitted result.

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
Legacy admissions without the new archive contract retain their original live
authority requirement. New admissions can recover from verified original durable
Job publication and settlement, with fresh read authority and no model replay.
The mandatory archive contract and bounded convergence are described below.

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

## Mandatory private result archive (append-only contract)

New admissions bind `creative-adaptation-text-asset/1` to the original proposal
and Job. Dispatch consent now includes retaining the exact model output as a
private draft. Existing GET/list/refresh safely converge a completed result into
one original AssetLibrary TextAsset v1 before exposing parsed scenes for review.
No new endpoint, save button, queue or retry-model operation is required.

`asset_output` reports `PENDING`, `INCOMPLETE`, `DRAFT`, `APPROVED` or
`NO_ACCEPTED_RESULT`; only verified drafts/approved results expose asset ID,
version, exact raw digest/size and the complete execution receipt. That receipt
records the actual prompt/request/nullable parameters, model and durable route
identity, source/selection versions/digests, original reservation settlement
revision and final executor publication. Public generic asset/generation routes
cannot expose these actor-private bytes or private receipt fields.

Explicit review still writes only a separate SCREENPLAY document and its source
links. The original Creative decision is committed before projecting APPROVED
asset v2; a later read can finish that projection without another human action.
The original raw asset bytes remain unchanged even if a reviewer edits scenes.
Invalid generated JSON is retained as private raw evidence, never adopted.

Recovery requires the same original durable Job and settlement, current actor,
Host, feature, source/privacy/incarnation and route authority. It does not
reconstruct authorization callbacks or call the model. An adapter re-created by
the same durable runtime identity can support passive recovery; a changed model,
route identity or in-call registration cannot. Live dispatch keeps its existing
process-binding checks. The early completed accounting save is insufficient:
only the original executor's final publication marker permits archiving.

All byte limits are serialization-based and checked before reservation/inference.
Receipt faults, corrupt metadata, lost acknowledgements and pending publication
mask output/provenance/review together. Retries are bounded per existing read,
with a two-second/100-entry failure cooldown and at most one convergence per list.

An optional owned CPU check is available through the original acceptance script's
`--scenario adaptation` mode. It uses the already verified local GGUF/runtime,
CPU-only two threads and an explicit 8192-token host context. Graph remains the
default 2048-token scenario. The script never downloads a model or repairs/retries
its output. Invalid real structured output retains exact private raw evidence and
fails the structured acceptance; an explicit test-client review does not certify
human literary quality. Consult the stage report for actually executed results.


## Bounded ordered chapter adaptation

The same create endpoint accepts either the original single-chapter fields or
`sources: [{chapter_id, expected_source_version}, ...]` with title/instruction.
Mixed source modes, duplicates, fewer than two or more than sixteen chapters
are rejected. Every chapter must be complete, saved, available in the current
project/branch, at most 8,000 Unicode characters, and the aggregate at most 32,000
characters. Existing encoded prompt/request/receipt/storage limits also apply;
no source is truncated, substituted, automatically rebased or retried.

Creative snapshots preserve the exact requested order, chapter versions/digests,
full text/selection digests, native Author source fingerprints and complete
native source projections. A digest binds the ordered array. All chapters and
privacy evidence are checked at creation, preview, admission, dispatch, result,
archive recovery, read and review. Changing only the second chapter invalidates
the whole proposal just as changing the anchor does.

This mode uses the original AuthorPreparer with `source_mode: NONE`, no primary
manuscript source, and ordered explicit CHAPTER references through the existing
NativeAuthorSources resolver. Automatic context, style and plan references are
disabled. Preview checks the actual complete context against the snapshots and
rejects truncation. Broker admission names every chapter. The original Job keeps
the first chapter as its anchor and carries a typed, exact ordered-source binding.
There is still only one original execution, settlement and raw output asset.

Every scene and report change carries a 1-based `source_ordinal`. Each scene has
one source chapter; change links cannot cross chapters, and quotes must match the
indicated chapter. Every selected chapter must appear in the difference report,
including an omission entry for a wholly omitted chapter. The host supplies the
adopted scene's `source_chapter_id`; model-supplied links remain prohibited.
Input order is exact, while reviewed scene sequence can interleave chapter
sources. The reviewed screenplay records all source chapters and the ordered
provenance manifest without modifying the novel or Canon.

Existing archive contract names remain unchanged. Ordered origin/execution
receipts use schema version 2, with closed snapshots and an exact chapter-only
explicit context; legacy schema version 1 retains its empty-context validation.
Reopening recovers the same durable original result without model replay.

The UI reuses the existing scoped chapter list and bounded chapter-detail reads.
Details are necessary because list projections can normalize trailing newlines.
Saved/reopened proposals are checked against all original sources independently
of the active manuscript editor. Uncertain or stale writes preserve unsaved
review edits; these edits remain in page memory until adopted or explicitly
exported, and are not claimed to survive a browser restart.

Verification receipts: `adaptation-ordered-baseline.json` (295 File tests),
`adaptation-ordered-lifecycle.json` (74 File/passive tests), and
`ordered-receipt-focused.json` (172 File/passive tests) under
`docs/delivery/v2-development/`. These runs overlap and must not be added as a
unique-test total. PostgreSQL was deselected in these worker runs. Frontend
focused tests passed; browser geometry/visual execution remains blocked by the
missing bundled Chromium. No model inference, model download, or paid API was
used for this slice; synthetic protocol acceptance is not literary-quality
acceptance.
