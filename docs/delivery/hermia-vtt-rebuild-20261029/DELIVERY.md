# NEW VTT literal rebuild and real OTIO regression

This is new implementation and new evidence. It is not the missing historical VTT artifact, nor the approved original 40-file upload. No GitHub publication occurred.

## Source
- Public ancestor: `395ac26dd2de3d473e56964dbeb9ac9806facb85`.
- Immediate baseline: new six-fix export rebuild `faede394ee2891d69851022f000ae4b66276de62`.
- Production/test freeze: `f007fb4ea5096c3904e02f1f521600defa1f83ce`, tree `27c5a577a4343c430c085c4ab628992f23c6dccb`.
- Production delta for this slice: only `app/services/studio_timeline_subtitles.py`. Added VTT tests and copied the actual successful OTIO test file verbatim from commit `2a5d099ac549096e656e5cce6a634d6db4a597c1`. Other production files are unchanged from the new six-fix baseline.

## Behavior and scope
Literal caption strings containing reference spellings such as `R&amp;D` or `&lt;tag&gt;` were previously exported verbatim and interpreted differently by actual FFmpeg WebVTT decoding. Export now escapes ampersands once, preserving authored strings, including numeric-reference spellings such as `&#65;`. Import performs one decoding pass for the bounded `amp`, `lt`, `gt`, `nbsp`, `lrm`, `rlm` subset before the existing owner normalizer. Decoded forbidden markup is still rejected. SRT is unchanged.

Important correction: the current [W3C WebVTT draft](https://www.w3.org/TR/2026/CRD-webvtt1-20260520/), sections 4.2.2 and 6.4, delegates to broader HTML character-reference parsing. Any prior statement that the specification supports exactly six references is withdrawn. This implementation is an intentionally bounded plain-text importer, not full WebVTT conformance. External unescaped numeric/other HTML references are outside the validated import subset and retain existing literal behavior. This does not prevent our own exported literal strings from round-tripping safely. General external WebVTT styling/entities need a separate compatibility contract.

## Actual new validation
- Final immutable-baseline codec suite: **10 failed, 4 passed**, exit 1, against `faede394`; `baseline-final.log`. Failures are authored-literal corruption, required supported decoding, and decoded-markup rejection, not ten separate production defects.
- Fixed frozen joint suite: **31 passed**, exit 0, in 19.47 seconds. Includes 14 codec checks, 12 actual OTIO/dual HTTP checks, and 5 existing history/identity checks. `joint.log`, `joint.xml`, `joint.exit`.
- Joint 922 Python source/test hashes were recorded before and after and match exactly (`before.json`, `after.json`).
- Independent exact frozen suite: **13 passed**, with exact baseline **9 failed / 4 passed**; 601 production Python file hashes unchanged. Actual FFmpeg display, both API prefixes, import/export/replay, readonly preview, and history restoration included. See `independent/REVIEW.md` and raw evidence. Do not add overlapping test counts.
- Real installed official `opentimelineio==0.18.1` used; no new dependencies installed for this slice. FFmpeg was already installed.

## Honest exploratory records
`baseline.log` is an initial 13-case run (10 failed / 3 passed), superseded by the final 14-case baseline. Two archive setup failures omitted required local interoperability modules; these are retained as `baseline-fixture-*` and excluded from product failure counts. `fixed.log` is an exploratory 25-case pass during test finalization and is not the final freeze evidence. Only the final joint fixed-source run is the final claim.

The independent report discloses its initial archive/collection and an after-test system-Python provenance attempt; corrected interpreter/archive evidence is recorded. No test result is inferred from an unfinished process or XML alone.

## Limits
POSIX/File synthetic service and mounted HTTP endpoints only. No browser, Premiere/Resolve/NLE, Windows, PostgreSQL, real model/GPU, or hosted CI claim. No audio-history owner, frontend, or Work-private source changes. No old unseen cumulative code was restored. No merge, Release, deployment, or GitHub upload.
