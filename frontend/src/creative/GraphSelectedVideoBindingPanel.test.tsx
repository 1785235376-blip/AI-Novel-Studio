// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GraphSelectedVideoBindingPanel } from './GraphSelectedVideoBindingPanel';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import type { StudioClient } from './studioClient';
import type { ProductionProvider } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';
import { imageGraphRecord } from './studioImageGraph.testFixtures';
import { videoBindingCatalog, videoBindingGraph, videoBindingProvider } from './graphSelectedVideoBinding.testFixtures';

afterEach(cleanup);
const deferred = <T,>() => { let resolve!: (value: T) => void, reject!: (value: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
async function setup(rows = [videoBindingProvider(), videoBindingProvider('local-two')]) {
  const providers = vi.fn<(signal?: AbortSignal) => Promise<ProductionProvider[]>>().mockResolvedValue(rows);
  const writes = { create: vi.fn(), save: vi.fn(), createRun: vi.fn(), preflight: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn(), reviewMedia: vi.fn(), previewModel: vi.fn(), dispatchModel: vi.fn() };
  const client = { graphs: { catalog: vi.fn().mockResolvedValue(videoBindingCatalog()), videoCatalog: vi.fn().mockImplementation(async () => videoBindingCatalog()),
    list: vi.fn().mockResolvedValue({ items: [] }), ...writes } } as unknown as StudioClient;
  const props: StudioGraphEditorProps = { identity: 'original-actor', active: true, denied: false, canMutate: true, canReview: true,
    client, providerSource: { providers }, busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work() };
  const hook = renderHook(value => useStudioGraphEditorController(value), { initialProps: props });
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  act(() => { hook.result.current.change(videoBindingGraph()); hook.result.current.setSelected(['video-1', 'video-3']); });
  const noWrites = () => Object.values(writes).forEach(fn => expect(fn).not.toHaveBeenCalled());
  return { ...hook, props, providers, writes, noWrites };
}
type API = Awaited<ReturnType<typeof setup>>;
async function preview(api: API, provider = videoBindingProvider()) {
  expect(api.result.current.selectedVideoBinding.canRead).toBe(true);
  await act(() => api.result.current.selectedVideoBinding.load());
  expect(api.result.current.selectedVideoBinding.rows).toContainEqual(provider);
  act(() => api.result.current.selectedVideoBinding.choose(mediaProviderKey(provider)));
  expect(api.result.current.selectedVideoBinding.choice).toBe(mediaProviderKey(provider));
  act(() => api.result.current.selectedVideoBinding.prepare());
  expect(api.result.current.selectedVideoBinding.error).toBe('');
  expect(api.result.current.selectedVideoBinding.preview?.changes).toHaveLength(2);
}

describe('selected-video authoring through original controller and history', () => {
  it('does nothing automatically; previews exact old/new tuples and applies once with one undo/redo', async () => {
    const api = await setup(); expect(api.providers).not.toHaveBeenCalled(); const before = structuredClone(api.result.current.draft), history = api.result.current.past.length;
    await preview(api); expect(api.result.current.draft).toEqual(before); expect(api.result.current.past).toHaveLength(history);
    expect(api.result.current.selectedVideoBinding.preview!.changes[0]).toEqual({ nodeId: 'video-1', before: { provider_id: 'old-video-1', model_id: 'model-video-1', allow_cloud: true }, after: { provider_id: 'local-one', model_id: 'model-local-one', allow_cloud: false } });
    const apply = api.result.current.selectedVideoBinding.apply;
    act(() => { expect(apply()).toBe(true); expect(apply()).toBe(false); });
    const after = structuredClone(api.result.current.draft); expect(api.result.current.past).toHaveLength(history + 1);
    expect(after.nodes[1]).toEqual(before.nodes[1]); expect(after.nodes[3]).toEqual(before.nodes[3]);
    act(() => api.result.current.travel(false)); expect(api.result.current.draft).toEqual(before);
    act(() => { expect(apply()).toBe(false); }); expect(api.result.current.draft).toEqual(before);
    act(() => api.result.current.travel(true)); expect(api.result.current.draft).toEqual(after); api.noWrites();
  });
  it('keeps an unselected empty-model branch and rejects a later no-change preview', async () => {
    const api = await setup(), source = structuredClone(api.result.current.draft);
    source.nodes[1].parameters.provider_id = ''; source.nodes[1].parameters.model_id = '';
    act(() => api.result.current.change(source)); await preview(api); act(() => api.result.current.selectedVideoBinding.apply());
    expect(api.result.current.draft.nodes[1].parameters.model_id).toBe('');
    const history = api.result.current.past.length;
    await act(() => api.result.current.selectedVideoBinding.load()); act(() => api.result.current.selectedVideoBinding.choose(mediaProviderKey(videoBindingProvider())));
    act(() => api.result.current.selectedVideoBinding.prepare()); expect(api.result.current.selectedVideoBinding.error).toContain('没有可应用');
    expect(api.result.current.past).toHaveLength(history); api.noWrites();
  });
  it('rejects selection A → B → A and retained load/choice/preview/apply callbacks', async () => {
    const api = await setup(); await preview(api); const stale = api.result.current.selectedVideoBinding, before = structuredClone(api.result.current.draft);
    act(() => { api.result.current.setSelected(['video-2']); api.result.current.setSelected(['video-1', 'video-3']); expect(stale.apply()).toBe(false); });
    act(() => { stale.choose(mediaProviderKey(videoBindingProvider('local-two'))); stale.prepare(); }); await act(() => stale.load());
    expect(api.providers).toHaveBeenCalledTimes(1); expect(api.result.current.selectedVideoBinding.preview).toBeUndefined(); expect(api.result.current.draft).toEqual(before); api.noWrites();
  });
  it('rejects draft A → B → A even when the original object returns within one React event', async () => {
    const api = await setup(); await preview(api); const stale = api.result.current.selectedVideoBinding.apply, original = api.result.current.draft;
    act(() => { api.result.current.change({ ...original, title: 'temporary B' }); api.result.current.change(original); expect(stale()).toBe(false); });
    expect(api.result.current.draft).toEqual(original); expect(api.result.current.selectedVideoBinding.preview).toBeUndefined(); api.noWrites();
  });
  it('retires a preview after the saved graph version goes 1 → 2 → 1', async () => {
    const api = await setup(), record = imageGraphRecord(); record.definition = videoBindingGraph();
    const get = vi.fn().mockResolvedValue(record); Object.assign(api.props.client.graphs, { get });
    await act(() => api.result.current.open(record.id)); act(() => api.result.current.setSelected(['video-1', 'video-3'])); await preview(api);
    const stale = api.result.current.selectedVideoBinding.apply;
    get.mockResolvedValueOnce({ ...record, version: record.version + 1 }); await act(() => api.result.current.open(record.id));
    get.mockResolvedValueOnce(record); await act(() => api.result.current.open(record.id));
    act(() => expect(stale()).toBe(false)); expect(api.result.current.selectedVideoBinding.preview).toBeUndefined();
    expect(api.result.current.draft).toEqual(record.definition); api.noWrites();
  });
  it('retires an old callback when the discovery method changes on the same source object', async () => {
    const api = await setup(); await preview(api); const stale = api.result.current.selectedVideoBinding.apply;
    api.props.providerSource!.providers = vi.fn().mockResolvedValue([]); api.rerender({ ...api.props });
    act(() => expect(stale()).toBe(false)); expect(api.result.current.selectedVideoBinding.rows).toEqual([]); api.noWrites();
  });
  it('rejects provider A → B → A and refreshes with changed route/capability data', async () => {
    const api = await setup(); await preview(api); const stale = api.result.current.selectedVideoBinding.apply;
    act(() => api.result.current.selectedVideoBinding.choose(mediaProviderKey(videoBindingProvider('local-two'))));
    act(() => api.result.current.selectedVideoBinding.choose(mediaProviderKey(videoBindingProvider())));
    act(() => expect(stale()).toBe(false)); expect(api.result.current.selectedVideoBinding.preview).toBeUndefined();
    act(() => api.result.current.selectedVideoBinding.prepare()); const prior = api.result.current.selectedVideoBinding.apply;
    api.providers.mockResolvedValueOnce([{ ...videoBindingProvider(), route_digest: 'b'.repeat(64), supported_parameters: [] }]);
    await act(() => api.result.current.selectedVideoBinding.load()); act(() => expect(prior()).toBe(false));
    act(() => api.result.current.selectedVideoBinding.choose(mediaProviderKey({ ...videoBindingProvider(), route_digest: 'b'.repeat(64) })));
    act(() => api.result.current.selectedVideoBinding.prepare()); expect(api.result.current.selectedVideoBinding.error).toMatch(/video-1.*parameters.seed/); api.noWrites();
  });
  it.each(['identity', 'client', 'providerSource', 'canMutate', 'busy', 'externalDirty', 'active', 'draftOwner'] as const)('retires preview after %s A → B → A', async key => {
    const api = await setup(); await preview(api); const stale = api.result.current.selectedVideoBinding.apply, history = api.result.current.past.length;
    const replacement = key === 'identity' ? 'other-actor' : key === 'client' ? { ...api.props.client } : key === 'providerSource' ? { providers: vi.fn().mockResolvedValue([]) }
      : key === 'draftOwner' ? { projectId: 'other', incarnation: 'file:other', actorId: 'other-actor', actorWorkspaceId: '', mode: 'local' as const, workspaceId: '', storylineId: '', branchId: '' }
      : !api.props[key];
    api.rerender({ ...api.props, [key]: replacement }); api.rerender(api.props);
    act(() => expect(stale()).toBe(false)); expect(api.result.current.selectedVideoBinding.preview).toBeUndefined();
    expect(api.result.current.past).toHaveLength(history); api.noWrites();
  });
  it('honors synchronous busy, pending image form and current revocation', async () => {
    const api = await setup(); let busy = false, current = true, pendingImage = false;
    api.rerender({ ...api.props, isBusy: () => busy, isCurrent: () => current, isDirectorImagePending: () => pendingImage }); await preview(api);
    const before = structuredClone(api.result.current.draft), apply = api.result.current.selectedVideoBinding.apply;
    busy = true; act(() => expect(apply()).toBe(false)); busy = false;
    pendingImage = true; act(() => expect(apply()).toBe(false)); pendingImage = false;
    current = false; act(() => expect(apply()).toBe(false));
    expect(api.result.current.draft).toEqual(before); api.noWrites();
  });
  it('retires previews when execution form is dirty or permission is denied', async () => {
    const api = await setup(); await preview(api); const stale = api.result.current.selectedVideoBinding.apply;
    act(() => api.result.current.setExecutionDirty(true)); act(() => api.result.current.setExecutionDirty(false));
    act(() => expect(stale()).toBe(false)); expect(api.result.current.selectedVideoBinding.preview).toBeUndefined();
    await preview(api); const prior = api.result.current.selectedVideoBinding.apply;
    api.rerender({ ...api.props, denied: true }); api.rerender(api.props); act(() => expect(prior()).toBe(false)); api.noWrites();
  });
  it('preserves the original dirty timeline form and refuses discovery or binding across it', async () => {
    const api = await setup(), graph = structuredClone(api.result.current.draft);
    graph.nodes[3] = { id: 'timeline', definition_id: 'timeline_export', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: {} };
    act(() => { api.result.current.change(graph); api.result.current.setSelected(['timeline']); });
    act(() => api.result.current.timelineEditor.changeForm('in_ms', '77'));
    expect(api.result.current.timelineEditor.formDirty).toBe(true);
    act(() => api.result.current.setSelected(['video-1', 'video-3']));
    const before = structuredClone(api.result.current.draft), form = structuredClone(api.result.current.timelineEditor.form);
    expect(api.result.current.selectedVideoBinding.canRead).toBe(false); await act(() => api.result.current.selectedVideoBinding.load());
    act(() => { api.result.current.selectedVideoBinding.choose(mediaProviderKey(videoBindingProvider())); api.result.current.selectedVideoBinding.prepare(); expect(api.result.current.selectedVideoBinding.apply()).toBe(false); });
    expect(api.providers).not.toHaveBeenCalled(); expect(api.result.current.draft).toEqual(before); expect(api.result.current.timelineEditor.form).toEqual(form); api.noWrites();
  });
  it.each(['identity', 'client', 'providerSource', 'canMutate', 'externalDirty'] as const)('ignores late discovery after %s A → B → A', async key => {
    const api = await setup(), late = deferred<ProductionProvider[]>(); api.providers.mockReturnValueOnce(late.promise);
    let work!: Promise<void>; act(() => { work = api.result.current.selectedVideoBinding.load(); });
    const replacement = key === 'identity' ? 'other-actor' : key === 'client' ? { ...api.props.client } : key === 'providerSource' ? { providers: vi.fn().mockResolvedValue([]) } : !api.props[key];
    api.rerender({ ...api.props, [key]: replacement }); api.rerender(api.props);
    await act(async () => { late.resolve([videoBindingProvider()]); await work; });
    expect(api.result.current.selectedVideoBinding.rows).toEqual([]); expect(api.result.current.selectedVideoBinding.loading).toBe(false); api.noWrites();
  });
  it('discards late results and stale finally/error while a newer request is loading', async () => {
    const api = await setup(), first = deferred<ProductionProvider[]>(), second = deferred<ProductionProvider[]>();
    api.providers.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    let one!: Promise<void>, two!: Promise<void>;
    act(() => { one = api.result.current.selectedVideoBinding.load(); });
    act(() => api.result.current.setSelected(['video-2'])); act(() => api.result.current.setSelected(['video-1', 'video-3']));
    act(() => { two = api.result.current.selectedVideoBinding.load(); });
    await act(async () => { first.reject(new Error('old error')); await one; });
    expect(api.result.current.selectedVideoBinding.loading).toBe(true); expect(api.result.current.selectedVideoBinding.error).toBe('');
    await act(async () => { second.resolve([videoBindingProvider()]); await two; });
    expect(api.result.current.selectedVideoBinding.rows).toEqual([videoBindingProvider()]); api.noWrites();
  });
  it('rejects late discovery after actor/client/catalog replacement and aborts on unmount', async () => {
    const api = await setup(), late = deferred<ProductionProvider[]>(); api.providers.mockReturnValueOnce(late.promise);
    let work!: Promise<void>; act(() => { work = api.result.current.selectedVideoBinding.load(); });
    await act(() => api.result.current.loadVideoCatalog());
    await act(async () => { late.resolve([videoBindingProvider()]); await work; }); expect(api.result.current.selectedVideoBinding.rows).toEqual([]);
    const final = deferred<ProductionProvider[]>(); api.providers.mockReturnValueOnce(final.promise);
    act(() => { work = api.result.current.selectedVideoBinding.load(); }); const signal = api.providers.mock.calls.at(-1)![0]!;
    api.unmount(); expect(signal.aborted).toBe(true); await act(async () => { final.resolve([videoBindingProvider()]); await work; }); api.noWrites();
  });
  it('hides duplicate/cloud/wrong-operation options, and never replaces or clears unsupported values', async () => {
    const provider = videoBindingProvider(), cloud = { ...videoBindingProvider('cloud'), local: false }, wrong = { ...videoBindingProvider('wrong'), operation_id: 'm7.video.i2v' as const };
    const api = await setup([provider, { ...provider }, cloud, wrong]); const before = structuredClone(api.result.current.draft);
    await act(() => api.result.current.selectedVideoBinding.load()); expect(api.result.current.selectedVideoBinding.rows).toEqual([]); expect(api.result.current.selectedVideoBinding.error).toContain('含糊');
    act(() => api.result.current.selectedVideoBinding.choose(mediaProviderKey(cloud))); act(() => api.result.current.selectedVideoBinding.prepare());
    expect(api.result.current.draft).toEqual(before); api.noWrites();
  });
});

describe('mounted selected-video binding controls', () => {
  it('requires explicit preview and confirmation and detects DOM option drift', async () => {
    const api = await setup();
    const panel = render(<GraphSelectedVideoBindingPanel binding={api.result.current.selectedVideoBinding} />);
    const refresh = () => panel.rerender(<GraphSelectedVideoBindingPanel binding={api.result.current.selectedVideoBinding} />);
    expect(screen.queryByLabelText('所选视频节点绑定预览')).toBeNull();
    await act(() => api.result.current.selectedVideoBinding.load()); refresh();
    fireEvent.change(screen.getByLabelText('批量绑定本地服务商与模型'), { target: { value: mediaProviderKey(videoBindingProvider()) } }); refresh();
    const before = structuredClone(api.result.current.draft); fireEvent.click(screen.getByRole('button', { name: '预览所选视频节点绑定' })); refresh();
    expect(screen.getByLabelText('所选视频节点绑定预览').textContent).toContain('old-video-1 → local-one'); expect(api.result.current.draft).toEqual(before);
    (screen.getByLabelText('批量绑定本地服务商与模型') as HTMLSelectElement).value = mediaProviderKey(videoBindingProvider('local-two'));
    fireEvent.click(screen.getByRole('button', { name: '确认应用所选视频节点本地绑定' })); refresh(); expect(api.result.current.draft).toEqual(before); expect(screen.queryByLabelText('所选视频节点绑定预览')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '预览所选视频节点绑定' })); refresh();
    fireEvent.click(screen.getByRole('button', { name: '确认应用所选视频节点本地绑定' })); refresh();
    expect(api.result.current.draft.nodes[0].parameters.allow_cloud).toBe(false); expect(screen.getByText(/CONFIGURED_NOT_VERIFIED/)).toBeTruthy(); api.noWrites();
  });
});
