// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Chapter } from '../api';
import { StyleAnalysisModelPanel } from './StyleAnalysisModelPanel';
import { experimentalClient } from './api';
import { styleReviewClient, type StyleAnalysis, type StyleModelPreview, type StyleModelOpinion } from './styleReviewClient';
const route = { route_id: 'route1', provider_id: 'mock', model_id: 'mock-writer', display_name: 'Mock test model', synthetic: true, available: true, reasons: [], identity: {} };
const preview: StyleModelPreview = { preview_digest: 'a'.repeat(64), previewed_at: '2026-10-06T15:30:00Z', budget: {}, actor: 'author', scope: {}, sources: { c1: { version: 3, digest: 'digest' } }, request: { prompt: 'EXACT_SELECTED_STYLE_FRAGMENT', context: {} }, rubric: { id: 'style-model-evidence-v1', version: 1, boundary: 'Qualitative only' }, broker: { chosen: { ...route, price: { reserve_microusd: 0 } }, budget_version: 0, candidates: [route], decision_reason: 'ELIGIBLE' }, excluded: ['UNSELECTED_RANGES'], max_output_bytes: 32768, timeout_seconds: 120, execution_available: true, quality_verification: 'SYNTHETIC_PROTOCOL_ONLY', style_profile: { id: 's1', version: 2, title: 'Style', instructions: 'Keep concise', rules: [] }, samples: [{ chapter_id: 'c1', expected_version: 3, start: 4, end: 20 }], source_strategy: 'EXACT_SELECTED_STYLE_RANGES' };
const analysis: StyleAnalysis = { id: 'a1', version: 2, style_id: 's1', style_version: 2, language: 'en', method_version: 'counts', status: 'COMPLETED', stale: false, metrics: {}, samples: preview.samples, comparison: null, limitations: [], privacy_level: 'LOCAL_ONLY', model_assessments: [], model_opinion_state: 'NOT_REQUESTED' };
const chapter = { id: 'c1', version: 3, title: 'Synthetic source' } as Chapter;
const client = () => styleReviewClient(experimentalClient('n1', { sessionToken: 'host', scope: { workspaceId: 'w', projectId: 'n1', storylineId: 's', branchId: 'b' } }));
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('does nothing on open and requires explicit local route selection and preview', async () => {
  const fetch = vi.fn(async (url: string) => response(url.endsWith('/catalog') ? { routes: [route] } : { ...analysis, model_preview: preview })); vi.stubGlobal('fetch', fetch);
  const changed = vi.fn(); render(<StyleAnalysisModelPanel api={client()} analysis={analysis} chapter={chapter} onChanged={changed} />);
  expect(fetch).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '查看文风解读本地模型' })); await screen.findByLabelText('文风解读模型 a1');
  expect((screen.getByRole('button', { name: '准备准确文风模型预览' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('文风解读模型 a1'), { target: { value: route.route_id } }); fireEvent.click(screen.getByRole('button', { name: '准备准确文风模型预览' }));
  await waitFor(() => expect(changed).toHaveBeenCalledOnce()); expect(fetch.mock.calls.some(([url]) => url.endsWith('/dispatch'))).toBe(false);
});
it('requires the separately reviewed exact receipt and suppresses duplicate dispatch clicks', async () => {
  const fetch = vi.fn(async (_url: string, _init?: RequestInit) => response(analysis)); vi.stubGlobal('fetch', fetch); const changed = vi.fn();
  render(<StyleAnalysisModelPanel api={client()} analysis={{ ...analysis, model_preview: preview }} onChanged={changed} />);
  const send = screen.getByRole('button', { name: '明确发送此次文风解读' }); expect((send as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('准确文风模型请求 a1') as HTMLTextAreaElement).value).toContain('EXACT_SELECTED_STYLE_FRAGMENT');
  fireEvent.click(screen.getByLabelText('已核对文风原文范围、档案、模型与零费用预占')); fireEvent.click(send); fireEvent.click(send);
  await waitFor(() => expect(changed).toHaveBeenCalledOnce()); expect(fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({ expected_version: 2, reviewed_preview_digest: preview.preview_digest });
  expect(fetch.mock.calls[0][1]!.headers).toMatchObject({ 'X-Session-Token': 'host', 'X-Branch-Id': 'b' });
});
it('hides old previews after chapter changes and blocks late callbacks after unmount', async () => {
  let complete!: (value: Response) => void; vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { complete = resolve; })));
  const changed = vi.fn(), api = client(); const view = render(<StyleAnalysisModelPanel api={api} analysis={{ ...analysis, model_preview: preview }} chapter={chapter} onChanged={changed} />);
  fireEvent.click(screen.getByLabelText('已核对文风原文范围、档案、模型与零费用预占')); fireEvent.click(screen.getByRole('button', { name: '明确发送此次文风解读' }));
  view.rerender(<StyleAnalysisModelPanel api={api} analysis={{ ...analysis, model_preview: preview }} chapter={{ ...chapter, version: 4 }} onChanged={changed} />);
  expect(screen.queryByLabelText('准确文风模型请求 a1')).toBeNull(); view.unmount(); await act(async () => complete(response(analysis))); expect(changed).not.toHaveBeenCalled();
});
it('reconciles and cancels only the original unknown job, including a stale source', async () => {
  const fetch = vi.fn(async (_url: string, _init?: RequestInit) => response(analysis)); vi.stubGlobal('fetch', fetch);
  const execution = { job_id: 'original', reservation_id: 'reservation', status: 'UNKNOWN', receipt_state: 'UNKNOWN_NO_AUTOMATIC_REPLAY', model_called: false, usage_state: 'UNKNOWN' };
  render(<StyleAnalysisModelPanel api={client()} analysis={{ ...analysis, stale: true, model_preview: preview, model_execution: execution }} onChanged={vi.fn()} />);
  expect(screen.queryByRole('button', { name: '明确发送此次文风解读' })).toBeNull(); expect(screen.queryByLabelText('准确文风模型请求 a1')).toBeNull();
  expect((screen.getByRole('button', { name: '查询原任务并核对文风证据' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '取消原文风模型任务' })); await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
  expect(fetch.mock.calls[0][0]).toContain('/analyses/a1/model/cancel'); expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({ expected_version: 2 });
});
it('keeps deterministic and model-derived values separate and persists reasoned review without an apply action', async () => {
  const opinion: StyleModelOpinion = { id: 'o1', category: 'RHYTHM', interpretation: 'A tentative reading.', boundary: 'Not a score.', evidence: [{ chapter_id: 'c1', chapter_version: 3, paragraph: 1, start: 4, end: 8, quote: 'rain' }], origin: 'MODEL_DERIVED', decision: 'PENDING', model: route, quality_verification: 'SYNTHETIC_PROTOCOL_ONLY', independence: 'UNVERIFIED', review_history: [] };
  const fetch = vi.fn(async (_url: string, _init?: RequestInit) => response(analysis)); vi.stubGlobal('fetch', fetch);
  render(<StyleAnalysisModelPanel api={client()} analysis={{ ...analysis, model_assessments: [opinion], model_opinion_state: 'AVAILABLE' }} onChanged={vi.fn()} />);
  expect(screen.getByText('Model-derived · 节奏 · PENDING')).toBeTruthy();
  const review = screen.getByRole('button', { name: '记录文风意见已核对' }); expect((review as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('文风意见审核理由 o1'), { target: { value: 'Checked synthetic reference.' } }); fireEvent.click(review);
  await waitFor(() => expect(fetch).toHaveBeenCalledOnce()); expect(fetch.mock.calls[0][0]).toContain('/opinions/o1/review');
  expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({ expected_version: 2, action: 'review', reason: 'Checked synthetic reference.' });
  expect(screen.queryByRole('button', { name: /应用|改写正文/ })).toBeNull();
});
it('reports an empty local catalog without inventing configured model opinions', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ routes: [] })));
  render(<StyleAnalysisModelPanel api={client()} analysis={analysis} onChanged={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: '查看文风解读本地模型' })); await screen.findByText('未配置可用的本地文风解读模型');
  expect((screen.getByRole('button', { name: '准备准确文风模型预览' }) as HTMLButtonElement).disabled).toBe(true);
});
it('Task Center opens only the exact original-job analysis and reports a missing target without fallback', async () => {
  const { StyleAnalysisPanel } = await import('./StyleAnalysisPanel');
  const execution = { job_id: 'wanted-job', reservation_id: null, status: 'UNKNOWN', receipt_state: 'UNKNOWN_NO_AUTOMATIC_REPLAY', model_called: false, usage_state: 'UNKNOWN' };
  const fetch = vi.fn(async (url: string, _init?: RequestInit) => response(url.endsWith('/catalog') ? { styles: [], chapters: [], characters: [], operations: [] } : { items: [{ ...analysis, model_execution: execution }, { ...analysis, id: 'unrelated-analysis', model_execution: { ...execution, job_id: 'other-job' } }] }));
  vi.stubGlobal('fetch', fetch); const scoped = experimentalClient('n1', { sessionToken: 'host' });
  const view = render(<StyleAnalysisPanel client={scoped} requestedJobId="wanted-job" />);
  const wanted = await screen.findByRole('article', { name: '文风报告 a1' });
  expect(wanted.getAttribute('aria-current')).toBe('true'); expect(document.activeElement).toBe(wanted);
  expect(screen.queryByRole('article', { name: '文风报告 unrelated-analysis' })).toBeNull(); expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  view.rerender(<StyleAnalysisPanel client={scoped} requestedJobId="missing-job" />);
  await screen.findByText('请求的原文风模型任务当前不可读或已移除；没有打开其他报告，也不会重放任务。'); expect(screen.queryByRole('article', { name: '文风报告 a1' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '退出任务定位，查看全部文风报告' })); expect(screen.getByRole('article', { name: '文风报告 a1' })).toBeTruthy();
});
