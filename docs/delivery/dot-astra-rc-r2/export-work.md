# D02 / D08 / D09 export and screenplay work

Date: 2026-10-05. Integration branch: `work/dot-astra-v1-rc-r2`. Starting baseline: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`. This report describes the working-tree checkpoint tested before the integration owner's commit. The final delivery receipt must supply the exact committed SHA and hosted CI results; these local results are not a claim that a later SHA has already passed.

## Delivered behavior

### D02: Fountain structure and authenticated recovery

- Reproduced AN-AUDIT-04 using the complete independent `fountain-js@1.2.4` parser. Baseline tokens show numeric and mixed-case/non-Latin cues becoming Action, blank dialogue paragraphs becoming Action, and the two-line uppercase action becoming a character/dialogue pair. The parser also exposed provenance metadata entering the screenplay body. Synthetic before/after token evidence is in `evidence/fountain-before.json` and `evidence/fountain-after.json`.
- Emit explicit `@` character cues preserving authored case, force each action paragraph, and use exactly two spaces for intentionally empty dialogue lines. Protect literal emphasis/boneyard delimiters. Put provenance in the title-page Notes field. A terminal empty forced-action continuation works around the independent parser's automatic `TO:` precedence while keeping the authored line an Action token.
- Unsupported ambiguous literal `[[...]]`, dialogue consisting of a parenthetical, and multiline/dual-dialogue cue injection fail explicitly with `EXPORT_SCHEMA_INVALID`; Word/JSON remain alternatives. This avoids silently hiding or reclassifying user-authored material. The implementation does not claim universal app compatibility.
- `GET /api/exports` discovers durable tasks with exact actor/workspace/project/storyline/branch scope, status filters, bounded pages, and fresh membership authentication on every request. Individual reads, cancellation, retries and downloads separately reauthorize the persisted owner/scope. Revoked access and another actor cannot reuse an old task ID. Turning collaboration runtime off does not unlock a persisted collaboration job.
- API lifecycle responses exclude source snapshots, raw file bytes and artifact filesystem paths. They retain `snapshot_id`, source version metadata, recovery/attempt counts, resource diagnostics and file metadata.
- ExportPanel lists history and automatically rediscovers the latest task on reopen; displays full snapshot identity, status, retry/cancel/download, errors and pagination. Scope/session changes remount the observer and use an opaque per-mount cache identity. No session token is stored in a query key or browser storage.
- Every export request receives the captured React-prop request context explicitly, closing the interval before App's API-context effect updates global state. Late old-scope results remain fenced. Auth/history errors hide stale results.
- Legacy screenplay/shot-list/storyboard previews also use authenticated branch-filtered snapshots in collaboration mode rather than bypassing the durable routes' scope boundary.

### D09: resource ZIP connected end to end

- `screenplay-package`, `shot-list-package`, and `storyboard-package` are real supported queue/API/UI formats. The legacy direct industry-format endpoint stays closed; packages require a durable snapshot.
- Capture exact resource bytes at task creation, bounded to 25 MiB per resource and 64 MiB total resources. Validate safe identity before any loader call; validate project/branch ownership, declared byte length and SHA-256. Asset metadata and bytes are deep-captured, encoded and persisted with the task.
- A dedicated frozen reader accepts only captured payloads, rechecks identity/scope/size/hash and encoding limits, and cannot open paths/URLs or consult the live asset library. Replay after assets or screenplay change therefore produces the original captured data.
- Queue package exports require all referenced resources. Missing, foreign, unsafe, oversized or corrupted assets produce a failed task with explicit resource diagnostics, never a successful partial ZIP. Pure builder `allow_missing` compatibility remains separate from the queue's strict policy.
- ZIP manifests contain snapshot/source versions, safe package paths, actual resource sizes/digests and the exact entry list. Existing deterministic ZIP and OOXML builders are reused.
- Artifact downloads perform bounded reads and verify declared size/hash. An exporter without a decodable file can no longer publish a success state.

### D08: safe revisions, authorable structure and storage concurrency

- New screenplay creation records its branch. List and all screenplay-ID routes are branch/membership guarded; unscoped legacy screenplays are not silently assigned to a branch. The separately authenticated provider callback remains under the media worker's callback contract.
- Approved screenplays can explicitly fork a new draft, from the current or an identified historical edit version. The new draft retains chapter/source provenance and `derived_from` metadata. Approved originals and their downstream shots/assets/tasks remain unchanged; the draft must go through review/planning again.
- File and PostgreSQL now maintain a distinct storage `edit_version`, independent of screenplay/shot/storyboard/transition revision counters. Every ScreenplayService mutation passes the version it read into repository CAS. Stale writes raise the existing `VersionConflict` / HTTP 409 contract; they are not retried with overwritten content.
- File CAS/history is protected by the existing cross-process mutation lock and one atomic JSON replacement. PostgreSQL locks the Novel row before reading/modifying its metadata. Other existing whole-metadata writers use the same lock to avoid erasing screenplay changes with stale metadata.
- `version_history` is generated from persisted state, omits nested history and cannot be supplied/erased by a caller. It includes old screenplay/scene/shot and associated state. The current list response omits that potentially large array; the authenticated `/screenplays/{id}/revisions` route exposes history on demand. Export snapshots omit old history and record the current edit version.
- Scene UI exposes heading/time/location/cast/action/dialogue/emotion. Shot UI exposes shot size/angle/camera movement/composition/action/dialogue/sound/duration. Approved scene and shot controls are frozen.
- Scene/shot/storyboard/transition/asset editors retain their originally displayed expected version. A 409 refreshes the server view but preserves local fields. The user sees the latest snapshot and explicitly chooses whether to load it or keep their local values against that new version. No automatic retry/last-write-wins behavior was added.
- Screenplay UI includes loading/empty/error states, scoped cache identities, revision history and fork actions. Core AppShell/design tokens/geometry remain unchanged.

## Local verification actually run

All backend runs used isolated HOME/XDG/data/temp directories, File storage, synthetic data, memory credentials, offline/model-disabled settings and no paid API calls.

- Focused backend checkpoint: **133 passed**, one upstream Starlette/httpx deprecation warning. Includes existing export queue/snapshot/resource integrity regressions, new authenticated history/recovery/ZIP cases, screenplay File CAS/history/new-process/concurrency cases, branch/revision API checks, and existing screenplay/shot/video contracts. Receipt: `evidence/export-backend.txt`.
- Frontend checkpoint: **72 passed in 6 files**, including **21 complete independent Fountain parser cases**. The parser receives actual Python exporter output, not a hand-written fixture or finite replacement lexer. Also covers history remount/download, late result fencing, request-context timing, screenplay controls and 409 draft preservation. Receipt: `evidence/export-frontend.txt`.
- `npx tsc -b`: PASS. `node scripts/check_ui_design_tokens.mjs`: PASS (39 checked files). `git diff --check`: PASS.
- The new browser test uses the real frontend, HTTP routes, durable export queue and filesystem with synthetic trusted-session/membership authorities. It creates a task, closes/reopens the page, finds the identical job/snapshot, downloads actual bytes, changes actor/branch and checks desktop overflow at 1366/1440/1920 widths. **NOT_RUN locally past browser launch**: bundled browser download was unavailable; `/usr/bin/chromium` then failed at `process_singleton_posix.cc` with `socket() failed: Operation not permitted`. Both blocked receipts are retained. No screenshot/geometry pass is claimed.
- **Three real PostgreSQL tests added, NOT_RUN locally**: simultaneous same-version writers, concurrent unrelated metadata writer preserving history, and new-process history reopen/stale-write rejection. `tests/test_screenplay_cas_postgres.py` is explicitly `postgres_backend_only` and needs the disposable CI PostgreSQL URL. The integration owner must report the hosted result separately.

Commands:

```text
python -m pytest -q tests/test_screenplay_cas_history.py tests/test_screenplay_branch_revision.py tests/test_phase8_screenplay.py tests/test_phase8_shots.py tests/test_phase1_video_runtime.py tests/test_industry_export_queue.py tests/test_export_jobs.py tests/test_export_history_recovery.py tests/test_export_resource_packages.py tests/test_industry_export_independent_audit.py tests/test_industry_resource_integrity.py tests/test_export_snapshot_and_import_review.py

