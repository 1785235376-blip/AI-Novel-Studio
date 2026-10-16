// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Chapter } from '../api';
import { experimentalClient } from './api';
import { StyleAnalysisPanel } from './StyleAnalysisPanel';
import { NarrativeJudgePanel } from './NarrativeJudgePanel';

const chapter = { id: 'chapter-one', title: '雨夜', version: 3 } as Chapter;
const context = { sessionToken: 'session-one', scope: { workspaceId: 'w', projectId: 'novel-one', storylineId: 's', branchId: 'branch-one' } };
const style = { id: 'style-one', version: 2, status: 'APPROVED', title: '克制文风', instructions: '使用短句，保留停顿。', rules: ['留意重复意象'], chapter_ids: ['chapter-one'], character_ids: ['person-one'], privacy_level: 'LOCAL_ONLY' };
const catalog = { styles: [style], chapters: [{ ...chapter, characters: 50 }], characters: [{ id: 'person-one', name: '小林' }], operations: ['continue', 'rewrite', 'polish', 'brainstorm', 'review'] };
const preview = { style_id: style.id, style_version: 2, instructions: style.instructions, rules: style.rules, operation: 'continue', character_id: null, privacy_level: 'LOCAL_ONLY', context_injection: 'INSTRUCTIONS_ONLY', rules_usage: 'REFERENCE_ONLY', model_called: false, preview_digest: 'receipt-one' };
const analysis = { id: 'analysis-one', version: 1, style_id: style.id, style_version: 2, language: 'zh', method_version: 'counts-v1', status: 'COMPLETED', stale: false, metrics: { sentence_count: 4, paragraph_count: 2, unit_count: 40, dialogue_characters: 8, characters: 50 }, samples: [{ chapter_id: chapter.id, expected_version: 3, start: 0, end: null }], comparison: null, limitations: ['统计不能判断文学质量。'], privacy_level: 'LOCAL_ONLY' };
const rubric = { id: 'narrative-rules-v1', version: 1, title: '叙事基础检查', checks: ['重复段落'], limitations: ['不判断人物动机。'] };
const finding = { id: 'finding-one', version: 4, status: 'OPEN', decision: 'PENDING', code: 'REPEATED_PARAGRAPH', category: 'REPETITION', severity: 'WARNING', explanation: '两个段落完全相同。', suggestion: '核对是否为有意重复。', boundary: '不能判断作者意图。', origin: 'DETERMINISTIC', evidence: [{ chapter_id: chapter.id, chapter_version: 3, paragraph: 2, start: 12, end: 20, quote: '雨仍然在下。' }], stale: false };
const run = { id: 'run-one', version: 1, status: 'COMPLETED', stale: false, findings: [finding], abstentions: ['情节合理性无法判断。'], verification: 'DETERMINISTIC_RULES', model_called: false };
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const client = () => experimentalClient('novel-one', context);
function transport() {
  let analyses: unknown[] = [], reviewed = { ...finding };
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/style-analysis/catalog')) return reply(catalog);
    if (url.endsWith('/style-analysis/analyses') && init?.method === 'POST') { analyses = [analysis]; return reply(analysis); }
    if (url.endsWith('/style-analysis/analyses')) return reply({ items: analyses });
    if (url.endsWith('/style-analysis/profiles')) return reply({ ...style, status: 'DRAFT', version: 1 });
    if (url.endsWith('/style-analysis/profiles/style-one') && init?.method === 'PUT') return reply({ ...style, version: 3, status: 'DRAFT', ...JSON.parse(init.body as string) });
    if (url.endsWith('/style-one/preview')) { const body = JSON.parse(init!.body as string); return reply({ ...preview, operation: body.operation, character_id: body.character_id }); }
    if (url.endsWith('/narrative-judge/catalog')) return reply({ chapters: [chapter], rubrics: [rubric], adapters: [] });
    if (url.endsWith('/narrative-judge/runs/run-one')) return reply({ ...run, findings: [reviewed] });
    if (url.endsWith('/narrative-judge/runs')) return reply(init?.method === 'POST' ? run : { items: [run] });
    if (url.endsWith('/findings/finding-one/review')) { const body = JSON.parse(init!.body as string); reviewed = { ...finding, version: 5, decision: body.action === 'ignore' ? 'IGNORED' : body.action === 'reopen' ? 'PENDING' : 'REVIEWED' }; return reply(reviewed); }
    throw new Error(`Unhandled ${init?.method} ${url}`);
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function selectStyle() {
  await screen.findByRole('button', { name: '编辑风格 克制文风' });
  fireEvent.change(screen.getByLabelText('分析与预览的风格档案'), { target: { value: style.id } });
  fireEvent.change(screen.getByLabelText('预览关联人物（可选）'), { target: { value: 'person-one' } });
}
async function previewStyle() {
  await selectStyle();
  fireEvent.click(screen.getByRole('button', { name: '预览风格注入内容' }));
  await screen.findByRole('region', { name: '准确风格输入预览' });
}
async function selectRun() {
  await screen.findByLabelText('审阅章节：雨夜 · v3');
  fireEvent.change(screen.getByLabelText('查看审阅记录'), { target: { value: run.id } });
  return screen.findByRole('article', { name: '检查线索 finding-one' });
}
it('reads without running analysis, requires explicit preview/review/use, and validates the receipt again', async () => {
  const fetch = transport(), onUseStyle = vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<StyleAnalysisPanel client={client()} chapter={chapter} onUseStyle={onUseStyle} />);
  await selectStyle();
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  expect(onUseStyle).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '预览风格注入内容' }));
  await screen.findByRole('region', { name: '准确风格输入预览' });
  const use = screen.getByRole('button', { name: '明确使用此风格准备写作' }) as HTMLButtonElement;
  expect(use.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对风格指令、用途与版本'));
  fireEvent.click(use); fireEvent.click(use);
  await waitFor(() => expect(onUseStyle).toHaveBeenCalledTimes(1));
  expect(onUseStyle).toHaveBeenCalledWith(style.id);
  const calls = fetch.mock.calls.filter(([url]) => url.endsWith('/preview'));
  expect(calls).toHaveLength(2);
  expect(JSON.parse(calls[0][1]!.body as string)).toEqual({ expected_version: 2, operation: 'continue', character_id: 'person-one' });
  expect(calls[0][1]!.headers).toMatchObject({ 'X-Session-Token': 'session-one', 'X-Branch-Id': 'branch-one' });
});
it('invalidates a preview when its controls or chapter revision change', async () => {
  vi.stubGlobal('fetch', transport()); const stable = client();
  const view = render(<StyleAnalysisPanel client={stable} chapter={chapter} />); await previewStyle();
  fireEvent.change(screen.getByLabelText('预览写作用途'), { target: { value: 'polish' } });
  expect(screen.queryByRole('region', { name: '准确风格输入预览' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '预览风格注入内容' })); await screen.findByRole('region', { name: '准确风格输入预览' });
  view.rerender(<StyleAnalysisPanel client={stable} chapter={{ ...chapter, version: 4 }} />);
  expect(screen.queryByRole('region', { name: '准确风格输入预览' })).toBeNull();
});
it('blocks late preview callbacks and generation selection after a scope remount', async () => {
  const base = transport(), onUseStyle = vi.fn(); let complete!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/preview') ? new Promise<Response>(resolve => { complete = resolve; }) : base(url, init)));
  const view = render(<StyleAnalysisPanel client={client()} chapter={chapter} onUseStyle={onUseStyle} />); await selectStyle();
  fireEvent.click(screen.getByRole('button', { name: '预览风格注入内容' }));
  view.rerender(<StyleAnalysisPanel client={experimentalClient('novel-two', { sessionToken: 'other' })} onUseStyle={onUseStyle} />);
  await act(async () => complete(reply(preview)));
  expect(screen.queryByRole('region', { name: '准确风格输入预览' })).toBeNull(); expect(onUseStyle).not.toHaveBeenCalled();
});
it('uses version-bound explicit sample ranges and comparison without a quality percentage', async () => {
  const fetch = transport(), onNavigate = vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<StyleAnalysisPanel client={client()} chapter={chapter} onNavigate={onNavigate} />); await selectStyle();
  fireEvent.click(screen.getByLabelText('分析样本：雨夜 · v3'));
  fireEvent.change(screen.getByLabelText('雨夜 样本起始字符'), { target: { value: '2' } });
  fireEvent.change(screen.getByLabelText('雨夜 样本结束字符（留空至章末）'), { target: { value: '20' } });
  fireEvent.click(screen.getByLabelText('与当前已保存章节比较「雨夜」v3'));
  fireEvent.click(screen.getByRole('button', { name: '分析所选已保存样本' }));
  await screen.findByRole('article', { name: '文风报告 analysis-one' });
  const request = fetch.mock.calls.find(([url, init]) => url.endsWith('/analyses') && init?.method === 'POST')!;
  expect(JSON.parse(request[1]!.body as string)).toEqual({ style_id: style.id, expected_style_version: 2, language: 'zh', samples: [{ chapter_id: chapter.id, expected_version: 3, start: 2, end: 20 }], operations: ['continue'], comparison: { chapter_id: chapter.id, expected_version: 3, language: 'zh' } });
  expect(screen.getByText('句子数')).toBeTruthy(); expect(screen.queryByText(/质量.*%/)).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '打开样本来源 1' }));
  expect(onNavigate).toHaveBeenCalledWith(expect.objectContaining({ id: chapter.id, version: 3 }));
});
it('preserves profile text on a 409, requires deliberate revision rebase, and never auto-selects generation', async () => {
  const base = transport(), onUseStyle = vi.fn(); let changed = false;
  const fetch = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith('/style-analysis/profiles/style-one') && init?.method === 'PUT') { changed = true; return Promise.resolve(reply({ code: 'VERSION_CONFLICT' }, 409)); }
    if (url.endsWith('/style-analysis/catalog') && changed) return Promise.resolve(reply({ ...catalog, styles: [{ ...style, version: 3, instructions: '服务器的新风格' }] }));
    return base(url, init);
  }); vi.stubGlobal('fetch', fetch); render(<StyleAnalysisPanel client={client()} onUseStyle={onUseStyle} />);
  fireEvent.click(await screen.findByRole('button', { name: '编辑风格 克制文风' }));
  fireEvent.change(screen.getByLabelText('可复用风格指令（最多 120 字）'), { target: { value: '保留我的未保存短句。' } });
  fireEvent.click(screen.getByRole('button', { name: '保存风格新草稿版本' })); await screen.findByRole('alert');
  expect((screen.getByLabelText('可复用风格指令（最多 120 字）') as HTMLTextAreaElement).value).toBe('保留我的未保存短句。');
  fireEvent.click(screen.getByRole('button', { name: '刷新风格与来源（保留输入）' }));
  await screen.findByRole('button', { name: '已核对，以服务器版本继续编辑（保留输入）' });
  expect((screen.getByRole('button', { name: '保存风格新草稿版本' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '已核对，以服务器版本继续编辑（保留输入）' }));
  expect((screen.getByLabelText('可复用风格指令（最多 120 字）') as HTMLTextAreaElement).value).toBe('保留我的未保存短句。'); expect(onUseStyle).not.toHaveBeenCalled();
});
it('requires an explicit judge run with current revisions and renders abstentions and anchored evidence', async () => {
  const fetch = transport(), onNavigate = vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<NarrativeJudgePanel client={client()} chapter={chapter} onNavigate={onNavigate} />);
  await screen.findByLabelText('审阅章节：雨夜 · v3');
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '检查所选已保存章节' }));
  await screen.findByRole('article', { name: '检查线索 finding-one' });
  const request = fetch.mock.calls.find(([url, init]) => url.endsWith('/runs') && init?.method === 'POST')!;
  expect(JSON.parse(request[1]!.body as string)).toEqual({ chapter_ids: [chapter.id], expected_versions: { [chapter.id]: 3 }, rubric_id: rubric.id });
  expect(screen.getByText('情节合理性无法判断。')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '打开此证据来源章节 1' }));
  expect(onNavigate).toHaveBeenCalledWith({ kind: 'chapter', id: chapter.id, version: 3 });
});
it('records a reasoned decision and supports reopen with no manuscript write', async () => {
  const fetch = transport(); vi.stubGlobal('fetch', fetch); render(<NarrativeJudgePanel client={client()} chapter={chapter} />); const article = await selectRun();
  expect((within(article).getByRole('button', { name: '记录已核对' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('审核理由 finding-one'), { target: { value: '重复是有意回响，保留。' } });
  fireEvent.click(screen.getByLabelText('关联当前已保存修订「雨夜」v3'));
  fireEvent.click(screen.getByRole('button', { name: '记录忽略理由' }));
  await screen.findByRole('button', { name: '重新打开核对' });
  const request = fetch.mock.calls.find(([url]) => url.endsWith('/findings/finding-one/review'))!;
  expect(JSON.parse(request[1]!.body as string)).toEqual({ expected_version: 4, action: 'ignore', reason: '重复是有意回响，保留。', revision_chapter_id: chapter.id, revision_version: 3 });
  expect((screen.getByLabelText('审核理由 finding-one') as HTMLTextAreaElement).value).toBe('重复是有意回响，保留。');
  fireEvent.click(screen.getByRole('button', { name: '重新打开核对' })); await screen.findByRole('button', { name: '记录已核对' });
  expect(fetch.mock.calls.filter(([, init]) => init?.method !== 'GET').every(([url]) => url.endsWith('/findings/finding-one/review'))).toBe(true);
});
it('retains judge reasons across 409 refresh and filter changes', async () => {
  const base = transport(); const fetch = vi.fn((url: string, init?: RequestInit) => url.endsWith('/findings/finding-one/review') ? Promise.resolve(reply({ code: 'VERSION_CONFLICT' }, 409)) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(<NarrativeJudgePanel client={client()} chapter={chapter} />); await selectRun();
  fireEvent.change(screen.getByLabelText('审核理由 finding-one'), { target: { value: '请保留这段理由。' } });
  fireEvent.click(screen.getByRole('button', { name: '记录已核对' })); await screen.findByRole('alert');
  fireEvent.change(screen.getByLabelText('按审核决定筛选'), { target: { value: 'IGNORED' } });
  await screen.findByText('当前筛选没有结果');
  fireEvent.change(screen.getByLabelText('按审核决定筛选'), { target: { value: '' } });
  expect((screen.getByLabelText('审核理由 finding-one') as HTMLTextAreaElement).value).toBe('请保留这段理由。');
  fireEvent.click(screen.getByRole('button', { name: '刷新审阅与来源（保留输入）' }));
  await screen.findByRole('article', { name: '检查线索 finding-one' });
  expect((screen.getByLabelText('审核理由 finding-one') as HTMLTextAreaElement).value).toBe('请保留这段理由。');
});
it('does not display a previous scope judge result or keep its private reason', async () => {
  const base = transport(); let finish!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/runs/run-one') ? new Promise<Response>(resolve => { finish = resolve; }) : base(url, init)));
  const view = render(<NarrativeJudgePanel client={client()} chapter={chapter} />);
  await screen.findByLabelText('审阅章节：雨夜 · v3'); fireEvent.change(screen.getByLabelText('查看审阅记录'), { target: { value: run.id } });
  view.rerender(<NarrativeJudgePanel client={experimentalClient('another-project', { sessionToken: 'other' })} />);
  await act(async () => finish(reply(run)));
  expect(screen.queryByRole('article', { name: '检查线索 finding-one' })).toBeNull();
});
it('shows permission recovery and keeps draft inputs while hiding old records', async () => {
  const base = transport(); let deny = false;
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => deny && url.endsWith('/style-analysis/catalog') ? Promise.resolve(reply({ code: 'FORBIDDEN' }, 403)) : base(url, init)));
  render(<StyleAnalysisPanel client={client()} chapter={chapter} />); await selectStyle();
  fireEvent.change(screen.getByLabelText('风格档案标题'), { target: { value: '我的草稿' } }); deny = true;
  fireEvent.click(screen.getByRole('button', { name: '刷新风格与来源（保留输入）' })); await screen.findByRole('alert');
  expect(screen.queryByRole('button', { name: '编辑风格 克制文风' })).toBeNull();
  expect((screen.getByLabelText('风格档案标题') as HTMLInputElement).value).toBe('我的草稿');
  expect((screen.getByRole('button', { name: '保存风格草稿' }) as HTMLButtonElement).disabled).toBe(true);
  deny = false; fireEvent.click(screen.getByRole('button', { name: '刷新风格与来源（保留输入）' })); await screen.findByRole('button', { name: '编辑风格 克制文风' });
});
it('keeps stale judge evidence advisory and disables review/navigation until a fresh run', async () => {
  const base = transport(); vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/runs/run-one') ? Promise.resolve(reply({ ...run, stale: true })) : base(url, init)));
  render(<NarrativeJudgePanel client={client()} chapter={chapter} onNavigate={vi.fn()} />); await selectRun();
  expect(screen.queryByRole('button', { name: '记录已核对' })).toBeNull();
  expect(screen.queryByRole('button', { name: '打开此证据来源章节 1' })).toBeNull();
  expect(screen.queryByText('雨仍然在下。')).toBeNull();
});
it('renders sparse redacted stale reports without exposing metrics or claiming a clean judge result', async () => {
  const base = transport(); vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith('/style-analysis/analyses')) return Promise.resolve(reply({ items: [{ id: analysis.id, version: 1, style_id: style.id, status: 'COMPLETED', stale: true, limitations: ['旧指标已隐藏。'] }] }));
    if (url.endsWith('/runs/run-one')) return Promise.resolve(reply({ id: run.id, version: 1, status: 'COMPLETED', stale: true, findings: [], abstentions: ['旧评语已隐藏。'], verification: 'DETERMINISTIC_RULES', model_called: false }));
    return base(url, init);
  }));
  const view = render(<StyleAnalysisPanel client={client()} />); await screen.findByRole('article', { name: '文风报告 analysis-one' });
  expect(screen.queryByText('句子数')).toBeNull(); expect(screen.queryByRole('button', { name: '打开样本来源 1' })).toBeNull();
  view.unmount(); render(<NarrativeJudgePanel client={client()} />);
  await screen.findByLabelText('审阅章节：雨夜 · v3'); fireEvent.change(screen.getByLabelText('查看审阅记录'), { target: { value: run.id } });
  await screen.findByText('旧评语已隐藏。'); expect(screen.queryByText('规则未发现匹配线索')).toBeNull(); expect(screen.queryByText(/0 条检查线索/)).toBeNull();
});
it('rejects a changed use receipt and does not invoke the generation callback', async () => {
  const base = transport(), onUseStyle = vi.fn(); let requests = 0;
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith('/preview') && ++requests > 1) return Promise.resolve(reply({ ...preview, character_id: 'person-one', preview_digest: 'changed' }));
    return base(url, init);
  })); render(<StyleAnalysisPanel client={client()} onUseStyle={onUseStyle} />); await previewStyle();
  fireEvent.click(screen.getByLabelText('已核对风格指令、用途与版本'));
  fireEvent.click(screen.getByRole('button', { name: '明确使用此风格准备写作' })); await screen.findByRole('alert');
  expect(onUseStyle).not.toHaveBeenCalled(); expect(screen.queryByRole('region', { name: '准确风格输入预览' })).toBeNull();
});
it('serializes repeated judge decisions and prevents refresh from remounting an active write', async () => {
  const base = transport(); let complete!: (value: Response) => void;
  const fetch = vi.fn((url: string, init?: RequestInit) => url.endsWith('/findings/finding-one/review') ? new Promise<Response>(resolve => { complete = resolve; }) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(<NarrativeJudgePanel client={client()} chapter={chapter} />); await selectRun();
  fireEvent.change(screen.getByLabelText('审核理由 finding-one'), { target: { value: '核对完成。' } });
  const button = screen.getByRole('button', { name: '记录已核对' }); fireEvent.click(button); fireEvent.click(button);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/findings/finding-one/review'))).toHaveLength(1);
  expect((screen.getByRole('button', { name: '刷新审阅与来源（保留输入）' }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => complete(reply({ ...finding, decision: 'REVIEWED' })));
});
it('clears revision-link consent when the current chapter changes while preserving its review reason', async () => {
  vi.stubGlobal('fetch', transport()); const stable = client(); const view = render(<NarrativeJudgePanel client={stable} chapter={chapter} />); await selectRun();
  fireEvent.change(screen.getByLabelText('审核理由 finding-one'), { target: { value: '需复核修订。' } });
  fireEvent.click(screen.getByLabelText('关联当前已保存修订「雨夜」v3'));
  view.rerender(<NarrativeJudgePanel client={stable} chapter={{ ...chapter, version: 4 }} />);
  expect((screen.getByLabelText('关联当前已保存修订「雨夜」v4') as HTMLInputElement).checked).toBe(false);
  expect((screen.getByLabelText('审核理由 finding-one') as HTMLTextAreaElement).value).toBe('需复核修订。');
});
it('requires a declared character before previewing a character-scoped style', async () => {
  const fetch = transport(); vi.stubGlobal('fetch', fetch); render(<StyleAnalysisPanel client={client()} />);
  await screen.findByRole('button', { name: '编辑风格 克制文风' });
  fireEvent.change(screen.getByLabelText('分析与预览的风格档案'), { target: { value: style.id } });
  expect((screen.getByRole('button', { name: '预览风格注入内容' }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
});
