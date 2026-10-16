// @vitest-environment jsdom
import { act, cleanup, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import { imageGraphCatalog } from './studioImageGraph.testFixtures';
import type { StudioClient } from './studioClient';
import type { ProductionProvider } from './studioProductionClient';
import type { StudioGraphDefinition, StudioGraphNode } from './studioGraphTypes';

const node = (kind: StudioGraphNode['definition_id'] = 'image_generate', id = 'manual-a'): StudioGraphNode => ({ id, definition_id: kind, definition_version: 1, enabled: true,
  position: { x: 0, y: 0 }, parameters: { operation_id: kind === 'video_generate' ? 'm7.video.t2v' : kind === 'image_upscale' ? 'm5.image.upscale' : 'm5.image.t2i',
    provider_id: 'saved-provider', model_id: 'saved-model', allow_cloud: true, parameters: { seed: 7 }, license_note: 'retain this note' } });
const row: ProductionProvider = { operation_id: 'm5.image.t2i', provider_id: 'saved-provider', model_id: 'saved-model', local: false,
  route_digest: 'a'.repeat(64), capability: 'IMAGE', supported_parameters: [], readiness: 'CONFIGURED_NOT_VERIFIED' };
async function setup(kind: StudioGraphNode['definition_id'] = 'image_generate', withoutCatalog = false) {
  const providers = vi.fn<(signal?: AbortSignal) => Promise<ProductionProvider[]>>().mockResolvedValue([row]);
  const writes = { create: vi.fn(), save: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn(), createRun: vi.fn() };
  const client = { graphs: { catalog: vi.fn().mockResolvedValue(imageGraphCatalog()), list: vi.fn().mockResolvedValue({ items: [] }), ...writes } } as unknown as StudioClient;
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'manual-owner', client, providerSource: withoutCatalog ? undefined : { providers },
    canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work() };
  const hook = renderHook(value => useStudioGraphEditorController(value), { initialProps: props });
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  const graph: StudioGraphDefinition = { schema_version: kind === 'video_generate' ? 5 : 4, title: 'Manual compatibility', nodes: [node(kind), node(kind, 'manual-b')], edges: [], viewport: { x: 0, y: 0, zoom: 1 } };
  act(() => { hook.result.current.change(graph); hook.result.current.setSelected(['manual-a']); });
  return { ...hook, props, providers, noWrites: () => Object.values(writes).forEach(fn => expect(fn).not.toHaveBeenCalled()) };
}
afterEach(cleanup);
describe('advanced graph IDs preserve original authoring authority', () => {
  it.each([['image_generate', '图片'], ['image_upscale', '超分'], ['video_generate', '视频']] as const)('restores %s IDs without claiming a known route or dispatching', async (kind, label) => {
    const api = await setup(kind, true), before = structuredClone(api.result.current.draft), count = api.result.current.past.length;
    render(studioGraphEditorView(api.result.current, api.props).inspector);
    expect(screen.getByText('高级：手动填写已有配置标识')).toBeTruthy();
    expect((screen.getByLabelText(`${label}服务商 ID`) as HTMLInputElement).value).toBe('saved-provider');
    expect((screen.getByLabelText(`${label}模型 ID`) as HTMLInputElement).value).toBe('saved-model');
    expect(screen.getByText(/当前标识路线：未知/)).toBeTruthy();
    act(() => api.result.current.updateMediaField('provider_id', 'manually-authored-provider'));
    expect(api.result.current.node!.parameters).toMatchObject({ provider_id: 'manually-authored-provider', model_id: 'saved-model', allow_cloud: false, parameters: { seed: 7 }, license_note: 'retain this note' });
    expect(api.result.current.past).toHaveLength(count + 1); expect(api.result.current.providerPicker.bindingRoute).toBe('unknown');
    act(() => api.result.current.travel(false)); expect(api.result.current.draft).toEqual(before);
    expect(api.providers).not.toHaveBeenCalled(); api.noWrites();
  });
  it('derives a known route from the complete catalog rather than the local list filter', async () => {
    const api = await setup(); await act(() => api.result.current.providerPicker.load());
    expect(api.result.current.providerPicker.route).toBe('local'); expect(api.result.current.providerPicker.rows).toEqual([]);
    expect(api.result.current.providerPicker.bindingRoute).toBe('cloud');
    act(() => api.result.current.updateMediaField('model_id', 'unknown-model'));
    expect(api.result.current.providerPicker.bindingRoute).toBe('unknown'); expect(api.result.current.node!.parameters.allow_cloud).toBe(false); api.noWrites();
  });
  it.each(['selection', 'selection round trip', 'permission', 'external edit', 'owner', 'synchronous busy'] as const)('rejects a retained manual handler after %s changes', async mode => {
    const api = await setup(); let busy = false;
    api.rerender({ ...api.props, isBusy: () => busy }); const stale = api.result.current.updateMediaField;
    if (mode.startsWith('selection')) { act(() => api.result.current.setSelected(['manual-b'])); if (mode === 'selection round trip') act(() => api.result.current.setSelected(['manual-a'])); }
    else if (mode === 'permission') api.rerender({ ...api.props, canMutate: false });
    else if (mode === 'external edit') api.rerender({ ...api.props, externalDirty: true });
    else if (mode === 'owner') api.rerender({ ...api.props, identity: 'replacement-owner' });
    else busy = true;
    const before = structuredClone(api.result.current.draft);
    act(() => stale('provider_id', 'stale-must-not-bind')); expect(api.result.current.draft).toEqual(before); api.noWrites();
  });
  it('aborts a pending catalog read on a fresh manual edit and ignores its late result', async () => {
    const api = await setup(); let resolve!: (rows: ProductionProvider[]) => void;
    api.providers.mockImplementationOnce(() => new Promise(yes => { resolve = yes; }));
    let work!: Promise<void>; act(() => { work = api.result.current.providerPicker.load(); });
    const signal = api.providers.mock.calls[0][0]!;
    act(() => api.result.current.updateMediaField('model_id', 'manual-during-read'));
    expect(signal.aborted).toBe(true); const edited = structuredClone(api.result.current.draft);
    await act(async () => { resolve([row]); await work; });
    expect(api.result.current.draft).toEqual(edited); expect(api.result.current.providerPicker.loaded).toBe(false);
    expect(api.result.current.providerPicker.bindingRoute).toBe('unknown'); api.noWrites();
  });
});
