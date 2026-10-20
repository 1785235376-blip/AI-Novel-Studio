// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { api, ApiError, type Chapter } from './api';
import { drafts, conflicts } from './drafts';
import { useStudio } from './store';

// Real App hydration, draft authority and Story callback wiring. Only unrelated
// chrome, the rich-text widget and the isolated version editor are replaced.
vi.mock('./Editor', async original => ({ ...(await original<typeof import('./Editor')>()), ChapterEditor: ({ content, onChange, onCompositionChange }: any) =>
  <textarea aria-label="Test chapter editor" value={content} onChange={e => onChange(e.target.value, doc(e.target.value))} onCompositionStart={() => onCompositionChange?.(true)} /> }));
vi.mock('./ui/AppShell', () => ({ AppShell: ({ main, status, sidebar }: any) => <>{sidebar}<main>{main}</main><footer>{status}</footer></> }));
vi.mock('./novel/AiWritingPanel', () => ({ AiWritingPanel: () => null }));
vi.mock('./novel/SourcePrivacyControl', () => ({ SourcePrivacyControl: () => null }));
vi.mock('./novel/ChapterTree', () => ({ ChapterTree: () => null }));
vi.mock('./ui/FeatureLauncher', () => ({ FeatureLauncher: ({ onSelect }: any) => <><button onClick={() => onSelect('story')}>Open Story</button><button onClick={() => onSelect('history')}>Leave Story</button></> }));
vi.mock('./novel/StoryDatabase', async original => ({ ...(await original<typeof import('./novel/StoryDatabase')>()), TimelineEditor: ({ onOpenChapter }: any) => <>
  <button onClick={() => onOpenChapter('story:~source', navigation.signal)}>Open exact Story source</button>
  <button onClick={() => navigation.abort()}>Cancel source navigation</button>
</> }));
function doc(text: string) { return { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] }; }
function chapter(id = 'story:1', content = 'SAVED'): Chapter { return { id, novel_id: 'story', number: id === 'story:1' ? 1 : 2, title: 'Synthetic', content, document: doc(content), version: 3, word_count: content.length, status: 'DRAFT' }; }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; }
let navigation: AbortController; const clients: QueryClient[] = [];
beforeEach(() => {
  navigation = new AbortController(); localStorage.clear(); sessionStorage.clear();
  useStudio.getState().setCollaboration(''); useStudio.setState({ novelId: 'story', chapterId: 'story:1', textModel: null });
  vi.spyOn(api, 'chapters').mockResolvedValue([chapter(), chapter('story:~source', 'SOURCE')]);
  vi.spyOn(api, 'chapter').mockResolvedValue(chapter('story:~source', 'SOURCE'));
  vi.spyOn(api, 'legacyHistory').mockResolvedValue([]);
  vi.spyOn(api, 'novel').mockResolvedValue({ id: 'story', title: 'Synthetic' } as any);
  vi.spyOn(api, 'outline').mockResolvedValue({}); vi.spyOn(api, 'resource').mockResolvedValue([]); vi.spyOn(api, 'storyRoutes').mockResolvedValue([]);
});
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.restoreAllMocks(); localStorage.clear(); sessionStorage.clear(); });
async function setup() {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } }); clients.push(query);
  query.setQueryData(['novels'], [{ id: 'story', title: 'Synthetic' }]);
  query.setQueryData(['chapter', 'file', 'story:1'], chapter());
  query.setQueryData(['chapter', 'file', 'story:~source'], chapter('story:~source', 'SOURCE'));
  query.setQueryData(['chapters', 'file', 'story'], [chapter(), chapter('story:~source', 'SOURCE')]);
  query.setQueryData(['archived-chapters', 'file', 'story'], []); query.setQueryData(['text-models'], []);
  query.setQueryData(['media-tasks', 'story'], { audiobook: [], motion: [] });
  query.setQueryData(['writing-goal', 'story'], { current_words: 0, target_words: 0, current_chapters: 2, target_chapters: 0, words_progress: 0 });
  query.setQueryData(['experimental-features', 'file'], { experimental: true, default_enabled: false, features: { 'experimental.story_record_versions_v1': true } });
  render(<QueryClientProvider client={query}><App /></QueryClientProvider>);
  await waitFor(() => expect((screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement).value).toBe('SAVED'));
  fireEvent.click(screen.getByRole('button', { name: 'Open Story' }));
  fireEvent.click(await screen.findByRole('tab', { name: '时间线' }));
  await screen.findByRole('button', { name: 'Open exact Story source' });
  return query;
}
const open = () => fireEvent.click(screen.getByRole('button', { name: 'Open exact Story source' }));
const edit = () => fireEvent.change(screen.getByLabelText('Test chapter editor'), { target: { value: 'NEW UNSAVED TEXT' } });
it('reads the exact chapter through original authority before normal App hydration', async () => {
  await setup(); open();
  await waitFor(() => expect(useStudio.getState().chapterId).toBe('story:~source'));
  expect(api.chapter).toHaveBeenCalledWith('story:~source', expect.objectContaining({ sessionToken: '' }));
  expect((screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement).value).toBe('SOURCE');
});
it.each(['dirty', 'composing', 'target draft'])('blocks source navigation for %s using existing manuscript state', async reason => {
  await setup();
  if (reason === 'dirty') edit();
  if (reason === 'composing') fireEvent.compositionStart(screen.getByLabelText('Test chapter editor'));
  if (reason === 'target draft') drafts.save({ chapterId: 'story:~source', content: 'TARGET DRAFT', baseVersion: 3, updatedAt: new Date().toISOString() }, 'file');
  open(); expect(api.chapter).not.toHaveBeenCalled(); expect(useStudio.getState().chapterId).toBe('story:1');
  if (reason === 'dirty') expect(drafts.load('story:1', 'file')?.content).toBe('NEW UNSAVED TEXT');
});
it.each(['cancel', 'leave', 'new input', 'chapter ABA'])('ignores the late source read after %s', async reason => {
  const pending = deferred<Chapter>(); vi.mocked(api.chapter).mockReturnValue(pending.promise);
  await setup(); open(); expect(api.chapter).toHaveBeenCalledOnce();
  if (reason === 'cancel') fireEvent.click(screen.getByRole('button', { name: 'Cancel source navigation' }));
  if (reason === 'leave') fireEvent.click(screen.getByRole('button', { name: 'Leave Story' }));
  if (reason === 'new input') edit();
  if (reason === 'chapter ABA') { act(() => useStudio.getState().setChapter('story:~source')); act(() => useStudio.getState().setChapter('story:1')); }
  await act(async () => pending.resolve(chapter('story:~source', 'LATE SOURCE')));
  expect(useStudio.getState().chapterId).toBe('story:1');
  expect((screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement).value).not.toBe('LATE SOURCE');
});
it('keeps the current chapter when source permission is revoked or coordinates mismatch', async () => {
  await setup(); vi.mocked(api.chapter).mockRejectedValueOnce(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Denied' })); open();
  await waitFor(() => expect(api.chapter).toHaveBeenCalledOnce());
  expect(useStudio.getState().chapterId).toBe('story:1');
  vi.mocked(api.chapter).mockResolvedValue({ ...chapter('story:~source'), novel_id: 'other' }); open();
  await waitFor(() => expect(api.chapter).toHaveBeenCalledTimes(2)); expect(useStudio.getState().chapterId).toBe('story:1');
  expect(conflicts.load('story:1', 'file')).toBeUndefined();
});
