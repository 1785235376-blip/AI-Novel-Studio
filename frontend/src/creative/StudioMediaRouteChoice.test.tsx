// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { mediaProviderKey, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { MediaCommand, MediaOperation, ProductionJob, ProductionPreview, ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { cutoutAssets } from './studioCpuCutout.testFixtures';
const digest = 'a'.repeat(64), source = cutoutAssets()[0];
const row = (local: boolean, operation: MediaOperation = 'm5.image.t2i'): ProductionProvider => ({ operation_id: operation, provider_id: local ? 'local-config' : 'cloud-config', model_id: 'configured-model', local,
  route_digest: digest, capability: 'IMAGE', supported_parameters: ['seed', 'width'], readiness: 'CONFIGURED_NOT_VERIFIED' });
const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const select = () => screen.getByLabelText('服务商与模型') as HTMLSelectElement;
function setup(rows = [row(true), row(false)], extra: Partial<StudioMediaExecutionProps> = {}) {
  const providers = vi.fn().mockResolvedValue(rows), create = vi.fn(), execute = vi.fn(), get = vi.fn(), list = vi.fn().mockResolvedValue([]);
  const preview = vi.fn(async (command: MediaCommand) => ({ operation_id: command.operation_id, preview_digest: digest, request_digest: digest,
    provider: rows.find(item => item.provider_id === command.provider_id), execution_recipe: {}, command } as unknown as ProductionPreview));
  const client = { providers, preview, create, execute, get, list } as unknown as StudioProductionClient;
  const props: StudioMediaExecutionProps = { client, assets: [source], canMutate: true, canReview: true, busy: false, isCurrent: () => true,
    read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn(), ...extra };
  return { ...render(<StudioMediaExecutionPanel {...props} />), props, providers, preview, create, execute, get, list };
}
async function loaded() { await waitFor(() => expect(button('重新读取配置').disabled).toBe(false)); }
afterEach(cleanup);
describe('explicit standalone image/video route choice', () => {
  it.each(['m5.image.t2i', 'm7.video.t2v'] as MediaOperation[])('starts %s locally without selecting or dispatching even with only cloud configuration', async operation => {
    const api = setup([row(false, operation)]); await loaded(); change('操作', operation);
    expect((screen.getByLabelText('制作路线') as HTMLSelectElement).value).toBe('local'); expect(select().options).toHaveLength(1);
    expect(screen.getByText(/当前操作暂无本地配置/)).toBeTruthy(); change('制作路线', 'cloud'); expect(select().options).toHaveLength(2); expect(select().value).toBe('');
    change('服务商与模型', mediaProviderKey(row(false, operation))); change('本次提示词', 'Preserved prompt'); expect(button('读取制作预览').disabled).toBe(true);
    change('制作路线', 'local'); expect(select().value).toBe(''); expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('Preserved prompt');
    expect(api.preview).not.toHaveBeenCalled(); expect(api.create).not.toHaveBeenCalled(); expect(api.execute).not.toHaveBeenCalled();
  });
  it('preserves sources and parameters across both directions, invalidates preview and requires new cloud consent', async () => {
    const operation = 'm7.video.i2v', local = row(true, operation), cloud = row(false, operation);
    const api = setup([local, cloud]); await loaded(); change('操作', operation); change('服务商与模型', mediaProviderKey(local));
    change('本次提示词', 'Keep this'); change('种子（0–2147483647）', '42'); fireEvent.click(screen.getByLabelText(`${source.filename} · v${source.version}`));
    change('制作路线', 'cloud'); expect(select().value).toBe(''); change('服务商与模型', mediaProviderKey(cloud));
    expect((screen.getByLabelText('种子（0–2147483647）') as HTMLInputElement).value).toBe('42'); expect((screen.getByLabelText(`${source.filename} · v${source.version}`) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByLabelText(/确认本次允许将提示词/)); fireEvent.click(button('读取制作预览'));
    await screen.findByRole('region', { name: '制作预览确认' }); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); expect(button('仅创建任务并入队').disabled).toBe(false);
    change('制作路线', 'local'); expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull(); change('服务商与模型', mediaProviderKey(local));
    expect((screen.getByLabelText('种子（0–2147483647）') as HTMLInputElement).value).toBe('42'); change('制作路线', 'cloud'); change('服务商与模型', mediaProviderKey(cloud));
    expect((screen.getByLabelText(/确认本次允许将提示词/) as HTMLInputElement).checked).toBe(false); expect(api.preview).toHaveBeenCalledTimes(1); expect(api.create).not.toHaveBeenCalled(); expect(api.execute).not.toHaveBeenCalled();
  });
  it('locks route edits and coalesces repeated preview clicks while the original read is pending', async () => {
    const api = setup(); await loaded(); change('服务商与模型', mediaProviderKey(row(true))); change('本次提示词', 'One preview');
    let resolve!: (value: ProductionPreview) => void;
    api.preview.mockImplementationOnce(() => new Promise<ProductionPreview>(yes => { resolve = yes; }));
    fireEvent.click(button('读取制作预览')); fireEvent.click(button('读取制作预览'));
    expect(api.preview).toHaveBeenCalledTimes(1); expect((screen.getByLabelText('制作路线') as HTMLSelectElement).disabled).toBe(true);
    const command = api.preview.mock.calls[0][0];
    await act(async () => { resolve({ operation_id: command.operation_id, preview_digest: digest, request_digest: digest, provider: row(true), execution_recipe: {}, command } as unknown as ProductionPreview); });
    expect((screen.getByLabelText('制作路线') as HTMLSelectElement).disabled).toBe(false); expect(api.create).not.toHaveBeenCalled(); expect(api.execute).not.toHaveBeenCalled();
  });
  it('preserves route and input on failed configuration reads without inferring availability or falling back', async () => {
    const api = setup(); await loaded(); change('制作路线', 'cloud'); change('服务商与模型', mediaProviderKey(row(false))); change('本次提示词', 'Keep on error');
    api.providers.mockRejectedValueOnce(new Error('Configuration offline')); fireEvent.click(button('重新读取配置')); await screen.findByText(/Configuration offline|服务商配置读取失败/);
    expect((screen.getByLabelText('制作路线') as HTMLSelectElement).value).toBe('cloud'); expect(select().value).toBe(mediaProviderKey(row(false)));
    expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('Keep on error'); expect(screen.getByText(/配置参考不代表服务已验证可用/)).toBeTruthy(); expect(api.preview).not.toHaveBeenCalled();
  });
  it('does not substitute a route after a configuration disappears', async () => {
    const api = setup(); await loaded(); change('服务商与模型', mediaProviderKey(row(true))); change('本次提示词', 'Keep reload');
    api.providers.mockResolvedValueOnce([row(false)]); fireEvent.click(button('重新读取配置')); await screen.findByText(/当前操作暂无本地配置/);
    expect(select().value).toBe(''); expect(button('读取制作预览').disabled).toBe(true); expect(api.preview).not.toHaveBeenCalled(); expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('Keep reload');
  });
  it('ignores a late configuration read after owner replacement', async () => {
    const api = setup(); await loaded(); let resolve!: (rows: ProductionProvider[]) => void;
    api.providers.mockReturnValueOnce(new Promise<ProductionProvider[]>(yes => { resolve = yes; })); fireEvent.click(button('重新读取配置'));
    api.rerender(<StudioMediaExecutionPanel {...api.props} client={{ ...api.props.client, providers: vi.fn().mockResolvedValue([]) }} />); await screen.findByText(/当前操作暂无本地配置/);
    await act(async () => { resolve([row(false)]); }); change('制作路线', 'cloud'); expect(select().options).toHaveLength(1); expect(api.preview).not.toHaveBeenCalled();
  });
  it('reopens the original job without changing draft route or submitting', async () => {
    const api = setup(); await loaded(); change('制作路线', 'cloud'); change('本次提示词', 'New draft');
    const job = { owner: 'image', id: 'original-job', version: 1, operation_id: 'm5.image.t2i', status: 'QUEUED', sources: [], request_digest: digest, output_candidate: null } as unknown as ProductionJob;
    api.list.mockResolvedValue([job]); api.get.mockResolvedValue(job); fireEvent.click(button('读取任务列表')); await screen.findByLabelText('已保存任务'); change('已保存任务', 'image:original-job'); await screen.findByText('已读取当前任务版本；未重新执行。');
    expect((screen.getByLabelText('制作路线') as HTMLSelectElement).value).toBe('cloud'); expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('New draft');
    expect(api.get).toHaveBeenCalledTimes(1); expect(api.preview).not.toHaveBeenCalled(); expect(api.create).not.toHaveBeenCalled(); expect(api.execute).not.toHaveBeenCalled();
  });
  it('keeps prepared storyboard requests and local-only operations without a route switch', async () => {
    const command = { operation_id: 'm7.video.t2v', request_id: 'prepared', source_snapshots: [] } as unknown as MediaCommand;
    const api = setup([], { preparedCommand: command, preparedIsCurrent: () => true }); expect(screen.queryByLabelText('制作路线')).toBeNull(); expect(screen.getByText('原分镜视频请求')).toBeTruthy();
    api.unmount(); setup(); await loaded(); for (const operation of ['m5.image.cutout', 'm5.image.upscale', 'm8.audio.trim']) { change('操作', operation); expect(screen.queryByLabelText('制作路线')).toBeNull(); }
  });
});
