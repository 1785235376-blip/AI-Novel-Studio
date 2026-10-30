# Independent shared WebVTT consumer review

All production parse_subtitle_cues callers mapped: Studio import_subtitles sends parsed cues through its existing timeline normalizer; experimental SubtitleTimelineService.import_preview sends them through Cue, _validate and render_captions, preserving exact tick representability and read-only preview. B04 download calls render_captions, which calls read_captions only as exported-byte self-check. No other production parser callers found by git grep.

Baseline distinctions, captured in baseline-roundtrip.json and expanded-roundtrip.json with loaded module paths:
- Frozen342 already changed authored literal &amp; into & on B04 export/import (pre-existing emitter bug).
- Frozen342 preserved authored &#65;, &copy;, &NotEqualTilde; while frozen46 (new broad shared decoder) changed those to A, copyright, and two-codepoint not-equal respectively (introduced regression footprint).
- R&D stays same plain text, although correct external VTT emission still requires escaping ampersands.

Initial22 authored-export/readback/import/SRT/empty fixtures each yield13 fail/9pass on342 and46 because fixtures also require correctly escaped emitted bytes. Those counts are not measures of introduced regressions; use the explicit matrices above. Added4 original B04 owner rejection controls for decoded low control, DEL, markup and blank-line text; these are parser-to-Cue boundary tests, not HTTP tests.

Reviewed candidate production delta: shared single-pass decode_vtt_text helper; B04 VTT emits escaped composed cue+speaker text and decodes only cue text for its own readback. Does not replace B04 parser shape/timing/empty contract with Studio parser and does not migrate stored records or rewrite history. SRT branch remains byte-identical. Actual HTTP tests are implementation sibling's separate evidence.

## Final frozen verification
Independent git archive of 94c4fcb2d2e938d6e0fbccc58f0678ef0fd9530c passes81 cases: 41 WebVTT reference/Studio owner controls, 11 clip-link receipt controls, 3 genuine native OTIO0.18.1 controls, 22 caption authored-export/readback/import/SRT/empty controls, 4 B04 original owner rejection controls. No skips, pytest exit0. app/tests manifests identical before/after; loaded paths and SHA256 recorded in fixed-module-provenance.txt. No production review findings. This review did not mutate production or persisted user data.
