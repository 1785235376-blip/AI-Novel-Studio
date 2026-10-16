// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { ApiError } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { studioProductionClient, type StudioProductionClient } from './studioProductionClient';
import type { StudioAsset } from './studioClient';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimelineRow, cloneTimeline, type StudioTimelineRow } from './studioTimelineTypes';
import { applyTimelineSourceEdits, checkedTimelineSourceEffect, prepareTimelineSourceEdit, timelineSourceRequestDigest, type TimelineSourceEditRequest, type TimelineSourceIntent } from './studioTimelineSourceEditContract';
import capture from './fixtures/phase6.capture.editing-pipeline.json';
const copy = <T,>(value: T): T => structuredClone(value);
const source = () => checkedTimelineRow(copy(capture.created));
const assets = () => [copy(capture.video_source), copy(capture.audio_formal), copy(capture.replacement_asset)] as unknown as StudioAsset[];
const insertBody = () => copy(capture.insert_body) as TimelineSourceEditRequest;
const replaceBody = () => copy(capture.replacement_body) as TimelineSourceEditRequest;
const intent = (): TimelineSourceIntent => ({ mode: 'NEW_TRACK', asset_id: capture.audio_formal.id, track_id: '', clip_id: '', start_ms: 0, in_ms: 0, out_ms: 800, include_audio: false });
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
// Controlled controller responses test UI decisions. The separate raw captures
// below are actual native File API evidence and remain byte-for-byte unchanged.
async function controlledEffect(input: StudioTimelineRow, body: TimelineSourceEditRequest): Promise<StudioTimelineRow> {
  const digest = 'c'.repeat(64); return { ...cloneTimeline(input), version: input.version + 1, timeline_digest: digest, timeline: applyTimelineSourceEdits(input, body.operations),
    edit_receipt: { request_id: body.request_id, request_digest: await timelineSourceRequestDigest(body), input_version: input.version, input_digest: input.timeline_digest, output_digest: digest } };
}
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); useLocalHostSession.setState({ token: 'synthetic-source-edit-unit', actorId: '' }); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('Phase 6 actual original edit batch and current effect receipts', () => {
  it('matches the original full request digest and native atomic new-track/first-clip effect', async () => {
    const row = checkedTimelineRow(capture.inserted); expect(await timelineSourceRequestDigest(insertBody())).toBe(capture.inserted.edit_receipt.request_digest);
    expect(await checkedTimelineSourceEffect(row, source(), insertBody())).toEqual(row);
    expect(insertBody().operations[0]).toMatchObject({ op: 'track.insert', track: { clips: [] } }); expect(row.timeline.tracks[1].clips[0].source_snapshot).toMatchObject({ id: capture.audio_formal.id, version: 2, asset_kind: 'audio' });
  });
  it('matches original replacement request/effect and the same read-only current recovery', async () => {
    const base = checkedTimelineRow(capture.inserted); expect(await timelineSourceRequestDigest(replaceBody())).toBe(capture.replaced.edit_receipt.request_digest);
    expect(await checkedTimelineSourceEffect(checkedTimelineRow(capture.replacement_recovered), base, replaceBody())).toEqual(checkedTimelineRow(capture.replaced));
    expect(capture.replaced.timeline.tracks[1]).toEqual(capture.inserted.timeline.tracks[1]);
  });
  it.each(['request_id', 'request_digest', 'input_digest', 'output_digest'] as const)('rejects changed original edit receipt %s', async key => {
    const value = copy(capture.insert_recovered); value.edit_receipt[key] = key === 'request_id' ? 'other-request' : '0'.repeat(64);
    await expect(Promise.resolve().then(() => checkedTimelineSourceEffect(checkedTimelineRow(value), source(), insertBody()))).rejects.toBeTruthy();
  });
  it('rejects identical clip effects from a different original request and preserves title', async () => {
    const row = checkedTimelineRow(capture.insert_recovered); await expect(checkedTimelineSourceEffect(row, source(), { ...insertBody(), request_id: 'other-operation' })).rejects.toBeTruthy();
    await expect(checkedTimelineSourceEffect({ ...row, title: '作者标题已变化' }, source(), insertBody())).rejects.toBeTruthy();
  });
  it('uses the original edit POST and current GET with no second mutation', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => copy(capture.inserted) }); vi.stubGlobal('fetch', fetcher);
    const client = studioProductionClient(capture.created.novel_id, { sessionToken: '' }); expect(await client.timelineEdit!(source(), insertBody())).toEqual(checkedTimelineRow(capture.inserted));
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(insertBody()); expect(fetcher.mock.calls[0][0]).toMatch(/\/timelines\/[^/]+\/edit$/);
    await client.timelineGet(source().id); expect(fetcher.mock.calls[1][1].method).toBe('GET'); expect(fetcher.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1);
  });
  it.each([1e-7, 1e-5, -1e-7])('rejects unsupported original canonical numeric precision %s before POST', async gain => {
    const body = insertBody(); if (body.operations[0].op === 'track.insert') body.operations[0].track.gain_db = gain;
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); const client = studioProductionClient(capture.created.novel_id, { sessionToken: '' });
    await expect(client.timelineEdit!(source(), body)).rejects.toThrow('数字精度'); await expect(timelineSourceRequestDigest(body)).rejects.toThrow('数字精度'); expect(fetcher).not.toHaveBeenCalled();
  });
  it('preserves supported fractional gain and the original Python full-body digest without rounding', async () => {
    const body = insertBody(); if (body.operations[0].op === 'track.insert') body.operations[0].track.gain_db = -3.5;
    // Independent original Python json.dumps(sort_keys=True, ensure_ascii=False,
    // separators=(",",":")) reference over the captured request + explicit gain.
    expect(await timelineSourceRequestDigest(body)).toBe('6c0069dc2e84b032226fd511e0b8380d930f16969c45d634dfb4245cfad70755');
    expect(applyTimelineSourceEdits(source(), body.operations).tracks[1].gain_db).toBe(-3.5); expect(body.operations[0]).toMatchObject({ track: { gain_db: -3.5 } });
  });
});

