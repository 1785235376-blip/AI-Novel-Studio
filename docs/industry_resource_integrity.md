# Industry export resource integrity

The existing pure screenplay, storyboard and shot-list ZIP builders accept a
caller-owned `get(id)` / `content(id)` loader. They do not open resource paths,
follow filesystem links, call providers, or fetch network resources. These
changes do not expose resource package formats in the queue, API or UI.

## Identity and captured-content contract

- Loader metadata must contain the exact requested asset ID and the exact
  nonblank requested novel ID. Missing ownership is not permission.
- Asset IDs are validated before reaching the loader. Path separators,
  absolute paths, control characters and colon/stream syntax are rejected.
- Duplicate snapshot identities, including available/missing conflicts, are
  ambiguous and are reported missing rather than resolved by last-write-wins.
- A captured, valid SHA-256 digest is required. The returned bytes must match
  that snapshot digest. Current loader metadata cannot replace the captured
  digest or authorize changed bytes. Legacy snapshots without a digest need
  a fresh capture for resource packaging.
- Each binary is capped at 25 MiB, matching asset creation. Verified binaries
  have a cumulative 64 MiB uncompressed cap. Boundaries are inclusive. These
  caps apply before adding bytes to the package staging map; the trusted loader
  remains responsible for safe, bounded underlying reads.

`allow_missing` records rejected/unavailable assets with `packaged: false` and
omits their bytes. `require_all` raises `IndustryExportResourceError` before
returning an archive if any resource cannot be packaged. No configured loader
also means missing binary content, even when snapshot metadata exists.

## ZIP consistency

All three package builders share the existing deterministic resource member
staging logic. Member names are sanitized basenames with unique numeric
prefixes under `resources/`; the resource ID is never used as a file path.
The shot-list ZIP now actually contains the assets its manifest claims are
packaged. Every available resource has a `package_path`, size, and verified
SHA-256 matching a real archive member. ZIP members are regular files, never
symlinks. The manifest file list matches the complete archive member list.

Regression coverage: `tests/test_industry_resource_integrity.py`. Local
verification evidence is kept under `.cloud-validation/resource-integrity/`.
The original implementation was loaded separately from `git show HEAD` for
baseline reproduction without changing the working tree. Tests cover ownership,
identity, duplicate IDs, checksum substitution, missing-resource policies,
archive contents/digests, unsafe paths, collisions, nonbinary/path-like loader
results, both byte caps and their inclusive boundaries.

## DOCX text validity

The shared text cleaner now uses the XML 1.0 permitted character ranges.
It removes forbidden controls, lone surrogates, U+FFFE and U+FFFF while retaining
Chinese text, emoji and valid supplementary-plane characters. Regression tests
parse every XML/relationship member of a DOCX generated from malformed text in
title, scene content, dialogue, resource descriptions and source metadata. The
exporter's creator property remains the fixed `AI Novel Studio` value.
