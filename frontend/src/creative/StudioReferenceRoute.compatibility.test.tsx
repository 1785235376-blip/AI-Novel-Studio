// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { mediaProviderKey, useStudioMediaExecution, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { MediaCommand, ProductionPreview, ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { cutoutAssets } from './studioCpuCutout.testFixtures';
const digest = 'a'.repeat(64), asset = cutoutAssets()[0];
const provider = (local: boolean): ProductionProvider => ({ operation_id: 'm5.image.reference', provider_id: local ? 'local-reference' : 'cloud-reference',
  model_id: 'configured-model', local, route_digest: digest, capability: 'IMAGE', supported_parameters: ['seed'], readiness: 'CONFIGURED_NOT_VERIFIED',
  image_capabilities: { recipe_id: 'comfy-flux1-v1', reference_limit: 5, reference_semantics: 'WEIGHTED_PIXEL_INITIALIZATION', mask_semantics: null, structural_only: true, inference_verified: false } });
const local = provider(true), cloud = provider(false);
function fixture(rows = [cloud, local]) {
  const providers = vi.fn<(signal?: AbortSignal) => Promise<ProductionProvider[]>>().mockResolvedValue(rows), create = vi.fn(), execute = vi.fn();
  const preview = vi.fn(async (command: MediaCommand) => ({ operation_id: command.operation_id, command, provider: rows.find(row => row.provider_id === command.provider_id),
    preview_digest: digest, request_digest: digest, execution_recipe: {} } as unknown as ProductionPreview));
  const client = { providers, preview, create, execute, list: vi.fn().mockResolvedValue([]) } as unknown as StudioProductionClient;
  const props: StudioMediaExecutionProps = { client, assets: [asset], canMutate: true, canReview: true, busy: false, isCurrent: () => true,
    read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn() };
  return { props, providers, preview, create, execute, noDispatch: () => { expect(create).not.toHaveBeenCalled(); expect(execute).not.toHaveBeenCalled(); } };
}
const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const select = (label: string) => screen.getByLabelText(label) as HTMLSelectElement;
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
afterEach(cleanup);
describe('explicit cross-route reference compatibility', () => {
  it('shows local configurations first but never selects a cloud-only configuration automatically', async () => {
    const api = fixture([cloud]); render(<StudioMediaExecutionPanel {...api.props} />);
    await waitFor(() => expect(button('重新读取配置').disabled).toBe(false)); change('操作', 'm5.image.reference');
    expect(select('制作路线').value).toBe('local'); expect(select('服务商与模型').value).toBe('');
    expect(screen.getByRole('option', { name: 'cloud-reference · configured-model · 云端' })).toBeTruthy();
    expect(button('读取制作预览').disabled).toBe(true); expect(api.preview).not.toHaveBeenCalled(); api.noDispatch();
  });
  it('changes route only by explicit selection, clearing both consents and preserving reference inputs in both directions', async () => {
    const api = fixture(); render(<StudioMediaExecutionPanel {...api.props} />);
    await waitFor(() => expect(button('重新读取配置').disabled).toBe(false)); change('操作', 'm5.image.reference');
    expect(Array.from(select('服务商与模型').options).map(option => option.value)).toEqual(['', mediaProviderKey(local), mediaProviderKey(cloud)]);
    change('服务商与模型', mediaProviderKey(cloud)); expect(select('制作路线').value).toBe('cloud');
    change('本次提示词', 'Preserve reference prompt'); change('种子（0–2147483647）', '42');
    fireEvent.click(screen.getByLabelText(`参考 ${asset.filename} · v${asset.version}`)); change(`参考权重 · ${asset.filename} · v${asset.version}`, '0.5');
    expect(button('读取制作预览').disabled).toBe(true); expect(api.preview).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText(/确认本次允许将提示词及选中的参考素材/)); fireEvent.click(button('读取制作预览'));
    await screen.findByRole('region', { name: '制作预览确认' }); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
    expect(button('仅创建任务并入队').disabled).toBe(false);
    change('服务商与模型', mediaProviderKey(local)); expect(select('制作路线').value).toBe('local');
    expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
    change('服务商与模型', mediaProviderKey(cloud)); expect(select('制作路线').value).toBe('cloud');
    expect((screen.getByLabelText(/确认本次允许将提示词及选中的参考素材/) as HTMLInputElement).checked).toBe(false);
    expect(button('读取制作预览').disabled).toBe(true); expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('Preserve reference prompt');
    expect((screen.getByLabelText('种子（0–2147483647）') as HTMLInputElement).value).toBe('42');
    expect((screen.getByLabelText(`参考权重 · ${asset.filename} · v${asset.version}`) as HTMLInputElement).value).toBe('0.5');
    expect((screen.getByLabelText(`参考 ${asset.filename} · v${asset.version}`) as HTMLInputElement).checked).toBe(true);
    expect(api.preview).toHaveBeenCalledTimes(1); api.noDispatch();
  });
  it('rejects stale catalog keys during a read and after a digest replacement, without changing route or consent', async () => {
    const api = fixture(), hook = renderHook(useStudioMediaExecution, { initialProps: api.props });
    await waitFor(() => expect(hook.result.current.providerLoading).toBe(false)); act(() => hook.result.current.changeOperation('m5.image.reference'));
    act(() => hook.result.current.changeField('providerKey', mediaProviderKey(local)));
    let resolve!: (rows: ProductionProvider[]) => void; api.providers.mockImplementationOnce(() => new Promise(yes => { resolve = yes; }));
    let work!: Promise<void>; act(() => { work = hook.result.current.loadProviders(); }); const before = structuredClone(hook.result.current.draft);
    act(() => hook.result.current.changeField('providerKey', mediaProviderKey(cloud))); expect(hook.result.current.draft).toEqual(before);
    const changedCloud = { ...cloud, route_digest: 'b'.repeat(64) };
    await act(async () => { resolve([local, changedCloud]); await work; });
    act(() => hook.result.current.changeField('providerKey', mediaProviderKey(cloud))); expect(hook.result.current.draft).toEqual(before);
    act(() => hook.result.current.changeField('providerKey', mediaProviderKey(changedCloud)));
    expect(hook.result.current.draft).toMatchObject({ providerKey: mediaProviderKey(changedCloud), route: 'cloud', allowCloud: false });
    expect(api.preview).not.toHaveBeenCalled(); api.noDispatch();
  });
  it('rejects unknown and ambiguous configuration keys rather than selecting the first match', async () => {
    const api = fixture([local, cloud, cloud]), hook = renderHook(useStudioMediaExecution, { initialProps: api.props });
    await waitFor(() => expect(hook.result.current.providerLoading).toBe(false)); act(() => hook.result.current.changeOperation('m5.image.reference'));
    const before = structuredClone(hook.result.current.draft);
    for (const key of ['unknown-key', mediaProviderKey(cloud)]) {
      act(() => hook.result.current.changeField('providerKey', key)); expect(hook.result.current.draft).toEqual(before);
    }
    expect(api.preview).not.toHaveBeenCalled(); api.noDispatch();
  });
  it('ignores an old reference catalog when the provider owner is replaced', async () => {
    const api = fixture(), hook = renderHook(useStudioMediaExecution, { initialProps: api.props });
    await waitFor(() => expect(hook.result.current.providerLoading).toBe(false)); act(() => hook.result.current.changeOperation('m5.image.reference'));
    let resolve!: (rows: ProductionProvider[]) => void; api.providers.mockImplementationOnce(() => new Promise(yes => { resolve = yes; }));
    let work!: Promise<void>; act(() => { work = hook.result.current.loadProviders(); });
    hook.rerender({ ...api.props, client: { ...api.props.client, providers: vi.fn().mockResolvedValue([]) } });
    await act(async () => { resolve([cloud]); await work; });
    const before = structuredClone(hook.result.current.draft); act(() => hook.result.current.changeField('providerKey', mediaProviderKey(cloud)));
    expect(hook.result.current.providers).toEqual([]); expect(hook.result.current.draft).toEqual(before); expect(api.preview).not.toHaveBeenCalled(); api.noDispatch();
  });
});
