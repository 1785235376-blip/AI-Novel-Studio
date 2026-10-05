// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { RevisionIntelligencePanel } from './RevisionIntelligencePanel';
import { experimentalClient } from './api';
import type { Chapter } from '../api';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const chapter = { id: 'n:1', novel_id: 'n', title: '第一章', version: 4 } as Chapter;
const client = () => experimentalClient('n', { sessionToken: 'session' });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const blocks = ['甲🙂é', '乙保留', '丙结尾'].map((before, i) => ({ anchor_id: String(i).repeat(64), path: [i], before, after: before + '改', from_pos: i * 10 + 1, to_pos: i * 10 + 5, status: 'PENDING', lock_state: 'UNLOCKED', diff: [{ kind: 'replace', before, after: before + '改' }], diff_method: 'EXACT_CODEPOINT_DIFF' }));
const catalog = { chapters: [chapter], blocks: blocks.map(b => ({ ...b, text: b.before, supported: true })), branch_sources_available: true };
const selected = { chapter_id: chapter.id, chapter_version: 4, from_pos: 1, to_pos: 25, text: blocks.map(b => b.before).join('\n') };
const receipt = { selection: selected, selection_digest: 'a'.repeat(64), blocks, model_called: false, coordinate_contract: 'PROSEMIRROR_UTF16_V1' };
const proposal = { id: 'p', version: 1, status: 'REVIEW', source: { chapter_id: chapter.id, version: 4 }, blocks, origin: 'MANUAL_CANDIDATE', goal: '' };
function mount(fetch: ReturnType<typeof vi.fn>, props: Record<string, unknown> = {}) {
  vi.stubGlobal('fetch', fetch);
  return render(<RevisionIntelligencePanel client={client()} chapter={chapter} selection={{ from: 1, to: 25, text: selected.text }} saved onChapterSaved={vi.fn()} {...props} />);
}
const read = (url: string) => url.includes('/catalog') ? catalog : { items: [] };

it('captures original PM selection, previews two accepted blocks, and requires explicit confirmation', async () => {
  const onSaved = vi.fn();
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method === 'GET') return reply(read(url));
    if (url.endsWith('/selection')) return reply(receipt);
    if (url.endsWith('/proposals')) return reply(proposal, 201);
    if (url.endsWith('/preview')) { const body = JSON.parse(init.body as string); return reply({ ...body, preview_digest: 'b'.repeat(64), checkpoint_version: 4, creates_new_current_revision: true, pending_blocks: 1 }); }
    return reply({ proposal: { ...proposal, status: 'PARTIAL', version: 3 }, chapter: { ...chapter, version: 5 } });
  });
  mount(fetch, { onChapterSaved: onSaved });
  fireEvent.click(screen.getByRole('button', { name: '校验编辑器选区' }));
  fireEvent.change(await screen.findByLabelText('区块 1 候选文字'), { target: { value: '甲🙂é改' } });
  fireEvent.change(screen.getByLabelText('区块 3 候选文字'), { target: { value: '丙结尾改' } });
  fireEvent.click(screen.getByRole('button', { name: '保存候选并逐项审核' }));
  fireEvent.change(await screen.findByLabelText('区块 1 决定'), { target: { value: 'accept' } });
  fireEvent.change(screen.getByLabelText('区块 3 决定'), { target: { value: 'accept' } });
  fireEvent.click(screen.getByRole('button', { name: '预览所选区块与检查点' }));
  const apply = await screen.findByRole('button', { name: '确认仅应用所选决定' });
  expect((apply as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对所选区块与原版本检查点'));
  fireEvent.click(apply);
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ version: 5 })));
  const selectedBody = JSON.parse(fetch.mock.calls.find(([url]) => url.endsWith('/selection'))![1].body as string);
  expect(selectedBody).toEqual(selected);
  const applied = JSON.parse(fetch.mock.calls.find(([url]) => url.endsWith('/apply'))![1].body as string);
  expect(applied.accept_ids).toEqual([blocks[0].anchor_id, blocks[2].anchor_id]);
  expect(applied.reject_ids).toEqual([]); expect(applied.preview_digest).toBe('b'.repeat(64));
  expect(fetch.mock.calls.some(([url]) => url.includes('/generate'))).toBe(false);
});

it('preserves candidates on source conflict and invalidates stale approval after editing choices', async () => {
  const fetch = vi.fn(async (url: string, init: RequestInit) => init.method === 'GET' ? reply(url.endsWith('/proposals') ? { items: [proposal] } : read(url)) : url.endsWith('/preview') ? reply({ preview_digest: 'b'.repeat(64), checkpoint_version: 4, creates_new_current_revision: true, pending_blocks: 2, accept_ids: [blocks[0].anchor_id], reject_ids: [] }) : reply({ detail: { code: 'REVISION_CHAPTER_CHANGED' } }, 409));
  mount(fetch);
  fireEvent.click(await screen.findByRole('button', { name: '审核此修订' }));
  fireEvent.change(screen.getByLabelText('区块 1 决定'), { target: { value: 'accept' } });
  fireEvent.click(screen.getByRole('button', { name: '预览所选区块与检查点' }));
  fireEvent.click(await screen.findByLabelText('已核对所选区块与原版本检查点'));
  fireEvent.change(screen.getByLabelText('区块 2 决定'), { target: { value: 'reject' } });
  expect(screen.queryByRole('button', { name: '确认仅应用所选决定' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '预览所选区块与检查点' }));
  fireEvent.click(await screen.findByLabelText('已核对所选区块与原版本检查点'));
  fireEvent.click(screen.getByRole('button', { name: '确认仅应用所选决定' }));
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('REVISION_CHAPTER_CHANGED'));
  expect(screen.getByLabelText('区块 1 决定')).toBeTruthy();
  expect(screen.queryByRole('button', { name: '确认仅应用所选决定' })).toBeNull();
});

