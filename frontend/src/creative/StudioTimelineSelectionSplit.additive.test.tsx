// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { applySelectionSplit, selectionSplitOperations } from '../nle/timelineSelectionSplit';
import { ClipInspectorPanel } from '../nle/ClipInspectorPanel';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimelineRow, cloneTimeline, type StudioTimelineClip, type StudioTimelineDraft, type StudioTimelineRow } from './studioTimelineTypes';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';

const routed = vi.hoisted(() => ({ edit: undefined as undefined | ((command: { kind: string; payload: unknown }) => void), select: undefined as undefined | ((ids: string[]) => void), playhead: undefined as undefined | ((value: number) => void) }));
vi.mock('../nle/TimelineWorkspacePanel', async importOriginal => {
  const actual = await importOriginal<typeof import('../nle/TimelineWorkspacePanel')>();
  return { ...actual, TimelineWorkspacePanel: (p: React.ComponentProps<typeof actual.TimelineWorkspacePanel>) => {
    routed.edit = p.onEdit as typeof routed.edit; routed.select = p.onSelectClips; routed.playhead = p.onPlayhead; return <actual.TimelineWorkspacePanel {...p} />;
  } };
});

const splitButton = vi.hoisted(() => ({ click: undefined as undefined | (() => void) }));
vi.mock('../ui/primitives', async importOriginal => {
  const actual = await importOriginal<typeof import('../ui/primitives')>();
  return { ...actual, Button: (props: React.ComponentProps<typeof actual.Button>) => {
    if (props.children === '在播放头拆分所选片段') splitButton.click = props.onClick as () => void;
    return <actual.Button {...props} />;
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

describe('reviewed selected split', () => {
  it('applies one undo/redo and original CAS Save/reopen, preserving skipped and unselected clips', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!, before = cloneTimeline(hook.result.current.draft!);
    const selection = ['audio-target', 'still', 'at-boundary'];
    const ids = { 'audio-target': 'right-a', still: 'right-image' };
    const expected = { ...before, timeline: applySelectionSplit(before.timeline, selection, 2000, ids) };
    act(() => expect(hook.result.current.splitSelection(selection, 2000, ids)).toBe(true));
    expect(hook.result.current.draft).toEqual(expected); expect(find(expected, 'audio-target').out_ms).toBe(2100);
    expect(find(expected, 'right-a').in_ms).toBe(2100); expect(find(expected, 'at-boundary')).toEqual(find(before, 'at-boundary'));
    expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineEdit).not.toHaveBeenCalled();
    act(() => hook.result.current.undo()); expect(hook.result.current.draft).toEqual(before); expect(hook.result.current.canUndo).toBe(false);
    act(() => hook.result.current.redo()); expect(hook.result.current.draft).toEqual(expected);
    await act(async () => hook.result.current.save()); expect(state.client.timelineSave).toHaveBeenCalledWith('timeline-selection-duplicate', { ...expected, expected_version: 1 });
    await act(async () => hook.result.current.checkServer()); act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
    expect(hook.result.current.draft).toEqual(expected);
  });
  it('rejects fractional cuts, collisions, repeated calls and undo ABA without partial history', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!, before = cloneTimeline(hook.result.current.draft!);
    act(() => expect(hook.result.current.splitSelection(['audio-target'], 2001, { 'audio-target': 'right' })).toBe(false));
    act(() => expect(hook.result.current.splitSelection(['audio-target'], 2000, { 'audio-target': 'still' })).toBe(false));
    expect(hook.result.current.draft).toEqual(before); expect(hook.result.current.canUndo).toBe(false);
    const retained = hook.result.current.splitSelection;
    act(() => { expect(retained(['audio-target'], 2000, { 'audio-target': 'right' })).toBe(true); expect(retained(['audio-target'], 2000, { 'audio-target': 'again' })).toBe(false); });
    act(() => hook.result.current.undo()); act(() => expect(retained(['audio-target'], 2000, { 'audio-target': 'again' })).toBe(false));
  });
  it('preflights without allocating, presents ordered affected/skipped rows and allocates once on explicit Apply', () => {
    const onEdit = vi.fn(), newId = vi.fn(() => 'right');
    const props = { timeline: row().timeline, selectedClipIds: ['at-boundary', 'audio-target'], playheadMs: 2000, marks: { inMs: null, outMs: null }, editable: true, newId, onEdit };
    const view = render(<ClipInspectorPanel {...props} />);
    expect(newId).not.toHaveBeenCalled(); expect(screen.getByLabelText('播放头拆分预览').textContent).toMatch(/at-boundary.*跳过.*audio-target.*拆分为左右两段/);
    const button = screen.getByRole('button', { name: '在播放头拆分所选片段' });
    fireEvent.click(button); fireEvent.click(button); expect(newId).toHaveBeenCalledTimes(1); expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit.mock.calls[0][0].payload).toEqual(selectionSplitOperations(props.timeline, props.selectedClipIds, 2000, { 'audio-target': 'right' }));
    view.rerender(<ClipInspectorPanel {...props} playheadMs={2001} />); expect(screen.getByRole('button', { name: '在播放头拆分所选片段' }).hasAttribute('disabled')).toBe(true);
  });
});