cd frontend
npm test -- --run src/novel/ScreenplayPanel.test.tsx src/novel/ScreenplayPanel.revision.test.tsx src/novel/ExportPanel.test.tsx src/novel/ExportPanel.scope.test.tsx src/novel/ExportPanel.recovery.test.tsx src/novel/FountainParser.test.ts
npx tsc -b
node ../scripts/check_ui_design_tokens.mjs
npx playwright test --config playwright.export.config.ts
```

The browser config requires an isolated `NOVEL_DATA_PATH`, Python test dependencies, frontend dependencies and a working Playwright browser. It starts a synthetic fixture API on loopback port 8018 and Vite on 5178. Do not expose the fixture server or point it at user data.

## Boundaries / release checklist

- D02 code is connected and contract/parser verified. Browser closure/reopen and Windows application import remain independent acceptance gates until hosted/native evidence exists.
- D09 resource ZIP is connected and tested with actual archives and bytes. Word/LibreOffice rendering, final-font licensing/embedding, PDF/EPUB typography and Windows target applications were not verified here. Do not label the entire document-quality work package complete.
- D08 gains durable CAS/history/forks and fuller authoring. HTTP scene/shot/storyboard/transition/asset edits, approvals and revision forks require `expected_version` in every runtime mode; omission returns 428 and stale values return 409. Legacy functional test clients were updated to read the visible current version before those writes, retaining all prior content/state assertions. Internal service operations may omit an editor-origin version but still use their captured read version for repository CAS. Older external clients must update to send the precondition. Motion-task editor preconditions are tracked separately with the media work.
- Version history and export snapshots intentionally persist locally. They are not auto-pruned; very large long-running projects need a separate retention/compaction design. No retention/deletion policy was invented in this task.
- Existing pre-upgrade ownerless export records are not adopted into another collaboration user. Existing unscoped screenplays/assets are not automatically assigned to a branch. An explicit ownership migration/recovery workflow remains future work; local legacy data stays accessible in its original local profile.
- No schema migration is required for the new screenplay JSON fields. Existing records start at edit version 0 and gain version/history on the first CAS save. PostgreSQL execution is still a hosted-CI gate.
- Real Windows, WebView2/Host, real models/GPU, production credentials and paid/cloud generation were NOT_RUN. These tests use no real manuscript or personal assets.

## Opus UI handoff additions

Primary components: `frontend/src/novel/ExportPanel.tsx`, `ScreenplayPanel.tsx`; styles: `export.css`, `screenplay.css`; shared Button/Badge/Panel/EmptyState and existing design tokens are reused. Preserve observer remounts, opaque cache identities, explicit captured request context, 409 local-draft retention, explicit revision fork, frozen approved controls and the strict resource-package error state. History JSON previews are functional, not final visual design. Browser screenshots should be captured from the real tests after a supported Chromium run; none were manufactured locally.

## Public precondition hardening follow-on

After the 133/72-test checkpoint, editorial HTTP missing-precondition handling was tightened to 428 in all runtime modes. New direct HTTP checks prove omitted versions do not change state; existing stale409/no-overwrite checks remain. The additional regression receipt is `evidence/screenplay-required-cas.txt`; use its actual result rather than assuming the earlier checkpoint covered this change.

The all-mode mandatory-precondition follow-on regression ran successfully: **45 passed**, one upstream deprecation warning. It includes the existing phase8 functional tests, media API tests and direct missing428/stale409/no-overwrite checks. This is an additional overlapping focused run, not 45 tests to add to the 133-test checkpoint as a unique total.

Fountain sources: [official syntax](https://fountain.io/syntax/) and [independent complete parser](https://github.com/jonnygreenwald/fountain-js). The parser is MIT-licensed and test-only; production exporters remain provider-free.

Scope clarification: chapter prose still follows the existing project-owned manuscript contract. This work gates task ownership and branch-owned screenplays/assets; it does not invent a separate physical manuscript per collaboration BranchRevision.
