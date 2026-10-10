// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Chapter } from '../api';
import { NarrativeJudgeModelPanel } from './NarrativeJudgeModelPanel';
import { experimentalClient } from './api';
import { styleReviewClient, type JudgeModelPreview, type JudgeRun } from './styleReviewClient';

const route = { route_id: 'route-one', provider_id: 'mock', model_id: 'mock-writer', display_name: '内置测试模型', synthetic: true, available: true, reasons: [], identity: { model_version: 'synthetic-v1' } };
const preview: JudgeModelPreview = { preview_digest: 'a'.repeat(64), previewed_at: '2026-10-05T00:00:00Z', budget: { limit_microusd: 0 }, actor: 'owner', scope: {}, sources: { c1: { version: 3, digest: 'source' } }, request: { prompt: 'EXACT_VISIBLE_EVIDENCE', context: {} }, rubric: { id: 'narrative-model-evidence-v1', version: 1, boundary: 'Not independent' }, broker: { chosen: { ...route, price: { reserve_microusd: 0, source: 'Synthetic' } }, budget_version: 0, candidates: [route], decision_reason: 'ELIGIBLE' }, excluded: ['AUTOMATIC_CONTEXT'], max_output_bytes: 32768, timeout_seconds: 120, execution_available: true, quality_verification: 'SYNTHETIC_PROTOCOL_ONLY' };
const row: JudgeRun = { id: 'run-one', version: 2, status: 'COMPLETED', stale: false, findings: [], abstentions: [], verification: 'DETERMINISTIC_RULES', model_called: false };
const chapter = { id: 'c1', version: 3, title: '合成场景' } as Chapter;
const api = () => styleReviewClient(experimentalClient('novel-one', { sessionToken: 'test-session', scope: { workspaceId: 'w', projectId: 'novel-one', storylineId: 's', branchId: 'branch-one' } }));
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('opening a rule result does not load or call a model; explicit route selection only previews', async () => {
  const fetch = vi.fn(async (url: string) => response(url.endsWith('/catalog') ? { routes: [route] } : { ...row, model_preview: preview }));
  vi.stubGlobal('fetch', fetch); const onChanged = vi.fn();
  render(<NarrativeJudgeModelPanel api={api()} run={row} chapter={chapter} onChanged={onChanged} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '查看已注册本地审稿路线' }));
  await screen.findByLabelText('已注册本地审稿模型');
  expect((screen.getByRole('button', { name: '准备准确模型审稿预览' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('已注册本地审稿模型'), { target: { value: route.route_id } });
  fireEvent.click(screen.getByRole('button', { name: '准备准确模型审稿预览' }));
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  expect(fetch.mock.calls.map(([url]) => url)).toEqual(expect.arrayContaining([expect.stringContaining('/model/catalog'), expect.stringContaining('/model/preview')]));
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/dispatch'))).toBe(false);
});

it('requires a separate reviewed exact receipt and suppresses synchronous repeated sends', async () => {
  const fetch = vi.fn(async () => response(row)); vi.stubGlobal('fetch', fetch); const onChanged = vi.fn();
  render(<NarrativeJudgeModelPanel api={api()} run={{ ...row, model_preview: preview }} chapter={chapter} onChanged={onChanged} />);
  expect((screen.getByRole('button', { name: '明确发送此次本地模型审稿' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('准确模型请求（含完整选中证据）') as HTMLTextAreaElement).value).toContain('EXACT_VISIBLE_EVIDENCE');
  fireEvent.click(screen.getByLabelText('已核对完整证据、版本、模型身份与零费用预占'));
  const button = screen.getByRole('button', { name: '明确发送此次本地模型审稿' }); fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  expect(fetch).toHaveBeenCalledOnce();
  const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toContain('/runs/run-one/model/dispatch');
  expect(JSON.parse(init.body as string)).toEqual({ expected_version: 2, reviewed_preview_digest: preview.preview_digest });
  expect(init.headers).toMatchObject({ 'X-Session-Token': 'test-session', 'X-Branch-Id': 'branch-one' });
});

it('source revision changes hide the old preview and remove consent before any send', () => {
  vi.stubGlobal('fetch', vi.fn()); const stable = api(); const run = { ...row, model_preview: preview };
  const view = render(<NarrativeJudgeModelPanel api={stable} run={run} chapter={chapter} onChanged={() => {}} />);
  fireEvent.click(screen.getByLabelText('已核对完整证据、版本、模型身份与零费用预占'));
  view.rerender(<NarrativeJudgeModelPanel api={stable} run={run} chapter={{ ...chapter, version: 4 }} onChanged={() => {}} />);
  expect(screen.queryByRole('region', { name: '准确模型审稿预览' })).toBeNull();
  expect(screen.queryByRole('button', { name: '明确发送此次本地模型审稿' })).toBeNull();
});

it('missing dependencies preserves rules and shows a visible blocker without auto retry', async () => {
  const fetch = vi.fn(async () => response({ detail: { code: 'EXPERIMENTAL_DISABLED' } }, 404)); vi.stubGlobal('fetch', fetch);
  render(<NarrativeJudgeModelPanel api={api()} run={row} chapter={chapter} onChanged={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: '查看已注册本地审稿路线' }));
  await screen.findByText(/若缺少主机会话/); expect(fetch).toHaveBeenCalledOnce();
  expect(screen.queryByRole('button', { name: '明确发送此次本地模型审稿' })).toBeNull();
});

it('unknown execution exposes original-job reconciliation and never another dispatch', async () => {
  const fetch = vi.fn(async () => response(row)); vi.stubGlobal('fetch', fetch);
  render(<NarrativeJudgeModelPanel api={api()} run={{ ...row, model_preview: preview, model_execution: { job_id: 'original-job', reservation_id: 'held', status: 'UNKNOWN', receipt_state: 'UNKNOWN_NO_AUTOMATIC_REPLAY', model_called: false, usage_state: 'UNKNOWN' } }} chapter={chapter} onChanged={() => {}} />);
  expect(screen.getByText(/原任务状态未知/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: '明确发送此次本地模型审稿' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '查询原任务并核对模型证据' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
  expect((fetch.mock.calls[0] as unknown as [string])[0]).toContain('/model/refresh');
});

it('late responses cannot update a departed scope', async () => {
  let complete!: (response: Response) => void; const fetch = vi.fn(() => new Promise<Response>(resolve => { complete = resolve; }));
  vi.stubGlobal('fetch', fetch); const onChanged = vi.fn();
  const view = render(<NarrativeJudgeModelPanel api={api()} run={{ ...row, model_preview: preview }} chapter={chapter} onChanged={onChanged} />);
  fireEvent.click(screen.getByLabelText('已核对完整证据、版本、模型身份与零费用预占'));
  fireEvent.click(screen.getByRole('button', { name: '明确发送此次本地模型审稿' }));
  view.unmount(); await act(async () => complete(response(row)));
  expect(onChanged).not.toHaveBeenCalled();
});
