// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { ProviderTaskMatchPanel } from './ProviderTaskMatchPanel';
import { GraphModelExecutionPanel } from './GraphModelExecutionPanel';
import { createStudioGraphClient } from './studioGraphClient';
import { modelCapabilities } from './studioGraphModel.testFixtures';
import { providerCatalog, taskMatch, taskRequirement } from './studioProvider.testFixtures';
import type { StudioTaskRequirement } from './studioProviderTypes';

type Props = ComponentProps<typeof ProviderTaskMatchPanel>;
const read = <T,>(work: () => Promise<T>) => work();
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const click = (name: string) => fireEvent.click(button(name));
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (value: unknown) => void; const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; }); return { promise, resolve, reject }; }
function setup(options: Partial<Props> = {}) {
  const client = { providerContracts: vi.fn().mockResolvedValue(providerCatalog()), modelMatch: vi.fn().mockImplementation((value: StudioTaskRequirement) => Promise.resolve(taskMatch(value))) };
  const props: Props = { client, routes: modelCapabilities().routes, locked: false, isCurrent: () => true, read, onUnavailable: vi.fn(), ...options };
  const view = render(<ProviderTaskMatchPanel {...props} />); return { ...view, client, props, rerender: (patch: Partial<Props>) => view.rerender(<ProviderTaskMatchPanel {...props} {...patch} />) };
}
async function catalog() { click('读取提供方契约'); await screen.findByRole('combobox', { name: '匹配任务类型' }); }
afterEach(cleanup);

