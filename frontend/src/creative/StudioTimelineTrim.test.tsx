// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { ClipInspectorPanel } from '../nle/ClipInspectorPanel';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimelineRow, cloneTimeline, type StudioTimelineClip, type StudioTimelineDraft, type StudioTimelineRow } from './studioTimelineTypes';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';

// Synthetic controller fixtures, not claims of real media/render verification.
const source = (kind: 'image' | 'audio' | 'video') => ({ id: `asset-${kind}`, kind: 'ASSET' as const, asset_kind: kind, version: 1, digest: 'a'.repeat(64) });
const audio = (id: string, start: number): StudioTimelineClip => ({ id, source_snapshot: source('audio'), start_ms: start, in_ms: 0, out_ms: 300,
  speed_num: 1, speed_den: 1, fade_in_ms: 0, fade_out_ms: 0 });
function row(): StudioTimelineRow {
  return checkedTimelineRow({ id: 'timeline-trim', version: 1, timeline_digest: 'b'.repeat(64), title: 'Trim fixture', created_at: '2026-10-17', updated_at: '2026-10-17',
    timeline: { schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25, captions: [{ start_ms: 3500, end_ms: 4500, text: 'Unchanged caption' }], tracks: [
      { id: 'visual', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'still', source_snapshot: source('image'), start_ms: 0, in_ms: 0, out_ms: 7000, x: 0, y: 0, width: 64, height: 64 }] },
      { id: 'sound', kind: 'AUDIO', order: 1, muted: false, gain_db: 0, clips: [
        { ...audio('audio-target', 1000), out_ms: 3000, speed_num: 3, speed_den: 2 }, audio('before-boundary', 2999), audio('at-boundary', 3000), audio('later', 4500)] },
      { id: 'other-sound', kind: 'AUDIO', order: 2, muted: false, gain_db: 0, clips: [audio('other-track', 3000)] },
    ] } });
}
const assets = () => ['image', 'audio', 'video'].map(kind => ({ id: `asset-${kind}`, kind, version: 1, sha256: 'a'.repeat(64), filename: `${kind}.fixture`, deleted_at: null })) as unknown as StudioAsset[];
const find = (draft: StudioTimelineDraft | undefined, id: string) => draft!.timeline.tracks.flatMap(track => track.clips).find(clip => clip.id === id)!;
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function setup(input = row(), panel = false) {
  let saved = cloneTimeline(input);
  const client = { timelineList: vi.fn(async () => ({ items: [cloneTimeline(saved)] })), timelineGet: vi.fn(async () => cloneTimeline(saved)),
    timelineSave: vi.fn(async (_id: string | undefined, body: StudioTimelineDraft & { expected_version: number }) => {
      saved = checkedTimelineRow({ ...saved, title: body.title, timeline: body.timeline, version: body.expected_version + 1, timeline_digest: 'c'.repeat(64) }); return cloneTimeline(saved);
    }), timelineRender: vi.fn(), timelineEdit: vi.fn(), list: vi.fn() };
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: assets(), canMutate: true, busy: false,
    isCurrent: () => true, read: async work => work(), mutate: async work => work(), onDirtyChange: vi.fn(), onJob: vi.fn(), onUnavailable: vi.fn() };
  const hook = panel ? undefined : renderHook((next: StudioTimelineEditorProps) => useStudioTimelineEditor(next), { initialProps: props });
  const view = panel ? render(<StudioTimelineEditor {...props} />) : undefined;
  return { client, props, hook, view };
}
async function adopt(state: ReturnType<typeof setup>) {
  const hook = state.hook!; await waitFor(() => expect(hook.result.current.rows).toHaveLength(1));
  await act(async () => hook.result.current.checkServer('timeline-trim'));
  act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
}
function trim(state: ReturnType<typeof setup>, out = 1500, ripple = true, track = 'sound', clip = 'audio-target', start = 0) {
  let applied = false; act(() => { applied = state.hook!.result.current.trimClip(track, clip, start, out, ripple); }); return applied;
}

