# U03 deterministic scoped search

## Sources and safety

The opt-in `workspace_tools_v2` route uses the original `domain.read` authority before each target read and again before returning results, counts, suggestions or a resolved navigation target. Authorized-project enumeration supplies candidate IDs only; denied IDs, titles and counts are omitted. Each result carries the original project/branch, entity ID, current version and a digest of its allowed search projection. A resolve rereads the source and rejects stale revisions unless the author explicitly chooses its current version. Search commands remain navigation only.

Local File chapter manifests stat the original Markdown/document-package files and read archive state inside the existing project lifecycle guard. File fingerprints include inode, size, nanosecond modification time and nanosecond change time. Original atomic saves, archive/delete and normal external edits invalidate the manifest. Changed chapters alone are read and projected. Legacy document packages are derived in memory; search never materializes them on disk. Writers that defeat all filesystem metadata are unsupported; explicit rebuild reads all sources again.

Local PostgreSQL manifests select original chapter number, version, content hash, update timestamp and title. They do not select manuscript JSON. Changed chapters alone use the original repository get operation. The tests inspect actual warm SQL and reject a chapter document-column read. No new source table or migration exists.

Structured entities, existing continuity findings and safe task projections are reread from their original authorities on each request because they do not all expose independent durable version manifests. Names/aliases are searchable for characters and locations, without private body fields. Existing branch manuscript storage is not implemented by the original chapter authority; branch chapter search remains unavailable rather than using base-project prose. No authorization result is cached.

The index is process-local, bounded to eight actor/scope entries, 2,000 records and 2,000,000 characters per entry. Authorized-project search processes at most 20 authorized scopes and returns 50 results per page. Counts are for the retained index; truncation is explicit. Cold restart, cache eviction, or more scopes than cache entries can require source rereads. There is no browser manuscript index, background task, model request or automatic feature activation.

## Cancellation and rebuild

Each UI request has a unique request ID and captured actor/branch client. Cancel aborts transport and sends an authorized cancellation request. Server checks cancellation between sources and before index replacement and response publication. Pre-start cancellation tombstones close a cancel/start race. Changes to query, filters, scope or IME composition discard old UI results/counts/suggestions; cancelled or late responses cannot repaint them.

A rebuild creates a replacement off to the side. Metadata and permission revalidation must succeed before swapping it into the cache. Cancellation, source changes and failed permission checks never publish a partially rebuilt index. Cancellation is cooperative between source reads, not a promise to interrupt an individual database or filesystem operation.

## Verification and measurements

Added real File and marked real-PostgreSQL contracts cover cheap warm manifests, single-source updates, archive/delete, read-only legacy chapters, multi-project permissions and late revocation, current counts/suggestions, stale resolve, races, cancellation, paging, aliases/tags/recent/fulltext/unresolved filters and original generation-task navigation versions. UI tests cover captured scope, filters, pagination/rebuild, revoked sources, IME, cancellation, late responses and abortable cross-project navigation. The hosted browser journey is `frontend/tests/e2e/r4-search.spec.ts`.

Local execution on 2026-10-05: Linux 6.18.44 x86_64 / glibc 2.41, Python 3.12.14, AMD EPYC 9V74 reported by the shared executor. Isolated File backend; synthetic Unicode prose only. Each sample has three chapters, one with the stated large text, and no task/entity readers. Fixture creation is excluded. Cold time is a forced index build in the running process; warm p95 is nearest-rank p95 of 20 subsequent service calls. The performance test emits JUnit properties so hosted measurements can supersede these observations.

| Large chapter characters | Cold index ms | Warm service p95 ms | Rebuild peak Python allocation bytes | Process peak RSS KiB |
| --- | ---: | ---: | ---: | ---: |
| 100,000 | 5.552 | 4.556 | 2,022,083 | 132,416 |
| 500,000 | 13.462 | 6.624 | 10,022,059 | 143,312 |
| 1,000,000 | 33.762 | 11.534 | 20,022,283 | 159,312 |

Python allocation peak is measured in a separate traced rebuild after timing. RSS is the whole test process's cumulative high-water mark, not index size or a per-call allocation. Timing is not traced. The test explicitly fails if a warm search calls chapter text projection or reads File chapter/document bodies. `chapter_bodies_read` counts changed chapter-body hydrations; `projection_rows_scanned` counts visible legacy entity/task/fallback projections; `source_rows_read` counts changed manifest-entry hydrations, including already-projected structured rows. These are diagnostic counts, not claims of zero total filesystem/database I/O.

Local relevant verification: 42 backend passes, 39 backend-marked skips; 30 UI unit passes; TypeScript build and design-token guard pass. PostgreSQL had no available test endpoint and is not locally verified. The browser journey was collected only; no local Chromium launch was retried after the known executor restriction. Hosted browser screenshots, visual/geometry regression and real PostgreSQL execution are pending integration CI. Editor input p95, app startup time, Windows IME and screen-reader compatibility were not measured by this search test. The observed service timings do not guarantee other machines or data distributions meet the suggested 500 ms target.
