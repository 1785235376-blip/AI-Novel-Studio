# Comic native reference layers and ORA export slice

Base: `eb8b8b8ed617c34e1e01415fa5eef9d4c074c348`. This is a bounded additive
implementation, not acceptance of all IMAGE-COMIC-02/08/09/10/15/18.

## Original ownership and compatibility

`comic_layouts_v2` retains the native document, canonical panels/bubbles, history,
approval and CAS. `ComicCollectionsMixin` retains book/chapter/page membership.
Existing project incarnation, source/privacy, original Asset pins and explicit
review remain authoritative. No new assets, jobs, project registry or model calls.

`layer_stack` is optional and stays omitted on legacy document normalization,
read/save and restore. Without it the original report shape, digest inputs and
PNG painter are retained. Explicit opt-in creates a new draft. Each opted-in
stack references exactly one panel-art/frame pair per panel and one bubble
shape/text pair per bubble; text and geometry are not copied into layer records.
Items use namespaced IDs and bottom-to-top order, names, visibility and integer
percentage opacity. Only normal source-over compositing is supported.

Layer controls update the local draft immediately. Pixel previews are not live: edits
clear the previous report, and require saving then requesting server preview again.
The top-first layer list maps 上移/下移 to the bottom-to-top render order.

The UI preserves authored properties through edits, duplication, arrangement,
undo/redo and saved history. Backend book-page duplication remaps both canonical
IDs and all layer IDs/references. Destructive screenplay preset regeneration is
blocked on layered drafts rather than discarding authored layers.

## ORA export

`GET /comic-layouts/records/{rid}/export-ora?expected_version=...` requires a saved
explicit stack and current approval. It rechecks current authority, document
version and source bindings before and after encoding. Old PNG ZIP export remains.

The output contains first/stored `mimetype`, escaped UTF-8 `stack.xml`, separate
cropped RGBA PNGs, a paper layer, full-page `mergedimage.png`, a bounded thumbnail,
and `comic-loss-receipt.json` (plus the verified font license when text is used).
XML order is top-first, with explicit offsets, opacity and visibility. Pixel
composition is independently tested, including hidden/reordered/translucent
layers. XML-illegal names/titles are rejected on layer-enabled documents.

The native project preserves editable dialogue. ORA text and shapes are raster
layers; it is not a native project archive. The receipt and UI disclose that
native relationships/history/approval cannot be restored from this ORA. No ORA
import, font replacement or model generation is implemented.

References: [OpenRaster file layout](https://www.openraster.org/baseline/file-layout-spec.html)
and [layer stack](https://www.openraster.org/baseline/layer-stack-spec.html).

## Explicit resource limits

- Existing 16M page pixels, 20M per source/resample, 64 MiB source/output bytes,
  original 25 MiB per asset, panel/bubble/text/history bounds stay in force.
- At most 256 logical layers; summed cropped layer surfaces at most 64M pixels,
  including hidden layers. Only one cropped surface is emitted at a time.
- Layer-enabled source-validation and render stages each cap aggregate decoded
  source pixels at 64M, before pixel load. Duplicate payload pins reuse bindings.
- A request-local ORA budget counts every actual source decode across all
  repeated preflight/current/render/final checks, capped at 128M pixels. It is
  reset in `finally`; no request/global cache or authority bypass is introduced.
- Summed layer resample work is capped at 64M pixels before resizing, including
  COVER images whose decoded/resized areas exceed their cropped output areas.
- PNG encoding and ZIP writes enforce 64 MiB during writes, not only afterward.

## Verification and remaining acceptance

See `docs/delivery/v2-development/comic-layers-reviewed-final.{json,log}` for the
backend File result and exact source hashes. Earlier failed runs remain intact:
the first lacked sparse-checkout interop modules; later failures were test fixture
or expected-status corrections. No database service or dependency was installed.

Frontend evidence: `comic-layers-ui-regression.{json,log}` (183 tests / 15 files),
`comic-layers-ui-types-final.{json,log}`, and `comic-layers-ui-guards.{json,log}`.

The isolated slice did not run PostgreSQL; subsequent integrated PostgreSQL evidence
is recorded in comic-layer-integration-postgres.json (52 passed, four File-only skips).
NOT_RUN: browser/visual/geometry acceptance,
and target-application open/edit/save/reimport. Pinned licensed CJK pixel tests
remain skipped when the existing verified font is unavailable; the original
font gate is not bypassed or substituted. Native Unicode text persistence and
explicit missing-font behavior are separately tested.

Still open: staged original-Asset import/review/CAS attachment and durable
recovery, actual ORA roundtrip, masks/erase/inpaint/outpaint, tails and advanced
typography/vertical text, procedural effects/blends, native portable archives,
and additional publication/print formats. A multi-asset import must not claim
atomic rollback merely because Asset creates run inside a Comic transaction.
