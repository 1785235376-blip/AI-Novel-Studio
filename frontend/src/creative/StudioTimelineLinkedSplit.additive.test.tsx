// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimeline, checkedTimelineRow, cloneTimeline, type StudioTimelineDraft, type StudioTimelineRow } from './studioTimelineTypes';
import { requireClipLinkPreservation } from './studioTimelineClipLinks';
import { linkedSplitFacts, splitLinkedTimeline } from './studioTimelineLinkedSplit';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';

const source = (kind: 'video' | 'audio') => ({ id: 'asset-' + kind, kind: 'ASSET' as const, asset_kind: kind, version: 1, digest: 'a'.repeat(64) });
function row(offset = 250): StudioTimelineRow {
  return checkedTimelineRow({ id: 'linked-timeline', version: 1, title: 'Synthetic saved linked pair', timeline_digest: 'b'.repeat(64), created_at: '2026-10-19', updated_at: '2026-10-19',
    timeline: { schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25, captions: [], tracks: [
      { id: 'visual', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'picture', source_snapshot: source('video'), start_ms: 1000, in_ms: 100, out_ms: 900, x: 0, y: 0, width: 64, height: 64 }] },
      { id: 'voice', kind: 'AUDIO', order: 1, muted: false, gain_db: 0, clips: [{ id: 'sound', source_snapshot: source('audio'), start_ms: 1000 + offset, in_ms: 50, out_ms: 850 }] },
    ], clip_links: [{ video_clip_id: 'picture', audio_clip_id: 'sound', offset_ms: offset }] } });
}
const assets = () => ['video', 'audio'].map(kind => ({ id: 'asset-' + kind, kind, version: 1, sha256: 'a'.repeat(64), deleted_at: null })) as unknown as StudioAsset[];
const ids = { video: 'picture-tail', audio: 'sound-tail' };
const allClips = (draft: StudioTimelineDraft) => draft.timeline.tracks.flatMap(track => track.clips);
afterEach(cleanup);
function setup(input = row(), panel = false) {
  let saved = cloneTimeline(input);
  const client = { timelineList: vi.fn(async () => ({ items: [cloneTimeline(saved)] })), timelineGet: vi.fn(async () => cloneTimeline(saved)),
    timelineSave: vi.fn(async (_id: string | undefined, body: StudioTimelineDraft & { expected_version: number }) => {
      saved = checkedTimelineRow({ ...saved, ...body, version: body.expected_version + 1, timeline_digest: 'c'.repeat(64) }); return cloneTimeline(saved);
    }), timelineRender: vi.fn(), timelineEdit: vi.fn() };
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: assets(), canMutate: true, busy: false,
    isCurrent: () => true, read: async work => work(), mutate: async work => work(), onDirtyChange: vi.fn(), onJob: vi.fn(), onUnavailable: vi.fn() };
  const hook = panel ? undefined : renderHook((p: StudioTimelineEditorProps) => useStudioTimelineEditor(p), { initialProps: props });
  if (panel) render(<StudioTimelineEditor {...props} />);
  return { props, client, hook };
}
async function adopt(state: ReturnType<typeof setup>) {
  const hook = state.hook!; await waitFor(() => expect(hook.result.current.rows).toHaveLength(1));
  await act(async () => hook.result.current.checkServer('linked-timeline'));
  act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
}