function setup(options: { current?: () => boolean; legacy?: boolean; panel?: boolean } = {}) {
  const rows = assets(), client = { timelineList: vi.fn().mockResolvedValue({ items: [source()] }), timelineGet: vi.fn().mockResolvedValue(source()), timelineSave: vi.fn(), timelineRender: vi.fn(), list: vi.fn(),
    ...(options.legacy ? {} : { timelineEdit: vi.fn(controlledEffect) }) };
  const onDirtyChange = vi.fn(), onUnavailable = vi.fn(); const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: rows, canMutate: true, busy: false,
    isCurrent: options.current ?? (() => true), read: async work => work(), mutate: async work => work(), onDirtyChange, onUnavailable, onJob: vi.fn() };
  const hook = options.panel ? undefined : renderHook((next: StudioTimelineEditorProps) => useStudioTimelineEditor(next), { initialProps: props });
  const view = options.panel ? render(<StudioTimelineEditor {...props} />) : undefined; return { props, client, hook, view, onDirtyChange, onUnavailable };
}
async function adoptSource(state: ReturnType<typeof setup>) { await waitFor(() => expect(state.hook!.result.current.rows).toHaveLength(1)); await act(async () => state.hook!.result.current.checkServer(source().id));
  act(() => state.hook!.result.current.setAdoptConfirmed(true)); act(() => state.hook!.result.current.adoptCandidate(false)); expect(state.hook!.result.current.base?.version).toBe(1); }
async function prepare(state: ReturnType<typeof setup>) { await adoptSource(state); act(() => state.hook!.result.current.sourceEdit.change(intent())); act(() => state.hook!.result.current.sourceEdit.prepare());
  expect(state.hook!.result.current.sourceEdit.prepared?.operations).toHaveLength(2); act(() => state.hook!.result.current.sourceEdit.confirm(true)); }

