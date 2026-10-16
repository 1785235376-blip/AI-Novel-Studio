// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { imageGraphCatalog } from './studioImageGraph.testFixtures';
import { mediaProviderKey } from './useStudioMediaExecution';
import type { ProductionProvider } from './studioProductionClient';
import type { StudioClient } from './studioClient';
import type { StudioGraphDefinition, StudioGraphNode } from './studioGraphTypes';
const row = (local = true, operation: ProductionProvider['operation_id'] = 'm5.image.t2i'): ProductionProvider => ({
  operation_id: operation, provider_id: local ? 'local-provider' : 'cloud-provider', model_id: 'model', local, route_digest: 'a'.repeat(64), capability: 'MEDIA', supported_parameters: [], readiness: 'CONFIGURED_NOT_VERIFIED' });
const node = (kind: StudioGraphNode['definition_id'] = 'image_generate', id = 'node'): StudioGraphNode => ({ id, definition_id: kind, definition_version: 1, enabled: true,
  position: { x: 0, y: 0 }, parameters: { operation_id: kind === 'video_generate' ? 'm7.video.t2v' : kind === 'image_upscale' ? 'm5.image.upscale' : 'm5.image.t2i', provider_id: '', model_id: '', allow_cloud: false, parameters: { seed: 7 }, license_note: 'keep' } });
