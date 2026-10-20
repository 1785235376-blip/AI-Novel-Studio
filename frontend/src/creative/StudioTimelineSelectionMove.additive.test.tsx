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
  return checkedTimelineRow({ id: 'timeline-selection-move', version: 1, timeline_digest: 'b'.repeat(64), title: 'Selection move fixture', created_at: '2026-10-17', updated_at: '2026-10-17',
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
  await act(async () => hook.result.current.checkServer('timeline-selection-move'));
  act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
}
describe('atomic local selection move', () => {
  it.each([500, -1000])('moves selected clips by %s in one history entry preserving all other fields', async offset => {
    const state = setup(); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    const expected = cloneTimeline(before); for (const id of ['audio-target', 'at-boundary']) find(expected, id).start_ms += offset;
    expected.timeline.tracks[1].clips.sort((a, b) => a.start_ms - b.start_ms);
    act(() => { expect(state.hook!.result.current.moveSelection(['audio-target', 'at-boundary'], offset)).toBe(true); });
    expect(state.hook!.result.current.draft).toEqual(expected);
    expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineEdit).not.toHaveBeenCalled();
    expect(state.client.timelineRender).not.toHaveBeenCalled();
    act(() => state.hook!.result.current.undo()); expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
    act(() => state.hook!.result.current.redo()); expect(state.hook!.result.current.draft).toEqual(expected);
    await act(async () => state.hook!.result.current.save());
    expect(state.client.timelineSave).toHaveBeenCalledWith('timeline-selection-move', { ...expected, expected_version: 1 });
    await act(async () => state.hook!.result.current.checkServer());
    act(() => state.hook!.result.current.setAdoptConfirmed(true)); act(() => state.hook!.result.current.adoptCandidate(false));
    expect(state.hook!.result.current.draft).toEqual(expected);
  });
  it.each([0, -1001, 9000, 0.5, NaN, Infinity])('rejects/no-ops %s atomically', async offset => {
    const state = setup(); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    act(() => { expect(state.hook!.result.current.moveSelection(['audio-target', 'later'], offset)).toBe(false); });
    expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it.each([[], ['audio-target', 'audio-target'], ['missing'], ['audio-target', 'missing']].map(ids => ({ ids })))('rejects invalid selection $ids', async ({ ids }) => {
    const state = setup(); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    act(() => { expect(state.hook!.result.current.moveSelection(ids, 100)).toBe(false); });
    expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it('moves adjacent video clips despite transient overlap and rejects final collision', async () => {
    const input = row(), first = find(input, 'still'); first.out_ms = 2000;
    input.timeline.tracks[0].clips.push({ ...cloneTimeline(first), id: 'next', start_ms: 2000 });
    const state = setup(checkedTimelineRow(input)); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    act(() => { expect(state.hook!.result.current.moveSelection(['still'], 500)).toBe(false); });
    expect(state.hook!.result.current.draft).toEqual(before);
    act(() => { expect(state.hook!.result.current.moveSelection(['still', 'next'], 500)).toBe(true); });
    expect(find(state.hook!.result.current.draft, 'still').start_ms).toBe(500);
    expect(find(state.hook!.result.current.draft, 'next').start_ms).toBe(2500);
  });
  it('preserves a transition pair and refuses a broken partial move', async () => {
    const input = row(), first = find(input, 'still'); first.source_snapshot = source('video'); first.out_ms = 2000;
    first.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'next', duration_ms: 200 };
    const next = { ...cloneTimeline(first), id: 'next', start_ms: 1800 }; delete next.transition_out; input.timeline.tracks[0].clips.push(next);
    const state = setup(checkedTimelineRow(input)); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    act(() => { expect(state.hook!.result.current.moveSelection(['still'], 500)).toBe(false); });
    expect(state.hook!.result.current.draft).toEqual(before);
    act(() => { expect(state.hook!.result.current.moveSelection(['still', 'next'], 500)).toBe(true); });
    expect(find(state.hook!.result.current.draft, 'still').transition_out).toEqual(first.transition_out);
  });
  it('rejects locked track without touching history', async () => {
    const input = row(); input.timeline.tracks[1].locked = true; const state = setup(input); await adopt(state);
    act(() => { expect(state.hook!.result.current.moveSelection(['audio-target'], 500)).toBe(false); });
    expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it('retains callbacks on unrelated rerenders but rejects edit/undo ABA', async () => {
    const state = setup(); await adopt(state); const old = state.hook!.result.current.moveSelection;
    state.hook!.rerender({ ...state.props, assets: assets() });
    act(() => { expect(old(['audio-target'], 100)).toBe(true); }); act(() => state.hook!.result.current.undo());
    act(() => { expect(old(['audio-target'], 100)).toBe(false); });
  });
  it.each(['authority', 'busy', 'permission', 'client', 'project', 'unmount'] as const)('refuses retained callback after %s', async fault => {
    const state = setup(); await adopt(state); const old = state.hook!.result.current.moveSelection;
    if (fault === 'unmount') state.hook!.unmount();
    else state.hook!.rerender({ ...state.props, ...(fault === 'authority' ? { isCurrent: () => false } : fault === 'busy' ? { busy: true }
      : fault === 'permission' ? { canMutate: false } : fault === 'project' ? { projectId: 'other' } : { client: { ...state.client } as unknown as StudioProductionClient }) });
    act(() => { expect(old(['audio-target'], 100)).toBe(false); });
  });
  it.each([409, 500])('blocks after unconfirmed Save %s', async status => {
    const state = setup(); await adopt(state); act(() => { state.hook!.result.current.moveSelection(['audio-target'], 100); });
    state.client.timelineSave.mockRejectedValueOnce(new ApiError({ status, code: 'FAILED', message: 'failed' }));
    await act(async () => state.hook!.result.current.save());
    act(() => { expect(state.hook!.result.current.moveSelection(['audio-target'], 100)).toBe(false); });
  });
  it('blocks during pending Save', async () => {
    const state = setup(); await adopt(state); act(() => { state.hook!.result.current.moveSelection(['audio-target'], 100); });
    const pending = deferred<StudioTimelineRow>(); state.client.timelineSave.mockReturnValueOnce(pending.promise);
    let saving!: Promise<void>; act(() => { saving = state.hook!.result.current.save(); });
    act(() => { expect(state.hook!.result.current.moveSelection(['audio-target'], 100)).toBe(false); });
    await act(async () => { pending.resolve(row()); await saving; });
  });
});

const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const set = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
async function openPanel() {
  await screen.findByRole('option', { name: 'Selection move fixture · v1' }); set('读取已保存时间线', 'timeline-selection-move');
  await screen.findByRole('heading', { name: 'Selection move fixture · v1' });
  fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线');
}
const batch = (offset = 100) => ({ kind: 'clip.move', payload: [{ op: 'clip.move', clip_id: 'audio-target', track_id: 'sound', start_ms: 1000 + offset }] });
describe('mounted selection move routing', () => {
  it('moves the whole selected track, undoes atomically, and saves through original CAS', async () => {
    const state = setup(row(), true); await openPanel();
    fireEvent.click(screen.getAllByRole('button', { name: '选择整条轨道的片段' })[1]);
    set('整体移动增量（毫秒，可为负）', '500'); click('整体移动所选片段');
    expect(screen.getByText(/整体移动已应用到本地草稿/)).toBeTruthy(); expect(state.client.timelineSave).not.toHaveBeenCalled();
    click('撤销本地编辑'); expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true); click('重做本地编辑');
    click('保存时间线'); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
    const body = state.client.timelineSave.mock.calls[0][1]; expect(body.expected_version).toBe(1);
    const expected = row(); expected.timeline.tracks[1].clips.forEach(clip => { clip.start_ms += 500; });
    expect(body.timeline).toEqual(expected.timeline); expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
    state.view!.unmount(); render(<StudioTimelineEditor {...state.props} />);
    await screen.findByRole('option', { name: 'Selection move fixture · v2' }); set('读取已保存时间线', 'timeline-selection-move');
    await screen.findByRole('heading', { name: 'Selection move fixture · v2' });
    fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线');
    expect((within(screen.getByRole('region', { name: '轨道 2 片段 1' })).getByLabelText('放入时间线（毫秒）') as HTMLInputElement).value).toBe('1500');
  });
  it('refuses retained selection ABA callback while a fresh callback works', async () => {
    setup(row(), true); await openPanel(); click('audio-target'); const old = routed.edit!;
    click('later'); click('audio-target'); act(() => old(batch()));
    expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    act(() => routed.edit!(batch())); expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(false);
  });
  it('refuses incomplete, changed-track, extra-field and unequal-offset batches', async () => {
    setup(row(), true); await openPanel(); fireEvent.click(screen.getAllByRole('button', { name: '选择整条轨道的片段' })[1]);
    const good = row().timeline.tracks[1].clips.map(clip => ({ op: 'clip.move', clip_id: clip.id, track_id: 'sound', start_ms: clip.start_ms + 100 }));
    for (const payload of [good.slice(1), good.map((op, i) => i ? op : { ...op, track_id: 'other-sound' }),
      good.map((op, i) => i ? op : { ...op, ripple: true }), good.map((op, i) => i ? op : { ...op, start_ms: op.start_ms + 1 })]) {
      act(() => routed.edit!({ kind: 'clip.move', payload }));
      expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    }
  });
  it.each(['authority', 'isBusy', 'permission', 'project'] as const)('invalidates controller callback through observed %s ABA', async fault => {
    const state = setup(); await adopt(state); const old = state.hook!.result.current.moveSelection;
    state.hook!.rerender({ ...state.props, ...(fault === 'authority' ? { isCurrent: () => false }
      : fault === 'isBusy' ? { isBusy: () => true } : fault === 'permission' ? { canMutate: false } : { projectId: 'other' }) });
    state.hook!.rerender(state.props);
    act(() => { expect(old(['audio-target'], 100)).toBe(false); });
  });
});
