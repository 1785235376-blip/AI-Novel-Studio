// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { LanguageTranslationPanel } from './LanguageTranslationPanel';
import { MultilingualEditionsPanel } from './MultilingualEditionsPanel';
import { experimentalClient } from './api';
import { multilingualEditionsClient, type LanguageEdition, type TranslationRun } from './multilingualEditionsClient';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const edition: LanguageEdition = { id: 'ed', version: 3, status: 'DRAFT', title: 'Arabic edition', target_language: 'ar', source_language: 'zh-Hant', direction: 'rtl', stale: false, content_withheld: false, rules: [], segments: [{ id: 'seg', chapter_id: 'ch', source_version: 2, path: [0], from_pos: 1, to_pos: 5, source_text: '阿青🙂', target_text: '', note: '', status: 'DRAFT', issues: [] }] };
const route = { route_id: 'r', provider_id: 'mock', model_id: 'mock-writer', display_name: 'Synthetic', available: true, reasons: [], synthetic: true, verification: 'SYNTHETIC_PROTOCOL_ONLY' };
const candidate = { text: 'مرحبا🙂é', digest: 'b'.repeat(64), job_id: 'job-original', request_digest: 'c'.repeat(64), applied: false as const, quality_verification: 'NOT_RUN' };
const makeRun = (): TranslationRun => ({ id: 'original-run', version: 1, edition_id: 'ed', edition_version: 3, segment_id: 'seg', status: 'PREVIEW', stale: false, content_withheld: false, automatic_retry: false, quality_verification: 'NOT_RUN', execution: null, candidate: null, preview: { preview_digest: 'a'.repeat(64), execution_available: true, max_output_bytes: 20000, timeout_seconds: 300, excluded: ['OTHER_SEGMENTS'], request: { prompt: 'Only 阿青🙂 with approved terms', context: {} }, broker: { id: 'quote', version: 1, budget_version: 0, chosen: { ...route, price: { currency: 'USD', reserve_microusd: 0, source: 'Builtin synthetic' } }, candidates: [route] } } });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
function fixture(override?: (url: string, init: RequestInit) => Promise<Response> | Response | undefined) {
  let run: TranslationRun | undefined;
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    const replaced = override?.(url, init); if (replaced) return replaced;
    if (url.endsWith('/translation/routes')) return reply({ items: [route] });
    if (url.endsWith('/translations')) return reply({ items: run ? [run] : [], truncated: false });
    if (url.endsWith('/translation-preview')) { run = makeRun(); return reply(run, 201); }
    if (url.endsWith('/dispatch')) { run = { ...run!, version: 2, status: 'QUEUED', execution: { job_id: 'job-original', reservation_id: 'ledger', receipt_state: 'RECORDED', model_called: false, usage_state: 'UNKNOWN', accounting: null } }; return reply(run); }
    if (url.endsWith('/refresh')) { run = { ...run!, version: 3, status: 'CANDIDATE', candidate, execution: { ...run!.execution!, model_called: true, accounting: { status: 'SETTLED', cost_state: 'KNOWN_SYNTHETIC_ZERO', actual_microusd: 0 } } }; return reply(run); }
    if (url.endsWith('/cancel')) { run = { ...run!, version: run!.version + 1, status: 'CANCELLED', candidate: null }; return reply(run); }
    if (url.endsWith('/adopt')) return reply({ ...edition, version: 4, segments: [{ ...edition.segments![0], target_text: candidate.text }] });
    if (url.endsWith('/catalog')) return reply({ chapters: [], translation: { available: false }, branch_sources_available: true });
    if (url.endsWith('/language-editions')) return reply({ items: [edition] });
    return reply({ detail: { code: 'UNEXPECTED' } }, 500);
  });
  vi.stubGlobal('fetch', fetch);
  const client = experimentalClient('n', { sessionToken: 'host', scope: { branchId: 'branch' } as any });
  const api = multilingualEditionsClient(client); const perform = vi.fn(async (fn: () => Promise<LanguageEdition>) => fn());
  return { fetch, client, props: { api, edition, segment: edition.segments![0], blocked: false, perform } };
}
async function preview() {
  fireEvent.click(screen.getByRole('button', { name: '打开本段模型翻译' })); await screen.findByRole('option', { name: /Synthetic/ });
  fireEvent.change(screen.getByLabelText('本段翻译本地模型路线'), { target: { value: 'r' } });
  expect((screen.getByRole('button', { name: '预览本段翻译请求与费用' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('允许合成协议测试路线，不代表真实翻译质量')); fireEvent.click(screen.getByRole('button', { name: '预览本段翻译请求与费用' }));
  await screen.findByLabelText('本段翻译精确提示词');
}
async function dispatch() {
  const button = screen.getByRole('button', { name: '明确启动本段翻译' }); expect((button as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对本段原文、术语、目标语言、本地路线和零成本预留')); fireEvent.click(button); await screen.findByText(/原模型任务 job-original/);
}
it('exact preview, explicit single dispatch, original recovery and separate adopt consent', async () => {
  const e = fixture(); render(<StrictMode><LanguageTranslationPanel {...e.props} /></StrictMode>); expect(e.fetch).not.toHaveBeenCalled(); await preview();
  expect((screen.getByLabelText('本段翻译精确上下文') as HTMLTextAreaElement).value).toBe('{}'); expect(e.fetch.mock.calls.some(([url]) => url.endsWith('/dispatch'))).toBe(false); await dispatch();
  fireEvent.click(screen.getByRole('button', { name: '收起本段模型翻译' })); fireEvent.click(screen.getByRole('button', { name: '打开本段模型翻译' })); fireEvent.click(await screen.findByRole('button', { name: /翻译任务 original/ }));
  fireEvent.click(screen.getByRole('button', { name: '刷新原翻译任务并核对候选' })); const text = await screen.findByLabelText('本段未审核翻译候选'); expect(text.getAttribute('dir')).toBe('rtl');
  const adopt = screen.getByRole('button', { name: '仅采用到本段译文草稿' }); expect((adopt as HTMLButtonElement).disabled).toBe(true); expect(e.props.perform).not.toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText('确认将候选替换本段已保存译文为草稿，之后另行审核')); fireEvent.click(adopt); await waitFor(() => expect(e.props.perform).toHaveBeenCalledOnce());
  const [, request] = e.fetch.mock.calls.find(([url]) => url.endsWith('/adopt'))!; expect(JSON.parse(String(request.body))).toEqual({ expected_version: 3, expected_edition_version: 3, candidate_digest: candidate.digest });
  expect(new Headers(request.headers).get('X-Branch-Id')).toBe('branch'); expect(e.fetch.mock.calls.filter(([url]) => url.endsWith('/dispatch'))).toHaveLength(1); expect(e.fetch.mock.calls.some(([url]) => /chapters|\/accept$/.test(url))).toBe(false);
});
it('unsaved input invalidates consent and blocks dispatch without dropping receipts', async () => {
  const e = fixture(); const view = render(<LanguageTranslationPanel {...e.props} />); await preview(); fireEvent.click(screen.getByLabelText('已核对本段原文、术语、目标语言、本地路线和零成本预留'));
  view.rerender(<LanguageTranslationPanel {...e.props} blocked />); expect((screen.getByRole('button', { name: '明确启动本段翻译' }) as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<LanguageTranslationPanel {...e.props} />); expect((screen.getByRole('button', { name: '明确启动本段翻译' }) as HTMLButtonElement).disabled).toBe(true);
});
it('cancelled tasks expose no adopt or replay action', async () => {
  const e = fixture(); render(<LanguageTranslationPanel {...e.props} />); await preview(); await dispatch(); fireEvent.click(screen.getByRole('button', { name: '取消本段翻译任务' })); await screen.findByText('状态 CANCELLED');
  expect(screen.queryByRole('button', { name: '明确启动本段翻译' })).toBeNull(); expect(screen.queryByRole('button', { name: '仅采用到本段译文草稿' })).toBeNull();
});
it('late preview after closing stays hidden and never dispatches', async () => {
  let finish!: (value: Response) => void; const e = fixture(url => url.endsWith('/translation-preview') ? new Promise<Response>(resolve => { finish = resolve; }) : undefined); render(<LanguageTranslationPanel {...e.props} />);
  fireEvent.click(screen.getByRole('button', { name: '打开本段模型翻译' })); await screen.findByRole('option', { name: /Synthetic/ }); fireEvent.change(screen.getByLabelText('本段翻译本地模型路线'), { target: { value: 'r' } });
  fireEvent.click(screen.getByLabelText('允许合成协议测试路线，不代表真实翻译质量')); fireEvent.click(screen.getByRole('button', { name: '预览本段翻译请求与费用' })); fireEvent.click(screen.getByRole('button', { name: '收起本段模型翻译' })); finish(reply(makeRun()));
  await waitFor(() => expect(screen.queryByLabelText('本段翻译精确提示词')).toBeNull()); expect(e.fetch.mock.calls.some(([url]) => url.endsWith('/dispatch'))).toBe(false);
});
it('adoption updates visible saved draft while requiring separate submit and review', async () => {
  const e = fixture(); render(<MultilingualEditionsPanel client={e.client} />); fireEvent.click(await screen.findByRole('button', { name: /Arabic edition · ar/ })); await preview(); await dispatch();
  fireEvent.click(screen.getByRole('button', { name: '刷新原翻译任务并核对候选' })); await screen.findByLabelText('本段未审核翻译候选'); fireEvent.click(screen.getByLabelText('确认将候选替换本段已保存译文为草稿，之后另行审核')); fireEvent.click(screen.getByRole('button', { name: '仅采用到本段译文草稿' }));
  await screen.findByText('候选已采用到本段译文草稿，仍需提交与逐段审核。');
  await waitFor(() => {
    expect((screen.getByLabelText('第 1 段译文') as HTMLTextAreaElement).value).toBe(candidate.text);
    expect((screen.getByRole('button', { name: '提交本段审核' }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByText('译文输入尚未保存。', { exact: false })).toBeNull();
  });
});
