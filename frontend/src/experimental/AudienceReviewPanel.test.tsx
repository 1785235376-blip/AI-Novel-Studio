// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError, type Chapter } from '../api';
import type { ExperimentalClient } from './api';
import { AudienceReviewPanel } from './AudienceReviewPanel';
import { NarrativeJudgePanel } from './NarrativeJudgePanel';
import { audienceReviewClient, type AudienceFinding, type AudienceRun } from './audienceReviewClient';

const chapter = { id: 'c1', title: '测试章节', version: 2 } as Chapter;
const chapters = [chapter, { id: 'c2', title: '另一章节', version: 3 }];
const source = { chapter_id: 'c1', chapter_version: 2, source_digest: 'a'.repeat(64), paragraphs: [{ paragraph: 2, start: 3, end: 6, quote: '😀原文' }], unsupported_paragraphs: 1 };
const finding: AudienceFinding = { id: 'f1', version: 4, status: 'OPEN', decision: 'PENDING', code: 'AUTHOR_READER_OBSERVATION', category: 'READABILITY', severity: 'INFO', explanation: '作者担心此处指代不清。', suggestion: '说明所指人物。', boundary: '作者输入，未经过真实读者测试。', origin: 'AUTHOR_ENTERED', audience_profile_index: 0, evidence: [{ ...source.paragraphs[0], chapter_id: 'c1', chapter_version: 2 }], stale: false };
const run = (id = 'r1'): AudienceRun => ({ id, version: 1, status: 'COMPLETED', stale: false, findings: [{ ...finding, id: id === 'r1' ? 'f1' : 'f2' }], abstentions: [], model_called: false, verification: 'AUTHOR_ENTERED_AND_LOCAL_ARITHMETIC', audience: { chapter_id: 'c1', chapter_version: 2, comparison: 'DIFFERENT_ADVICE', profiles: [{ name: 'A', genre_experience: 'NOVICE', target_age_group: 'GENERAL', language_habit: '现代中文', reading_speed: 300, schema_version: 1, digest: 'digest-a' }, { name: 'B', genre_experience: 'EXPERIENCED', target_age_group: 'ADULTS', language_habit: '古典中文', reading_speed: 600, schema_version: 1, digest: 'digest-b' }], measurements: [{ profile_index: 0, nonspace_characters: 300, estimated_seconds: 60 }, { profile_index: 1, nonspace_characters: 300, estimated_seconds: 30 }] } });
function mockClient(items: AudienceRun[] = []) {
  const get = vi.fn<(path: string, signal?: AbortSignal) => Promise<any>>(async path => {
    if (path.endsWith('/audience/catalog')) return { chapters, profiles: [] };
    if (path.endsWith('/audience/comparisons')) return { items };
    if (path.includes('/audience/source/c1')) return source;
    if (path.includes('/audience/source/c2')) return { ...source, chapter_id: 'c2', chapter_version: 3 };
    if (path === '/narrative-judge/catalog') return { chapters, rubrics: [], adapters: [] };
    if (path === '/narrative-judge/runs') return { items: [] };
    throw new Error(path);
  });
  const post = vi.fn<(path: string, body: any) => Promise<any>>(async () => run());
  return { get, post, client: { get, post, put: vi.fn(), blob: vi.fn() } as unknown as ExperimentalClient };
}
function change(label: string, value: string) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }
const save = () => screen.getByRole('button', { name: '保存两个设定的比较（不改正文）' }) as HTMLButtonElement;
async function fillProfiles() { await screen.findByLabelText('设定 1 语言习惯'); change('设定 1 语言习惯', '现代中文'); change('设定 2 语言习惯', '习惯古典词语'); }
function fillNotes() { for (const index of [1, 2]) { change(`设定 ${index} 证据段落`, '2'); change(`设定 ${index} 作者观察`, `作者观察 ${index}`); change(`设定 ${index} 作者建议`, `作者建议 ${index}`); } }
async function chooseRun(id = 'r1') { await waitFor(() => expect((screen.getByLabelText('查看读者比较记录') as HTMLSelectElement).disabled).toBe(false)); change('查看读者比较记录', id); }
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; }); return { resolve, reject, promise }; }
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('saves two author profiles and exact server Unicode evidence with the captured digest once', async () => {
  const calls = mockClient(); render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await fillProfiles();
  expect(calls.post).not.toHaveBeenCalled(); expect(screen.getByText(/1 个段落超过 2000 字证据上限/)).toBeTruthy();
  fillNotes(); change('作者对两组建议的比较', 'DIFFERENT_ADVICE');
  expect((screen.getByLabelText('设定 1 准确原文') as HTMLTextAreaElement).value).toBe('😀原文'); fireEvent.click(save()); fireEvent.click(save());
  await waitFor(() => expect(calls.post).toHaveBeenCalledTimes(1));
  expect(calls.post.mock.calls[0]).toEqual(['/narrative-judge/audience/comparisons', { chapter_id: 'c1', expected_version: 2, expected_source_digest: source.source_digest, profiles: [{ name: '读者设定 A', genre_experience: 'NOVICE', target_age_group: 'GENERAL', language_habit: '现代中文', reading_speed: 250 }, { name: '读者设定 B', genre_experience: 'EXPERIENCED', target_age_group: 'GENERAL', language_habit: '习惯古典词语', reading_speed: 400 }], comparison: 'DIFFERENT_ADVICE', observations: [0, 1].map(index => ({ profile_index: index, evidence: finding.evidence[0], observation: `作者观察 ${index + 1}`, suggestion: `作者建议 ${index + 1}` })) }]);
  expect(calls.get.mock.calls.some(([path]) => path.includes('/model/'))).toBe(false);
});

