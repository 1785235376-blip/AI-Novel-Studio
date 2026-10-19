// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { ApiError } from '../api';
import { GraphRunPanel } from './GraphRunPanel';
import { useStudioGraphRunController } from './useStudioGraphRunController';
import { createStudioGraphClient, type StudioGraphTransport } from './studioGraphClient';
import type { StudioGraphPreflight, StudioGraphRecord, StudioGraphRun } from './studioGraphTypes';

const sha = 'a'.repeat(64), stamp = '2026-10-19T00:00:00Z';
const owner = { project_id: 'project', scope: { mode: 'local' as const, novel_id: 'project' } };
const graph = (): StudioGraphRecord => ({ ...owner, id: 'graph', version: 3, created_at: stamp, updated_at: stamp,
  definition_digest: sha, execution_digest: sha, can_edit: true, reference_states: [],
  definition: { schema_version: 1, title: 'Local failure', nodes: [
    { id: 'source', definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text: 'Author text' } },
    { id: 'draft', definition_id: 'draft_prepare', definition_version: 1, enabled: true, position: { x: 300, y: 0 }, parameters: {} },
  ], edges: [{ id: 'edge', source_node_id: 'source', source_port: 'text', target_node_id: 'draft', target_port: 'text' }],
  viewport: { x: 0, y: 0, zoom: 1 } } });
