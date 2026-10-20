// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { api, ApiError, type Chapter } from './api';
import { drafts, conflicts, conflictResolutionDrafts } from './drafts';
import { useStudio } from './store';
import { generationRecovery } from './generationRecovery';

// Real App state, version guards, local persistence and requests; only unrelated
// chrome and rich text are replaced. Editor.recovery tests mount real TipTap.
vi.mock('./Editor', async importOriginal => ({ ...(await importOriginal<typeof import('./Editor')>()), ChapterEditor: ({ content, onChange, onCompositionChange }: any) =>
  <textarea aria-label="Test chapter editor" value={content} onChange={event => onChange(event.target.value, doc(event.target.value))}
    onCompositionStart={() => onCompositionChange?.(true)} onCompositionEnd={() => onCompositionChange?.(false)} /> }));
vi.mock('./ui/AppShell', () => ({ AppShell: ({ main, status, inspector, sidebar }: any) => <>{sidebar}<main>{main}</main><aside>{inspector}</aside><footer>{status}</footer></> }));
vi.mock('./novel/AiWritingPanel', () => ({ AiWritingPanel: ({ onGenerate, onGenerateVariants, onRetry, onCancel, onAccept, onReject, draft, variants }: any) => <>
  <button onClick={() => onGenerate('continue', '', '')}>Audit generate</button>
  <button onClick={() => onGenerateVariants('continue', '', 2, '')}>Audit variants</button>
  <button onClick={() => onRetry(draft || variants?.[0])}>Audit retry</button>
  <button onClick={onCancel}>Audit cancel</button>
  <button onClick={() => onAccept(draft || variants?.[0])}>Audit accept</button>
  <button onClick={() => onReject(draft || variants?.[0])}>Audit reject</button>
  <output aria-label="Audit draft">{draft ? JSON.stringify(draft) : ''}</output>
  <output aria-label="Audit variants">{JSON.stringify(variants || [])}</output>
</> }));
vi.mock('./novel/SourcePrivacyControl', () => ({ SourcePrivacyControl: () => null }));
vi.mock('./novel/ChapterTree', () => ({ ChapterTree: () => null }));
vi.mock('./ui/FeatureLauncher', () => ({ FeatureLauncher: ({ onSelect }: any) => <button onClick={() => onSelect('experimental')}>Open broker</button> }));
vi.mock('./experimental/DeferredExperimentalWorkbench', () => ({ DeferredExperimentalWorkbench: ({ onNavigate }: any) => <>
  <button onClick={() => onNavigate({ kind: 'generation', id: 'author-one', chapter_id: 'recovery:1', version: 3, signal: navigationController?.signal })}>Open current author job</button>
  <button onClick={() => onNavigate({ kind: 'generation', id: 'author-two', chapter_id: 'recovery:2', version: 10 })}>Open other author job</button>
  <button onClick={() => onNavigate({ kind: 'generation', id: 'author-newest', chapter_id: 'recovery:1', version: 3 })}>Open newer author job</button>
  <button onClick={() => onNavigate({ kind: 'feature', id: 'history', feature: 'history' })}>Leave tasks</button>
</> }));
function doc(text: string) { return { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] }; }
function chapter(content = 'SAVED', version = 3, id = 'recovery:1'): Chapter {
  return { id, novel_id: 'recovery', number: 1, title: 'Synthetic chapter', content, document: doc(content), version, word_count: content.length, status: 'DRAFT' };
}
function taskState(id: string, status = 'COMPLETED', output = 'READY FIRST', baseVersion = 3) { return { id, novel_id: 'recovery', chapter_id: 'recovery:1', status, output, base_chapter_version: baseVersion }; }
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
const clients: QueryClient[] = [];
let navigationController: AbortController | undefined;
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
  query.setQueryData(['experimental-features', 'file'], { experimental: enabled, default_enabled: false, features: { 'experimental.writing_recovery_v2': false, 'experimental.model_broker_v2': false, 'experimental.workspace_tools_v2': enabled } });
  const app = <QueryClientProvider client={query}><App /></QueryClientProvider>;
  const view = render(strict ? <StrictMode>{app}</StrictMode> : app);
  return { query, view };
}
const editor = () => screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement;
function edit(text: string) { fireEvent.change(editor(), { target: { value: text } }); }
beforeEach(() => {
  navigationController = undefined;
  localStorage.clear(); sessionStorage.clear(); useStudio.getState().setCollaboration('');
  useStudio.setState({ novelId: 'recovery', chapterId: 'recovery:1', textModel: null });
  vi.spyOn(api, 'generate').mockRejectedValue(new Error('must not create a generation'));
  vi.spyOn(api, 'accept').mockRejectedValue(new Error('must not accept'));
  vi.spyOn(api, 'legacyHistory').mockResolvedValue([]);
  vi.spyOn(api, 'chapters').mockResolvedValue([chapter()]);
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


async function openTasks() {
  fireEvent.click(screen.getByRole('button', { name: 'Open broker' }));
  await screen.findByRole('button', { name: 'Open current author job' });
}
it('opens the exact original text job without broker or recovery flags, generation or acceptance', async () => {
  vi.mocked(api.job).mockResolvedValue({ ...taskState('author-one', 'COMPLETED', 'EXACT AUTHOR OUTPUT'), source: 'ORIGINAL SOURCE' });
  setup(); await openTasks();
  fireEvent.click(screen.getByRole('button', { name: 'Open current author job' }));
  await waitFor(() => expect(screen.getByLabelText('Audit draft').textContent).toContain('EXACT AUTHOR OUTPUT'));
  expect(api.job).toHaveBeenCalledTimes(2);
  expect(api.job).toHaveBeenCalledWith('author-one', expect.objectContaining({ sessionToken: '' }));
  expect(screen.getByLabelText('Audit draft').textContent).toContain('ORIGINAL SOURCE');
  expect(editor().value).toBe('SAVED');
  expect(api.generate).not.toHaveBeenCalled(); expect(api.accept).not.toHaveBeenCalled();
});
it('opens a different chapter and preserves the previous unsaved manuscript', async () => {
  vi.mocked(api.job).mockResolvedValue({ ...taskState('author-two', 'COMPLETED', 'SECOND AUTHOR OUTPUT', 10), chapter_id: 'recovery:2' });
  setup(); edit('UNSAVED ORIGINAL MANUSCRIPT'); await openTasks();
  fireEvent.click(screen.getByRole('button', { name: 'Open other author job' }));
  await waitFor(() => expect(screen.getByLabelText('Audit draft').textContent).toContain('SECOND AUTHOR OUTPUT'));
  expect(useStudio.getState().chapterId).toBe('recovery:2');
  expect(drafts.load('recovery:1')?.content).toBe('UNSAVED ORIGINAL MANUSCRIPT');
  expect(editor().value).toBe('SECOND'); expect(api.job).toHaveBeenCalledTimes(3);
});
it('keeps a stale original source version visibly blocked from acceptance', async () => {
  vi.mocked(api.job).mockResolvedValue(taskState('author-one', 'COMPLETED', 'OLD VERSION OUTPUT', 2));
  setup(); await openTasks(); fireEvent.click(screen.getByRole('button', { name: 'Open current author job' }));
  await waitFor(() => expect(screen.getByLabelText('Audit draft').textContent).toContain('OLD VERSION OUTPUT'));
  const value = JSON.parse(screen.getByLabelText('Audit draft').textContent!);
  expect(generationRecovery.load('file', 'recovery:1')?.baseChapterVersion).toBe(2); expect(value.acceptBlocked).toBe(true);
  expect(editor().value).toBe('SAVED'); expect(api.accept).not.toHaveBeenCalled();
});
it('rechecks original authority at the destination after chapter navigation', async () => {
  vi.mocked(api.job).mockResolvedValueOnce({ ...taskState('author-two', 'COMPLETED', 'REVOKED OUTPUT', 10), chapter_id: 'recovery:2' })
    .mockRejectedValue(new ApiError({ status: 403, code: 'DENIED', message: 'Denied' }));
  setup(); await openTasks(); fireEvent.click(screen.getByRole('button', { name: 'Open other author job' }));
  await waitFor(() => expect(api.job).toHaveBeenCalledTimes(2));
  expect(screen.getByLabelText('Audit draft').textContent).not.toContain('REVOKED OUTPUT');
  expect(generationRecovery.load('file', 'recovery:2')).toBeUndefined(); expect(editor().value).toBe('SECOND');
});
it('discards old responses after chapter A to B to A even though coordinates match again', async () => {
  const pending = deferred<any>(); vi.mocked(api.job).mockReturnValue(pending.promise);
  setup(); await openTasks(); fireEvent.click(screen.getByRole('button', { name: 'Open current author job' }));
  act(() => useStudio.getState().setChapter('recovery:2'));
  act(() => useStudio.getState().setChapter('recovery:1'));
  await act(async () => pending.resolve(taskState('author-one', 'COMPLETED', 'OBSOLETE SECRET')));
  expect(screen.getByLabelText('Audit draft').textContent).not.toContain('OBSOLETE SECRET');
  expect(api.job).toHaveBeenCalledTimes(1);
});
it('discards a delayed task lookup after leaving the task view', async () => {
  const pending = deferred<any>(); vi.mocked(api.job).mockReturnValue(pending.promise);
  setup(); await openTasks(); fireEvent.click(screen.getByRole('button', { name: 'Open current author job' }));
  fireEvent.click(screen.getByRole('button', { name: 'Leave tasks' }));
  await act(async () => pending.resolve(taskState('author-one', 'COMPLETED', 'DISMISSED OUTPUT')));
  expect(screen.getByLabelText('Audit draft').textContent).not.toContain('DISMISSED OUTPUT');
  expect(api.job).toHaveBeenCalledTimes(1);
});
it('only opens the newest explicitly selected original task', async () => {
  const pending = deferred<any>();
  vi.mocked(api.job).mockImplementation(id => id === 'author-one' ? pending.promise : Promise.resolve(taskState(id, 'COMPLETED', 'NEWEST OUTPUT')));
  setup(); await openTasks(); fireEvent.click(screen.getByRole('button', { name: 'Open current author job' }));
  fireEvent.click(screen.getByRole('button', { name: 'Open newer author job' }));
  await waitFor(() => expect(screen.getByLabelText('Audit draft').textContent).toContain('NEWEST OUTPUT'));
  await act(async () => pending.resolve(taskState('author-one', 'COMPLETED', 'LATE OLD OUTPUT')));
  expect(screen.getByLabelText('Audit draft').textContent).toContain('NEWEST OUTPUT');
  expect(screen.getByLabelText('Audit draft').textContent).not.toContain('LATE OLD OUTPUT');
});
it('drops a pending original read when its workspace entry is disabled', async () => {
  const pending = deferred<any>(); vi.mocked(api.job).mockReturnValue(pending.promise);
  const { query } = setup(); await openTasks(); fireEvent.click(screen.getByRole('button', { name: 'Open current author job' }));
  await act(async () => { query.setQueryData(['experimental-features', 'file'], { experimental: false, features: {} }); });
  await act(async () => pending.resolve(taskState('author-one', 'COMPLETED', 'DISABLED SECRET')));
  expect(screen.getByLabelText('Audit draft').textContent).not.toContain('DISABLED SECRET');
  expect(api.job).toHaveBeenCalledTimes(1);
});
it('rejects mismatched original job coordinates without opening or changing manuscript', async () => {
  vi.mocked(api.job).mockResolvedValue({ ...taskState('author-one', 'COMPLETED', 'WRONG SCOPE OUTPUT'), novel_id: 'other-project' });
  setup(); edit('PRESERVE MY DRAFT'); await openTasks(); fireEvent.click(screen.getByRole('button', { name: 'Open current author job' }));
  await waitFor(() => expect(api.job).toHaveBeenCalledTimes(1));
  expect(screen.getByLabelText('Audit draft').textContent).not.toContain('WRONG SCOPE OUTPUT');
  expect(editor().value).toBe('PRESERVE MY DRAFT');
});

it('drops a lookup dismissed inside the child task surface without parent navigation', async () => {
  navigationController = new AbortController();
  const pending = deferred<any>(); vi.mocked(api.job).mockReturnValue(pending.promise);
  setup(); await openTasks(); fireEvent.click(screen.getByRole('button', { name: 'Open current author job' }));
  navigationController.abort();
  await act(async () => pending.resolve(taskState('author-one', 'COMPLETED', 'CHILD DISMISSED OUTPUT')));
  expect(screen.getByLabelText('Audit draft').textContent).not.toContain('CHILD DISMISSED OUTPUT');
  expect(api.job).toHaveBeenCalledTimes(1);
});
