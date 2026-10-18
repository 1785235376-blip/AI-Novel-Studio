# Independent AUDIO timeline and genuine WAV mixdown

Date: 2026-10-18. Bounded original-owner implementation slice. Final verification HEAD: `b9d9cc02aa01a03dab5805584cd1a290334ea1a7` with the audio implementation still uncommitted at verification. No commit or push was made by this worker. Root owns catalog/package checks and integration commits.

## Delivered behavior

The existing AUDIO workspace now mounts the original Studio timeline editor in AUDIO mode. Existing formal audio Assets can be arranged on independent audio tracks, trimmed, moved, gain-adjusted and faded, saved, and reopened using the original timeline document/CAS/history owner. No VIDEO track or video canvas is required or generated.

Explicit playback preview checks the exact saved timeline, source pins, profile and native-tool identities. Explicit build invokes the original production export/job owner once. Explicit load reads and checks the original private candidate bytes, then uses HTMLAudioElement with `audio/wav`; opening the editor, previewing the plan and loading bytes do not autoplay. Source/version/identity changes retire local Blob playback; UNKNOWN retains its original request and is reconciled without a new render.

The existing reviewed export panel offers the fixed WAV profile. The existing StudioMediaExecutionPanel receives the original timeline job and verifies candidate MIME, byte count and digest before explicit human review promotes the original Asset. Original download provides the reviewed WAV file.

## Closed contract and unchanged budgets

- Schema 3 is explicitly `{schema_version: 3, media_kind: "AUDIO", duration_ms, tracks}`. Width, height, FPS, captions, video tracks, visual sources and visual-only clip fields are rejected.
- Existing schema-1/schema-2 video records retain their previous normalized fields, defaults, digests and rendering branches. Audio schema 3 shares original audio track/clip validation and original atomic edit operations.
- One profile: `{preset: "AUDIO_WAV_PCM16"}`. No arbitrary codec, rate, channel, bitrate, path or filter controls.
- Output is PCM signed 16-bit, 48,000 Hz, stereo WAV. Admission uses exactly `44 + duration_ms × 48 × 2 × 2` bytes. Final native probe and WAV decoding prove one audio stream, zero video streams, exact sample count/format and exact byte count.
- Original 25 MiB output limit, 200 MiB cumulative source limit, four audio tracks, thirty clips and ten-minute draft maximum remain unchanged. At the fixed WAV format, the output limit admits at most 136,533 ms; the UI explains and checks that ceiling before execution.
- Audio-only compilation has no color/black-frame input, video filter or video map. It reuses the existing audio filter chain, with compensated limiter latency and disabled automatic gain boost for the new audio profile. Legacy video filter behavior is unchanged.
- Publication, candidate access, recovery and review derive expected kind from the exact immutable bound export profile and its digest. An arbitrary supplied candidate kind cannot authorize audio output. Old receipts without explicit profiles keep their original video-only meaning.
- Graph timeline export and OTIO/subtitle transfer remain video-only with explicit rejection of schema-3 audio, avoiding an accidental unsupported format expansion.

## Real CPU and original-owner evidence

Both File and real PostgreSQL exercised two independently imported author-created WAV tones, 440 Hz and 880 Hz. Original atomic edits applied trim, -3/-6 dB gain and fades; a fresh owner reopened the saved timeline. Original playback plan/build/candidate/attestation/review and final Asset bytes completed, including the mounted `/api` and `/api/v1` routes.

Actual mixed output on both backends:

- 2,000 ms; 96,000 stereo frames; 384,044 bytes
- PCM16 / 48 kHz / 2 channels; zero video streams
- SHA-256: `b9559fa78c09840fdaed8e5e959464136ec7b0cc8fc0c0f2c39618176c53bb58`
- Measured overlap amplitudes: 440 Hz = 2002.3636806016525; 880 Hz = 1417.5684072363754. Their ratio and absolute levels match authored gain with the existing equal-power mono-to-stereo conversion. Early/overlap/late intervals and fade attenuation are independently checked.
- All-muted output contains exactly the expected silent samples, and the actual FFmpeg command has no video input or mapping.
- Real native source mutation and cancellation prevent publication. A synthetic interruption after the real private Asset commit yields UNKNOWN; explicit recovery finds that exact audio candidate and approves it without rerendering.
- Source/CAS/track-lock protections, stale playback, closed fields, exact capacity boundary, mismatched profile/kind, host revocation and private-before-review access are covered.

