# Research OCR source preparation

2026-10-18. This is a read-only preparation component, not a working OCR feature.
The existing Research real-adapter refusal remains in force. No route, JobManager
execution branch, model registration, scheduler or provider is enabled here.

`PreparedResearchOCRSource` lives with the original Research vision contract. It
captures the original ResearchLibraryService source, project incarnation, actor,
scope, version, content hash, visibility, page and PNG/JPEG media declaration.
The original import owns image verification; this component bounds decoded input
to 4 MiB and verifies its stored content hash. It does not perform new pixel
recognition, PDF rasterization, image conversion or quality evaluation.

Preparation requires the incarnation-aware original owner and a live authorization
callback. Reads recheck current source visibility, project identity and full source
state around callbacks. Source replacement, revocation, authority loss and reuse
of the public project ID invalidate the captured snapshot. New-incarnation sources
remain usable. Metadata returned by `binding` is a detached historical snapshot,
not live authority; `read_current` and `validate_current` perform fresh checks.
No source bytes are embedded in the binding or written to a new job collection.

## Verification

- 61 File/runtime checks passed; 21 PostgreSQL cases deselected. Includes the new
  preparation cases, the unchanged typed OCR runtime tests and current-incarnation
  regression tests.
- 10 real PostgreSQL preparation cases passed; 10 File cases deselected. Reused
  disposable database OID 31303; no fresh migration claim. Server stopped normally.
- PNG/JPEG inputs are real generated test images. No OCR inference was performed.
- Existing tests were not altered. Original persisted source records were compared
  before/after read-only preparation and denial. No frontend or dependency changes;
  the prior frontend type/build evidence is unchanged and was not redundantly rerun.
- Public manifest already includes the changed Research module. No new executable
  module, NSFW boundary, public route or export catalog entry was added. This slice
  does not claim a newly built whole-product artifact or final product acceptance.

## Next integration

The original JobManager must own preparation, dispatch, cancellation, terminal
publication and recovery. It must bind this source snapshot together with the
original VisionOCRModelNode admission and a real bounded provider. The preparation
object alone does not authorize execution or justify changing broker availability.
