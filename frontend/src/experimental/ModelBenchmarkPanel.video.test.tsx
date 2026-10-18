// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ModelBenchmarkPanel } from './ModelBenchmarkPanel';
import { experimentalClient, type Row } from './api';
import { modelBrokerClient, type BenchmarkStatus, type BrokerApi, type BrokerRoute } from './modelBrokerClient';

const enabled = 'ONE_REGISTERED_LOCAL_T2V_THROUGH_ORIGINAL_STUDIO_REVIEW';
const digest = 'a'.repeat(64);
const reviewLabel = '我已核对原始请求、模型、参数与费用，仅授权生成这一个私有视频样本';
const executeLabel = '按已核对请求执行一个视频样本';
const videoSet: Row = { id: 'video-set', version: 2, title: 'Video fixture', cases: [{ title: 'Video sample', kind: 'VIDEO_WORKFLOW', prompt: 'Synthetic moving square', rule: 'NONEMPTY', expected: [] }], repetitions: 1, max_output_tokens: 128, timeout_seconds: 30, max_cost_microusd: 0 };
const textSet: Row = { ...videoSet, id: 'text-set', title: 'Text fixture', cases: [{ ...videoSet.cases[0], kind: 'SHORT_REVIEW' }] };
const videoRoute = { route_id: 'local-video', capability: 'VIDEO', display_name: 'Registered local T2V', available: true, cloud: false } as BrokerRoute;
const textRoute = { ...videoRoute, route_id: 'local-text', capability: 'TEXT', display_name: 'Local text' };
const productionPreview = { contract: 'studio-production-preview/1', preview_digest: digest, operation_id: 'm7.video.t2v', provider: { provider_id: 'registered-local-video', model_id: 'video-model', local: true }, execution_recipe: { parameters: { width: 256, height: 256, duration_seconds: 1, frame_rate: 8, seed: 7 }, timing: { frames: 9, frame_rate: 8, duration_ms: 1125 } }, command: { prompt: 'Synthetic moving square' } };
const ready = (preview = false): Row => ({ id: 'video-run', version: preview ? 2 : 1, capability: 'VIDEO', status: 'READY', total: 1, completed: 0, results: [], video_sample: preview ? { index: 0, status: 'PREVIEWED', preview: { production_preview: productionPreview, preview_digest: digest } } : null });
const running = (status = 'REMOTE_RUNNING'): Row => ({ ...ready(true), version: 3, status: 'RUNNING', video_sample: { ...ready(true).video_sample, status, job: { id: 'original-job', version: 4, status, request_digest: 'b'.repeat(64), output_candidate: null } } });
function fixture(runs: Row[] = [], sets: Row[] = [videoSet]): { api: BrokerApi; state: BenchmarkStatus } {
  const state: BenchmarkStatus = { sets, runs, evidence: [], comparisons: [], video_execution: enabled };
  const api = {
    benchmarks: vi.fn(async () => structuredClone(state)), capabilityProfiles: vi.fn(async () => ({ items: [] })),
    createSet: vi.fn(async (value: Record<string, unknown>) => ({ ...videoSet, ...value })), startBenchmark: vi.fn(async () => { state.runs = [ready()]; return ready(); }),
    benchmarkAction: vi.fn(async (run: Row, action: string) => {
      const next = action === 'preview' ? { ...run, version: run.version + 1, video_sample: ready(true).video_sample } : action === 'cancel' ? { ...run, status: 'CANCELLED', version: run.version + 1 } : { ...run, version: run.version + 1 };
      state.runs = [next]; return next;
    }),
    executeBenchmark: vi.fn(async () => { const next = running(); state.runs = [next]; return next; }),
    benchmarkVideoCandidate: vi.fn(async () => new Blob(['private video'], { type: 'video/webm' })),
  } as unknown as BrokerApi;
  return { api, state };
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('bounded local T2V benchmark', () => {
  it('keeps mount and run creation generation-free and filters local available VIDEO routes', async () => {
    const { api } = fixture([], [textSet, videoSet, { ...videoSet, id: 'mixed', title: 'Mixed fixture', cases: [...videoSet.cases, ...textSet.cases] }]);
    render(<ModelBenchmarkPanel api={api} routes={[textRoute, videoRoute, { ...videoRoute, route_id: 'cloud', display_name: 'Cloud video', cloud: true }, { ...videoRoute, route_id: 'offline', display_name: 'Offline video', available: false }]} />);
    await screen.findByRole('option', { name: 'Video fixture · v2' });
    expect(api.startBenchmark).not.toHaveBeenCalled(); expect(api.benchmarkAction).not.toHaveBeenCalled(); expect(api.executeBenchmark).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('待运行任务集'), { target: { value: textSet.id } });
    fireEvent.change(screen.getByLabelText('本次评测的本地模型路线'), { target: { value: textRoute.route_id } });
    fireEvent.change(screen.getByLabelText('待运行任务集'), { target: { value: videoSet.id } });
    expect(screen.queryByRole('option', { name: 'Local text' })).toBeNull();
    expect(screen.queryByRole('option', { name: 'Cloud video' })).toBeNull(); expect(screen.queryByRole('option', { name: 'Offline video' })).toBeNull();
    expect(button('建立有界评测运行').disabled).toBe(true);
    expect(screen.getByText(/256 × 256；请求时长 1 秒；帧率 8 fps；seed 7/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('本次评测的本地模型路线'), { target: { value: videoRoute.route_id } });
    fireEvent.click(button('建立有界评测运行'));
    await waitFor(() => expect(api.startBenchmark).toHaveBeenCalledWith(videoSet, videoRoute.route_id, expect.any(String)));
    await screen.findByText('运行 video-run · READY');
    expect(api.benchmarkAction).not.toHaveBeenCalled(); expect(api.executeBenchmark).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: '执行下一评测样本' })).toBeNull();
    fireEvent.change(screen.getByLabelText('待运行任务集'), { target: { value: 'mixed' } });
    expect(screen.queryByRole('option', { name: 'Registered local T2V' })).toBeNull(); expect(button('建立有界评测运行').disabled).toBe(true);
  });

  it('fails closed when an older backend has not admitted local T2V', async () => {
    const { api, state } = fixture(); state.video_execution = 'IMPORT_ONLY_LOCAL_ADMISSION_UNAVAILABLE';
    render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByRole('option', { name: 'Video fixture · v2' });
    fireEvent.change(screen.getByLabelText('待运行任务集'), { target: { value: videoSet.id } });
    expect(screen.getByText(/当前服务尚未开放本地文生视频实测/)).toBeTruthy(); expect(button('建立有界评测运行').disabled).toBe(true);
  });

  it('locks VIDEO to NONEMPTY and clears prior text rule targets', async () => {
    const { api } = fixture(); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByRole('option', { name: 'Video fixture · v2' });
    fireEvent.change(screen.getByLabelText('评测任务集标题'), { target: { value: 'Video rules' } });
    fireEvent.change(screen.getByLabelText('样本 1 合成测试输入'), { target: { value: 'Synthetic fixture' } });
    fireEvent.change(screen.getByLabelText('样本 1 正确性规则'), { target: { value: 'CONTAINS' } });
    fireEvent.change(screen.getByLabelText('样本 1 规则目标（每行一项）'), { target: { value: 'old text' } });
    fireEvent.change(screen.getByLabelText('样本 1 类型'), { target: { value: 'VIDEO_WORKFLOW' } });
    const rule = screen.getByLabelText('样本 1 正确性规则') as HTMLSelectElement;
    expect(rule.disabled).toBe(true); expect(rule.value).toBe('NONEMPTY'); expect(screen.queryByLabelText('样本 1 规则目标（每行一项）')).toBeNull();
    fireEvent.click(button('保存评测任务集'));
    await waitFor(() => expect(api.createSet).toHaveBeenCalledWith(expect.objectContaining({ cases: [expect.objectContaining({ kind: 'VIDEO_WORKFLOW', rule: 'NONEMPTY', expected: [] })] })));
    expect(api.executeBenchmark).not.toHaveBeenCalled();
  });

  it('requires an exact reviewed original preview before one execution and never autosteps', async () => {
    const { api } = fixture([ready()]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByText('运行 video-run · READY');
    expect(button(executeLabel).disabled).toBe(true); expect(screen.queryByLabelText(reviewLabel)).toBeNull();
    expect(screen.queryByText(/执行已尝试，请先核对运行状态/)).toBeNull();
    fireEvent.click(button('预览这一视频样本请求'));
    await waitFor(() => expect(api.benchmarkAction).toHaveBeenCalledWith(expect.objectContaining({ version: 1 }), 'preview'));
    const review = await screen.findByLabelText(reviewLabel);
    expect(screen.getByRole('region', { name: '视频样本原始请求预览' }).textContent).toContain('"frames": 9');
    expect((screen.getByLabelText('这一视频样本的准确生成 Prompt') as HTMLTextAreaElement).value).toBe('Synthetic moving square');
    expect(button(executeLabel).disabled).toBe(true); expect(api.executeBenchmark).not.toHaveBeenCalled();
    fireEvent.click(review); fireEvent.click(button(executeLabel)); fireEvent.click(button(executeLabel));
    await waitFor(() => expect(api.executeBenchmark).toHaveBeenCalledTimes(1));
    expect(api.executeBenchmark).toHaveBeenCalledWith(expect.objectContaining({ id: 'video-run', version: 2 }), digest);
    await screen.findByText('运行 video-run · RUNNING');
    expect(button(executeLabel).disabled).toBe(true); expect(button('预览这一视频样本请求').disabled).toBe(true);
    expect(vi.mocked(api.benchmarkAction).mock.calls.some(([, action]) => action === 'step')).toBe(false);
    expect(screen.getByRole('region', { name: '原视频任务回执' }).textContent).toContain('original-job');
  });

  it('discards review after a version/digest refresh and requires new authorization', async () => {
    const { api, state } = fixture([ready(true)]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByLabelText(reviewLabel)); expect(button(executeLabel).disabled).toBe(false);
    state.runs = [{ ...ready(true), version: 9, video_sample: { index: 0, status: 'PREVIEWED', preview: { production_preview: { ...productionPreview, preview_digest: 'c'.repeat(64) }, preview_digest: 'c'.repeat(64) } } }];
    fireEvent.click(button('核对运行状态'));
    await waitFor(() => expect(screen.getByText(`请求预览摘要：${'c'.repeat(64)}`)).toBeTruthy());
    expect((screen.getByLabelText(reviewLabel) as HTMLInputElement).checked).toBe(false); expect(button(executeLabel).disabled).toBe(true);
    expect(api.executeBenchmark).not.toHaveBeenCalled();
  });

  it.each([undefined, '', 'not-a-digest'])('does not authorize a missing or malformed preview digest (%s)', async badDigest => {
    const current = ready(true); current.video_sample.preview.preview_digest = badDigest;
    const { api } = fixture([current]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByLabelText(reviewLabel);
    expect((screen.getByLabelText(reviewLabel) as HTMLInputElement).disabled).toBe(true); expect(button(executeLabel).disabled).toBe(true);
  });

  it('keeps cancellation available during execute and reads the latest version before cancelling', async () => {
    const { api, state } = fixture([ready(true)]); let finish!: (value: Row) => void;
    vi.mocked(api.executeBenchmark).mockImplementation(async () => { state.runs = [running()]; return new Promise(resolve => { finish = resolve; }); });
    render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByLabelText(reviewLabel)); fireEvent.click(button(executeLabel));
    await waitFor(() => expect(api.executeBenchmark).toHaveBeenCalledTimes(1));
    expect(button('取消此评测运行').disabled).toBe(false); fireEvent.click(button('取消此评测运行'));
    await waitFor(() => expect(api.benchmarkAction).toHaveBeenCalledWith(expect.objectContaining({ version: 3 }), 'cancel'));
    await screen.findByText('运行 video-run · CANCELLED');
    await act(async () => finish(running()));
    expect(screen.getByText('运行 video-run · CANCELLED')).toBeTruthy(); expect(api.executeBenchmark).toHaveBeenCalledTimes(1);
  });

  it('requires a current-state read after uncertain execution instead of blind retry', async () => {
    const { api } = fixture([ready(true)]); vi.mocked(api.executeBenchmark).mockRejectedValueOnce(new Error('transport lost'));
    render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByLabelText(reviewLabel)); fireEvent.click(button(executeLabel));
    await screen.findByText(/执行已尝试，请先核对运行状态/);
    expect(button(executeLabel).disabled).toBe(true); expect((screen.getByLabelText(reviewLabel) as HTMLInputElement).disabled).toBe(true);
    expect(api.executeBenchmark).toHaveBeenCalledTimes(1);
  });

  it('refreshes and reconciles the same original unknown job without invoking execute', async () => {
    const { api } = fixture([running('UNKNOWN')]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByText('运行 video-run · RUNNING');
    fireEvent.click(button('刷新原视频任务'));
    await waitFor(() => expect(api.benchmarkAction).toHaveBeenCalledWith(expect.objectContaining({ version: 3 }), 'refresh'));
    await waitFor(() => expect(button('核对原视频任务（不重发）').disabled).toBe(false));
    fireEvent.click(button('核对原视频任务（不重发）'));
    await waitFor(() => expect(api.benchmarkAction).toHaveBeenCalledWith(expect.objectContaining({ version: 4 }), 'reconcile'));
    expect(api.executeBenchmark).not.toHaveBeenCalled(); expect(button(executeLabel).disabled).toBe(true);
  });

  it('does not restore a private preview or authorization from the previous client scope', async () => {
    const first = fixture([ready()]), second = fixture([ready()]); let finish!: (value: Row) => void;
    vi.mocked(first.api.benchmarkAction).mockImplementation(async () => new Promise(resolve => { finish = resolve; }));
    const view = render(<ModelBenchmarkPanel api={first.api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByRole('button', { name: '预览这一视频样本请求' }));
    view.rerender(<ModelBenchmarkPanel api={second.api} routes={[videoRoute]} />);
    await screen.findByText('运行 video-run · READY');
    await act(async () => finish(ready(true)));
    expect(screen.queryByRole('region', { name: '视频样本原始请求预览' })).toBeNull(); expect(button(executeLabel).disabled).toBe(true);
    expect(second.api.executeBenchmark).not.toHaveBeenCalled();
  });

  it('shows video completion as a private candidate with separate observation time and no image workflow', async () => {
    const completed = { ...running('SUCCEEDED'), version: 5, status: 'COMPLETED', completed: 1, results: [{ case_title: 'Video sample', passed: true, latency_ms: null, observed_task_latency_ms: 4321, media_receipt: { owner: 'video', task_id: 'original-job', status: 'SUCCEEDED', output_candidate: { digest: 'd'.repeat(64), review_state: 'PENDING' } } }] };
    const { api, state } = fixture([completed]);
    state.evidence = [{ id: 'video-evidence', version: 1, capability: 'VIDEO', origin: 'EXECUTED', evidence_state: 'CURRENT', verification: 'LOCAL_EXECUTED', metrics: { sample_count: 1, latency_ms: null, observed_task_latency_ms: 4321, rule_pass_count: 1 } }];
    render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByText('运行 video-run · COMPLETED');
    expect(screen.getByText(/Video sample · 规则通过 · 任务观测耗时 4321 ms/)).toBeTruthy();
    expect(screen.getByText(/任务观测耗时包含轮询与用户等待/)).toBeTruthy();
    expect(screen.getByText(/推理延迟未测量；任务观测耗时 4321 ms（含轮询与用户等待）/)).toBeTruthy();
    expect(screen.getByText(/完成状态只记录本组执行证据；候选保持私有/)).toBeTruthy();
    expect(screen.queryByText(/在原 Studio 视频任务中人工审核/)).toBeNull();
    expect(screen.queryByText(/请到封面与分镜生成工作流/)).toBeNull();
    expect(screen.queryByLabelText(/样本 1 输出/)).toBeNull(); expect(screen.queryByRole('link', { name: '查看此任务的私有视频候选' })).toBeNull();
    expect(button(executeLabel).disabled).toBe(true);
    const options = within(screen.getByLabelText('结果组一')).getAllByRole('option'); expect(options).toHaveLength(1);
  });


  it.each(['QUEUED', 'ADMISSION_UNKNOWN'])('resumes only the recovered original QUEUED job after explicit review (%s)', async sampleStatus => {
    const current = running('QUEUED'); current.video_sample.status = sampleStatus;
    const { api } = fixture([current]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    const review = await screen.findByLabelText(reviewLabel);
    expect(button('继续执行已排队的原视频任务').disabled).toBe(true);
    expect(screen.getByText(/不会新建或重新排队/)).toBeTruthy();
    fireEvent.click(review); fireEvent.click(button('继续执行已排队的原视频任务'));
    await waitFor(() => expect(api.executeBenchmark).toHaveBeenCalledWith(expect.objectContaining({ version: 3, status: 'RUNNING', video_sample: expect.objectContaining({ job: expect.objectContaining({ id: 'original-job', status: 'QUEUED' }) }) }), digest));
    expect(api.startBenchmark).not.toHaveBeenCalled(); expect(api.benchmarkAction).not.toHaveBeenCalled();
  });

  it.each(['ADMISSION_UNKNOWN', 'UNKNOWN'])('never executes an uncertain send or unknown original job (%s)', async sampleStatus => {
    const current = running('UNKNOWN'); current.video_sample.status = sampleStatus;
    const { api } = fixture([current]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByLabelText(reviewLabel);
    expect((screen.getByLabelText(reviewLabel) as HTMLInputElement).disabled).toBe(true);
    expect(button(executeLabel).disabled).toBe(true); expect(api.executeBenchmark).not.toHaveBeenCalled();
  });

  it('fixes video budget to zero and explains unresolved original reservations', async () => {
    const { api } = fixture([ready()]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByText('运行 video-run · READY');
    fireEvent.change(screen.getByLabelText('整组费用预占上限（µUSD）'), { target: { value: '19' } });
    fireEvent.change(screen.getByLabelText('样本 1 类型'), { target: { value: 'VIDEO_WORKFLOW' } });
    const budget = screen.getByLabelText('整组费用预占上限（µUSD）') as HTMLInputElement;
    expect(budget.value).toBe('0'); expect(budget.disabled).toBe(true);
    expect(screen.getByText(/私有输出完成不会自动核销费用/)).toBeTruthy();
    expect(screen.getByText(/未结预占可能阻止下一样本/)).toBeTruthy();
  });


  it('requires a fresh preview for the next sample instead of reusing completed authorization', async () => {
    const current: Row = { ...running('AWAITING_REVIEW'), total: 2, completed: 1, version: 7, status: 'READY' };
    current.video_sample.status = 'COMPLETED';
    const { api } = fixture([current]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    const review = await screen.findByLabelText(reviewLabel) as HTMLInputElement;
    expect(review.disabled).toBe(true); expect(button(executeLabel).disabled).toBe(true);
    expect(button('预览这一视频样本请求').disabled).toBe(false);
    expect(screen.getByText(/上一份预览不能重复执行/)).toBeTruthy();
    expect(api.executeBenchmark).not.toHaveBeenCalled(); expect(api.benchmarkAction).not.toHaveBeenCalled();
  });

  it('blocks saved VIDEO sets with a nonzero budget until the fixed zero budget is saved', async () => {
    const { api } = fixture([], [{ ...videoSet, max_cost_microusd: 25 }]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByRole('option', { name: 'Video fixture · v2' });
    fireEvent.change(screen.getByLabelText('待运行任务集'), { target: { value: videoSet.id } });
    fireEvent.change(screen.getByLabelText('本次评测的本地模型路线'), { target: { value: videoRoute.route_id } });
    expect(button('建立有界评测运行').disabled).toBe(true);
    expect(screen.getByText(/视频评测的外部费用上限必须为 0 µUSD/)).toBeTruthy();
    expect(api.startBenchmark).not.toHaveBeenCalled();
  });

  it('preserves existing image and text step controls', async () => {
    const image = { ...ready(), id: 'image-run', capability: 'IMAGE' }; const text = { ...ready(), id: 'text-run', capability: 'TEXT' };
    const { api } = fixture([image, text]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute, textRoute]} />);
    await screen.findByText('运行 image-run · READY');
    expect(screen.getAllByRole('button', { name: '执行下一评测样本' })).toHaveLength(2);
    expect(screen.queryByRole('button', { name: executeLabel })).toBeNull();
  });
});

it('uses scoped original benchmark endpoints and exact CAS/digest payloads for all video actions', async () => {
  const fetch = vi.fn(async () => new Response(JSON.stringify(ready()), { status: 200 })); vi.stubGlobal('fetch', fetch);
  const api = modelBrokerClient(experimentalClient('project one', { sessionToken: 'trusted', scope: { workspaceId: 'w', projectId: 'project one', storylineId: 's', branchId: 'branch-one' } }));
  const run = { ...ready(), id: 'run/one', version: 8 };
  for (const action of ['preview', 'refresh', 'reconcile', 'cancel'] as const) await api.benchmarkAction(run, action);
  await api.executeBenchmark(run, digest);
  const calls = fetch.mock.calls as unknown as [string, RequestInit][];
  expect(calls.map(([url]) => url)).toEqual(['preview', 'refresh', 'reconcile', 'cancel', 'execute'].map(action => `/api/novels/project%20one/experimental/model-benchmarks/runs/run%2Fone/${action}`));
  expect(calls.map(([, init]) => JSON.parse(String(init.body)))).toEqual([{ expected_version: 8 }, { expected_version: 8 }, { expected_version: 8 }, { expected_version: 8 }, { expected_version: 8, reviewed_preview_digest: digest }]);
  expect(calls.every(([, init]) => init.method === 'POST')).toBe(true);
  expect(calls[4][1].headers).toMatchObject({ 'X-Session-Token': 'trusted', 'X-Branch-Id': 'branch-one' });
});


function playableRun(): Row {
  const run = { ...running('AWAITING_REVIEW'), total: 2, completed: 2, status: 'COMPLETED', results: [0, 1].map(index => ({ index, case_title: `Video ${index + 1}`, passed: true, latency_ms: null, observed_task_latency_ms: 100, media_receipt: { owner: 'video', task_id: `job-${index}`, status: 'AWAITING_REVIEW', output_candidate: { digest: 'd'.repeat(64) } } })) } as Row;
  run.video_sample.index = 1; run.video_sample.job.output_candidate = { digest: 'd'.repeat(64) };
  return run;
}
function objectUrls() {
  const create = vi.fn(() => 'blob:private-video'), revoke = vi.fn();
  const OriginalURL = URL;
  vi.stubGlobal('URL', class extends OriginalURL { static createObjectURL = create; static revokeObjectURL = revoke; });
  return { create, revoke };
}

describe('authenticated private video candidate preview', () => {
  it('loads only on explicit click, deduplicates current/completed receipts and revokes on close', async () => {
    const urls = objectUrls(), { api } = fixture([playableRun()]);
    render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    await screen.findByRole('button', { name: '查看样本 1 的私有视频' });
    expect(screen.getAllByRole('button', { name: /查看样本 .* 的私有视频/ })).toHaveLength(2);
    expect(api.benchmarkVideoCandidate).not.toHaveBeenCalled(); expect(screen.queryByLabelText('样本 1 私有视频预览')).toBeNull();
    fireEvent.click(button('查看样本 1 的私有视频')); fireEvent.click(button('查看样本 1 的私有视频'));
    const video = await screen.findByLabelText('样本 1 私有视频预览') as HTMLVideoElement;
    expect(api.benchmarkVideoCandidate).toHaveBeenCalledTimes(1); expect(api.benchmarkVideoCandidate).toHaveBeenCalledWith('video-run', 0, expect.any(AbortSignal));
    expect(video.getAttribute('src')).toBe('blob:private-video'); expect(video.controls).toBe(true); expect(video.autoplay).toBe(false);
    expect(video.preload).toBe('metadata'); expect(urls.create).toHaveBeenCalledTimes(1);
    fireEvent.click(button('关闭样本 1 视频预览'));
    expect(urls.revoke).toHaveBeenCalledWith('blob:private-video'); expect(screen.queryByLabelText('样本 1 私有视频预览')).toBeNull();
    expect(api.executeBenchmark).not.toHaveBeenCalled(); expect(api.benchmarkAction).not.toHaveBeenCalled();
  });

  it('aborts close and discards a late reply while allowing an explicit new read', async () => {
    const urls = objectUrls(), { api } = fixture([playableRun()]); let finish!: (blob: Blob) => void;
    vi.mocked(api.benchmarkVideoCandidate).mockImplementationOnce(async () => new Promise(resolve => { finish = resolve; }));
    render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看样本 1 的私有视频' }));
    const signal = vi.mocked(api.benchmarkVideoCandidate).mock.calls[0][2]!;
    fireEvent.click(button('关闭样本 1 视频预览')); expect(signal.aborted).toBe(true);
    fireEvent.click(button('查看样本 1 的私有视频')); await screen.findByLabelText('样本 1 私有视频预览');
    await act(async () => finish(new Blob(['late old video'], { type: 'video/webm' })));
    expect(urls.create).toHaveBeenCalledTimes(1); expect(api.benchmarkVideoCandidate).toHaveBeenCalledTimes(2);
  });

  it('revokes loaded private URLs on scope change and fences pending reads from the prior scope', async () => {
    const urls = objectUrls(), first = fixture([playableRun()]), second = fixture([playableRun()]); let finish!: (blob: Blob) => void;
    vi.mocked(first.api.benchmarkVideoCandidate).mockResolvedValueOnce(new Blob(['first'], { type: 'video/webm' })).mockImplementationOnce(async () => new Promise(resolve => { finish = resolve; }));
    const view = render(<ModelBenchmarkPanel api={first.api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看样本 1 的私有视频' })); await screen.findByLabelText('样本 1 私有视频预览');
    fireEvent.click(button('查看样本 2 的私有视频'));
    const signal = vi.mocked(first.api.benchmarkVideoCandidate).mock.calls[1][2]!;
    view.rerender(<ModelBenchmarkPanel api={second.api} routes={[videoRoute]} />);
    await screen.findByRole('button', { name: '查看样本 1 的私有视频' });
    expect(signal.aborted).toBe(true); expect(urls.revoke).toHaveBeenCalledWith('blob:private-video');
    await act(async () => finish(new Blob(['private late result'], { type: 'video/webm' })));
    expect(urls.create).toHaveBeenCalledTimes(1); expect(screen.queryByLabelText('样本 1 私有视频预览')).toBeNull();
    expect(screen.queryByLabelText('样本 2 私有视频预览')).toBeNull(); expect(second.api.benchmarkVideoCandidate).not.toHaveBeenCalled();
  });

  it('revokes private URLs on unmount and never loads a supplied candidate_url', async () => {
    const urls = objectUrls(), run = playableRun(); run.video_sample.candidate_url = 'https://other.example/private-video';
    const { api } = fixture([run]); const view = render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看样本 2 的私有视频' })); await screen.findByLabelText('样本 2 私有视频预览');
    expect(screen.queryByRole('link', { name: /私有视频/ })).toBeNull(); view.unmount();
    expect(urls.revoke).toHaveBeenCalledTimes(1); expect(urls.revoke).toHaveBeenCalledWith('blob:private-video');
  });

  it.each([new Blob([], { type: 'video/webm' }), new Blob(['not video'], { type: 'text/html' })])('rejects empty/non-video responses without exposing an ObjectURL', async blob => {
    const urls = objectUrls(), { api } = fixture([playableRun()]); vi.mocked(api.benchmarkVideoCandidate).mockResolvedValue(blob);
    render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看样本 1 的私有视频' }));
    await screen.findByText(/私有视频读取失败/); expect(urls.create).not.toHaveBeenCalled();
    expect(button('查看样本 1 的私有视频').disabled).toBe(false);
  });


  it('offers a current private output before results are recorded and revokes it on refresh', async () => {
    const urls = objectUrls(), run = running('AWAITING_REVIEW'); run.video_sample.job.output_candidate = { digest: 'd'.repeat(64) };
    const { api } = fixture([run]); render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看样本 1 的私有视频' }));
    await screen.findByLabelText('样本 1 私有视频预览');
    fireEvent.click(button('核对运行状态'));
    await screen.findByRole('button', { name: '查看样本 1 的私有视频' });
    expect(urls.revoke).toHaveBeenCalledWith('blob:private-video');
    expect(screen.queryByLabelText('样本 1 私有视频预览')).toBeNull(); expect(api.benchmarkVideoCandidate).toHaveBeenCalledTimes(1);
  });

  it('shows permission failure without retrying or requesting generation', async () => {
    const urls = objectUrls(), { api } = fixture([playableRun()]); vi.mocked(api.benchmarkVideoCandidate).mockRejectedValue(new Error('FORBIDDEN'));
    render(<ModelBenchmarkPanel api={api} routes={[videoRoute]} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看样本 1 的私有视频' }));
    await screen.findByText(/私有视频读取失败/); expect(api.benchmarkVideoCandidate).toHaveBeenCalledTimes(1);
    expect(urls.create).not.toHaveBeenCalled(); expect(api.executeBenchmark).not.toHaveBeenCalled();
  });
});

it('reads candidate bytes with the captured session/branch and abort signal, never a bare URL', async () => {
  const fetch = vi.fn(async () => new Response('video', { status: 200, headers: { 'Content-Type': 'video/webm' } })); vi.stubGlobal('fetch', fetch);
  const api = modelBrokerClient(experimentalClient('project one', { sessionToken: 'trusted', scope: { workspaceId: 'w', projectId: 'project one', storylineId: 's', branchId: 'branch-one' } }));
  const controller = new AbortController(); const blob = await api.benchmarkVideoCandidate('run/one', 2, controller.signal);
  expect(blob.type).toBe('video/webm');
  const calls = fetch.mock.calls as unknown as [string, RequestInit][];
  expect(calls[0][0]).toBe('/api/novels/project%20one/experimental/model-benchmarks/runs/run%2Fone/video/2/candidate');
  expect(calls[0][1]).toMatchObject({ method: 'GET', signal: controller.signal, headers: { 'X-Session-Token': 'trusted', 'X-Branch-Id': 'branch-one' } });
  expect(calls[0][1].body).toBeUndefined();
});