describe('Phase 6 original Timeline controller preserves source, locks and UNKNOWN', () => {
  it('prepares atomically without saving, then explicitly saves through original edit and clears local undo', async () => {
    const state = setup(); await prepare(state); expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.hook!.result.current.sourceEdit.canExecute).toBe(true);
    await act(async () => state.hook!.result.current.sourceEdit.execute()); expect(state.client.timelineEdit).toHaveBeenCalledOnce(); const body = state.client.timelineEdit!.mock.calls[0][1];
    expect(body.operations[0]).toMatchObject({ op: 'track.insert', track: { clips: [] } }); expect(body.operations[1].op).toBe('clip.insert');
    expect(state.hook!.result.current.base?.version).toBe(2); expect(state.hook!.result.current.base?.timeline.tracks[1].clips[0].source_snapshot.digest).toBe(capture.audio_formal.sha256);
    expect(state.hook!.result.current.canUndo).toBe(false); expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
  });
  it.each([503, 200])('blocks replay of a lost/invalid (%s) edit until exact current request/effect GET succeeds', async status => {
    const state = setup(); await prepare(state); state.client.timelineEdit!.mockRejectedValue(status === 503 ? new ApiError({ status: 503, code: 'SYNTHETIC_UNKNOWN', message: 'Synthetic lost reply' }) : new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: 'Synthetic invalid success' }));
    await act(async () => state.hook!.result.current.sourceEdit.execute()); const retained = state.hook!.result.current.sourceEdit.unknown!; expect(retained).toBeTruthy(); expect(state.hook!.result.current.canEdit).toBe(false);
    await act(async () => state.hook!.result.current.sourceEdit.execute()); await act(async () => state.hook!.result.current.checkServer()); expect(state.client.timelineEdit).toHaveBeenCalledOnce(); expect(state.client.timelineGet).toHaveBeenCalledOnce();
    state.client.timelineGet.mockResolvedValue(await controlledEffect(retained.source, retained.body)); await act(async () => state.hook!.result.current.sourceEdit.check());
    expect(state.hook!.result.current.sourceEdit.unknown).toBeUndefined(); expect(state.hook!.result.current.base?.version).toBe(2); expect(state.client.timelineEdit).toHaveBeenCalledOnce(); expect(state.hook!.result.current.canEdit).toBe(true);
  });
  it('keeps UNKNOWN for identical content without the original current receipt', async () => {
    const state = setup(); await prepare(state); state.client.timelineEdit!.mockRejectedValue(new Error('Controlled network interruption')); await act(async () => state.hook!.result.current.sourceEdit.execute());
    const retained = state.hook!.result.current.sourceEdit.unknown!, value = await controlledEffect(retained.source, retained.body); delete (value as Partial<typeof value>).edit_receipt;
    state.client.timelineGet.mockResolvedValue(value); await act(async () => state.hook!.result.current.sourceEdit.check()); expect(state.hook!.result.current.sourceEdit.unknown).toBeTruthy(); expect(state.hook!.result.current.base?.version).toBe(1);
    expect(state.hook!.result.current.sourceEdit.canExecute).toBe(false); expect(state.client.timelineEdit).toHaveBeenCalledOnce(); expect(state.onDirtyChange).toHaveBeenLastCalledWith(true);
  });
  it('invalidates confirmation when formal Asset version changes and sends nothing', async () => {
    const state = setup(); await prepare(state); const changed = assets(); changed[1].version++; state.hook!.rerender({ ...state.props, assets: changed });
    await waitFor(() => expect(state.hook!.result.current.sourceEdit.prepared).toBeUndefined()); await act(async () => state.hook!.result.current.sourceEdit.execute()); expect(state.client.timelineEdit).not.toHaveBeenCalled();
  });
  it('retains UNKNOWN when the formal Asset changes while the original edit reply is pending', async () => {
    const state = setup(), late = deferred<StudioTimelineRow>(); await prepare(state); state.client.timelineEdit!.mockReturnValueOnce(late.promise);
    let promise!: Promise<void>; act(() => { promise = state.hook!.result.current.sourceEdit.execute(); }); const retained = state.hook!.result.current.sourceEdit.unknown!;
    const changed = assets(); changed[1].version++; state.hook!.rerender({ ...state.props, assets: changed });
    await act(async () => { late.resolve(await controlledEffect(retained.source, retained.body)); await promise; });
    expect(state.hook!.result.current.base?.version).toBe(1); expect(state.hook!.result.current.sourceEdit.unknown).toBeTruthy(); expect(state.hook!.result.current.canEdit).toBe(false); expect(state.client.timelineEdit).toHaveBeenCalledOnce();
  });
  it('ignores a late edit reply after parent identity loss and chains no read', async () => {
    let current = true; const state = setup({ current: () => current }), late = deferred<StudioTimelineRow>(); await prepare(state); state.client.timelineEdit!.mockReturnValueOnce(late.promise);
    let promise!: Promise<void>; act(() => { promise = state.hook!.result.current.sourceEdit.execute(); }); const retained = state.hook!.result.current.sourceEdit.unknown!; current = false; state.hook!.rerender(state.props);
    await act(async () => { late.resolve(await controlledEffect(retained.source, retained.body)); await promise; }); expect(state.hook!.result.current.base).toBeUndefined(); expect(state.hook!.result.current.sourceEdit.unknown).toBeUndefined(); expect(state.client.timelineGet).toHaveBeenCalledOnce();
  });
  it('rejects locked target tracks, wrong kind and out-of-canvas ranges before any edit', () => {
    const input = source(); input.timeline.tracks[0].locked = true;
    expect(() => prepareTimelineSourceEdit(input, assets(), { ...intent(), mode: 'REPLACE', asset_id: capture.replacement_asset.id, track_id: 'picture', clip_id: 'picture-one' }, { track: 'new-track', clip: 'new-clip' })).toThrow();
    expect(() => prepareTimelineSourceEdit(source(), assets(), { ...intent(), mode: 'INSERT', track_id: 'picture' }, { track: 'new-track', clip: 'new-clip' })).toThrow();
    expect(() => prepareTimelineSourceEdit(source(), assets(), { ...intent(), start_ms: 900, out_ms: 800 }, { track: 'new-track', clip: 'new-clip' })).toThrow();
  });
  it('keeps old embedded clients functional and exposes explicit formal-source controls only when available', async () => {
    const legacy = setup({ panel: true, legacy: true }); await screen.findByRole('option', { name: /v1/ }); fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: source().id } });
    await screen.findByRole('region', { name: '核对服务端时间线' }); fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); fireEvent.click(screen.getByRole('button', { name: '采用服务端时间线' }));
    expect(screen.queryByRole('region', { name: '正式素材时间线操作' })).toBeNull(); expect(legacy.client.timelineSave).not.toHaveBeenCalled(); cleanup();
    setup({ panel: true }); await screen.findByRole('option', { name: /v1/ }); fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: source().id } }); await screen.findByRole('region', { name: '核对服务端时间线' });
    fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); fireEvent.click(screen.getByRole('button', { name: '采用服务端时间线' })); expect(screen.getByRole('region', { name: '正式素材时间线操作' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: '明确保存正式素材操作' })).toBeNull();
  });
});
