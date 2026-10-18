# Ordered adaptation and direct Studio usage continuation

Prior product: b99210e2abfdce3323532cd0b746dff70b1ab991; includes documentation checkpoint 2d2bc815.

Ordered screenplay adaptation reuses the existing Creative/AuthorPreparer/Broker/JobManager/private archive/human-review owners. An explicitly ordered set of 2–16 saved chapters is supported, at most 8,000 characters each and 32,000 total. Native explicit sources must be complete and exact; truncation is rejected. Versioned V2 receipts preserve ordered source manifests and per-scene source ordinals, while legacy single-source V1 receipts stay supported. Every selected source is rechecked through lifecycle and archive recovery. No model completion automatically modifies the manuscript or Canon. The frontend quarantines private cached output after authoritative list/detail invalidation and preserves edits privately pending explicit revalidation/discard.

Direct Studio usage projection reports saved Graph asset pins and Timeline clip pins through original Host/session/feature/actor/incarnation read guards. It is separate from refresh/lock/review/execution targets. Each successful response carries an authorized source snapshot even when empty; the UI publishes paired owner results only when source identities match. Coverage is bounded to direct selected-asset references, not recursive descendants or unsaved edits. Missing authority is unavailable coverage, not zero usage. Observation never provisions missing owner identity.

Verification:
- Ordered adaptation new lifecycle: 74 File passes (47 PG deselected); all assigned backend/test hashes unchanged during that run. Earlier 295-case legacy File pass overlapped implementation additions and is supplementary, not final-source whole-suite evidence.
- Real PostgreSQL adaptation source/archive/lifecycle: 190 passed, 197 deselected. Adaptation backend stayed frozen; unrelated usage/UI edits are explicitly recorded in the whole-tree receipt. Original DB reused, no migrations, server stopped and cleanup completed.
- Direct usages File/API: 118 passed; real PostgreSQL parity: 18 passed, with SQL document/revision/updated_at/xmin, project UUID and asset-file no-mutation assertions. Server stopped and cleanup completed.
- Root final UI: 193 passed across ten suites, TypeScript, Vite production build and 52-file token guard passed.
- Real PUBLIC wheel and catalog: 6 passed. Only SourceAdaptationPanel.tsx changed during this backend package check; all app/ and packaging/ hashes match final backend. Final UI/build covers that panel afterward.

Catalog: 2397 operations, fingerprint e6e4a14bf5b7c5b799c3ad8bc11926847b3225a4c627e4e8f3033ce171f42273. New standard adaptation_sources.py and asset_usages.py are included in PUBLIC manifest; private namespace exclusion preserved. Test counts overlap and must not be summed as unique coverage.

Actual model quality, browser interaction/geometry, Windows and full-product acceptance remain open. Original failure logs and source-snapshot flags are preserved. No main merge or Release is implied.
