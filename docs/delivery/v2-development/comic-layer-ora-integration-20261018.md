# Native Comic reference layers and bounded ORA export

2026-10-18 19:47 UTC. Product 69943270e38df8d6d9869808c75760ca0a1c883a,
based on faff5940f211c5c7f10a32f7c9dd3ba4df2f7bb5.

## Implemented boundary

Existing Comic records now optionally persist a versioned reference layer stack.
Canonical panel geometry and dialogue remain in their original records. Layer
names, visibility, integer opacity and order survive editing, duplication,
arrangement, undo/redo, save and restore. Legacy documents remain unlayered until
explicit enable; legacy normalization, report digests and PNG rendering stay intact.

Approved current pages can export actual OpenRaster: individual cropped PNG layers,
escaped stack.xml with offsets, order, visibility and opacity, merged image,
thumbnail and an explicit loss receipt. Native dialogue remains editable in the
project; external ORA text is raster. No new Asset store or workflow owner.

Controls update the local draft immediately. Rendered pixels are not live: edits
invalidate the prior preview and require saving plus server preflight/preview.
The top-first list maps movement labels to bottom-to-top rendering correctly.

Per-source/stage and summed layer/resample limits, a 128M operation-wide decode
budget, and bounded PNG/ZIP encoding prevent repeated checks from escaping the
work budget. Hidden layers count. XML-invalid layer names/titles are rejected.

## Verification

- Integrated File: 84 passed, one pinned-font skip, 56 PG variants deselected.
- Real PostgreSQL: 52 passed, four File-only skips, 85 deselected. Reused UTF-8
  PostgreSQL 17 database OID 16384; no creation or migration. Exact before/after
  durable row hashes match; runtime stopped. See cleanup/runtime receipts.
- UI: 148 passed in ten suites; TypeScript production build, Vite and token guard
  passed. Existing large-bundle warning remains.
- PUBLIC wheel and catalog: final six passed. Initial run failed because the new
  manifest entries were not lexicographically sorted; the manifest was corrected,
  tests were not weakened. Original failed receipt/log retained.
- Catalog: 2445 operations, two added aliases, none removed; fingerprint
  f89931a94e6f5501814f237af585e5ee22506cd2c0cca4180f9854dd4b3a8dda.
- All integration receipts report stable source inputs. Committed-source receipt
  verifies every final PUBLIC source path against the product commit.

Evidence prefix: comic-layer-integration-* in this directory. Earlier isolated
comic-layers-* results are retained and overlap these tests; counts are not summed.

## Still open

ORA import/staging/review/attachment/recovery, target-application open/edit/save/
reimport, live layered pixel editing, masks, erasure, inpaint/outpaint, advanced
typography, native portable archives and broader publication formats remain open.
Browser/visual, Windows and target-application acceptance were not run. Missing
verified CJK font gates were preserved. No model or paid API calls occurred.
IMAGE-COMIC-02 and IMAGE-COMIC-15 remain PARTIAL / NOT_ACCEPTED; this is not V2
release acceptance.
