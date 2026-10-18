# Passive Research OCR records in the original job owner

2026-10-18. This slice reserves and persists the OCR domain. It **does not enable
OCR job execution, release model-broker admission or connect Research review**.

ResearchOCRJobBinding is a strict, closed, passive contract: project incarnation,
actor, exact local/collaboration scope, source image ID/version/digest, media type,
language, route digest and reviewed-preview digest. No chapter or Graph identity
is fabricated. No image bytes or native paths are in this binding. Digests stored
in a record are evidence fields, never proof of consent or live authorization.

The existing source-bound generation repository classifier and File/PostgreSQL
project-owner guards now cover this typed domain as well. Their historical helper
name includes Graph, but OCR records carry no graph_binding. Project reuse cannot
adopt old records; complete discriminator removal cannot downgrade a saved record.
Bound source, scope, actor, route and request identity remain immutable on updates.

Job retains a detached public binding. Every OCR discriminator independently
prevents ordinary Author preparation, start, direct worker entry, content serving
and manuscript adoption. In-progress restart records become FAILED with cleared
uncertain output. No callback, provider or broker accounting is restored or replayed.
Completed passive records also remain content-inaccessible through generation
availability checks. A future private live execution capability is still required.

## Actual verification

- 83 File checks passed; 80 PG cases deselected. Includes the unchanged original
  Director persistence regressions as well as the new OCR cases.
- 80 real PostgreSQL checks passed; 83 File cases deselected. Reused original test
  database OID 31303, no fresh migration claim; server stopped successfully.
- 2 unchanged original Author generation/explicit accept/cancel checks passed.
- 3 PUBLIC checks passed, including actual offline wheel and metadata validation.
  The PUBLIC allowlist adds only the STANDARD passive binding module.
- Source/job records, rejection outcomes and positive new-owner persistence were
  verified against the real repositories. No old test was relaxed or modified.
- No UI changed; no redundant frontend build, model-quality, current product-browser
  or installed Windows acceptance is claimed. The wheel remains a 0.7.0 test artifact.

Next: bind an original JobManager live capability to the current Research source
preparation and pinned VisionOCRModelNode, original broker hooks, cancellation,
terminal publication and original Research review receipt. Existing synthetic-only
Research dispatch and real-provider-unavailable reporting remain unchanged until
that complete guarded path exists.
