# U11 / U15: local reading, preflight and writing sessions

## Scope and single authorities

- `reader_preflight_v2` has no model dependency. `writing_sessions_v2` requires the exact `workspace_tools_v2` flag. Both remain server-owned, default OFF, and forced OFF in V1 acceptance mode.
- The original chapter repository remains the sole manuscript/history authority. The original novel `writing_goal` remains the project-goal authority; this feature reads its targets and computes display totals only from currently authorized chapters. No project goal is copied into a new store.
- The original task center and its scoped task readers remain the only task projection. New notices project current real task outcomes; they do not execute, retry, approve or create tasks.
- Reader settings/annotations/ignore reasons and optional session/checklist/stopping-note metadata use the existing actor-scoped experimental store with scope, CAS version, current-authority recheck and rollback. These collections do not enter old novel metadata, original writing-goal responses or manuscript exports.
- Each route captures session/branch context, checks the relevant flag and original read/write permission, then rechecks current authority before returning read data or committing a write. A changed actor/scope or disabled feature fails closed.

## Pure chapter reads, including legacy File projects

`reader_sources.authorized_chapter_rows` uses the existing File project lifecycle lock and existing Markdown/order/archive/document-package metadata. If an old document package does not exist, the same original Markdown conversion is performed in memory. It never invokes the materializing File chapter `get/list`, creates a document package, migrates data or writes a manuscript. PostgreSQL reuses its existing read-only document projection. Collaboration requires an injected authorized branch reader; no base-chapter fallback is allowed.

The content revision includes chapter ID, version, branch, rich document and editor text. Lazy timestamp materialization by the original editor does not falsely expire an otherwise unchanged source. Read/preflight tests compare all project-file bytes before and after reading a never-opened legacy chapter, and verify that its absent package remains absent.

## U11 user workflow

1. Open the experimental reader. Read contiguous saved chapters and use the keyboard-accessible TOC. Choose simulated width 390, 768 or 960 px.
2. Each paragraph can open the original editor through a server-validated quote/version/codepoint anchor or receive a private annotation. Showing/hiding annotations does not change prose. Expired quotes are suppressed; old annotations are marked stale and never silently attached to new prose.
3. Configure continuous-punctuation and repeated-English-word checks, plus up to 30 exact literal naming/replacement rules. Chinese repetition can be specified through literal rules. User strings are escaped as literal data, never executable regular expressions or scripts. Findings are advice, not aesthetic enforcement. Ignore a current finding only with an explicit nonblank reason. No automatic replacements occur.
4. Save author-supplied text/media licensing and font declarations. These declarations are not a legal assessment or proof of individual asset licensing.
5. Run a read-only preflight for TXT, Markdown, DOCX, EPUB or PDF. Host input contains only authorized chapter ID/version and saved/unsaved/local-draft/save-failure/unknown status, never local draft text.
6. The result separates file-integrity blockers, warnings and informational restrictions, and shows coverage. It checks authorized chapter content, title-only/empty chapters, current pending generation/task results, stale task/annotation references, explicit chapter media references and byte/hash integrity. PDF font capability comes from the existing PDF exporter. Unknown/unavailable/partial sources remain explicit.
7. Open the real source or original export center to resolve an issue. A preflight does not create an export job or accept AI content. The original export queue still captures and uses its own immutable snapshot; a regression test confirms later edits/preflight cannot change old snapshot output.

### U11 limits

- Maximum 200 chapters, 2,000,000 editor characters and 10,000 paragraph lines per reading scope; 300 returned findings, 300 annotations, 600 stored ignore reasons; oversized inputs fail explicitly rather than claiming a complete check.
- Media integrity covers explicit references in authorized chapters only, at most 100 references and 32 MiB per check. Exceeding the byte budget is an unverified-coverage warning, not a false corruption assertion. Screenplay-wide and full production-package checks remain in their original services.
- Project-wide hidden/deleted/other-branch source titles, counts and annotations are not projected. Completed session statistics are redacted if their source IDs cease to be authorized.
- Rendering is `APP_LAYOUT_SIMULATION`; `target_renderer_verified` is false. The reader is not Word, an EPUB reader, a PDF viewer or an actual file renderer. Font presence is not glyph-coverage or third-party rendering validation.
- External changes are caught at quote navigation and at the end of a preflight scan. The UI requires a new check when known inputs/source state change; it does not claim background monitoring.