The PostgreSQL harness reused the existing owned cluster/database on port 55439: PostgreSQL 17.11, database `v2_recovered_ocr_export_20261018`, OID 16384. No new database or migration was requested. The original harness reports server stopped and cleanup completed.

## Terminal verification

All final staged receipts below report exit 0 and `sources_changed_during_check: false`.

| Check | Result | Evidence |
| --- | --- | --- |
| File AUDIO + legacy graph/video/trim/waveform/native/receipt regressions | 453 passed; 37 PostgreSQL cases deselected | [receipt](audio-only-file-final-20261018.json), [raw log](audio-only-file-final-20261018.log) |
| Real PostgreSQL AUDIO + original video CPU pipeline | 27 passed; 39 non-PG cases deselected | [receipt](audio-only-pg-final-20261018.json), [raw log](audio-only-pg-final-20261018.log), [runtime/cleanup proof](audio-only-pg-final-20261018-postgres-runtime.json) |
| Root combined AUDIO/Studio Tasks UI + TypeScript + Vite + design-token guard | 134 tests passed, compiler/build/token checks passed | [receipt](audio-studio-tasks-final.json), [raw log](audio-studio-tasks-final.log) |
| Frozen pre-change renderer versus current renderer | Schema 1 and schema 2 normalized values, digests, actual rendered bytes and measurements exactly equal | [receipt](audio-only-legacy-byte-final-20261018.json), [raw log](audio-only-legacy-byte-final-20261018.log), [retained probe](audio-only-legacy-byte-probe-20261018.py) |

The legacy byte probe loads renderer source from the explicit pre-audio commit `91a3f328eec5b7a9076595a5640932aa3b77987c`, uses owned synthetic source media and the same installed native tools, and compares both actual render results. It covers the original review-MP4 path for representative video-plus-audio schema-1 and schema-2 timelines; it is not a universal codec/platform equivalence claim. Both outputs are 14,266 bytes. Schema-1 output SHA is `94a96a20bef739d7e2fc6b7118f80d1faa930033597cab7f3e39eba56ccfc781`; schema-2 SHA is `53a1fc373d56201f37bbf5aa66c965c7267c43476c4cd46dd47a0c644627ff83`.

Additional raw frontend regression evidence, copied unchanged from the worker logs:

- [26 files / 458 tests](audio-only-frontend-regression-20261018.log)
- [10 files / 209 tests](audio-only-frontend-focused-20261018.log), including 34 new AUDIO-specific cases in `frontend/src/creative/studioAudioTimeline.additive.test.tsx`; `studioAudioTimeline.testFixtures.ts` is a supporting fixture module, not a second suite.
- These raw diagnostic/targeted logs do not replace the source-bound root integration receipt.

Exact terminal commands and complete source hashes are retained in the JSON receipts. The clean existing interpreter was `.runtime/recovered-python-20261018/bin/python`; no installation, model download, paid API, external compute, user Windows access or new execution owner was used.

## Retained red evidence

Initial focused failures remain in `audio-only-file-debug-20261018`, `audio-only-api-debug-20261018`, `audio-only-focused-debug3-20261018` and `audio-only-focused-debug4-20261018` JSON/log pairs. The real fixes were adding sample-count/bit-depth fields to the original public measurement projection and correcting test setup/observations: schema-1 test input must not contain schema-2 role fields, original HTTP validation remains privacy-safe 422 `EXPERIMENTAL_INVALID`, and the render observer must distinguish FFmpeg output from FFprobe reading the same WAV. The final tests retain exact byte, kind, authority, sample, gain and fade assertions.

## Acceptance boundaries

Browser interaction, actual-browser screenshots/geometry/visual regression, user Windows installation/playback, GPU/performance, real-model quality and the full 2-video/2-audio/subtitle product journey are NOT_RUN in this slice. jsdom HTMLAudioElement tests are not actual browser playback acceptance. This implements the bounded independent multitrack WAV path; it does not assert completion of all Audio Studio or all V2 requirements. PUBLIC packaging/catalog refresh remains root-owned and is reported separately.
