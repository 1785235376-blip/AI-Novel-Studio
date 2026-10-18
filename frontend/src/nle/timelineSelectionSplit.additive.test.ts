import { describe, expect, it } from 'vitest';
import { checkedTimeline, cloneTimeline } from '../creative/studioTimelineTypes';
import { applySelectionSplit, selectionSplitOperations, selectionSplitPreview, sameSelectionSplitDescriptors } from './timelineSelectionSplit';
const source = (kind: 'video' | 'audio' | 'image') => ({ id: `asset-${kind}`, kind: 'ASSET', asset_kind: kind, version: 1, digest: 'a'.repeat(64) });
const fixture = () => checkedTimeline({ schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25, captions: [{ start_ms: 0, end_ms: 1000, text: 'keep' }], tracks: [
  ...['one', 'two'].map((id, order) => ({ id, kind: 'VIDEO', order, muted: false, gain_db: 0, clips: [{ id: `v-${id}`, source_snapshot: source('video'), start_ms: 1000, in_ms: 600, out_ms: 3600, speed_num: 3, speed_den: 2, x: 0, y: 0, width: 64, height: 64, include_audio: true, gain_db: -4, muted: true, fade_in_ms: 200, fade_out_ms: 300, crop: { x: 0, y: 0, width: 64, height: 64 } }] })),
  { id: 'sound', kind: 'AUDIO', order: 2, muted: false, gain_db: 0, clips: [{ id: 'a', source_snapshot: source('audio'), start_ms: 0, in_ms: 0, out_ms: 5000 }, { id: 'boundary', source_snapshot: source('audio'), start_ms: 2000, in_ms: 0, out_ms: 1000 }] },
] });
describe('selected split compiler and detached final validation', () => {
  it('splits two video tracks and audio exactly, keeping pins/properties/captions and ordered skips', () => {
    const input = fixture(), before = cloneTimeline(input), selection = ['boundary', 'v-two', 'a', 'v-one'];
    const ids = { 'v-two': 'r-two', a: 'r-a', 'v-one': 'r-one' };
    expect(selectionSplitPreview(input, selection, 2000).map(row => [row.clip.id, row.affected])).toEqual([['boundary', false], ['v-two', true], ['a', true], ['v-one', true]]);
    const result = applySelectionSplit(input, selection, 2000, ids);
    expect(input).toEqual(before); expect(result.duration_ms).toBe(input.duration_ms); expect(result.captions).toEqual(input.captions);
    const left = result.tracks[0].clips[0], right = result.tracks[0].clips[1];
    expect(left).toEqual({ ...input.tracks[0].clips[0], out_ms: 2100, fade_out_ms: 0 });
    expect(right).toEqual({ ...input.tracks[0].clips[0], id: 'r-one', start_ms: 2000, in_ms: 2100, fade_in_ms: 0 });
  });
  it.each([[], ['a', 'a'], ['missing'], Array(1), ['a', , 'boundary']])('rejects malformed selection %#', selection => {
    expect(() => selectionSplitPreview(fixture(), selection as string[], 2000)).toThrow();
  });
  it('allows skipped locked clips, blocks crossing locked clips, fractional conversion and outer fade truncation', () => {
    const input = fixture(); input.tracks[2].locked = true;
    expect(selectionSplitPreview(input, ['boundary', 'v-one'], 2000).map(row => row.affected)).toEqual([false, true]);
    expect(() => selectionSplitPreview(input, ['a', 'v-one'], 2000)).toThrow(/锁定/);
    expect(() => selectionSplitPreview(input, ['v-one'], 2001)).toThrow(/整数/);
    expect(() => selectionSplitPreview(input, ['v-one'], 1100)).toThrow();
  });
  it('enforces complete collision-free identity maps and exact descriptors', () => {
    const input = fixture();
    for (const ids of [{}, { a: 'a' }, { a: 'bad id' }, { a: 'right', extra: 'extra' }]) expect(() => selectionSplitOperations(input, ['a'], 2000, ids as Record<string, string>)).toThrow();
    const expected = selectionSplitOperations(input, ['a'], 2000, { a: 'right' });
    expect(sameSelectionSplitDescriptors(cloneTimeline(expected), expected)).toBe(true);
    expect(sameSelectionSplitDescriptors([{ ...expected[0], extra: undefined }], expected)).toBe(false);
    expect(sameSelectionSplitDescriptors([], expected)).toBe(false);
    expect(() => selectionSplitOperations(input, ['boundary'], 2000, {})).toThrow();
  });
  it('permits exactly 30 final clips, rejecting 31 before allocation', () => {
    const input = fixture(); input.tracks[2].clips = Array.from({ length: 27 }, (_, i) => ({ ...input.tracks[2].clips[0], id: `a-${i}` }));
    expect(selectionSplitOperations(input, ['a-0'], 2000, { 'a-0': 'right' })).toHaveLength(1);
    expect(() => selectionSplitPreview(input, ['a-0', 'a-1'], 2000)).toThrow(/30/);
  });
});
