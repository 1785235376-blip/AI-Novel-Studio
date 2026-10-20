# EDIT04 / AUDIO09: bounded linked VIDEO/AUDIO trim

Base: `d9466d253fa4d8141391fd7295af65ce7276ee56`. Source inspection confirmed that the prior link guard refused `clip.trim`; d946 supplied linked split only. This slice adds linked non-ripple source trim through the original Timeline owner, editor history and CAS Save. No persistent schema fields or additional state machine are introduced.

## Contract and explicit semantics

The input is one existing schema 2 VIDEO/AUDIO pair, with actual video/audio sources at 1×, neither track locked, and no fades or transitions touching either member. The original link, IDs, tracks, source snapshots, timeline starts and offset stay unchanged. Other clips, captions and document settings remain unchanged.

The requested shared relative interval is `[keep_from_ms, keep_to_ms)`, measured from each member's original source in-point. Both values must be integer milliseconds with `0 <= keep_from < keep_to <= min(video.out-video.in, audio.out-audio.in)`. Each member receives `[old.in+keep_from, old.in+keep_to)`. This retains the existing **fixed timeline start** semantics of original non-ripple `clip.trim`. It does not implement edge dragging that advances the timeline start, extension or ripple. Unequal input lengths use the smaller common range; the panel explicitly previews the result for both members, even if one member's source range would stay unchanged. An exact no-op for both members is refused.

Example: video start 1000, source `[100,900)`; audio start 1250, source `[50,850)`; offset 250. Retaining `[100,650)` yields video `[200,750)` at 1000 and audio `[150,700)` at 1250. Both last 550ms. Other clips keep their original positions, including any later clips on these tracks.

New standalone operation in the original `/edit` batch:

```json
{"op":"clip.trim_linked","video_clip_id":"picture","audio_clip_id":"sound","keep_from_ms":100,"keep_to_ms":650}
```

This operation must be the only operation in its batch. It retains original request ID/digest replay, version/digest CAS, source checks, authorization guards and atomic File transaction. Unknown fields (including `ripple`), invalid IDs, boundaries outside the common range, empty/reversed ranges, fractions/booleans, locked tracks, stale sources and unsupported media/speed/fade/transition modes refuse without a partial change. Original unlinked single-clip trim behavior is preserved; the old single-clip trim entry still refuses linked members.

## Whole Save and d946 compatibility

Full DTO Save admits linked trim only if the **entire normalized timeline** is exactly the old timeline with these two source intervals replaced. This prevents orphaned split tails from being mistaken for a valid trim, preserves d946's missing-tail-link refusal, and prevents this bounded trim Save from including unrelated Timeline edits. Save immediately after trimming, before editing other Timeline content. Title is outside the timeline DTO and retains the existing contract.

The local controller only enables this pattern through the explicit linked-trim method. Ordinary numeric changes and original single-clip controls do not acquire a linked trim capability. The panel previews both source ranges and fixed timeline starts before Apply. It requires a saved clean draft with current sources. Parent client/context, authority, busy state and selection generations are checked; local form input generations reject retained callbacks after input ABA. Duplicate application uses the original generation fence and creates one history entry. Undo/Redo before Save retains original IDs and restores the whole pair once. After Save, the original adopt path clears local history, with the old revision retained in server history. No linked merge/restore operation is added.

UNKNOWN rendering/export request identity and recovery remain owned by the existing controller. Linked trim refuses while UNKNOWN, keeps the original request identity and timeline, and does not render, retry or create a replacement request. The new test invokes only mocked render/list methods for that check.

## Reproduce in the existing VIDEO editor

1. Use current imported video/audio assets and create the example pair above. Keep schema 2, 1×, no fades/transitions. Link and Save through the original controls.
2. Select either member, or both members of the same pair. In **已保存链接联动裁剪**, enter **共同保留入点（相对毫秒）** = 100 and **共同保留出点（相对毫秒）** = 650.
3. Check the displayed ranges for both `picture` and `sound`, unchanged starts 1000/1250 and offset 250. Click **按已预览区间联动裁剪链接**.
4. Undo and Redo before Save should each be one action. Save before other Timeline edits, then explicitly read/adopt the server revision; ranges and link must remain.
5. A bound above 800, a locked partner or a source version change must refuse the entire edit. Existing unlinked trim remains available through its original inspector.

## Verification and limits

Companion local evidence: `../linked-trim-evidence/`. Final targeted runs: 39 backend checks (23 new trim + 16 d946 split), with 7 real File cases (4 new trim + 3 d946 split), and 7 PostgreSQL parameters excluded; 52 frontend checks (16 new trim, 29 original single trim, 7 d946 split); full frontend `tsc -b`; actual React VIDEO component geometry at 1366×768, 1440×900 and 1920×1080 with no page errors or horizontal document overflow.

The new File cases import tiny CPU-created MP4/WAV assets through the real File owner. They verify replay/reopen, original CAS/history, malformed partner rollback, permission withdrawal at the final commit guard, track lock, stale source and bounds rollback. The permission test exercises the real transaction with a revoked synthetic guard; it is not a live HTTP ACL test. Initial cross-pattern regression is preserved in the evidence and was fixed before final checks.

Four screenshots are explicitly labeled synthetic UI fixtures of the actual React component; they do not demonstrate a real backend/browser save, generation, playback or rendering. PostgreSQL, a live browser-to-HTTP flow, rendering/export, ripple/extension, multiple linked pairs, speed/fade/transition trim and full NLE acceptance are not claimed. No model or paid API was called. Shared DSH components, Graph core, rendering/playback implementations and demo services were not edited. No push or Release was performed.