const deferred = <T,>() => { let resolve!: (value: T) => void, reject!: (value: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
afterEach(cleanup);
async function setup(nodes = [node()], rows = [row(), row(false)]) {
  const providers = vi.fn<(signal?: AbortSignal) => Promise<ProductionProvider[]>>().mockResolvedValue(rows);
  const writes = { create: vi.fn(), save: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn(), createRun: vi.fn() };
  const client = { graphs: { catalog: vi.fn().mockResolvedValue(imageGraphCatalog()), list: vi.fn().mockResolvedValue({ items: [] }), ...writes } } as unknown as StudioClient;
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'project-one', client, providerSource: { providers }, canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work() };
  const hook = renderHook(value => useStudioGraphEditorController(value), { initialProps: props });
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  const graph: StudioGraphDefinition = { schema_version: nodes[0].definition_id === 'video_generate' ? 5 : 4, title: 'Picker fixture', nodes, edges: [], viewport: { x: 0, y: 0, zoom: 1 } };
  act(() => { hook.result.current.change(graph); hook.result.current.setSelected([nodes[0].id]); });
  return { ...hook, props, providers, noWrites: () => Object.values(writes).forEach(fn => expect(fn).not.toHaveBeenCalled()) };
}
describe('graph configuration picker: local authoring only', () => {
  it.each(['image_generate', 'video_generate'] as const)('keeps %s local-first and permits explicit cloud and return to local', async kind => {
    const operation = kind === 'video_generate' ? 'm7.video.t2v' : 'm5.image.t2i', cloud = row(false, operation), api = await setup([node(kind)], [cloud]);
    expect(api.providers).not.toHaveBeenCalled(); act(() => api.result.current.providerPicker.chooseRoute('local')); const before = structuredClone(api.result.current.draft);
    await act(() => api.result.current.providerPicker.load()); expect(api.result.current.providerPicker.route).toBe('local'); expect(api.result.current.providerPicker.rows).toEqual([]);
    act(() => api.result.current.providerPicker.chooseRoute('cloud')); expect(api.result.current.providerPicker.rows).toEqual([cloud]); expect(api.result.current.providerPicker.choice).toBe(''); expect(api.result.current.draft).toEqual(before);
    act(() => api.result.current.providerPicker.choose(mediaProviderKey(cloud))); expect(api.result.current.node!.parameters).toMatchObject({ provider_id: cloud.provider_id, model_id: cloud.model_id, allow_cloud: false, parameters: { seed: 7 }, license_note: 'keep' });
    const bound = structuredClone(api.result.current.draft); act(() => api.result.current.providerPicker.chooseRoute('local')); expect(api.result.current.providerPicker.route).toBe('local'); expect(api.result.current.draft).toEqual(bound); api.noWrites();
  });
  it('changes binding and consent atomically with one undo and does not persist a digest', async () => {
    const original = node(); Object.assign(original.parameters, { provider_id: 'saved', model_id: 'saved-model', allow_cloud: true });
    const api = await setup([original]); await act(() => api.result.current.providerPicker.load()); const before = structuredClone(api.result.current.draft), history = api.result.current.past.length;
    act(() => api.result.current.providerPicker.choose(mediaProviderKey(row()))); expect(api.result.current.past).toHaveLength(history + 1); expect(api.result.current.node!.parameters.allow_cloud).toBe(false); expect(api.result.current.node!.parameters).not.toHaveProperty('route_digest');
    act(() => api.result.current.travel(false)); expect(api.result.current.draft).toEqual(before); expect(api.result.current.providerPicker.choice).toBe('');
    act(() => api.result.current.travel(true)); expect(api.result.current.node!.parameters.provider_id).toBe('local-provider'); api.noWrites();
  });
  it('clears cloud consent atomically when operation changes, retaining IDs and parameters', async () => {
    const original = node(); Object.assign(original.parameters, { provider_id: 'saved', model_id: 'saved-model', allow_cloud: true }); const api = await setup([original]);
    act(() => api.result.current.updateMediaField('operation_id', 'm5.image.i2i')); expect(api.result.current.node!.parameters).toMatchObject({ operation_id: 'm5.image.i2i', provider_id: 'saved', model_id: 'saved-model', allow_cloud: false, parameters: { seed: 7 } }); api.noWrites();
  });
  it('retains unknown saved IDs across empty, failed, and refreshed catalogs', async () => {
    const original = node(); Object.assign(original.parameters, { provider_id: 'unknown', model_id: 'missing', allow_cloud: true }); const api = await setup([original], []), before = structuredClone(api.result.current.draft);
    await act(() => api.result.current.providerPicker.load()); expect(api.result.current.providerPicker.matched).toBe(false);
    api.providers.mockRejectedValueOnce(new Error('offline')); await act(() => api.result.current.providerPicker.load()); expect(api.result.current.providerPicker.error).toBeTruthy();
    api.providers.mockResolvedValueOnce([row()]); await act(() => api.result.current.providerPicker.load()); expect(api.result.current.providerPicker.choice).toBe(''); expect(api.result.current.draft).toEqual(before); api.noWrites();
  });
  it('rejects ambiguous tuples, changed-digest stale options, and wrong operations', async () => {
    const changed = { ...row(), route_digest: 'b'.repeat(64) }, wrong = row(true, 'm7.video.t2v'), api = await setup([node()], [row(), changed, wrong]);
    await act(() => api.result.current.providerPicker.load()); expect(api.result.current.providerPicker.rows).toEqual([]); expect(api.result.current.providerPicker.error).toContain('含糊');
    act(() => api.result.current.providerPicker.choose(mediaProviderKey(wrong))); expect(api.result.current.node!.parameters.provider_id).toBe('');
    api.providers.mockResolvedValueOnce([row()]); await act(() => api.result.current.providerPicker.load()); const stale = api.result.current.providerPicker.choose;
    act(() => api.result.current.providerPicker.choose(mediaProviderKey(row()))); api.providers.mockResolvedValueOnce([changed]); await act(() => api.result.current.providerPicker.load());
    const before = structuredClone(api.result.current.draft); act(() => stale(mediaProviderKey(row()))); expect(api.result.current.providerPicker.choice).toBe(''); expect(api.result.current.draft).toEqual(before); api.noWrites();
  });
  it('never offers a cloud upscale row', async () => {
    const local = row(true, 'm5.image.upscale'), cloud = row(false, 'm5.image.upscale'), api = await setup([node('image_upscale')], [local, cloud]);
    await act(() => api.result.current.providerPicker.load()); act(() => api.result.current.providerPicker.chooseRoute('cloud')); expect(api.result.current.providerPicker.route).toBe('local'); expect(api.result.current.providerPicker.rows).toEqual([local]);
    act(() => api.result.current.providerPicker.choose(mediaProviderKey(cloud))); expect(api.result.current.node!.parameters.provider_id).toBe(''); api.noWrites();
  });
  it.each(['node', 'operation'] as const)('discards a late response after %s A → B → A', async kind => {
    const api = await setup([node(), node('image_generate', 'other')]), late = deferred<ProductionProvider[]>(); api.providers.mockReturnValueOnce(late.promise);
    let work!: Promise<void>; act(() => { work = api.result.current.providerPicker.load(); });
    if (kind === 'node') { act(() => api.result.current.setSelected(['other'])); act(() => api.result.current.setSelected(['node'])); }
    else { act(() => api.result.current.updateMediaField('operation_id', 'm5.image.i2i')); act(() => api.result.current.updateMediaField('operation_id', 'm5.image.t2i')); }
    await act(async () => { late.resolve([row()]); await work; }); expect(api.result.current.providerPicker.loaded).toBe(false); expect(api.result.current.providerPicker.loading).toBe(false); api.noWrites();
  });
  it.each((['identity', 'client', 'providerSource'] as const).flatMap(key => [false, true].map(returnToOriginal => ({ key, returnToOriginal }))))('ignores old results after $key replacement (return: $returnToOriginal)', async ({ key, returnToOriginal }) => {
    const api = await setup(), late = deferred<ProductionProvider[]>(); api.providers.mockReturnValueOnce(late.promise); let work!: Promise<void>; act(() => { work = api.result.current.providerPicker.load(); });
    api.rerender({ ...api.props, [key]: key === 'identity' ? 'project-two' : key === 'client' ? { ...api.props.client } : { providers: vi.fn().mockResolvedValue([]) } });
    if (returnToOriginal) api.rerender(api.props);
    await act(async () => { late.resolve([row()]); await work; }); expect(api.result.current.providerPicker.loaded).toBe(false); expect(api.result.current.providerPicker.rows).toEqual([]); api.noWrites();
  });
  it('keeps newest read when old error/finally arrives during the newer request', async () => {
    const api = await setup(), first = deferred<ProductionProvider[]>(), second = deferred<ProductionProvider[]>(); api.providers.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    let one!: Promise<void>, two!: Promise<void>; act(() => { one = api.result.current.providerPicker.load(); });
    act(() => api.result.current.setSelected([])); act(() => api.result.current.setSelected(['node']));
    act(() => { two = api.result.current.providerPicker.load(); });
    await act(async () => { first.reject(new Error('stale error')); await one; }); expect(api.result.current.providerPicker.loading).toBe(true); expect(api.result.current.providerPicker.error).toBe('');
    await act(async () => { second.resolve([row()]); await two; }); expect(api.result.current.providerPicker.rows).toEqual([row()]); api.noWrites();
  });
  it('rejects stale node/route callbacks and obeys synchronous busy', async () => {
    const api = await setup([node(), node('image_generate', 'other')]); await act(() => api.result.current.providerPicker.load()); const stale = api.result.current.providerPicker.choose;
    act(() => api.result.current.providerPicker.chooseRoute('cloud')); act(() => stale(mediaProviderKey(row()))); expect(api.result.current.node!.parameters.provider_id).toBe('');
    act(() => api.result.current.providerPicker.chooseRoute('local')); act(() => stale(mediaProviderKey(row()))); expect(api.result.current.node!.parameters.provider_id).toBe('');
    act(() => api.result.current.providerPicker.chooseRoute('cloud'));
    const staleCloud = api.result.current.providerPicker.choose; act(() => api.result.current.setSelected(['other'])); act(() => staleCloud(mediaProviderKey(row(false)))); expect(api.result.current.node!.parameters.provider_id).toBe('');
    let busy = false; api.rerender({ ...api.props, isBusy: () => busy }); await act(() => api.result.current.providerPicker.load()); busy = true;
    act(() => api.result.current.providerPicker.choose(mediaProviderKey(row()))); expect(api.result.current.node!.parameters.provider_id).toBe(''); api.noWrites();
  });
  it('rejects identical duplicate rows and discards a late read after resetting the graph', async () => {
    const api = await setup([node()], [row(), row()]); await act(() => api.result.current.providerPicker.load());
    expect(api.result.current.providerPicker.rows).toEqual([]); expect(api.result.current.providerPicker.error).toContain('含糊');
    const late = deferred<ProductionProvider[]>(); api.providers.mockReturnValueOnce(late.promise); let work!: Promise<void>;
    act(() => { work = api.result.current.providerPicker.load(); }); act(() => api.result.current.discard());
    const before = structuredClone(api.result.current.draft); await act(async () => { late.resolve([row()]); await work; });
    expect(api.result.current.draft).toEqual(before); expect(api.result.current.providerPicker.loaded).toBe(false); api.noWrites();
  });
  it('blocks disabled route handler while reading and aborts on unmount', async () => {
    const api = await setup(), late = deferred<ProductionProvider[]>(); api.providers.mockReturnValueOnce(late.promise); let work!: Promise<void>;
    act(() => { work = api.result.current.providerPicker.load(); }); await act(() => api.result.current.providerPicker.load()); expect(api.providers).toHaveBeenCalledTimes(1); act(() => api.result.current.providerPicker.chooseRoute('cloud')); expect(api.result.current.providerPicker.route).toBe('local');
    const signal = api.providers.mock.calls[0][0]!; api.unmount(); expect(signal.aborted).toBe(true); await act(async () => { late.resolve([row()]); await work; }); api.noWrites();
  });
});
