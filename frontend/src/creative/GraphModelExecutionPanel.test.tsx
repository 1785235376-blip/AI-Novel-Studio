// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { GraphRunPanel } from './GraphRunPanel';
import type { StudioGraphRun } from './studioGraphTypes';
import { modelAdmittedRun, modelCapabilities, modelDigest, modelGraph, modelPreviewRun, modelRun, modelRuntime } from './studioGraphModel.testFixtures';

const perform = <T,>(work: () => Promise<T>) => work();
type Props = ComponentProps<typeof GraphRunPanel>;
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function setup(initial = modelRun(), options: Partial<Props> = {}) {
  const client = { catalog: vi.fn(), list: vi.fn(), create: vi.fn(), get: vi.fn(), save: vi.fn(), preflight: vi.fn(), createRun: vi.fn(),
    runs: vi.fn().mockResolvedValue({ items: [initial] }), getRun: vi.fn().mockResolvedValue(initial), action: vi.fn().mockResolvedValue(initial),
    modelCapabilities: vi.fn().mockResolvedValue(modelCapabilities()), previewModel: vi.fn().mockResolvedValue(modelPreviewRun()),
    dispatchModel: vi.fn().mockResolvedValue(modelAdmittedRun()), refreshModel: vi.fn().mockResolvedValue(modelAdmittedRun()) };
  const props: Props = { client, graph: modelGraph(), targetNodeIds: ['review'], dirty: false, busy: false, canMutate: true, canReview: true,
    modelExecutionEnabled: true, isCurrent: () => true, read: perform, mutate: perform, ...options };
  const rendered = render(<GraphRunPanel {...props} />);
  return { ...rendered, client, props, rerender: (patch: Partial<Props>) => rendered.rerender(<GraphRunPanel {...props} {...patch} />) };
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const click = (name: string) => fireEvent.click(button(name));
const consent = () => screen.getByRole('checkbox', { name: '已核对当前节点、完整输入和本地路由，允许调用一次' }) as HTMLInputElement;
async function selectRun() {
  click('读取运行记录'); fireEvent.change(await screen.findByRole('combobox', { name: '已保存运行' }), { target: { value: 'model_run' } });
  await screen.findByRole('region', { name: '当前创作图运行' });
}
async function selectRoute(id = 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd') {
  click('读取本地模型能力'); const select = await screen.findByRole('combobox', { name: '本地文字模型路由' }); fireEvent.change(select, { target: { value: id } });
}
async function preview() { click('预览图节点模型输入'); await screen.findByRole('region', { name: '图节点模型输入预览' }); }
afterEach(cleanup);

describe('explicit local graph model execution UI', () => {
  it('has no model surface or model requests when the catalog gate is off', async () => {
    const { client } = setup(modelRun(), { modelExecutionEnabled: false });
    expect(screen.queryByRole('region', { name: '可选本地文字模型执行' })).toBeNull();
    expect(client.modelCapabilities).not.toHaveBeenCalled(); expect(client.previewModel).not.toHaveBeenCalled(); expect(client.dispatchModel).not.toHaveBeenCalled();
  });
  it('does no automatic capability read, route choice, preview, dispatch or result refresh', async () => {
    const { client } = setup(); expect(client.modelCapabilities).not.toHaveBeenCalled(); await selectRun();
    expect(client.modelCapabilities).not.toHaveBeenCalled(); expect(button('预览图节点模型输入').disabled).toBe(true);
    click('读取本地模型能力'); const select = await screen.findByRole('combobox', { name: '本地文字模型路由' }) as HTMLSelectElement;
    expect(select.value).toBe(''); expect(button('预览图节点模型输入').disabled).toBe(true);
    fireEvent.change(select, { target: { value: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd' } }); expect(button('预览图节点模型输入').disabled).toBe(false);
    expect(client.previewModel).not.toHaveBeenCalled(); expect(client.dispatchModel).not.toHaveBeenCalled(); expect(client.refreshModel).not.toHaveBeenCalled();
    expect(screen.getByText(/云端 API：预留，当前不可执行/)).toBeTruthy(); expect(screen.getByText(/实际推理质量验收：未运行/)).toBeTruthy();
  });
  it('prepares the original local workflow separately from model dispatch', async () => {
    const initial = modelRun({ status: 'QUEUED', model_runtime: modelRuntime({ status: 'PENDING' }) });
    const { client } = setup(initial); client.action.mockResolvedValue(modelRun()); await selectRun();
    expect(screen.queryByRole('button', { name: '预览图节点模型输入' })).toBeNull(); click('执行前置本地节点');
    await screen.findByText('AWAITING_PREVIEW'); expect(client.action).toHaveBeenCalledWith('model_run', 'execute', { expected_version: 2, note: '' });
    expect(client.previewModel).not.toHaveBeenCalled(); expect(client.dispatchModel).not.toHaveBeenCalled();
  });
  it('dispatches only once using current run CAS and the explicitly reviewed preview digest', async () => {
    const { client } = setup(); const pending = deferred<StudioGraphRun>(); client.dispatchModel.mockReturnValue(pending.promise);
    await selectRun(); await selectRoute(); await preview();
    expect(client.previewModel).toHaveBeenCalledWith('model_run', { expected_version: 2, route_id: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', allow_synthetic: false });
    expect(screen.getByText('Complete reviewed author input')).toBeTruthy(); expect(button('确认调用图节点本地模型').disabled).toBe(true);
    fireEvent.click(consent()); click('确认调用图节点本地模型'); click('确认调用图节点本地模型');
    expect(client.dispatchModel).toHaveBeenCalledTimes(1); expect(client.dispatchModel).toHaveBeenCalledWith('model_run', { expected_version: 3, reviewed_preview_digest: modelDigest });
    await act(async () => pending.resolve(modelAdmittedRun())); await screen.findByRole('region', { name: '图节点模型执行回执' });
    expect(screen.queryByRole('button', { name: '确认调用图节点本地模型' })).toBeNull(); expect(client.refreshModel).not.toHaveBeenCalled();
    expect(button('暂停运行').disabled).toBe(true); expect(button('恢复运行').disabled).toBe(true); expect(button('取消运行').disabled).toBe(false);
    expect(screen.getAllByText(/调用记录尚待核对/).length).toBeGreaterThan(0);
  });
  it('requires separate explicit synthetic consent and never labels a mock as real inference verification', async () => {
    const { client } = setup(); client.previewModel.mockResolvedValue(modelPreviewRun(true)); client.dispatchModel.mockResolvedValue(modelAdmittedRun(true));
    await selectRun(); await selectRoute('eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'); expect(button('预览图节点模型输入').disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', { name: '明确使用测试适配器；不代表真实本地模型推理' })); await preview();
    expect(client.previewModel).toHaveBeenCalledWith('model_run', { expected_version: 2, route_id: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', allow_synthetic: true });
    fireEvent.click(consent()); click('确认调用图节点本地模型'); await screen.findByText(/测试适配器任务/);
    expect(screen.getByText(/实际推理质量验收：未运行/)).toBeTruthy();
  });
  it('clears reviewed consent on route changes, synthetic consent changes and dirty graph state', async () => {
    const { client, rerender } = setup(); await selectRun(); await selectRoute(); await preview(); fireEvent.click(consent());
    fireEvent.change(screen.getByRole('combobox', { name: '本地文字模型路由' }), { target: { value: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee' } });
    expect(consent().checked).toBe(false); expect(button('确认调用图节点本地模型').disabled).toBe(true);
    fireEvent.change(screen.getByRole('combobox', { name: '本地文字模型路由' }), { target: { value: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd' } }); fireEvent.click(consent());
    rerender({ dirty: true }); expect(consent().checked).toBe(false); expect(button('确认调用图节点本地模型').disabled).toBe(true);
    rerender({ dirty: false }); expect(consent().checked).toBe(false); expect(client.dispatchModel).not.toHaveBeenCalled();
  });
  it('does not auto-repeat an uncertain dispatch and only permits reconciliation or cancellation', async () => {
    const { client } = setup(); client.dispatchModel.mockRejectedValue(new ApiError({ status: 0, code: 'STUDIO_NETWORK_FAILED', message: 'Connection lost.' }));
    await selectRun(); await selectRoute(); await preview(); fireEvent.click(consent()); click('确认调用图节点本地模型');
    await screen.findByText('调用回执不确定。请重新读取当前运行或核对结果；不会自动重放。');
    expect(client.dispatchModel).toHaveBeenCalledTimes(1); expect(button('确认调用图节点本地模型').disabled).toBe(true); expect(button('预览图节点模型输入').disabled).toBe(true);
    expect(button('取消运行').disabled).toBe(false); expect(button('重新读取当前运行').disabled).toBe(false);
  });
  it('treats an invalid HTTP-200 dispatch projection as an uncertain commit and requires reconciliation', async () => {
    const { client } = setup(); client.dispatchModel.mockRejectedValue(new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: 'Invalid model receipt.' }));
    await selectRun(); await selectRoute(); await preview(); fireEvent.click(consent()); click('确认调用图节点本地模型');
    await screen.findByText('调用回执不确定。请重新读取当前运行或核对结果；不会自动重放。');
    expect(client.dispatchModel).toHaveBeenCalledTimes(1); expect(button('确认调用图节点本地模型').disabled).toBe(true);
    expect(consent().disabled).toBe(true); expect(button('预览图节点模型输入').disabled).toBe(true);
    expect(button('取消运行').disabled).toBe(false); expect(button('重新读取当前运行').disabled).toBe(false);
    client.getRun.mockResolvedValue(modelAdmittedRun()); click('重新读取当前运行'); await screen.findByRole('region', { name: '图节点模型执行回执' });
    expect(screen.queryByRole('button', { name: '确认调用图节点本地模型' })).toBeNull(); expect(client.dispatchModel).toHaveBeenCalledTimes(1);
  });
  it('keeps manual receipt refresh and original graph cancellation separate and explicit', async () => {
    const { client } = setup(modelAdmittedRun()); await selectRun(); expect(client.refreshModel).not.toHaveBeenCalled();
    click('核对图节点模型结果'); await waitFor(() => expect(client.refreshModel).toHaveBeenCalledWith('model_run', { expected_version: 4 }));
    await waitFor(() => expect(button('取消运行').disabled).toBe(false)); click('取消运行');
    await waitFor(() => expect(client.action).toHaveBeenCalledWith('model_run', 'cancel', { expected_version: 4, note: '' })); expect(client.dispatchModel).not.toHaveBeenCalled();
  });
  it('does not render capabilities that arrive after owner revocation', async () => {
    let current = true; const { client } = setup(modelRun(), { isCurrent: () => current }); const pending = deferred<ReturnType<typeof modelCapabilities>>();
    client.modelCapabilities.mockReturnValue(pending.promise); click('读取本地模型能力'); current = false;
    await act(async () => pending.resolve(modelCapabilities())); expect(screen.queryByRole('combobox', { name: '本地文字模型路由' })).toBeNull(); expect(client.dispatchModel).not.toHaveBeenCalled();
  });
  it.each([401, 403, 404])('purges an existing model preview after authoritative capability denial %i', async status => {
    const { client } = setup(modelPreviewRun()); client.modelCapabilities.mockRejectedValue(new ApiError({ status, code: 'EXPERIMENTAL_FEATURE_DISABLED', message: 'Unavailable.' }));
    await selectRun(); expect(screen.getByText('Complete reviewed author input')).toBeTruthy(); click('读取本地模型能力');
    await screen.findByText('模型执行权限或入口已变更，已清除先前的模型预览和结果。请重新核对当前能力与运行记录。');
    expect(screen.queryByText('Complete reviewed author input')).toBeNull(); expect(screen.queryByRole('region', { name: '当前创作图运行' })).toBeNull(); expect(client.dispatchModel).not.toHaveBeenCalled();
  });
  it('purges cached prompt and route controls when dispatch discovers feature revocation', async () => {
    const { client } = setup(); client.dispatchModel.mockRejectedValue(new ApiError({ status: 404, code: 'EXPERIMENTAL_FEATURE_DISABLED', message: 'Unavailable.' }));
    await selectRun(); await selectRoute(); await preview(); fireEvent.click(consent()); click('确认调用图节点本地模型');
    await screen.findByText('模型执行权限或入口已变更，已清除先前的模型预览和结果。请重新核对当前能力与运行记录。');
    expect(screen.queryByText('Complete reviewed author input')).toBeNull(); expect(screen.queryByRole('combobox', { name: '本地文字模型路由' })).toBeNull(); expect(client.dispatchModel).toHaveBeenCalledTimes(1);
  });
  it('drops a late private model preview when the saved graph version changes', async () => {
    const { client, rerender } = setup(); const pending = deferred<StudioGraphRun>(); client.previewModel.mockReturnValue(pending.promise);
    await selectRun(); await selectRoute(); click('预览图节点模型输入'); rerender({ graph: { ...modelGraph(), version: 2 } });
    await act(async () => pending.resolve(modelPreviewRun())); expect(screen.queryByText('Complete reviewed author input')).toBeNull(); expect(screen.queryByRole('region', { name: '当前创作图运行' })).toBeNull();
  });
  it('does not expose a stale model preview or enable model actions for paused runs', async () => {
    setup({ ...modelPreviewRun(), stale: true, status: 'PAUSED' }); await selectRun();
    expect(screen.queryByText('Complete reviewed author input')).toBeNull(); expect(button('预览图节点模型输入').disabled).toBe(true); expect(screen.queryByRole('button', { name: '确认调用图节点本地模型' })).toBeNull();
  });
  it('retains separate human review authority, exact output digest and model-origin labeling', async () => {
    const initial = modelAdmittedRun(); initial.status = 'WAITING_APPROVAL'; initial.model_runtime!.status = 'RESULT_REVIEW';
    initial.model_runtime!.execution!.model_called = true; initial.model_called = true;
    initial.review = { node_id: 'review', output_digest: 'c'.repeat(64), draft: { origin: 'MODEL_PROPOSAL', text: 'Candidate requiring review' } };
    const { client } = setup(initial, { canMutate: false, canReview: true }); await selectRun();
    const review = within(screen.getByRole('region', { name: '节点输出审核' })); expect(review.getByText('来源：模型提案（需人工审核）')).toBeTruthy();
    expect(button('批准节点输出').disabled).toBe(true); fireEvent.click(review.getByRole('checkbox')); click('批准节点输出');
    await waitFor(() => expect(client.action).toHaveBeenCalledWith('model_run', 'approve', { expected_version: 4, node_id: 'review', reviewed_output_digest: 'c'.repeat(64), note: '' }));
    expect(client.dispatchModel).not.toHaveBeenCalled();
  });
});
