// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { checkedTimeline, cloneTimeline } from '../creative/studioTimelineTypes';
import { SelectionRemovePanel } from './SelectionRemovePanel';
import { selectionRemovePreview, sameSelectionRemoveDescriptors } from './timelineSelectionRemove';
import { selectionRemoveRow } from './timelineSelectionRemove.testFixtures';

afterEach(cleanup);
const ids = ['video-remove', 'audio-remove'];
const retainedClick = (button: HTMLElement) => (button as unknown as Record<string, { onClick: () => void }>)[
  Object.keys(button).find(key => key.startsWith('__reactProps$'))!].onClick;

it('previews cross-track ordinary removal with exact retained pins/timing/captions and pure audio support', () => {
  const input = selectionRemoveRow().timeline, before = cloneTimeline(input);
  const result = selectionRemovePreview(input, ids);
  expect(result.operations).toEqual(ids.map(clip_id => ({ op: 'clip.remove', clip_id, ripple: false })));
  expect(result.targets.map(row => [row.clipId, row.trackId, row.startMs, row.endMs])).toEqual([
    ['video-remove', 'visual', 0, 2000], ['audio-remove', 'sound', 1000, 3000],
  ]);
  const expected = cloneTimeline(before);
  expected.tracks.forEach(track => { track.clips = track.clips.filter(clip => !ids.includes(clip.id)); });
  expect(result.timeline).toEqual(expected); expect(input).toEqual(before);
  const sound = cloneTimeline(input.tracks[1]); sound.order = 0;
  const pure = checkedTimeline({ schema_version: 3, media_kind: 'AUDIO', duration_ms: 8000, tracks: [sound] });
  const removed = selectionRemovePreview(pure, ['audio-remove']).timeline;
  expect(removed.schema_version).toBe(3); expect(removed.tracks[0].clips).toEqual([sound.clips[1]]);
});

it('refuses invalid/duplicate/oversized selection, empty tracks, locks and dangling transitions atomically', () => {
  const source = selectionRemoveRow().timeline;
  const cases: [unknown, string[]][] = [[source, []], [source, ['missing']], [source, [...ids, ids[0]]],
    [source, Array.from({ length: 41 }, (_, i) => `clip-${i}`)], [source, ['video-remove', 'video-keep']]];
  const locked = cloneTimeline(source); locked.tracks[1].locked = true; cases.push([locked, ids]);
  const transition = cloneTimeline(source);
  transition.tracks[0].clips[0].opacity = transition.tracks[0].clips[1].opacity;
  transition.tracks[0].clips[0].transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'video-keep', duration_ms: 200 };
  transition.tracks[0].clips[1].start_ms = 1800;
  cases.push([checkedTimeline(transition), ['video-keep']]);
  for (const [timeline, selection] of cases) {
    const before = JSON.stringify(timeline);
    expect(() => selectionRemovePreview(timeline, selection)).toThrow();
    expect(JSON.stringify(timeline)).toBe(before);
  }
});

it('descriptors accept exactly the reviewed non-ripple selection and reject omissions/extras/changed intent', () => {
  const expected = selectionRemovePreview(selectionRemoveRow().timeline, ids).operations;
  expect(sameSelectionRemoveDescriptors(expected, expected)).toBe(true);
  for (const value of [expected.slice(1), [...expected, expected[0]], [...expected].reverse(),
    expected.map(op => ({ ...op, ripple: true })), expected.map(op => ({ ...op, unexpected: 'x' })), null]) {
    expect(sameSelectionRemoveDescriptors(value, expected)).toBe(false);
  }
});

it('requires an explicit current preview click, preserves duplicate-click/stale/ABA/unmount guards', () => {
  const onEdit = vi.fn(), current = vi.fn(() => true);
  const props = { timeline: selectionRemoveRow().timeline, selectedClipIds: ids, editable: true, onEdit, isReviewCurrent: current };
  const view = render(<SelectionRemovePanel {...props} />);
  const panel = screen.getByRole('region', { name: '所选片段删除预览' });
  expect(within(panel).getByText(/1000 — 3000 毫秒/)).toBeTruthy(); expect(onEdit).not.toHaveBeenCalled();
  const old = retainedClick(screen.getByRole('button', { name: '删除所选片段（保留间隙）' }));
  view.rerender(<SelectionRemovePanel {...props} selectedClipIds={['audio-remove']} />);
  view.rerender(<SelectionRemovePanel {...props} />); old(); expect(onEdit).not.toHaveBeenCalled();
  current.mockReturnValue(false); fireEvent.click(screen.getByRole('button')); expect(onEdit).not.toHaveBeenCalled();
  current.mockReturnValue(true); fireEvent.click(screen.getByRole('button'));
  expect(onEdit).toHaveBeenCalledTimes(1);
  expect(onEdit).toHaveBeenCalledWith({ kind: 'clip.remove', payload: selectionRemovePreview(props.timeline, ids).operations });
  fireEvent.click(screen.getByRole('button')); expect(onEdit).toHaveBeenCalledTimes(1);
  const last = retainedClick(screen.getByRole('button')); view.unmount(); last(); expect(onEdit).toHaveBeenCalledTimes(1);
});

it('disables refusal and read-only previews without emitting edits', () => {
  const onEdit = vi.fn(), timeline = selectionRemoveRow().timeline;
  const view = render(<SelectionRemovePanel timeline={timeline} selectedClipIds={['video-remove', 'video-keep']} editable onEdit={onEdit} />);
  expect(screen.getByText(/删除会清空轨道/)).toBeTruthy(); expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<SelectionRemovePanel timeline={timeline} selectedClipIds={ids} editable={false} onEdit={onEdit} />);
  fireEvent.click(screen.getByRole('button')); expect(onEdit).not.toHaveBeenCalled();
});