it('validates speeds and evidence, permitting explicit unassessed arithmetic without notes', async () => {
  const calls = mockClient(); render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await fillProfiles();
  for (const value of ['0', '10001', '1.5', '']) { change('设定 1 阅读速度（非空白字符／分钟）', value); expect(save().disabled).toBe(true); }
  change('设定 1 阅读速度（非空白字符／分钟）', '600'); expect(save().disabled).toBe(false);
  change('作者对两组建议的比较', 'AGREEMENT'); expect(save().disabled).toBe(true);
  change('作者对两组建议的比较', 'NOT_ASSESSED'); change('设定 1 作者观察', '缺少证据的记录'); expect(save().disabled).toBe(true);
  change('设定 1 作者观察', ''); fireEvent.click(save()); await waitFor(() => expect(calls.post).toHaveBeenCalledTimes(1)); expect(calls.post.mock.calls[0][1].observations).toEqual([]);
});

it('preserves source-keyed creation drafts and comparison-keyed review reasons across local navigation', async () => {
  const calls = mockClient([run(), run('r2')]); render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await fillProfiles(); fillNotes();
  await chooseRun(); change('读者观察审核理由 f1', '第一份独立理由'); change('查看读者比较记录', 'r2'); change('读者观察审核理由 f2', '第二份独立理由'); change('查看读者比较记录', 'r1');
  expect((screen.getByLabelText('读者观察审核理由 f1') as HTMLTextAreaElement).value).toBe('第一份独立理由');
  expect((screen.getByLabelText('设定 1 作者观察') as HTMLTextAreaElement).value).toBe('作者观察 1');
  change('读者比较章节', 'c2'); await screen.findByLabelText('设定 1 语言习惯'); expect((screen.getByLabelText('设定 1 语言习惯') as HTMLTextAreaElement).value).toBe('');
  change('设定 1 语言习惯', '另一章节输入'); change('读者比较章节', 'c1'); await screen.findByLabelText('设定 1 准确原文');
  expect((screen.getByLabelText('设定 1 语言习惯') as HTMLTextAreaElement).value).toBe('现代中文'); expect((screen.getByLabelText('设定 1 作者观察') as HTMLTextAreaElement).value).toBe('作者观察 1');
});

