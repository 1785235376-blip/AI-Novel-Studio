// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MediaPanel } from './MediaPanel';
import { ModelBenchmarkPanel } from './ModelBenchmarkPanel';
import type { ExperimentalClient, Row } from './api';
import type { BrokerApi, BrokerRoute } from './modelBrokerClient';

const adapter = { adapter_id: 'registered-image:fixture', family: 'A1111 fixture', modality: 'IMAGE', runnable: true, local: true, state: 'CONTRACT_VERIFIED' };
const brief = { id: 'brief', version: 1, kind: 'COVER', title: 'Fixture cover' };
const task = { id: 'task', version: 1, status: 'QUEUED', operation: 'cover_generation', adapter_definition: adapter, registration_identity: { model_digest: 'a'.repeat(64) } };
const quote = { id: 'quote', version: 1, ready: true, broker_decision_id: 'quote', broker_decision_version: 1, cost: { state: 'ESTIMATE', estimate_microusd: 23 }, parameters: { width: 512, height: 512, steps: 20, seed: 8 }, blockers: [] };
function mediaClient(tasks: Row[] = []) {
  return { get: vi.fn(async (path: string) => ({ items: path.endsWith('/adapters') ? [adapter] : path.endsWith('/cover-briefs') ? [brief] : path.endsWith('/tasks') ? tasks : [] })),
    post: vi.fn(async (path: string) => path.endsWith('/preflight') ? quote : task), blob: vi.fn() } as unknown as ExperimentalClient;
}
afterEach(() => cleanup());

it('selects a registered original image route and queues exactly one seeded task without inference', async () => {
  const api = mediaClient(); render(<MediaPanel client={api} />);
  await screen.findByRole('option', { name: adapter.family });
  fireEvent.change(screen.getByLabelText('图像工作流路线'), { target: { value: adapter.adapter_id } });
  fireEvent.change(screen.getByLabelText('本地图像 seed'), { target: { value: '8' } });
  await waitFor(() => expect(screen.getByRole('button', { name: '创建本地图像任务' }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '创建本地图像任务' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/media/tasks', { brief_id: 'brief', expected_brief_version: 1, adapter_id: adapter.adapter_id, candidate_count: 1, parameters: { seed: 8 } }));
  expect(vi.mocked(api.post).mock.calls).toHaveLength(1);
});

it('requires a fresh quote before real-local execution and keeps cancellation available', async () => {
  const api = mediaClient([task]); let finish: (result: unknown) => void = () => {};
  vi.mocked(api.post).mockImplementation(async path => path.endsWith('/execute') ? new Promise(resolve => { finish = resolve; }) : path.endsWith('/preflight') ? quote : { ...task, status: 'CANCELLED' });
  render(<MediaPanel client={api} />);
  fireEvent.click(await screen.findByRole('button', { name: '检查本地图像路线与费用' }));
  expect(await screen.findByText(/23 µUSD/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '按预检执行本地图像任务' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/media/tasks/task/execute', { expected_version: 1, broker_decision_id: 'quote', broker_decision_version: 1 }));
  const cancel = screen.getByRole('button', { name: '取消本地图像任务' });
  expect(cancel.hasAttribute('disabled')).toBe(false); fireEvent.click(cancel);
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/media/tasks/task/cancel', { expected_version: 1 }));
  finish({ ...task, status: 'CANCELLED' });
});

it('discards a late quote after a changed client scope', async () => {
  const first = mediaClient([task]); let finish: (result: unknown) => void = () => {};
  vi.mocked(first.post).mockImplementation(async () => new Promise(resolve => { finish = resolve; }));
  const view = render(<MediaPanel client={first} />);
  fireEvent.click(await screen.findByRole('button', { name: '检查本地图像路线与费用' }));
  view.rerender(<MediaPanel client={mediaClient([task])} />);
  finish(quote);
  await waitFor(() => expect(screen.queryByRole('button', { name: '按预检执行本地图像任务' })).toBeNull());
});

it('filters benchmark choices by saved image capability and invalidates the previous text choice', async () => {
  const imageSet = { id: 'image-set', version: 1, title: 'Image set', cases: [{ title: 'image', kind: 'IMAGE_WORKFLOW', prompt: 'fixture', rule: 'NONEMPTY', expected: [] }], repetitions: 1 };
  const textSet = { ...imageSet, id: 'text-set', title: 'Text set', cases: [{ ...imageSet.cases[0], kind: 'SHORT_REVIEW' }] };
  const text = { route_id: 'text-route', capability: 'TEXT', display_name: 'Text fixture', available: true, cloud: false } as BrokerRoute;
  const image = { ...text, route_id: 'image-route', capability: 'IMAGE', display_name: 'Registered image fixture' };
  const api = { benchmarks: vi.fn(async () => ({ sets: [textSet, imageSet], runs: [], evidence: [] })), startBenchmark: vi.fn(async () => ({})) } as unknown as BrokerApi;
  render(<ModelBenchmarkPanel api={api} routes={[text, image]} />);
  await screen.findByRole('option', { name: 'Text set · v1' });
  fireEvent.change(screen.getByLabelText('待运行任务集'), { target: { value: 'text-set' } });
  fireEvent.change(screen.getByLabelText('本次评测的本地模型路线'), { target: { value: 'text-route' } });
  fireEvent.change(screen.getByLabelText('待运行任务集'), { target: { value: 'image-set' } });
  expect(screen.queryByRole('option', { name: 'Text fixture' })).toBeNull();
  expect(screen.getByRole('button', { name: '建立有界评测运行' }).hasAttribute('disabled')).toBe(true);
  fireEvent.change(screen.getByLabelText('本次评测的本地模型路线'), { target: { value: 'image-route' } });
  fireEvent.click(screen.getByRole('button', { name: '建立有界评测运行' }));
  await waitFor(() => expect(api.startBenchmark).toHaveBeenCalledWith(imageSet, 'image-route', expect.any(String)));
});
