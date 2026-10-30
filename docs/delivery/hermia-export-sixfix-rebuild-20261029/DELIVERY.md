# Export six-fix NEW cumulative rebuild — 2026-10-29 UTC

## Provenance and publication boundary

This is NEW implementation and NEW verification. It is not a recovered copy of the missing original 40-file package or later historical cumulative packages. No GitHub push, main change, merge, release or external publication occurred. The original 40-file approval does not authorize publication of this package.

Public baseline: `395ac26dd2de3d473e56964dbeb9ac9806facb85`.
New first-three parent: `bb427114f0573d2532e1900b96155efc47b58fe3` (already separately retained in Space).
New remaining-three tested commit: `c3a5cc6e3450a331733c92c06dd5eedbfd5b317a`, tree `b3ec647fbeee27cac30b2058a0b54e01975693c2`.
Branch: `work/hermia-export-sixfix-rebuild-20261029`.
The final documentation commit in the package README changes no application/test bytes.

## Cumulative changes

The parent supplies missing-file artifact receipt validation, base64 pre-decode admission, and bounded regular-artifact descriptor reads. This new slice adds:

1. Novel DOCX/EPUB XML 1.0 text filtering now excludes U+FFFE/U+FFFF, while retaining Chinese, emoji and legal higher-plane values. Actual ZIP XML members are parsed; the already-correct industry exporter was not changed.
2. Legacy `content` with `content_encoding=base64` uses the decoded-byte budget, matching raw bytes and `content_base64`; encoded admission and final decoded bound remain enforced. Plain UTF-8 text retains its byte cap. Invalid legacy payloads may now fail earlier during serialization rather than later during persistence/download; this is not evidence of a previously successful corrupt artifact.
3. A fresh same-key/same-novel/same-permission request cannot silently return an export of a different canonical format. Existing ValueError/HTTP 400 boundary returns `EXPORT_IDEMPOTENCY_FORMAT_CONFLICT`. Aliases retain idempotency and the existing snapshot. Existing scope, 24-hour expiry and concurrency semantics remain.

No audio, frontend, provider, execution-owner, cross-cancel, numeric-recovery, VTT, or OTIO changes are included. Those prior local packages are not silently claimed recovered.

## Newly executed verification

- Own exact clean parent suite: 18 failed / 20 passed. Three failures concern earlier rejection of invalid legacy encoding, not distinct successful corruption defects. `baseline-clean.log` is authoritative; exploratory `baseline.log` retained separately.
- Focused new tests plus original export/DOCX/integrity: 130 passed, exit 0.
- Final frozen joint 12-file suite: 177 passed, exit 0, 63.01 seconds. 951 tracked app/test files hash-identical before/after. Commands and exact test identities are recoverable from `joint.xml`, logs and manifests.
- Independent exact parent: 15 failed / 9 passed. Same 24 cases on fixed c3a: 24 passed, exit 0. 601 production Python files unchanged. Includes real queue binary representation cases and both mounted API prefixes with HTTP 400 conflict controls.
- Test groups overlap and must not be summed. Failing cases are not counts of distinct bugs.

Existing Python environment only; no dependencies installed by this slice. Tests use synthetic temporary data and existing POSIX/File runtime. Windows, PostgreSQL, browser UI, live models, GPU, distributed guarantees and full Studio V2 acceptance are not asserted. No budget, permission or limit was relaxed.
