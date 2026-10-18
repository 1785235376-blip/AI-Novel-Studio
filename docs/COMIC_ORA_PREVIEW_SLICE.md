# Bounded ORA inspection slice

`app.experimental.comic_ora_import.preview_ora(bytes)` is a pure, no-write
inspection helper. No upload/API route, Asset creation, review, receipt storage,
Comic attachment, or native editable-text reconstruction is implemented here.
Its result contains canonical raster layer PNGs (bottom first), recomposed page
PNG, source/archive hashes, and an explicit loss/unsupported-semantics report.
Archived IDs, approvals, provenance and sidecars grant no authority. Future
staging must independently resolve known generated origin and cannot treat an
unknown external raster as a trusted manual Asset.

## Supported profile

One flat stack, normal source-over, integer-percent opacity, visibility and
bounded signed offsets; 8-bit non-interlaced RGB/RGBA PNG. Unsupported groups,
blend modes, effects, color-management profiles, animation, external references,
non-raster content and precision beyond this profile fail explicitly. Metadata
that does not affect supported pixels is stripped and listed separately. Archived
merged previews are checked but never substitute for layer recomposition.
Rasterized dialogue stays rasterized; editable native dialogue is not recovered.

## Bounds

- Archive and sum of ZIP member uncompressed bytes: 64 MiB each.
- Up to 262 members, 256 unique layer sources, 200:1 ZIP compression ratio.
- Central-directory entries bounded before ZipFile object allocation; no ZIP64
  directory, split archive, trailing payload, duplicate/case-colliding names,
  directories, special files, absolute paths or traversal.
- XML: 512 KiB, UTF-8, depth 3, 258 elements; no DTD/entities or unsupported attrs.
- Page: 320–1600 by 320–12000, at most 16M pixels. Layers: each at most 20M
  pixels and 25 MiB source/canonical PNG; aggregate layer pixels 64M and canonical
  layer bytes 64 MiB. PNG chunks/IDAT counts and CRCs are checked.
- Whole-call pixel work: 192M including bounded zlib scan, Pillow decode and layer
  composition. Hidden layers count; repeated member references are rejected.
- PNG zlib output is scanned with bounded chunks before Pillow. Ancillary text
  is removed before decoding, so compressed metadata cannot trigger expansion.
- Pinned existing Pillow renderer gate remains required; no font installation.

## Verification and remaining acceptance

Adversarial pure tests cover ZIP/XML/PNG rejection, bounded output inflation,
aggregate work, no writes, source order/opacity/visibility, negative offsets,
sidecar distrust and real Phase B export → parse raster recomposition. These
are pure tests, with no meaningful File/PG variant: original persistence owners
are deliberately untouched. Asset staging/review/journal and atomic page CAS
attachment require separate design/review and File/PG integration tests.
Target-application interchange and browser visual acceptance remain NOT_RUN.
This slice does not close full ORA import/re-edit acceptance.
