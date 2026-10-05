// @vitest-environment jsdom
import { StrictMode, useMemo } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { api, ApiError, type Chapter } from './api';
import { drafts, conflicts, conflictResolutionDrafts } from './drafts';
import { useStudio } from './store';
import { generationRecovery } from './generationRecovery';
import { experimentalClient } from './experimental/api';
import { WorkspaceToolsPanel } from './experimental/WorkspaceToolsPanel';
import { defaultLayout } from './experimental/uxClient';
import { authorRequestKey, defaultAuthorRequestScope } from './novel/authorContextClient';
import { readLocalWorkspaceSelection, rememberLocalWorkspaceSelection } from './workspaceSelection';

// Real App state, version guards, local persistence and requests; only unrelated
// chrome and rich text are replaced. Editor.recovery tests mount real TipTap.
vi.mock('./Editor', async importOriginal => ({ ...(await importOriginal<typeof import('./Editor')>()), ChapterEditor: ({ content, onChange, onCompositionChange, writingPreferences, restoreAnchor }: any) => <>
  <textarea aria-label="Test chapter editor" value={content} onChange={event => onChange(event.target.value, doc(event.target.value))}
    onCompositionStart={() => onCompositionChange?.(true)} onCompositionEnd={() => onCompositionChange?.(false)} />
  <output aria-label="Applied reading preferences">{JSON.stringify(writingPreferences)}</output>
  <output aria-label="Applied chapter anchor">{JSON.stringify(restoreAnchor)}</output>
</> }));
vi.mock('./ui/AppShell', () => ({ AppShell: ({ main, status, sidebar, inspector, focusMode }: any) => <div data-testid="shell" data-focus={focusMode}>{sidebar}<main>{main}</main>{inspector}<footer>{status}</footer></div> }));
vi.mock('./novel/AiWritingPanel', () => ({ AiWritingPanel: ({ onGenerate, onGenerateVariants, onRetry, onCancel, onAccept, onReject, draft, variants, authorPreview }: any) => <>
  <button onClick={() => onGenerate('continue', '', '')}>Audit generate</button>
  <button onClick={() => {
    const state = useStudio.getState();
    const body = { novel_id: state.novelId, chapter_id: authorPreview.chapterId, chapter_version: authorPreview.chapterVersion, operation: 'continue', instruction: 'Exact reviewed exclusions', style: '', profile: authorPreview.profile, provider_id: state.textModel!.providerId, model_id: state.textModel!.modelId, source: authorPreview.source, selected_text: authorPreview.source, style_profile_id: authorPreview.styleProfileId, plot_plan_id: authorPreview.plotPlanId, request_scope: { ...defaultAuthorRequestScope, source_items: [{ key: 'a'.repeat(64), source_digest: 'b'.repeat(64), include: false }] } };
    onGenerate('continue', body.instruction, '', { requestBody: body, previewDigest: 'c'.repeat(64), chapterVersion: body.chapter_version, requestKey: authorRequestKey(body, authorPreview.context), requestId: 'reviewed-original-request' });
  }}>Generate exact reviewed request</button>
  <button onClick={() => onGenerateVariants('continue', '', 2, '')}>Audit variants</button>
  <button onClick={() => onRetry(draft || variants?.[0])}>Audit retry</button>
  <button onClick={onCancel}>Audit cancel</button>
  <button onClick={() => onAccept(draft || variants?.[0])}>Audit accept</button>
  <button onClick={() => onReject(draft || variants?.[0])}>Audit reject</button>
  <output aria-label="Audit draft">{draft ? JSON.stringify(draft) : ''}</output>
  <output aria-label="Audit variants">{JSON.stringify(variants || [])}</output>
</> }));
vi.mock('./novel/SourcePrivacyControl', () => ({ SourcePrivacyControl: () => null }));
vi.mock('./novel/EntryExperience', () => ({ EntryExperience: ({ initialToken, localHome, onOpenLocalSample }: any) => initialToken ? <div>Authorized project picker</div> : <>{localHome}<button onClick={() => onOpenLocalSample?.('recovery')}>Open confirmed isolated sample</button></> }));
vi.mock('./novel/NovelImportPanel', () => ({ NovelImportPanel: () => null }));
vi.mock('./novel/ChapterTree', () => ({ ChapterTree: () => null }));
vi.mock('./ui/FeatureLauncher', () => ({ FeatureLauncher: ({ onSelect }: any) => <button onClick={() => onSelect('experimental')}>Open broker</button> }));
vi.mock('./experimental/WritingFocusPanel', async original => ({ ...(await original<typeof import('./experimental/WritingFocusPanel')>()), WritingReferenceRail: () => <aside aria-label="Original authority reference rail" /> }));
vi.mock('./experimental/DeferredExperimentalWorkbench', () => ({ DeferredExperimentalWorkbench: ({ novelId, context, workspaceSection, ...props }: any) => {
  const client = useMemo(() => experimentalClient(novelId, context), [novelId, context.sessionToken, context.actor?.id]);
  return <WorkspaceToolsPanel {...props} client={client} initialSection={workspaceSection} />;
} }));
function doc(text: string) { return { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] }; }
function chapter(content = 'SAVED', version = 3, id = 'recovery:1'): Chapter {
  return { id, novel_id: 'recovery', number: 1, title: 'Synthetic chapter', content, document: doc(content), version, word_count: content.length, status: 'DRAFT' };
}
function taskState(id: string, status = 'COMPLETED', output = 'READY FIRST', baseVersion = 3) { return { id, novel_id: 'recovery', chapter_id: 'recovery:1', status, output, base_chapter_version: baseVersion }; }
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
const clients: QueryClient[] = [];
const preferences = { column_width: 'comfortable', font_size: 18, line_height: 1.75, paragraph_focus: false };
const resume = { item: { id: 'saved-workspace', version: 1, chapter_id: 'recovery:2', chapter_version: 10, chapter_title: 'Last chapter', anchor: { offset: 2, scroll: 16 },
  layout: defaultLayout, view: { focus_active: true, references_visible: false }, focus_state: 'READY', pending_tasks: [], stopping_note: 'Tomorrow review the lighthouse', recent_commands: [], pinned_chapter_ids: [], guide_dismissed: false, updated_at: '2026-10-05' }, availability: 'READY' };
