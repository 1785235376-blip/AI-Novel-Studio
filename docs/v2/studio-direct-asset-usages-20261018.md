# Direct Studio asset usages — 2026-10-18

Bounded A09/U06 continuation over product baseline `b99210e2` / checkpoint `2d2bc815`. This is not a complete downstream inventory or completion of those roadmap items.

## Original-owner implementation

- `app/creative/asset_usages.py` projects only direct saved `asset_reference` graph nodes and saved Timeline clip `source_snapshot` references to the explicitly selected image/audio/video asset. Disabled saved graph nodes remain recorded uses. No runs, candidate results, inferred descendants, indirect graph execution, unsaved edits, or external exports are enumerated.
- Two GET observations are mounted in the original Graph and production execution routers, under `/novels/{nid}/experimental/production/assets/{aid}/studio-{graph,timeline}-usages`. Original Studio scope/feature/actor/incarnation and Host admission remain in force. The new Graph observation opts into Host capture even for schema 1; other Graph routes retain their prior admission behavior and schema-dependent execution flags.
- Original authorized list reads discover candidates; original get reads validate each exact consumer. Missing readers, inaccessible sources, malformed owners, changed source/consumer identity, and lost authority fail closed with no partial usage response. No raw-store fallback exists. `existing_owner_only()` prevents missing File identity provisioning.
- Both observations return an explicit authorized current source snapshot even for zero rows. Consumer rows carry original owner/ID/version/digest, node or track/clip identity, and recorded versus current source pins. Source and consumer identities are reread before return; all fresh authority guards remain active through response preparation.
- At most 25 consumer documents are admitted per owner and at most 200 usage rows are returned, deterministically ordered with explicit truncation. Uninspected dependencies remain `UNKNOWN`; neither zero nor truncated results claim global completeness.
- Existing lineage `usages`, ChangeImpact `items`, refresh/lock targets, review flows, persisted schemas/digests, and original source guards are unchanged. No duplicate store, executor, review authority, or rebind action was added.

## Mounted UI

`StudioUsagesPanel` is a separate read-only section in `ProductionLineagePanel` and ASSET-only `ChangeImpactPanel`. Reads require an explicit button action. Both owner responses publish atomically only after valid metadata and matching top-level source snapshots, including empty results; any denial/error/malformed evidence clears both. No Studio row becomes a legacy lock, preflight, regeneration, or review target.

The decoder validates owner, coverage, caps, unique consumer identity, bounded IDs, canonical SHA-256 digests, media kinds, pin/state consistency, and cross-owner source equality. Client/source/version lifetimes discard late responses; parent refresh invalidation explicitly resets the preview without querying automatically. Existing primitives and styles are reused; protected shell/tokens were not modified.

## Verification and limits

- Backend final source receipt: `../delivery/v2-development/studio-asset-usages-file-r6.json` and adjacent log. Original isolated runner and recovered Python: 118 passed, 20 deselected, File only. Includes new mounted tests under `/api` and `/api/v1` plus original Creative Graph API regressions.
- Cases include schemas 1–5 graphs and legacy/2/3 timelines; exact saved identities; disabled graph nodes; current/stale pins; actor-private original owner rows; Host/origin/forwarded/feature/V1 denial; revocation/ABA; source/consumer changes; final permission loss; missing/replaced project incarnation; corrupt/discovery-mismatched identities; bounded scans/truncation; explicit source in authorized empty responses; unchanged durable bytes and forbidden write/dispatch hooks.
- The legacy timeline fixture uses explicitly labeled opaque original-owner metadata-only video bytes. It does not claim playable video or render/probe acceptance.
- Intermediate receipts are historical, not final evidence. Early failures corrected schema-4 image-only and legacy-video fixture assumptions, the local-mode canonical actor test assumption, and new schema-1 observation Host capture.
- Frontend final source receipt: `../delivery/v2-development/studio-asset-usages-ui-r3.json` and adjacent log: 94 tests passed across the new unit/integration tests and four original panel regression files. Earlier UI runs exposed a test-only role query and a real same-source parent-refresh lifetime gap; explicit reset keys fix the latter without changing shared hooks or old action targets.
- Real PostgreSQL parity: `../delivery/v2-development/studio-asset-usages-pg-r1.json` and `studio-asset-usages-pg-r1-postgres-runtime.json`: 18 explicitly `postgres_backend_only` tests passed using the original mounted PostgreSQL repository fixture. Reused PostgreSQL 17.11 / database OID 16384 / UTF8 at the existing loopback endpoint; no migrations or database creation. Exact SQL scope document/revision/updated_at/xmin, novel UUID/xmin, and asset files remain unchanged across observations. Actual same-slug delete/recreate yields a new original UUID and cannot recover old source pins or consumers. Original-owner private rows and mid-read revocation remain fenced. Harness confirms server stopped and cleanup completed.
- Combined TypeScript/build/catalog/PUBLIC verification is owned by the integrating parent. No browser, visual screenshot, native IME/assistive technology, model/provider, Windows/GPU, hosted CI, or whole-product RC acceptance is claimed by this slice.
- No installs/downloads, paid calls, model calls, commits or push were performed. P0 and existing release gates are unchanged.
