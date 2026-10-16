// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { ExperimentalClient } from './api';
import { ProductionLineagePanel } from './ProductionLineagePanel';

const hash = 'a'.repeat(64);
const asset = { id: 'asset-child', label: 'Derived image', version: 2, kind: 'image', digest: hash, deleted: false, integrity: 'VERIFIED', origin: 'DERIVED_PROCESSING', license: { label: 'CC0 declaration', source: 'Author statement', note: '' }, operation: 'Crop', parents: [{ id: 'parent', label: 'Original image', version: 1, digest: hash, state: 'CURRENT' }], sources: [], stale: false, impact: { assets: [], usages: [{ id: 'brief', kind: 'MEDIA_BRIEF', label: 'COVER', version: 1 }], other_dependencies: 'UNKNOWN' } };
const parent = { ...asset, id: 'parent', label: 'Original image', version: 1, origin: 'ORIGINAL_INPUT', parents: [] };
const manifest = { id: 'manifest', version: 1, status: 'RECORDED', created_at: '2026-10-05T10:00:00Z', task_id: 'original-task', task_version: 3, operation: 'cover_generation', input_digest: hash, manifest_digest: hash, adapter_id: 'mock-image-v1', model_id: 'mock-png-v1', parameters: { candidate_count: 2 }, seed: { value: null }, verification: 'MOCK_ONLY', environment: { app_version: '0.7.0', runtime: { python: '3.11', zlib: '1.2' }, adapter_version: '1', adapter_digest: hash, workflow_version: 'r3-media-request-v1', workflow_digest: hash, model_digest: hash, deterministic: true }, outputs: [{ proposal_id: 'old-output', candidate_index: 0, digest: hash }], input_versions: [] };
const preflight = { manifest_id: 'manifest', manifest_version: 1, ready: true, blockers: [], preflight_digest: hash, broker_decision_id: null, broker_decision_version: null, verification: 'SYNTHETIC_PROTOCOL_ONLY', cost: { state: 'KNOWN_SYNTHETIC_ZERO', currency: 'USD', estimate_microusd: 0 }, states: { traceable: true, rebuildable: true, replayable: true, deterministic: true, byte_equal: null } };
const replay = { id: 'replay', version: 1, manifest_id: 'manifest', task_id: 'new-task', task_version: 1, status: 'QUEUED', byte_equal: null, outputs: [], recovery: null, recoverable: false, broker_required: false, reservation_id: null };
function client() {
  return { get: vi.fn(async (path: string) => {
    if (path === '/production/assets') return { items: [parent, asset] };
    if (path.startsWith('/production/assets/')) return path.endsWith('/parent') ? parent : asset;
    if (path === '/production/manifests') return { items: [manifest] };
    if (path === '/media/tasks') return { items: [{ id: 'original-task', version: 3, status: 'SUCCEEDED', operation: 'cover_generation' }] };
    if (path === '/production/replays') return { items: [replay] };
    if (path.endsWith('/export')) return { schema: 'production-public-manifest-v2', manifest_digest: hash, redaction: { raw_prompts: false } };
    throw new Error(path);
  }), post: vi.fn(async (path: string) => path.endsWith('/preflight') ? preflight : path.endsWith('/replay') ? replay : manifest), put: vi.fn(async () => asset), blob: vi.fn() } as unknown as ExperimentalClient;
}
async function openAsset() { fireEvent.click(await screen.findByRole('button', { name: 'Derived image · v2' })); await screen.findByRole('region', { name: '资产来源关系图' }); }
async function openManifest() { fireEvent.click(await screen.findByRole('button', { name: /清单 cover_generation/ })); await screen.findByRole('region', { name: '生产清单详情' }); }
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('ProductionLineagePanel real API actions', () => {
  it('shows relationship graph, known impact and saves explicit versioned declaration', async () => {
    const api = client(), navigate = vi.fn(); render(<ProductionLineagePanel client={api} onNavigate={navigate} />);
    await openAsset();
    expect(screen.getByRole('region', { name: '资产替换影响' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('许可使用备注'), { target: { value: 'Attribution required' } });
    fireEvent.click(screen.getByRole('button', { name: '保存来源声明' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith('/production/assets/asset-child/lineage', expect.objectContaining({ expected_version: 2, parent_asset_ids: ['parent'], license: expect.objectContaining({ note: 'Attribution required' }) })));
    expect(api.post).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole('button', { name: '查看媒体任务与审核' }));
    expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'cover_storyboard_generation', feature: 'cover_storyboard_generation' });
    expect(vi.mocked(api.get).mock.calls.some(([p]) => p === '/media/tasks')).toBe(false);
  });
  it('preserves draft after conflict and exposes explicit reload recovery', async () => {
    const api = client(); vi.mocked(api.put).mockRejectedValueOnce(new ApiError({ status: 409, code: 'EXPERIMENTAL_VERSION_CONFLICT', message: '版本冲突，草稿已保留' }));
    render(<ProductionLineagePanel client={api} />); await openAsset();
    fireEvent.change(screen.getByLabelText('许可声明'), { target: { value: 'My retained declaration' } });
    fireEvent.click(screen.getByRole('button', { name: '保存来源声明' }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect((screen.getByLabelText('许可声明') as HTMLInputElement).value).toBe('My retained declaration');
    expect(screen.getByRole('button', { name: '重新读取资产详情' })).toBeTruthy();
  });
  it('missing parent is a tombstone and cannot be silently edited into original', async () => {
    const api = client(), read = api.get;
    api.get = vi.fn(async (path: string) => path === '/production/assets/asset-child' ? { ...asset, parents: [{ state: 'UNAVAILABLE', label: '来源不可用或无权访问' }], stale: true } : read(path)) as ExperimentalClient['get'];
    render(<ProductionLineagePanel client={api} />); await openAsset();
    expect(screen.getByText(/当前资产或父资产不可用/)).toBeTruthy();
    expect((screen.getByRole('button', { name: '保存来源声明' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: '查看父资产 Original image' })).toBeNull();
  });
  it('captures a selected completed media task, preflights, creates but never auto executes', async () => {
    const api = client(); render(<ProductionLineagePanel client={api} manifestsEnabled />);
    await screen.findByLabelText('已完成的媒体任务');
    fireEvent.change(screen.getByLabelText('已完成的媒体任务'), { target: { value: 'original-task' } });
    fireEvent.click(screen.getByRole('button', { name: '记录所选任务清单' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/production/manifests', { task_id: 'original-task', expected_task_version: 3 }));
    await screen.findByRole('button', { name: '检查重放条件' });
    fireEvent.click(screen.getByRole('button', { name: '检查重放条件' }));
    await screen.findByRole('region', { name: '重放预检' });
    expect(within(screen.getByRole('region', { name: '重放预检' })).getByText('输出逐字节一致：尚未比较')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '创建新的重放任务' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/production/manifests/manifest/replay', expect.objectContaining({ preflight_digest: hash, idempotency_key: expect.any(String) })));
    expect(vi.mocked(api.post).mock.calls.some(([p]) => p.endsWith('/execute'))).toBe(false);
  });
  it('keeps idempotency key on uncertain create and blocks known unavailable dependency', async () => {
    const api = client(); const normal = api.post;
    api.post = vi.fn(async (path: string, body: unknown) => { if (path.endsWith('/replay')) throw new Error('network'); return normal(path, body); }) as ExperimentalClient['post'];
    render(<ProductionLineagePanel client={api} manifestsEnabled />); await openManifest();
    fireEvent.click(screen.getByRole('button', { name: '检查重放条件' })); await screen.findByRole('region', { name: '重放预检' });
    fireEvent.click(screen.getByRole('button', { name: '创建新的重放任务' })); await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: '创建新的重放任务' }));
    await waitFor(() => expect(vi.mocked(api.post).mock.calls.filter(([p]) => p.endsWith('/replay'))).toHaveLength(2));
    const calls = vi.mocked(api.post).mock.calls.filter(([p]) => p.endsWith('/replay')); expect(calls[0][1]).toEqual(calls[1][1]);
  });
  it('exports only server redacted data as a file and never a raw request', async () => {
    const api = client(); const create = vi.fn().mockReturnValue('blob:redacted'), revoke = vi.fn();
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: create }); Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revoke });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    render(<ProductionLineagePanel client={api} manifestsEnabled />); await openManifest();
    fireEvent.click(screen.getByRole('button', { name: '下载脱敏生产清单' }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(api.get).toHaveBeenCalledWith('/production/manifests/manifest/export');
    expect(create.mock.calls[0][0].type).toBe('application/json'); expect(revoke).toHaveBeenCalledWith('blob:redacted');
  });
  it('allows cancellation during an in-flight replay using the latest existing task version', async () => {
    const api = client(); let finish: (value: unknown) => void = () => {};
    api.post = vi.fn(async (path: string) => path.endsWith('/execute') ? new Promise(resolve => { finish = resolve; }) : replay) as ExperimentalClient['post'];
    render(<ProductionLineagePanel client={api} manifestsEnabled />);
    fireEvent.click(await screen.findByRole('button', { name: '执行这次合成重放' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/production/replays/replay/execute', { expected_task_version: 1 }));
    fireEvent.click(screen.getByRole('button', { name: '取消重放' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/production/replays/replay/cancel', { expected_task_version: 1 }));
    finish(replay);
  });
  it('renders blockers distinctly from deterministic and equality claims', async () => {
    const api = client(); vi.mocked(api.post).mockResolvedValue({ ...preflight, ready: false, blockers: ['CONFIGURED_ADAPTER_REQUIRED'], states: { ...preflight.states, replayable: false, rebuildable: false } });
    render(<ProductionLineagePanel client={api} manifestsEnabled />); await openManifest();
    fireEvent.click(screen.getByRole('button', { name: '检查重放条件' })); await screen.findByText(/没有已配置的可执行 Adapter/);
    expect((screen.getByRole('button', { name: '创建新的重放任务' }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('switching authority clears private drafts and fences late preflight responses', async () => {
    const api = client(); let finish: (value: unknown) => void = () => {};
    api.post = vi.fn(() => new Promise(resolve => { finish = resolve; })) as ExperimentalClient['post'];
    const view = render(<ProductionLineagePanel client={api} manifestsEnabled />); await openManifest();
    fireEvent.click(screen.getByRole('button', { name: '检查重放条件' }));
    const next = client(); view.rerender(<ProductionLineagePanel client={next} manifestsEnabled />); finish(preflight);
    await waitFor(() => expect(screen.queryByRole('region', { name: '重放预检' })).toBeNull());
    expect(screen.queryByRole('region', { name: '生产清单详情' })).toBeNull();
  });

  it('does not download a late export after the originating authority is unmounted', async () => {
    const api = client(), read = api.get;
    let finish: (value: unknown) => void = () => {};
    api.get = vi.fn(async (path: string) => path.endsWith('/export') ? new Promise(resolve => { finish = resolve; }) : read(path)) as ExperimentalClient['get'];
    const create = vi.fn(); Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: create });
    const view = render(<ProductionLineagePanel client={api} manifestsEnabled />); await openManifest();
    fireEvent.click(screen.getByRole('button', { name: '下载脱敏生产清单' }));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/production/manifests/manifest/export'));
    view.rerender(<ProductionLineagePanel client={client()} manifestsEnabled />);
    finish({ schema: 'production-public-manifest-v2' });
    await waitFor(() => expect(screen.queryByRole('region', { name: '生产清单详情' })).toBeNull());
    expect(create).not.toHaveBeenCalled();
  });
  it('reopening reads existing replay result and links to review without approving', async () => {
    const api = client(), read = api.get, navigate = vi.fn();
    api.get = vi.fn(async (path: string) => path === '/production/replays' ? { items: [{ ...replay, status: 'SUCCEEDED', task_version: 3, byte_equal: true, outputs: [{ proposal_id: 'new', candidate_index: 0, digest: hash, status: 'PENDING_REVIEW' }] }] } : read(path)) as ExperimentalClient['get'];
    render(<ProductionLineagePanel client={api} manifestsEnabled onNavigate={navigate} />);
    const history = await screen.findByRole('region', { name: '重放历史' });
    expect(await within(history).findByText('输出逐字节一致：是')).toBeTruthy();
    fireEvent.click(within(history).getByRole('button', { name: '审核重放产物' }));
    expect(navigate).toHaveBeenCalled(); expect(api.post).not.toHaveBeenCalled();
  });
});
