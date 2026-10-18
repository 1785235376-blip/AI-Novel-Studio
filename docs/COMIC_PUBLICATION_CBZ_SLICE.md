# Ordered Comic book CBZ publication slice

## Scope

IMAGE-COMIC-18 remains PARTIAL / NOT_ACCEPTED. This slice adds a real multi-page
CBZ reading copy to the original independent Comic book owner. It does not add
another editor, persistence registry, export queue or source promotion path.

The saved book's chapter array and each chapter's page array define order.
Exports contain numbered full-page PNGs (`0001.png`, etc.), not renamed page
segment ZIPs. A record's existing rendered segments are decoded, checked for
contiguous coverage, and stitched without changing its approved document or
segment height. Blank authored pages and approved image/layer pages use the
same original renderer.

## Current authority and pins

- POST `books/{id}/publication-preflight`: expected book version plus explicit
  LTR/RTL choice; returns exact ordered page IDs, versions, current review
  digests and one publication digest.
- POST `books/{id}/export-cbz`: requires the exact preflight pins and digest.
- Each snapshot uses the original scope transaction, asset lock and project
  owner lease, after confirming that the book already exists. Observations do
  not create an owner or missing collection.
- The publication digest binds saved structure, project incarnation, scope,
  actor, order, direction and all page pins. Every page must be an independent
  PAGE record with current explicit approval and renderable preflight.
- Original `_current` checks source bindings, reviewed raster provenance,
  character bindings, asset metadata/hash/version and source privacy.
- After archive construction, the entire current book/page snapshot and
  authority are checked again before response bytes are exposed.
- Response SHA-256 and publication-digest headers are verified by the client.
  Dirty drafts and stale owner/collection results cannot trigger a download.

## Budgets and losses

The whole request admits at most 100 pages and 64 million aggregate page
pixels; smaller work/output caps can reject a book before that page count.
A request-local budget bounds 256 MiB cumulative source bytes, 256 million
actual source/stitch decoded pixels and 256 million render/resample/stitch/
encoder work pixels. Repeated source checks consume the same budget. The
original `_image` hook is inert outside this request. Source-size admission and
bounded Asset content reads happen before file allocation. Render work includes
layer surfaces and conservative opacity-copy costs, including invisible
layers that the original renderer constructs. Intermediate segment, full-page encoder and final ZIP sinks reject writes
beyond 64 MiB; all buffer writes share a 192 MiB cumulative byte-work cap. Processing is sequential.

The archive contains a minimal manifest, checksums, dimensions, safe-area
pixels and applicable pinned OFL license. It deliberately omits private raw
source records, prompts, local paths, actor/scope IDs and project incarnation.
Source review digests identify approved content without embedding source text.

Reading direction is manifest metadata only. It does not reorder pages,
mirror panels or guarantee a reader honors it. Output flattens text/layers to
RGB PNG. Source-image publication rights are not independently verified.
There is no editable native project archive, Comic PDF, PDF/X, JPEG/WebP
output, print DPI/bleed or EPUB capability claim in this slice.

## Verification and remaining acceptance

`tests/test_comic_publication.py` uses the actual mounted production routes at
both `/api` and `/api/v1`, with File and opt-in real PostgreSQL fixtures. It
checks six stitched pages, image pixels/order/checksums, exact pins, final
rechecks, source/privacy changes, budgets, private failures, no storage change,
and real session revocation. PostgreSQL runs must be performed separately by
the authorized integration owner; no synthetic database fallback is permitted.

ZIP CRC plus Pillow verification is automated artifact evidence only.
Independent CBZ reader acceptance is **NOT_RUN**. Before claiming the required
format acceptance, verify order and image completeness in two independent
readers, or one reader plus an independent unpack tool. Fixed-layout EPUB,
other requested publication formats and editable project archive remain open.

CBZ image reads reuse the original Asset guarded-reader capability. Platforms
without that reader's required safe-open flags fail closed instead of falling
back to an unguarded path. Real Windows CBZ execution is **NOT_RUN**; this slice
does not establish a new cross-platform acceptance claim. Existing non-CBZ
reader behavior is unchanged.

Final frozen local checks: 165 backend tests passed (135 PostgreSQL cases
excluded from this File run), 302 frontend tests passed, full TypeScript and UI
token/static-geometry checks passed. No runtime server, model, dependency
installation, PostgreSQL service or browser visual test was started by this
slice's implementation workers. The integration owner must retain separate
actual-PostgreSQL and external-reader evidence.
