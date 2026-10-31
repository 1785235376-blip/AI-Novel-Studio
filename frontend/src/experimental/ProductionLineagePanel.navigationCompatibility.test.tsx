// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

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
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const retainedClick = (node: HTMLElement) => (node as unknown as Record<string, { onClick: () => void }>)[Object.keys(node).find(key => key.startsWith('__reactProps'))!].onClick;
function readyClient(override: Record<string, unknown> = {}) {
  const api = client(), read = api.get;
  api.get = vi.fn(async (path: string) => path === '/production/replays'
    ? { items: [{ ...replay, status: 'SUCCEEDED', task_version: 3, byte_equal: true, outputs: [{ proposal_id: 'candidate', candidate_index: 0, digest: hash, status: 'PENDING_REVIEW' }], ...override }] }
    : read(path)) as ExperimentalClient['get'];
  return api;
}
const primary = () => screen.getByRole('button', { name: '审核重放产物' });

it('the pristine primary navigates to the exact original task once without approving or executing', async () => {
  const api = readyClient(), navigate = vi.fn();
  render(<ProductionLineagePanel client={api} manifestsEnabled onNavigate={navigate} />);
  const button = await screen.findByRole('button', { name: '审核重放产物' });
  const stale = retainedClick(button);
  act(() => { stale(); stale(); });
  expect(navigate).toHaveBeenCalledTimes(1);
  expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'new-task', feature: 'cover_storyboard_generation', task_authority: 'media' });
  expect(api.post).not.toHaveBeenCalled(); expect(api.put).not.toHaveBeenCalled();
});

it('retires a retained fast handler synchronously on asset entry and preserves a dirty declaration on cancellation', async () => {
  const api = readyClient(), navigate = vi.fn();
  render(<ProductionLineagePanel client={api} manifestsEnabled onNavigate={navigate} />);
  const stale = retainedClick(await screen.findByRole('button', { name: '审核重放产物' }));
  act(() => { fireEvent.click(screen.getByRole('button', { name: 'Derived image · v2' })); stale(); });
  expect(navigate).not.toHaveBeenCalled();
  fireEvent.change(await screen.findByLabelText('许可使用备注'), { target: { value: 'Keep my declaration' } });
  fireEvent.click(primary());
  expect(navigate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '留在此处' }));
  expect((screen.getByLabelText('许可使用备注') as HTMLTextAreaElement).value).toBe('Keep my declaration');
  expect(api.post).not.toHaveBeenCalled(); expect(api.put).not.toHaveBeenCalled();
});

it('opening and cancelling the exact action permanently retires pristine, even before a rerender', async () => {
  const api = readyClient(), navigate = vi.fn();
  render(<ProductionLineagePanel client={api} manifestsEnabled onNavigate={navigate} />);
  const stale = retainedClick(await screen.findByRole('button', { name: '审核重放产物' }));
  act(() => { fireEvent.click(screen.getByRole('button', { name: '核对确切重放任务' })); stale(); });
  expect(navigate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '留在此处' }));
  fireEvent.click(primary());
  expect(screen.getByRole('button', { name: '确认离开并审核重放产物' })).toBeTruthy();
  expect(navigate).not.toHaveBeenCalled(); expect(api.post).not.toHaveBeenCalled();
});

it.each(['preflight', 'submission'])('requires leave consent during a pending %s', async kind => {
  const api = readyClient(), navigate = vi.fn();
  let finish!: (value: unknown) => void;
  api.post = vi.fn(() => new Promise(resolve => { finish = resolve; })) as ExperimentalClient['post'];
  render(<ProductionLineagePanel client={api} manifestsEnabled onNavigate={navigate} />);
  await screen.findByRole('button', { name: '审核重放产物' });
  if (kind === 'preflight') {
    fireEvent.click(screen.getByRole('button', { name: /清单 cover_generation/ }));
    fireEvent.click(await screen.findByRole('button', { name: '检查重放条件' }));
  } else {
    fireEvent.change(screen.getByLabelText('已完成的媒体任务'), { target: { value: 'original-task' } });
    fireEvent.click(screen.getByRole('button', { name: '记录所选任务清单' }));
  }
  await waitFor(() => expect(finish).toBeTypeOf('function'));
  fireEvent.click(primary()); expect(navigate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '留在此处' }));
  await act(async () => finish(kind === 'preflight' ? preflight : manifest));
  expect(navigate).not.toHaveBeenCalled(); expect(api.post).toHaveBeenCalledTimes(1);
});

