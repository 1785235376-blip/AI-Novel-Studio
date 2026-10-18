# Basic clip color through the original Timeline owner

Date: 2026-10-18. Bounded editing implementation, plus a reproduced native cross-dissolve repair. This is not advanced grading, browser/Windows acceptance, real-model quality acceptance, or whole-V2 completion. No commit, push, installation, model call or user-computer access was performed by this worker.

## Implemented path

Select one VIDEO-track picture clip in the existing Timeline Inspector → stage brightness/contrast/saturation → explicitly apply one original `clip.update` descriptor to the existing local draft → existing undo/redo → explicit original Timeline Save/CAS → original saved preview/build or export → private candidate → explicit review → genuine downloadable video Asset. Reopening uses original GET/adoption and retains the authored settings. Inputs, Apply, Save and reopen never automatically render or play.

The Inspector uses the existing primitives, classes and mounted editor/controller. It introduces no second timeline engine, persistence, queue, provider or renderer. Changing a selected target or timeline context resets unapplied color inputs. Multiple selection, locked tracks, schema 1, audio tracks and unavailable authority cannot apply color. Source replacement remains separately routed through its original source-edit owner; color descriptors cannot smuggle source edits.

## Closed optional contract

Only schema-2 VIDEO clips accept optional `color_adjustment`, with exactly these three required finite numeric values:

- `brightness`: −1 through 1, neutral 0
- `contrast`: 0 through 2, neutral 1
- `saturation`: 0 through 3, neutral 1

Both video-source and image-source picture clips are supported. Booleans, strings, NaN/Infinity, missing/extra keys, arbitrary filters, LUTs and paths are rejected. Whole-document `null` is invalid; an explicit original `clip.update` with `color_adjustment: null` removes the optional property. Schema-1 admission remains unchanged and requires the existing explicit schema-2 upgrade. Schema-3 AUDIO and AUDIO clips reject the field, including removal operations. Existing track locks, source pins, admission budgets, CAS, history and private-before-review rules remain authoritative.

Absent color stays absent in canonical DTOs and digests. A neutral color object skips the filter, avoiding an unnecessary pixel conversion. Non-neutral values compile only into a server-built fixed FFmpeg `eq` chain. The renderer extracts original alpha, adjusts picture planes, restores alpha, and then runs original scale/pad/opacity/fades/transitions. This is bounded SDR-style 8-bit FFmpeg equalization, not HDR grading, color-management interchange, curves, qualifiers or Resolve equivalence. Codec/YUV round-trip quantization means saturation zero can decode with a few RGB levels of channel difference.

## Reproduced existing cross-dissolve repair

A new real native test exposed an existing failure with both colored and wholly uncolored transitions: `xfade` rejected input frame rate `1/0` after the existing premultiply chain. Both failing runs are retained. The shared fix restores declared FPS and AVTB immediately after premultiply/tail-pad/trim for every transition participant. There is no color-dependent prerequisite for a working dissolve.

This deliberately changes the legacy transition filter graph to repair its native failure. The legacy identity claim is therefore limited to unchanged schema-1/schema-2 **non-transition** paths. Actual legacy normalization, digests, output bytes and measurements are compared against source `3fe05b171e05f777dba6553c3fad185592b72774`. Colored and uncolored dissolve tests independently decode start/mid/end frames and check the midpoint blend.

## Interchange boundary

The existing OTIO bridge retains the complete settings in its original Studio metadata. It now explicitly reports `BASIC_COLOR_NOT_NATIVE_NLE_PRESERVED_IN_STUDIO_METADATA`; external NLEs do not automatically apply these controls. Unchanged native projection round-trips exactly; a changed native projection rejects stale Studio effects as before. No external Resolve/Premiere acceptance is claimed.

## Verification status

Final backend checks ran at HEAD `26e3c055ad6d874f5d80244a137606877eb8459b` with this implementation uncommitted. Both terminal receipts report `exit_code: 0` and `sources_changed_during_check: false`; complete source hashes and commands are retained.

| Scope | Result | Evidence |
| --- | --- | --- |
| New color contracts/native pixel tests/mounted export plus original AUDIO/video/edit/OTIO regression | 83 passed; 43 PostgreSQL cases deselected | [File receipt](basic-color-file-final-20261018.json), [raw log](basic-color-file-final-20261018.log) |
| Real PostgreSQL original edit/save/history/playback/recovery/source/CAS and both mounted export prefixes | 6 passed; 31 non-PG cases deselected | [PG receipt](basic-color-pg-final-20261018.json), [raw log](basic-color-pg-final-20261018.log), [terminal runtime/cleanup](basic-color-pg-final-20261018-postgres-runtime.json) |
| Diagnostic Inspector/NLE/audio component regression before shared freeze | 135 tests passed across four files, including 31 new color cases | [UI receipt](basic-color-ui-debug2-20261018.json), [raw log](basic-color-ui-debug2-20261018.log) |