it('suppresses late selections after project or chapter navigation', async () => {
  let finish: (response: Response) => void = () => {};
  const fetch = vi.fn(async (url: string) => url.endsWith('/selection') ? new Promise<Response>(resolve => { finish = resolve; }) : reply(read(url)));
  const view = mount(fetch);
  fireEvent.click(screen.getByRole('button', { name: '校验编辑器选区' }));
  view.rerender(<RevisionIntelligencePanel client={client()} chapter={{ ...chapter, id: 'n:2' }} saved />);
  finish(reply(receipt));
  await waitFor(() => expect(screen.queryByLabelText('区块 1 候选文字')).toBeNull());
});

it('disables direct-navigation writes with no saved chapter and never calls a model by default', async () => {
  const fetch = vi.fn(async (url: string, _init?: RequestInit) => reply(read(url)));
  vi.stubGlobal('fetch', fetch); render(<RevisionIntelligencePanel client={client()} />);
  expect(screen.getByText('先选择章节')).toBeTruthy();
  expect((screen.getByRole('button', { name: '校验编辑器选区' }) as HTMLButtonElement).disabled).toBe(true);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
  expect(fetch.mock.calls.every(([, init]) => !init || (init as RequestInit).method === 'GET')).toBe(true);
});

it('shows stale/uncertain records without an enabled acceptance button', async () => {
  const fetch = vi.fn(async (url: string) => reply(url.endsWith('/proposals') ? { items: [{ ...proposal, stale: true, blocks: undefined, status: 'ACCEPTANCE_UNCERTAIN' }] } : read(url)));
  mount(fetch);
  const button = await screen.findByRole('button', { name: '审核此修订' });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/正文可能已保存/)).toBeTruthy();
});

it('reuses exact author preview and blocks extra generated paragraphs from automatic candidate import', async () => {
  const oneReceipt = { ...receipt, blocks: blocks.slice(0, 1) };
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.includes('/generation/job')) return reply({ id: 'job', status: 'COMPLETED', output: '全章一\n全章二', execution_mode: 'MOCK_ONLY' });
    if (init.method === 'GET') return reply(read(url));
    if (url.endsWith('/selection')) return reply(oneReceipt);
    if (url.endsWith('/preview')) return reply({ preview_digest: 'f'.repeat(64), chapter_version: 4, target: 'local', provider_id: 'local', model_id: 'configured', prompt_characters: 9, source_characters: 3, source_strategy: 'EXACT_SAVED_SELECTION', context_sections: [], privacy_omissions: [], creation_records: [], request: { prompt: '准确请求', context: {}, parameters: {}, system_instruction: null } });
    return reply({ job_id: 'job', status: 'QUEUED' }, 202);
  });
  mount(fetch, { generation: { enabled: true, novelId: 'n', context: { sessionToken: 'session' }, providerId: 'local', modelId: 'configured', profile: 'LOCAL_ONLY' } });
  fireEvent.click(screen.getByRole('button', { name: '校验编辑器选区' }));
  fireEvent.click(await screen.findByRole('button', { name: '检查真实生成请求' }));
  await screen.findByDisplayValue('准确请求');
  fireEvent.click(screen.getByLabelText('已核对实际请求，授权所选明确模型处理这一次选区'));
  fireEvent.click(screen.getByRole('button', { name: '生成一次选区草稿' }));
  fireEvent.click(await screen.findByRole('button', { name: '刷新选区生成任务' }));
  const button = await screen.findByRole('button', { name: '将对应段落导入候选，仍需审核' });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('区块 1 候选文字') as HTMLTextAreaElement).value).toBe(blocks[0].before);
  const generated = JSON.parse(fetch.mock.calls.find(([url]) => url.endsWith('/generate'))![1].body as string);
  expect(generated.revision_selection).toEqual(selected); expect(generated.revision_selection_digest).toBe(receipt.selection_digest);
  expect(generated.request_scope).toEqual({ source_mode: 'SELECTION_ONLY', include_automatic_context: false, include_style_reference: true, include_plan_reference: true });
  const previewed = JSON.parse(fetch.mock.calls.find(([url]) => url.endsWith('/author-context/preview'))![1].body as string);
  expect(generated.request_scope).toEqual(previewed.request_scope);
  expect(generated.preview_digest).toBe('f'.repeat(64)); expect(generated.provider_id).toBe('local');
});
