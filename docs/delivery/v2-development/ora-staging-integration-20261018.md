# Private ORA staging and exact crash recovery

2026-10-18 20:09 UTC. Product 2a9287733aea93bdda4dd2de27c3021b46dc6ded,
base 6408344745134be12b13002da378076406597c81.

## Bounded implemented behavior

The existing Comic scope records a bounded import receipt and exact planned Asset
UUIDs before original Asset.create. Canonical raster bytes enter actor-private,
project-incarnation-bound Assets with immutable server-only ORA origin in the
first metadata commit. Archive IDs/sidecars never confer provenance or approval.
No new project/Asset/Job owner, public route, UI, promotion or page attachment.

Stage/status/resume recheck original flags, authority and incarnation. Exact
archive bytes must be reselected after restart. Asset and scope acknowledgement
losses reconcile exact planned IDs, canonical bytes and original origin rather
than creating duplicate candidates or searching arbitrary foreign assets.
Bounded nonblocking/no-follow reads reject special files.

Partial stages remain explicitly recoverable. Asset writes and scope checkpoints
are not advertised as one rollback-capable transaction. Scope→Asset→project leases
survive scope commit. Original legacy Asset readers remain unchanged. Generic
metadata writes and promotion cannot bypass the staged origin restrictions.

Project quotas count both committed metadata and exact current-incarnation
planned binary-only orphans across receipts. Recovery does not count the same
orphan twice. This fixes the review finding that repeated hard crashes could
otherwise accumulate retained bytes outside the metadata-based quota.
Status now performs a final full authority check, including feature retirement.

## Evidence

- Initial integrated File run:16 pass/1 fail. The test regenerated ZIP fixtures
  with wall-clock DOS timestamps, so its supposedly identical archive had changed
  SHA-256. Production correctly rejected the changed archive.
- Fixture-only correction fixes timestamps. New File/PG regression proves that
  timestamp-only archive changes are still rejected despite identical pixels;
  exact original bytes resume. Product digest checks were not relaxed.
- Final integrated File/parser run:68 pass,18 PG variants deselected.
- Real PostgreSQL:18 pass,18 File variants deselected; original earlier17 pass
  retained separately. Exact before/after novels/scope row hashes match; reused
  UTF-8 PG17.11 database OID16384, no creation/migrations, server stopped.
- PUBLIC six pass. Only test fixtures changed afterward; packaged product inputs
  are unchanged. Catalog2447 operations, no new routes; fingerprint
  03e9147e0f6c11cc222d43d815518a2dad6619df46466b3b622747afb20e9cdd.
- Final File receipt verifies all3093 source paths against the committed product.
- No frontend changes: all1601 frontend source paths match the prior integrated
  UI/TypeScript/Vite/token receipt. Existing frontend test artifact reused.
- Earlier isolated162 pass and pinned-font skip overlap these checks; not summed.
  Original failure receipts/logs remain unchanged.

## Remaining

Explicit review, atomic page attachment, new bound-raster layer reading, mounted
upload/recovery UI and actual external application edit/import acceptance remain
open. Staging alone is not a usable end-to-end Comic import workflow or V2 release.
