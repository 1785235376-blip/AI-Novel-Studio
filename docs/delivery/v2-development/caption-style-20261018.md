# Basic global caption styling through the original Timeline owner

2026-10-18. Original roadmap §15.1 explicitly requires subtitle styling. This bounded implementation adds that basic capability, not advanced typography, per-cue ASS editing, external fonts, Windows acceptance or whole-V2 completion.

## Original-owner path

Existing VIDEO Timeline caption section → staged global style → explicit Apply → original local draft and undo/redo → explicit Save/CAS → original saved playback or delivery export → private candidate → original explicit review. Reopen retains the authored settings. No new Timeline engine, subtitle persistence, jobs, provider, renderer or automatic model/render action was added. Existing caption text/timing edits and SRT/VTT import remain on their original owners.

### Closed optional contract

Only VIDEO schema 2 accepts an optional top-level `caption_style`, with exactly four required fields:

- `font_size`: integer 8–72, libass reference units, not output pixels
- `primary_color`: strict `#RRGGBB`, canonicalized uppercase
- `alignment`: `TOP_CENTER` or `BOTTOM_CENTER`
- `outline_width`: integer 0–4

The existing font fallback is unchanged. No font family/path/URL, ASS text, filter expression or custom option is admitted. Existing literal caption restrictions remain intact. Unknown fields, missing fields, booleans as integers, non-finite/non-integral numbers, malformed hex and arbitrary alignment strings fail closed.

Absent style stays absent: no historical defaults or digest rewrites. Schema 1 needs the existing explicit schema-2 upgrade; schema 3 AUDIO rejects the field, including removal operations. Original `canvas.update` accepts the closed object or explicit `null` removal; saved-document null is invalid. Caption appearance remains independent of media-track locks, just like existing caption text, while existing canvas geometry/track lock behavior is unchanged.

The existing generated-SRT renderer gains only a compiler-owned `force_style` suffix for an explicitly present style. Primary color is converted into opaque ASS BGR. Top-center uses internal libass/SSA alignment code **6**, bottom-center code **2**. ASS event override `\an8` must not be confused with the `force_style` alignment value. Absent style emits exactly the historical subtitle filter.

### UI

The small subordinate `StudioTimelineCaptionStyle` control uses shared primitives and existing styling. Inputs stage locally; Apply/Remove enter original `c.change` history. No CSS, shell, protected surface or new save pathway was introduced. Stale callbacks, changed client/revision, unavailable authority, UNKNOWN and conflict states are fenced. Suggested control values do not become saved defaults. Schema upgrade is explicit, and AUDIO has no caption controls. `nle/timelineOps.ts` preserves optional style when rebuilding captions.

### Interchange

- SRT/VTT stay plain text/timing; exporting an authored style explicitly reports `CAPTION_STYLE_NOT_PRESERVED_IN_PLAIN_SIDECAR` and requires the existing loss acknowledgment before download.
- SRT/VTT import replaces cues while retaining the target Timeline's global style. It does not import styling markup.
- OTIO uses the original Studio metadata, reports `CAPTION_STYLE_NOT_NATIVE_NLE_PRESERVED_IN_STUDIO_METADATA`, and round-trips exactly only while native projection remains unchanged. Native edits trigger the existing stale-metadata loss behavior. External NLE fidelity is not claimed.

## Final backend verification

Both final receipts have `exit_code: 0` and `sources_changed_during_check: false`. They ran at HEAD `b2d2df3533aa2179ad12f6d7f8cc823c353f6ce6` with the implementation uncommitted. Counts are separate scopes, not a cumulative product-total claim.

| Scope | Result | Evidence |
| --- | --- | --- |
| New caption tests + original basic-color/AUDIO/caption-transfer/NLE regressions | 88 passed, 15 PostgreSQL cases deselected | [receipt](caption-style-file-final-20261018.json), [log](caption-style-file-final-20261018.log) |
| Real PostgreSQL caption lifecycle and both mounted HTTP export prefixes | 5 passed, 26 non-PG cases deselected | [receipt](caption-style-pg-final-20261018.json), [log](caption-style-pg-final-20261018.log), [runtime cleanup](caption-style-pg-final-20261018-postgres-runtime.json) |
| New frontend diagnostic tests | 52 passed | [UI commands/coverage](caption-style-ui-20261018.md) |
| Adjacent frontend diagnostic tests | 128 passed | [UI commands/coverage](caption-style-ui-20261018.md) |

