// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useStudioMediaExecution, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { cutoutAssets, cutoutJob } from './studioCpuCutout.testFixtures';
const asset = cutoutAssets()[0];
const deferred = () => { let resolve!: (value: typeof asset) => void; const promise = new Promise<typeof asset>(yes => { resolve = yes; }); return { promise, resolve }; };
async function setup(readAsset = vi.fn().mockResolvedValue(asset), providers: ProductionProvider[] = []) {
  const client = { providers: vi.fn().mockResolvedValue(providers), preview: vi.fn(), create: vi.fn(), execute: vi.fn() } as unknown as StudioProductionClient;
  const props: StudioMediaExecutionProps = { client, assets: [asset], canMutate: true, canReview: true, busy: false, isCurrent: () => true,
    read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn(),
    assetHandoff: { target: 'VIDEO', id: 'intent', reference: { asset_id: asset.id, version: asset.version, digest: asset.sha256 }, readAsset } };
  const state = renderHook(useStudioMediaExecution, { initialProps: props });
  await waitFor(() => expect(state.result.current.providerLoading).toBe(false));
  act(() => state.result.current.changeOperation('m7.video.i2v'));
  return { ...state, props, client, readAsset };
}
afterEach(cleanup);
describe('original media draft exact video handoff', () => {
  it('explicitly rereads and adds once while preserving inputs and making no execution calls', async () => {
    const s = await setup(); act(() => { s.result.current.changeField('prompt', 'keep'); s.result.current.changeParameter('seed', '42'); s.result.current.changeField('allowCloud', true); });
    expect(s.readAsset).not.toHaveBeenCalled(); await act(() => s.result.current.readHandoff(false)); expect(s.result.current.draft.sources).toEqual([]);
    await act(() => s.result.current.readHandoff(true)); expect(s.result.current.draft.sources).toEqual([{ id: asset.id, kind: 'ASSET', asset_kind: 'image', version: asset.version, digest: asset.sha256 }]);
    expect(s.result.current.draft.prompt).toBe('keep'); expect(s.result.current.draft.parameters.seed).toBe('42'); expect(s.result.current.draft.allowCloud).toBe(false);
    await act(() => s.result.current.readHandoff(true)); expect(s.readAsset).toHaveBeenCalledTimes(2);
    expect(s.client.preview).not.toHaveBeenCalled(); expect(s.client.create).not.toHaveBeenCalled(); expect(s.client.execute).not.toHaveBeenCalled();
  });
  it.each([{ version: asset.version + 1 }, { sha256: 'b'.repeat(64) }, { id: 'other' }, { kind: 'video' }, { deleted_at: 'deleted' }, { manual_mask: {} }, { version: NaN }, { sha256: 'invalid' }, { kind: 'audio' }])('rejects changed source %j', async patch => {
    const s = await setup(vi.fn().mockResolvedValueOnce(asset).mockResolvedValue({ ...asset, ...patch }));
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.draft.sources).toEqual([]); expect(s.result.current.handoffNotice).toMatch(/来源类型/);
  });
  it.each(['draft ABA', 'busy ABA', 'client ABA', 'request', 'cancel', 'permission ABA', 'source ABA', 'operation ABA', 'unmount'] as const)('fences delayed acceptance after %s', async action => {
    const delay = deferred(), s = await setup(vi.fn().mockResolvedValueOnce(asset).mockReturnValue(delay.promise));
    await act(() => s.result.current.readHandoff(false)); let pending!: Promise<void>; act(() => { pending = s.result.current.readHandoff(true); });
    if (action === 'operation ABA') act(() => { s.result.current.changeOperation('m7.video.v2v'); s.result.current.changeOperation('m7.video.i2v'); });
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
    act(() => { s.result.current.changeOperation('m7.video.i2v'); s.result.current.selectSource(asset.id, true); });
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true)); expect(s.result.current.handoffNotice).toMatch(/已绑定/); expect(s.result.current.draft.sources).toHaveLength(1);
  });
  it('rejects a missing current list entry and preserves an offline draft', async () => {
    const s = await setup(); s.rerender({ ...s.props, assets: [] }); await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.handoffNotice).toMatch(/素材列表/); expect(s.result.current.draft.sources).toEqual([]);
    s.rerender({ ...s.props, assetHandoff: { ...s.props.assetHandoff!, readAsset: async () => { throw new Error('offline'); } } });
    await act(() => s.result.current.readHandoff(false)); expect(s.result.current.handoffNotice).toBe('offline');
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

  it('adds an exact video to the original V2V draft with no configured executable provider', async () => {
    const s = await setup(), video = { ...asset, id: 'video', kind: 'video' as const };
    const readAsset = vi.fn().mockResolvedValue(video);
    s.rerender({ ...s.props, assets: [video], assetHandoff: { target: 'VIDEO', id: 'video', reference: { asset_id: video.id, version: video.version, digest: video.sha256 }, readAsset } });
    act(() => { s.result.current.changeOperation('m7.video.v2v'); s.result.current.changeField('videoReferencePurpose', 'camera'); });
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.draft.sources).toEqual([{ id: video.id, kind: 'ASSET', asset_kind: 'video', version: video.version, digest: video.sha256 }]);
    expect(s.result.current.draft.videoReferencePurpose).toBe('camera'); expect(s.result.current.canInspect).toBe(false);
    expect(readAsset).toHaveBeenCalledTimes(2); expect(s.client.preview).not.toHaveBeenCalled(); expect(s.client.create).not.toHaveBeenCalled();
  });
  it('never replaces a different source or changes the chosen provider', async () => {
    const s = await setup(), other = { ...asset, id: 'other' };
    s.rerender({ ...s.props, assets: [asset, other] });
    act(() => { s.result.current.selectSource(other.id, true); s.result.current.changeField('providerKey', 'keep-provider'); });
    const before = s.result.current.draft;
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.draft).toEqual(before); expect(s.result.current.handoffNotice).toMatch(/已有来源绑定/);
  });
  it('synchronously blocks metadata reads during configuration loading', async () => {
    const s = await setup(); let resolve!: (rows: ProductionProvider[]) => void;
    vi.mocked(s.client.providers).mockImplementation(() => new Promise(yes => { resolve = yes; }));
    let pending!: Promise<void>;
    await act(async () => { pending = s.result.current.loadProviders(); await s.result.current.readHandoff(false); });
    expect(s.readAsset).not.toHaveBeenCalled(); expect(s.result.current.canHandoff).toBe(false);
    await act(async () => { resolve([]); await pending; });
    await act(() => s.result.current.readHandoff(false)); expect(s.readAsset).toHaveBeenCalledTimes(1);
  });

});
