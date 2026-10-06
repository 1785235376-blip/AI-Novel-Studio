// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { NarrativeJudgePanel } from './NarrativeJudgePanel';
import { NarrativeJudgeRevisionTaskPanel } from './NarrativeJudgeRevisionTaskPanel';
import { StyleAnalysisPanel } from './StyleAnalysisPanel';
import type { JudgeFinding, StyleReviewClient } from './styleReviewClient';
const finding: JudgeFinding = { id: 'f1', version: 1, status: 'OPEN', decision: 'PENDING', code: 'EXACT_REPEATED_PARAGRAPH', category: 'REPETITION', severity: 'INFO', explanation: 'Same paragraph occurs twice.', suggestion: 'Keep or revise the refrain.', boundary: 'Exact text equality only.', origin: 'DETERMINISTIC', evidence: [{ chapter_id: 'c1', chapter_version: 2, paragraph: 1, start: 0, end: 12, quote: 'The refrain.' }], stale: false };
const task = { id: 'task1', title: 'Review the refrain', version: 1, status: 'ASSIGNED' };
const catalog = { finding_id: 'f1', finding_version: 1, existing_task: null, members: [{ id: 'author', name: 'Author', can_write: true, can_review: true }] };
const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200 });
const api = () => ({ revisionTaskCatalog: vi.fn().mockResolvedValue(catalog), createRevisionTask: vi.fn().mockResolvedValue({ task, manuscript_changed: false, task_authority: 'writer_room_v2' }) });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function prepare() { fireEvent.click(screen.getByRole('button', { name: '准备修订任务' })); await screen.findByLabelText('修订任务标题 f1'); fireEvent.change(screen.getByLabelText('修订负责人 f1'), { target: { value: 'author' } }); fireEvent.change(screen.getByLabelText('修订审核人 f1'), { target: { value: 'author' } }); }
it('creates a deliberately assigned original-room task once with exact finding CAS', async () => {
  const calls = api(), navigate = vi.fn(); render(<NarrativeJudgeRevisionTaskPanel api={calls as unknown as StyleReviewClient} finding={finding} disabled={false} onNavigate={navigate} />);
  expect(calls.revisionTaskCatalog).not.toHaveBeenCalled(); await prepare(); fireEvent.change(screen.getByLabelText('修订任务标题 f1'), { target: { value: 'Review the refrain' } });
  const create = screen.getByRole('button', { name: '明确创建修订任务' }); fireEvent.click(create); fireEvent.click(create); await screen.findByText(/已保存任务：Review the refrain/);
  expect(calls.createRevisionTask).toHaveBeenCalledTimes(1); expect(calls.createRevisionTask).toHaveBeenCalledWith('f1', 1, { title: 'Review the refrain', description: finding.suggestion, assignee: 'author', reviewer: 'author' });
  fireEvent.click(screen.getByRole('button', { name: '打开协作室处理修订' })); expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'writer_room_v2', feature: 'writer_room_v2' });
});
it('reopens an original persisted task without a replacement after an unknown response', async () => {
  const calls = api(); calls.revisionTaskCatalog.mockResolvedValue({ ...catalog, existing_task: task }); render(<NarrativeJudgeRevisionTaskPanel api={calls as unknown as StyleReviewClient} finding={finding} disabled={false} />);
  fireEvent.click(screen.getByRole('button', { name: '准备修订任务' })); await screen.findByText(/已保存任务：Review the refrain/); expect(screen.queryByRole('button', { name: '明确创建修订任务' })).toBeNull(); expect(calls.createRevisionTask).not.toHaveBeenCalled();
});
it('preserves fields after failure and ignores late completion after closing preparation', async () => {
  const calls = api(); calls.createRevisionTask.mockRejectedValueOnce(new Error('Source changed')); render(<NarrativeJudgeRevisionTaskPanel api={calls as unknown as StyleReviewClient} finding={finding} disabled={false} />); await prepare();
  fireEvent.change(screen.getByLabelText('修订任务说明 f1'), { target: { value: 'My preserved task description.' } }); fireEvent.click(screen.getByRole('button', { name: '明确创建修订任务' })); await screen.findByRole('alert'); expect((screen.getByLabelText('修订任务说明 f1') as HTMLTextAreaElement).value).toBe('My preserved task description.');
  let finish!: (value: unknown) => void; calls.createRevisionTask.mockImplementation(() => new Promise(resolve => { finish = resolve; })); fireEvent.click(screen.getByRole('button', { name: '明确创建修订任务' })); fireEvent.click(screen.getByRole('button', { name: '关闭修订任务准备' })); await act(async () => finish({ task })); expect(screen.queryByText(/已保存任务：Review the refrain/)).toBeNull(); expect(screen.queryByLabelText('修订任务说明 f1')).toBeNull();
});
it('does not restore a catalog after a scope-keyed remount', async () => {
  const calls = api(); let finish!: (value: unknown) => void; calls.revisionTaskCatalog.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const view = render(<NarrativeJudgeRevisionTaskPanel key="scope1" api={calls as unknown as StyleReviewClient} finding={finding} disabled={false} />); fireEvent.click(screen.getByRole('button', { name: '准备修订任务' })); view.rerender(<NarrativeJudgeRevisionTaskPanel key="scope2" api={api() as unknown as StyleReviewClient} finding={finding} disabled={false} />); await act(async () => finish(catalog)); expect(screen.queryByLabelText('修订任务标题 f1')).toBeNull();
});
it('requires an intentional reason, hides the finding by default and supports explicit reopen', async () => {
  let current = { ...finding }; const run = () => ({ id: 'run1', version: 1, status: 'COMPLETED', stale: false, findings: [current], abstentions: [], model_called: false, verification: 'DETERMINISTIC_RULES' });
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/catalog')) return response({ chapters: [], rubrics: [], adapters: [] }); if (url.endsWith('/runs')) return response({ items: [run()] }); if (url.endsWith('/runs/run1')) return response(run());
    if (url.endsWith('/findings/f1/review')) { const body = JSON.parse(init!.body as string); current = { ...current, version: current.version + 1, decision: body.action === 'intentional' ? 'INTENTIONAL' : 'PENDING', status: body.action === 'intentional' ? 'RESOLVED' : 'OPEN' }; return response(current); } throw new Error(url);
  }); vi.stubGlobal('fetch', fetch); render(<NarrativeJudgePanel client={experimentalClient('novel', { sessionToken: '' })} />);
  await waitFor(() => expect((screen.getByLabelText('查看审阅记录') as HTMLSelectElement).disabled).toBe(false)); fireEvent.change(screen.getByLabelText('查看审阅记录'), { target: { value: 'run1' } });
  const intentional = await screen.findByRole('button', { name: '标为有意安排，不再重复提示' }); expect((intentional as HTMLButtonElement).disabled).toBe(true); fireEvent.change(screen.getByLabelText('审核理由 f1'), { target: { value: 'A deliberate refrain.' } }); fireEvent.click(intentional);
  await screen.findByText('有意安排的重复线索已收起。选择“有意安排”可查看或重新打开。'); expect(screen.queryByRole('article', { name: '检查线索 f1' })).toBeNull(); fireEvent.change(screen.getByLabelText('按审核决定筛选'), { target: { value: 'INTENTIONAL' } }); expect(screen.getByRole('article', { name: '检查线索 f1' })).toBeTruthy(); expect(screen.queryByRole('button', { name: '准备修订任务' })).toBeNull(); fireEvent.click(screen.getByRole('button', { name: '重新打开核对' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/review'))).toHaveLength(2)); expect(JSON.parse(fetch.mock.calls.find(([url]) => url.endsWith('/review'))![1]!.body as string)).toEqual({ expected_version: 1, action: 'intentional', reason: 'A deliberate refrain.' });
});
it('distinguishes source-local deterministic metrics from unconfigured model opinions', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/catalog') ? response({ styles: [], chapters: [], characters: [], operations: [] }) : response({ items: [{ id: 'a1', version: 1, style_id: 's1', style_version: 1, language: 'en', status: 'COMPLETED', stale: false, method_version: 'unicode-style-statistics-v2-independent-samples', metrics: { sentence_count: 2, sentence_length_mean: { numerator: 24, denominator: 2 } }, model_opinion_state: 'NOT_CONFIGURED', samples: [], limitations: [], sample_metrics: [{ chapter_id: 'c1', expected_version: 2, start: 9, end: 21, metrics: { sentence_length_mean: { numerator: 12, denominator: 1 } }, paragraphs: [{ paragraph: 2, start: 9, end: 21, quote: 'Exact source', partial_paragraph: true }], paragraphs_truncated: false }] }] })));
  render(<StyleAnalysisPanel client={experimentalClient('novel', { sessionToken: '' })} />); await screen.findByText('Deterministic Metric · 确定性测量'); expect(screen.getByText(/Model Opinion：尚未请求模型意见/)).toBeTruthy(); expect(screen.getByText('24 / 2 = 12.00')).toBeTruthy(); fireEvent.click(screen.getByText('来源样本 1 的独立测量与原文位置')); expect((screen.getByLabelText('样本 1 段落 2 原文') as HTMLTextAreaElement).value).toBe('Exact source'); expect(screen.getByText(/仅选择段落的一部分/)).toBeTruthy();
});
