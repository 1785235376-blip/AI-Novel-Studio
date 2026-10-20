// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { LinkedClipTrimPanel } from '../nle/LinkedClipTrimPanel';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimelineRow, cloneTimeline, type StudioTimelineDraft, type StudioTimelineRow } from './studioTimelineTypes';
import { linkedTrimFacts, trimLinkedTimeline } from './studioTimelineLinkedTrim';
import { requireClipLinkPreservation } from './studioTimelineClipLinks';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';

const routed = vi.hoisted(() => ({ trim: undefined as undefined | ((from: number, to: number) => void), click: undefined as undefined | (() => void) }));
vi.mock('../nle/LinkedClipTrimPanel', async importOriginal => {
  const actual = await importOriginal<typeof import('../nle/LinkedClipTrimPanel')>();
  return { ...actual, LinkedClipTrimPanel: (props: Parameters<typeof actual.LinkedClipTrimPanel>[0]) => { routed.trim = props.onTrim; return <actual.LinkedClipTrimPanel {...props} />; } };
});
vi.mock('../ui/primitives', async importOriginal => {
  const actual = await importOriginal<typeof import('../ui/primitives')>();
  return { ...actual, Button: (props: Parameters<typeof actual.Button>[0]) => {
    if (props.children === '按已预览区间联动裁剪链接') routed.click = props.onClick as () => void;
    return <actual.Button {...props} />;
  } };
});
const source = (kind: 'video' | 'audio') => ({ id: 'asset-' + kind, kind: 'ASSET' as const, asset_kind: kind, version: 1, digest: 'a'.repeat(64) });
function row(offset = 250): StudioTimelineRow {
  return checkedTimelineRow({ id: 'linked-trim', version: 1, title: 'Synthetic saved linked trim', timeline_digest: 'b'.repeat(64), created_at: '2026-10-20', updated_at: '2026-10-20',
    timeline: { schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25, captions: [{ start_ms: 3000, end_ms: 3500, text: 'Unselected' }], tracks: [
      { id: 'visual', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [
        { id: 'picture', source_snapshot: source('video'), start_ms: 1000, in_ms: 100, out_ms: 900, x: 0, y: 0, width: 64, height: 64 },
        { id: 'picture-other', source_snapshot: source('video'), start_ms: 4000, in_ms: 0, out_ms: 500, x: 0, y: 0, width: 64, height: 64 }] },
      { id: 'voice', kind: 'AUDIO', order: 1, muted: false, gain_db: 0, clips: [
        { id: 'sound', source_snapshot: source('audio'), start_ms: 1000 + offset, in_ms: 50, out_ms: 850 },
        { id: 'sound-other', source_snapshot: source('audio'), start_ms: 4000, in_ms: 0, out_ms: 500 }] },
    ], clip_links: [{ video_clip_id: 'picture', audio_clip_id: 'sound', offset_ms: offset }] } });
}
const assets = () => ['video', 'audio'].map(kind => ({ id: 'asset-' + kind, kind, version: 1, sha256: 'a'.repeat(64), deleted_at: null })) as unknown as StudioAsset[];
const clips = (draft: StudioTimelineDraft) => new Map(draft.timeline.tracks.flatMap(track => track.clips).map(clip => [clip.id, clip]));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function setup(input = row(), panel = false) {
  let saved = cloneTimeline(input);
  const client = { timelineList: vi.fn(async () => ({ items: [cloneTimeline(saved)] })), timelineGet: vi.fn(async () => cloneTimeline(saved)),
    timelineSave: vi.fn(async (_id: string | undefined, body: StudioTimelineDraft & { expected_version: number }) => {
      saved = checkedTimelineRow({ ...saved, ...body, version: body.expected_version + 1, timeline_digest: 'c'.repeat(64) }); return cloneTimeline(saved);
    }), timelineRender: vi.fn(), timelineEdit: vi.fn(), list: vi.fn(async () => []) };
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: assets(), canMutate: true, busy: false,
    isCurrent: () => true, read: async work => work(), mutate: async work => work(), onDirtyChange: vi.fn(), onJob: vi.fn(), onUnavailable: vi.fn() };
  const hook = panel ? undefined : renderHook((p: StudioTimelineEditorProps) => useStudioTimelineEditor(p), { initialProps: props });
  const view = panel ? render(<StudioTimelineEditor {...props} />) : undefined;
  return { props, client, hook, view };
}
async function adopt(state: ReturnType<typeof setup>) {
  const hook = state.hook!; await waitFor(() => expect(hook.result.current.rows).toHaveLength(1));
  await act(async () => hook.result.current.checkServer('linked-trim'));
  act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
}
async function openPanel() {
  await waitFor(() => expect(screen.getByLabelText('读取已保存时间线').querySelector('option[value="linked-trim"]')).toBeTruthy());
  fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: 'linked-trim' } });
  const review = await screen.findByLabelText('核对服务端时间线'); fireEvent.click(within(review).getByLabelText('已核对服务端内容与本地输入，确认以下选择'));
  fireEvent.click(within(review).getByRole('button', { name: '采用服务端时间线' }));
  fireEvent.click(within(screen.getByLabelText('轨道头')).getByRole('button', { name: 'picture' }));
}
function fill() {
  fireEvent.change(screen.getByLabelText('共同保留入点（相对毫秒）'), { target: { value: '100' } });
  fireEvent.change(screen.getByLabelText('共同保留出点（相对毫秒）'), { target: { value: '650' } });
}