describe('explicit advisory provider and requirement panel', () => {
  it('never reads on mount or chooses a route after a catalog read', async () => {
    const { client } = setup(); expect(client.providerContracts).not.toHaveBeenCalled(); expect(client.modelMatch).not.toHaveBeenCalled();
    await catalog(); expect((screen.getByRole('combobox', { name: '匹配指定路由' }) as HTMLSelectElement).value).toBe('');
    expect(client.providerContracts).toHaveBeenCalledTimes(1); expect(client.modelMatch).not.toHaveBeenCalled();
    expect(screen.getByText(/LM Studio 仍缺少可信本地性证据/)).toBeTruthy(); expect(screen.getByText(/图片和视频生成仅预留/)).toBeTruthy();
    expect(screen.getByText(/API 仅预留，不可执行/)).toBeTruthy(); expect(screen.getAllByText(/声明能力：/)).toHaveLength(5); expect(screen.getAllByText(/已验证适配器契约：/)).toHaveLength(5);
  });
  it('submits explicit requirement fields only and does not treat eligible as dispatch authority', async () => {
    const { client } = setup(); await catalog();
    fireEvent.change(screen.getByLabelText('匹配指定路由', { exact: true }), { target: { value: 'd'.repeat(64) } });
    fireEvent.change(screen.getByLabelText('最低主机 RAM（MiB，可选）', { exact: true }), { target: { value: '8000' } });
    fireEvent.change(screen.getByLabelText('最低主机 VRAM（MiB，可选）', { exact: true }), { target: { value: '4000' } });
    expect(client.modelMatch).not.toHaveBeenCalled(); click('查看任务匹配说明'); await screen.findByRole('region', { name: '任务匹配结果' });
    expect(client.modelMatch).toHaveBeenCalledWith(taskRequirement({ preferred_route: 'd'.repeat(64), min_host_ram_mib: 8000, min_host_vram_mib: 4000 }), expect.any(AbortSignal));
    expect(screen.getByText('仅建议，不授权执行')).toBeTruthy(); expect(screen.getByText(/当前可用内存：未知；GPU 适配：未验证/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /调用.*模型/ })).toBeNull();
  });
  it.each(['IMAGE_GENERATION', 'VIDEO_GENERATION'] as const)('explains reserved %s without calling the matcher on selection', async task_type => {
    const { client } = setup(); await catalog(); fireEvent.change(screen.getByLabelText('匹配任务类型', { exact: true }), { target: { value: task_type } });
    expect(client.modelMatch).not.toHaveBeenCalled(); expect(screen.getByText(/执行未开放；这里只显示不匹配原因/)).toBeTruthy();
    click('查看任务匹配说明'); await screen.findByRole('region', { name: '任务匹配结果' });
    expect(client.modelMatch.mock.calls[0][0].task_type).toBe(task_type); expect(screen.getByText('TASK_CAPABILITY_MISMATCH')).toBeTruthy();
  });
  it('keeps explicit synthetic matching consent separate and resets it on task or route changes', async () => {
    const { client } = setup(); await catalog(); const consent = () => screen.getByRole('checkbox', { name: '明确将测试适配器纳入匹配；这不是模型调用授权' }) as HTMLInputElement;
    expect(consent().checked).toBe(false); fireEvent.click(consent()); click('查看任务匹配说明'); await screen.findByRole('region', { name: '任务匹配结果' });
    expect(client.modelMatch.mock.calls[0][0].allow_synthetic).toBe(true);
    fireEvent.change(screen.getByLabelText('匹配指定路由', { exact: true }), { target: { value: 'e'.repeat(64) } }); expect(consent().checked).toBe(false);
    expect(screen.queryByRole('region', { name: '任务匹配结果' })).toBeNull(); fireEvent.click(consent());
    fireEvent.change(screen.getByLabelText('匹配任务类型', { exact: true }), { target: { value: 'IMAGE_GENERATION' } }); expect(consent().checked).toBe(false);
  });
  it('blocks invalid memory requirements locally, retaining an empty-field option', async () => {
    const { client } = setup(); await catalog(); const input = screen.getByLabelText('最低主机 RAM（MiB，可选）', { exact: true });
    for (const value of ['0', '-1', '1.5', '10000001']) { fireEvent.change(input, { target: { value } }); expect(button('查看任务匹配说明').disabled).toBe(true); click('查看任务匹配说明'); }
    expect(client.modelMatch).not.toHaveBeenCalled(); fireEvent.change(input, { target: { value: '' } }); expect(button('查看任务匹配说明').disabled).toBe(false);
  });
  it('coalesces duplicate catalog and match clicks while each read is pending', async () => {
    const { client } = setup(), first = deferred<ReturnType<typeof providerCatalog>>(); client.providerContracts.mockReturnValue(first.promise);
    click('读取提供方契约'); click('读取提供方契约'); expect(client.providerContracts).toHaveBeenCalledTimes(1);
    await act(async () => first.resolve(providerCatalog())); const second = deferred<ReturnType<typeof taskMatch>>(); client.modelMatch.mockReturnValue(second.promise);
    click('查看任务匹配说明'); click('查看任务匹配说明'); expect(client.modelMatch).toHaveBeenCalledTimes(1);
    await act(async () => second.resolve(taskMatch())); expect(button('查看任务匹配说明').disabled).toBe(false);
  });
  it('aborts a superseded requirement and ignores its late success without clearing a newer request', async () => {
    const { client } = setup(); await catalog(); const old = deferred<ReturnType<typeof taskMatch>>(), newer = deferred<ReturnType<typeof taskMatch>>();
    client.modelMatch.mockReturnValueOnce(old.promise).mockReturnValueOnce(newer.promise); click('查看任务匹配说明'); const oldSignal = client.modelMatch.mock.calls[0][1] as AbortSignal;
    fireEvent.change(screen.getByLabelText('匹配任务类型', { exact: true }), { target: { value: 'IMAGE_GENERATION' } }); expect(oldSignal.aborted).toBe(true);
    click('查看任务匹配说明'); await act(async () => old.resolve(taskMatch())); expect(screen.queryByRole('region', { name: '任务匹配结果' })).toBeNull(); expect(button('查看任务匹配说明').disabled).toBe(true);
    await act(async () => newer.resolve(taskMatch(taskRequirement({ task_type: 'IMAGE_GENERATION' })))); expect(screen.getByText('TASK_CAPABILITY_MISMATCH')).toBeTruthy();
  });
  it('does not let stale denied responses revoke the current scope or newer requirement', async () => {
    const { client, props } = setup(); await catalog(); const old = deferred<ReturnType<typeof taskMatch>>(); client.modelMatch.mockReturnValueOnce(old.promise);
    click('查看任务匹配说明'); fireEvent.change(screen.getByLabelText('最低主机 RAM（MiB，可选）', { exact: true }), { target: { value: '2000' } });
    await act(async () => old.reject(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Old request denied' })));
    expect(props.onUnavailable).not.toHaveBeenCalled(); expect(screen.queryByText('Old request denied')).toBeNull(); expect(button('查看任务匹配说明').disabled).toBe(false);
  });
  it.each([401, 403, 404])('purges all cached advisory data after authoritative permission denial %i', async status => {
    const { client, props } = setup(); await catalog(); click('查看任务匹配说明'); await screen.findByRole('region', { name: '任务匹配结果' });
    client.modelMatch.mockRejectedValue(new ApiError({ status, code: 'UNAVAILABLE', message: 'Unavailable' })); click('查看任务匹配说明');
    await waitFor(() => expect(props.onUnavailable).toHaveBeenCalledTimes(1)); expect(screen.queryByRole('region', { name: '任务匹配结果' })).toBeNull(); expect(screen.queryByRole('combobox', { name: '匹配任务类型' })).toBeNull();
  });
  it('drops and aborts a late read when locked, unmounted, or the owner is revoked', async () => {
    let current = true; const { client, rerender, unmount } = setup({ isCurrent: () => current }); const pending = deferred<ReturnType<typeof providerCatalog>>(); client.providerContracts.mockReturnValue(pending.promise);
    click('读取提供方契约'); current = false; await act(async () => pending.resolve(providerCatalog())); expect(screen.queryByRole('combobox', { name: '匹配任务类型' })).toBeNull();
    current = true; rerender({ locked: true }); expect(button('读取提供方契约').disabled).toBe(true);
    rerender({ locked: false }); client.providerContracts.mockReturnValue(new Promise(() => {})); click('读取提供方契约'); rerender({ locked: true }); expect((client.providerContracts.mock.calls[1][0] as AbortSignal).aborted).toBe(true);
    rerender({ locked: false }); click('读取提供方契约'); unmount(); expect((client.providerContracts.mock.calls[2][0] as AbortSignal).aborted).toBe(true);
  });
  it('clears catalog and pending work when transport owner changes', async () => {
    const { client, rerender } = setup(); await catalog(); const old = deferred<ReturnType<typeof taskMatch>>(); client.modelMatch.mockReturnValue(old.promise); click('查看任务匹配说明');
    const next = { providerContracts: vi.fn().mockResolvedValue(providerCatalog()), modelMatch: vi.fn().mockResolvedValue(taskMatch()) }; rerender({ client: next });
    await act(async () => old.resolve(taskMatch())); expect(screen.queryByRole('region', { name: '任务匹配结果' })).toBeNull(); expect(screen.queryByRole('combobox', { name: '匹配任务类型' })).toBeNull();
    expect(next.providerContracts).not.toHaveBeenCalled();
  });
  it('shows malformed HTTP-200 as an error rather than a positive capability or an execution option', async () => {
    const raw = { ...providerCatalog(), dispatch_authorized: true }, json = vi.fn().mockResolvedValue(raw), client = createStudioGraphClient('model_project', {}, { json }); setup({ client });
    click('读取提供方契约'); await screen.findByRole('alert'); expect(screen.queryByRole('combobox', { name: '匹配任务类型' })).toBeNull(); expect(json).toHaveBeenCalledTimes(1);
  });
  it('can read as an authorized viewer and never changes the existing selected execution route', async () => {
    const perform = vi.fn(), json = vi.fn().mockImplementation((url: string, _method: string, value: StudioTaskRequirement) => Promise.resolve(url.endsWith('model-capabilities') ? modelCapabilities() : url.endsWith('provider-contracts') ? providerCatalog() : taskMatch(value)));
    const client = createStudioGraphClient('model_project', {}, { json });
    const view = render(<GraphModelExecutionPanel client={client} locked={false} canMutate={false} uncertain={false} isCurrent={() => true} read={read} perform={perform} onUnavailable={vi.fn()} />);
    await catalog(); click('查看任务匹配说明'); await screen.findByRole('region', { name: '任务匹配结果' }); expect(perform).not.toHaveBeenCalled();
    view.rerender(<GraphModelExecutionPanel client={client} locked={false} canMutate uncertain={false} isCurrent={() => true} read={read} perform={perform} onUnavailable={vi.fn()} />);
    click('读取本地模型能力'); const select = await screen.findByRole('combobox', { name: '本地文字模型路由' }) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'd'.repeat(64) } }); await catalog(); fireEvent.change(screen.getByLabelText('匹配指定路由', { exact: true }), { target: { value: 'e'.repeat(64) } });
    click('查看任务匹配说明'); await screen.findByRole('region', { name: '任务匹配结果' }); expect(select.value).toBe('d'.repeat(64)); expect(perform).not.toHaveBeenCalled();
    expect(json.mock.calls.every(([url]) => !/\/model\/(preview|dispatch|refresh)$/.test(url))).toBe(true);
  });
});