describe('saved VIDEO/AUDIO linked split on original owner', () => {
  it.each([250, -250, 0])('partitions both sources exactly while retaining offset %s and both relations', offset => {
    const before = row(offset).timeline;
    const result = checkedTimeline(splitLinkedTimeline(before, ['sound'], 1400, ids));
    expect(result.schema_version).toBe(2); expect(result.clip_links).toEqual([
      { video_clip_id: 'picture', audio_clip_id: 'sound', offset_ms: offset },
      { video_clip_id: 'picture-tail', audio_clip_id: 'sound-tail', offset_ms: offset },
    ]);
    expect(result.tracks.flatMap(track => track.clips).map(clip => [clip.id, clip.start_ms, clip.in_ms, clip.out_ms])).toEqual([
      ['picture', 1000, 100, 500], ['picture-tail', 1400, 500, 900],
      ['sound', 1000 + offset, 50, 450], ['sound-tail', 1400 + offset, 450, 850],
    ]);
    expect(() => requireClipLinkPreservation(before, result)).not.toThrow();
    const forged = cloneTimeline(result); forged.tracks[1].clips[0].out_ms++;
    expect(() => requireClipLinkPreservation(before, forged)).toThrow();
    const dropped = cloneTimeline(result); dropped.clip_links!.pop();
    expect(() => requireClipLinkPreservation(before, dropped)).toThrow();
    expect(row(offset).timeline).toEqual(before);
  });

  it('rejects boundaries, shorter partner, unsupported modes and reused IDs atomically', () => {
    const original = row().timeline;
    for (const cut of [1000, 1800, 1400.5]) expect(() => splitLinkedTimeline(original, ['picture'], cut, ids)).toThrow();
    const shorter = cloneTimeline(original); shorter.tracks[1].clips[0].out_ms = 350;
    expect(() => linkedSplitFacts(shorter, ['picture'], 1400)).toThrow(/共同相对区间/);
    expect(() => splitLinkedTimeline(original, ['picture'], 1400, { ...ids, video: 'picture' })).toThrow();
    for (const mode of ['lock', 'speed', 'fade', 'image', 'transition']) {
      const input = cloneTimeline(original), video = input.tracks[0].clips[0];
      if (mode === 'lock') input.tracks[1].locked = true;
      if (mode === 'speed') video.speed_num = 2;
      if (mode === 'fade') video.fade_out_ms = 10;
      if (mode === 'image') video.source_snapshot.asset_kind = 'image';
      if (mode === 'transition') video.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'other', duration_ms: 10 };
      const before = cloneTimeline(input);
      expect(() => splitLinkedTimeline(input, ['picture', 'sound'], 1400, ids)).toThrow(); expect(input).toEqual(before);
    }
  });

  it('uses one original undo, stable redo IDs, CAS Save and reopens both pairs; duplicate callback does nothing', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!, before = cloneTimeline(hook.result.current.draft!);
    const click = hook.result.current.splitLinkedClips;
    act(() => { expect(click(['picture'], 1400, ids)).toBe(true); expect(click(['picture'], 1400, { video: 'duplicate-v', audio: 'duplicate-a' })).toBe(false); });
    const expected = cloneTimeline(hook.result.current.draft!); expect(allClips(expected)).toHaveLength(4);
    act(() => hook.result.current.undo()); expect(hook.result.current.draft).toEqual(before);
    act(() => hook.result.current.redo()); expect(hook.result.current.draft).toEqual(expected);
    await act(async () => hook.result.current.save());
    expect(state.client.timelineSave).toHaveBeenCalledTimes(1);
    expect(state.client.timelineSave).toHaveBeenCalledWith('linked-timeline', { ...expected, expected_version: 1 });
    expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
    await act(async () => hook.result.current.checkServer()); act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
    expect(hook.result.current.draft).toEqual(expected); expect(hook.result.current.base?.version).toBe(2);
  });

  it('refuses dirty, retired, stale-source and old single-clip paths without silently unlinking', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!, original = cloneTimeline(hook.result.current.draft!);
    act(() => expect(hook.result.current.splitSelection(['picture'], 1400, { picture: 'single' })).toBe(false));
    const retired = hook.result.current.splitLinkedClips;
    act(() => hook.result.current.change(draft => { draft.title = 'Unsaved input'; })); const dirty = cloneTimeline(hook.result.current.draft!);
    act(() => expect(retired(['picture'], 1400, ids)).toBe(false));
    act(() => expect(hook.result.current.splitLinkedClips(['picture'], 1400, ids)).toBe(false)); expect(hook.result.current.error).toContain('先保存');
    expect(hook.result.current.draft).toEqual(dirty);
    act(() => hook.result.current.undo()); expect(hook.result.current.draft).toEqual(original);
    hook.rerender({ ...state.props, assets: assets().filter(asset => asset.kind !== 'audio') });
    act(() => expect(hook.result.current.splitLinkedClips(['picture'], 1400, ids)).toBe(false)); expect(hook.result.current.draft).toEqual(original);
  });

  it('wires explicit video-reference playhead and selected pair through original editor, then requires Save', async () => {
    const state = setup(row(), true); await waitFor(() => expect(screen.getByLabelText('读取已保存时间线').querySelector('option[value="linked-timeline"]')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: 'linked-timeline' } });
    const review = await screen.findByLabelText('核对服务端时间线'); fireEvent.click(within(review).getByLabelText('已核对服务端内容与本地输入，确认以下选择'));
    fireEvent.click(within(review).getByRole('button', { name: '采用服务端时间线' }));
    fireEvent.click(within(screen.getByLabelText('轨道头')).getByRole('button', { name: 'picture' }));
    fireEvent.change(screen.getByLabelText('播放头（毫秒）'), { target: { value: '1400' } });
    fireEvent.click(screen.getByRole('button', { name: '跳转到播放头' }));
    const panel = screen.getByRole('region', { name: '已保存链接联动拆分' });
    expect(within(panel).getByText(/视频切点 1400 毫秒；音频切点 1650 毫秒/)).toBeTruthy();
    const split = within(panel).getByRole('button', { name: '按已核对切点联动拆分链接' }); expect((split as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(split); expect((within(panel).getByRole('button', { name: '按已核对切点联动拆分链接' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '保存时间线' }));
    await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
    const body = state.client.timelineSave.mock.calls[0][1]; expect(body.expected_version).toBe(1); expect(allClips(body)).toHaveLength(4); expect(body.timeline.clip_links).toHaveLength(2);
  });
});
