import { describe, expect, it } from 'vitest';
import { checkedTimeline, cloneTimeline } from '../creative/studioTimelineTypes';
import { selectionDuplicateOperations, sameSelectionDuplicateDescriptors } from './timelineSelectionDuplicate';
const timeline = checkedTimeline({ schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25, captions: [], tracks: [
  { id: 'visual', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'still', start_ms: 0, in_ms: 0, out_ms: 8000, x: 0, y: 0, width: 64, height: 64, source_snapshot: { id: 'image', kind: 'ASSET', asset_kind: 'image', version: 1, digest: 'b'.repeat(64) } }] },
  { id: 'sound', kind: 'AUDIO', order: 1, muted: false, gain_db: 0, clips: ['a', 'b'].map((id, i) => ({ id, start_ms: 1000 + i * 1000, in_ms: 600, out_ms: 3600,
    speed_num: 3, speed_den: 2, source_snapshot: { id: 'asset', kind: 'ASSET', asset_kind: 'audio', version: 1, digest: 'a'.repeat(64) } })) },
] });

const ids = { a: 'copy-a', b: 'copy-b' };
describe('selection duplicate descriptor compiler', () => {
  it.each([1000, -1000, 0])('compiles signed %s preserving originals and authored identities', offset => {
    const before = cloneTimeline(timeline);
    expect(selectionDuplicateOperations(timeline, ['b', 'a'], offset, ids)).toEqual([
      { op: 'clip.duplicate', clip_id: 'b', new_clip_id: 'copy-b', track_id: 'sound', start_ms: 2000 + offset },
      { op: 'clip.duplicate', clip_id: 'a', new_clip_id: 'copy-a', track_id: 'sound', start_ms: 1000 + offset },
    ]); expect(timeline).toEqual(before);
  });
  it.each([[], ['a', 'a'], ['missing'], Array(1), ['a', , 'b']].map(selection => ({ selection })))('rejects malformed selection $selection', ({ selection }) => {
    expect(() => selectionDuplicateOperations(timeline, selection as string[], 0, ids)).toThrow();
  });
  it.each([NaN, Infinity, 0.5, -1001, 4001, Number.MAX_SAFE_INTEGER])('rejects invalid offset %s', offset => {
    expect(() => selectionDuplicateOperations(timeline, ['a', 'b'], offset, ids)).toThrow();
  });
  it.each([{}, { a: 'copy-a' }, { ...ids, extra: 'copy-extra' }, { a: 'a', b: 'new' }, { a: 'still', b: 'new' },
    { a: 'same', b: 'same' }, { a: '', b: 'new' }, { a: 'x'.repeat(241), b: 'new' }, { a: 'bad id', b: 'new' },
    Object.assign(Object.create({ a: 'copy-a' }), { b: 'copy-b' }), { ...ids, [Symbol('extra')]: 'extra' }].map(mapping => ({ mapping })))('rejects invalid mapping %#', ({ mapping }) => {
    expect(() => selectionDuplicateOperations(timeline, ['a', 'b'], 0, mapping as Record<string, string>)).toThrow();
  });
  it('rejects accessor identity maps without invoking their getters', () => {
    let reads = 0;
    const mapping = Object.defineProperty({}, 'a', { enumerable: true, get: () => { reads++; return 'new'; } });
    expect(() => selectionDuplicateOperations(timeline, ['a'], 0, mapping)).toThrow(); expect(reads).toBe(0);
  });
  it('rejects locked targets and more than 30 resulting clips', () => {
    const locked = cloneTimeline(timeline); locked.tracks[1].locked = true;
    expect(() => selectionDuplicateOperations(locked, ['a'], 0, { a: 'new' })).toThrow(/锁定/);
    const full = cloneTimeline(timeline);
    full.tracks[1].clips = Array.from({ length: 29 }, (_, i) => ({ ...full.tracks[1].clips[0], id: `audio-${i}` }));
    expect(() => selectionDuplicateOperations(full, ['audio-0'], 0, { 'audio-0': 'new' })).toThrow(/30/);
  });
  it('permits exactly 30 resulting clips with maximum-length valid IDs within unchanged batch bounds', () => {
    const input = cloneTimeline(timeline);
    input.tracks[1].clips = Array.from({ length: 15 }, (_, i) => ({ ...input.tracks[1].clips[0], id: `audio-${i}` }));
    const selection = input.tracks[1].clips.slice(0, 14).map(clip => clip.id);
    const mapping = Object.fromEntries(selection.map((id, i) => [id, `copy-${i}-` + 'x'.repeat(234 - String(i).length)]));
    const operations = selectionDuplicateOperations(input, selection, 0, mapping);
    expect(operations).toHaveLength(14); expect(operations.length).toBeLessThanOrEqual(40);
    expect(new TextEncoder().encode(JSON.stringify(operations)).length).toBeLessThan(128000);
  });
  it('compiles internal transitions only after all copies and omits external outgoing transitions', () => {
    const input = cloneTimeline(timeline), first = input.tracks[0].clips[0]; first.out_ms = 2000;
    first.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'next', duration_ms: 200 };
    input.tracks[0].clips.push({ ...first, id: 'next', start_ms: 1800, transition_out: undefined });
    delete input.tracks[0].clips[1].transition_out;
    const operations = selectionDuplicateOperations(input, ['next', 'still'], 4000, { next: 'new-next', still: 'new-still' });
    expect(operations).toEqual([
      { op: 'clip.duplicate', clip_id: 'next', new_clip_id: 'new-next', track_id: 'visual', start_ms: 5800 },
      { op: 'clip.duplicate', clip_id: 'still', new_clip_id: 'new-still', track_id: 'visual', start_ms: 4000 },
      { op: 'clip.update', clip_id: 'new-still', changes: { transition_out: { kind: 'CROSS_DISSOLVE', to_clip_id: 'new-next', duration_ms: 200 } } },
    ]);
    expect(selectionDuplicateOperations(input, ['still'], 4000, { still: 'new-still' })).toHaveLength(1);
    expect(first.transition_out.to_clip_id).toBe('next');
    expect(new TextEncoder().encode(JSON.stringify(operations)).length).toBeLessThan(128000);
  });
  it('strictly verifies recursively without ignoring undefined, sparse, symbolic or hidden fields', () => {
    const expected = selectionDuplicateOperations(timeline, ['a'], 0, { a: 'new' });
    expect(sameSelectionDuplicateDescriptors(cloneTimeline(expected), expected)).toBe(true);
    for (const actual of [[{ ...expected[0], extra: undefined }], Array(1), [{ ...expected[0], [Symbol('extra')]: true }],
      [Object.defineProperty({ ...expected[0] }, 'hidden', { value: undefined })], [Object.create(expected[0])],
      [Object.defineProperty({ ...expected[0] }, 'clip_id', { get: () => 'a', enumerable: true })]]) {
      expect(sameSelectionDuplicateDescriptors(actual, expected)).toBe(false);
    }
  });
});
