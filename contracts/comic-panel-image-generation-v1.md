# Comic panel Image generation v1

This is a saved-source adapter, not a generation or review engine. It reuses
ProductionExecutionService, ImageJobService / studio_image_execution, existing
provider admission and dispatch guards, and AssetLibrary.promote_owned. This
standalone Image path does not invoke the Model Broker.

## Scope and explicit actions

Only saved IMAGE-kind panels with a nonempty image_brief are accepted. The exact
saved brief (including whitespace) is the prompt. Appearance references are
rejected with COMIC_IMAGE_APPEARANCE_REFERENCES_UNSUPPORTED. Only explicit local
T2I is supported; I2I, cloud egress, implicit reference omission, and automatic
fallback are not supported. Provider, model, and dimensions are explicit and
validated by the original Image parameter/route contracts. No rendering quality
is inferred.

POST /projects/{nid}/studio/production/comic-pages/{rid}/panels/{panel_id}/image-request
accepts expected_version, request_id, provider_id, model_id, parameters. It
returns studio-comic-image-request/1 with source_snapshot and original command.
It creates no job, asset, owner marker, provider call, or Comic edit.

The existing production preview, create, execute, candidate, review, cancel and
reconcile endpoints retain their existing contracts and Host/scope authority.
Only explicit execute dispatches. Candidate bytes remain private until explicit
original Image review. Image approval does not mutate or approve any Comic page.
Comic's upload approval path still rejects generated assets.

POST the same panel prefix /adopt-image accepts expected_version, job_id,
expected_job_version, expected_request_digest, expected_asset_version, and
expected_output_digest. It requires an exact APPROVED original Image result.
Private, failed, unknown, cancelled or reviewing jobs cannot be attached. It
returns the existing Comic record view, increments its version, updates only the
selected panel's asset_id and expected_asset_version, returns DRAFT, and clears
publication approval. Failure preserves the approved Asset. Replays are rejected
by stale CAS, never silently retried or treated as idempotent success.

## Source and authority

ProductionSourceSnapshot gains COMIC_PANEL with id=page ID, version=page version,
and digest=canonical persisted row excluding history. Its required comic_panel
object contains panel_id, panel_digest, brief_digest, actor, scope_key and
incarnation. All digests are lowercase SHA-256. Non-Comic sources forbid this
object and omit it from serialization, preserving old wire identities.

MediaCommand admits exactly one COMIC_PANEL source for local m5.image.t2i. The
original Comic owner rechecks page version/digest, exact panel/brief, current
screenplay/character/asset evidence, actor, scope and project incarnation at
request, preview, queue, dispatch, private publication, review and adoption.
The new kind is not admitted into Graph execution, video/audio commands, or
cloud asset-DAG traversal.

Queue and adoption use original queue -> raw scope -> asset -> project leases.
Publication/review retain original raw scope -> asset -> project order. Provider
transport occurs outside those leases. No nested same-scope transaction or
clearing/rebinding of active Asset scope is used.

## Durable approved asset reuse

Comic keeps original unbound upload reads. Formal Studio images are separately
read using the current original project's scope/incarnation, never an asset's
self-declared scope. Their immutable original Image explicit-approval receipt,
origin, version and bytes are verified. Private candidates are not placed in the
Comic asset catalog. This supports mixed manual and generated page assets.

After adoption, approved-asset reuse does not require the old producing page to
remain unchanged: adoption itself changes that page. Source freshness is checked
at generation/review/adoption boundaries; durable reuse verifies the immutable
approval and current asset pin. Manual selection of approved assets is retained.

## Acceptance limits

Tests use original owners and synthetic local-provider transport returning real
PNG bytes. They do not run a model, paid provider, GPU workload or browser, and do
not establish artistic quality, model quality or Windows product acceptance.
