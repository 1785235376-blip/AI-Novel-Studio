// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SourceAdaptationPanel } from './SourceAdaptationPanel';
import { creativeClient, type AdaptationProposal } from './client';
import { newScene } from './types';
import type { Chapter } from '../api';

const chapter = { id: 'chapter-1', novel_id: 'novel-1', title: 'Saved source', content: 'The visitor waits.', version: 3, number: 1, word_count: 3, document: {}, status: 'DRAFT' } as Chapter;
function proposal(patch: Partial<AdaptationProposal> = {}): AdaptationProposal {
  return { id: 'proposal-1', version: 1, status: 'DRAFT', title: 'Adapted screenplay', chapter_id: chapter.id,
    source_version: 3, source_digest: 'a'.repeat(64), selection_digest: 'b'.repeat(64), selected_text: chapter.content,
    output: null, output_digest: null, model_preview: null, model_execution: null, provenance: null, document_id: null, ...patch };
}
function candidate() { return proposal({ version: 5, status: 'NEEDS_REVIEW', output_digest: 'c'.repeat(64), output: {
  scenes: [{ ...newScene(1), id: 'scene-1', heading: 'INT. STUDY', action: 'A visitor waits.' }],
  report: { summary: 'Narration becomes action.', changes: [{ id: 'change-1', kind: 'VISUALIZATION', source_quote: chapter.content, scene_ids: ['scene-1'], note: 'Verify meaning.' }] } },
  model_execution: { job_id: 'job-1', status: 'CANDIDATES', model_called: true, receipt_state: 'RECORDED', usage_state: 'REPORTED' } }); }
