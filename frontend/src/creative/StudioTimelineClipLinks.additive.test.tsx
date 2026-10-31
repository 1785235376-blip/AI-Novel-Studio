// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimeline, checkedTimelineRow, cloneTimeline, type StudioTimelineDraft, type StudioTimelineRow } from './studioTimelineTypes';
import { changeClipLinks } from './studioTimelineClipLinks';
import { selectionMoveOperations } from '../nle/timelineSelectionMove';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';

const source = (kind: 'image' | 'audio') => ({ id: 'asset-' + kind, kind: 'ASSET' as const, asset_kind: kind, version: 1, digest: 'a'.repeat(64) });
function row(): StudioTimelineRow {
  return checkedTimelineRow({ id: 'linked-timeline', version: 1, title: 'Synthetic link fixture', timeline_digest: 'b'.repeat(64), created_at: '2026-10-19', updated_at: '2026-10-19',
    timeline: { schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25, captions: [], tracks: [
      { id: 'visual', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'picture', source_snapshot: source('image'), start_ms: 1000, in_ms: 0, out_ms: 500, x: 0, y: 0, width: 64, height: 64 }] },
      { id: 'voice', kind: 'AUDIO', order: 1, muted: false, gain_db: 0, clips: [{ id: 'sound', source_snapshot: source('audio'), start_ms: 1250, in_ms: 0, out_ms: 300 }] },
    ] } });
}
const assets = () => ['image', 'audio'].map(kind => ({ id: 'asset-' + kind, kind, version: 1, sha256: 'a'.repeat(64), deleted_at: null })) as unknown as StudioAsset[];
const starts = (draft: StudioTimelineDraft | undefined) => draft!.timeline.tracks.map(track => track.clips[0].start_ms);
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
  const view = panel ? render(<StudioTimelineEditor {...props} />) : undefined;
  return { props, client, hook, view };
}
async function adopt(state: ReturnType<typeof setup>) {
  const hook = state.hook!; await waitFor(() => expect(hook.result.current.rows).toHaveLength(1));
  await act(async () => hook.result.current.checkServer('linked-timeline'));
  act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
}
describe('bounded persistent clip links on original editor owner', () => {
  it('retains legacy absence and rejects malformed pairs without upgrading old schema', () => {
    const original = row().timeline; expect(original).not.toHaveProperty('clip_links');
    expect(checkedTimeline(original)).toEqual(original);
    expect(() => checkedTimeline({ ...original, clip_links: [{ video_clip_id: 'picture', audio_clip_id: 'picture', offset_ms: 0 }] })).toThrow();
    expect(() => checkedTimeline({ ...original, schema_version: undefined, clip_links: [] })).toThrow();
    expect(() => changeClipLinks(original, ['picture', 'picture'], false)).toThrow();
  });
  it('links, moves one or both members once, uses one undo per intent, CAS saves and reopens', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!, original = cloneTimeline(hook.result.current.draft!);
    act(() => expect(hook.result.current.linkClips(['picture', 'sound'])).toBe(true));
    const linked = cloneTimeline(hook.result.current.draft!); expect(linked.timeline.clip_links).toEqual([{ video_clip_id: 'picture', audio_clip_id: 'sound', offset_ms: 250 }]);
    act(() => hook.result.current.undo()); expect(hook.result.current.draft).toEqual(original);
    act(() => hook.result.current.redo()); expect(hook.result.current.draft).toEqual(linked);
    act(() => expect(hook.result.current.moveSelection(['picture'], 500)).toBe(true)); expect(starts(hook.result.current.draft)).toEqual([1500, 1750]);
    act(() => hook.result.current.undo()); expect(hook.result.current.draft).toEqual(linked);
    act(() => hook.result.current.redo());
    act(() => expect(hook.result.current.moveSelection(['picture', 'sound'], 100)).toBe(true)); expect(starts(hook.result.current.draft)).toEqual([1600, 1850]);
    expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
    const expected = cloneTimeline(hook.result.current.draft!); await act(async () => hook.result.current.save());
    expect(state.client.timelineSave).toHaveBeenCalledWith('linked-timeline', { ...expected, expected_version: 1 });
    await act(async () => hook.result.current.checkServer()); act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
    expect(hook.result.current.draft).toEqual(expected);
    act(() => expect(hook.result.current.unlinkClips(['sound'])).toBe(true)); expect(hook.result.current.draft!.timeline).not.toHaveProperty('clip_links');
  });
  it('refuses bounds, linked trim/split and direct numeric/source edits atomically', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!;
    act(() => hook.result.current.linkClips(['picture', 'sound'])); const before = cloneTimeline(hook.result.current.draft!);
    act(() => expect(hook.result.current.moveSelection(['sound'], -1300)).toBe(false)); expect(hook.result.current.draft).toEqual(before);
    act(() => expect(hook.result.current.trimClip('visual', 'picture', 0, 400, false)).toBe(false)); expect(hook.result.current.error).toContain('先明确解除链接');
    act(() => expect(hook.result.current.splitSelection(['picture'], 1200, { picture: 'new-head' })).toBe(false));
    act(() => expect(hook.result.current.change(draft => { draft.timeline.tracks[1].clips[0].start_ms++; })).toBe(false));
    act(() => expect(hook.result.current.change(draft => { draft.timeline.tracks[1].clips[0].source_snapshot.version++; })).toBe(false));
    expect(hook.result.current.draft).toEqual(before);
  });
  it('rejects a locked partner, stale source and retired edit callback', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!;
    const retired = hook.result.current.linkClips;
    act(() => hook.result.current.change(draft => { draft.title = 'Changed context'; }));
    act(() => expect(retired(['picture', 'sound'])).toBe(false));
    act(() => hook.result.current.linkClips(['picture', 'sound'])); const before = cloneTimeline(hook.result.current.draft!);
    const locked = cloneTimeline(before.timeline); locked.tracks[1].locked = true;
    expect(() => selectionMoveOperations(locked, ['picture'], 100)).toThrow(/锁定/);
    state.hook!.rerender({ ...state.props, assets: assets().filter(asset => asset.kind !== 'audio') });
    act(() => expect(hook.result.current.moveSelection(['picture'], 100)).toBe(false));
    act(() => expect(hook.result.current.unlinkClips(['picture'])).toBe(false)); expect(hook.result.current.draft).toEqual(before);
  });
  it('wires explicit link and unlink from the original cross-track selection', async () => {
    setup(row(), true); await waitFor(() => expect(screen.getByLabelText('读取已保存时间线').querySelector('option[value="linked-timeline"]')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: 'linked-timeline' } });
    const review = await screen.findByLabelText('核对服务端时间线'); fireEvent.click(within(review).getByLabelText('已核对服务端内容与本地输入，确认以下选择'));
    fireEvent.click(within(review).getByRole('button', { name: '采用服务端时间线' }));
    const tracks = screen.getByLabelText('轨道头'); fireEvent.click(within(tracks).getByRole('button', { name: 'picture' }));
    fireEvent.click(within(tracks).getByRole('button', { name: 'sound' }), { ctrlKey: true });
    const panel = screen.getByRole('region', { name: '视频音频片段链接' }); const link = within(panel).getByRole('button', { name: '链接所选视频与音频' });
    expect((link as HTMLButtonElement).disabled).toBe(false); fireEvent.click(link);
    expect(within(panel).getByText(/picture ↔ sound.*250/)).toBeTruthy();
    fireEvent.click(within(panel).getByRole('button', { name: '解除所选片段链接' })); expect(within(panel).queryByText(/picture ↔ sound/)).toBeNull();
  });
});