it('records author dispositions with existing finding CAS and links exact source without editing prose', async () => {
  const calls = mockClient([run()]), navigate = vi.fn(); render(<AudienceReviewPanel client={calls.client} chapter={chapter} onNavigate={navigate} />); await chooseRun();
  expect(screen.getByText('AUTHOR_ENTERED · 作者填写')).toBeTruthy(); expect(screen.getByText(/估算 60.00 秒/)).toBeTruthy();
  const accept = screen.getByRole('button', { name: '接受作者建议（不改正文）' }) as HTMLButtonElement; expect(accept.disabled).toBe(true);
  change('读者观察审核理由 f1', '已核对准确引文'); fireEvent.click(accept); fireEvent.click(accept);
  await waitFor(() => expect(calls.post).toHaveBeenCalledTimes(1)); expect(calls.post.mock.calls[0]).toEqual(['/narrative-judge/findings/f1/review', { expected_version: 4, action: 'accept', reason: '已核对准确引文' }]);
  await waitFor(() => expect((screen.getByRole('button', { name: '打开读者观察来源 1' }) as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(screen.getByRole('button', { name: '打开读者观察来源 1' })); expect(navigate).toHaveBeenCalledWith({ kind: 'chapter', id: 'c1', version: 2 });
});

it('handles redacted stale receipts without exposing profiles, metrics or findings', async () => {
  const calls = mockClient([{ ...run(), stale: true, audience: undefined, findings: [] }]); render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await chooseRun();
  expect(screen.getByText(/旧设定、测量和观察已隐藏/)).toBeTruthy(); expect(screen.queryByText('digest-a')).toBeNull(); expect(screen.queryByLabelText('读者观察审核理由 f1')).toBeNull();
});

it('hides old findings when the catalog version disagrees even if stale is false', async () => {
  const calls = mockClient([run()]); const original = calls.get.getMockImplementation()!; calls.get.mockImplementation(async path => path.endsWith('/audience/catalog') ? { chapters: [{ ...chapter, version: 3 }], profiles: [] } : original(path));
  render(<AudienceReviewPanel client={calls.client} chapter={{ ...chapter, version: 3 }} />); await chooseRun(); expect(screen.getByText(/旧设定、测量和观察已隐藏/)).toBeTruthy(); expect(screen.queryByText(/作者担心此处指代不清/)).toBeNull();
});

it('preserves inputs on conflict without automatically resubmitting', async () => {
  const calls = mockClient(); calls.post.mockRejectedValue(new ApiError({ status: 409, code: 'VERSION_CONFLICT', message: '来源版本变化' }));
  render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await fillProfiles(); fillNotes(); fireEvent.click(save()); await screen.findByRole('alert');
  expect((screen.getByLabelText('设定 1 作者观察') as HTMLTextAreaElement).value).toBe('作者观察 1'); expect(calls.post).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: '刷新读者比较与来源（保留输入）' })); await screen.findByLabelText('设定 1 准确原文'); expect((screen.getByLabelText('设定 1 作者建议') as HTMLTextAreaElement).value).toBe('作者建议 1'); expect(calls.post).toHaveBeenCalledTimes(1);
});

it('ignores late old-source responses when selecting another chapter', async () => {
  const calls = mockClient(), oldSource = deferred<typeof source>(); const original = calls.get.getMockImplementation()!; calls.get.mockImplementation(async path => path.includes('/source/c1') ? oldSource.promise : original(path));
  render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await waitFor(() => expect((screen.getByLabelText('读者比较章节') as HTMLSelectElement).disabled).toBe(false)); change('读者比较章节', 'c2'); await fillProfiles(); change('设定 1 证据段落', '2');
  await act(async () => oldSource.resolve({ ...source, paragraphs: [{ ...source.paragraphs[0], quote: '旧来源私人文本' }] })); expect((screen.getByLabelText('设定 1 准确原文') as HTMLTextAreaElement).value).toBe('😀原文'); expect(screen.queryByDisplayValue('旧来源私人文本')).toBeNull();
});

it.each(['success', 'failure'] as const)('ignores late create %s after a client change', async outcome => {
  const first = mockClient([run()]), pending = deferred<AudienceRun>(); first.post.mockImplementation(() => pending.promise);
  const view = render(<AudienceReviewPanel client={first.client} chapter={chapter} />); await fillProfiles(); fillNotes(); fireEvent.click(save());
  const second = mockClient(); view.rerender(<AudienceReviewPanel client={second.client} chapter={chapter} />); await screen.findByLabelText('设定 1 语言习惯'); expect((screen.getByLabelText('设定 1 语言习惯') as HTMLTextAreaElement).value).toBe('');
  await act(async () => { if (outcome === 'success') pending.resolve(run()); else pending.reject(new Error('old scope')); });
  expect(screen.queryByText(/读者设定比较已保存/)).toBeNull(); expect(screen.queryByRole('alert')).toBeNull(); expect(second.post).not.toHaveBeenCalled();
});

it.each(['create', 'review'] as const)('invalidates pending %s success after the current chapter version changes', async operation => {
  const calls = mockClient([run()]), pending = deferred<AudienceRun>(); calls.post.mockImplementation(() => pending.promise);
  const view = render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await fillProfiles();
  if (operation === 'create') fireEvent.click(save()); else { await chooseRun(); change('读者观察审核理由 f1', '旧版本审核理由'); fireEvent.click(screen.getByRole('button', { name: '接受作者建议（不改正文）' })); }
  view.rerender(<AudienceReviewPanel client={calls.client} chapter={{ ...chapter, version: 3 }} />); expect(screen.queryByLabelText('设定 1 准确原文')).toBeNull(); await act(async () => pending.resolve(run())); expect(screen.queryByText(/比较已保存|作者决定已保存/)).toBeNull();
});

