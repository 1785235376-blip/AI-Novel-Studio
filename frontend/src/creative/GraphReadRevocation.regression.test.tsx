// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { GraphModelExecutionPanel } from './GraphModelExecutionPanel';
import { GraphRunPanel } from './GraphRunPanel';
import { modelCapabilities, modelGraph, modelRun } from './studioGraphModel.testFixtures';
import { storedTextAssetRun } from './studioGraphTextAsset.testFixtures';
import type { StudioGraphRun } from './studioGraphTypes';

const execute = <T,>(work: () => Promise<T>) => work();
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const click = (name: string) => fireEvent.click(button(name));
const denial = (status = 403) => new ApiError({ status, code: 'DENIED', message: 'Unavailable.' });
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (value: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function api() {
  return { catalog: vi.fn(), list: vi.fn(), create: vi.fn(), get: vi.fn(), save: vi.fn(), preflight: vi.fn(), createRun: vi.fn(),
    runs: vi.fn().mockResolvedValue({ items: [modelRun(), modelRun({ id: 'newer_run' })] }),
    getRun: vi.fn().mockResolvedValue(modelRun()), action: vi.fn().mockResolvedValue(modelRun({ version: 6 })),
    modelCapabilities: vi.fn().mockResolvedValue(modelCapabilities()), previewModel: vi.fn(), dispatchModel: vi.fn(), refreshModel: vi.fn() };
}
function setup(patch: Partial<ComponentProps<typeof GraphRunPanel>> = {}) {
  const client = api();
  const props: ComponentProps<typeof GraphRunPanel> = { client, graph: modelGraph(), targetNodeIds: ['review'], dirty: false, busy: false,
    canMutate: true, canReview: true, isCurrent: () => true, read: execute, mutate: execute, ...patch };
  const view = render(<GraphRunPanel {...props} />);
  return { client, ...view, rerender: (next: Partial<typeof props>) => view.rerender(<GraphRunPanel {...props} {...next} />) };
}
async function savedRuns() { click('读取运行记录'); return screen.findByRole('combobox', { name: '已保存运行' }); }
afterEach(cleanup);

describe('private graph revocation remains fail-closed without parent teardown', () => {
  it.each([401, 403, 404])('hides every private model receipt after capability denial %i', async status => {
    const client = api(), onUnavailable = vi.fn(), perform = vi.fn();
    client.modelCapabilities.mockRejectedValue(denial(status));
    const props = { client, run: storedTextAssetRun(), locked: false, canMutate: true, uncertain: false,
      isCurrent: () => true, read: execute, perform, onUnavailable };
    const view = render(<GraphModelExecutionPanel {...props} />);
    expect(screen.getByText(/private_text_asset/)).toBeTruthy();
    click('读取本地模型能力');
    await screen.findByText(/已清除先前的模型预览和结果/);
    expect(onUnavailable).toHaveBeenCalledOnce();
    expect(screen.queryByRole('region', { name: '私有文字资产回执' })).toBeNull();
    expect(screen.queryByRole('region', { name: '图节点模型执行回执' })).toBeNull();
    expect(screen.queryByText('Complete reviewed author input')).toBeNull();
    view.rerender(<GraphModelExecutionPanel {...props} run={{ ...props.run, version: 20 }} />);
    expect(screen.queryByText(/private_text_asset/)).toBeNull();
    expect(button('读取本地模型能力').disabled).toBe(true);
    expect(perform).not.toHaveBeenCalled();
  });

  it('also clears the model receipt when the nested provider read is denied', async () => {
    const client = { ...api(), providerContracts: vi.fn().mockRejectedValue(denial()), modelMatch: vi.fn() };
    const onUnavailable = vi.fn(), perform = vi.fn();
    render(<GraphModelExecutionPanel client={client} run={storedTextAssetRun()} locked={false} canMutate uncertain={false}
      isCurrent={() => true} read={execute} perform={perform} onUnavailable={onUnavailable} />);
    click('读取提供方契约'); await screen.findByText(/已清除先前的模型预览和结果/);
    expect(screen.queryByText(/private_text_asset/)).toBeNull();
    expect(onUnavailable).toHaveBeenCalledOnce(); expect(perform).not.toHaveBeenCalled();
  });
});

describe('newer explicit run intent supersedes reads, never commands', () => {
  it('ignores a denied older list after an exact-CAS action succeeds', async () => {
    const { client } = setup(), list = deferred<{ items: StudioGraphRun[] }>();
    const select = await savedRuns(); fireEvent.change(select, { target: { value: 'model_run' } });
    await screen.findByRole('region', { name: '当前创作图运行' });
    client.runs.mockReturnValueOnce(list.promise); click('读取运行记录');
    const signal = client.runs.mock.calls[1][1] as AbortSignal;
    expect(button('取消运行').disabled).toBe(false); click('取消运行');
    await screen.findByText('运行 model_run · v6 · 图 v1');
    expect(signal.aborted).toBe(true);
    expect(client.action).toHaveBeenCalledOnce();
    expect(client.action).toHaveBeenCalledWith('model_run', 'cancel', { expected_version: 2, note: '' });
    await act(async () => list.reject(denial()));
    expect(screen.getByRole('region', { name: '当前创作图运行' })).toBeTruthy();
    expect(screen.queryByText(/权限或入口已变更/)).toBeNull();
  });

  it('ignores a denied older selection and keeps only the newer exact run', async () => {
    const { client } = setup(), older = deferred<StudioGraphRun>(), newer = deferred<StudioGraphRun>();
    client.getRun.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const select = await savedRuns(); fireEvent.change(select, { target: { value: 'model_run' } });
    expect((select as HTMLSelectElement).disabled).toBe(false);
    fireEvent.change(select, { target: { value: 'newer_run' } });
    await act(async () => newer.resolve(modelRun({ id: 'newer_run', version: 9 })));
    await act(async () => older.reject(denial(401)));
    expect(screen.getByText('运行 newer_run · v9 · 图 v1')).toBeTruthy();
    expect(client.getRun.mock.calls).toEqual([['model_run'], ['newer_run']]);
    expect(screen.queryByText(/权限或入口已变更/)).toBeNull();
  });

  it('cannot replace or duplicate an in-flight command with another selection', async () => {
    const { client } = setup(), command = deferred<StudioGraphRun>();
    client.action.mockReturnValueOnce(command.promise);
    const select = await savedRuns(); fireEvent.change(select, { target: { value: 'model_run' } });
    await screen.findByRole('region', { name: '当前创作图运行' }); click('取消运行');
    expect((select as HTMLSelectElement).disabled).toBe(true);
    fireEvent.change(select, { target: { value: 'newer_run' } }); click('取消运行');
    expect(client.getRun).toHaveBeenCalledTimes(1); expect(client.action).toHaveBeenCalledTimes(1);
    await act(async () => command.resolve(modelRun({ status: 'CANCELLED', version: 3 })));
    expect(screen.getByText('运行 model_run · v3 · 图 v1')).toBeTruthy();
  });

  it('aborts persisted-run recovery when a newer requested identity replaces it', async () => {
    const older = deferred<StudioGraphRun>(), newer = deferred<StudioGraphRun>(), client = api();
    client.getRun.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const { rerender } = setup({ client, requestedRunId: 'model_run' });
    await waitFor(() => expect(client.getRun).toHaveBeenCalledOnce());
    const signal = client.getRun.mock.calls[0][1] as AbortSignal;
    rerender({ requestedRunId: 'newer_run' });
    expect(signal.aborted).toBe(true);
    await act(async () => newer.resolve(modelRun({ id: 'newer_run', version: 10 })));
    await act(async () => older.resolve(storedTextAssetRun()));
    expect(screen.getByText('运行 newer_run · v10 · 图 v1')).toBeTruthy();
    expect(screen.queryByText(/private_text_asset|Saved proposed text/)).toBeNull();
    expect(client.action).not.toHaveBeenCalled(); expect(client.createRun).not.toHaveBeenCalled();
  });
});