let target: any;
let inventory: any[];
const response = (data: unknown) => new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
function setup(enabled = true, strict = false, author = false) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } }); clients.push(query);
  query.setQueryData(['novels'], inventory);
  query.setQueryData(['chapter', 'file', 'recovery:1'], chapter());
  query.setQueryData(['chapter', 'file', 'recovery:2'], chapter('SECOND', 10, 'recovery:2'));
  query.setQueryData(['chapters', 'file', 'recovery'], [chapter(), chapter('SECOND', 10, 'recovery:2')]);
  query.setQueryData(['archived-chapters', 'file', 'recovery'], []);
  query.setQueryData(['text-models'], []);
  query.setQueryData(['media-tasks', 'recovery'], { audiobook: [], motion: [] });
  query.setQueryData(['writing-goal', 'recovery'], { current_words: 0, target_words: 10, current_chapters: 2, target_chapters: 3, words_progress: 0 });
  query.setQueryData(['writing-focus-preferences', 'file', 'recovery', undefined], { preferences });
  query.setQueryData(['experimental-features', 'file'], { experimental: enabled, default_enabled: false, features: { 'experimental.author_context_inspector_v2': author, 'experimental.writing_recovery_v2': false, 'experimental.model_broker_v2': false, 'experimental.workspace_tools_v2': enabled, 'experimental.writing_focus_v2': enabled } });
  const app = <QueryClientProvider client={query}><App /></QueryClientProvider>;
  const view = render(strict ? <StrictMode>{app}</StrictMode> : app);
  return { query, view };
}
const editor = () => screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement;
function edit(text: string) { fireEvent.change(editor(), { target: { value: text } }); }
beforeEach(() => {
  inventory = [{ id: 'recovery', title: 'Synthetic' }];
  vi.spyOn(api, 'novels').mockImplementation(async () => inventory);
  target = { kind: 'chapter', id: 'recovery:2', version: 10, anchor: { offset: 2, scroll: 16 }, workspace: { layout: defaultLayout, view: { focus_active: true, references_visible: false }, focus_state: 'READY', reference_recovery_required: false, focus_preferences: { ...preferences, font_size: 24 } } };
  vi.spyOn(api, 'chapter').mockResolvedValue(chapter('SECOND', 10, 'recovery:2'));
  vi.stubGlobal('fetch', vi.fn(async (url: string) => response(url.endsWith('/resume/resolve') ? target : url.endsWith('/resume') ? (url.includes('/novels/first/') ? { item: null, availability: 'EMPTY' } : resume) : url.includes('/tasks?') ? { items: [], unavailable: [], truncated: false } : { items: [] })));
  localStorage.clear(); sessionStorage.clear(); useStudio.getState().setCollaboration('');
  useStudio.setState({ novelId: 'recovery', chapterId: 'recovery:1', textModel: null });
  vi.spyOn(api, 'generate').mockRejectedValue(new Error('must not create a generation'));
  vi.spyOn(api, 'accept').mockRejectedValue(new Error('must not accept'));
  vi.spyOn(api, 'legacyHistory').mockResolvedValue([]);
  vi.spyOn(api, 'chapters').mockImplementation(async id => id === 'recovery' ? [chapter()] : []);
  vi.spyOn(api, 'job').mockImplementation(async id => {
    const saved = generationRecovery.load('file', 'recovery:1');
    const variant = saved?.variants?.find(item => item.id === id);
    return taskState(id, variant ? (variant.status === 'ready' ? 'COMPLETED' : variant.status === 'failed' ? 'FAILED' : 'GENERATING') : saved?.job?.status ?? 'COMPLETED',
      variant?.output ?? saved?.job?.output ?? 'READY FIRST', variant?.baseChapterVersion ?? saved?.baseChapterVersion ?? 3);
  });
});
afterEach(() => {
  cleanup(); clients.splice(0).forEach(client => client.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals();
  ['recovery:1', 'recovery:2'].forEach(id => { drafts.remove(id); conflicts.remove(id); conflicts.clearHistory(id); conflictResolutionDrafts.remove(id); });
  localStorage.clear(); sessionStorage.clear();
});


async function restore() {
  fireEvent.click(await screen.findByRole('button', { name: '查看上次工作现场' }));
  fireEvent.click(await screen.findByRole('button', { name: '恢复章节位置' }));
}
it('reopens the saved chapter through current authority and applies original reading/split state only after explicit restore', async () => {
  setup(true, true);
  await screen.findByText('上次工作：Last chapter');
  expect(useStudio.getState().chapterId).toBe('recovery:1');
  expect(api.chapter).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Original authority reference rail')).toBeTruthy();
  await restore();
  await waitFor(() => expect(useStudio.getState().chapterId).toBe('recovery:2'));
  expect(editor().value).toBe('SECOND');
  expect(screen.getByLabelText('Applied reading preferences').textContent).toContain('24');
  expect(screen.queryByLabelText('Original authority reference rail')).toBeNull();
  expect(screen.getByLabelText('Applied chapter anchor').textContent).toContain('"offset":2');
  expect(screen.getByTestId('shell').getAttribute('data-focus')).toBe('true');
  expect(api.chapter).toHaveBeenCalledWith('recovery:2', expect.objectContaining({ sessionToken: '' }));
  expect(api.generate).not.toHaveBeenCalled(); expect(api.accept).not.toHaveBeenCalled();
});
it('does not navigate away from dirty manuscript', async () => {
  setup(); edit('UNSAVED MANUSCRIPT');
  await restore(); await screen.findByText(/当前或目标章节有未保存草稿/);
  expect(editor().value).toBe('UNSAVED MANUSCRIPT'); expect(useStudio.getState().chapterId).toBe('recovery:1');
  expect(api.chapter).not.toHaveBeenCalled();
});
it('retains newer typing when fresh chapter verification is delayed', async () => {
  const pending = deferred<Chapter>(); vi.mocked(api.chapter).mockReturnValue(pending.promise);
  setup(); await restore(); await waitFor(() => expect(api.chapter).toHaveBeenCalledTimes(1));
  edit('TYPED WHILE REOPENING');
  await act(async () => pending.resolve(chapter('SECOND', 10, 'recovery:2')));
  expect(editor().value).toBe('TYPED WHILE REOPENING'); expect(useStudio.getState().chapterId).toBe('recovery:1');
  expect(screen.getByLabelText('Applied reading preferences').textContent).toContain('18');
});
it('discards a delayed verification after the restore panel is dismissed', async () => {
  const pending = deferred<Chapter>(); vi.mocked(api.chapter).mockReturnValue(pending.promise);
  setup(); await restore(); await waitFor(() => expect(api.chapter).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: '任务中心' }));
  await act(async () => pending.resolve(chapter('SECOND', 10, 'recovery:2')));
  expect(useStudio.getState().chapterId).toBe('recovery:1'); expect(editor().value).toBe('SAVED');
});
it('rejects a changed source version instead of applying an old anchor or layout', async () => {
  vi.mocked(api.chapter).mockResolvedValue(chapter('NEW SERVER VERSION', 11, 'recovery:2'));
  setup(); await restore(); await screen.findByText(/章节版本已变化，未套用旧现场/);
  expect(useStudio.getState().chapterId).toBe('recovery:1');
  expect(screen.getByLabelText('Original authority reference rail')).toBeTruthy();
});
it('preserves current U04 settings when the saved reference/preferences pointer changed', async () => {
  target.workspace.focus_state = 'CHANGED'; delete target.workspace.focus_preferences;
  setup(); await restore();
  await waitFor(() => expect(useStudio.getState().chapterId).toBe('recovery:2'));
  expect(screen.getByLabelText('Applied reading preferences').textContent).toContain('18');
  expect(screen.getByLabelText('Original authority reference rail')).toBeTruthy();
});
it('does not fetch resume metadata or expose the new entry when the server flag is off', async () => {
  setup(false); await act(async () => {});
  expect(screen.queryByLabelText('当前项目上次工作')).toBeNull();
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/workspace/'))).toBe(false);
});
it('does not reopen after chapter A to B to A while current authority is being verified', async () => {
  const pending = deferred<Chapter>(); vi.mocked(api.chapter).mockReturnValue(pending.promise);
  setup(); await restore(); await waitFor(() => expect(api.chapter).toHaveBeenCalledTimes(1));
  act(() => useStudio.setState({ chapterId: 'recovery:2' }));
  act(() => useStudio.setState({ chapterId: 'recovery:1' }));
  await act(async () => pending.resolve(chapter('SECOND', 10, 'recovery:2')));
  expect(useStudio.getState().chapterId).toBe('recovery:1');
  expect(screen.getByLabelText('Applied reading preferences').textContent).toContain('18');
});
it('preserves an existing target chapter draft instead of replacing it with the saved workspace', async () => {
  drafts.save({ chapterId: 'recovery:2', content: 'TARGET DRAFT', document: doc('TARGET DRAFT'), baseVersion: 10, updatedAt: '2026-10-05' });
  setup(); await restore(); await screen.findByText(/当前或目标章节有未保存草稿/);
  expect(useStudio.getState().chapterId).toBe('recovery:1');
  expect(drafts.load('recovery:2')?.content).toBe('TARGET DRAFT'); expect(api.chapter).not.toHaveBeenCalled();
});
it('blocks reopening while IME composition has reserved the current buffer', async () => {
  setup(); fireEvent.compositionStart(editor()); await restore();
  await screen.findByText(/当前或目标章节有未保存草稿/);
  expect(useStudio.getState().chapterId).toBe('recovery:1'); expect(api.chapter).not.toHaveBeenCalled();
});
it('remembers an explicitly selected non-first project and reopens it after a fresh inventory check', async () => {
  inventory = [{ id: 'first', title: 'First project' }, { id: 'recovery', title: 'Synthetic' }];
  const { view } = setup();
  await screen.findByText('上次工作：Last chapter');
  fireEvent.click(screen.getByRole('button', { name: '切换本机作品' }));
  fireEvent.click(await screen.findByRole('button', { name: 'First project' }));
  await waitFor(() => expect(useStudio.getState().novelId).toBe('first'));
  fireEvent.click(screen.getByRole('button', { name: '切换本机作品' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Synthetic' }));
  await waitFor(() => expect(readLocalWorkspaceSelection()).toEqual({ state: 'SAVED', projectId: 'recovery' }));
  view.unmount();
  useStudio.setState({ novelId: '', chapterId: '' });
  const pending = deferred<any[]>(); vi.mocked(api.novels).mockReturnValue(pending.promise);
  setup(); await act(async () => {});
  expect(useStudio.getState().novelId).toBe('');
  await act(async () => pending.resolve(inventory));
  await waitFor(() => expect(useStudio.getState().novelId).toBe('recovery'));
  expect(api.novels).toHaveBeenCalled();
});
it('leaves the picker open when a saved project is unavailable rather than silently choosing the first', async () => {
  inventory = [{ id: 'first', title: 'First project' }];
  rememberLocalWorkspaceSelection('deleted-or-revoked-project');
  useStudio.setState({ novelId: '', chapterId: '' });
  setup();
  await screen.findByText(/上次项目当前不存在或不可访问/);
  expect(useStudio.getState().novelId).toBe('');
  expect(screen.getByRole('button', { name: 'First project' })).toBeTruthy();
});
it('never consumes the local-author selection hint in an authenticated session', async () => {
  rememberLocalWorkspaceSelection('recovery');
  useStudio.setState({ sessionToken: 'other-session', novelId: '', chapterId: '' });
  setup(); await screen.findByText('Authorized project picker');
  expect(useStudio.getState().novelId).toBe(''); expect(api.novels).not.toHaveBeenCalled();
});
it('keeps a dirty buffer on an attempted local project switch', async () => {
  setup(); edit('DO NOT LOSE THIS');
  fireEvent.click(screen.getByRole('button', { name: '切换本机作品' }));
  expect(useStudio.getState().novelId).toBe('recovery');
  expect(editor().value).toBe('DO NOT LOSE THIS');
});

it('opens a confirmed sample only after refreshing original project inventory', async () => {
  inventory = []; useStudio.setState({ novelId: '', chapterId: '' });
  const { query } = setup();
  await waitFor(() => expect(api.novels).toHaveBeenCalledTimes(1));
  const pending = deferred<any[]>(); vi.mocked(api.novels).mockReturnValueOnce(pending.promise);
  fireEvent.click(screen.getByRole('button', { name: 'Open confirmed isolated sample' }));
  await waitFor(() => expect(api.novels).toHaveBeenCalledTimes(2));
  expect(useStudio.getState().novelId).toBe('');
  const rows = [{ id: 'recovery', title: '灯塔来信 · 独立练习' }];
  await act(async () => pending.resolve(rows));
  await waitFor(() => expect(useStudio.getState().novelId).toBe('recovery'));
  expect(query.getQueryData(['novels'])).toEqual(rows);
  expect(readLocalWorkspaceSelection()).toEqual({ state: 'SAVED', projectId: 'recovery' });
});
it('does not open a sample after session changes during original inventory refresh', async () => {
  inventory = []; useStudio.setState({ novelId: '', chapterId: '' }); setup();
  await waitFor(() => expect(api.novels).toHaveBeenCalledTimes(1));
  const pending = deferred<any[]>(); vi.mocked(api.novels).mockReturnValueOnce(pending.promise);
  fireEvent.click(screen.getByRole('button', { name: 'Open confirmed isolated sample' }));
  await waitFor(() => expect(api.novels).toHaveBeenCalledTimes(2));
  act(() => useStudio.setState({ sessionToken: 'new-session', novelId: '', chapterId: '' }));
  await act(async () => pending.resolve([{ id: 'recovery', title: 'Old sample' }]));
  expect(useStudio.getState().novelId).toBe('');
  expect(screen.getByText('Authorized project picker')).toBeTruthy();
});
it('retains a picker and explanation when the confirmed sample is no longer in inventory', async () => {
  inventory = []; useStudio.setState({ novelId: '', chapterId: '' }); setup();
  await waitFor(() => expect(api.novels).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Open confirmed isolated sample' }));
  await screen.findByText(/练习项目当前不存在或不可访问/);
  expect(useStudio.getState().novelId).toBe('');
});

it.each([false, true])('keeps the original three workspace rows with resume enabled=%s', async enabled => {
  setup(enabled);
  if (enabled) await screen.findByText('上次工作：Last chapter');
  const workspace = document.querySelector('.novel-writing-workspace')!;
  const children = Array.from(workspace.children);
  expect(children).toHaveLength(3);
  expect(children[0].classList.contains('novel-workspace-chrome')).toBe(true);
  expect(children[0].querySelector('.editorbar')).not.toBeNull();
  expect(children[1].classList.contains('writing-editor-row')).toBe(true);
  expect(children[1].contains(editor())).toBe(true);
  expect(children[0].querySelector('[aria-label="当前项目上次工作"]') !== null).toBe(enabled);
  expect(workspace.querySelector(':scope > [aria-label="当前项目上次工作"]')).toBeNull();
});
it('keeps a long stopping note intact in its editor while the chrome uses a bounded preview', async () => {
  const note = '核对灯塔来信与人物动机。'.repeat(150);
  vi.stubGlobal('fetch', vi.fn(async (url: string) => response(url.endsWith('/resume') ? { ...resume, item: { ...resume.item, stopping_note: note } } : { items: [] })));
  setup();
  await screen.findByText('上次工作：Last chapter');
  const preview = document.querySelector('.workspace-resume-summary__note')!;
  expect(preview.textContent).toBe(note);
  expect(preview.closest('.novel-workspace-chrome')).not.toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '查看上次工作现场' }));
  await waitFor(() => expect((screen.getByLabelText('停止点与下次要做的事') as HTMLTextAreaElement).value).toBe(note));
});
it('adds no grid row or editor remount when a volatile-memory draft warning appears', async () => {
  const { query } = setup(); await screen.findByText('上次工作：Last chapter');
  act(() => query.setQueryData(['experimental-features', 'file'], { experimental: true, default_enabled: false, features: { 'experimental.workspace_tools_v2': true, 'experimental.writing_focus_v2': true, 'experimental.writing_recovery_v2': true } }));
  const originalEditor = editor();
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Full', 'QuotaExceededError'); });
  edit('DRAFT REMAINS VISIBLE');
  await screen.findByText(/本机草稿写入失败。当前修改仅在此页面内存中/);
  const workspace = document.querySelector('.novel-writing-workspace')!;
  expect(workspace.children).toHaveLength(3);
  expect(workspace.children[0].querySelector('[role="alert"]')).not.toBeNull();
  expect(editor()).toBe(originalEditor); expect(editor().value).toBe('DRAFT REMAINS VISIBLE');
});
it('keeps the original save controls outside the shrinking metadata group in recovery state', async () => {
  const { query } = setup(); await screen.findByText('上次工作：Last chapter');
  act(() => query.setQueryData(['experimental-features', 'file'], { experimental: true, default_enabled: false, features: { 'experimental.workspace_tools_v2': true, 'experimental.writing_focus_v2': true, 'experimental.writing_recovery_v2': true } }));
  const originalEditor = editor(); edit('INTACT RECOVERY BUFFER');
  const bar = document.querySelector('.novel-workspace-chrome > .editorbar')!;
  const metadata = bar.querySelector(':scope > .novel-editor-metadata')!;
  const actions = bar.querySelector(':scope > .save-controls')!;
  expect(metadata.querySelector('.editorbar__identity')).not.toBeNull();
  expect(metadata.querySelector('.writing-goal')).not.toBeNull();
  expect(actions.querySelector('button')?.textContent).toBe('保存');
  expect(screen.getByRole('button', { name: '导出当前草稿' }).parentElement).toBe(actions);
  expect(editor()).toBe(originalEditor); expect(editor().value).toBe('INTACT RECOVERY BUFFER');
});

function otherProjectSearch() {
  inventory.push({ id: 'other', title: 'Other authorized project' });
  const result = { kind: 'chapter', id: 'other:2', novel_id: 'other', branch_id: null, version: 5, revision: 'exact-source', title: 'Other chapter', aliases: [], offset: 2, snippet: 'OTHER SAVED', feature: 'editor' };
  const originalFetch = vi.mocked(fetch).getMockImplementation()!;
  vi.mocked(fetch).mockImplementation(async (url: any, init?: any) => response(String(url).endsWith('/writing-goal') ? { current_words: 11, target_words: 20, current_chapters: 1, target_chapters: 2, words_progress: .55 } : String(url).includes('/search?') ? { items: [result], branch_sources_available: true, suggestions: [], match_count: 1 } : String(url).endsWith('/search/resolve') ? { ...result, anchor: { offset: 2, scroll: 0 } } : await (await originalFetch(url, init)).json()));
  const destination = { ...chapter('OTHER SAVED', 5, 'other:2'), novel_id: 'other', number: 2 };
  vi.mocked(api.chapter).mockResolvedValue(destination);
  return destination;
}
async function openSearchResult() {
  fireEvent.click(await screen.findByRole('button', { name: 'Open broker' }));
  fireEvent.click(await screen.findByRole('button', { name: '搜索与命令' }));
  fireEvent.click(await screen.findByRole('button', { name: '打开章节位置' }));
}
it('opens another authorized project only after original inventory and exact chapter version revalidation', async () => {
  const destination = otherProjectSearch();setup(true, true);await screen.findByText('上次工作：Last chapter');
  await openSearchResult();await waitFor(() => expect(useStudio.getState().chapterId).toBe('other:2'));
  expect(useStudio.getState().novelId).toBe('other');expect(api.novels).toHaveBeenCalled();expect(api.chapter).toHaveBeenCalledWith('other:2', expect.any(Object));
  await waitFor(() => expect(editor().value).toBe(destination.content));expect(api.generate).not.toHaveBeenCalled();
});
it('refuses cross-project search navigation while manuscript is dirty', async () => {
  otherProjectSearch();setup();await screen.findByText('上次工作：Last chapter');edit('LOCAL UNSAVED');
  await openSearchResult();await screen.findByText(/再打开另一作品的搜索结果/);
  expect(useStudio.getState().novelId).toBe('recovery');expect(editor().value).toBe('LOCAL UNSAVED');expect(api.chapter).not.toHaveBeenCalled();
});
it('drops a delayed cross-project source when the author types during revalidation', async () => {
  const destination = otherProjectSearch(), pending = deferred<Chapter>();vi.mocked(api.chapter).mockReturnValue(pending.promise);
  setup();await screen.findByText('上次工作：Last chapter');await openSearchResult();await waitFor(() => expect(api.chapter).toHaveBeenCalled());
  edit('NEW INPUT');await act(async () => pending.resolve(destination));
  expect(useStudio.getState().novelId).toBe('recovery');expect(editor().value).toBe('NEW INPUT');
});
it('does not navigate to a search project removed from the refreshed original inventory', async () => {
  otherProjectSearch();setup();await screen.findByText('上次工作：Last chapter');vi.mocked(api.novels).mockResolvedValue([{ id: 'recovery', title: 'Synthetic' }] as any);
  await openSearchResult();await screen.findByText(/搜索目标当前不可读或版本已变/);
  expect(useStudio.getState().novelId).toBe('recovery');expect(api.chapter).not.toHaveBeenCalled();
});


it('forwards the actual reviewed source exclusions through App into the original author endpoint', async () => {
  useStudio.setState({ textModel: { providerId: 'fixture', modelId: 'registered-local' } });
  const fetch = vi.mocked(globalThis.fetch);
  fetch.mockImplementation(async (url: any, init?: RequestInit) => String(url).endsWith('/author-context/generate') ? response({ job_id: 'reviewed-original-job', base_chapter_version: 3 }) : response({ items: [] }));
  setup(true, false, true); await screen.findByLabelText('Test chapter editor');
  fireEvent.click(screen.getByRole('button', { name: 'Generate exact reviewed request' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/author-context/generate'))).toBe(true));
  const send = fetch.mock.calls.find(([url]) => String(url).endsWith('/author-context/generate'))!;
  expect(JSON.parse(String(send[1]?.body))).toMatchObject({ preview_digest: 'c'.repeat(64), generation_request_id: 'reviewed-original-request', instruction: 'Exact reviewed exclusions', request_scope: { source_items: [{ key: 'a'.repeat(64), source_digest: 'b'.repeat(64), include: false }] } });
  expect(api.generate).not.toHaveBeenCalled();
});

it('cannot fall back to legacy generation when the enabled request inspector receipt is omitted', async () => {
  useStudio.setState({ textModel: { providerId: 'fixture', modelId: 'registered-local' } });
  setup(true, false, true); await screen.findByLabelText('Test chapter editor');
  fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  await waitFor(() => expect(screen.getByLabelText('Audit draft').textContent).toContain('请先检查本次真实请求'));
  expect(api.generate).not.toHaveBeenCalled();
  expect(vi.mocked(globalThis.fetch).mock.calls.some(([url]) => String(url).includes('/author-context/generate'))).toBe(false);
});