describe('original local Timeline trim semantics', () => {
  it.each([[1500, -1000], [4500, 1000]])('uses rational rendered delta for out=%s and exactly the old end threshold', async (out, delta) => {
    const state = setup(); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    expect(trim(state, out)).toBe(true); const after = state.hook!.result.current.draft!;
    expect(find(after, 'audio-target')).toMatchObject({ start_ms: 1000, in_ms: 0, out_ms: out, speed_num: 3, speed_den: 2 });
    expect(find(after, 'before-boundary').start_ms).toBe(2999);
    expect(find(after, 'at-boundary').start_ms).toBe(3000 + delta); expect(find(after, 'later').start_ms).toBe(4500 + delta);
    expect(after.timeline.tracks[0]).toEqual(before.timeline.tracks[0]); expect(after.timeline.tracks[2]).toEqual(before.timeline.tracks[2]);
    expect(after.timeline.captions).toEqual(before.timeline.captions); expect(after.timeline.duration_ms).toBe(before.timeline.duration_ms);
    for (const clip of before.timeline.tracks.flatMap(track => track.clips)) expect(find(after, clip.id).source_snapshot).toEqual(clip.source_snapshot);
    expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
    act(() => state.hook!.result.current.undo()); expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
    act(() => state.hook!.result.current.redo()); expect(state.hook!.result.current.draft).toEqual(after); expect(state.hook!.result.current.canRedo).toBe(false);
  });
  it('keeps later positions with ripple off, and creates no extra history for unchanged trim', async () => {
    const state = setup(); await adopt(state); expect(trim(state, 1500, false)).toBe(true);
    expect(find(state.hook!.result.current.draft, 'at-boundary').start_ms).toBe(3000);
    expect(trim(state, 1500, true)).toBe(false); act(() => state.hook!.result.current.undo()); expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it('trims image display duration with zero in-point', async () => {
    const state = setup(); await adopt(state); expect(trim(state, 6000, false, 'visual', 'still')).toBe(true);
    expect(find(state.hook!.result.current.draft, 'still')).toMatchObject({ in_ms: 0, out_ms: 6000, speed_num: 1, speed_den: 1 });
  });
  it.each([[-1, 1500], [0, 1501], [1500, 1500], [1600, 1500], [0, 36000001], [0, Number.NaN], [0.5, 1500]])('atomically rejects in/out %s/%s', async (start, out) => {
    const state = setup(); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    expect(trim(state, out, true, 'sound', 'audio-target', start)).toBe(false); expect(state.hook!.result.current.draft).toEqual(before);
    expect(state.hook!.result.current.canUndo).toBe(false); expect(state.client.timelineSave).not.toHaveBeenCalled();
  });
  it.each(['image-in', 'fade', 'locked', 'overflow', 'overlap', 'transition'] as const)('keeps original %s guard atomic', async fault => {
    const input = row();
    if (fault === 'fade') find(input, 'audio-target').fade_in_ms = 1500;
    if (fault === 'locked') input.timeline.tracks[1].locked = true;
    if (fault === 'overflow') find(input, 'later').start_ms = 7500;
    if (fault === 'overlap' || fault === 'transition') {
      const left = find(input, 'still'); left.out_ms = 2000;
      input.timeline.tracks[0].clips.push({ ...cloneTimeline(left), id: 'next-still', start_ms: fault === 'transition' ? 1800 : 2000 });
      if (fault === 'transition') left.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'next-still', duration_ms: 200 };
    }
    const state = setup(checkedTimelineRow(input)); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    const visual = ['image-in', 'overlap', 'transition'].includes(fault);
    expect(trim(state, fault === 'overflow' ? 4500 : fault === 'overlap' ? 2500 : 1500, fault !== 'overlap', visual ? 'visual' : 'sound', visual ? 'still' : 'audio-target', fault === 'image-in' ? 1 : 0)).toBe(false);
    expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it('uses only original explicit Save CAS, then original GET/adoption after reopen', async () => {
    const state = setup(); await adopt(state); trim(state); const expected = cloneTimeline(state.hook!.result.current.draft!);
    await act(async () => state.hook!.result.current.save());
    expect(state.client.timelineSave).toHaveBeenCalledTimes(1); expect(state.client.timelineSave).toHaveBeenCalledWith('timeline-trim', { ...expected, expected_version: 1 });
    expect(state.hook!.result.current.base?.version).toBe(2); expect(state.hook!.result.current.canUndo).toBe(false);
    state.hook!.unmount();
    const reopened = renderHook(() => useStudioTimelineEditor(state.props)); await waitFor(() => expect(reopened.result.current.rows).toHaveLength(1));
    await act(async () => reopened.result.current.checkServer('timeline-trim')); act(() => reopened.result.current.setAdoptConfirmed(true)); act(() => reopened.result.current.adoptCandidate(false));
    expect(reopened.result.current.draft).toEqual(expected); expect(reopened.result.current.base?.version).toBe(2);
    expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
  });
});

describe('trim lifecycle and fail-closed controller', () => {
  it('preserves a callback over unrelated rerenders but rejects it after edit/undo generation changes', async () => {
    const state = setup(); await adopt(state); const callback = state.hook!.result.current.trimClip;
    state.hook!.rerender({ ...state.props, assets: assets() }); let result = false;
    act(() => { result = callback('sound', 'audio-target', 0, 1500, true); }); expect(result).toBe(true);
    act(() => state.hook!.result.current.undo()); act(() => { result = callback('sound', 'audio-target', 0, 4500, true); });
    expect(result).toBe(false); expect(find(state.hook!.result.current.draft, 'audio-target').out_ms).toBe(3000);
  });
  it.each(['authority', 'busy', 'permission', 'client', 'unmount'] as const)('rejects retained trim callback after %s change', async fault => {
    const state = setup(); await adopt(state); const callback = state.hook!.result.current.trimClip;
    if (fault === 'unmount') state.hook!.unmount();
    else state.hook!.rerender({ ...state.props, ...(fault === 'authority' ? { isCurrent: () => false } : fault === 'busy' ? { busy: true } : fault === 'permission' ? { canMutate: false } : { client: { ...state.client } as unknown as StudioProductionClient }) });
    let result = true; act(() => { result = callback('sound', 'audio-target', 0, 1500, true); }); expect(result).toBe(false);
    expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineEdit).not.toHaveBeenCalled();
  });
  it.each([409, 503])('preserves failed Save %s and prevents trim/retry', async status => {
    const state = setup(); await adopt(state); trim(state); state.client.timelineSave.mockRejectedValueOnce(new ApiError({ status, code: status === 409 ? 'CONFLICT' : 'LOST', message: 'Synthetic failure' }));
    await act(async () => state.hook!.result.current.save()); const before = cloneTimeline(state.hook!.result.current.draft!);
    expect(state.hook!.result.current.failure).toBe(status === 409 ? 'CONFLICT' : 'UNKNOWN'); expect(trim(state, 4500)).toBe(false);
    await act(async () => state.hook!.result.current.save()); expect(state.hook!.result.current.draft).toEqual(before); expect(state.client.timelineSave).toHaveBeenCalledTimes(1);
  });
  it('blocks trim while original Save is pending', async () => {
    const state = setup(); await adopt(state); trim(state); const before = cloneTimeline(state.hook!.result.current.draft!), pending = deferred<StudioTimelineRow>();
    state.client.timelineSave.mockReturnValueOnce(pending.promise); let promise!: Promise<void>;
    act(() => { promise = state.hook!.result.current.save(); }); expect(trim(state, 4500)).toBe(false);
    await act(async () => { pending.resolve(checkedTimelineRow({ ...row(), ...before, version: 2, timeline_digest: 'c'.repeat(64) })); await promise; });
    expect(state.hook!.result.current.draft).toEqual(before);
  });
});

const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const set = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
describe('mounted original inspector trim', () => {
  it('routes trim without start/at position, supports one-step undo/redo and explicit Save', async () => {
    const state = setup(row(), true); await screen.findByRole('option', { name: 'Trim fixture · v1' });
    set('读取已保存时间线', 'timeline-trim'); await screen.findByRole('heading', { name: 'Trim fixture · v1' });
    fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线'); click('audio-target');
    set('请求的动作', 'trim'); set('裁剪入点（毫秒）', '0'); set('裁剪出点（毫秒）', '1500'); fireEvent.click(screen.getByLabelText('波纹闭合间隙'));
    click('生成编辑指令');
    const target = () => within(screen.getByRole('region', { name: '轨道 2 片段 1' })).getByLabelText('素材出点（毫秒）') as HTMLInputElement;
    expect(target().value).toBe('1500'); expect(screen.getByText(/裁剪已应用到本地草稿/)).toBeTruthy();
    expect(state.client.timelineSave).not.toHaveBeenCalled(); click('撤销本地编辑'); expect(target().value).toBe('3000');
    expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true); click('重做本地编辑'); expect(target().value).toBe('1500');
    click('保存时间线'); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
    const body = state.client.timelineSave.mock.calls[0][1]; expect(body.expected_version).toBe(1); expect(find(body, 'at-boundary').start_ms).toBe(2000);
    expect(body.timeline.captions).toEqual(row().timeline.captions); expect(state.client.timelineEdit).not.toHaveBeenCalled();
  });
  it('preserves typed trim through unrelated rerenders and resets points/consent on target changes', () => {
    const props = { timeline: row().timeline, selectedClipIds: ['audio-target'], playheadMs: 0, marks: { inMs: null, outMs: null }, editable: true, onEdit: vi.fn() };
    const view = render(<ClipInspectorPanel {...props} />); set('请求的动作', 'trim'); set('裁剪入点（毫秒）', '0'); set('裁剪出点（毫秒）', '1500'); fireEvent.click(screen.getByLabelText('波纹闭合间隙'));
    view.rerender(<ClipInspectorPanel {...props} playheadMs={10} />); expect((screen.getByLabelText('裁剪出点（毫秒）') as HTMLInputElement).value).toBe('1500');
    click('生成编辑指令'); expect(props.onEdit).toHaveBeenCalledWith({ kind: 'clip.trim', payload: { op: 'clip.trim', clip_id: 'audio-target', in_ms: 0, out_ms: 1500, ripple: true } });
    view.rerender(<ClipInspectorPanel {...props} selectedClipIds={['at-boundary']} />);
    expect((screen.getByLabelText('裁剪出点（毫秒）') as HTMLInputElement).value).toBe(''); expect((screen.getByLabelText('波纹闭合间隙') as HTMLInputElement).checked).toBe(false);
    click('生成编辑指令'); expect(props.onEdit).toHaveBeenCalledTimes(1);
  });
});