function response(body: unknown, status = 200) { return { ok: status >= 200 && status < 300, status, json: async () => body }; }
function setup(options: { rows?: AdaptationProposal[]; override?: (url: string, init: RequestInit) => unknown; allowed?: boolean } = {}) {
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const value = options.override?.(url, init); if (value !== undefined) return await value;
    if (url.endsWith('/model-routes')) return response({ items: [{ route_id: 'r'.repeat(64), provider_id: 'local', model_id: 'verified-model', synthetic: false, available: true, reasons: [] }, { route_id: 'mock', provider_id: 'mock', model_id: 'mock-writer', synthetic: true, available: true, reasons: [] }] });
    if (url.endsWith('/adaptation-proposals') && init.method === 'GET') return response({ items: options.rows || [] });
    if (url.endsWith('/adaptation-proposals') && init.method === 'POST') return response(proposal());
    if (url.endsWith('/preview')) return response(proposal({ version: 2, model_preview: { preview_digest: 'd'.repeat(64), execution_available: true, model_called: false, allow_cloud_fallback: false, automatic_retry: false, timeout_seconds: 180, source_strategy: 'EXACT_SAVED_SELECTION_NO_IMPLICIT_CONTEXT', request: { prompt: chapter.content, parameters: {} }, broker: { chosen: { provider_id: 'local', model_id: 'verified-model' } } } }));
    if (url.endsWith('/dispatch')) return response(proposal({ version: 4, status: 'GENERATING', model_execution: { job_id: 'job-1', status: 'QUEUED', model_called: false, receipt_state: 'RECORDED', usage_state: 'UNKNOWN' } }));
    if (url.endsWith('/review')) return response({ proposal: { ...candidate(), status: 'APPROVED', version: 6, document_id: 'screenplay-1' }, document: { id: 'screenplay-1', mode: 'SCREENPLAY', version: 1 } });
    throw new Error(`unexpected request ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  const client = creativeClient('novel-1', { sessionToken: 'original-session', scope: { workspaceId: 'w', projectId: 'novel-1', storylineId: 's', branchId: 'original-branch' } });
  const callbacks = { onDocument: vi.fn(), onDenied: vi.fn(), onBusyChange: vi.fn(), onDraftChange: vi.fn() };
  const view = render(<SourceAdaptationPanel client={client} chapter={chapter} sourceReady={true} canMutate={options.allowed ?? true} {...callbacks} />);
  fireEvent.click(screen.getByText('从已保存章节改编剧本'));
  return { fetchMock, view, client, ...callbacks, mutations: () => fetchMock.mock.calls.filter(([, init]) => init?.method !== 'GET') };
}
async function loaded() { await waitFor(() => expect(screen.queryByText('读取改编建议和本地路由…')).toBeNull()); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('requires explicit source and exact input review and never exposes synthetic routes as real models', async () => {
  const app = setup(); await loaded(); expect(app.mutations()).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('改编剧本标题'), { target: { value: 'Screenplay' } });
  const create = screen.getByRole('button', { name: '建立改编建议（尚不调用模型）' });
  expect((create as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已选择以上已保存版本作为改编来源')); fireEvent.click(create);
  await screen.findByText('Adapted screenplay · 建议 v1');
  expect(screen.queryByText(/mock-writer/)).toBeNull();
  fireEvent.change(screen.getByLabelText('改编本地模型'), { target: { value: 'r'.repeat(64) } });
  fireEvent.click(screen.getByRole('button', { name: '预览改编模型输入' }));
  await screen.findByText('预览未调用模型');
  const dispatch = screen.getByRole('button', { name: '确认改编调用' }); expect((dispatch as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对完整输入，允许本地调用一次并保存待审建议')); fireEvent.click(dispatch); fireEvent.click(dispatch);
  await screen.findByText('Job job-1 · RECORDED');
  expect(app.mutations().filter(([url]) => url.endsWith('/dispatch'))).toHaveLength(1);
  const preview = app.mutations().find(([url]) => url.endsWith('/preview'))!;
  expect(JSON.parse(String(preview[1]?.body))).toMatchObject({ allow_synthetic: false, expected_version: 1 });
  for (const [, init] of app.mutations()) expect(init?.headers).toMatchObject({ 'X-Session-Token': 'original-session', 'X-Branch-Id': 'original-branch' });
  expect(app.onDocument).not.toHaveBeenCalled();
});

it('keeps edited scenes and difference notes until separately reviewed, then opens only the returned screenplay', async () => {
  const app = setup({ rows: [candidate()] }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  fireEvent.change(screen.getByLabelText('改编场景 1 动作'), { target: { value: 'Human reviewed action.' } });
  fireEvent.change(screen.getByLabelText('改编差异 1 说明'), { target: { value: 'Human verified the visual interpretation.' } });
  expect(app.mutations()).toHaveLength(0);
  const adopt = screen.getByRole('button', { name: '审核并创建剧本' }); expect((adopt as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对原文、场景及删改推断，创建独立剧本文档')); fireEvent.click(adopt);
  await waitFor(() => expect(app.onDocument).toHaveBeenCalledOnce());
  const body = JSON.parse(String(app.mutations()[0][1]?.body));
  expect(body).toMatchObject({ expected_version: 5, reviewed_output_digest: 'c'.repeat(64) });
  expect(body.output.scenes[0].action).toBe('Human reviewed action.');
  expect(body.output.report.changes[0].note).toBe('Human verified the visual interpretation.');
  expect(app.mutations().some(([url]) => url.includes('/chapters/') || url.includes('/generation/'))).toBe(false);
});

it('preserves review edits after an uncertain write and does not automatically retry', async () => {
  const app = setup({ rows: [candidate()], override: (url) => url.endsWith('/review') ? Promise.reject(new Error('private provider information')) : undefined }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  fireEvent.change(screen.getByLabelText('改编场景 1 动作'), { target: { value: 'Keep this local review edit.' } });
  fireEvent.click(screen.getByLabelText('已核对原文、场景及删改推断，创建独立剧本文档')); fireEvent.click(screen.getByRole('button', { name: '审核并创建剧本' }));
  await screen.findByText(/本地审核编辑仍保留/);
  expect((screen.getByLabelText('改编场景 1 动作') as HTMLTextAreaElement).value).toBe('Keep this local review edit.');
  expect(screen.queryByText('private provider information')).toBeNull(); expect(app.mutations()).toHaveLength(1);
  expect(app.onDocument).not.toHaveBeenCalled();
});

it('ignores a late response after scope disposal', async () => {
  let complete!: (value: unknown) => void;
  const app = setup({ override: (url, init) => url.endsWith('/adaptation-proposals') && init.method === 'POST' ? new Promise(resolve => { complete = resolve; }) : undefined }); await loaded();
  fireEvent.change(screen.getByLabelText('改编剧本标题'), { target: { value: 'Source' } }); fireEvent.click(screen.getByLabelText('已选择以上已保存版本作为改编来源'));
  fireEvent.click(screen.getByRole('button', { name: '建立改编建议（尚不调用模型）' })); app.view.unmount();
  await act(async () => complete(response(proposal()))); expect(app.onDocument).not.toHaveBeenCalled();
});

it.each([401, 403])('purges protected contents on %i without reusing another identity', async status => {
  const app = setup({ override: url => url.endsWith('/model-routes') ? response({ code: 'DENIED' }, status) : undefined });
  await waitFor(() => expect(app.onDenied).toHaveBeenCalledOnce());
  expect(screen.queryByLabelText('改编剧本标题')).toBeNull(); expect(app.mutations()).toHaveLength(0);
});

it('keeps persisted proposals readable when optional model features are disabled', async () => {
  const app = setup({ rows: [proposal()], override: url => url.endsWith('/model-routes') ? response({ code: 'FEATURE_DISABLED' }, 404) : undefined });
  await loaded(); fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · DRAFT' }));
  expect(screen.getByText('Adapted screenplay · 建议 v1')).toBeTruthy();
  expect((screen.getByRole('button', { name: '预览改编模型输入' }) as HTMLButtonElement).disabled).toBe(true);
  expect(app.mutations()).toHaveLength(0);
});
