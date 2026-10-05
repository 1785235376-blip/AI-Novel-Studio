# Hosted browser and task lifecycle repair

The real Chromium business flow on remote `4e7ca3d3bfcf9908fee7d3a6e80a3d1243b9238a` (Actions run `37277922570`) exposed a stale revision-history cache: after AI Draft acceptance advanced a chapter to version 3, the mounted panel retained the history fetched at version 2 and could not offer pre-AI version 2 for restore. This was a product defect, not a relaxed browser assertion.

The repair keys history by chapter version and an opaque per-scope observer identifier, captures API context, fences late list/detail/restore completions across actor/session/workspace/project/storyline/branch changes including A→B→A, and sends a successful restore through existing App hydration. A newer dirty local buffer is preserved and surfaced in the existing conflict dialog. No session token is placed in revision cache keys. Nineteen new real-QueryClient/App tests cover these behaviors; the focused frontend run passed 49 tests plus typecheck and token lint. See `revision-history-work.md` and its evidence receipts.

The same hosted backend run exposed two late Agent timeout callbacks after synthetic project cleanup. Scheduled timers are now owned by the service, cancelled on completion/cancel, and removed when a project/job has already been deleted. Missing jobs are not recreated; database failures are not silently treated as deletion. The focused timer/Agent/final-dispatch suite passed 75 tests; see `evidence/agent-timer-cleanup.txt`.

Linux CI now installs the existing required ffmpeg/ffprobe dependency and records tool versions, rather than accepting media-test skips caused by a missing codec tool. This does not change the tests' assertions or claim real AI video generation.

These local test results do not replace the required new hosted business browser, PostgreSQL, or native Windows-package CI runs. The previous run's backend lanes were File 2069 passed/45 skipped and PostgreSQL 2073 passed/41 skipped; frontend 548 unit tests, nine geometry/discovery checks and export recovery passed, but one business journey failed at the stale history list. These are historical results for `4e7ca3d3`, not results for this repair.
