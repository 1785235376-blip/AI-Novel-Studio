// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { mediaProviderKey, useStudioMediaExecution, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { cutoutAssets, cutoutJob, cutoutPreview } from './studioCpuCutout.testFixtures';
const asset = cutoutAssets()[0], other = { ...asset, id: 'kept-reference', filename: 'kept-reference.png' };
const provider: ProductionProvider = { operation_id: 'm5.image.reference', provider_id: 'reference-local', model_id: 'model', local: true,
  route_digest: asset.sha256, capability: 'IMAGE', readiness: 'CONFIGURED_NOT_VERIFIED', supported_parameters: ['seed'],
  image_capabilities: { recipe_id: 'comfy-flux1-v1', reference_limit: 5, reference_semantics: 'WEIGHTED_PIXEL_INITIALIZATION', mask_semantics: null, structural_only: true, inference_verified: false } };
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
function fixture(rows: ProductionProvider[] = [provider], readAsset = vi.fn().mockResolvedValue(asset)) {
  const client = { providers: vi.fn().mockResolvedValue(rows), preview: vi.fn(), create: vi.fn(), execute: vi.fn(), candidate: vi.fn(), list: vi.fn().mockResolvedValue([]) } as unknown as StudioProductionClient;
  const props: StudioMediaExecutionProps = { client, assets: [asset, other], canMutate: true, canReview: true, busy: false, isCurrent: () => true,
    read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn(),
    assetHandoff: { id: 'reference-intent', target: 'IMAGE', reference: { asset_id: asset.id, version: asset.version, digest: asset.sha256 }, readAsset } };
  return { props, client, readAsset };
}
async function setup(rows = [provider], readAsset = vi.fn().mockResolvedValue(asset), choose = true) {
  const api = fixture(rows, readAsset), state = renderHook(useStudioMediaExecution, { initialProps: api.props });
  await waitFor(() => expect(state.result.current.providerLoading).toBe(false));
  act(() => { state.result.current.changeOperation('m5.image.reference'); if (choose && rows[0]) state.result.current.changeField('providerKey', mediaProviderKey(rows[0])); });
  return { ...api, ...state };
}
const noExecution = (client: StudioProductionClient) => { expect(client.create).not.toHaveBeenCalled(); expect(client.execute).not.toHaveBeenCalled(); expect(client.candidate).not.toHaveBeenCalled(); };
afterEach(cleanup);
describe('explicit asset handoff into original weighted image references', () => {
  it.each([true, false])('appends a verified weight-one pin while preserving every existing input, local=%s', async local => {
    const chosen = { ...provider, local }, s = await setup([chosen]);
    act(() => { s.result.current.selectReference(other.id, true); s.result.current.changeReferenceWeight(other.id, '0.35');
      s.result.current.changeReferenceMetadata(other.id, 'purpose', 'character'); s.result.current.changeReferenceMetadata(other.id, 'source_note', 'Keep the outfit');
      s.result.current.changeField('prompt', 'Keep this prompt'); s.result.current.changeField('licenseNote', 'Owned source'); s.result.current.changeParameter('seed', '42'); s.result.current.changeField('allowCloud', true); });
    const before = structuredClone(s.result.current.draft);
    expect(s.readAsset).not.toHaveBeenCalled(); await act(() => s.result.current.readHandoff(true)); expect(s.readAsset).not.toHaveBeenCalled();
    await act(() => s.result.current.readHandoff(false)); expect(s.result.current.draft).toEqual(before); expect(s.result.current.handoffAsset?.id).toBe(asset.id);
    await act(() => s.result.current.readHandoff(true));
    const after = s.result.current.draft;
    expect(after).toEqual({ ...before, allowCloud: false, sources: [...before.sources, { id: asset.id, kind: 'ASSET', asset_kind: 'image', version: asset.version, digest: asset.sha256 }],
      imageReferences: [...before.imageReferences, { source: { id: asset.id, kind: 'ASSET', asset_kind: 'image', version: asset.version, digest: asset.sha256 }, weight: '1' }] });
    expect(after.imageSource).toBeUndefined(); expect(after.maskSource).toBeUndefined(); expect(s.readAsset).toHaveBeenCalledTimes(2);
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true)); expect(s.readAsset).toHaveBeenCalledTimes(2);
    expect(s.client.preview).not.toHaveBeenCalled(); noExecution(s.client);
  });
  it('clears the original execution preview and both consents, without creating or dispatching', async () => {
    const s = await setup([{ ...provider, local: false }]);
    act(() => { s.result.current.selectReference(other.id, true); s.result.current.changeField('prompt', 'keep'); s.result.current.changeField('allowCloud', true); });
    vi.mocked(s.client.preview).mockImplementation(async command => ({ ...cutoutPreview(command), provider: { ...provider, local: false }, operation_id: command.operation_id }));
    await act(() => s.result.current.inspect()); act(() => s.result.current.confirmPreview(true)); expect(s.result.current.canCreate).toBe(true);
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.preview).toBeUndefined(); expect(s.result.current.previewReviewed).toBe(false); expect(s.result.current.canCreate).toBe(false); expect(s.result.current.draft.allowCloud).toBe(false);
    expect(s.client.preview).toHaveBeenCalledTimes(1); noExecution(s.client);
  });
  it.each(['unselected', 'missing capability', 'wrong operation', 'wrong capability'] as const)('rejects %s without fallback to legacy sources', async mode => {
    const row = mode === 'missing capability' ? { ...provider, image_capabilities: undefined } : mode === 'wrong operation' ? { ...provider, operation_id: 'm5.image.i2i' as const } : mode === 'wrong capability' ? { ...provider, capability: 'VIDEO' as const } : provider;
    const s = await setup([row], undefined, mode !== 'unselected'); const before = structuredClone(s.result.current.draft);
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.draft).toEqual(before); expect(s.result.current.handoffAsset).toBeUndefined(); expect(s.result.current.handoffNotice).toMatch(/服务商配置/); noExecution(s.client);
  });
  it.each([1, 5, 9])('obeys provider limit %s and the hard five cap without truncation', async limit => {
    const row = { ...provider, image_capabilities: { ...provider.image_capabilities!, reference_limit: limit } }, s = await setup([row]);
    const extras = Array.from({ length: Math.min(limit, 5) }, (_, i) => ({ ...asset, id: `kept-${i}` })); s.rerender({ ...s.props, assets: [asset, ...extras] });
    act(() => extras.forEach(item => s.result.current.selectReference(item.id, true))); const before = structuredClone(s.result.current.draft);
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.handoffNotice).toMatch(/上限/); expect(s.result.current.draft).toEqual(before); noExecution(s.client);
  });
  it.each(['duplicate', 'unclassified source'] as const)('rejects %s and preserves existing bindings', async mode => {
    const s = await setup(); act(() => mode === 'duplicate' ? s.result.current.selectReference(asset.id, true) : s.result.current.selectSource(other.id, true));
    const before = structuredClone(s.result.current.draft); await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.draft).toEqual(before); expect(s.result.current.handoffAsset).toBeUndefined(); expect(s.result.current.handoffNotice).toMatch(/已绑定|无法安全追加/);
  });
  it.each([{ version: asset.version + 1 }, { sha256: 'b'.repeat(64) }, { id: 'other' }, { kind: 'video' }, { deleted_at: 'deleted' }, { manual_mask: {} }])('rejects changed metadata during acceptance: %j', async patch => {
    const s = await setup(undefined, vi.fn().mockResolvedValueOnce(asset).mockResolvedValue({ ...asset, ...patch }));
    await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
    expect(s.result.current.draft.imageReferences).toEqual([]); expect(s.result.current.handoffNotice).toMatch(/来源类型/); noExecution(s.client);
  });
  it.each(['missing', 'version', 'digest', 'mask'] as const)('requires matching list metadata before preview: %s', async mode => {
    const s = await setup(); const changed = mode === 'version' ? { ...asset, version: asset.version + 1 } : mode === 'digest' ? { ...asset, sha256: 'b'.repeat(64) } : { ...asset, manual_mask: {} };
    s.rerender({ ...s.props, assets: mode === 'missing' ? [] : [changed] as typeof s.props.assets });
    await act(() => s.result.current.readHandoff(false)); expect(s.result.current.handoffAsset).toBeUndefined(); expect(s.result.current.handoffNotice).toMatch(/素材列表/); expect(s.result.current.draft.imageReferences).toEqual([]);
  });
  for (const phase of [false, true]) it.each(['draft ABA', 'operation ABA', 'provider ABA', 'reload', 'busy ABA', 'permission ABA', 'source ABA', 'client ABA', 'request ABA', 'cancel', 'owner', 'UNKNOWN', 'unmount'] as const)(`fences delayed ${phase ? 'acceptance' : 'preview'} after %s`, async action => {
    const delay = deferred<typeof asset>(), read = phase ? vi.fn().mockResolvedValueOnce(asset).mockReturnValue(delay.promise) : vi.fn().mockReturnValue(delay.promise), s = await setup(undefined, read);
    if (phase) await act(() => s.result.current.readHandoff(false)); let pending!: Promise<void>; act(() => { pending = s.result.current.readHandoff(phase); });
    if (action === 'draft ABA') act(() => { s.result.current.changeField('prompt', 'other'); s.result.current.changeField('prompt', ''); });
    if (action === 'operation ABA') act(() => { s.result.current.changeOperation('m5.image.i2i'); s.result.current.changeOperation('m5.image.reference'); });
    if (action === 'provider ABA') act(() => { s.result.current.changeField('providerKey', ''); s.result.current.changeField('providerKey', mediaProviderKey(provider)); });
    if (action === 'reload') await act(() => s.result.current.loadProviders());
    if (action === 'busy ABA') { s.rerender({ ...s.props, busy: true }); s.rerender(s.props); }
    if (action === 'permission ABA') { s.rerender({ ...s.props, canMutate: false }); s.rerender(s.props); }
    if (action === 'source ABA') { s.rerender({ ...s.props, assets: [{ ...asset, version: asset.version + 1 }] }); s.rerender(s.props); }
    if (action === 'client ABA') { s.rerender({ ...s.props, client: { ...s.client } }); s.rerender(s.props); }
    if (action === 'request ABA') { s.rerender({ ...s.props, assetHandoff: { ...s.props.assetHandoff!, id: 'replacement' } }); s.rerender(s.props); }
    if (action === 'cancel') act(() => s.result.current.cancelHandoff());
    if (action === 'owner') s.rerender({ ...s.props, isCurrent: () => false });
    if (action === 'UNKNOWN') s.rerender({ ...s.props, externalJob: cutoutJob('UNKNOWN') });
    if (action === 'unmount') s.unmount();
    const dirtyCalls = vi.mocked(s.props.onDirtyChange).mock.calls.length;
    await act(async () => { delay.resolve(asset); await pending; }); expect(s.result.current.draft.imageReferences).toEqual([]);
    if (action === 'unmount') {
      expect(s.props.onDirtyChange).toHaveBeenCalledTimes(dirtyCalls);
      const reads = s.readAsset.mock.calls.length;
      await act(() => s.result.current.readHandoff(false)); await act(() => s.result.current.readHandoff(true));
      expect(s.readAsset).toHaveBeenCalledTimes(reads); expect(s.client.preview).not.toHaveBeenCalled();
    }
    else expect(s.result.current.handoffAsset).toBeUndefined();
    noExecution(s.client);
  });
  it('requires a new preview after an edit and rejects a same-tick reload through a retained callback', async () => {
    const s = await setup(); await act(() => s.result.current.readHandoff(false)); const retained = s.result.current.readHandoff;
    await act(async () => { await s.result.current.loadProviders(); await retained(true); }); expect(s.readAsset).toHaveBeenCalledTimes(1);
    await act(() => s.result.current.readHandoff(false)); const second = s.result.current.readHandoff;
    act(() => s.result.current.changeParameter('seed', '42')); await act(() => second(true)); expect(s.readAsset).toHaveBeenCalledTimes(2); expect(s.result.current.draft.imageReferences).toEqual([]);
  });
  it('requires explicit operation/provider and two separate UI actions', async () => {
    const api = fixture(); render(<StudioMediaExecutionPanel {...api.props} />); await waitFor(() => expect((screen.getByRole('button', { name: '重新读取配置' }) as HTMLButtonElement).disabled).toBe(false));
    expect((screen.getByRole('button', { name: '核对图片交接版本' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('操作'), { target: { value: 'm5.image.reference' } }); expect(screen.getByText(/新参考权重为 1/)).toBeTruthy();
    expect((screen.getByLabelText('服务商与模型') as HTMLSelectElement).value).toBe(''); expect(api.readAsset).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('服务商与模型'), { target: { value: mediaProviderKey(provider) } }); fireEvent.click(screen.getByRole('button', { name: '核对图片交接版本' }));
    await screen.findByRole('button', { name: '明确加入图片制作草稿' }); expect((screen.getByLabelText(`参考 ${asset.filename} · v${asset.version}`) as HTMLInputElement).checked).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '明确加入图片制作草稿' })); await waitFor(() => expect((screen.getByLabelText(`参考 ${asset.filename} · v${asset.version}`) as HTMLInputElement).checked).toBe(true));
    expect(api.readAsset).toHaveBeenCalledTimes(2); expect(api.client.preview).not.toHaveBeenCalled(); noExecution(api.client);
  });
});
