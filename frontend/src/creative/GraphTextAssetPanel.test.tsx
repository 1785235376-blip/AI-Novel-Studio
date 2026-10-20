// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { GraphModelExecutionPanel } from './GraphModelExecutionPanel';
import { GraphRunPanel } from './GraphRunPanel';
import { modelAdmittedRun, modelCapabilities, modelGraph, modelPreviewRun, modelRun } from './studioGraphModel.testFixtures';
import { pendingTextAsset, resultStorage, storedTextAssetRun } from './studioGraphTextAsset.testFixtures';
import type { StudioGraphRun } from './studioGraphTypes';
const read = <T,>(work: () => Promise<T>) => work();
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const click = (name: string) => fireEvent.click(button(name));
const consent = () => screen.getByRole('checkbox', { name: '已核对当前节点、完整输入和本地路由，允许调用一次' });
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function client() {
  return { catalog: vi.fn(), list: vi.fn(), create: vi.fn(), get: vi.fn(), save: vi.fn(), preflight: vi.fn(), createRun: vi.fn(),
    runs: vi.fn().mockResolvedValue({ items: [modelRun()] }), getRun: vi.fn().mockResolvedValue(modelRun()), action: vi.fn(),
    modelCapabilities: vi.fn().mockResolvedValue({ ...modelCapabilities(), result_storage: resultStorage() }), previewModel: vi.fn().mockResolvedValue(modelPreviewRun()),
    dispatchModel: vi.fn().mockResolvedValue({ ...modelAdmittedRun(), asset_output: pendingTextAsset() }), refreshModel: vi.fn().mockResolvedValue(storedTextAssetRun()) };
}
function setup(initial = modelRun(), patch: Partial<ComponentProps<typeof GraphRunPanel>> = {}) {
  const api = client(); api.runs.mockResolvedValue({ items: [initial] }); api.getRun.mockResolvedValue(initial);
  const props: ComponentProps<typeof GraphRunPanel> = { client: api, graph: modelGraph(), targetNodeIds: ['review'], dirty: false, busy: false, canMutate: true, canReview: true, modelExecutionEnabled: true, isCurrent: () => true, read, mutate: read, ...patch };
  const view = render(<GraphRunPanel {...props} />); return { ...view, api, props, rerender: (change: Partial<typeof props>) => view.rerender(<GraphRunPanel {...props} {...change} />) };
}
async function selectRun() { click('读取运行记录'); fireEvent.change(await screen.findByRole('combobox', { name: '已保存运行' }), { target: { value: 'model_run' } }); await screen.findByRole('region', { name: '当前创作图运行' }); }
async function selectRoute() { click('读取本地模型能力'); fireEvent.change(await screen.findByRole('combobox', { name: '本地文字模型路由' }), { target: { value: 'd'.repeat(64) } }); }
afterEach(cleanup);