describe('linked trim on original Timeline owner', () => {
  it.each([250, -250, 0])('retains both IDs, offset %s, exact subranges and all unselected content', offset => {
    const before = row(offset), expected = cloneTimeline(before);
    clips(expected).get('picture')!.in_ms = 200; clips(expected).get('picture')!.out_ms = 750;
    clips(expected).get('sound')!.in_ms = 150; clips(expected).get('sound')!.out_ms = 700;
    const after = trimLinkedTimeline(before.timeline, ['sound'], 100, 650);
    expect(after).toEqual(expected.timeline); expect(() => requireClipLinkPreservation(before.timeline, after)).not.toThrow();
    const forged = cloneTimeline(after); forged.tracks[1].clips[0].in_ms++;
    expect(() => requireClipLinkPreservation(before.timeline, forged)).toThrow();
    const shorter = cloneTimeline(before.timeline); shorter.tracks[1].clips[0].out_ms = 600;
    expect(() => linkedTrimFacts(shorter, ['picture'], 100, 650)).toThrow();
  });
  it('uses one Undo, stable Redo, CAS Save/reopen and blocks duplicate callback', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!, before = cloneTimeline(hook.result.current.draft!);
    const click = hook.result.current.trimLinkedClips;
    act(() => { expect(click(['picture'], 100, 650)).toBe(true); expect(click(['picture'], 100, 600)).toBe(false); });
    const expected = cloneTimeline(hook.result.current.draft!); expect(expected.timeline).toEqual(trimLinkedTimeline(before.timeline, ['picture'], 100, 650));
    act(() => hook.result.current.undo()); expect(hook.result.current.draft).toEqual(before);
    act(() => hook.result.current.redo()); expect(hook.result.current.draft).toEqual(expected);
    await act(async () => hook.result.current.save()); expect(state.client.timelineSave).toHaveBeenCalledTimes(1);
    expect(state.client.timelineSave).toHaveBeenCalledWith('linked-trim', { ...expected, expected_version: 1 });
    await act(async () => hook.result.current.checkServer()); act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
    expect(hook.result.current.draft).toEqual(expected); expect(hook.result.current.base?.version).toBe(2); expect(state.client.timelineEdit).not.toHaveBeenCalled();
  });
  it('preserves old single-clip and numeric guards even when one shorter member would be unchanged', async () => {
    const input = row(); input.timeline.tracks[1].clips[0].out_ms = 650;
    const state = setup(input); await adopt(state); const hook = state.hook!, before = cloneTimeline(hook.result.current.draft!);
    act(() => expect(hook.result.current.trimClip('visual', 'picture', 100, 700, false)).toBe(false));
    act(() => expect(hook.result.current.change(draft => { clips(draft).get('picture')!.out_ms = 700; })).toBe(false));
    expect(hook.result.current.draft).toEqual(before);
    act(() => expect(hook.result.current.trimLinkedClips(['picture'], 0, 600)).toBe(true));
  });
  it.each(['authority', 'busy', 'isBusy', 'permission', 'client', 'project', 'unmount'] as const)('rejects retired %s ABA callbacks', async fault => {
    const state = setup(); await adopt(state); const hook = state.hook!, old = hook.result.current.trimLinkedClips;
    if (fault === 'unmount') hook.unmount();
    else {
      hook.rerender({ ...state.props, ...(fault === 'authority' ? { isCurrent: () => false } : fault === 'busy' ? { busy: true }
        : fault === 'isBusy' ? { isBusy: () => true } : fault === 'permission' ? { canMutate: false } : fault === 'project' ? { projectId: 'other' }
        : { client: { ...state.client } as unknown as StudioProductionClient }) });
      hook.rerender(state.props);
    }
    act(() => expect(old(['picture'], 100, 650)).toBe(false)); expect(state.client.timelineSave).not.toHaveBeenCalled();
  });
  it('refuses dirty input and source version change without touching history or draft', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!;
    act(() => hook.result.current.change(draft => { draft.title = 'Unsaved'; })); const dirty = cloneTimeline(hook.result.current.draft!);
    act(() => expect(hook.result.current.trimLinkedClips(['sound'], 100, 650)).toBe(false)); expect(hook.result.current.draft).toEqual(dirty);
    act(() => hook.result.current.undo()); const clean = cloneTimeline(hook.result.current.draft!);
    hook.rerender({ ...state.props, assets: assets().map(asset => asset.kind === 'audio' ? { ...asset, version: 2 } : asset) });
    act(() => expect(hook.result.current.trimLinkedClips(['sound'], 100, 650)).toBe(false)); expect(hook.result.current.draft).toEqual(clean); expect(hook.result.current.canUndo).toBe(false);
  });
  it('preserves UNKNOWN request identity and original manual recovery without a replacement render', async () => {
    const state = setup(); await adopt(state); const hook = state.hook!;
    state.client.timelineRender.mockRejectedValueOnce(new TypeError('Synthetic lost response; no real render'));
    act(() => hook.result.current.setConfirmed(true)); await act(async () => hook.result.current.render());
    expect(hook.result.current.attempt?.state).toBe('UNKNOWN'); const original = cloneTimeline(hook.result.current.attempt!), before = cloneTimeline(hook.result.current.draft!);
    act(() => { expect(hook.result.current.trimLinkedClips(['picture'], 100, 650)).toBe(false); hook.result.current.undo(); hook.result.current.redo(); });
    expect(hook.result.current.draft).toEqual(before); await act(async () => hook.result.current.checkRenderJob());
    expect(hook.result.current.attempt).toEqual(original); expect(state.client.list).toHaveBeenCalledTimes(1); expect(state.client.timelineRender).toHaveBeenCalledTimes(1); expect(state.client.timelineSave).not.toHaveBeenCalled();
  });
  it('rejects stale form input ABA, then accepts a fresh explicit two-member preview', () => {
    const onTrim = vi.fn(); render(<LinkedClipTrimPanel timeline={row().timeline} selectedClipIds={['picture']} ready onTrim={onTrim} />); fill();
    const old = routed.click!; fireEvent.change(screen.getByLabelText('共同保留入点（相对毫秒）'), { target: { value: '101' } });
    fireEvent.change(screen.getByLabelText('共同保留入点（相对毫秒）'), { target: { value: '100' } }); act(() => old()); expect(onTrim).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '按已预览区间联动裁剪链接' })); expect(onTrim).toHaveBeenCalledWith(100, 650);
  });
  it('rejects retained selection ABA, previews both sources, saves once through the original editor', async () => {
    const state = setup(row(), true); await openPanel(); fill(); const retired = routed.trim!;
    const tracks = screen.getByLabelText('轨道头'); fireEvent.click(within(tracks).getByRole('button', { name: 'picture-other' }));
    fireEvent.click(within(tracks).getByRole('button', { name: 'picture' })); act(() => retired(100, 650));
    expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true); fill();
    const panel = screen.getByRole('region', { name: '已保存链接联动裁剪' });
    expect(within(panel).getByText(/picture：来源 \[100, 900\) → \[200, 750\)/)).toBeTruthy();
    expect(within(panel).getByText(/sound：来源 \[50, 850\) → \[150, 700\)/)).toBeTruthy();
    fireEvent.click(within(panel).getByRole('button', { name: '按已预览区间联动裁剪链接' }));
    fireEvent.click(screen.getByRole('button', { name: '保存时间线' })); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
    const body = state.client.timelineSave.mock.calls[0][1]; expect(body.timeline).toEqual(trimLinkedTimeline(row().timeline, ['picture'], 100, 650)); expect(body.expected_version).toBe(1);
  });
});
