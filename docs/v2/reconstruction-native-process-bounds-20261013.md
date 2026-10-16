# Reconstructed shared native-process capture bounds

## Provenance and scope

This is a new reconstruction from published base
`de23bb50b96f07dac3e96dc0f9a1df9940e494b3`, not recovered implementation or
validation of the historical checkpoint 9 commit. Only
`app/services/studio_timeline_export.py` is changed in application code. The
regression file is additive; all original tests and other process owners are
unchanged. There is no new command endpoint, shell runner, model launcher,
third-party executable, or caller-controlled native command surface.

## Reproduced defects

Three controlled Python-child tests failed against the published implementation
before repair, and failed again when the original module was restored for a
baseline comparison:

- Unused stdout went to an unbounded temporary file instead of being discarded.
- Stderr went to an unbounded temporary file, although only its first 64 KiB was
  eventually read for an error.
- A child could write 2 MiB of captured stdout and exit between polls; the
  original runner accepted that oversized result without raising its limit error.

No actual user media, model, credential, paid API, or GPU was used.

## Reconstructed behavior

- Unused stdout is connected directly to `subprocess.DEVNULL`.
- Captured stdout is drained by the existing owner into the supplied temporary
  destination, with a strict 1,048,576-byte write ceiling. The next byte raises
  the existing `STUDIO_TIMELINE_PROBE_OUTPUT_LIMIT` validation error, including
  when the child has already exited.
- Stderr retains at most its original 65,536-byte diagnostic prefix in memory.
  Further bytes are drained and discarded. A noisy successful tool stays
  successful; nonzero exit retains `CalledProcessError` and bounded private
  `stderr` bytes. Raw stderr is not added to exception text or public receipts.
- Each stream gets at most one 65,536-byte read per loop. Idle polling uses a
  25 ms delay; all iterations and the completion boundary retain the caller's
  authority/cancellation guard and deadline. The deadline also covers final
  draining after process exit.
- POSIX pipes use nonblocking reads. Windows uses a sized `HANDLE` with
  `PeekNamedPipe` before a bounded read, so the existing Python 3.11 minimum
  does not require Windows pipe support added to `os.set_blocking` in 3.12.
  Each pipe has one owner and no reader thread.
- Normal exit, guard failures (including `BaseException`), setup/read errors,
  and output overflow close owned handles. Cancellation/timeout terminates
  the direct child, waits two seconds, then kills and waits when needed. The
  original caller owns removal of its temporary directory and any bounded
  partial stdout file. This is not a new process-tree supervisor.

Platform references: [Python `os.set_blocking`](https://docs.python.org/3/library/os.html#os.set_blocking)
and [Microsoft `PeekNamedPipe`](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe).
These references explain the implementation choice, not actual Windows acceptance.

## Verification

The original `scripts/run_v2_checks.py` was used without edits, with owned
`.runtime` data/home/cache paths plus explicit `.runtime` pytest and temporary
paths for final verification. The source snapshots were unchanged during the
final checks. Sanitized counts, timestamps, and source hashes are in
`reconstruction-native-process-bounds-20261013.json`; raw runner output stays
local and is not committed.

- Additive suite: **29 passed**. Covers exact stdout boundaries, one-byte and
  fast-exit overflow, simultaneous streams, multi-MiB stderr floods, bounded
  private diagnostics, refusal before launch, cancellation, timeout,
  terminate-to-kill escalation, child reaping, handle cleanup, final guard,
  post-exit drain deadline, and eight synthetic Windows pipe cases.
- Actual CPU native check: encoder listing, one-second generated MP4, and
  `ffprobe` output proof passed through the repaired runner. Installed tools:
  FFmpeg/ffprobe 7.1.5; Python 3.12.14 on Linux.
- Combined additive and original related suites: **111 passed, 33 skipped,
  1 failed**. The failure is explicitly preserved below; this is not a full
  green-suite claim.

Original related files were `test_r2_media_lifecycle.py`,
`test_r2_media_api.py`, `test_v2_independent_media_job.py`,
`test_v2_media_prerequisites.py`, `test_surface_freeze_media_engine_adapters.py`,
and `test_audio_production_api.py`. The published checkout has no dedicated
shared timeline-export/Whisper test suite; the new native integration test is
additive evidence rather than a claim of recovered coverage.

### Pre-existing failure

`test_surface_freeze_media_engine_adapters.py::test_real_model_adapter_requires_original_runtime_admission[file]`
fails identically with the original published module and with the repaired
module. The frozen assertion expects
`NOT_CONFIGURED_ORIGINAL_MEDIA_RUNTIME_REQUIRED`, while published code returns
`ORIGINAL_AUDIO_MODEL_NODE_EXPLICIT_REGISTERED_LOCAL_ROUTE_REQUIRED`. Its
source and test were not changed. This is unrelated to process capture and
remains an open baseline mismatch.

## Limits

Actual Windows, real PostgreSQL for this work package, user models, GPU quality,
full-repository tests, hosted CI, and publication were not run. Windows tests are
synthetic only. Other subprocess owners are outside this change, including the
separate subtitle-alignment implementation. Historical feature classifications
and historical validation claims are not promoted by this reconstruction.
