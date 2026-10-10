// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { GraphRunPanel } from './GraphRunPanel';
import type { StudioGraphPreflight, StudioGraphRecord, StudioGraphRun } from './studioGraphTypes';

const digest = 'a'.repeat(64), outputDigest = 'b'.repeat(64), stamp = '2026-10-09T13:00:00Z';
const owner = { project_id: 'project', scope: { mode: 'collaboration' as const, novel_id: 'project', workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch' } };
const graph = (): StudioGraphRecord => ({ ...owner, id: 'graph', version: 4, created_at: stamp, updated_at: stamp,
  definition_digest: digest, execution_digest: digest, can_edit: true, reference_states: [],
  definition: { schema_version: 1, title: 'Saved graph', nodes: [
    { id: 'source', definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text: 'Source text' } },
    { id: 'draft', definition_id: 'draft_prepare', definition_version: 1, enabled: true, position: { x: 300, y: 0 }, parameters: {} },
    { id: 'review', definition_id: 'human_review', definition_version: 1, enabled: true, position: { x: 600, y: 0 }, parameters: {} },
  ], edges: [
    { id: 'source_draft', source_node_id: 'source', source_port: 'text', target_node_id: 'draft', target_port: 'text' },
    { id: 'draft_review', source_node_id: 'draft', source_port: 'draft', target_node_id: 'review', target_port: 'draft' },
  ], viewport: { x: 0, y: 0, zoom: 1 } } });
const preflight = (): StudioGraphPreflight => ({ ...owner, graph_id: 'graph', valid: true, executable: true, issues: [],
  execution_order: ['source', 'draft', 'review'], selected_closure: ['source', 'draft', 'review'], definition_digest: digest,
  preflight_digest: digest, expected_version: 4, target_node_ids: ['review'], model_called: false, external_calls: 0 });
const run = (fields: Partial<StudioGraphRun> = {}): StudioGraphRun => ({ ...owner, id: 'run_one', version: 7, graph_id: 'graph', graph_version: 4,
  status: 'QUEUED', current_node_id: null, node_states: { source: { status: 'PENDING', output: null, error: null }, draft: { status: 'PENDING', output: null, error: null }, review: { status: 'PENDING', output: null, error: null } },
  review: null, cache: { hits: 0, misses: 0, mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' }, created_at: stamp, updated_at: stamp,
  model_called: false, external_calls: 0, applied: false, stale: false, reviewed: false, timeout_seconds: 3600, deadline_at: '2026-10-09T14:00:00Z', ...fields });
const reviewRun = (fields: Partial<StudioGraphRun> = {}) => run({ status: 'WAITING_APPROVAL', current_node_id: 'review',
  review: { node_id: 'review', output_digest: outputDigest, draft: { text: 'Current reviewed candidate', origin: 'USER_SUPPLIED', direction: { note: 'Author direction' }, plan: [{ sequence: 1, beat: 'First beat' }] } }, ...fields });
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
const perform = <T,>(work: () => Promise<T>): Promise<T> => work();
type Props = ComponentProps<typeof GraphRunPanel>;
function setup(options: Partial<Omit<Props, 'client'>> = {}) {
  const client = { catalog: vi.fn(), list: vi.fn(), create: vi.fn(), get: vi.fn(), save: vi.fn(),
    modelCapabilities: vi.fn(), previewModel: vi.fn(), dispatchModel: vi.fn(), refreshModel: vi.fn(),
    preflight: vi.fn().mockResolvedValue(preflight()), runs: vi.fn().mockResolvedValue({ items: [run()] }),
    createRun: vi.fn().mockResolvedValue(run()), getRun: vi.fn().mockResolvedValue(run()), action: vi.fn().mockResolvedValue(run({ version: 8 })) };
  const props: Props = { client, graph: graph(), targetNodeIds: ['review'], dirty: false, busy: false, canMutate: true, canReview: true,
    isCurrent: () => true, read: perform, mutate: perform, ...options };
  const rendered = render(<GraphRunPanel {...props} />);
  return { ...rendered, client, props, rerender: (next: Partial<Props>) => rendered.rerender(<GraphRunPanel {...props} {...next} />) };
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const acknowledgePreflight = () => fireEvent.click(screen.getByRole('checkbox', { name: '已核对当前图版本、节点范围与本地处理边界' }));
const acknowledgeOutput = () => fireEvent.click(screen.getByRole('checkbox', { name: '已阅读本次输出并核对当前审核摘要' }));
async function inspect() { click('核对运行范围'); await screen.findByRole('region', { name: '运行预检' }); }
async function selectRun() {
  click('读取运行记录');
  fireEvent.change(await screen.findByRole('combobox', { name: '已保存运行' }), { target: { value: 'run_one' } });
  await screen.findByRole('region', { name: '当前创作图运行' });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('explicit graph preflight and local run creation', () => {
  it('does not read, execute or create automatically and requires a saved graph', () => {
    const { client } = setup({ graph: undefined });
    expect(button('核对运行范围').disabled).toBe(true); expect(button('读取运行记录').disabled).toBe(true);
    expect(client.preflight).not.toHaveBeenCalled(); expect(client.createRun).not.toHaveBeenCalled(); expect(client.action).not.toHaveBeenCalled();
  });

  it('requires explicit review of exact graph version, selection and preflight digest before creating', async () => {
    const { client } = setup(); await inspect();
    expect(client.preflight).toHaveBeenCalledWith('graph', { expected_version: 4, target_node_ids: ['review'] });
    expect(button('创建本地运行').disabled).toBe(true); acknowledgePreflight(); click('创建本地运行');
    await screen.findByRole('region', { name: '当前创作图运行' });
    expect(client.createRun).toHaveBeenCalledWith('graph', { expected_graph_version: 4, reviewed_preflight_digest: digest, target_node_ids: ['review'], request_id: expect.stringMatching(/^run_[a-f0-9]+$/) });
    expect(client.action).not.toHaveBeenCalled(); expect(screen.getByText('运行记录已建立。尚未自动执行节点。')).toBeTruthy();
  });

  it('does not treat a blocker or write permission absence as approval to create', async () => {
    const { client } = setup({ canMutate: false });
    client.preflight.mockResolvedValue({ ...preflight(), executable: false, issues: [{ code: 'CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED', node_id: 'asset' }] });
    await inspect(); expect(screen.getByText(/CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED/)).toBeTruthy();
    expect((screen.getByRole('checkbox', { name: '已核对当前图版本、节点范围与本地处理边界' }) as HTMLInputElement).disabled).toBe(true);
    expect(button('创建本地运行').disabled).toBe(true); expect(client.createRun).not.toHaveBeenCalled();
  });

  it('invalidates reviewed preflight when the selected target changes or the draft becomes dirty', async () => {
    const { client, rerender } = setup(); await inspect(); acknowledgePreflight();
    rerender({ targetNodeIds: ['source'] }); expect(screen.queryByRole('region', { name: '运行预检' })).toBeNull();
    rerender({ dirty: true }); expect(button('核对运行范围').disabled).toBe(true); expect(client.createRun).not.toHaveBeenCalled();
  });

  it('reuses the exact request ID only when explicitly retrying an uncertain creation', async () => {
    const { client } = setup(); client.createRun.mockRejectedValueOnce(new ApiError({ status: 0, code: 'STUDIO_NETWORK_FAILED', message: 'Connection lost.' })).mockResolvedValueOnce(run());
    await inspect(); acknowledgePreflight(); click('创建本地运行');
    await screen.findByRole('button', { name: '使用同一请求重试创建运行' });
    expect(client.createRun).toHaveBeenCalledTimes(1); click('使用同一请求重试创建运行');
    await screen.findByRole('region', { name: '当前创作图运行' });
    expect(client.createRun).toHaveBeenCalledTimes(2); expect(client.createRun.mock.calls[1]).toEqual(client.createRun.mock.calls[0]);
  });

  it('allocates a fresh request for a second explicitly reviewed creation after confirmed success', async () => {
    const { client } = setup(); await inspect(); acknowledgePreflight(); click('创建本地运行');
    await screen.findByRole('region', { name: '当前创作图运行' }); acknowledgePreflight(); click('创建本地运行');
    await waitFor(() => expect(client.createRun).toHaveBeenCalledTimes(2));
    expect(client.createRun.mock.calls[1][1].request_id).not.toBe(client.createRun.mock.calls[0][1].request_id);
  });
});

describe('run actions and independent review authority', () => {
  it.each(['approve', 'reject'] as const)('requires reading the displayed output before %s and sends the exact digest, node and CAS', async action => {
    const { client } = setup({ canMutate: false, canReview: true });
    client.runs.mockResolvedValue({ items: [reviewRun()] }); client.getRun.mockResolvedValue(reviewRun());
    client.action.mockResolvedValue(run({ version: 8, status: action === 'approve' ? 'SUCCEEDED' : 'REJECTED', reviewed: action === 'approve' }));
    await selectRun(); expect(screen.getByText('Current reviewed candidate')).toBeTruthy();
    expect(screen.getByText('导演备注：Author direction')).toBeTruthy(); expect(screen.getByText('First beat')).toBeTruthy();
    const label = action === 'approve' ? '批准节点输出' : '驳回节点输出'; expect(button(label).disabled).toBe(true);
    fireEvent.change(screen.getByRole('textbox', { name: '运行备注' }), { target: { value: 'Checked exact candidate' } });
    acknowledgeOutput(); click(label);
    await waitFor(() => expect(client.action).toHaveBeenCalledOnce());
    expect(client.action).toHaveBeenCalledWith('run_one', action, { expected_version: 7, node_id: 'review', reviewed_output_digest: outputDigest, note: 'Checked exact candidate' });
    expect(client.createRun).not.toHaveBeenCalled();
  });

  it('does not infer review permission from mutation authority', async () => {
    const { client } = setup({ canMutate: true, canReview: false }); client.getRun.mockResolvedValue(reviewRun());
    await selectRun(); expect(button('批准节点输出').disabled).toBe(true); expect(button('驳回节点输出').disabled).toBe(true);
    expect((screen.getByRole('checkbox', { name: '已阅读本次输出并核对当前审核摘要' }) as HTMLInputElement).disabled).toBe(true);
    expect(client.action).not.toHaveBeenCalled();
  });

  it('sends local execution once despite repeated clicks and uses the selected run CAS', async () => {
    const pending = deferred<StudioGraphRun>(), { client } = setup(); client.action.mockReturnValue(pending.promise);
    await selectRun(); click('执行本地节点'); click('执行本地节点');
    expect(client.action).toHaveBeenCalledTimes(1); expect(client.action).toHaveBeenCalledWith('run_one', 'execute', { expected_version: 7, note: '' });
    await act(async () => pending.resolve(reviewRun({ version: 8 })));
    expect(screen.getByRole('region', { name: '节点输出审核' })).toBeTruthy();
  });

  it('does not offer execute for an already RUNNING record', async () => {
    const { client } = setup(); client.getRun.mockResolvedValue(run({ status: 'RUNNING' }));
    await selectRun(); expect(button('执行本地节点').disabled).toBe(true); expect(button('暂停运行').disabled).toBe(false);
  });

  it('locks all run mutations while the graph is dirty', async () => {
    const { client, rerender } = setup(); client.getRun.mockResolvedValue(reviewRun()); await selectRun(); acknowledgeOutput();
    rerender({ dirty: true });
    for (const name of ['批准节点输出', '驳回节点输出', '暂停运行', '取消运行']) expect(button(name).disabled).toBe(true);
    expect(client.action).not.toHaveBeenCalled();
  });

  it('hides stale review material and permits only cancellation among mutations', async () => {
    const { client } = setup(); client.getRun.mockResolvedValue(reviewRun({ stale: true })); await selectRun();
    expect(screen.queryByText('Current reviewed candidate')).toBeNull(); expect(screen.queryByRole('region', { name: '节点输出审核' })).toBeNull();
    for (const name of ['执行本地节点', '暂停运行', '恢复运行']) expect(button(name).disabled).toBe(true);
    expect(button('取消运行').disabled).toBe(false); click('取消运行');
    await waitFor(() => expect(client.action).toHaveBeenCalledWith('run_one', 'cancel', { expected_version: 7, note: '' }));
  });

  it('does not repeat a conflicted action and requires a fresh read before proceeding', async () => {
    const { client } = setup(); client.action.mockRejectedValueOnce(new ApiError({ status: 409, code: 'VERSION_CONFLICT', message: 'Version changed.' }));
    await selectRun(); click('执行本地节点'); await screen.findByText('版本或回执不确定。请先重新读取运行，不会自动重复动作。');
    expect(client.action).toHaveBeenCalledOnce(); expect(button('执行本地节点').disabled).toBe(true); expect(button('暂停运行').disabled).toBe(true);
    client.getRun.mockResolvedValue(run({ version: 9 })); click('重新读取当前运行');
    await waitFor(() => expect(button('执行本地节点').disabled).toBe(false));
    client.action.mockResolvedValue(run({ version: 10 })); click('执行本地节点');
    await waitFor(() => expect(client.action).toHaveBeenLastCalledWith('run_one', 'execute', { expected_version: 9, note: '' }));
  });
});

describe('late run and preflight response fences', () => {
  it('does not let older list completions erase a created run or roll back an action result', async () => {
    const beforeCreate = deferred<{ items: StudioGraphRun[] }>(), beforeAction = deferred<{ items: StudioGraphRun[] }>();
    const { client } = setup(); client.runs.mockReturnValueOnce(beforeCreate.promise).mockReturnValueOnce(beforeAction.promise);
    await inspect(); acknowledgePreflight(); click('读取运行记录'); click('创建本地运行');
    await screen.findByRole('region', { name: '当前创作图运行' });
    expect(screen.queryByText('正在读取原工作流信息…')).toBeNull();
    await act(async () => beforeCreate.resolve({ items: [] }));
    expect(screen.getByRole('option', { name: /run_one.*v7/ })).toBeTruthy();

    client.action.mockResolvedValue(reviewRun({ version: 8 })); click('读取运行记录'); click('执行本地节点');
    await screen.findByRole('region', { name: '节点输出审核' });
    expect(screen.queryByText('正在读取原工作流信息…')).toBeNull();
    await act(async () => beforeAction.resolve({ items: [run()] }));
    expect(screen.getByRole('option', { name: /run_one.*v8/ })).toBeTruthy();
    expect(screen.queryByRole('option', { name: /run_one.*v7/ })).toBeNull();
    expect(client.createRun).toHaveBeenCalledOnce(); expect(client.action).toHaveBeenCalledOnce();
  });

  it('does not render a preflight that arrives after its scope is no longer current', async () => {
    let current = true;
    const pending = deferred<StudioGraphPreflight>(), { client } = setup({ isCurrent: () => current });
    client.preflight.mockReturnValue(pending.promise); click('核对运行范围'); current = false;
    await act(async () => pending.resolve(preflight()));
    expect(screen.queryByRole('region', { name: '运行预检' })).toBeNull(); expect(client.createRun).not.toHaveBeenCalled();
  });

  it('drops a preflight after its target selection changes', async () => {
    const pending = deferred<StudioGraphPreflight>(), { client, rerender } = setup(); client.preflight.mockReturnValue(pending.promise);
    click('核对运行范围'); rerender({ targetNodeIds: ['source'] });
    await act(async () => pending.resolve(preflight())); expect(screen.queryByRole('region', { name: '运行预检' })).toBeNull();
  });

  it('drops an older selected run when a newer selection finishes first', async () => {
    const first = deferred<StudioGraphRun>(), second = deferred<StudioGraphRun>(), { client } = setup();
    client.runs.mockResolvedValue({ items: [run(), run({ id: 'run_two' })] }); client.getRun.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    click('读取运行记录'); const select = await screen.findByRole('combobox', { name: '已保存运行' });
    fireEvent.change(select, { target: { value: 'run_one' } }); fireEvent.change(select, { target: { value: 'run_two' } });
    await act(async () => second.resolve(run({ id: 'run_two', version: 9 })));
    await act(async () => first.resolve(reviewRun()));
    const panel = screen.getByRole('region', { name: '当前创作图运行' }); expect(within(panel).getByText('运行 run_two · v9 · 图 v4')).toBeTruthy();
    expect(screen.queryByText('Current reviewed candidate')).toBeNull();
  });

  it('cannot restore an old run after the graph version changes or the scope expires', async () => {
    let current = true;
    const pending = deferred<StudioGraphRun>(), { client, rerender } = setup({ isCurrent: () => current }); client.getRun.mockReturnValue(pending.promise);
    click('读取运行记录'); fireEvent.change(await screen.findByRole('combobox', { name: '已保存运行' }), { target: { value: 'run_one' } });
    current = false; rerender({ graph: { ...graph(), version: 5 } });
    await act(async () => pending.resolve(reviewRun()));
    expect(screen.queryByRole('region', { name: '当前创作图运行' })).toBeNull(); expect(screen.queryByText('Current reviewed candidate')).toBeNull();
  });
});
