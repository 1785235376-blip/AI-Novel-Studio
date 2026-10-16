// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { StudioTimelineAssetHandoff, appendTimelineAsset, timelineAssetPlacement, type TimelineAssetHandoff } from './StudioTimelineAssetHandoff';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';
import { newTimelineDraft, type StudioTimelineDraft, type StudioTimelineRow } from './studioTimelineTypes';
const sha = 'a'.repeat(64);
const asset = (): StudioAsset => ({ id: 'asset-one', novel_id: 'project', branch_id: null, filename: 'source.mp4', kind: 'video', version: 2, sha256: sha, size: 20, media_type: 'video/mp4', created_at: '', updated_at: '', deleted_at: null });
function draft(): StudioTimelineDraft { const row = newTimelineDraft(); row.timeline.tracks = [{ id: 'track', kind: 'VIDEO', order: 0, gain_db: 0, muted: false, clips: [] }]; return row; }
const request = (readAsset = vi.fn().mockResolvedValue(asset())): TimelineAssetHandoff => ({ id: 'handoff', reference: { asset_id: 'asset-one', version: 2, digest: sha }, readAsset });
const range = { in_ms: 0, out_ms: 1000 };
const manualRange = () => fireEvent.change(screen.getByLabelText('交接来源终点（毫秒）'), { target: { value: '1000' } });
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
beforeEach(() => vi.stubGlobal('crypto', webcrypto));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function panel(patch: Partial<Parameters<typeof StudioTimelineAssetHandoff>[0]> = {}) {
  const props = { request: request(), draft: draft(), canEdit: true, isCurrent: () => true, getRevision: () => '0', onApply: vi.fn().mockReturnValue(true), ...patch };
  return { props, ...render(<StudioTimelineAssetHandoff {...props} />) };
}
async function preview() { click('核对交接素材版本'); await screen.findByLabelText('交接目标轨道'); fireEvent.change(screen.getByLabelText('交接目标轨道'), { target: { value: 'track' } }); manualRange(); }
describe('exact original asset reference handoff', () => {
  it('reads only on request, rereads at explicit acceptance, and consumes one intent once', async () => {
    const state = panel(); expect(state.props.request.readAsset).not.toHaveBeenCalled(); await preview(); expect(state.props.onApply).not.toHaveBeenCalled();
    click('明确加入原时间线草稿'); click('明确加入原时间线草稿'); await screen.findByText(/已把核对的原素材版本加入/);
    expect(state.props.request.readAsset).toHaveBeenCalledTimes(2); expect(state.props.onApply).toHaveBeenCalledTimes(1); expect(state.props.onApply).toHaveBeenCalledWith('track', asset(), range);
  });
  it.each([{ version: 3 }, { sha256: 'b'.repeat(64) }, { id: 'other' }, { deleted_at: 'today' }])('refuses changed metadata %j', async patch => {
    const read = vi.fn().mockResolvedValueOnce(asset()).mockResolvedValue({ ...asset(), ...patch }); const state = panel({ request: request(read) });
    await preview(); click('明确加入原时间线草稿'); await screen.findByText(/来源已变化或不可用/); expect(state.props.onApply).not.toHaveBeenCalled();
  });
  it('preserves draft on offline read and allows an explicit read retry', async () => {
    const read = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(asset()); const state = panel({ request: request(read) });
    click('核对交接素材版本'); await screen.findByText('offline'); await preview(); expect(state.props.onApply).not.toHaveBeenCalled();
  });
  it.each(['cancel', 'unmount', 'identity', 'draft', 'busy', 'track'] as const)('drops an in-flight add after %s', async action => {
    const delayed = deferred<StudioAsset>(), read = vi.fn().mockResolvedValueOnce(asset()).mockReturnValue(delayed.promise);
    const state = panel({ request: request(read) }); await preview(); click('明确加入原时间线草稿');
    if (action === 'cancel') click('取消素材交接');
    if (action === 'unmount') state.unmount();
    if (action === 'identity') state.rerender(<StudioTimelineAssetHandoff {...state.props} isCurrent={() => false} />);
    if (action === 'busy') state.rerender(<StudioTimelineAssetHandoff {...state.props} canEdit={false} />);
    if (action === 'draft') state.rerender(<StudioTimelineAssetHandoff {...state.props} draft={{ ...state.props.draft, title: 'changed' }} />);
    if (action === 'track') { const changed = structuredClone(state.props.draft); changed.timeline.tracks[0].locked = true; state.rerender(<StudioTimelineAssetHandoff {...state.props} draft={changed} />); }
    await act(async () => delayed.resolve(asset())); expect(state.props.onApply).not.toHaveBeenCalled();
  });
  it('rejects a target or busy ABA generation even when draft JSON is identical', async () => {
    const delayed = deferred<StudioAsset>(), read = vi.fn().mockResolvedValueOnce(asset()).mockReturnValue(delayed.promise);
    let revision = '0'; const state = panel({ request: request(read), getRevision: () => revision });
    await preview(); click('明确加入原时间线草稿'); revision = '2'; await act(async () => delayed.resolve(asset()));
    expect(state.props.onApply).not.toHaveBeenCalled(); expect(screen.getByText(/草稿、轨道或编辑状态已变化/)).toBeTruthy();
  });
  it('appends compatible v2 image/audio while preserving all prior authored fields', () => {
    const value = draft(); value.timeline.schema_version = 2; value.timeline.width = 640; value.timeline.height = 360;
    value.timeline.captions = [{ start_ms: 0, end_ms: 1000, text: 'Keep caption' }];
    appendTimelineAsset(value, 'track', asset(), range); value.timeline.tracks[0].clips[0].gain_db = -3;
    const previous = structuredClone(value), image = { ...asset(), kind: 'image' };
    appendTimelineAsset(value, 'track', image);
    expect(value.timeline.tracks[0].clips[0]).toEqual(previous.timeline.tracks[0].clips[0]);
    expect(value.timeline.captions).toEqual(previous.timeline.captions); expect(value.timeline.width).toBe(640);
    value.timeline.tracks.push({ id: 'audio', kind: 'AUDIO', order: 1, muted: false, gain_db: -6, clips: [] });
    appendTimelineAsset(value, 'audio', { ...asset(), kind: 'audio' }, range); expect(value.timeline.tracks[1].clips[0].source_snapshot.asset_kind).toBe('audio');
    expect(value.timeline.tracks[1].gain_db).toBe(-6); expect(value.timeline.tracks[0].clips[1].source_snapshot.asset_kind).toBe('image');
  });
  it('refuses locked, incompatible, full, and exhausted tracks without changing the draft', () => {
    for (const mode of ['locked', 'audio', 'full', 'end', 'image']) {
      const value = draft(), media = asset();
      if (mode === 'locked') value.timeline.tracks[0].locked = true;
      if (mode === 'audio') value.timeline.tracks[0].kind = 'AUDIO';
      if (mode === 'image') media.kind = 'image';
      if (mode === 'full') { value.timeline.duration_ms = 60000; for (let i = 0; i < 30; i++) appendTimelineAsset(value, 'track', media, range); expect(value.timeline.tracks[0].clips).toHaveLength(30); }
      if (mode === 'end') { appendTimelineAsset(value, 'track', media, range); value.timeline.duration_ms = 1000; }
      const before = structuredClone(value); expect(timelineAssetPlacement(value, 'track', media)).toBeNull(); appendTimelineAsset(value, 'track', media, range); expect(value).toEqual(before);
    }
  });
});

