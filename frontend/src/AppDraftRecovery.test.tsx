// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { api, ApiError, type Chapter } from './api';
import { drafts, conflicts, conflictResolutionDrafts } from './drafts';
import { useStudio } from './store';

// Real App state, version guards, local persistence and requests; only unrelated
// chrome and rich text are replaced. Editor.recovery tests mount real TipTap.
vi.mock('./Editor', async importOriginal => ({ ...(await importOriginal<typeof import('./Editor')>()), ChapterEditor: ({ content, onChange, onCompositionChange }: any) =>
  <textarea aria-label="Test chapter editor" value={content} onChange={event => onChange(event.target.value, doc(event.target.value))}
    onCompositionStart={() => onCompositionChange?.(true)} onCompositionEnd={() => onCompositionChange?.(false)} /> }));
vi.mock('./ui/AppShell', () => ({ AppShell: ({ main, status }: any) => <><main>{main}</main><footer>{status}</footer></> }));
vi.mock('./novel/AiWritingPanel', () => ({ AiWritingPanel: () => null }));
vi.mock('./novel/SourcePrivacyControl', () => ({ SourcePrivacyControl: () => null }));
vi.mock('./novel/ChapterTree', () => ({ ChapterTree: () => null }));
vi.mock('./ui/FeatureLauncher', () => ({ FeatureLauncher: () => null }));
function doc(text: string) { return { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] }; }
function chapter(content = 'SAVED', version = 3, id = 'recovery:1'): Chapter {
  return { id, novel_id: 'recovery', number: 1, title: 'Synthetic chapter', content, document: doc(content), version, word_count: content.length, status: 'DRAFT' };
}
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
const clients: QueryClient[] = [];
function setup(enabled = true, strict = false) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } }); clients.push(query);
  query.setQueryData(['novels'], [{ id: 'recovery', title: 'Synthetic' }]);
  query.setQueryData(['chapter', 'file', 'recovery:1'], chapter());
  query.setQueryData(['chapter', 'file', 'recovery:2'], chapter('SECOND', 10, 'recovery:2'));
  query.setQueryData(['chapters', 'file', 'recovery'], [chapter(), chapter('SECOND', 10, 'recovery:2')]);
  query.setQueryData(['archived-chapters', 'file', 'recovery'], []);
  query.setQueryData(['text-models'], []);
  query.setQueryData(['media-tasks', 'recovery'], { audiobook: [], motion: [] });
  query.setQueryData(['writing-goal', 'recovery'], { current_words: 0, target_words: 10, current_chapters: 2, target_chapters: 3, words_progress: 0 });
  query.setQueryData(['experimental-features', 'file'], { experimental: enabled, default_enabled: false, features: { 'experimental.writing_recovery_v2': enabled } });
  const app = <QueryClientProvider client={query}><App /></QueryClientProvider>;
  const view = render(strict ? <StrictMode>{app}</StrictMode> : app);
  return { query, view };
}
const editor = () => screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement;
function edit(text: string) { fireEvent.change(editor(), { target: { value: text } }); }
function save() { fireEvent.click(screen.getByRole('button', { name: '保存' })); }
beforeEach(() => {
  localStorage.clear(); useStudio.getState().setCollaboration('');
  useStudio.setState({ novelId: 'recovery', chapterId: 'recovery:1', textModel: null });
  vi.spyOn(api, 'legacyHistory').mockResolvedValue([]);
  vi.spyOn(api, 'chapters').mockResolvedValue([chapter()]);
});
afterEach(() => {
  cleanup(); clients.splice(0).forEach(client => client.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals();
  ['recovery:1', 'recovery:2'].forEach(id => { drafts.remove(id); conflicts.remove(id); conflicts.clearHistory(id); conflictResolutionDrafts.remove(id); });
  localStorage.clear();
});
it('keeps flag-off controls unchanged and starts no recovery unload listener', () => {
  setup(false); edit('OFF DRAFT');
  expect(screen.queryByRole('button', { name: '导出当前草稿' })).toBeNull();
  expect(screen.getAllByText(/有未保存修改/).length).toBeGreaterThan(0);
  const event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(false);
});
it('keeps newer typing dirty through a delayed save, coalesces repeated clicks and rebases only after acknowledgement', async () => {
  const pending = deferred<Chapter>(), request = vi.spyOn(api, 'saveChapter').mockReturnValue(pending.promise);
  setup(true, true); edit('FIRST'); save(); save();
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
  expect(screen.getByText('正在提交，等待后端确认…')).toBeTruthy();
  edit('NEWER 中文 👩🏽‍🚀');
  await act(async () => pending.resolve(chapter('FIRST', 4)));
  await waitFor(() => expect(drafts.load('recovery:1')?.baseVersion).toBe(4));
  expect(editor().value).toBe('NEWER 中文 👩🏽‍🚀');
  expect(screen.queryByText('后端已保存')).toBeNull();
  request.mockResolvedValue(chapter('NEWER 中文 👩🏽‍🚀', 5)); save();
  await screen.findByText('后端已保存'); expect(drafts.load('recovery:1')).toBeUndefined();
  expect(request.mock.calls[1][2]).toBe(4);
});
it('preserves a quota-failed buffer across a new server version and offers exact text export', async () => {
  const create = vi.fn((_blob: Blob) => 'blob:recovery'); vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
  const { query } = setup(true, true);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Full', 'QuotaExceededError'); });
  edit('不能丢的 <b>正文</b> 👩🏽‍🚀');
  expect(screen.getByRole('alert').textContent).toContain('仅在此页面内存');
  const event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true);
  act(() => { query.setQueryData(['chapter', 'file', 'recovery:1'], chapter('OTHER AUTHOR', 4)); });
  expect(editor().value).toBe('不能丢的 <b>正文</b> 👩🏽‍🚀');
  const dialog = await screen.findByRole('dialog'); expect(within(dialog).getByText(/冲突草稿仅在当前页面内存/)).toBeTruthy();
  fireEvent.click(within(dialog).getByRole('button', { name: '保留本地草稿并关闭' }));
  fireEvent.click(screen.getByRole('button', { name: '导出当前草稿' })); expect(create).toHaveBeenCalledOnce();
  edit('继续输入'); expect(screen.getByRole('button', { name: '保存' }).hasAttribute('disabled')).toBe(true);
});
it.each(['network', 'invalid', 'wrong-content'])('never marks saved on %s failure', async kind => {
  vi.spyOn(api, 'saveChapter').mockImplementation(async () => {
    if (kind === 'network') throw new TypeError('Network unavailable');
    return kind === 'invalid' ? {} as Chapter : chapter('NOT MY CANDIDATE', 4);
  });
  setup(); edit('PRESERVE'); save();
  await screen.findByText('后端未确认保存，请重试');
  expect(editor().value).toBe('PRESERVE'); expect(drafts.load('recovery:1')?.content).toBe('PRESERVE');
  expect(screen.queryByText('后端已保存')).toBeNull();
});
it('ends saving visibly even when a conflict lookup also loses connection', async () => {
  vi.spyOn(api, 'saveChapter').mockRejectedValue(new ApiError({ status: 409, code: 'VERSION_CONFLICT', message: 'conflict' }));
  vi.spyOn(api, 'chapter').mockRejectedValue(new TypeError('disconnected'));
  setup(); edit('OFFLINE CANDIDATE'); save();
  await screen.findByText('后端未确认保存，请重试');
  await waitFor(() => expect(api.chapter).toHaveBeenCalled());
  expect(drafts.load('recovery:1')?.content).toBe('OFFLINE CANDIDATE');
  expect(screen.getByRole('button', { name: '保存' }).hasAttribute('disabled')).toBe(false);
});
it('does not display a late conflict result in another chapter', async () => {
  const lookup = deferred<Chapter>();
  vi.spyOn(api, 'saveChapter').mockRejectedValue(new ApiError({ status: 409, code: 'VERSION_CONFLICT', message: 'conflict' }));
  const get = vi.spyOn(api, 'chapter').mockReturnValue(lookup.promise);
  setup(); edit('FIRST PRIVATE'); save(); await waitFor(() => expect(get).toHaveBeenCalled());
  act(() => useStudio.getState().setChapter('recovery:2')); edit('SECOND NEW');
  await act(async () => lookup.resolve(chapter('FIRST SERVER', 4)));
  expect(editor().value).toBe('SECOND NEW'); expect(screen.queryByRole('dialog')).toBeNull();
  expect(drafts.load('recovery:1')?.content).toBe('FIRST PRIVATE');
  expect(drafts.load('recovery:2')?.content).toBe('SECOND NEW');
});
it('fences a late success across an A-B-A chapter change and retains both candidates', async () => {
  const pending = deferred<Chapter>(); const request = vi.spyOn(api, 'saveChapter').mockReturnValue(pending.promise);
  setup(); edit('FIRST PENDING'); save(); await waitFor(() => expect(request).toHaveBeenCalled());
  act(() => { useStudio.getState().setChapter('recovery:2'); useStudio.getState().setChapter('recovery:1'); });
  edit('RETURNED NEWER'); await act(async () => pending.resolve(chapter('FIRST PENDING', 4)));
  expect(editor().value).toBe('RETURNED NEWER'); expect(drafts.load('recovery:1')?.baseVersion).toBe(3);
  expect(screen.queryByText('后端已保存')).toBeNull();
});
it('suppresses autosave and manual submit throughout composition and submits after it ends', async () => {
  const request = vi.spyOn(api, 'saveChapter').mockResolvedValue(chapter('中文组合完成', 4));
  setup(); fireEvent.compositionStart(editor()); edit('中文组合完成'); save();
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 1050)); });
  expect(request).not.toHaveBeenCalled(); expect(screen.getByText('正在输入…')).toBeTruthy();
  fireEvent.compositionEnd(editor()); save(); await screen.findByText('后端已保存');
});
it('hydrates a durable plain-text draft without borrowing stale server rich text', () => {
  drafts.save({ chapterId: 'recovery:1', content: 'RECOVERED RAW', baseVersion: 3, updatedAt: 'now' });
  setup(true, true);
  expect(editor().value).toBe('RECOVERED RAW'); expect(drafts.load('recovery:1')?.document).toBeUndefined();
  expect(screen.getByText('草稿已写入本机，待提交')).toBeTruthy();
});
it('reserves the pre-IME version before its first transaction and defers conflict focus until composition ends', async () => {
  const { query } = setup();
  fireEvent.compositionStart(editor());
  act(() => { query.setQueryData(['chapter', 'file', 'recovery:1'], chapter('EXTERNAL UPDATE', 4)); });
  await waitFor(() => expect(conflicts.load('recovery:1')?.server.version).toBe(4));
  expect(screen.queryByRole('dialog')).toBeNull();
  edit('中文输入结束'); fireEvent.compositionEnd(editor());
  const dialog = await screen.findByRole('dialog');
  expect(within(dialog).getByText('中文输入结束', { selector: 'pre' })).toBeTruthy();
  expect(editor().value).toBe('中文输入结束'); expect(drafts.load('recovery:1')?.baseVersion).toBe(3);
});
it('accepts the existing backend Markdown projection when the acknowledged document matches', async () => {
  vi.spyOn(api, 'saveChapter').mockResolvedValue({ ...chapter('正文', 4), content: '正文\n\n' });
  setup(); edit('正文'); save();
  await screen.findByText('后端已保存'); expect(drafts.load('recovery:1')).toBeUndefined();
});

