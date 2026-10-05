// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { api, ApiError, setCollaborationContext, type Chapter } from './api';
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
vi.mock('./experimental/ExperimentalWorkbench', () => ({ EXPERIMENTAL_GROUPS: [], EXPERIMENTAL_TABS: [['model_broker_v2','Broker']], ExperimentalWorkbench: ({ onOpenGeneration }: any) => <><button onClick={() => void onOpenGeneration('broker-one', 'recovery:1').catch(() => {})}>Open current broker job</button><button onClick={() => void onOpenGeneration('broker-two', 'recovery:2').catch(() => {})}>Open other broker job</button></> }));
function doc(text: string) { return { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] }; }
function chapter(content = 'SAVED', version = 3, id = 'recovery:1'): Chapter {
  return { id, novel_id: 'recovery', number: 1, title: 'Synthetic chapter', content, document: doc(content), version, word_count: content.length, status: 'DRAFT' };
}
function taskState(id: string, status = 'COMPLETED', output = 'READY FIRST', baseVersion = 3) { return { id, novel_id: 'recovery', chapter_id: 'recovery:1', status, output, base_chapter_version: baseVersion }; }
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
  query.setQueryData(['experimental-features', 'file'], { experimental: enabled, default_enabled: false, features: { 'experimental.writing_recovery_v2': enabled, 'experimental.model_broker_v2': enabled } });
  const app = <QueryClientProvider client={query}><App /></QueryClientProvider>;
  const view = render(strict ? <StrictMode>{app}</StrictMode> : app);
  return { query, view };
}
const editor = () => screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement;
function edit(text: string) { fireEvent.change(editor(), { target: { value: text } }); }
function save() { fireEvent.click(screen.getByRole('button', { name: '保存' })); }
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); useStudio.getState().setCollaboration('');
  useStudio.setState({ novelId: 'recovery', chapterId: 'recovery:1', textModel: null });
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

it('opens an existing broker job only after fresh authorization and retains original review actions', async () => {
  vi.mocked(api.job).mockResolvedValue(taskState('broker-one', 'COMPLETED', 'AUTHORIZED BROKER DRAFT'));
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Open broker' }));
  fireEvent.click(screen.getByRole('button', { name: 'Open current broker job' }));
  await waitFor(() => expect(screen.getByLabelText('Audit draft').textContent).toContain('AUTHORIZED BROKER DRAFT'));
  expect(api.job).toHaveBeenCalledWith('broker-one', expect.objectContaining({ sessionToken: '' }));
  expect(editor().value).toBe('SAVED');
});
it('navigates to the authorized job chapter and keeps the previous unsaved manuscript', async () => {
  vi.mocked(api.job).mockResolvedValue({ ...taskState('broker-two', 'COMPLETED', 'SECOND BROKER DRAFT', 10), chapter_id: 'recovery:2' });
  setup(); edit('PRESERVE FIRST DRAFT'); fireEvent.click(screen.getByRole('button', { name: 'Open broker' }));
  fireEvent.click(screen.getByRole('button', { name: 'Open other broker job' }));
  await waitFor(() => expect(screen.getByLabelText('Audit draft').textContent).toContain('SECOND BROKER DRAFT'));
  expect(useStudio.getState().chapterId).toBe('recovery:2');
  expect(drafts.load('recovery:1')?.content).toBe('PRESERVE FIRST DRAFT');
  expect(editor().value).toBe('SECOND');
});
it('does not display a broker result if authority is revoked after chapter navigation', async () => {
  vi.mocked(api.job).mockResolvedValueOnce({ ...taskState('broker-two', 'COMPLETED', 'REVOKED PROSE', 10), chapter_id: 'recovery:2' }).mockRejectedValue(new ApiError({ status: 403, code: 'DENIED', message: 'Denied' }));
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Open broker' })); fireEvent.click(screen.getByRole('button', { name: 'Open other broker job' }));
  await waitFor(() => expect(useStudio.getState().chapterId).toBe('recovery:2'));
  await waitFor(() => expect(api.job).toHaveBeenCalledTimes(2));
  expect(screen.getByLabelText('Audit draft').textContent).not.toContain('REVOKED PROSE');
  expect(generationRecovery.load('file', 'recovery:2')).toBeUndefined();
});
it('ignores a delayed broker lookup after the author switches chapter', async () => {
  const pending = deferred<any>(); vi.mocked(api.job).mockReturnValue(pending.promise);
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Open broker' })); fireEvent.click(screen.getByRole('button', { name: 'Open current broker job' }));
  act(() => useStudio.getState().setChapter('recovery:2'));
  await act(async () => pending.resolve(taskState('broker-one', 'COMPLETED', 'LATE BROKER SECRET')));
  expect(screen.getByLabelText('Audit draft').textContent).not.toContain('LATE BROKER SECRET');
  expect(editor().value).toBe('SECOND');
});