describe('same-confirmation automatic private TextAsset archival', () => {
  it('discloses archival beside the original confirmation and submits one dispatch without another step', async () => {
    const { api } = setup(); await selectRun(); await selectRoute(); click('预览图节点模型输入'); await screen.findByRole('region', { name: '图节点模型输入预览' });
    expect(screen.getByText('成功结果会保存为私有待审核文字资产，审核不会写入正文。')).toBeTruthy();
    expect(screen.getAllByRole('checkbox')).toHaveLength(1); expect(button('确认调用图节点本地模型').disabled).toBe(true);
    fireEvent.click(consent()); click('确认调用图节点本地模型'); await screen.findByRole('region', { name: '私有文字资产回执' });
    expect(api.dispatchModel).toHaveBeenCalledTimes(1); expect(api.dispatchModel).toHaveBeenCalledWith('model_run', { expected_version: 3, reviewed_preview_digest: 'a'.repeat(64), archive_result: true });
    expect(screen.getByText('等待核对')).toBeTruthy(); expect(api.refreshModel).not.toHaveBeenCalled(); expect(screen.queryByRole('button', { name: /归档|保存.*资产/ })).toBeNull();
  });
  it('keeps legacy dispatch and visible confirmation unchanged when the server omits result storage', async () => {
    const { api } = setup(); api.modelCapabilities.mockResolvedValue(modelCapabilities() as never); await selectRun(); await selectRoute(); click('预览图节点模型输入'); await screen.findByRole('region', { name: '图节点模型输入预览' });
    expect(screen.queryByText('成功结果会保存为私有待审核文字资产，审核不会写入正文。')).toBeNull(); fireEvent.click(consent()); click('确认调用图节点本地模型');
    await waitFor(() => expect(api.dispatchModel).toHaveBeenCalledWith('model_run', { expected_version: 3, reviewed_preview_digest: 'a'.repeat(64) }));
  });
  it('displays original asset/model/source metadata in the current model panel and never adds a publication action', async () => {
    setup(storedTextAssetRun()); await selectRun(); expect(screen.getByRole('region', { name: '私有文字资产回执' })).toBeTruthy();
    expect(screen.getByText(/资产：private_text_asset · v1 · 19 字节 · text\/plain/)).toBeTruthy(); expect(screen.getByText(/模型：local \/ writer/)).toBeTruthy();
    expect(screen.getByText(/图摘要：/)).toBeTruthy(); expect(screen.getByText(/输入摘要：/)).toBeTruthy(); expect(screen.getByText(/文字 SHA-256：/)).toBeTruthy();
    expect(screen.getByText(/仅当前创作者可见；未写入正文/)).toBeTruthy(); expect(screen.queryByRole('button', { name: /发布|应用到正文|导出/ })).toBeNull();
  });
  it('uses only the existing read to reconcile incomplete storage and never repeats inference', async () => {
    const incomplete = storedTextAssetRun(); incomplete.asset_output = pendingTextAsset('INCOMPLETE'); incomplete.stale = true; incomplete.review = null; incomplete.model_runtime!.preview = null;
    for (const node of Object.values(incomplete.node_states)) node.output = null;
    const { api } = setup(incomplete); await selectRun(); expect(screen.getByText('存储未完成')).toBeTruthy(); expect(screen.queryByText('Saved proposed text')).toBeNull(); expect(screen.queryByRole('button', { name: '批准节点输出' })).toBeNull();
    api.getRun.mockResolvedValue(storedTextAssetRun()); click('重新读取当前运行'); await screen.findByText(/资产：private_text_asset/);
    expect(api.getRun).toHaveBeenCalledTimes(2); expect(api.dispatchModel).not.toHaveBeenCalled(); expect(api.refreshModel).not.toHaveBeenCalled(); expect(screen.getByText('Saved proposed text')).toBeTruthy();
  });
  it('shows approved and rejected storage states while preserving human review authority', async () => {
    const { api } = setup(storedTextAssetRun()); api.action.mockResolvedValue(storedTextAssetRun('APPROVED')); await selectRun();
    expect(button('批准节点输出').disabled).toBe(true); fireEvent.click(screen.getByRole('checkbox', { name: '已阅读本次输出并核对当前审核摘要' })); click('批准节点输出'); await screen.findByText('已批准');
    expect(api.action).toHaveBeenCalledWith('model_run', 'approve', { expected_version: 5, node_id: 'review', reviewed_output_digest: 'f'.repeat(64), note: '' });
    expect(screen.getByText(/资产：private_text_asset · v2/)).toBeTruthy(); expect(api.dispatchModel).not.toHaveBeenCalled();
  });
  it.each(['APPROVED', 'REJECTED'] as const)('reports the private asset receipt after %s without claiming assets were untouched', async state => {
    const { api } = setup(storedTextAssetRun()); api.action.mockResolvedValue(storedTextAssetRun(state)); await selectRun();
    fireEvent.click(screen.getByRole('checkbox', { name: '已阅读本次输出并核对当前审核摘要' })); click(state === 'APPROVED' ? '批准节点输出' : '驳回节点输出');
    await screen.findByText('原工作流运行记录已更新；私有文字资产状态见下方回执，正文未被写入。');
    expect(screen.queryByText('原工作流运行记录已更新；正文和资产未被写入。')).toBeNull();
    expect(screen.getByText(/资产：private_text_asset · v2/)).toBeTruthy(); expect(api.dispatchModel).not.toHaveBeenCalled();
  });
  it('preserves the original action notice for legacy runs without an asset output', async () => {
    const initial = storedTextAssetRun(), approved = storedTextAssetRun('APPROVED'); delete initial.asset_output; delete approved.asset_output;
    const { api } = setup(initial); api.action.mockResolvedValue(approved); await selectRun();
    fireEvent.click(screen.getByRole('checkbox', { name: '已阅读本次输出并核对当前审核摘要' })); click('批准节点输出');
    await screen.findByText('原工作流运行记录已更新；正文和资产未被写入。');
    expect(screen.queryByText('原工作流运行记录已更新；私有文字资产状态见下方回执，正文未被写入。')).toBeNull();
    expect(screen.queryByRole('region', { name: '私有文字资产回执' })).toBeNull(); expect(api.dispatchModel).not.toHaveBeenCalled();
  });
  it('drops a late private asset receipt after graph identity changes', async () => {
    const { api, rerender } = setup(), pending = deferred<StudioGraphRun>(); api.getRun.mockReturnValue(pending.promise);
    click('读取运行记录'); fireEvent.change(await screen.findByRole('combobox', { name: '已保存运行' }), { target: { value: 'model_run' } });
    rerender({ graph: { ...modelGraph(), version: 2 } }); await act(async () => pending.resolve(storedTextAssetRun()));
    expect(screen.queryByText(/private_text_asset/)).toBeNull(); expect(screen.queryByText('Saved proposed text')).toBeNull(); expect(api.dispatchModel).not.toHaveBeenCalled();
  });
  it.each([401, 403, 404])('clears private asset metadata after model capability denial %i', async status => {
    const { api } = setup(storedTextAssetRun()); await selectRun(); api.modelCapabilities.mockRejectedValue(new ApiError({ status, code: 'DENIED', message: 'Unavailable' })); click('读取本地模型能力');
    await screen.findByText(/已清除先前的模型预览和结果/); expect(screen.queryByRole('region', { name: '私有文字资产回执' })).toBeNull(); expect(screen.queryByText('Saved proposed text')).toBeNull();
  });
  it('clears the original consent after storage capability refresh, without automatically dispatching', async () => {
    const api = client(), perform = vi.fn().mockResolvedValue(true);
    render(<GraphModelExecutionPanel client={api} run={modelPreviewRun()} locked={false} canMutate uncertain={false} isCurrent={() => true} read={read} perform={perform} onUnavailable={vi.fn()} />);
    await selectRoute(); fireEvent.click(consent()); expect(button('确认调用图节点本地模型').disabled).toBe(false);
    api.modelCapabilities.mockResolvedValue(modelCapabilities() as never); click('读取本地模型能力'); await waitFor(() => expect(button('读取本地模型能力').disabled).toBe(false));
    expect((consent() as HTMLInputElement).checked).toBe(false); expect(button('确认调用图节点本地模型').disabled).toBe(true); expect(perform).not.toHaveBeenCalled();
  });
});
