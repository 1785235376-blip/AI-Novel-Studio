// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { ExperimentalClient } from './api';
import { ChangeImpactPanel } from './ChangeImpactPanel';

const source = { kind: 'CHAPTER', id: 'chapter', label: 'Changed chapter', binding: { version: 2, digest: 'digest' } };
const node = { key: 'MEDIA_TASK:old-task', kind: 'MEDIA_TASK', id: 'old-task', label: 'Related cover', version: 3, status: 'SUCCEEDED', feature: 'cover_storyboard_generation', stale: true, locked: false, lock_version: 0, refresh_candidate: true, refresh_reason: null, evidence: [{ key: 'CHAPTER:chapter', label: 'Changed chapter', state: 'STALE' }] };
const plan = { id: 'preflight', version: 1, preflight_digest: 'a'.repeat(64), ready: true, maximum_candidates: 1, items: [{ key: node.key, label: node.label, blockers: [] }], cost: { state: 'KNOWN_SYNTHETIC_ZERO', currency: 'USD', estimate_microusd: 0 }, verification: 'SYNTHETIC_PROTOCOL_ONLY' };
const refresh = { id: 'refresh', version: 1, node_key: node.key, task_id: 'new-task', task_version: 1, status: 'QUEUED', source_current: true, outputs: [], recovery: null };
function client() {
  return { get: vi.fn(async (path: string) => path === '/change-impact/sources' ? { items: [source, { ...source, id: 'other', label: 'Another chapter' }] } : { items: [] }),
    post: vi.fn(async (path: string) => path.endsWith('/query') ? { source, items: [node], inferred: [], unrecorded_dependencies: 'UNKNOWN' } : path.endsWith('/preflights') ? plan : { items: [refresh] }),
    put: vi.fn(async () => ({ ...node, locked: true, lock_version: 1 })), blob: vi.fn() } as unknown as ExperimentalClient;
}
async function select() { fireEvent.change(await screen.findByLabelText('发生修改的来源'), { target: { value: 'CHAPTER:chapter' } }); await screen.findByRole('checkbox', { name: /选择更新 Related cover/ }); }
async function check() { fireEvent.click(screen.getByRole('checkbox', { name: /选择更新 Related cover/ })); fireEvent.click(screen.getByRole('button', { name: '预检选中的 1 项' })); await screen.findByRole('region', { name: '选择性更新预检' }); }
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('ChangeImpactPanel explicit scoped actions', () => {
  it('shows exact/unknown evidence and preflights only explicitly selected nodes, never auto executes', async () => {
    const api = client(); render(<ChangeImpactPanel client={api} />); await select();
    expect(screen.getByText(/模型推断影响：未运行/)).toBeTruthy();
    expect(screen.getByRole('button', { name: '预检选中的 0 项' }).hasAttribute('disabled')).toBe(true);
    await check();
    expect(api.post).toHaveBeenCalledWith('/change-impact/preflights', { source: { kind: 'CHAPTER', id: 'chapter' }, selected: [{ key: node.key, expected_version: 3 }] });
    fireEvent.click(screen.getByRole('button', { name: '仅准备这些选中更新' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/change-impact/preflights/preflight/prepare', expect.objectContaining({ preflight_digest: plan.preflight_digest, expected_version: 1, idempotency_key: expect.any(String) })));
    expect(vi.mocked(api.post).mock.calls.some(([path]) => path.endsWith('/execute'))).toBe(false);
  });
  it('persists versioned locks and refreshes without silently keeping stale selection', async () => {
    const api = client(); render(<ChangeImpactPanel client={api} />); await select(); await check();
    fireEvent.click(screen.getByRole('button', { name: '锁定满意成果' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith('/change-impact/locks', { key: node.key, expected_version: 3, expected_lock_version: 0, locked: true }));
    await waitFor(() => expect(screen.queryByRole('region', { name: '选择性更新预检' })).toBeNull());
    expect(screen.getByRole('button', { name: '预检选中的 0 项' }).hasAttribute('disabled')).toBe(true);
  });
  it('retains idempotency token for explicit retry after uncertain prepare', async () => {
    const api = client(); const original = api.post;
    api.post = vi.fn(async (path, body) => { if (path.endsWith('/prepare')) throw new Error('network'); return original(path, body); }) as ExperimentalClient['post'];
    render(<ChangeImpactPanel client={api} />); await select(); await check();
    fireEvent.click(screen.getByRole('button', { name: '仅准备这些选中更新' })); await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: '仅准备这些选中更新' }));
    await waitFor(() => expect(vi.mocked(api.post).mock.calls.filter(([path]) => path.endsWith('/prepare'))).toHaveLength(2));
    const calls = vi.mocked(api.post).mock.calls.filter(([path]) => path.endsWith('/prepare'));
    expect(calls[0][1]).toEqual(calls[1][1]);
  });
  it('blocks unsupported and locked selections, shows empty state and honest unsupported preflight', async () => {
    const api = client(); vi.mocked(api.post).mockImplementation(async () => ({ source, items: [{ ...node, locked: true, refresh_candidate: false, refresh_reason: 'LOCKED_OUTCOME' }] }));
    render(<ChangeImpactPanel client={api} />); await select();
    expect(screen.getByRole('checkbox').hasAttribute('disabled')).toBe(true);
    expect(screen.getByText('成果已锁定，请先明确解锁。')).toBeTruthy();
    cleanup();
    vi.mocked(api.post).mockResolvedValue({ source, items: [] }); render(<ChangeImpactPanel client={api} />);
    fireEvent.change(await screen.findByLabelText('发生修改的来源'), { target: { value: 'CHAPTER:chapter' } });
    expect(await screen.findByText('没有已记录的下游依赖')).toBeTruthy();
    cleanup();
    const available = client(); const normal = available.post;
    available.post = vi.fn(async (path, body) => path.endsWith('/preflights') ? { ...plan, ready: false, items: [{ ...plan.items[0], blockers: ['REGISTERED_LOCAL_IMAGE_EXECUTOR_REQUIRED'] }], cost: { ...plan.cost, estimate_microusd: null } } : normal(path, body)) as ExperimentalClient['post'];
    render(<ChangeImpactPanel client={available} />); await select(); await check();
    expect(screen.getByRole('button', { name: '仅准备这些选中更新' }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByText(/需要已启用的原本地图像 Adapter/)).toBeTruthy();
  });
  it('allows cancel while execute awaits completion, using latest task version', async () => {
    const api = client(); vi.mocked(api.get).mockImplementation(async path => path.endsWith('/sources') ? { items: [source] } : { items: [{ ...refresh, task_version: 2 }] });
    let finish: (value: unknown) => void = () => {};
    api.post = vi.fn(async path => path.endsWith('/execute') ? new Promise(resolve => { finish = resolve; }) : { ...refresh, status: 'CANCELLED' }) as ExperimentalClient['post'];
    render(<ChangeImpactPanel client={api} />);
    fireEvent.click(await screen.findByRole('button', { name: '执行此选中任务' }));
    fireEvent.click(screen.getByRole('button', { name: '取消此次更新' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/change-impact/refreshes/refresh/cancel', { expected_task_version: 2 }));
    finish(refresh);
  });
  it('unmount and authority change discard late private responses in StrictMode', async () => {
    const old = client(); let finish: (value: unknown) => void = () => {};
    old.post = vi.fn(async () => new Promise(resolve => { finish = resolve; })) as ExperimentalClient['post'];
    const rendered = render(<StrictMode><ChangeImpactPanel client={old} /></StrictMode>);
    fireEvent.change(await screen.findByLabelText('发生修改的来源'), { target: { value: 'CHAPTER:chapter' } });
    const fresh = client(); vi.mocked(fresh.get).mockResolvedValue({ items: [] });
    rendered.rerender(<StrictMode><ChangeImpactPanel client={fresh} /></StrictMode>);
    finish({ source, items: [{ ...node, label: 'PRIVATE_OLD_SCOPE' }] });
    await waitFor(() => expect(screen.queryByText(/PRIVATE_OLD_SCOPE/)).toBeNull());
    expect(screen.queryByRole('region', { name: '修改影响清单' })).toBeNull();
    rendered.unmount();
  });
  it('scope changes while preflight pending never resurrect its action', async () => {
    const api = client(), normal = api.post; let finish: (value: unknown) => void = () => {};
    api.post = vi.fn(async (path, body) => path.endsWith('/preflights') ? new Promise(resolve => { finish = resolve; }) : normal(path, body)) as ExperimentalClient['post'];
    render(<ChangeImpactPanel client={api} />); await select();
    fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: '预检选中的 1 项' }));
    fireEvent.change(screen.getByLabelText('发生修改的来源'), { target: { value: 'CHAPTER:other' } });
    finish(plan);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Another chapter 的已记录依赖' })).toBeTruthy());
    expect(screen.queryByRole('button', { name: '仅准备这些选中更新' })).toBeNull();
  });
  it('read-only calls nothing; permission failure is actionable and retry stays explicit', async () => {
    const api = client(); const rendered = render(<ChangeImpactPanel client={api} readOnly />);
    expect(api.get).not.toHaveBeenCalled(); expect(screen.getByText(/只读身份不能查看/)).toBeTruthy();
    rendered.unmount();
    vi.mocked(api.get).mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: '当前身份没有此操作权限。' }));
    render(<ChangeImpactPanel client={api} />); await screen.findAllByRole('alert');
    expect(screen.getByText(/当前范围没有作者编辑权限/)).toBeTruthy();
    expect(screen.getByRole('button', { name: '刷新可访问来源' })).toBeTruthy();
  });
});