PostgreSQL 17.11 reused the original owned cluster on port 55439 and database `v2_recovered_ocr_export_20261018`, OID 16384. No database or migration was created. The harness confirms server stopped and cleanup completed. Installed FFmpeg was 7.1.5; only bounded CPU work ran. Root owns final TypeScript, Vite, catalog and combined UI verification; the diagnostic UI receipt does not replace that final pass.

Coverage:

- Closed field/range rejection; schema-1 upgrade; schema-3/AUDIO rejection; split/copy/remove and locked-track behavior
- Actual image and video source pixels under each individual control; neutral render identity; transparent-alpha composition
- Original edit replay, whole-document Save, reopen, history, restore, stale CAS, invalid atomic batch, stale sources, source change during real FFmpeg execution
- Saved playback cache identity changes; exact attestation; reviewed private candidate; actual H.264 delivery export and download on both mounted route prefixes
- UNKNOWN after actual private Asset publication and reconciliation of that original output without rerendering
- Mounted Inspector staged Apply, one-step undo/redo, Save/reopen, removal, disabled states and UNKNOWN/conflict save fencing
- Original audio-only and video/OTIO regressions

### Retained actual media

[Before MP4](basic-color-cpu-evidence-20261018/before.mp4) and [after MP4](basic-color-cpu-evidence-20261018/after.mp4) are the original PostgreSQL playback candidates. [Before PNG](basic-color-cpu-evidence-20261018/before.png) and [after PNG](basic-color-cpu-evidence-20261018/after.png) are FFmpeg-decoded first frames, visually inspected as the expected two swatches. These are media frames, not browser screenshots.

Both File and PostgreSQL independently produced the exact same [before/after proof](basic-color-cpu-evidence-20261018/basic-color-proof.json):

- Neutral/absent baseline: 3,129 bytes, SHA-256 `101c18875c966f0419c754637cf3ffb6f254de09c6d5dce6956e6398e6e90ff0`; sampled RGB `[32,47,63]`, `[160,191,224]`
- Authored brightness 0.2 / contrast 1.25 / saturation 0: 3,131 bytes, SHA-256 `eceadb75f918aa2bb6349c101b0d0bffffd121caf6663769c57a622a3f69b3c2`; sampled RGB `[79,81,76]`, `[255,255,255]`
- Separate [image control proof](basic-color-cpu-evidence-20261018/image-controls-proof.json) and [video control proof](basic-color-cpu-evidence-20261018/video-controls-proof.json) demonstrate each control independently; [brightness](basic-color-cpu-evidence-20261018/brightness.mp4), [contrast](basic-color-cpu-evidence-20261018/contrast.mp4), [saturation](basic-color-cpu-evidence-20261018/saturation.mp4) outputs are retained.
- [Uncolored dissolve](basic-color-cpu-evidence-20261018/uncolored-dissolve-proof.json): start `[32,47,63]`, midpoint `[95,118,143]`, end `[160,191,224]`.
- [Colored dissolve](basic-color-cpu-evidence-20261018/colored-dissolve-proof.json): start `[90,105,121]`, midpoint `[137,147,153]`, end `[184,186,181]`.
- [Legacy byte proof](basic-color-cpu-evidence-20261018/legacy-byte-proof.json): schema-1 and schema-2 non-transition normalized values/digests, actual output bytes and measurements equal the frozen baseline. Outputs are 2,293 bytes, SHA-256 `9b298c609c6224f193768ba97a889eddb3eaa06ded827c2c3a30b597f219d939` and `ff26318a295a641a42469387bff1595474c4115ae2c0ae608251e6ec844e410f`, respectively. This representative test is not a universal codec/platform identity claim.
- [Artifact manifest](basic-color-cpu-evidence-20261018/manifest.json) binds all retained evidence bytes.

### Retained diagnostic red evidence

- `basic-color-file-debug1-20261018`: decoded image saturation-zero RGB differed by up to five levels after FFmpeg YUV/MPEG round-trip. Pixel tests now use a six-level tolerance while still asserting large chroma reduction and exact bytes/digests.
- `basic-color-ui-debug1-20261018`: undefined color could disappear through a JSON clone before validation. The descriptor path now validates the detached DTO directly, preserving fail-closed rejection.
- `basic-color-file-debug2-20261018`, `basic-color-dissolve-debug-20261018`, and `basic-color-uncolored-dissolve-debug-20261018`: actual CFR failure and uncolored baseline reproduction.
- `basic-color-transition-debug3-20261018`: both shared-fix native midpoint proofs pass.

No browser screenshots, browser interaction/performance, canonical Playwright visual pass, user Windows playback/install or full 2V/2A/subtitle product journey are claimed.
