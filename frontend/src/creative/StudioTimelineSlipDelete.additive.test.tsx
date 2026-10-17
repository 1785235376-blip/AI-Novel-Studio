// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimelineRow, cloneTimeline, type StudioTimelineClip, type StudioTimelineDraft, type StudioTimelineRow } from './studioTimelineTypes';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';

const routed = vi.hoisted(() => ({ edit: undefined as undefined | ((command: { kind: string; payload: unknown }) => void) }));
vi.mock('../nle/TimelineWorkspacePanel', async importOriginal => {
  const actual = await importOriginal<typeof import('../nle/TimelineWorkspacePanel')>();
  return { ...actual, TimelineWorkspacePanel: (p: React.ComponentProps<typeof actual.TimelineWorkspacePanel>) => {
    routed.edit = p.onEdit as typeof routed.edit; return <actual.TimelineWorkspacePanel {...p} />;
  } };
});

// Synthetic controller fixtures, not claims of real media/render verification.
const source = (kind: 'image' | 'audio' | 'video') => ({ id: `asset-${kind}`, kind: 'ASSET' as const, asset_kind: kind, version: 1, digest: 'a'.repeat(64) });
const audio = (id: string, start: number): StudioTimelineClip => ({ id, source_snapshot: source('audio'), start_ms: start, in_ms: 0, out_ms: 300,
  speed_num: 1, speed_den: 1, fade_in_ms: 0, fade_out_ms: 0 });