const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
async function openPanel() {
  await screen.findByRole('option', { name: 'Selection duplicate fixture · v1' });
  fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: 'timeline-selection-duplicate' } });
  await screen.findByRole('heading', { name: 'Selection duplicate fixture · v1' });
  fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线');
  act(() => { routed.select!(['audio-target']); routed.playhead!(2000); });
}
const splitBatch = () => ({ kind: 'clip.split', payload: selectionSplitOperations(row().timeline, ['audio-target'], 2000, { 'audio-target': 'right' }) });
describe('mounted selected split fences', () => {
  it.each(['selection', 'playhead'] as const)('rejects retained %s ABA, and permits only fresh exact review once', async fault => {
    const state = setup(row(), true); await openPanel(); const retained = routed.edit!;
    if (fault === 'selection') { act(() => routed.select!(['still'])); act(() => routed.select!(['audio-target'])); }
    else { act(() => routed.playhead!(2002)); act(() => routed.playhead!(2000)); }
    act(() => retained(splitBatch())); expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    const fresh = routed.edit!; act(() => { fresh(splitBatch()); fresh(splitBatch()); });
    click('保存时间线'); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
    expect(state.client.timelineSave.mock.calls[0][1].timeline.tracks.flatMap(track => track.clips).filter(clip => clip.id === 'right')).toHaveLength(1);
  });
  it('rejects omitted, extra, forged-point and scalar descriptors without history', async () => {
    setup(row(), true); await openPanel(); const operation = splitBatch().payload[0];
    for (const payload of [[], [operation, operation], [{ ...operation, at_ms: 2002 }], [{ ...operation, extra: undefined }], operation]) {
      act(() => routed.edit!({ kind: 'clip.split', payload }));
      expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    }
  });
  it.each(['authority', 'busy', 'isBusy', 'permission', 'client', 'project', 'unmount'] as const)('rejects retained controller %s callback after observed ABA', async fault => {
    const state = setup(); await adopt(state); const hook = state.hook!, old = hook.result.current.splitSelection;
    if (fault === 'unmount') hook.unmount();
    else {
      hook.rerender({ ...state.props, ...(fault === 'authority' ? { isCurrent: () => false } : fault === 'busy' ? { busy: true }
        : fault === 'isBusy' ? { isBusy: () => true } : fault === 'permission' ? { canMutate: false } : fault === 'project' ? { projectId: 'other' }
        : { client: { ...state.client } as unknown as StudioProductionClient }) });
      hook.rerender(state.props);
    }
    act(() => expect(old(['audio-target'], 2000, { 'audio-target': 'right' })).toBe(false));
  });
});

it.each(['project', 'isBusy'] as const)('retires retained inspector Apply before allocating on %s ABA', async fault => {
  const state = setup(row(), true); await openPanel(); const old = splitButton.click!;
  const uuid = vi.spyOn(globalThis.crypto, 'randomUUID');
  state.view!.rerender(<StudioTimelineEditor {...state.props} {...(fault === 'project' ? { projectId: 'other' } : { isBusy: () => true })} />);
  state.view!.rerender(<StudioTimelineEditor {...state.props} />);
  act(() => old()); expect(uuid).not.toHaveBeenCalled();
  expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '在播放头拆分所选片段' })); expect(uuid).toHaveBeenCalledTimes(1);
});

it('legacy single-clip split keeps the right outgoing transition and removes it from the left through the shared owner-parity path', async () => {
  const input = row(), first = find(input, 'still'); first.source_snapshot = source('video'); first.out_ms = 2000;
  first.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: 'next', duration_ms: 200 };
  const next = { ...cloneTimeline(first), id: 'next', start_ms: 1800 }; delete next.transition_out; input.timeline.tracks[0].clips.push(next);
  const state = setup(checkedTimelineRow(input)); await adopt(state); const hook = state.hook!, before = cloneTimeline(hook.result.current.draft!);
  const uuid = vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue('11111111-1111-4111-8111-111111111111');
  act(() => hook.result.current.splitClip('visual', 'still', 1000));
  expect(uuid).toHaveBeenCalledTimes(1);
  expect(hook.result.current.draft!.timeline).toEqual(applySelectionSplit(before.timeline, ['still'], 1000, { still: '11111111-1111-4111-8111-111111111111' }));
  expect(find(hook.result.current.draft, 'still').transition_out).toBeUndefined();
  expect(find(hook.result.current.draft, '11111111-1111-4111-8111-111111111111').transition_out).toEqual(first.transition_out);
  act(() => hook.result.current.undo()); expect(hook.result.current.draft).toEqual(before); expect(hook.result.current.canUndo).toBe(false);
});
