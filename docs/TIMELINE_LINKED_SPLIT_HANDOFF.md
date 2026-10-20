# EDIT04 / AUDIO09: one saved VIDEO/AUDIO pair, linked split

Base: `11b53ede67259f7c2d81fb495e1b1dcfdfb7ce9c` (archive `a74c483993fef6bacc113354969b50d62d7baef5`). This slice adds an explicit split for one persisted link on the existing timeline owner. It does not change the timeline schema or introduce persisted fields. Existing link/move behavior is reused.

## Small contract

Schema 2 `clip_links` retains its existing `{video_clip_id, audio_clip_id, offset_ms}` format. For video start V, audio start A, saved offset d=A−V and video-referenced cut t:

- u=t−V must be an integer strictly inside `(0, min(video.out−video.in, audio.out−audio.in))`.
- Video cuts at t; audio cuts at t+d. This is the shared relative playback interval. It is not an instruction to cut both clips at the same absolute time.
- Both original IDs remain the left segments. Two explicit fresh IDs identify the right segments.
- Each left segment keeps its original start/in and ends at original in+u. Each right segment starts at original start+u and uses `[original in+u, original out)`.
- Both resulting pairs keep offset d, the same tracks, exact source snapshots and all other clip properties. The two source ranges join without a gap or overlap. Unrelated clips remain unchanged by the operation.

The first slice accepts actual `video`/`audio` assets at `speed_num=1, speed_den=1`, with neither member locked, no fades, and no incoming/outgoing transition touching the pair. Static images on VIDEO tracks, speed changes, transitions, fades, boundary/outside cuts, missing/stale sources, reused IDs, clip/link capacity overflow and batches containing other operations are rejected atomically. Original `clip.split` still refuses linked members. No path silently unlinks the pair.

## Original edit / Save / history

New edit operation, alone in the existing `/edit` operation array:

```json
{"op":"clip.split_linked","video_clip_id":"picture","audio_clip_id":"sound","at_ms":1400,"new_video_clip_id":"picture-tail","new_audio_clip_id":"sound-tail"}
```

The existing request digest/version/idempotency and authorization checks stay authoritative. Whole-DTO Save accepts the result only when the retained pair and a new tail pair exactly match the four-clip partition derived from the prior persisted DTO; altered source/range/property, missing tail link or changed offset fails. One pair may be split per Save. No split marker is persisted.

The original UI requires a saved, clean draft with current sources. Its existing selection and video playhead feed the explicit panel. The controller records one original history entry; Undo before Save restores the pair and Redo retains the same tail IDs. Save uses the original CAS route; accepting a saved revision clears local history under the existing editor contract. The prior revision remains in original server history. This slice does not add linked merge or a new revision-restore operation.

Old callbacks are fenced by client/context, draft generation, selection and playhead generations. A repeated callback cannot allocate another accepted split or write partial state. New IDs are allocated only after the original editor fence succeeds.

## Reproducible example

1. In the existing VIDEO editor, create a schema 2 timeline with a 1× video clip `picture` at start 1000ms, source `[100,900)`, and an audio clip `sound` at start 1250ms, source `[50,850)`. Use current imported local video/audio assets. Link the pair using the existing explicit link control and Save.
2. Select either member (or both members of that pair), set the original timeline ruler playhead to 1400ms and click **跳转到播放头**.
3. The **已保存链接联动拆分** panel previews video cut 1400ms, audio cut 1650ms and 250ms offset. Click **按已核对切点联动拆分链接**.
4. Verify video `[100,500)` at 1000 and `[500,900)` at 1400; audio `[50,450)` at 1250 and `[450,850)` at 1650. Both links have offset 250ms. Undo/Redo before saving is one operation. Save and explicitly read/adopt the server revision to verify persistence.
5. A cut at 1000 or 1800, a locked partner, stale source or unsupported mode must leave the saved document unchanged.

The added backend file `tests/test_timeline_linked_split_additive.py` provides reproducible fixtures using tiny CPU-generated MP4 and WAV imports and the real File owner; it calls no model or paid API. Run under the repository's isolated environment via `scripts/run_v2_checks.py` and a task-local `.runtime` profile. Select `-k 'not postgres'`. The targeted frontend tests are `StudioTimelineLinkedSplit.additive.test.tsx` and the existing `StudioTimelineClipLinks.additive.test.tsx`; run through the existing jsdom/Vitest setup. Full frontend `tsc -b` is also checked.

## Evidence and limits

Local companion evidence: `../linked-split-evidence/` contains exact commands, JUnit/logs, typecheck exit status, and 1366×768, 1440×900, 1920×1080 screenshots from the actual React component. Screenshots are conspicuously synthetic UI fixtures, with no backend save or media playback; they are not real backend acceptance evidence. Three separate File tests prove persistence, replay/reopen, original CAS/history, and failure atomicity. PostgreSQL, a live HTTP/browser-to-backend flow, rendering, export, speed/fade/transition splitting and multi-pair batches are outside this bounded check.

No dependency installation, model calls, paid APIs, user profile data edits, push or Release was performed. Previous demo/archive and frozen link/move worktrees remain separate.
