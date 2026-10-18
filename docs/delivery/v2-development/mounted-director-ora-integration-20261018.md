# Mounted IMAGE API and reviewed ORA raster attachment

2026-10-18 20:25 UTC. Product 7fad622f9cec1c4a8455f4f97412fcfa22dc9641;
base 899a2566ec5608c78e7eee5607069a2efe50981e.

## Director backend now mounted, frontend pending

Original Creative composition mounts distinct director-image-v3 routes. Actor,
scope and Host capability are derived by original authorization/discovery owners,
never accepted in browser bodies. Forwarded authority is rejected; strict inputs
are bounded, responses/errors sanitized and no-store. Original Prompt adoption
write gate remains false. No second workflow or provider registry.

Explicit preview, dispatch, prepare-review, human cost declaration, review and
adopt remain separate actions. Passive capabilities/list/status do not execute
models. Budget blockers remain intact. Content requires current source/target
authority. Metadata-only recovery and sealed live cancellation remain available
after source deletion, target edits or generation-feature disable, without
exposing stale advice or granting rerun. Missing persisted Job records return
EXECUTOR_UNAVAILABLE_NO_REPLAY; restart cannot reconstruct execution authority.
Cancellation does not establish that upstream inference stopped.

Mounted verification uses injected HTTP/model outputs. The authoring console UI
is not in this product checkpoint, and real inference/browser acceptance is open.

## ORA review and attachment, still server-only

Explicit manifest-bound review uses a sealed original Asset promotion adapter.
Review intent precedes promotions; effects and receipt checkpoints are separately
durable and recover exact acknowledgement loss. Generic metadata/manual approval
cannot acquire this authority. Unknown external raster origin stays unverified.

Attachment rechecks receipt, reviewed Asset pins, incarnation and existing
independent page CAS. Original page revision and attachment receipt commit
atomically with owner leases held through commit. Replays return the original
result without attaching twice. Reviewed RASTER layer references carry actual
pins/dimensions/offsets, retain source bounds and decode budgets, and coexist
with legacy unbound native artwork. Native text/geometry/order remain canonical.
Book copy remaps layer IDs without inventing panel targets for rasters.

Original read/re-edit/save and real ORA export→pure parse are covered. External
application editing is not tested. No ORA route/upload/editor UI is mounted yet.
The reference-only frontend refuses unsupported RASTER editing rather than
silently dropping content. A stale helper header predates these backend methods;
this report records their bounded current status.

## Evidence

- Mounted Director File13 pass, followed by2 source/target-drift cases (one
  overlaps the first run). Fourteen unique mounted scenarios.
- ORA File60 pass, one existing pinned-font skip.
- Combined actual PostgreSQL27 pass:13 Director plus14 ORA. Separate drift run2
  pass includes one overlapping case; do not sum as29 unique. Five-table exact
  before/after hashes match in both. Reused PG17.11 UTF-8 OID16384; stopped.
- PUBLIC6 pass, catalog2477 operations,20 IMAGE route aliases added, none removed.
  Fingerprint d76a0bed60a6dd534991ac36205d9aec77b1ebe5e80349bd782a4056a8ffe8b7.
- All3106 final source paths match committed product.
- No frontend source changed:1604 paths match prior Audience UI/build receipt;
  that verified frontend artifact is reused.
- Independent reviews clear after correcting missing-job recovery. No services
  other than disposable loopback PostgreSQL, real models, paid APIs or releases.
