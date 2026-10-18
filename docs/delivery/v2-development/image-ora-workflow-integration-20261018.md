# Guarded IMAGE authoring, ORA import UI, and pinned-font closure

2026-10-18 20:50 UTC. Product 79fbb1e5d80574e513cd51c09b54118b12c80d90;
base 7a9e7457d360d2c3f2379b0767a94def458f408d.

## Director IMAGE authoring flow

The original authoring Graph Director console now offers explicit source/model
preview, separately confirmed dispatch, passive recovery/cancellation, blank-by-
default human cost declaration, reviewed advice selection/note authoring and
original-document adoption/reread. Existing budget blockers and Model Center
setup remain; no automatic model call, fallback, budget change or Graph repin.
Advice is unverified model interpretation. Human costs remain unmeasured.

Reviewed UI fixes retire evidence on capability/source refresh, preserve unsubmitted
cost/note inputs through original workspace discard guards, and synchronously
fence real Graph node click/Escape/directory selection. Ordinary read-only graph
selection still works without IMAGE intent. Broker navigation uses the existing
guarded module/Style route. Passive/restarted jobs without a sealed live executor
show EXECUTOR_UNAVAILABLE_NO_REPLAY, including the original FAILED/restart-unknown
marker. No execution capability is reconstructed from persistence.

## ORA upload, recovery and raster authoring

Original Comic routes now expose the supported flat-raster import workflow:
bounded preview → explicit prepare/stage/resume → actual candidate pixel loading
and loss/license acknowledgment → explicit review → CAS attach to a saved, clean,
dimension-compatible independent page. Attachment creates a DRAFT; page approval
and export are separate. Imported origin remains unverified, never relabeled manual.

Authentication/current incarnation precede streaming. The16MiB raw archive limit
and actual JSON/base64 envelope cap apply before parsing; false/absent Content-Length
cannot bypass them. Bytearray accumulation avoids tiny-chunk overhead. Original
authority leases are acquired only for synchronous processing, not across awaits.
Candidate bytes are actor/receipt/origin/pin checked through original Asset reads.
Preview returns a bounded thumbnail. No server upload cache or browser persistent
storage is introduced; restart recovery reselects the exact file.

Native+RASTER layer edits preserve immutable source pins/dimensions and canonical
dialogue. Copy/arrangement/reconciliation no longer drop rasters. Standalone pages
do not need book membership. Selected File/license and dirty raster drafts reach
actual host/local navigation guards synchronously; catalog reload preserves inputs.
Late attachment results cannot overwrite newer edits. Rendered pixels still
require saving and server preview; unsupported ORA semantics remain explicit.

## Font input and Windows dependency correction

Original pinned fonttools4.59.1 universal wheel was obtained from official PyPI,
hash647db657073672a8330608970a984d51573557f328030566521bc03415535042, into a
task-local dependency directory. Shared/system Python was not changed.
Original prepare_pdf_font.py verified exact Google Fonts variable/OFL bytes and
derived Regular hash eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461.
The test PNG's Chinese sentence is legible without missing-glyph boxes.

A separate source audit found Windows embedded --no-index/--no-deps inputs omitted
fonttools although Comic runtime imports TTFont. The closed manifest/lock now add
the exact official universal wheel and both licenses; all33 previous entries/pins
are unchanged. New independent pyproject-root coverage fails before this addition
and passes after; embedded Windows smoke imports TTFont. Build-host fontbuild was
not incorrectly treated as embedded runtime evidence.

## Verification

- Director new UI/root regressions60 pass; final combined IMAGE/ORA/Style UI120
  pass across11 files, TypeScript/Vite/token pass. These overlap, not summed.
- ORA mounted API+authority File26 pass. Actual PostgreSQL57 pass across routes,
  production scoped mount, staging and attachment; exact fourteen-table hashes
  match, including authorization tables. PG17.11 UTF-8 OID16384 reused, stopped.
- Passive Director recovery File2/realPG2 pass with exact five-table hashes.
- Original pinned CJK File-path tests5 pass, zero skips: Unicode/overflow, copy
  pixels, native separate text layer, PDF embedding and approved export artifact.
  ActualPG font run1 pass, one original File-only restart case skipped. Pins and
  tests were not weakened. Font provenance and PNG/ZIP/OFL proof artifacts retained.
- Windows closure/source verifier41 pass; red-before-fix receipt preserved.
  Native Windows itself NOT_RUN.
- PUBLIC6 pass; catalog2495 operations,18 ORA aliases added, none removed.
  Fingerprint14517a83635d22579c922baedef7c3a183242f7334b45a1109da180f529c998d.
- All3121 final source paths match committed product. Original large-bundle and
  dependency/schema warnings remain.

Browser visual/geometry, real model quality/performance, actual external-editor
ORA roundtrip, general multilingual typography and native Windows packaging
acceptance remain open. The current exchange is a declared flat PNG/source-over
subset. This is not full V2 release acceptance.
