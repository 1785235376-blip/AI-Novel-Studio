# B04 measured-media caption import UI

## Bounded functional slice

The existing measured-media `CaptionEditor` now supports explicit SRT/VTT file selection, a read-only server conversion preview, explicit replacement of all local cues, and the original versioned `saveCues` action. Preview and replacement do not save or retry automatically. Existing local cues remain untouched through file selection, file reading, server errors and preview display; replacement requires the clearly labeled confirmation button. Dirty cue and split inputs are disclosed before replacement, and accepted cues remain visibly unsaved until the original save succeeds.

The native file input accepts `.srt`/`.vtt` names. Actual files must contain 1–192000 bytes of strict UTF-8. The client sends the original bytes as base64 and hashes those same bytes; CJK, emoji, UTF-8 BOM and CRLF are preserved. The original backend performs lexical, exact-rational timing, duration, overlap, text and export/read-back eligibility validation. UI rendering displays returned integer ticks without quantization. There is no ASR, timing adjustment, inferred speaker binding, rendering or new persistence owner.

Preview acceptance checks the exact record/version, asset ID/snapshot version/digest, timebase, format, byte length and SHA256. The response must contain bounded nonempty unique cue IDs and bounded nonempty text; local replacement copies only original Cue fields. File selection, draft edits including split controls, record/media/source changes, refresh, original save/split/merge admission, client/scope replacement and unmount invalidate retained handlers and stale responses. An obsolete hung read does not block a fresh preview after the owner changes. Synchronous locks block duplicate preview submissions and acceptance reuse.

The UI uses existing shared primitives and existing panel/action classes; no shell, token, dependency, manifest, guard or protected original test was changed. Caption transfer review, export and original save behavior remain in their existing owners.

## Verification and limitations

[Raw UI evidence](../delivery/v2-development/caption-import-ui-20261017/README.md): 71 unique focused tests passed, including 38 new additive import tests. These exercise mocked-transport jsdom UI and pure helpers; they are not real-browser file-picker or full E2E evidence. Forced TypeScript, production build and the original 52-file token guard passed. Frontend source hashes remained identical during all four commands. No browser/visual/geometry acceptance was run in this slice.

[Backend evidence](caption-import-preview-backend-20261017.md) separately records 109 passes with 96 PostgreSQL cases deselected, including actual in-process File-owner persistence and export. The UI and backend runs do not establish a live full-stack browser workflow.

An ambiguous original save failure preserves the local imported cues and does not trigger automatic retry. The original caption save owner does not have a durable UNKNOWN lock or exact write-outcome reconciliation, and this import slice does not add them. Explicit later user actions remain governed by that existing owner. Unsaved drafts remain session-local; crash recovery is not claimed. Broader B04, PostgreSQL, target-platform, actual subtitle-tool compatibility and full-release acceptance remain open. No push, merge, release, paid service, credential or user-computer action was performed by this slice.

Independent follow-up verification reran the 38 additive import cases successfully with default timeouts, one worker and no cache, preserving 1,275 frontend files. A separate independent backend run passed 63 cases with 62 PostgreSQL cases deselected and stable source. These are overlapping confirmations, not additional unique counts on top of 71 UI / 109 backend. The [final source-slice review](../delivery/v2-development/caption-import-ui-20261017/dot-caption-final-source-review-20261017.json) binds all seven source/test files and confirms protected surfaces unchanged. Parent inventory/commit handling remains separate.

## Raw evidence whitespace

The full staged whitespace check reports six trailing-whitespace lines in the preserved failed backend r1 traceback and two EOF blank lines in the original Vitest logs. These are raw evidence bytes and are intentionally unchanged. The separate source/test/documentation check excludes only raw log files; it passes. This is not a claim that the full staged check passed.
