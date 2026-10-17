import { describe, expect, it } from 'vitest';
import { checkedTimeline, cloneTimeline } from '../creative/studioTimelineTypes';
import { selectionMoveOperations } from './timelineSelectionMove';
const timeline = checkedTimeline({ schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25, captions: [], tracks: [
  { id: 'visual', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'still', start_ms: 0, in_ms: 0, out_ms: 8000, x: 0, y: 0, width: 64, height: 64, source_snapshot: { id: 'image', kind: 'ASSET', asset_kind: 'image', version: 1, digest: 'b'.repeat(64) } }] },
  { id: 'sound', kind: 'AUDIO', order: 1, muted: false, gain_db: 0, clips: ['a', 'b'].map((id, i) => ({ id, start_ms: 1000 + i * 1000, in_ms: 600, out_ms: 3600,
    speed_num: 3, speed_den: 2, source_snapshot: { id: 'asset', kind: 'ASSET', asset_kind: 'audio', version: 1, digest: 'a'.repeat(64) } })) },
] });
describe('selection move descriptor compiler', () => {
  it.each([1000, -1000, 0])('compiles signed %s without mutating or imposing audio collision rules', offset => {
    const before = cloneTimeline(timeline);
    expect(selectionMoveOperations(timeline, ['b', 'a'], offset)).toEqual([
      { op: 'clip.move', clip_id: 'b', track_id: 'sound', start_ms: 2000 + offset },
      { op: 'clip.move', clip_id: 'a', track_id: 'sound', start_ms: 1000 + offset },
    ]); expect(timeline).toEqual(before);
  });
  it.each([[], ['a', 'a'], ['missing'], Array(41).fill('a')].map(ids => ({ ids })))('rejects invalid selection $ids', ({ ids }) => {
    expect(() => selectionMoveOperations(timeline, ids, 1)).toThrow();
  });
  it.each([NaN, Infinity, 0.5, -1001, 4001, Number.MAX_SAFE_INTEGER])('rejects invalid offset %s', offset => {
    expect(() => selectionMoveOperations(timeline, ['a', 'b'], offset)).toThrow();
  });
  it('rejects locked selection', () => {
    const locked = cloneTimeline(timeline); locked.tracks[1].locked = true;
    expect(() => selectionMoveOperations(locked, ['a'], 1)).toThrow(/锁定/);
  });
});
