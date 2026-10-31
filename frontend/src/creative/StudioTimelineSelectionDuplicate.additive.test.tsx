// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { selectionDuplicateOperations } from '../nle/timelineSelectionDuplicate';
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
  return checkedTimelineRow({ id: 'timeline-selection-duplicate', version: 1, timeline_digest: 'b'.repeat(64), title: 'Selection duplicate fixture', created_at: '2026-10-17', updated_at: '2026-10-17',
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
  await act(async () => hook.result.current.checkServer('timeline-selection-duplicate'));
  act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
}

const map = { 'audio-target': 'copy-target', 'at-boundary': 'copy-boundary' };
const selected = Object.keys(map);
describe('atomic local selected duplication', () => {
  it.each([0, -1000, 500])('copies exact identities at offset %s, with one undo/redo and original Save CAS', async offset => {
    const state = setup(); await adopt(state); const hook = state.hook!, before = cloneTimeline(hook.result.current.draft!);
    const expected = cloneTimeline(before);
    for (const id of selected) expected.timeline.tracks[1].clips.push({ ...cloneTimeline(find(before, id)), id: map[id as keyof typeof map], start_ms: find(before, id).start_ms + offset });
    expected.timeline = checkedTimelineRow({ ...row(), timeline: expected.timeline }).timeline;
    act(() => { expect(hook.result.current.duplicateSelection(selected, offset, map)).toBe(true); });
    expect(hook.result.current.draft).toEqual(expected);
    for (const id of before.timeline.tracks.flatMap(track => track.clips.map(clip => clip.id))) expect(find(hook.result.current.draft, id)).toEqual(find(before, id));
    expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
    act(() => hook.result.current.undo()); expect(hook.result.current.draft).toEqual(before); expect(hook.result.current.canUndo).toBe(false);
    act(() => hook.result.current.redo()); expect(hook.result.current.draft).toEqual(expected);
    await act(async () => hook.result.current.save()); expect(state.client.timelineSave).toHaveBeenCalledWith('timeline-selection-duplicate', { ...expected, expected_version: 1 });
    await act(async () => hook.result.current.checkServer()); act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
    expect(hook.result.current.draft).toEqual(expected);
  });
  it('copies across original tracks while preserving fades, gain, mute and rational trim', async () => {
    const input = row(); find(input, 'audio-target').fade_in_ms = 200; find(input, 'audio-target').fade_out_ms = 300;
    find(input, 'audio-target').gain_db = -8; find(input, 'audio-target').muted = true;
    const state = setup(input); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    act(() => expect(state.hook!.result.current.duplicateSelection(['audio-target', 'other-track'], 0, { 'audio-target': 'new-a', 'other-track': 'new-b' })).toBe(true));
    expect(find(state.hook!.result.current.draft, 'new-a')).toEqual({ ...find(before, 'audio-target'), id: 'new-a' });
    expect(state.hook!.result.current.draft!.timeline.tracks[2].clips.some(clip => clip.id === 'new-b')).toBe(true);
  });
  it.each([-1001, 9000, 0.5, NaN, Infinity])('rejects invalid offset %s atomically', async offset => {
    const state = setup(); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    act(() => expect(state.hook!.result.current.duplicateSelection(selected, offset, map)).toBe(false));
    expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it('rejects existing or missing identities and locked tracks without history', async () => {
    const input = row(); input.timeline.tracks[2].locked = true; const state = setup(input); await adopt(state); const before = cloneTimeline(state.hook!.result.current.draft!);
    for (const mapping of [{}, { 'audio-target': 'still' }, { 'audio-target': 'other-track' }] as Array<Record<string, string>>) {
      act(() => expect(state.hook!.result.current.duplicateSelection(['audio-target'], 0, mapping)).toBe(false));
    }
    act(() => expect(state.hook!.result.current.duplicateSelection(['other-track'], 0, { 'other-track': 'new' })).toBe(false));
    expect(state.hook!.result.current.draft).toEqual(before); expect(state.hook!.result.current.canUndo).toBe(false);
  });
  it('remaps internal transition pairs and omits external outgoing relationships while retaining originals', async () => {
    const input = row(), first = find(input, 'still'); first.source_snapshot = source('video'); first.out_ms = 2000;
    first.crop = { x: 0, y: 0, width: 64, height: 64 };
    first.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'next', duration_ms: 200 };
    const next = { ...cloneTimeline(first), id: 'next', start_ms: 1800 }; delete next.transition_out; input.timeline.tracks[0].clips.push(next);
    const state = setup(checkedTimelineRow(input)); await adopt(state); const hook = state.hook!, before = cloneTimeline(hook.result.current.draft!);
    act(() => expect(hook.result.current.duplicateSelection(['still', 'next'], 0, { still: 'copy-still', next: 'copy-next' })).toBe(false));
    expect(hook.result.current.draft).toEqual(before); expect(hook.result.current.canUndo).toBe(false);
    act(() => expect(hook.result.current.duplicateSelection(['next', 'still'], 4000, { still: 'copy-still', next: 'copy-next' })).toBe(true));
    expect(find(hook.result.current.draft, 'copy-still')).toEqual({ ...find(before, 'still'), id: 'copy-still', start_ms: 4000,
      transition_out: { kind: 'CROSS_DISSOLVE', to_clip_id: 'copy-next', duration_ms: 200 } });
    expect(find(hook.result.current.draft, 'still')).toEqual(find(before, 'still'));
    act(() => hook.result.current.undo());
    act(() => expect(hook.result.current.duplicateSelection(['still'], 4000, { still: 'external-copy' })).toBe(true));
    expect(find(hook.result.current.draft, 'external-copy').transition_out).toBeUndefined(); expect(find(hook.result.current.draft, 'still').transition_out).toEqual(first.transition_out);
  });
  it('suppresses repeated retained callback and draft undo ABA, preserving unrelated-rerender validity', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!, old = hook.result.current.duplicateSelection;
    hook.rerender({ ...state.props, assets: assets() });
    act(() => { expect(old(selected, 0, map)).toBe(true); expect(old(selected, 0, map)).toBe(false); });
    act(() => hook.result.current.undo()); act(() => expect(old(selected, 0, map)).toBe(false));
    expect(hook.result.current.canUndo).toBe(false);
  });
  it.each(['authority', 'busy', 'isBusy', 'permission', 'client', 'project', 'unmount'] as const)('rejects retained %s callback, including observed ABA', async fault => {
    const state = setup(); await adopt(state); const hook = state.hook!, old = hook.result.current.duplicateSelection;
    if (fault === 'unmount') hook.unmount();
    else {
      hook.rerender({ ...state.props, ...(fault === 'authority' ? { isCurrent: () => false } : fault === 'busy' ? { busy: true }
        : fault === 'isBusy' ? { isBusy: () => true } : fault === 'permission' ? { canMutate: false } : fault === 'project' ? { projectId: 'other' }
        : { client: { ...state.client } as unknown as StudioProductionClient }) });
      hook.rerender(state.props);
    }
    act(() => expect(old(selected, 0, map)).toBe(false));
  });
  it.each([409, 500])('retains draft and refuses duplication after Save failure %s', async status => {
    const state = setup(); await adopt(state); const hook = state.hook!;
    act(() => expect(hook.result.current.duplicateSelection(selected, 0, map)).toBe(true));
    const before = cloneTimeline(hook.result.current.draft!); state.client.timelineSave.mockRejectedValueOnce(new ApiError({ status, code: 'FAILED', message: 'failed' }));
    await act(async () => hook.result.current.save()); act(() => expect(hook.result.current.duplicateSelection(['audio-target'], 0, { 'audio-target': 'new' })).toBe(false));
    expect(hook.result.current.draft).toEqual(before);
  });
  it('preserves source pins locally but explicit Save refuses unavailable sources', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!;
    hook.rerender({ ...state.props, assets: [] });
    act(() => expect(hook.result.current.duplicateSelection(selected, 0, map)).toBe(true));
    const before = cloneTimeline(hook.result.current.draft!);
    await act(async () => hook.result.current.save());
    expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(hook.result.current.draft).toEqual(before);
    expect(hook.result.current.error).toMatch(/素材版本已变化或不可用/);
  });
  it('rejects while Save is pending', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!;
    act(() => expect(hook.result.current.duplicateSelection(selected, 0, map)).toBe(true));
    const pending = deferred<StudioTimelineRow>(); state.client.timelineSave.mockReturnValueOnce(pending.promise);
    let saving!: Promise<void>; act(() => { saving = hook.result.current.save(); });
    act(() => expect(hook.result.current.duplicateSelection(['audio-target'], 0, { 'audio-target': 'new' })).toBe(false));
    await act(async () => { pending.resolve(row()); await saving; });

  });
});
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const set = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
async function openPanel() {
  await screen.findByRole('option', { name: 'Selection duplicate fixture · v1' }); set('读取已保存时间线', 'timeline-selection-duplicate');
  await screen.findByRole('heading', { name: 'Selection duplicate fixture · v1' });
  fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线');
}
const batch = () => ({ kind: 'clip.duplicate', payload: selectionDuplicateOperations(row().timeline, ['audio-target'], 0, { 'audio-target': 'copy-target' }) });
describe('mounted selected duplication route', () => {
  it('duplicates whole selected track once, preserves generated IDs through Save and fresh GET/remount', async () => {
    const state = setup(row(), true); await openPanel(); fireEvent.click(screen.getAllByRole('button', { name: '选择整条轨道的片段' })[1]);
    set('整体复制增量（毫秒，可为负或零）', '0'); click('整体复制所选片段');
    expect(screen.getByText(/整体复制已应用到本地草稿/)).toBeTruthy(); expect(state.client.timelineSave).not.toHaveBeenCalled();
    click('撤销本地编辑'); expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true); click('重做本地编辑');
    click('保存时间线'); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
    const body = state.client.timelineSave.mock.calls[0][1], originals = row().timeline.tracks[1].clips;
    expect(body.expected_version).toBe(1); expect(body.timeline.tracks[1].clips).toHaveLength(8);
    const copies = body.timeline.tracks[1].clips.filter(clip => !originals.some(original => original.id === clip.id));
    expect(new Set(copies.map(clip => clip.id)).size).toBe(4);
    originals.forEach(original => expect(body.timeline.tracks[1].clips.find(clip => clip.id === original.id)).toEqual(original));
    expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
    state.view!.unmount(); render(<StudioTimelineEditor {...state.props} />);
    await screen.findByRole('option', { name: 'Selection duplicate fixture · v2' }); set('读取已保存时间线', 'timeline-selection-duplicate');
    await screen.findByRole('heading', { name: 'Selection duplicate fixture · v2' }); fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线');
    copies.forEach(copy => expect(screen.getByRole('button', { name: copy.id })).toBeTruthy());
  });
  it('verifies exact nested transition fields before applying internal transition batches', async () => {
    const input = row(), first = find(input, 'still'); first.source_snapshot = source('video'); first.out_ms = 2000;
    first.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'next', duration_ms: 200 };
    const next = { ...cloneTimeline(first), id: 'next', start_ms: 1800 }; delete next.transition_out; input.timeline.tracks[0].clips.push(next);
    setup(checkedTimelineRow(input), true); await openPanel(); fireEvent.click(screen.getAllByRole('button', { name: '选择整条轨道的片段' })[0]);
    const good = selectionDuplicateOperations(input.timeline, ['still', 'next'], 4000, { still: 'copy-still', next: 'copy-next' });
    const update = good[2]; if (update.op !== 'clip.update') throw new Error('fixture needs update');
    for (const payload of [good.slice(0, 2), [...good.slice(0, 2), { ...update, changes: { ...update.changes, gain_db: undefined } }],
      [...good.slice(0, 2), { ...update, changes: { transition_out: { ...update.changes.transition_out, extra: undefined } } }],
      [...good.slice(0, 2), { ...update, changes: { transition_out: { ...update.changes.transition_out, to_clip_id: 'next' } } }]]) {
      act(() => routed.edit!({ kind: 'clip.duplicate', payload }));
      expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    }
    act(() => routed.edit!({ kind: 'clip.duplicate', payload: good }));
    expect(screen.getByRole('button', { name: 'copy-still' })).toBeTruthy(); expect(screen.getByRole('button', { name: 'copy-next' })).toBeTruthy();
  });
  it('rejects retained selection ABA callbacks and repeated mounted invocation', async () => {
    setup(row(), true); await openPanel(); click('audio-target'); const old = routed.edit!;
    click('later'); click('audio-target'); act(() => old(batch()));
    expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    const fresh = routed.edit!; act(() => { fresh(batch()); fresh(batch()); });
    click('撤销本地编辑'); expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('rejects missing, reordered, wrong-track, unequal-offset, extra-key and unauthorized-update descriptors', async () => {
    setup(row(), true); await openPanel(); fireEvent.click(screen.getAllByRole('button', { name: '选择整条轨道的片段' })[1]);
    const clips = row().timeline.tracks[1].clips, ids = Object.fromEntries(clips.map(clip => [clip.id, `new-${clip.id}`]));
    const good = selectionDuplicateOperations(row().timeline, clips.map(clip => clip.id), 0, ids);
    for (const payload of [good.slice(1), [...good].reverse(), good.map((op, i) => i ? op : { ...op, track_id: 'other-sound' }),
      good.map((op, i) => i ? op : { ...op, start_ms: 1001 }), good.map((op, i) => i ? op : { ...op, extra: undefined }),
      [...good, { op: 'clip.update', clip_id: 'audio-target', changes: { gain_db: 1 } }], Array(4)]) {
      act(() => routed.edit!({ kind: 'clip.duplicate', payload }));
      expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    }
  });
});
