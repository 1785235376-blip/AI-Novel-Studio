// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Chapter } from '../api';
import { ExperimentalWorkbench } from './ExperimentalWorkbench';
import { RevisionIntelligencePanel } from './RevisionIntelligencePanel';
import { experimentalClient, type ExperimentalFlags } from './api';
import type { JudgeRevisionIntent } from './judgeRevisionHandoff';

const chapter = { id: 'c', novel_id: 'n', title: '原章节', version: 4, content: '甲🙂。\n\n甲🙂。\n\n', document: { type: 'doc', content: [0, 1].map(() => ({ type: 'paragraph', content: [{ type: 'text', text: '甲🙂。' }] })) } } as Chapter;
const proof = { chapter_id: 'c', chapter_version: 4, paragraph: 2, start: 5, end: 8, quote: '甲🙂。' };
const finding = { id: 'f', version: 1, status: 'OPEN', decision: 'PENDING', code: 'EXACT_REPEATED_PARAGRAPH', category: 'REPETITION', severity: 'INFO', explanation: '文字重复', suggestion: '作者决定是否保留重复。', boundary: '重复不是文学错误证明', origin: 'DETERMINISTIC', stale: false, evidence: [{ ...proof, paragraph: 1, start: 0, end: 3 }, proof] };
const run = { id: 'r', version: 2, status: 'COMPLETED', stale: false, findings: [finding], abstentions: [], model_called: false };
const intent: JudgeRevisionIntent = { runId: 'r', runVersion: 2, findingId: 'f', findingVersion: 1, evidenceIndex: 1, evidence: proof };
const block = { path: [1], anchor_id: 'a'.repeat(64), before: '甲🙂。', after: '乙🙂。', from_pos: 7, to_pos: 11, status: 'PENDING', lock_state: 'UNLOCKED', diff: [{ kind: 'replace', before: '甲', after: '乙' }], diff_method: 'EXACT_CODEPOINT_DIFF' };
const catalog = { chapters: [chapter], branch_sources_available: true, blocks: [0, 1].map(i => ({ path: [i], from_pos: i * 6 + 1, to_pos: i * 6 + 5, text: '甲🙂。', supported: true, lock_state: 'UNLOCKED' })) };
const selection = { chapter_id: 'c', chapter_version: 4, from_pos: 7, to_pos: 11, text: '甲🙂。' };
const receipt = { selection, selection_digest: 'b'.repeat(64), blocks: [block], model_called: false, coordinate_contract: 'PROSEMIRROR_UTF16_V1' };
const proposal = { id: 'p', version: 1, status: 'REVIEW', source: { chapter_id: 'c', version: 4 }, blocks: [block], goal: '审阅依据', origin: 'MANUAL_CANDIDATE' };
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const flags: ExperimentalFlags = { experimental: true, default_enabled: false, features: { 'experimental.narrative_quality_judge_v2': true, 'experimental.revision_intelligence_v2': true } };
const props = { novelId: 'n', context: { sessionToken: 'test' }, flags, chapter, saved: true, requestedTab: 'narrative_quality_judge_v2' };
function mockFetch() {
  return vi.fn(async (url: string, init?: RequestInit): Promise<Response> => {
    if (url.endsWith('/narrative-judge/catalog')) return response({ chapters: [chapter], rubrics: [], adapters: [] });
    if (url.endsWith('/narrative-judge/runs')) return response({ items: [run] });
    if (url.endsWith('/narrative-judge/runs/r')) return response(run);
    if (url.includes('/revisions/catalog')) return response(catalog);
    if (url.endsWith('/selection')) return response(receipt);
    if (url.endsWith('/proposals') && init?.method === 'POST') return response(proposal);
    if (url.endsWith('/preview')) return response({ preview_digest: 'd'.repeat(64), checkpoint_version: 4, creates_new_current_revision: true, accept_ids: [block.anchor_id], reject_ids: [], pending_blocks: 0 });
    if (url.endsWith('/apply')) return response({ chapter: { ...chapter, version: 5 }, proposal: { ...proposal, status: 'ACCEPTED' } });
    return response({ items: [] });
  });
}
const writes = (fetch: ReturnType<typeof mockFetch>) => fetch.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET');
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function openJudge() {
  await waitFor(() => expect((screen.getByLabelText('查看审阅记录') as HTMLSelectElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('查看审阅记录'), { target: { value: 'r' } });
  await screen.findByRole('button', { name: '针对证据 2 准备原文修订' });
}
async function chooseParagraph() {
  await screen.findByLabelText('本次修订的原始证据');
  fireEvent.click(screen.getByText('从当前已保存段落选择'));
  fireEvent.click(screen.getByRole('button', { name: '选择第 2 段' }));
  await screen.findByLabelText('区块 1 候选文字');
}
it('mounts Judge evidence → explicit duplicate paragraph → existing candidate/diff/preview/human apply', async () => {
  const fetch = mockFetch(), saved = vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<ExperimentalWorkbench {...props} onChapterSaved={saved} />);
  await openJudge(); fireEvent.click(screen.getByRole('button', { name: '针对证据 2 准备原文修订' }));
  await screen.findByLabelText('本次修订的原始证据'); expect(writes(fetch)).toHaveLength(0);
  await chooseParagraph();
  expect(JSON.parse(writes(fetch)[0][1]!.body as string)).toEqual(selection);
  expect((screen.getByLabelText('区块 1 候选文字') as HTMLTextAreaElement).value).toBe('甲🙂。');
  expect((screen.getByLabelText('修订目标与保留要求') as HTMLTextAreaElement).value).toContain('r / f v1 · 证据 2');
  fireEvent.change(screen.getByLabelText('区块 1 候选文字'), { target: { value: '乙🙂。' } });
  fireEvent.click(screen.getByRole('button', { name: '保存候选并逐项审核' }));
  fireEvent.change(await screen.findByLabelText('区块 1 决定'), { target: { value: 'accept' } });
  expect(screen.getByText('查看可计算字符差异')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '预览所选区块与检查点' }));
  const apply = await screen.findByRole('button', { name: '确认仅应用所选决定' });
  expect((apply as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对所选区块与原版本检查点')); fireEvent.click(apply);
  await waitFor(() => expect(saved).toHaveBeenCalledWith(expect.objectContaining({ version: 5 })));
  expect(writes(fetch).map(([url]) => url.split('/').pop())).toEqual(['selection', 'proposals', 'preview', 'apply']);
  expect(fetch.mock.calls.some(([url]) => /generate|dispatch|\/review$/.test(url))).toBe(false);
});
it.each([false, true])('does not offer handoff when %s means revision disabled or chapter dirty', async dirty => {
  const fetch = mockFetch(); vi.stubGlobal('fetch', fetch);
  render(<ExperimentalWorkbench {...props} saved={!dirty} flags={dirty ? flags : { ...flags, features: { ...flags.features, 'experimental.revision_intelligence_v2': false } }} />);
  await waitFor(() => expect((screen.getByLabelText('查看审阅记录') as HTMLSelectElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('查看审阅记录'), { target: { value: 'r' } });
  await screen.findByText('文字重复'); expect(screen.queryByRole('button', { name: /准备原文修订/ })).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});
it('blocks an evidence version change on the receiving reread without a selection or proposal', async () => {
  const fetch = mockFetch(), base = fetch.getMockImplementation()!; let count = 0;
  fetch.mockImplementation(async (url, init) => url.endsWith('/runs/r') && ++count > 1 ? response({ ...run, findings: [{ ...finding, version: 2 }] }) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(<ExperimentalWorkbench {...props} />); await openJudge();
  fireEvent.click(screen.getByRole('button', { name: '针对证据 2 准备原文修订' }));
  await screen.findByText(/原线索、章节版本或引文位置已改变/);
  fireEvent.click(screen.getByText('从当前已保存段落选择'));
  expect((screen.getByRole('button', { name: '选择第 2 段' }) as HTMLButtonElement).disabled).toBe(true); expect(writes(fetch)).toHaveLength(0);
});
it('rechecks before candidate creation, retains handwritten candidate and blocks changed evidence', async () => {
  const fetch = mockFetch(), base = fetch.getMockImplementation()!; let stale = false;
  fetch.mockImplementation(async (url, init) => stale && url.endsWith('/runs/r') ? response({ ...run, stale: true, findings: [] }) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(<RevisionIntelligencePanel client={experimentalClient('n', props.context)} chapter={chapter} saved judgeIntent={intent} />);
  await chooseParagraph(); fireEvent.change(screen.getByLabelText('区块 1 候选文字'), { target: { value: '作者保留的候选' } }); stale = true;
  fireEvent.click(screen.getByRole('button', { name: '保存候选并逐项审核' }));
  await screen.findByText(/原线索、章节版本或引文位置已改变/);
  expect((screen.getByLabelText('区块 1 候选文字') as HTMLTextAreaElement).value).toBe('作者保留的候选');
  expect((screen.getByRole('button', { name: '保存候选并逐项审核' }) as HTMLButtonElement).disabled).toBe(true);
  expect(writes(fetch).map(([url]) => url.split('/').pop())).toEqual(['selection']);
});
it('ignores a late evidence reread after close and does not restore context after chapter ABA', async () => {
  const fetch = mockFetch(), base = fetch.getMockImplementation()!; let finish!: (value: Response) => void, count = 0;
  fetch.mockImplementation(async (url, init) => url.endsWith('/runs/r') && ++count === 2 ? new Promise(resolve => { finish = resolve; }) : base(url, init));
  vi.stubGlobal('fetch', fetch); const view = render(<ExperimentalWorkbench {...props} />); await openJudge();
  fireEvent.click(screen.getByRole('button', { name: '针对证据 2 准备原文修订' }));
  await waitFor(() => expect(finish).toBeTypeOf('function'));
  view.rerender(<ExperimentalWorkbench {...props} chapter={{ ...chapter, id: 'other' }} />);
  view.rerender(<ExperimentalWorkbench {...props} />);
  await act(async () => finish(response(run)));
  expect(screen.queryByLabelText('本次修订的原始证据')).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});
it('does not send selection after dirty-state ABA interrupts its source reread', async () => {
  const fetch = mockFetch(), base = fetch.getMockImplementation()!; let finish!: (value: Response) => void, count = 0;
  fetch.mockImplementation(async (url, init) => url.endsWith('/runs/r') && ++count === 2 ? new Promise(resolve => { finish = resolve; }) : base(url, init));
  vi.stubGlobal('fetch', fetch); const client = experimentalClient('n', props.context);
  const view = render(<RevisionIntelligencePanel client={client} chapter={chapter} saved judgeIntent={intent} />);
  await screen.findByLabelText('本次修订的原始证据'); fireEvent.click(screen.getByText('从当前已保存段落选择')); fireEvent.click(screen.getByRole('button', { name: '选择第 2 段' }));
  await waitFor(() => expect(finish).toBeTypeOf('function'));
  view.rerender(<RevisionIntelligencePanel client={client} chapter={chapter} saved={false} judgeIntent={intent} />);
  view.rerender(<RevisionIntelligencePanel client={client} chapter={chapter} saved judgeIntent={intent} />);
  await act(async () => finish(response(run)));
  expect(writes(fetch)).toHaveLength(0); expect(screen.queryByLabelText('区块 1 候选文字')).toBeNull();
});
it('a failed receiving read cannot borrow the displayed finding or issue a write', async () => {
  const fetch = mockFetch(), base = fetch.getMockImplementation()!;
  fetch.mockImplementation(async (url, init) => url.endsWith('/runs/r') ? response({ detail: 'unavailable' }, 403) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(<RevisionIntelligencePanel client={experimentalClient('n', props.context)} chapter={chapter} saved judgeIntent={intent} />);
  await screen.findByText(/原线索、章节版本或引文位置已改变/);
  expect(screen.queryByLabelText('本次修订的原始证据')).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});
it('repeated paragraph clicks share one in-flight read and selection request', async () => {
  const fetch = mockFetch(), base = fetch.getMockImplementation()!; let finish!: (value: Response) => void, count = 0;
  fetch.mockImplementation(async (url, init) => url.endsWith('/runs/r') && ++count === 2 ? new Promise(resolve => { finish = resolve; }) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(<RevisionIntelligencePanel client={experimentalClient('n', props.context)} chapter={chapter} saved judgeIntent={intent} />);
  await screen.findByLabelText('本次修订的原始证据'); fireEvent.click(screen.getByText('从当前已保存段落选择'));
  const choose = screen.getByRole('button', { name: '选择第 2 段' }); fireEvent.click(choose); fireEvent.click(choose);
  await waitFor(() => expect(finish).toBeTypeOf('function')); await act(async () => finish(response(run)));
  await screen.findByLabelText('区块 1 候选文字'); expect(count).toBe(2); expect(writes(fetch)).toHaveLength(1);
});
it('scope replacement with an outstanding read never creates a selection in either scope', async () => {
  const fetch = mockFetch(), base = fetch.getMockImplementation()!; let finish!: (value: Response) => void, count = 0;
  fetch.mockImplementation(async (url, init) => url.endsWith('/runs/r') && ++count === 2 ? new Promise(resolve => { finish = resolve; }) : base(url, init));
  vi.stubGlobal('fetch', fetch); const view = render(<RevisionIntelligencePanel client={experimentalClient('n', props.context)} chapter={chapter} saved judgeIntent={intent} />);
  await screen.findByLabelText('本次修订的原始证据'); fireEvent.click(screen.getByText('从当前已保存段落选择')); fireEvent.click(screen.getByRole('button', { name: '选择第 2 段' }));
  await waitFor(() => expect(finish).toBeTypeOf('function'));
  view.rerender(<RevisionIntelligencePanel client={experimentalClient('n', { sessionToken: 'other' })} chapter={chapter} saved />);
  await act(async () => finish(response(run)));
  expect(screen.queryByLabelText('本次修订的原始证据')).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});
it('keeps original uncertain-acceptance records read-only alongside the evidence handoff', async () => {
  const fetch = mockFetch(), base = fetch.getMockImplementation()!;
  fetch.mockImplementation(async (url, init) => url.endsWith('/proposals') ? response({ items: [{ ...proposal, status: 'ACCEPTANCE_UNCERTAIN', stale: true, blocks: undefined }] }) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(<RevisionIntelligencePanel client={experimentalClient('n', props.context)} chapter={chapter} saved judgeIntent={intent} />);
  await screen.findByText(/采用结果未确认/);
  expect((screen.getByRole('button', { name: '审核此修订' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole('button', { name: '确认仅应用所选决定' })).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});
it.each(['narrative_quality_judge_v2', 'revision_intelligence_v2'])('discards handoff after %s feature off/on', async feature => {
  const fetch = mockFetch(); vi.stubGlobal('fetch', fetch); const view = render(<ExperimentalWorkbench {...props} />);
  await openJudge(); fireEvent.click(screen.getByRole('button', { name: '针对证据 2 准备原文修订' })); await screen.findByLabelText('本次修订的原始证据');
  view.rerender(<ExperimentalWorkbench {...props} flags={{ ...flags, features: { ...flags.features, [`experimental.${feature}`]: false } }} />);
  view.rerender(<ExperimentalWorkbench {...props} />);
  expect(screen.queryByLabelText('本次修订的原始证据')).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});
it('transport failure during a recheck hides old evidence and preserves a blocked handwritten candidate', async () => {
  const fetch = mockFetch(), base = fetch.getMockImplementation()!; let fail = false;
  fetch.mockImplementation(async (url, init) => fail && url.endsWith('/runs/r') ? response({ detail: 'source unavailable' }, 503) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(<RevisionIntelligencePanel client={experimentalClient('n', props.context)} chapter={chapter} saved judgeIntent={intent} />);
  await chooseParagraph(); fireEvent.change(screen.getByLabelText('区块 1 候选文字'), { target: { value: '保留的人工改文' } }); fail = true;
  fireEvent.click(screen.getByRole('button', { name: '保存候选并逐项审核' })); await screen.findByText(/原线索、章节版本或引文位置已改变/);
  expect(screen.queryByLabelText('本次修订的原始证据')).toBeNull();
  expect((screen.getByLabelText('区块 1 候选文字') as HTMLTextAreaElement).value).toBe('保留的人工改文');
  expect((screen.getByRole('button', { name: '保存候选并逐项审核' }) as HTMLButtonElement).disabled).toBe(true);
  expect(writes(fetch)).toHaveLength(1);
});
