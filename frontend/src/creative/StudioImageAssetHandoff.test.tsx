// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mediaProviderKey, useStudioMediaExecution, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { cutoutAssets, cutoutJob, cutoutPreview } from './studioCpuCutout.testFixtures';
const asset = cutoutAssets()[0];
const deferred = () => { let resolve!: (value: typeof asset) => void; const promise = new Promise<typeof asset>(yes => { resolve = yes; }); return { promise, resolve }; };
async function setup(readAsset = vi.fn().mockResolvedValue(asset), providers: ProductionProvider[] = []) {
  const client = { providers: vi.fn().mockResolvedValue(providers), preview: vi.fn(), create: vi.fn(), execute: vi.fn() } as unknown as StudioProductionClient;
  const props: StudioMediaExecutionProps = { client, assets: [asset], canMutate: true, canReview: true, busy: false, isCurrent: () => true,
    read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn(),
    assetHandoff: { id: 'intent', reference: { asset_id: asset.id, version: asset.version, digest: asset.sha256 }, readAsset } };
  const state = renderHook(useStudioMediaExecution, { initialProps: props });
  await waitFor(() => expect(state.result.current.providerLoading).toBe(false));
  act(() => state.result.current.changeOperation('m5.image.i2i'));
  return { ...state, props, client, readAsset };
}
afterEach(cleanup);
describe('original media draft exact image handoff', () => {
  it('explicitly rereads and adds once while preserving inputs and making no execution calls', async () => {
    const s = await setup(); act(() => { s.result.current.changeField('prompt', 'keep'); s.result.current.changeParameter('seed', '42'); s.result.current.changeField('allowCloud', true); });
    expect(s.readAsset).not.toHaveBeenCalled(); await act(() => s.result.current.readHandoff(false)); expect(s.result.current.draft.sources).toEqual([]);
    await act(() => s.result.current.readHandoff(true)); expect(s.result.current.draft.sources).toEqual([{ id: asset.id, kind: 'ASSET', asset_kind: 'image', version: asset.version, digest: asset.sha256 }]);
    expect(s.result.current.draft.prompt).toBe('keep'); expect(s.result.current.draft.parameters.seed).toBe('42'); expect(s.result.current.draft.allowCloud).toBe(false);
    await act(() => s.result.current.readHandoff(true)); expect(s.readAsset).toHaveBeenCalledTimes(2);
    expect(s.client.preview).not.toHaveBeenCalled(); expect(s.client.create).not.toHaveBeenCalled(); expect(s.client.execute).not.toHaveBeenCalled();
  });
  it.each([{ version: asset.version + 1 }, { sha256: 'b'.repeat(64) }, { id: 'other' }, { kind: 'video' }, { deleted_at: 'deleted' }, { manual_mask: {} }])('rejects changed source %j', async patch => {
    const s = await setup(vi.fn().mockResolvedValueOnce(asset).mockResolvedValue({ ...asset, ...patch }));
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.draft.sources).toEqual([]); expect(s.result.current.handoffNotice).toMatch(/来源类型/);
  });
  it.each(['draft ABA', 'busy ABA', 'client ABA', 'request', 'cancel', 'permission ABA', 'source ABA', 'unmount'] as const)('fences delayed acceptance after %s', async action => {
    const delay = deferred(), s = await setup(vi.fn().mockResolvedValueOnce(asset).mockReturnValue(delay.promise));
    await act(() => s.result.current.readHandoff(false)); let pending!: Promise<void>; act(() => { pending = s.result.current.readHandoff(true); });
    if (action === 'draft ABA') act(() => { s.result.current.changeField('prompt', 'other'); s.result.current.changeField('prompt', ''); });
    if (action === 'busy ABA') { s.rerender({ ...s.props, busy: true }); s.rerender(s.props); }
    if (action === 'permission ABA') { s.rerender({ ...s.props, canMutate: false }); s.rerender(s.props); }
    if (action === 'source ABA') { s.rerender({ ...s.props, assets: [{ ...asset, version: asset.version + 1, deleted_at: 'deleted' }] }); s.rerender(s.props); }
    if (action === 'client ABA') { s.rerender({ ...s.props, client: { ...s.client } }); s.rerender(s.props); }
    if (action === 'request') s.rerender({ ...s.props, assetHandoff: { ...s.props.assetHandoff!, id: 'other' } });
    if (action === 'cancel') act(() => s.result.current.cancelHandoff());
    if (action === 'unmount') s.unmount();
    await act(async () => { delay.resolve(asset); await pending; }); expect(s.result.current.draft.sources).toEqual([]);
  });
  it('blocks unsupported operation and existing duplicate', async () => {
    const s = await setup(); act(() => s.result.current.changeOperation('m5.image.t2i')); await act(() => s.result.current.readHandoff(false)); expect(s.readAsset).not.toHaveBeenCalled();
    act(() => { s.result.current.changeOperation('m5.image.i2i'); s.result.current.selectSource(asset.id, true); });
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true)); expect(s.result.current.handoffNotice).toMatch(/已绑定/); expect(s.result.current.draft.sources).toHaveLength(1);
  });
  it('uses the existing modern image-source contract and never replaces a base image', async () => {
    const provider: ProductionProvider = { operation_id: 'm5.image.i2i', provider_id: 'local', model_id: 'model', local: true, route_digest: asset.sha256,
      capability: 'IMAGE', readiness: 'CONFIGURED_NOT_VERIFIED', supported_parameters: [], image_capabilities: { recipe_id: 'comfy-flux1-v1', reference_limit: 5,
        reference_semantics: 'WEIGHTED_PIXEL_INITIALIZATION', mask_semantics: null, structural_only: true, inference_verified: false } };
    const s = await setup(undefined, [provider]); act(() => s.result.current.changeField('providerKey', mediaProviderKey(provider)));
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.draft.imageSource?.id).toBe(asset.id); expect(s.result.current.draft.providerKey).toBe(mediaProviderKey(provider));
    const other = { ...asset, id: 'other' }; s.rerender({ ...s.props, assets: [asset, other], assetHandoff: { id: 'other', reference: { asset_id: other.id, version: other.version, digest: other.sha256 }, readAsset: async () => other } });
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.handoffNotice).toMatch(/已有基础图/); expect(s.result.current.draft.imageSource?.id).toBe(asset.id);
  });
  it('bounds legacy references at five without changing existing exact pins', async () => {
    const s = await setup(); const extras = Array.from({ length: 5 }, (_, n) => ({ ...asset, id: `other-${n}` }));
    s.rerender({ ...s.props, assets: [asset, ...extras] }); act(() => extras.forEach(row => s.result.current.selectSource(row.id, true)));
    const before = s.result.current.draft.sources; await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.draft.sources).toEqual(before); expect(s.result.current.handoffNotice).toMatch(/无法安全追加/);
  });
  it('rejects a missing current list entry and preserves an offline draft', async () => {
    const s = await setup(); s.rerender({ ...s.props, assets: [] }); await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.handoffNotice).toMatch(/素材列表/); expect(s.result.current.draft.sources).toEqual([]);
    s.rerender({ ...s.props, assetHandoff: { ...s.props.assetHandoff!, readAsset: async () => { throw new Error('offline'); } } });
    await act(() => s.result.current.readHandoff(false)); expect(s.result.current.handoffNotice).toBe('offline');
  });

  it('invalidates an existing execution preview and consent through the original edit owner', async () => {
    const provider: ProductionProvider = { operation_id: 'm5.image.i2i', provider_id: 'local', model_id: 'model', local: true, route_digest: asset.sha256,
      capability: 'IMAGE', readiness: 'CONFIGURED_NOT_VERIFIED', supported_parameters: [] };
    const s = await setup(undefined, [provider]), other = { ...asset, id: 'other' };
    s.rerender({ ...s.props, assets: [asset, other] });
    act(() => { s.result.current.changeField('providerKey', mediaProviderKey(provider)); s.result.current.changeField('prompt', 'keep'); s.result.current.selectSource('other', true); });
    vi.mocked(s.client.preview).mockImplementation(async command => ({ ...cutoutPreview(command), provider, operation_id: command.operation_id }));
    await act(() => s.result.current.inspect()); act(() => s.result.current.confirmPreview(true)); expect(s.result.current.canCreate).toBe(true);
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.preview).toBeUndefined(); expect(s.result.current.canCreate).toBe(false); expect(s.result.current.draft.sources).toHaveLength(2);
    expect(s.client.preview).toHaveBeenCalledTimes(1); expect(s.client.create).not.toHaveBeenCalled();
  });
  it('blocks an UNKNOWN original job and retained acceptance after a draft edit', async () => {
    const s = await setup(); await act(() => s.result.current.readHandoff(false)); const retained = s.result.current.readHandoff;
    act(() => s.result.current.changeField('prompt', 'changed')); await act(() => retained(true)); expect(s.readAsset).toHaveBeenCalledTimes(1);
    s.rerender({ ...s.props, externalJob: cutoutJob('UNKNOWN') }); await act(() => s.result.current.readHandoff(false));
    expect(s.readAsset).toHaveBeenCalledTimes(1); expect(s.result.current.draft.sources).toEqual([]);
  });

  it('fences same-tick configuration reload before accepting a retained preview', async () => {
    const s = await setup(); await act(() => s.result.current.readHandoff(false)); const retained = s.result.current.readHandoff;
    await act(async () => { await s.result.current.loadProviders(); await retained(true); });
    expect(s.readAsset).toHaveBeenCalledTimes(1); expect(s.result.current.draft.sources).toEqual([]);
  });

});
