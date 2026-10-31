// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SourceAdaptationPanel } from './SourceAdaptationPanel';
import { creativeClient, type AdaptationProposal } from './client';
import { newScene } from './types';
import { ApiError, type Chapter } from '../api';

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
function setup(options: { rows?: AdaptationProposal[]; override?: (url: string, init: RequestInit) => unknown; allowed?: boolean; savedChapters?: Chapter[]; activeChapter?: Chapter; loadSavedChapter?: (id: string) => Promise<Chapter> } = {}) {
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
  const view = render(<SourceAdaptationPanel client={client} chapter={options.activeChapter || chapter} savedChapters={options.savedChapters} savedChaptersReady={!!options.savedChapters} loadSavedChapter={options.loadSavedChapter} sourceReady={true} canMutate={options.allowed ?? true} {...callbacks} />);
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

it('shows private asset version and passive receipt without another save action', async () => {
  const row = { ...candidate(), asset_output: { contract: 'creative-adaptation-text-asset/1', state: 'DRAFT', asset_id: 'asset-1', version: 1, sha256: 'a'.repeat(64), execution_receipt: { quality_verification: 'NOT_RUN', model_id: 'verified-model' } } };
  const app = setup({ rows: [row] }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: /Adapted screenplay · NEEDS_REVIEW/ }));
  expect(screen.getByText('原始输出已归档为私有草稿')).toBeTruthy();
  expect(screen.getByText(/TextAsset asset-1 · v1/)).toBeTruthy();
  expect(screen.getByText('模型、输入、参数与工作流回执（未验证质量）')).toBeTruthy();
  expect(app.mutations()).toHaveLength(0);
});

it('keeps a committed screenplay distinct from its pending asset review projection', async () => {
  const row = proposal({ status: 'APPROVED', document_id: 'screenplay-1', asset_output: { contract: 'creative-adaptation-text-asset/1', state: 'INCOMPLETE', asset_id: null, version: null } });
  const app = setup({ rows: [row] }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: /Adapted screenplay · APPROVED/ }));
  expect(screen.getByText('资产归档尚未完成')).toBeTruthy();
  expect(screen.getByText(/剧本文档已保存，资产审核版本仍待同步/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: '审核并创建剧本' })).toBeNull();
  expect(app.mutations()).toHaveLength(0);
});

