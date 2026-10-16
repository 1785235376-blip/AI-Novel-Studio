# Existing non-WAV media inspection: bounded and cancellable

Baseline: `8a9b1038330977305c3574617548e72b03fc71ed`.

## Scope and compatibility

This prerequisite hardens the original media validator. It does not add an audio delivery format, format selector, module, queue, state owner, provider route, or public response field.

- `inspect_media(data, kind)` remains valid. An optional keyword-only guard observes the caller's existing authority.
- WAV keeps its PCM inspection and exact measurement dictionary. Other containers retain their original MIME, extension, measured duration, codec and validation fields; no new sample-rate/channel properties enter preview or request identities.
- Non-WAV probing and full decode reuse the unchanged `studio_timeline_export.run_guarded_process` through a local import. This avoids a top-level circular import and preserves the established runner and its tests.
- Original server-built argv, file/pipe protocol whitelist, private temporary input files, stream map, 20-second probe limit and 30-second full-decode limit remain. Probe capture is capped at 1 MiB while running; stderr retains only the runner's bounded 64 KiB private diagnostic prefix while excess output is drained. Decoder stdout is discarded.
- Malformed JSON, structures and selected metadata conversions fail closed with a generic decoding error. The original absent-format stream-duration fallback remains. Guard exceptions, including `AudiobookError` and WAV parser-error subclasses, retain their identity.

## Existing owner and lock boundaries

Import inspection receives the original project/feature/incarnation guard. The import route keeps its existing authority contract; it does not gain a new production Host-session requirement.

Production source inspection runs after releasing the asset lease. Its Host guard remains separate from the optional inspection-only audio or timeline attempt guard. The latter polls the original job/Graph fence without recursively re-reading and inspecting sources. Legacy unary source callbacks remain supported when that optional callback is absent.

The original audio owner applies this fence to initial source inspection, trim validation, native trim, output inspection and provider-receipt inspection. The original timeline owner carries the same optional callback through synchronous render/export and queued execution; direct input/output inspections also use its existing execution guard. No job-store polling is installed in the Host guard that runs under asset leases. Existing publication leases, private candidates, cancellation receipts, explicit review and no-automatic-replay behavior remain.

## Verification

Final results and content hashes are recorded in the accompanying sanitized verification JSON. Tests include:

- Actual controlled child processes at the capture limit and one byte above it, fast exit, noisy stderr, spawn/read failures, timeout, guard refusal at each phase, termination/reaping, closed handles and temporary-file cleanup
- Strict malformed native output and exact guard exception identity, including overflow and falsey malformed duration alternatives
- Both import orders and real installed CPU FFmpeg WAV, FLAC, MP3, MP4 and WebM decoding with unchanged dictionaries
- Mounted original import feature revocation and production Host revocation during probe/decode
- Audio first-source cancellation outside asset leases; cancelled synthetic provider receipts without publication or replay
- Original synchronous timeline render/export and queued timeline cancellation during the first source probe/decode, plus real private MP4 output
- Existing native bounds, media lifecycle, workspace, WAV controls and legacy hash, audio, Graph and timeline regression suites
- File and fresh owned PostgreSQL execution of affected contracts, using original migrations and disposable isolated state

Only synthetic media and controlled local test children are used. No model, GPU, external provider, paid API, download, user machine, Windows/device playback or product acceptance is claimed. Legacy callers using the default no-op guard gain bounded native execution, but do not acquire a new job-cancellation contract.

## Paused handoff

All already-running checks finished before this local capture. Final frozen-source checks: File 261 passed / 80 deselected, and fresh PostgreSQL 261 passed / 80 deselected, with no skips or failures. The original harness stopped the PostgreSQL server normally. Earlier broad checks passed 725 File and 737 PostgreSQL cases; each preserved 12 pre-existing optional OpenTimelineIO skips. Their precise pre-test-assertion mapping is retained in the sanitized JSON.

Development and publication are paused at the user's request for local Codex handoff. No further source/test changes, check runs, integration or push were started after that request. Raw diagnostic receipts and owned disposable state remain local and are excluded from the selected commit. The next step is integration/publication only after the user-directed handoff; new FLAC/MP3 delivery profiles remain a separate increment.
