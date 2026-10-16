# B04 subtitle file handoff preflight — 2026-10-16

Baseline: `f48b0dd14d18a728b50720bb85d0d1f53379c7a9`. Delivery is the containing local commit. Status: **PARTIAL**, bounded advisory workflow implemented; direct exact-bound cross-owner adoption remains unavailable.

## Audit before edits

- Original `app/experimental/subtitle_timeline.py` / `_api.py` and `SubtitleTimelinePanel.tsx` already own manual tick editing, measured media, speaker/source snapshots, versioned save, split/merge and SRT/WebVTT download with readback. No replacement exporter was needed.
- Existing `StudioTimelineTransferPanel.tsx` / `useStudioTimelineTransfer.ts`, `studio_timeline_subtitles.py`, original Timeline normalization and transfer owner already provide UTF-8 file selection, preview, replacement confirmation, target source/version/digest validation, loss acknowledgement, original saved version and UNKNOWN receipt recovery. Export/render/asset handoff were not rebuilt.
- There is no direct subtitle record → Timeline adoption contract carrying source track/version/asset snapshot, placement/trim/speed mapping and speaker identities. A sidecar carries only text and milliseconds. Neither its filename nor a local report supplies provenance, authorization or a target binding.
- Caption owner permits more text/cues than Timeline. A valid source download can therefore fail import. Timeline accepts 500 cues, 1000 Unicode codepoints per cue, 32000 total, one to eight nonempty literal lines; original source permits 2000 cues and longer text. Speaker names consume target text limits. Fractional ticks floor to milliseconds and can collapse a cue.
- Caption save uses expected version and original source checks, but this existing UI does not provide durable unsaved recovery, a caption history/restore control, or Timeline-style exact UNKNOWN write receipt reconciliation. These remain gaps; no retry/rollback guarantee was invented. Cross-owner one-click rollback is absent. Existing Timeline import replaces all captions and saves a new original-owner version after confirmation.

## Implemented useful slice

The existing subtitle editor exposes an explicit local compatibility check, live against its current local input. The report identifies unsaved input versus saved track/version/media identity; shows exact BigInt rational tick-to-millisecond preview and precision loss; checks safe integers, ordering, media range, nested overlaps and overlap reasons, missing speaker bindings, duplicate IDs, Unicode/literal/line and aggregate target limits. Per-cue issues focus the original text editor for correction. It never edits, sorts, truncates or generates a subtitle file itself.

Checks are advisory, not a new owner validator. Target Timeline duration/current source and actual file byte limits still require original import preview. Dirty inputs must first be saved; original download remains disabled while dirty. The report disappears while unavailable/loading/version-conflicted/stale and resets with original client remount. It states that speaker IDs, overlap reasons, source/version provenance are lost in SRT/VTT while speaker labels become literal text; file import does not auto-offset, scale or bind media. Existing explicit file download → original Timeline file selection → preview → human confirmation is the next step.

No new API, store, permission, backend change, provider, ASR or alignment quality claim. No automatic navigation that could discard a Timeline draft. Shared primitives/tokens and original module layout retained; canonical VIDEO reference inspected.

## Verification

See adjacent JSON for commands, exit codes, source and log hashes. Final runs: 75 mocked UI/pure checks; twelve original renderer/parser compatibility cases; one original nonsecurity File measured cue/split/merge/export/restart case; 30 PUBLIC checks; forced TypeScript/Vite build, discovery, token guard, diff check and 487-file PUBLIC closure. Original caption exports really pass through the original Timeline parser in the compatibility tests, including UTF-8, speaker flattening, overlaps and rational timing; unsupported literal content and shorter targets are rejected. These pure tests do not claim target owner persistence or a full cross-module browser journey.

Retained initial failure: six new parser tests supplied an invalid empty video track, receiving `STUDIO_TIMELINE_CLIP_LIMIT` before caption validation. Corrected the synthetic target fixture to include a valid pinned clip; no production behavior or assertions were relaxed. Earlier successful build occurred while that new test was added; final stable-source rerun supersedes it.

Browser/native/visual/HTTP integration, PG/P0/security lifecycle, Windows/GPU/provider/real ASR or alignment quality/full RC: NOT_RUN. P0 remains BLOCKED, R3-GATE HOLD, production Prompt Adoption disabled. No browser workaround, user computer, saved environment, push or hosted CI; CI cost unknown. Preserve all previous receipts. Parent independent review before next tracked slice.

Independent review corrections: defer computation until explicitly open/available; refuse over-500 collections before scanning/rendering and bound huge unsaved text; match original source timebase maxima; retain track ID/version beside dirty notice. Original renderer readback rejects CRLF/NEL/Unicode line separators and final trailing whitespace: advisory warnings and five original-owner negative tests now cover these without normalization or backend edits.
