# Explicit PCM16 timeline source bounds

The original saved timeline now exposes an explicit read-only `source-bounds` POST beside `waveform-preview`, under the same original route, host, scope, incarnation, timeline version/digest and source pin checks. It uses the same bounded pinned Asset reads and pure PCM16 validator. No FFmpeg/native decoder, model, job, cache, asset, history entry or timeline change is created.

Unlike waveform preview, this observation can report a saved clip whose requested range extends beyond the real source. It validates all declared PCM data, then returns exact frame count/sample rate, rational duration, requested frame bounds, an integer-millisecond maximum out point and `within_source`. The frontend checks the closed response against the selected saved clip and shows the measured limit and warning. Selection, draft, identity or authority changes retire the observation; it never automatically trims, saves or renders.

The original generic Save contract is deliberately unchanged. A 9-second source span over a genuine 6-second WAV can still be saved, and the new explicit check truthfully reports it out of bounds. This feature is diagnostic, not a new persistence rule or full render certification. Existing waveform preview still rejects an invalid source interval.

## Evidence

- `timeline-source-bounds-file-r1`: 100 PASS, five new tests plus unchanged original waveform and mounted API tests. Actual saved 9-second range / real 6-second PCM source, fractional sample limits, truncated full-data rejection, stale pins, authority denial and no durable writes are checked. Original generic Save was not weakened or replaced. A synthetic real File fixture supplies the UI test.
- `timeline-source-bounds-pg-r1`: 4 PASS on genuine PostgreSQL 17.11 project/timeline owners with the original filesystem Assets, reusing `v2_director_pending_green_20261018`, OID 31303; server stopped normally. No fresh-migration claim.
- `timeline-source-bounds-ui-r1`: FAIL, 3 new tests failed because a new re-export lacked its source-module binding; 30 passed, including all 29 unchanged waveform controller/mounted timeline tests. The production re-export was fixed; original tests unchanged and failed receipt retained.
- `timeline-source-bounds-ui-r2`: 33 PASS, TypeScript PASS, production Vite build PASS. Existing large-chunk warning remains.

## Remaining boundaries

Only bounded mono/stereo PCM16 WAV up to 8 MiB / ten minutes is supported. MP3, FLAC, video/VFR, target Windows/native execution and full product-browser acceptance are not claimed. The observation is ephemeral and is not passed off as a saved edit, media approval, generic validation of all sources or V2 release readiness.

## Explicit local-draft repair followthrough

After a valid out-of-bounds observation, the editor can preview shortening only the selected clip's source out point to the measured integer-millisecond maximum. It requires explicit confirmation and applies through the original `c.change` local history owner. No file, other clip, subtitle, placement, service save or render is changed. Locked tracks, changed drafts/pins, an empty remaining range, and original speed/fade/transition constraints reject the proposal. Source/identity/revision changes invalidate consent; consent is consumed synchronously and unmounted or repeated retained callbacks cannot apply it again.

`timeline-source-repair-ui-r1`: seven focused tests, TypeScript and production build passed. Before finalizing, lifecycle and synchronous-consent guards were added with another regression. `timeline-source-repair-ui-r2`: eight focused tests, TypeScript and production build passed. These are UI/pure-helper checks, not a product-browser or end-to-end save/undo claim. The generic backend Save contract remains unchanged.