const failed = (): StudioGraphRun => ({ ...owner, id: 'failed', version: 7, graph_id: 'graph', graph_version: 3, status: 'FAILED',
  current_node_id: null, node_states: { source: { status: 'SUCCEEDED', output: null, error: null },
    draft: { status: 'FAILED', output: null, error: { code: 'CREATIVE_GRAPH_NODE_FAILED' } } },
  review: null, cache: { hits: 0, misses: 0, mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' }, created_at: stamp, updated_at: stamp,
  model_called: false, external_calls: 0, applied: false, stale: false, reviewed: false, timeout_seconds: 3600,
  deadline_at: '2026-10-19T01:00:00Z', attempt: 1, retry_of: null });
const queued = (): StudioGraphRun => ({ ...failed(), id: 'new-attempt', version: 1, retry_of: 'failed', attempt: 2, status: 'QUEUED',
  node_states: { source: { status: 'PENDING', output: null, error: null }, draft: { status: 'PENDING', output: null, error: null } } });
const flight = (): StudioGraphPreflight => ({ ...owner, graph_id: 'graph', valid: true, executable: true, issues: [],
  selected_closure: ['source', 'draft'], execution_order: ['source', 'draft'], target_node_ids: ['draft', 'source'],
  definition_digest: sha, preflight_digest: sha, expected_version: 3, model_called: false, external_calls: 0 });
const perform = <T,>(work: () => Promise<T>) => work();
type Props = ComponentProps<typeof GraphRunPanel>;
function controlledClient() {
  return { catalog: vi.fn(), list: vi.fn(), create: vi.fn(), get: vi.fn(), save: vi.fn(),
    modelCapabilities: vi.fn(), previewModel: vi.fn(), dispatchModel: vi.fn(), refreshModel: vi.fn(),
    preflight: vi.fn().mockResolvedValue(flight()), runs: vi.fn().mockResolvedValue({ items: [failed()] }),
    createRun: vi.fn(), getRun: vi.fn().mockResolvedValue(failed()), action: vi.fn(), retryLocal: vi.fn().mockResolvedValue(queued()) };
}
function setup(options: Partial<Props> = {}) {
  const client = controlledClient();
  const props: Props = { client, graph: graph(), targetNodeIds: ['draft'], dirty: false, busy: false, canMutate: true, canReview: true,
    isCurrent: () => true, read: perform, mutate: perform, requestedRunId: 'failed', ...options };
  const view = render(<GraphRunPanel {...props} />);
  return { client, props, rerender: (extra: Partial<Props>) => view.rerender(<GraphRunPanel {...props} {...extra} />) };
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const click = (name: string) => fireEvent.click(button(name));
async function prepare() {
  await waitFor(() => expect(button('核对失败运行重试').disabled).toBe(false));
  click('核对失败运行重试');
  await screen.findByRole('checkbox', { name: '已核对原失败运行，仅创建关联的新尝试' });
}
function confirm() { fireEvent.click(screen.getByRole('checkbox', { name: '已核对原失败运行，仅创建关联的新尝试' })); }
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('failed pure-local retry controls', () => {
  it('reads the original closure, requires fresh consent and only creates on an explicit click', async () => {
    const { client } = setup(); await prepare();
    expect(client.preflight).toHaveBeenCalledWith('graph', { expected_version: 3, target_node_ids: ['draft', 'source'] }, expect.any(AbortSignal));
    expect(client.retryLocal).not.toHaveBeenCalled(); expect(button('仅创建重试运行').disabled).toBe(true);
    confirm(); click('仅创建重试运行');
    await screen.findByText(/第 2 次尝试/);
    expect(client.retryLocal).toHaveBeenCalledWith('failed', { expected_version: 7, expected_graph_version: 3,
      reviewed_preflight_digest: sha, request_id: expect.stringMatching(/^retry_[a-f0-9]+$/) });
    expect(client.action).not.toHaveBeenCalled(); expect(client.createRun).not.toHaveBeenCalled();
  });
  it('excludes duplicate clicks before React rerenders', async () => {
    const { client } = setup(); await prepare(); confirm();
    let resolve!: (value: StudioGraphRun) => void;
    client.retryLocal.mockReturnValue(new Promise(yes => { resolve = yes; }));
    const submit = button('仅创建重试运行');
    act(() => { fireEvent.click(submit); fireEvent.click(submit); });
    expect(client.retryLocal).toHaveBeenCalledTimes(1);
    await act(async () => { resolve(queued()); });
  });
  it('retains the same key after a lost reply and rereading the failed source', async () => {
    const { client } = setup(); await prepare(); confirm();
    client.retryLocal.mockRejectedValueOnce(new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'lost reply' }));
    click('仅创建重试运行'); await screen.findByRole('button', { name: '使用同一请求核对重试创建' });
    const first = client.retryLocal.mock.calls[0];
    client.getRun.mockResolvedValue({ ...failed() });
    click('重新读取当前运行');
    await waitFor(() => expect(button('使用同一请求核对重试创建').disabled).toBe(false));
    click('使用同一请求核对重试创建'); await screen.findByText(/第 2 次尝试/);
    expect(client.retryLocal.mock.calls[1]).toEqual(first);
    expect(client.retryLocal).toHaveBeenCalledTimes(2); expect(client.action).not.toHaveBeenCalled();
  });
  it('retires UNKNOWN recovery callbacks after write permission ABA while preserving the same key', async () => {
    const client = controlledClient();
    const props: Props = { client, graph: graph(), targetNodeIds: ['draft'], dirty: false, busy: false,
      canMutate: true, canReview: true, isCurrent: () => true, read: perform, mutate: perform, requestedRunId: 'failed' };
    const hook = renderHook((value: Props) => useStudioGraphRunController(value), { initialProps: props });
    await waitFor(() => expect(hook.result.current.canPrepareRetry).toBe(true));
    await act(async () => { await hook.result.current.prepareRetry(); });
    act(() => hook.result.current.confirmRetry(true));
    client.retryLocal.mockRejectedValueOnce(new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'lost reply' }));
    await act(async () => { await hook.result.current.retryFailedLocal(); });
    expect(client.retryLocal).toHaveBeenCalledTimes(1);
    const first = client.retryLocal.mock.calls[0], oldRecovery = hook.result.current.retryFailedLocal;
    expect(hook.result.current.retryPlan?.uncertain).toBe(true);
    hook.rerender({ ...props, canMutate: false });
    await act(async () => { await oldRecovery(); });
    expect(client.retryLocal).toHaveBeenCalledTimes(1);
    hook.rerender(props);
    await act(async () => { await oldRecovery(); });
    expect(client.retryLocal).toHaveBeenCalledTimes(1);
    expect(hook.result.current.retryPlan?.uncertain).toBe(true);
    expect(hook.result.current.retryPlan?.request).toBe(first[1].request_id);
    // Only a fresh explicit callback may reconcile the original admission.
    await act(async () => { await hook.result.current.retryFailedLocal(); });
    expect(client.retryLocal).toHaveBeenCalledTimes(2);
    expect(client.retryLocal.mock.calls[1]).toEqual(first);
    expect(hook.result.current.selected?.id).toBe('new-attempt');
    expect(client.preflight).toHaveBeenCalledTimes(1);
    expect(client.action).not.toHaveBeenCalled(); expect(client.createRun).not.toHaveBeenCalled();
  });
  it('invalidates consent when unsaved input or write permission changes', async () => {
    const view = setup(); await prepare(); confirm(); view.rerender({ dirty: true });
    expect(screen.queryByRole('button', { name: '仅创建重试运行' })).toBeNull();
    view.rerender({ dirty: false, canMutate: false });
    expect(button('核对失败运行重试').disabled).toBe(true); expect(view.client.retryLocal).not.toHaveBeenCalled();
  });
  it('rejects a preflight that expands the old closure', async () => {
    const { client } = setup(); client.preflight.mockResolvedValue({ ...flight(), selected_closure: ['source', 'draft', 'extra'] });
    await waitFor(() => expect(button('核对失败运行重试').disabled).toBe(false)); click('核对失败运行重试');
    await screen.findByText(/运行回执与当前图或记录不一致/);
    expect(screen.queryByRole('button', { name: '仅创建重试运行' })).toBeNull(); expect(client.retryLocal).not.toHaveBeenCalled();
  });
  it.each(['QUEUED', 'RUNNING', 'PAUSED', 'WAITING_APPROVAL', 'SUCCEEDED', 'CANCELLED', 'REJECTED'] as const)('does not offer retry for %s', async status => {
    const { client } = setup(); client.getRun.mockResolvedValue({ ...failed(), status });
    // Force a distinct reload after the initial request has settled.
    await screen.findByRole('region', { name: '当前创作图运行' });
    click('重新读取当前运行'); await waitFor(() => expect(client.getRun).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole('region', { name: '失败本地运行重试' })).toBeNull());
    expect(client.retryLocal).not.toHaveBeenCalled();
  });
  it('blocks an old definition version without silently updating pins', async () => {
    setup({ graph: { ...graph(), version: 4 } });
    await screen.findByRole('region', { name: '当前创作图运行' });
    expect(button('核对失败运行重试').disabled).toBe(true);
  });
});