it.each(['task ABA', 'asset refresh', 'manifest refresh'])('cannot regain the fast path after %s', async mode => {
  const api = readyClient(), navigate = vi.fn();
  render(<ProductionLineagePanel client={api} manifestsEnabled onNavigate={navigate} />);
  await screen.findByRole('button', { name: '审核重放产物' });
  if (mode === 'task ABA') {
    fireEvent.change(screen.getByLabelText('已完成的媒体任务'), { target: { value: 'original-task' } });
    fireEvent.change(screen.getByLabelText('已完成的媒体任务'), { target: { value: '' } });
  } else fireEvent.click(screen.getByRole('button', { name: mode === 'asset refresh' ? '刷新资产列表' : '刷新清单与重放状态' }));
  fireEvent.click(await screen.findByRole('button', { name: '审核重放产物' }));
  expect(navigate).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: '确认离开并审核重放产物' })).toBeTruthy();
});

it.each(['', 'bad task', 'https://wrong.example/task'])('never navigates an invalid task identifier %s', async task_id => {
  const navigate = vi.fn(); render(<ProductionLineagePanel client={readyClient({ task_id })} manifestsEnabled onNavigate={navigate} />);
  const button = await screen.findByRole('button', { name: '审核重放产物' });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  act(() => retainedClick(button)());
  expect(navigate).not.toHaveBeenCalled();
});

it('withholds the primary without outputs and retires old authority handlers on replacement and unmount', async () => {
  const navigate = vi.fn(), first = readyClient();
  const view = render(<ProductionLineagePanel client={first} manifestsEnabled onNavigate={navigate} />);
  const stale = retainedClick(await screen.findByRole('button', { name: '审核重放产物' }));
  view.rerender(<ProductionLineagePanel client={readyClient({ outputs: [] })} manifestsEnabled onNavigate={navigate} />);
  act(() => stale());
  await screen.findByRole('button', { name: '核对确切重放任务' });
  expect(screen.queryByRole('button', { name: '审核重放产物' })).toBeNull();
  view.rerender(<ProductionLineagePanel client={readyClient()} manifestsEnabled onNavigate={navigate} />);
  const current = retainedClick(await screen.findByRole('button', { name: '审核重放产物' }));
  act(() => stale()); expect(navigate).not.toHaveBeenCalled();
  view.unmount(); act(() => { stale(); current(); });
  expect(navigate).not.toHaveBeenCalled();
});

it('task-selector focus retires pristine before any value change', async () => {
  const navigate = vi.fn(); render(<ProductionLineagePanel client={readyClient()} manifestsEnabled onNavigate={navigate} />);
  const stale = retainedClick(await screen.findByRole('button', { name: '审核重放产物' }));
  act(() => { fireEvent.focus(screen.getByLabelText('已完成的媒体任务')); stale(); });
  expect((screen.getByLabelText('已完成的媒体任务') as HTMLSelectElement).value).toBe('');
  expect(navigate).not.toHaveBeenCalled();
  fireEvent.click(primary());
  expect(screen.getByRole('button', { name: '确认离开并审核重放产物' })).toBeTruthy();
});

it.each(['execute', 'cancel'])('another replay %s synchronously retires a successful replay fast handler', async action => {
  const api = readyClient(), read = api.get, navigate = vi.fn();
  const completed = { ...replay, status: 'SUCCEEDED', outputs: [{ proposal_id: 'candidate', candidate_index: 0, digest: hash, status: 'PENDING_REVIEW' }] };
  const queued = { ...replay, id: 'queued-replay', task_id: 'pending-task' };
  api.get = vi.fn(async (path: string) => path === '/production/replays' ? { items: [completed, queued] } : read(path)) as ExperimentalClient['get'];
  let finish!: (value: unknown) => void;
  api.post = vi.fn(() => new Promise(resolve => { finish = resolve; })) as ExperimentalClient['post'];
  render(<ProductionLineagePanel client={api} manifestsEnabled onNavigate={navigate} />);
  const stale = retainedClick(await screen.findByRole('button', { name: '审核重放产物' }));
  act(() => { fireEvent.click(screen.getByRole('button', { name: action === 'execute' ? '执行这次合成重放' : '取消重放' })); stale(); });
  expect(navigate).not.toHaveBeenCalled();
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
  fireEvent.click(primary());
  expect(screen.getByRole('button', { name: '确认离开并审核重放产物' })).toBeTruthy();
  expect(navigate).not.toHaveBeenCalled();
  await act(async () => finish(queued));
});
