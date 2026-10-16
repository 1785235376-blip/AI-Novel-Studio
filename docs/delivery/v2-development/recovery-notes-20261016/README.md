# Recovery-note preview verification bundle

Source base: `fdc19f304a6416d0f003f4b2ed944ceb2c5187d6`.
Scope: display-only cached presentation note/comment inspection; no controller/cache owner or protected-test changes.

## Source-file map

- Changed production owner: `frontend/src/creative/StudioGraphDraftRecovery.tsx`.
- New additive regression suite: `frontend/src/creative/StudioGraphDraftRecovery.notes.test.tsx`.
- Unchanged protected originals included in hash receipts: `frontend/src/creative/StudioGraphDraftRecovery.test.tsx`, `frontend/src/creative/studioGraphLocalDraft.test.ts`.
- Scoped report: `docs/v2/canvas-recovery-note-preview-20261016.md`.
- Scoped status entry: `docs/v2/frozen-capability-ledger-20261016.md`.

## Commands and actual results

Commands 1–4 ran sequentially from `frontend/`, using existing dependencies. No dependency installation/mutation, paid service, browser execution or user-machine action occurred.

1. `./node_modules/.bin/vitest run src/creative/StudioGraphDraftRecovery.test.tsx src/creative/studioGraphLocalDraft.test.ts src/creative/StudioGraphDraftRecovery.notes.test.tsx --maxWorkers=1 --minWorkers=1 --no-cache`
   - Initial: exit 1, 23 passed / 1 failed. Raw unchanged `focused-initial-failure.log` preserves the **new-fixture -0 JSON roundtrip** failure. Original JSON persistence normalizes negative zero to zero; only the new fixture was corrected to ordinary zero after the run ended. No production source or protected existing test was changed to resolve it.
   - Final frozen rerun: exit 0, **24 passed**, 3 files; `focused.log`. Default timeouts, one worker, no cache.
2. `./node_modules/.bin/tsc -b --force`: exit 0, PASS; `typecheck.log` is intentionally empty because success produced no stdout/stderr.
3. `./node_modules/.bin/vite build`: exit 0, PASS; `build.log`. Existing >500 kB bundle-size advisory remains.
4. `node ../scripts/check_ui_design_tokens.mjs`: exit 0, PASS (52 shared UI files); `tokens.log`.
5. Separate Node raw-color scan of changed `StudioGraphDraftRecovery.tsx`, matching `#[0-9a-f]{3,8}`, `rgb(` and `hsl(`: exit 0, PASS; `scoped-tokens.log`. The shared guard alone does not scan this creative component.
6. `sha256sum -c /tmp/recovery-notes-evidence/before.sha256`: exit 0, all four source/test entries OK; unchanged raw `after-verify.log`.
7. `git diff --exit-code -- frontend/src/creative/StudioGraphDraftRecovery.test.tsx frontend/src/creative/studioGraphLocalDraft.test.ts`: exit 0, no protected-test changes.
8. `git diff --check`: exit 0.

`before.sha256` was captured immediately after fixture correction, before the final sequential run. `after.sha256` was recaptured while preserving this bundle and matches it byte-for-byte. `after-verify.log` is the immediate post-run verification. `before-paths` and `after-paths` are raw `git diff --name-only` receipts for tracked files during the frozen source run; Git omits the untracked additive test from these receipts, so it is explicitly included in the source-file map and hash files above. Docs were written after that source run.

Logs are copied byte-for-byte from the local execution evidence. Tool-process exit codes are recorded in this index; no synthetic PASS output was appended to raw logs. The executor clock shown inside raw tool logs differs from the parent session date; filenames follow the task's 2026-10-16 session date, without rewriting raw timestamps.

Browser visual/accessibility/performance acceptance: **NOT_RUN**. Previously reported browser socket EPERM was not retried or bypassed. These mocked/jsdom results do not establish browser, HTTP integration, provider/model or full release acceptance. Parent independent review, manifest refresh and commit remain separate.