it.each(['create', 'review'] as const)('invalidates pending %s failure after the source version changes', async operation => {
  const calls = mockClient([run()]), pending = deferred<AudienceRun>(); calls.post.mockImplementation(() => pending.promise);
  const view = render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await fillProfiles();
  if (operation === 'create') fireEvent.click(save()); else { await chooseRun(); change('读者观察审核理由 f1', '旧版本审核理由'); fireEvent.click(screen.getByRole('button', { name: '接受作者建议（不改正文）' })); }
  view.rerender(<AudienceReviewPanel client={calls.client} chapter={{ ...chapter, version: 3 }} />); await act(async () => pending.reject(new Error('old scope failure'))); expect(screen.queryByRole('alert')).toBeNull();
});

it('does not bind an old observation to same-version source changes', async () => {
  const calls = mockClient(); render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await fillProfiles(); fillNotes(); const original = calls.get.getMockImplementation()!;
  calls.get.mockImplementation(async path => path.includes('/source/c1') ? { ...source, source_digest: 'b'.repeat(64) } : original(path));
  fireEvent.click(screen.getByRole('button', { name: '刷新读者比较与来源（保留输入）' })); await screen.findByLabelText('设定 1 语言习惯'); expect((screen.getByLabelText('设定 1 作者观察') as HTMLTextAreaElement).value).toBe(''); expect(screen.queryByLabelText('设定 1 准确原文')).toBeNull();
});

it('requires explicit source preparation after unavailable ownership and never auto-prepares', async () => {
  const calls = mockClient(), original = calls.get.getMockImplementation()!; let prepared = false;
  calls.get.mockImplementation(async path => { if (path.includes('/source/c1') && !prepared) throw new Error('owner missing'); return original(path); }); calls.post.mockImplementation(async () => { prepared = true; return source; });
  render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await screen.findByRole('alert'); expect(calls.post).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '准备当前章节的读者比较来源' })); await screen.findByLabelText('设定 1 语言习惯'); expect(calls.post).toHaveBeenCalledWith('/narrative-judge/audience/source/c1/prepare', { expected_version: 2 });
});

it('lazily mounts and keeps creation drafts when collapsed and reopened', async () => {
  const calls = mockClient(); render(<NarrativeJudgePanel client={calls.client} chapter={chapter} />); await waitFor(() => expect(calls.get).toHaveBeenCalledWith('/narrative-judge/catalog', expect.any(AbortSignal))); expect(calls.get.mock.calls.some(([path]) => path.includes('/audience/'))).toBe(false);
  const details = screen.getByText('目标读者比较（作者填写）').closest('details')!; details.open = true; fireEvent(details, new Event('toggle')); await fillProfiles(); change('设定 1 名称', '保留的比较设定'); details.open = false; fireEvent(details, new Event('toggle')); details.open = true; fireEvent(details, new Event('toggle')); expect((screen.getByLabelText('设定 1 名称') as HTMLInputElement).value).toBe('保留的比较设定');
});

it('encodes identifiers and carries expected source and finding versions', async () => {
  const calls = mockClient(); calls.get.mockResolvedValue(source); const api = audienceReviewClient(calls.client); await api.source('chapter/with space', 7); await api.review('finding/with space', { expected_version: 4, action: 'review', reason: '理由' }); expect(calls.get).toHaveBeenCalledWith('/narrative-judge/audience/source/chapter%2Fwith%20space?expected_version=7', undefined); expect(calls.post).toHaveBeenCalledWith('/narrative-judge/findings/finding%2Fwith%20space/review', { expected_version: 4, action: 'review', reason: '理由' });
});

it('fails closed on a source without a complete integrity digest', async () => {
  const calls = mockClient(), original = calls.get.getMockImplementation()!; calls.get.mockImplementation(async path => path.includes('/source/c1') ? { ...source, source_digest: '' } : original(path));
  render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await screen.findByText(/来源回执与当前章节版本或完整性摘要不一致/); expect(screen.queryByLabelText('设定 1 作者观察')).toBeNull(); expect(calls.post).not.toHaveBeenCalled();
});

it('shows saved decision action and timestamp alongside its reason', async () => {
  const row = run(); row.findings[0].review_history = [{ action: 'IGNORE', at: '2026-10-18T12:00:00Z', reason: '已记录原来的忽略理由。' }]; const calls = mockClient([row]);
  render(<AudienceReviewPanel client={calls.client} chapter={chapter} />); await chooseRun(); expect(screen.getByText('已忽略 · 2026-10-18T12:00:00Z')).toBeTruthy(); expect(screen.getByText('已记录原来的忽略理由。')).toBeTruthy();
});