function row(): StudioTimelineRow {
  return checkedTimelineRow({ id: 'timeline-slip-delete', version: 1, timeline_digest: 'b'.repeat(64), title: 'Slip/delete fixture', created_at: '2026-10-17', updated_at: '2026-10-17',
    timeline: { schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25, captions: [{ start_ms: 3500, end_ms: 4500, text: 'Unchanged caption' }], tracks: [
      { id: 'visual', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'still', source_snapshot: source('image'), start_ms: 0, in_ms: 0, out_ms: 7000, x: 0, y: 0, width: 64, height: 64 }] },
      { id: 'sound', kind: 'AUDIO', order: 1, muted: false, gain_db: 0, clips: [
        { ...audio('audio-target', 1000), in_ms: 600, out_ms: 3600, speed_num: 3, speed_den: 2 }, audio('before-boundary', 2999), audio('at-boundary', 3000), audio('later', 4500)] },
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
  await act(async () => hook.result.current.checkServer('timeline-slip-delete'));
  act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
}
function apply(state: ReturnType<typeof setup>, action: 'slip' | 'remove', offset = 500, ripple = true, track = 'sound', id = 'audio-target') {
  let result = false;
  act(() => { result = action === 'slip' ? state.hook!.result.current.slipClip(track, id, offset) : state.hook!.result.current.rippleRemoveClip(track, id, ripple); });
  return result;
}
describe('local slip and explicit ripple delete', () => {
  it.each([500, -600, 3000])('slips by %s without changing placement, duration or neighbors', async offset => {
    const state = setup(); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    expect(apply(state, 'slip', offset)).toBe(true); const after = cloneTimeline(state.hook!.result.current.draft!);
    const expected = cloneTimeline(before); find(expected, 'audio-target').in_ms += offset; find(expected, 'audio-target').out_ms += offset;
    expect(after).toEqual(expected); expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineEdit).not.toHaveBeenCalled();
    act(() => state.hook!.result.current.undo()); expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
    act(() => state.hook!.result.current.redo()); expect(state.hook!.result.current.draft).toEqual(after);
  });
  it('deletes with rational duration and exactly the OLD end threshold in one undo step', async () => {
    const state = setup(); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    expect(apply(state, 'remove')).toBe(true); const after = state.hook!.result.current.draft!;
    const expected = cloneTimeline(before); expected.timeline.tracks[1].clips = expected.timeline.tracks[1].clips.filter(clip => clip.id !== 'audio-target');
    find(expected, 'at-boundary').start_ms = 1000; find(expected, 'later').start_ms = 2500; expected.timeline.tracks[1].clips.sort((a, b) => a.start_ms - b.start_ms);
    expect(after).toEqual(expected); expect(find(after, 'before-boundary').start_ms).toBe(2999);
    act(() => state.hook!.result.current.undo()); expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
    act(() => state.hook!.result.current.redo()); expect(state.hook!.result.current.draft).toEqual(expected);
  });
  it.each([0, -601, 0.5, Number.NaN, Number.POSITIVE_INFINITY, 36000000])('rejects slip %s without mutation/history', async offset => {
    const state = setup(); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    expect(apply(state, 'slip', offset)).toBe(false); expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it.each(['image', 'last', 'consent', 'locked'] as const)('rejects %s atomically', async fault => {
    const input = row(); if (fault === 'locked') input.timeline.tracks[1].locked = true;
    const state = setup(input); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    expect(apply(state, fault === 'image' ? 'slip' : 'remove', 500, fault !== 'consent', fault === 'image' || fault === 'last' ? 'visual' : 'sound', fault === 'image' || fault === 'last' ? 'still' : 'audio-target')).toBe(false);
    expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it('preserves video transitions, source pins and rational speed during slip', async () => {
    const input = row(), left = find(input, 'still'); left.source_snapshot = source('video'); left.in_ms = 600; left.out_ms = 3600; left.speed_num = 3; left.speed_den = 2;
    left.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'next', duration_ms: 200 };
    const right = { ...cloneTimeline(left), id: 'next', start_ms: 1800 }; delete right.transition_out; input.timeline.tracks[0].clips.push(right);
    const state = setup(checkedTimelineRow(input)); await adopt(state); const expected = cloneTimeline(state.hook!.result.current.draft!);
    find(expected, 'still').in_ms += 1; find(expected, 'still').out_ms += 1;
    expect(apply(state, 'slip', 1, false, 'visual', 'still')).toBe(true); expect(state.hook!.result.current.draft).toEqual(expected);
  });
  it('refuses a dangling predecessor transition without repairing it', async () => {
    const input = row(), left = find(input, 'still'); left.out_ms = 2000;
    left.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'next', duration_ms: 200 };
    input.timeline.tracks[0].clips.push({ ...cloneTimeline(left), id: 'next', start_ms: 1800, out_ms: 2000, transition_out: undefined });
    delete input.timeline.tracks[0].clips[1].transition_out;
    const state = setup(checkedTimelineRow(input)); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    expect(apply(state, 'remove', 0, true, 'visual', 'next')).toBe(false); expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it.each(['slip', 'remove'] as const)('retains current callback but refuses stale %s after edit/undo', async action => {
    const state = setup(); await adopt(state); const c = state.hook!.result.current;
    state.hook!.rerender({ ...state.props, assets: assets() }); let result = false;
    act(() => { result = action === 'slip' ? c.slipClip('sound', 'audio-target', 500) : c.rippleRemoveClip('sound', 'audio-target', true); }); expect(result).toBe(true);
    act(() => state.hook!.result.current.undo());
    act(() => { result = action === 'slip' ? c.slipClip('sound', 'audio-target', 500) : c.rippleRemoveClip('sound', 'audio-target', true); }); expect(result).toBe(false);
  });
  it.each(['authority', 'busy', 'permission', 'client', 'unmount'] as const)('refuses both retained callbacks after %s', async fault => {
    const state = setup(); await adopt(state); const c = state.hook!.result.current;
    if (fault === 'unmount') state.hook!.unmount();
    else state.hook!.rerender({ ...state.props, ...(fault === 'authority' ? { isCurrent: () => false } : fault === 'busy' ? { busy: true } : fault === 'permission' ? { canMutate: false } : { client: { ...state.client } as unknown as StudioProductionClient }) });
    act(() => { expect(c.slipClip('sound', 'audio-target', 500)).toBe(false); expect(c.rippleRemoveClip('sound', 'audio-target', true)).toBe(false); });
  });
  it.each([409, 503])('preserves Save failure %s without editing or replay', async status => {
    const state = setup(); await adopt(state); apply(state, 'slip');
    state.client.timelineSave.mockRejectedValueOnce(new ApiError({ status, code: 'TEST_FAILURE', message: 'Synthetic failure' }));
    await act(async () => state.hook!.result.current.save()); const before = cloneTimeline(state.hook!.result.current.draft!);
    expect(apply(state, 'slip')).toBe(false); expect(apply(state, 'remove')).toBe(false);
    await act(async () => state.hook!.result.current.save()); expect(state.hook!.result.current.draft).toEqual(before); expect(state.client.timelineSave).toHaveBeenCalledTimes(1);
  });
  it('blocks both edits while original Save is pending', async () => {
    const state = setup(); await adopt(state); apply(state, 'slip'); const pending = deferred<StudioTimelineRow>();
    state.client.timelineSave.mockReturnValueOnce(pending.promise); let promise!: Promise<void>;
    act(() => { promise = state.hook!.result.current.save(); }); expect(apply(state, 'slip')).toBe(false); expect(apply(state, 'remove')).toBe(false);
    await act(async () => { pending.resolve(checkedTimelineRow({ ...row(), ...state.hook!.result.current.draft!, version: 2, timeline_digest: 'c'.repeat(64) })); await promise; });
  });
});
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const set = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
async function openPanel() {
  await screen.findByRole('option', { name: 'Slip/delete fixture · v1' }); set('读取已保存时间线', 'timeline-slip-delete');
  await screen.findByRole('heading', { name: 'Slip/delete fixture · v1' });
  fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线');
}
describe('mounted original editor slip/delete Save undo and reopen', () => {
  it('refuses extra fields, wrong targets and retained bridge callbacks after a draft generation change', async () => {
    setup(row(), true); await openPanel(); click('audio-target'); const callback = routed.edit!;
    act(() => callback({ kind: 'clip.slip', payload: { op: 'clip.slip', clip_id: 'audio-target', offset_ms: 500, start_ms: 0 } }));
    act(() => callback({ kind: 'clip.remove', payload: { op: 'clip.remove', clip_id: 'later', ripple: true } }));
    act(() => callback({ kind: 'clip.remove', payload: { op: 'clip.remove', clip_id: 'audio-target', ripple: false } }));
    expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    act(() => callback({ kind: 'clip.slip', payload: { op: 'clip.slip', clip_id: 'audio-target', offset_ms: 500 } }));
    click('撤销本地编辑');
    act(() => callback({ kind: 'clip.remove', payload: { op: 'clip.remove', clip_id: 'audio-target', ripple: true } }));
    expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole('button', { name: 'audio-target' })).toBeTruthy();
  });
  it.each(['slip', 'ripple'])('routes %s without timeline position and persists only with original CAS', async action => {
    const state = setup(row(), true); await openPanel(); click('audio-target'); set('请求的动作', action);
    if (action === 'slip') set('滑移增量（毫秒）', '500'); else fireEvent.click(screen.getByLabelText('波纹闭合间隙'));
    click('生成编辑指令'); expect(state.client.timelineSave).not.toHaveBeenCalled();
    expect(screen.getByText(/片段编辑已应用到本地草稿/)).toBeTruthy();
    click('撤销本地编辑'); expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true); click('重做本地编辑');
    click('保存时间线'); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
    const body = state.client.timelineSave.mock.calls[0][1]; expect(body.expected_version).toBe(1);
    if (action === 'slip') expect(find(body, 'audio-target')).toMatchObject({ in_ms: 1100, out_ms: 4100, start_ms: 1000 });
    else { expect(find(body, 'audio-target')).toBeUndefined(); expect(find(body, 'at-boundary').start_ms).toBe(1000); }
    state.view!.unmount(); render(<StudioTimelineEditor {...state.props} />);
    await screen.findByRole('option', { name: 'Slip/delete fixture · v2' }); set('读取已保存时间线', 'timeline-slip-delete');
    await screen.findByRole('heading', { name: 'Slip/delete fixture · v2' });
    fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线');
    if (action === 'slip') expect((within(screen.getByRole('region', { name: '轨道 2 片段 1' })).getByLabelText('素材入点（毫秒）') as HTMLInputElement).value).toBe('1100');
    else expect(screen.queryByRole('button', { name: 'audio-target' })).toBeNull();
    expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
  });
});