it('AUDIT preserves a recovered plain-text candidate if the receipt acknowledges different prose', async () => {
  drafts.save({ chapterId: 'recovery:1', content: 'RECOVERED UNIQUE TEXT', baseVersion: 3, updatedAt: 'now' });
  vi.spyOn(api, 'saveChapter').mockResolvedValue(chapter('OTHER WRONG TEXT', 4));
  setup(); save();
  await screen.findByText('后端未确认保存，请重试');
  expect(editor().value).toBe('RECOVERED UNIQUE TEXT');
  expect(drafts.load('recovery:1')?.content).toBe('RECOVERED UNIQUE TEXT');
});
it('AUDIT shows the latest retained candidate when a persisted conflict is reopened after reload', async () => {
  const local = { chapterId: 'recovery:1', content: 'OLDER CANDIDATE', baseVersion: 2, updatedAt: 'old' };
  conflicts.save({ chapterId: local.chapterId, local, server: chapter('SAVED', 3), detectedAt: 'old-conflict' });
  drafts.save({ ...local, content: 'NEWER CANDIDATE', updatedAt: 'new' });
  setup();
  const dialog = await screen.findByRole('dialog');
  expect(within(dialog).getByText('NEWER CANDIDATE', { selector: 'pre' })).toBeTruthy();
});
it('normalizes recovered raw prose into a verifiable literal document before saving', async () => {
  const content = '<b>原始正文</b>\n👩🏽‍🚀 e\u0301';
  drafts.save({ chapterId: 'recovery:1', content, baseVersion: 3, updatedAt: 'now' });
  const request = vi.spyOn(api, 'saveChapter').mockImplementation(async (_id, _content, _version, document) => ({
    ...chapter(content, 4), document, content: '<b>原始正文</b>\n\n👩🏽‍🚀 e\u0301\n\n',
  }));
  setup(); save(); await screen.findByText('后端已保存');
  expect(request.mock.calls[0][3]).toEqual({ type: 'doc', content: [
    { type: 'paragraph', content: [{ type: 'text', text: '<b>原始正文</b>' }] },
    { type: 'paragraph', content: [{ type: 'text', text: '👩🏽‍🚀 e\u0301' }] },
  ] });
  expect(drafts.load('recovery:1')).toBeUndefined();
});
it('retains an explicit manual merge when its receipt belongs to other prose', async () => {
  const local = { chapterId: 'recovery:1', content: 'LOCAL', baseVersion: 2, updatedAt: 'old' };
  drafts.save(local); conflicts.save({ chapterId: local.chapterId, local, server: chapter('SAVED', 3), detectedAt: 'old-conflict' });
  vi.spyOn(api, 'saveChapter').mockResolvedValue(chapter('UNRELATED', 4));
  setup(); const dialog = await screen.findByRole('dialog');
  fireEvent.change(within(dialog).getByLabelText('手工解决草稿'), { target: { value: 'EXPLICIT MERGED CANDIDATE' } });
  fireEvent.click(within(dialog).getByRole('button', { name: '应用手工解决并保存' }));
  expect(drafts.load('recovery:1')?.document).toBeUndefined(); save();
  await screen.findByText('后端未确认保存，请重试');
  expect(editor().value).toBe('EXPLICIT MERGED CANDIDATE');
  expect(drafts.load('recovery:1')?.content).toBe('EXPLICIT MERGED CANDIDATE');
});
it('archives the old conflict and invalidates its stale manual resolution when a newer candidate hydrates', async () => {
  const local = { chapterId: 'recovery:1', content: 'OLDER', baseVersion: 2, updatedAt: 'old' };
  conflicts.save({ chapterId: local.chapterId, local, server: chapter('SAVED', 3), detectedAt: 'old-conflict' });
  conflictResolutionDrafts.save({ chapterId: local.chapterId, content: 'STALE MERGE', serverVersion: 3, sourceConflictDetectedAt: 'old-conflict', updatedAt: 'old' });
  drafts.save({ ...local, content: 'LATEST', updatedAt: 'new' });
  setup(true, true); const dialog = await screen.findByRole('dialog');
  expect((within(dialog).getByLabelText('手工解决草稿') as HTMLTextAreaElement).value).toBe('LATEST');
  expect(conflicts.list(local.chapterId).some(item => item.local.content === 'OLDER')).toBe(true);
  expect(editor().value).toBe('LATEST');
});