const secondChapter: Chapter = { ...chapter, id: 'chapter-2', title: 'Second source', content: 'The visitor leaves.', version: 7, number: 2 };
function orderedProposal(patch: Partial<AdaptationProposal> = {}) {
  return proposal({ ...candidate(), source_mode: 'ORDERED_CHAPTERS', ordered_sources_digest: 'e'.repeat(64), sources: [chapter, secondChapter].map((row, index) => ({ ordinal: index + 1, chapter_id: row.id, source_version: row.version, source_digest: 'a'.repeat(64), selected_text: row.content, selection_digest: 'b'.repeat(64), native_source_digest: 'a'.repeat(64) })), ...patch });
}
it('creates ordered full chapter snapshots with exact versions and resets confirmation after reordering', async () => {
  const app = setup({ savedChapters: [chapter, secondChapter] }); await loaded();
  fireEvent.change(screen.getByLabelText('改编来源方式'), { target: { value: 'ordered' } });
  fireEvent.change(screen.getByLabelText('改编剧本标题'), { target: { value: 'Ordered screenplay' } });
  fireEvent.click(screen.getByLabelText('选择来源 Saved source'));
  fireEvent.click(screen.getByLabelText('选择来源 Second source'));
  fireEvent.click(screen.getByLabelText('已选择以上已保存版本作为改编来源'));
  fireEvent.click(screen.getByLabelText('上移来源 2'));
  const create = screen.getByRole('button', { name: '建立改编建议（尚不调用模型）' });
  expect((create as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已选择以上已保存版本作为改编来源')); fireEvent.click(create);
  await waitFor(() => expect(app.mutations()).toHaveLength(1));
  expect(JSON.parse(String(app.mutations()[0][1]?.body))).toEqual({ title: 'Ordered screenplay', instruction: '', sources: [{ chapter_id: secondChapter.id, expected_source_version: 7 }, { chapter_id: chapter.id, expected_source_version: 3 }] });
});
it.each(['individual', 'total', 'missing'] as const)('blocks invalid ordered sources (%s) without truncating', async mode => {
  const saved = mode === 'total' ? Array.from({ length: 5 }, (_, i) => ({ ...chapter, id: `chapter-${i}`, title: `Source ${i}`, content: 'x'.repeat(8000) })) : [chapter, { ...secondChapter, content: mode === 'individual' ? 'x'.repeat(8001) : '' }];
  const app = setup({ savedChapters: saved }); await loaded();
  fireEvent.change(screen.getByLabelText('改编来源方式'), { target: { value: 'ordered' } });
  fireEvent.change(screen.getByLabelText('改编剧本标题'), { target: { value: 'Bounded' } });
  for (const row of saved) fireEvent.click(screen.getByLabelText(`选择来源 ${row.title}`));
  fireEvent.click(screen.getByLabelText('已选择以上已保存版本作为改编来源'));
  expect((screen.getByRole('button', { name: '建立改编建议（尚不调用模型）' }) as HTMLButtonElement).disabled).toBe(true);
  expect(app.mutations()).toHaveLength(0);
});
it('reopens ordered review independent of the active editor and preserves edits when any source changes', async () => {
  const other = { ...chapter, id: 'unrelated', title: 'Unrelated editor' };
  const app = setup({ rows: [orderedProposal()], savedChapters: [chapter, secondChapter], activeChapter: other }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  const action = screen.getByLabelText('改编场景 1 动作');
  expect(action.closest('fieldset')?.disabled).toBe(false);
  fireEvent.change(action, { target: { value: 'Preserve ordered review edit' } });
  app.view.rerender(<SourceAdaptationPanel client={app.client} chapter={other} savedChapters={[chapter, { ...secondChapter, version: 8 }]} savedChaptersReady={true} sourceReady={false} canMutate={true} onDocument={app.onDocument} onDenied={app.onDenied} onBusyChange={app.onBusyChange} onDraftChange={app.onDraftChange} />);
  expect((screen.getByLabelText('改编场景 1 动作') as HTMLTextAreaElement).value).toBe('Preserve ordered review edit');
  expect(action.closest('fieldset')?.disabled).toBe(true);
  expect(screen.getByText(/请核对所有原始来源/)).toBeTruthy();
  expect(app.mutations()).toHaveLength(0);
});
it('requires at least two sources and caps ordered selection at sixteen', async () => {
  const saved = Array.from({ length: 17 }, (_, i) => ({ ...chapter, id: `source-${i}`, title: `Chapter ${i}` }));
  const app = setup({ savedChapters: saved }); await loaded();
  fireEvent.change(screen.getByLabelText('改编来源方式'), { target: { value: 'ordered' } });
  fireEvent.change(screen.getByLabelText('改编剧本标题'), { target: { value: 'Bounded selection' } });
  fireEvent.click(screen.getByLabelText('选择来源 Chapter 0'));
  fireEvent.click(screen.getByLabelText('已选择以上已保存版本作为改编来源'));
  expect((screen.getByRole('button', { name: '建立改编建议（尚不调用模型）' }) as HTMLButtonElement).disabled).toBe(true);
  for (const row of saved.slice(1, 16)) fireEvent.click(screen.getByLabelText(`选择来源 ${row.title}`));
  expect((screen.getByLabelText('选择来源 Chapter 16') as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByLabelText('选择来源 Chapter 0') as HTMLInputElement).disabled).toBe(false);
  expect(app.mutations()).toHaveLength(0);
});
it('retains source ordinals when adopting human-reviewed ordered output', async () => {
  const row = orderedProposal();
  row.output!.scenes[0].source_ordinal = 2; row.output!.report.changes[0].source_ordinal = 2;
  const app = setup({ rows: [row], savedChapters: [chapter, secondChapter], activeChapter: { ...chapter, id: 'another-editor' } }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  expect(screen.getByText('场景 1 · 来源 2')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('改编场景 1 动作'), { target: { value: 'Review the second chapter scene.' } });
  fireEvent.click(screen.getByLabelText('已核对原文、场景及删改推断，创建独立剧本文档'));
  fireEvent.click(screen.getByRole('button', { name: '审核并创建剧本' }));
  await waitFor(() => expect(app.onDocument).toHaveBeenCalledOnce());
  const output = JSON.parse(String(app.mutations()[0][1]?.body)).output;
  expect(output.scenes[0].source_ordinal).toBe(2); expect(output.report.changes[0].source_ordinal).toBe(2);
});

it('resolves complete source detail before allowing a list-trimmed chapter at the size boundary', async () => {
  const listed = { ...chapter, content: 'x'.repeat(8000) };
  const detail = { ...listed, content: listed.content + '\n' };
  const loader = vi.fn(async (id: string) => id === chapter.id ? detail : secondChapter);
  const app = setup({ savedChapters: [listed, secondChapter], loadSavedChapter: loader }); await loaded();
  fireEvent.change(screen.getByLabelText('改编来源方式'), { target: { value: 'ordered' } });
  fireEvent.change(screen.getByLabelText('改编剧本标题'), { target: { value: 'Exact source' } });
  fireEvent.click(screen.getByLabelText('选择来源 Saved source')); fireEvent.click(screen.getByLabelText('选择来源 Second source'));
  await screen.findByText(/Saved source · v3 · 8001 字符/);
  fireEvent.click(screen.getByLabelText('已选择以上已保存版本作为改编来源'));
  expect((screen.getByRole('button', { name: '建立改编建议（尚不调用模型）' }) as HTMLButtonElement).disabled).toBe(true);
  expect(app.mutations()).toHaveLength(0);
});
it('reopens full saved sources when chapter lists strip terminal newlines', async () => {
  const full = { ...chapter, content: chapter.content + '\n' };
  const row = orderedProposal(); row.sources![0].selected_text = full.content;
  const loader = vi.fn(async (id: string) => id === chapter.id ? full : secondChapter);
  setup({ rows: [row], savedChapters: [chapter, secondChapter], loadSavedChapter: loader }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  await waitFor(() => expect(screen.getByLabelText('改编场景 1 动作').closest('fieldset')?.disabled).toBe(false));
  expect(loader).toHaveBeenCalledWith(chapter.id); expect(loader).toHaveBeenCalledWith(secondChapter.id);
});
it('quarantines dirty cached output after privacy-only invalidation and reveals it only after exact revalidation', async () => {
  let accessible = true;
  const original = orderedProposal();
  const app = setup({ savedChapters: [chapter, secondChapter], override: (url, init) => url.endsWith('/adaptation-proposals') && init.method === 'GET' ? response({ items: accessible ? [original] : [] }) : undefined }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  fireEvent.change(screen.getByLabelText('改编场景 1 动作'), { target: { value: 'Private retained edit' } });
  accessible = false; fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' })); await loaded();
  expect(screen.queryByLabelText('改编建议审核')).toBeNull();
  expect(screen.queryByText('Private retained edit')).toBeNull();
  expect(screen.queryByRole('button', { name: '导出改编审核草稿' })).toBeNull();
  expect(app.onDraftChange).toHaveBeenLastCalledWith({ protected_review_pending: true });
  accessible = true; fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' })); await loaded();
  expect((screen.getByLabelText('改编场景 1 动作') as HTMLTextAreaElement).value).toBe('Private retained edit');
  expect(app.mutations()).toHaveLength(0);
});
it('keeps cached output hidden after a failed reload and requires explicit discard for a changed revision', async () => {
  let state = 0;
  const original = candidate();
  const app = setup({ override: (url, init) => url.endsWith('/adaptation-proposals') && init.method === 'GET' ? state === 1 ? Promise.reject(new Error('offline')) : response({ items: [state === 2 ? { ...original, version: original.version + 1 } : original] }) : undefined }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  fireEvent.change(screen.getByLabelText('改编场景 1 动作'), { target: { value: 'Keep hidden' } });
  state = 1; fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' })); await loaded();
  expect(screen.queryByLabelText('改编建议审核')).toBeNull();
  expect(screen.queryByRole('button', { name: '导出改编审核草稿' })).toBeNull();
  state = 2; fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' })); await loaded();
  expect(screen.queryByLabelText('改编建议审核')).toBeNull();
  fireEvent.click(screen.getByLabelText('确认放弃隐藏的审核草稿'));
  fireEvent.click(screen.getByRole('button', { name: '放弃隐藏草稿' }));
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  expect(screen.getByText('Adapted screenplay · 建议 v6')).toBeTruthy();
  expect((screen.getByLabelText('改编场景 1 动作') as HTMLTextAreaElement).value).not.toBe('Keep hidden');
  expect(app.mutations()).toHaveLength(0);
});
it('does not revive cached output from an A to B to A late list response', async () => {
  let late!: (value: unknown) => void;
  let calls = 0;
  const app = setup({ override: (url, init) => url.endsWith('/adaptation-proposals') && init.method === 'GET' ? ++calls === 2 ? new Promise(resolve => { late = resolve; }) : response({ items: calls === 1 ? [candidate()] : [] }) : undefined }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  fireEvent.change(screen.getByLabelText('改编场景 1 动作'), { target: { value: 'Scope A private edit' } });
  fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' }));
  const other = creativeClient('novel-1', { sessionToken: 'other-session', scope: { workspaceId: 'w', projectId: 'novel-1', storylineId: 's', branchId: 'branch-B' } });
  const props = { chapter, sourceReady: true, canMutate: true, onDocument: app.onDocument, onDenied: app.onDenied, onBusyChange: app.onBusyChange, onDraftChange: app.onDraftChange };
  app.view.rerender(<SourceAdaptationPanel client={other} {...props} />); await loaded();
  app.view.rerender(<SourceAdaptationPanel client={app.client} {...props} />); await loaded();
  await act(async () => late(response({ items: [candidate()] })));
  expect(screen.queryByLabelText('改编建议审核')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' })).toBeNull();
  expect(app.onDocument).not.toHaveBeenCalled();
});
it('quarantines a mutation conflict without discarding or exporting dirty review content', async () => {
  const app = setup({ rows: [candidate()], override: url => url.endsWith('/review') ? response({ code: 'ADAPTATION_SOURCE_CHANGED' }, 409) : undefined }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  fireEvent.change(screen.getByLabelText('改编场景 1 动作'), { target: { value: 'Conflicted private review' } });
  fireEvent.click(screen.getByLabelText('已核对原文、场景及删改推断，创建独立剧本文档')); fireEvent.click(screen.getByRole('button', { name: '审核并创建剧本' }));
  await waitFor(() => expect(screen.queryByLabelText('改编建议审核')).toBeNull());
  expect(screen.queryByRole('button', { name: '导出改编审核草稿' })).toBeNull();
  expect(app.onDraftChange).toHaveBeenLastCalledWith({ protected_review_pending: true });
  expect(app.mutations()).toHaveLength(1);
  expect(app.onDocument).not.toHaveBeenCalled();
});
it.each(['404', 'network', 'wrong-id', 'version', 'archived', 'content'] as const)('quarantines dirty output on authoritative detail %s until explicit valid refresh', async mode => {
  let invalid = false;
  const loader = vi.fn(async (id: string) => {
    if (id !== chapter.id) return secondChapter;
    if (!invalid) return chapter;
    if (mode === '404') throw new ApiError({ status: 404, code: 'SOURCE_NOT_FOUND', message: 'Source unavailable' });
    if (mode === 'network') throw new Error('offline');
    return { ...chapter, ...(mode === 'wrong-id' ? { id: 'wrong' } : mode === 'version' ? { version: 4 } : mode === 'archived' ? { is_archived: true } : { content: 'Changed source' }) };
  });
  const app = setup({ rows: [orderedProposal()], savedChapters: [chapter, secondChapter], loadSavedChapter: loader }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  const action = await screen.findByLabelText('改编场景 1 动作');
  fireEvent.change(action, { target: { value: 'Retained secret edit' } });
  invalid = true; fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' })); await loaded();
  await waitFor(() => expect(loader.mock.calls.length).toBeGreaterThanOrEqual(4));
  expect(screen.queryByLabelText('改编建议审核')).toBeNull();
  expect(screen.queryByRole('button', { name: '导出改编审核草稿' })).toBeNull();
  expect(app.onDraftChange).toHaveBeenLastCalledWith({ protected_review_pending: true });
  invalid = false; fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' })); await loaded();
  expect((await screen.findByLabelText('改编场景 1 动作') as HTMLTextAreaElement).value).toBe('Retained secret edit');
  expect(app.mutations()).toHaveLength(0);
});
it.each(['detail-first', 'list-first'] as const)('keeps independent list/detail gates closed when failed detail resolves %s', async order => {
  let refreshing = false, finishList!: (value: unknown) => void, failDetail!: (error: unknown) => void;
  const loader = vi.fn(async (id: string) => {
    if (id !== chapter.id) return secondChapter;
    if (!refreshing) return chapter;
    if (order === 'detail-first') throw new Error('offline');
    return await new Promise<Chapter>((_resolve, reject) => { failDetail = reject; });
  });
  const app = setup({ rows: [orderedProposal()], savedChapters: [chapter, secondChapter], loadSavedChapter: loader, override: (url, init) => refreshing && order === 'detail-first' && url.endsWith('/adaptation-proposals') && init.method === 'GET' ? new Promise(resolve => { finishList = resolve; }) : undefined }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  fireEvent.change(await screen.findByLabelText('改编场景 1 动作'), { target: { value: 'Do not expose' } });
  refreshing = true; fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' }));
  if (order === 'detail-first') { await screen.findByText(/操作回执未确认/); await act(async () => finishList(response({ items: [orderedProposal()] }))); }
  else { await loaded(); await act(async () => failDetail(new Error('offline'))); }
  expect(screen.queryByLabelText('改编建议审核')).toBeNull();
  expect(screen.queryByRole('button', { name: '导出改编审核草稿' })).toBeNull();
  expect(app.onDraftChange).toHaveBeenLastCalledWith({ protected_review_pending: true });
});
it('ignores late A detail after A to B to A source changes and preserves hidden dirty output', async () => {
  let phase = 'initial', late!: (value: Chapter) => void;
  const loader = vi.fn(async (id: string) => {
    if (id !== chapter.id) return secondChapter;
    if (phase === 'late') return await new Promise<Chapter>(resolve => { late = resolve; });
    if (phase === 'B') return { ...chapter, version: 4 };
    if (phase === 'failed-A') throw new Error('Current A is not verified');
    return chapter;
  });
  const app = setup({ rows: [orderedProposal()], savedChapters: [chapter, secondChapter], loadSavedChapter: loader }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  fireEvent.change(await screen.findByLabelText('改编场景 1 动作'), { target: { value: 'ABA retained edit' } });
  phase = 'late'; fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' })); await loaded();
  const props = { client: app.client, chapter, loadSavedChapter: loader, savedChaptersReady: true, sourceReady: true, canMutate: true, onDocument: app.onDocument, onDenied: app.onDenied, onBusyChange: app.onBusyChange, onDraftChange: app.onDraftChange };
  phase = 'B'; app.view.rerender(<SourceAdaptationPanel {...props} savedChapters={[{ ...chapter, version: 4 }, secondChapter]} />);
  await act(async () => {});
  phase = 'failed-A'; app.view.rerender(<SourceAdaptationPanel {...props} savedChapters={[chapter, secondChapter]} />);
  await screen.findByText(/操作回执未确认/);
  await act(async () => late(chapter));
  expect(screen.queryByLabelText('改编建议审核')).toBeNull();
  expect(app.onDraftChange).toHaveBeenLastCalledWith({ protected_review_pending: true });
  phase = 'recovered'; fireEvent.click(screen.getByRole('button', { name: '刷新改编建议列表' })); await loaded();
  expect((await screen.findByLabelText('改编场景 1 动作') as HTMLTextAreaElement).value).toBe('ABA retained edit');
  expect(app.mutations()).toHaveLength(0);
});
it('keeps a newly selected list row private until its exact detail read completes', async () => {
  let finish!: (value: Chapter) => void;
  const loader = vi.fn(async (id: string) => id === chapter.id ? await new Promise<Chapter>(resolve => { finish = resolve; }) : secondChapter);
  const app = setup({ rows: [orderedProposal()], savedChapters: [chapter, secondChapter], loadSavedChapter: loader }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  await waitFor(() => expect(loader).toHaveBeenCalledWith(chapter.id));
  expect(screen.queryByLabelText('改编建议审核')).toBeNull();
  expect(app.onDraftChange).toHaveBeenLastCalledWith({ protected_review_pending: true });
  await act(async () => finish(chapter));
  expect(screen.getByLabelText('改编建议审核')).toBeTruthy();
});
it('does not quarantine valid proposal content for an unrelated creation-only detail failure', async () => {
  const unrelated = { ...chapter, id: 'creation-only', title: 'Creation only' };
  const loader = vi.fn(async (id: string) => { if (id === unrelated.id) throw new Error('Creation source unavailable'); return id === chapter.id ? chapter : secondChapter; });
  setup({ rows: [orderedProposal()], savedChapters: [chapter, secondChapter, unrelated], loadSavedChapter: loader }); await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Adapted screenplay · NEEDS_REVIEW' }));
  await screen.findByLabelText('改编建议审核');
  fireEvent.change(screen.getByLabelText('改编来源方式'), { target: { value: 'ordered' } });
  fireEvent.click(screen.getByLabelText('选择来源 Creation only'));
  await screen.findByText(/操作回执未确认/);
  expect(await screen.findByLabelText('改编建议审核')).toBeTruthy();
  expect((screen.getByRole('button', { name: '建立改编建议（尚不调用模型）' }) as HTMLButtonElement).disabled).toBe(true);
});