Root owns final shared frontend type/build, catalog and PUBLIC-manifest checks. Frontend diagnostic stdout was not persisted as a separate test log; the UI report does not claim source-bound shared acceptance.

PostgreSQL reused the already-owned cluster, port 55439, database `v2_recovered_ocr_export_20261018`, OID 16384. No new database or migrations. The harness confirms server stopped and cleanup completed before releasing the exclusive slot.

Coverage includes strict schema/input rejection, schema upgrade/reset, unchanged literal text restrictions, invalid batch writes nothing, edit idempotency/CAS, Save/reopen/history/restore, changed playback/cache identity, stale reviewed input refusal, private-before-review, attestation, actual H.264 delivery/export/download, source mutation during native render preventing publication, UNKNOWN after publication recovering the original output without rerender, SRT/VTT loss acknowledgment and OTIO metadata behavior.

## Retained CPU evidence

All media is synthetic author-owned CPU input. Fonts and FFmpeg/libass were already installed. No download, paid API, actual model, GPU or user Windows access was used.

[Artifact manifest](caption-style-cpu-evidence-20261018/manifest.json) binds retained MP4/PNG/proof bytes. All seven direct-output PNGs were visually inspected:

- [Top-center](caption-style-cpu-evidence-20261018/top-during.png): red glyph bounds `[136,10,183,17]`
- [Bottom-center](caption-style-cpu-evidence-20261018/bottom-during.png): red glyph bounds `[136,162,183,170]`
- [Larger size](caption-style-cpu-evidence-20261018/large-during.png): bounds `[111,150,209,167]`; red pixels 622 versus 126 at size 24
- [Thicker outline](caption-style-cpu-evidence-20261018/outlined-during.png): measured black pixels 340 versus 9; known aspect-fit pillarboxes excluded from the outline measurement
- [White text](caption-style-cpu-evidence-20261018/white-during.png), independently compared against red output
- [Before cue](caption-style-cpu-evidence-20261018/before.png) and [after cue](caption-style-cpu-evidence-20261018/after.png): no caption pixels

[Direct CPU proof](caption-style-cpu-evidence-20261018/caption-style-proof.json) also compares actual historical schema-1/2 unstyled-caption normalized DTOs, digests, rendered bytes and measurements against frozen source `501ff11b`. Both representative paths are exactly unchanged. This is not a universal codec/platform bit-identity claim.

Original saved playback runs independently produced identical File and PostgreSQL bytes: 3,669 bytes, SHA-256 `e9f8ad2277380b7b63fc4662f93fe01f3d753380822c60f8cb8b8b5083c52240`. See [File proof](caption-style-cpu-evidence-20261018/file-saved-caption-proof.json), [PG proof](caption-style-cpu-evidence-20261018/postgres-saved-caption-proof.json), and retained matching MP4s. Saved-playback encoding differs from the direct renderer's default encoding, so those two output profiles are not claimed byte-identical.

## Retained diagnostic failures and boundaries

- [Debug 2](caption-style-file-debug2-20261018.log): a new outline-pixel test initially counted existing aspect-fit pillarboxes. Measurement was restricted to the known blue source rectangle; no production rendering change was needed.
- [Debug 3](caption-style-file-debug3-20261018.log): actual top alignment rendered middle-left when using ASS event code 8. Native decoded evidence identified the error; fixed compiler mapping 6 gives actual top-center, proved by the final test. The failure was not hidden by loosening the top/bottom assertion.
- [Debug 4](caption-style-file-debug4-20261018.json): focused 26-case backend pass, superseded by the source-stable final run; an unrelated Canon frontend test changed during that diagnostic run.
- Required Playwright baseline/geometry checks did not render: bundled Chromium was absent. An already-installed Chromium fallback, attempted before the stop message arrived, failed with sandbox socket denial. No download, browser snapshot update or visual pass is claimed. See UI report for diagnostic paths.
- Font fallback and glyph coverage, cross-machine appearance, browser performance and user Windows acceptance remain target-environment work. This slice does not install or guarantee CJK/custom fonts, exact cross-platform typography, per-cue styling or advanced text effects.