function editor() {
  let saved: StudioTimelineRow | undefined;
  const client = { timelineList: vi.fn(async () => ({ items: saved ? [saved] : [] })), timelineGet: vi.fn(async () => saved),
    timelineSave: vi.fn(async (_id: string | undefined, input: StudioTimelineDraft) => saved = { id: 'timeline-one', version: 1, title: input.title, timeline: input.timeline, timeline_digest: 'b'.repeat(64), created_at: '', updated_at: '' }), timelineRender: vi.fn() };
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: [asset()], projectId: 'project', canMutate: true, busy: false,
    isCurrent: () => true, read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onJob: vi.fn(), onUnavailable: vi.fn(), assetHandoff: request() };
  return { props, client, view: render(<StudioTimelineEditor {...props} />) };
}
describe('mounted original timeline draft owner', () => {
  it('adds one exact pinned clip, supports one undo/redo, explicitly saves and reopens the original owner', async () => {
    const state = editor(); await waitFor(() => expect(state.client.timelineList).toHaveBeenCalled());
    click('添加视频轨道'); click('核对交接素材版本'); const select = await screen.findByLabelText('交接目标轨道');
    fireEvent.change(select, { target: { value: (select as HTMLSelectElement).options[1].value } }); manualRange(); click('明确加入原时间线草稿'); await screen.findByText(/已把核对的原素材版本加入/);
    expect(screen.getByText(/未保存 · 1 条轨道 · 1 个片段/)).toBeTruthy(); click('撤销本地编辑'); expect(screen.getByText(/未保存 · 1 条轨道 · 0 个片段/)).toBeTruthy(); click('重做本地编辑');
    click('保存时间线'); await screen.findByText(/时间线已保存。/); expect(state.client.timelineSave).toHaveBeenCalledTimes(1);
    expect(state.client.timelineSave.mock.calls[0][1].timeline.tracks[0].clips[0].source_snapshot).toMatchObject({ id: 'asset-one', version: 2, digest: sha }); expect(state.client.timelineRender).not.toHaveBeenCalled();
    state.view.unmount(); render(<StudioTimelineEditor {...state.props} assetHandoff={undefined} />); await screen.findByRole('option', { name: /v1/ });
    fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: 'timeline-one' } });
    await screen.findByLabelText('已核对服务端内容与本地输入，确认以下选择'); fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线');
    expect(screen.getByText(/已读取或保存 v1 · 1 条轨道 · 1 个片段/)).toBeTruthy(); expect(state.client.timelineSave).toHaveBeenCalledTimes(1);
  });
  it('invalidates an add when an original draft edit is undone during the metadata read', async () => {
    const state = editor(), delayed = deferred<StudioAsset>();
    const read = state.props.assetHandoff!.readAsset as ReturnType<typeof vi.fn>;
    read.mockResolvedValueOnce(asset()).mockReturnValueOnce(delayed.promise);
    await waitFor(() => expect(state.client.timelineList).toHaveBeenCalled()); click('添加视频轨道'); click('核对交接素材版本');
    const select = await screen.findByLabelText('交接目标轨道'); fireEvent.change(select, { target: { value: (select as HTMLSelectElement).options[1].value } }); manualRange();
    click('明确加入原时间线草稿'); fireEvent.change(screen.getByLabelText('名称'), { target: { value: 'intervening edit' } }); click('撤销本地编辑');
    await act(async () => delayed.resolve(asset())); expect(screen.getByText(/草稿、轨道或编辑状态已变化/)).toBeTruthy();
    expect(screen.getByText(/未保存 · 1 条轨道 · 0 个片段/)).toBeTruthy();
  });
  it.each(['busy', 'canMutate'] as const)('rejects an original %s ABA during acceptance', async key => {
    const state = editor(), delayed = deferred<StudioAsset>();
    const read = state.props.assetHandoff!.readAsset as ReturnType<typeof vi.fn>;
    read.mockResolvedValueOnce(asset()).mockReturnValueOnce(delayed.promise);
    await waitFor(() => expect(state.client.timelineList).toHaveBeenCalled()); click('添加视频轨道'); click('核对交接素材版本');
    const select = await screen.findByLabelText('交接目标轨道'); fireEvent.change(select, { target: { value: (select as HTMLSelectElement).options[1].value } }); manualRange();
    click('明确加入原时间线草稿');
    state.view.rerender(<StudioTimelineEditor {...state.props} {...{ [key]: !state.props[key] }} />);
    state.view.rerender(<StudioTimelineEditor {...state.props} />);
    await act(async () => delayed.resolve(asset())); expect(screen.getByText(/草稿、轨道或编辑状态已变化/)).toBeTruthy();
    expect(screen.getByText(/未保存 · 1 条轨道 · 0 个片段/)).toBeTruthy();
  });
  it('blocks handoff while original save is UNKNOWN', async () => {
    const state = editor(); await waitFor(() => expect(state.client.timelineList).toHaveBeenCalled()); click('添加视频轨道');
    // Ordinary original picker establishes a valid draft before a lost save reply.
    const picker = screen.getByLabelText('选择已有视频素材'); fireEvent.change(picker, { target: { value: 'asset-one' } }); fireEvent.change(screen.getByLabelText('所选素材来源终点（毫秒）'), { target: { value: '1000' } }); click('将所选素材加入轨道');
    state.client.timelineSave.mockRejectedValueOnce(new TypeError('network lost')); click('保存时间线'); await screen.findByText(/保存结果不确定/);
    expect((screen.getByRole('button', { name: '核对交接素材版本' }) as HTMLButtonElement).disabled).toBe(true); expect(state.props.assetHandoff!.readAsset).not.toHaveBeenCalled();
  });
});