## U15 user workflow

1. View the original project's goal. Optionally start one active author/project/branch session with a text goal, character target and up to 30 hand-operated checklist items. Repeated start requests are capture-ID idempotent.
2. Save a stopping note and checklist with CAS, or end the session. Failures and conflicts preserve editable input. Refresh does not silently rebase over another version; the user explicitly restores server state.
3. Completion statistics read the actual current persisted chapters and original version history. Original File and PG histories contain **pre-save versions**, so the exact interval is baseline version <= history version < current version. Duplicate history IDs do not inflate events. Net characters count non-whitespace editor characters, can be negative, and are not personal keystrokes, elapsed effort, a ranking or a streak. Scope is currently authorized surviving chapters; no missing-source count leaks are returned.
4. Notices appear only within the original task center. Deduplication key is authority + task ID + version + status. Acknowledging that event is durable and does not acknowledge future versions. User priorities order urgent/normal/low. Focus defers nonurgent notices; the original editor's save failures remain visible and are additionally surfaced in the task center.
5. Reminders default OFF. An explicit setting selects a future wall-clock time and IANA timezone. There is one owned timer for the next matching time while that task center is mounted. Each opening delivers at most once. Closing/unmounting, scope change, disabled settings, a failed settings read or refresh clears the timer. An in-process preference change notifies the same captured client and clears the owned timer immediately; another window must re-read settings. There is no cross-window background service.
6. Restart/reopen schedules the next future matching minute; missed reminders are not replayed. DST gaps move to the next matching day. The UI states exact timezone and lifetime. No email, OS/browser push permission, external network delivery, behavior tracking, model execution or service process is enabled by reminders.

## Files and composition

- Backend: `reader_sources.py`, `reader_preflight.py`, `reader_preflight_api.py`, `writing_sessions.py`, `writing_sessions_api.py`.
- Frontend: `ReaderPreflightPanel.tsx`, `readerPreflightClient.ts`, `readerPreflight.css`, `WritingSessionPanel.tsx`, `writingSessionsClient.ts`.
- Shared composition (lead-owned): flags/capabilities, original API composition, App/ExperimentalWorkbench and `NoticeCenterAddon` inside the task-center section.
- API prefixes: `/novels/{nid}/experimental/reader-preflight` and `/novels/{nid}/experimental/writing-sessions`.

## Verification checkpoint

Run using `r2-run.sh`, the isolated File profile and pinned pnpm. No local PostgreSQL was started, no Chromium retry was made, no paid/provider calls or credentials were used, and no deployment/push/PR mutation occurred.

- Backend: `tests/test_r4_reader_sessions.py` (20 parameterized contracts) and `tests/test_r4_reader_sessions_mounted.py` (real mounted API). Latest checkpoint: **21 passed; 20 PostgreSQL parameters skipped** because an authorized real endpoint was unavailable. These are not PostgreSQL passes.
- Frontend: `ReaderSessionPanels.test.tsx` plus current `WorkspaceToolsPanel`, `ExperimentalWorkbench` and `WritingFocusPanel` integration checks: **44 passed** in four files. Covers real captured clients/headers/bodies, exact Unicode paragraph jump, TOC focus, failure preservation, stale/permission fences, late old-scope responses, real write request contracts, focus/save failure handling, reminder defaults/timer cleanup and IANA/DST calculations.
- TypeScript build check and existing UI token guard: passed.
- Browser journey `frontend/tests/e2e/r4-reader-sessions.spec.ts` is authored against real File API and React UI, with synthetic content and screenshots requested by the test. Execution is **NOT_RUN / platform-blocked** because Chromium previously failed with EPERM; no retry or substitution is claimed. No target-app rendering or real-browser geometry claim is made.
- Independent next-slice review remains **BLOCKED** by the platform. Implementation tests above are separate evidence and are not an independent review.

Status: deterministic local workflows implemented and composed; File/API/frontend contracts verified. Real PostgreSQL, browser/visual, target-reader rendering and user acceptance are not verified. No model-runtime claim applies to these deterministic features.