describe('checked retry client', () => {
  const body = { expected_version: 7, expected_graph_version: 3, reviewed_preflight_digest: sha, request_id: 'retry_exact' };
  function checkedClient(result: StudioGraphRun = queued()) {
    const json = vi.fn().mockResolvedValueOnce(failed()).mockResolvedValue(result);
    const client = createStudioGraphClient('project', {}, { json } as StudioGraphTransport);
    return { client, json };
  }
  it('binds the exact source and request key and retains attempt evidence', async () => {
    const { client, json } = checkedClient(); await client.getRun('failed');
    expect(await client.retryLocal('failed', body)).toEqual(queued());
    expect(json.mock.calls[1]).toEqual(['/api/projects/project/studio/graph-runs/failed/retry-local', 'POST', body, undefined, body.request_id]);
  });
  it.each([{ retry_of: 'wrong' }, { attempt: 1 }, { graph_id: 'other' }, { id: 'failed' }, { retry_of: null }])('rejects a misbound response %j', async patch => {
    const { client } = checkedClient({ ...queued(), ...patch }); await client.getRun('failed');
    await expect(client.retryLocal('failed', body)).rejects.toBeInstanceOf(ApiError);
  });
  it('rejects caller input edits before sending', async () => {
    const { client, json } = checkedClient(); await client.getRun('failed');
    expect(() => client.retryLocal('failed', { ...body, target_node_ids: ['other'] } as typeof body)).toThrow(ApiError);
    expect(json).toHaveBeenCalledTimes(1);
  });
});
