# EDIT04 / AUDIO09: bounded persistent clip links

Base: `d9b2ea4b602af099f133e7ef7e954fb7618979ae`.

Schema 2 optionally owns `clip_links: [{video_clip_id, audio_clip_id, offset_ms}]`.
Each pair references one VIDEO-track clip and one AUDIO-track clip in this
timeline. The existing 30-clip limit bounds the document to 15 disjoint pairs.
`offset_ms` is exactly audio start minus visual start. Normalization sorts pairs
and rejects duplicate membership, missing/wrong-kind clips, unknown fields and
inconsistent offsets. Absent remains absent: no upgrade, default link array or
digest rewrite for old unlinked records. Schema 1 and audio-only schema 3 remain
closed to this field. VIDEO-track still-image clips are eligible too; the link
does not assert that two assets originated from the same recording.

Original `/edit` adds explicit `clip.link {video_clip_id,audio_clip_id}` and
`clip.unlink {clip_id}` descriptors. Existing `clip.move` carries its partner by
the same delta. A batch containing both members at the same intended new
positions moves the pair once. Final normalization retains the original atomic
batch semantics, including overlap/bounds rejection. Lock checks cover both
members. Original source validation, actor/project ownership, history, request
idempotency and CAS remain authoritative. No save store or render engine is added.

The editor's small link/unlink entry uses its current cross-track selection.
The original selection-move compiler expands linked partners once, and each
intent produces one original draft-history entry. The same Timeline CAS save
persists both positions and link metadata; ordinary refresh/read/adopt restores
the pair. Retired callbacks are fenced by editor/selection generations. Direct
numeric inputs and whole-document saves cannot silently retime a retained pair.

Retained links explicitly refuse independent trim, split, slip, source-range,
speed and source-snapshot edits. The service also refuses linked clip removal
and duplication through individual `/edit` descriptors; unlink first. The editor
limits linked moves to each member's original track. Cross-track linked move,
linked trim/split propagation, multi-member groups, source inference and external
interchange preservation are outside this bounded change. To redefine an existing
pair's offset, unlink and save before establishing the new relation. Existing
export/import behavior is not expanded or claimed here.

## Changed surfaces

- `app/services/studio_timeline_schema.py`, `studio_timeline_edit.py`, new
  `studio_timeline_links.py`: optional normalization, closed edits and whole-save guard.
- `frontend/src/creative/studioTimelineTypes.ts`, new `studioTimelineClipLinks.ts`:
  matching DTO validation and link-preservation guard.
- `useStudioTimelineEditor.ts`, `StudioTimelineEditor.tsx`,
  `frontend/src/nle/timelineSelectionMove.ts`, new `TimelineClipLinkPanel.tsx`:
  original draft/history/CAS integration and a shared-primitives entry.
- Dedicated backend and editor regression files.

No Storyboard, playback, export/render proxy, shared shell, token or primitive
file changes. Integration may need ordinary line merging in the two original
editor files if another feature also edits them.

## Validation retained outside the source worktree

`../edit04-audio09-evidence/` holds actual logs and receipts:

- Backend: 13 passed (10 schema/edit cases and 3 real File cases); 3 PostgreSQL
  variants deliberately deselected. File checks prove CAS conflict, history,
  independent owner reopen, unlink persistence, locked partner, bounds, a failed
  batch after a valid move prefix, whole-DTO trim rejection, and original asset
  deletion followed by zero partial durable writes. Assets are valid synthetic
  PNG/WAV imports; no model calls, video rendering or generated-media claims.
- Frontend: 51 passed across the new 5-case editor suite and the two adjacent
  original selection-move suites. Includes original CAS routing, history,
  reopen/adopt, stale-source refusal and retired callback fencing.
- TypeScript: final `tsc -b` passed. The initial attempt identified two test-only
  Testing Library query options, corrected before the successful build.
- Original-component UI fixture: link/unlink controls exercised; 1366x768,
  1440x900 and 1920x1080 screenshots and geometry pass. Header/context/status
  remain 56/44/32; no page overflow or browser errors. Synthetic UI fixture,
  separately labeled, not backend/media acceptance.

Existing task13 demo sources, artifacts and services on 18913/5293 are preserved.
The development worktree uses existing dependencies through a junction, with no
copied dependency tree or historical evidence checkout. Only its owned 5294
visual service and reproducible test data/caches are cleaned at handoff.
