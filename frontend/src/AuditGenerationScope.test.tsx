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
vi.mock('./ui/AppShell', () => ({ AppShell: ({ main, status, inspector }: any) => <><main>{main}</main><aside>{inspector}</aside><footer>{status}</footer></> }));
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
vi.mock('./ui/FeatureLauncher', () => ({ FeatureLauncher: () => null }));
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
  query.setQueryData(['experimental-features', 'file'], { experimental: enabled, default_enabled: false, features: { 'experimental.writing_recovery_v2': enabled } });
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

it('AUDIT fences a late generation creation response after chapter navigation', async () => {
  const pending = deferred<any>();
  vi.spyOn(api, 'generate').mockReturnValue(pending.promise);
  vi.stubGlobal('EventSource', class { onmessage: any; onerror: any; close() {} });
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  await waitFor(() => expect(api.generate).toHaveBeenCalledOnce());
  act(() => useStudio.getState().setChapter('recovery:2'));
  await act(async () => pending.resolve({ job_id: 'old-first-chapter-job', events_url: '/events', base_chapter_version: 3 }));
  expect(editor().value).toBe('SECOND');
  expect(screen.getByLabelText('Audit draft').textContent).toBe('');
});

const draftView = () => screen.getByLabelText('Audit draft').textContent;
const variantsView = () => screen.getByLabelText('Audit variants').textContent;
function navigateSecond() { act(() => useStudio.getState().setChapter('recovery:2')); }
function streamHarness() {
  const streams: any[] = [];
  vi.stubGlobal('EventSource', class {
    onmessage: any; onerror: any; close = vi.fn();
    constructor(public url: string) { streams.push(this); }
  });
  return streams;
}
function recoverable(jobId = 'old-job', status = 'GENERATING') {
  return { chapterId: 'recovery:1', jobId, original: 'PRIVATE FIRST', baseChapterVersion: 3,
    job: { id: jobId, status, output: status === 'COMPLETED' ? 'READY FIRST' : '', original: 'PRIVATE FIRST', base_chapter_version: 3 } };
}
it('fences delayed creation across A-B-A and retains its originating task without starting an old stream', async () => {
  const pending = deferred<any>(), streams = streamHarness();
  vi.spyOn(api, 'generate').mockReturnValue(pending.promise);
  setup(true, true); fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  await waitFor(() => expect(api.generate).toHaveBeenCalledOnce());
  act(() => { useStudio.getState().setChapter('recovery:2'); useStudio.getState().setChapter('recovery:1'); });
  await act(async () => pending.resolve({ job_id: 'delayed-aba', events_url: '/events', base_chapter_version: 3 }));
  expect(draftView()).toBe(''); expect(streams).toHaveLength(0);
  expect(generationRecovery.load('file', 'recovery:1')?.jobId).toBe('delayed-aba');
  expect(generationRecovery.load('file', 'recovery:2')).toBeUndefined();
});
it('closes only the local stream on navigation and ignores queued events/errors without cancelling the server task', async () => {
  const streams = streamHarness();
  vi.spyOn(api, 'generate').mockResolvedValue({ job_id: 'stream-task', events_url: '/events', base_chapter_version: 3 });
  const cancel = vi.spyOn(api, 'cancel').mockResolvedValue({}), poll = vi.spyOn(api, 'job').mockResolvedValue({ status: 'COMPLETED', output: 'WRONG SCOPE' });
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  await waitFor(() => expect(streams).toHaveLength(1));
  act(() => streams[0].onmessage({ data: JSON.stringify({ status: 'GENERATING', chunk: 'FIRST PRIVATE CHUNK' }) }));
  expect(draftView()).toContain('FIRST PRIVATE CHUNK');
  navigateSecond();
  act(() => streams[0].onmessage({ data: JSON.stringify({ status: 'COMPLETED', chunk: 'LATE PRIVATE' }) }));
  await act(async () => streams[0].onerror());
  expect(draftView()).toBe(''); expect(streams[0].close).toHaveBeenCalled();
  expect(cancel).not.toHaveBeenCalled(); expect(poll).not.toHaveBeenCalled();
  expect(generationRecovery.load('file', 'recovery:1')?.job?.output).toBe('FIRST PRIVATE CHUNK');
});
it('fences in-flight stream recovery polling after navigation', async () => {
  const streams = streamHarness(), pending = deferred<any>();
  vi.spyOn(api, 'generate').mockResolvedValue({ job_id: 'recover-task', events_url: '/events', base_chapter_version: 3 });
  const poll = vi.spyOn(api, 'job').mockReturnValue(pending.promise);
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  await waitFor(() => expect(streams).toHaveLength(1));
  act(() => { void streams[0].onerror(); });
  await waitFor(() => expect(poll).toHaveBeenCalledOnce());
  navigateSecond(); await act(async () => pending.resolve({ status: 'COMPLETED', output: 'OLD RECOVERED' }));
  expect(draftView()).toBe(''); expect(poll).toHaveBeenCalledTimes(1);
});
it('fences initial recovery polling under StrictMode and retains metadata on genuine unmount', async () => {
  const pending = deferred<any>(); generationRecovery.save('file', recoverable());
  const poll = vi.spyOn(api, 'job').mockReturnValue(pending.promise);
  const { view } = setup(true, true);
  await waitFor(() => expect(poll).toHaveBeenCalled());
  navigateSecond(); await act(async () => pending.resolve({ status: 'COMPLETED', output: 'PRIVATE RECOVERY' }));
  expect(draftView()).toBe('');
  view.unmount(); expect(generationRecovery.load('file', 'recovery:1')?.jobId).toBe('old-job');
});
it('retains completed candidate output for reopening instead of deleting it at stream completion', async () => {
  const streams = streamHarness();
  vi.spyOn(api, 'generate').mockResolvedValue({ job_id: 'completed-task', events_url: '/events', base_chapter_version: 3 });
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  await waitFor(() => expect(streams).toHaveLength(1));
  act(() => streams[0].onmessage({ data: JSON.stringify({ status: 'COMPLETED', output: 'FINISHED CANDIDATE' }) }));
  expect(generationRecovery.load('file', 'recovery:1')?.job?.output).toBe('FINISHED CANDIDATE');
  navigateSecond(); act(() => useStudio.getState().setChapter('recovery:1'));
  await waitFor(() => expect(draftView()).toContain('FINISHED CANDIDATE'));
});
it('fences delayed variant creation and poll callbacks across chapters', async () => {
  const creation = deferred<any>(), pollResult = deferred<any>();
  const generate = vi.spyOn(api, 'generateVariants').mockReturnValue(creation.promise);
  const poll = vi.spyOn(api, 'job').mockReturnValue(pollResult.promise);
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Audit variants' }));
  await waitFor(() => expect(generate).toHaveBeenCalled());
  await act(async () => creation.resolve({ variants: [{ job_id: 'variant-one', variant_index: 1, base_chapter_version: 3 }] }));
  await waitFor(() => expect(poll).toHaveBeenCalled());
  navigateSecond(); await act(async () => pollResult.resolve({ status: 'COMPLETED', output: 'OLD VARIANT' }));
  expect(variantsView()).toBe('[]'); expect(draftView()).toBe('');
  expect(generationRecovery.load('file', 'recovery:1')?.variants?.[0].id).toBe('variant-one');
});
it.each(['single', 'variant'])('fences delayed %s retry creation while preserving new task metadata in the old chapter', async kind => {
  if (kind === 'single') generationRecovery.save('file', recoverable('failed-task', 'FAILED'));
  else generationRecovery.save('file', { chapterId: 'recovery:1', variants: [{ id: 'failed-variant', status: 'failed', output: 'OLD', original: 'PRIVATE FIRST', variantIndex: 1, baseChapterVersion: 3 }] });
  const pending = deferred<any>(); vi.spyOn(api, 'retryGeneration').mockReturnValue(pending.promise);
  const poll = vi.spyOn(api, 'job').mockResolvedValueOnce(taskState(kind === 'single' ? 'failed-task' : 'failed-variant', 'FAILED')).mockResolvedValue({ status: 'COMPLETED', output: 'RETRIED PRIVATE' });
  setup(); await waitFor(() => expect(kind === 'single' ? draftView() : variantsView()).toContain(kind === 'single' ? 'failed-task' : 'failed-variant'));
  fireEvent.click(screen.getByRole('button', { name: 'Audit retry' }));
  await waitFor(() => expect(api.retryGeneration).toHaveBeenCalled()); navigateSecond();
  await act(async () => pending.resolve({ job_id: 'new-retry', events_url: '/events', base_chapter_version: 3, retry_of: 'failed-task' }));
  expect(draftView()).toBe(''); expect(variantsView()).toBe('[]'); expect(poll).toHaveBeenCalledTimes(1);
  const saved = generationRecovery.load('file', 'recovery:1');
  expect(saved?.jobId || saved?.variants?.[0].id).toBe('new-retry');
});
it.each(['accept', 'reject', 'cancel'] as const)('fences a late %s action and preserves the new chapter view', async action => {
  generationRecovery.save('file', recoverable('action-task', action === 'cancel' ? 'GENERATING' : 'COMPLETED'));
  const pending = deferred<any>();
  vi.spyOn(api, action).mockReturnValue(pending.promise);
  vi.spyOn(api, 'job').mockResolvedValueOnce(taskState('action-task', action === 'cancel' ? 'GENERATING' : 'COMPLETED')).mockReturnValue(new Promise(() => {}));
  const get = vi.spyOn(api, 'chapter').mockResolvedValue(chapter('UNEXPECTED OLD'));
  setup(); await waitFor(() => expect(draftView()).toContain('action-task'));
  fireEvent.click(screen.getByRole('button', { name: `Audit ${action}` }));
  await waitFor(() => expect(api[action]).toHaveBeenCalled()); navigateSecond();
  await act(async () => pending.resolve({ chapter: chapter('OLD ACCEPTED', 4) }));
  expect(editor().value).toBe('SECOND'); expect(draftView()).toBe(''); expect(get).not.toHaveBeenCalled();
});
it('keeps all generation transport requests bound to the supplied session/branch after global context changes', async () => {
  vi.mocked(api.job).mockRestore();
  const captured = { sessionToken: 'origin-session', scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'origin-branch' } };
  setCollaborationContext({ sessionToken: 'different-session', scope: { ...captured.scope, branchId: 'different-branch' } });
  const fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) }); vi.stubGlobal('fetch', fetch);
  await api.generate('continue', {}, captured); await api.generateVariants('continue', {}, captured);
  await api.job('id', captured); await api.retryGeneration('id', captured); await api.cancel('id', captured);
  await api.accept('id', 'text', 3, captured); await api.reject('id', captured);
  expect(fetch).toHaveBeenCalledTimes(7);
  fetch.mock.calls.forEach(([, init]) => { expect(init.headers['X-Session-Token']).toBe('origin-session'); expect(init.headers['X-Branch-Id']).toBe('origin-branch'); });
});
it('fences a variant group that is created only after navigation', async () => {
  const pending = deferred<any>(); vi.spyOn(api, 'generateVariants').mockReturnValue(pending.promise);
  const poll = vi.spyOn(api, 'job').mockResolvedValue({ status: 'COMPLETED', output: 'OLD VARIANT' });
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Audit variants' }));
  await waitFor(() => expect(api.generateVariants).toHaveBeenCalled()); navigateSecond();
  await act(async () => pending.resolve({ variants: [{ job_id: 'late-variant', variant_index: 1, base_chapter_version: 3 }] }));
  expect(variantsView()).toBe('[]'); expect(poll).not.toHaveBeenCalled();
  expect(generationRecovery.load('file', 'recovery:1')?.variants?.[0].id).toBe('late-variant');
});
it('coalesces synchronous repeated generation clicks before React commits loading state', async () => {
  const pending = deferred<any>(); const generate = vi.spyOn(api, 'generate').mockReturnValue(pending.promise);
  const streams = streamHarness(); setup();
  const button = screen.getByRole('button', { name: 'Audit generate' });
  act(() => { button.click(); button.click(); });
  await waitFor(() => expect(generate).toHaveBeenCalledTimes(1));
  await act(async () => pending.resolve({ job_id: 'single-create', events_url: '/events', base_chapter_version: 3 }));
  expect(streams).toHaveLength(1);
});
it('does not let an obsolete creation replace newer origin recovery metadata', async () => {
  const first = deferred<any>(), second = deferred<any>(); streamHarness();
  vi.spyOn(api, 'generate').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  navigateSecond(); act(() => useStudio.getState().setChapter('recovery:1'));
  fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  await act(async () => second.resolve({ job_id: 'newer-task', events_url: '/events', base_chapter_version: 3 }));
  await act(async () => first.resolve({ job_id: 'obsolete-create', events_url: '/events', base_chapter_version: 3 }));
  expect(draftView()).toContain('newer-task'); expect(draftView()).not.toContain('obsolete-create');
  expect(generationRecovery.load('file', 'recovery:1')?.jobId).toBe('newer-task');
  expect(generationRecovery.history('file', 'recovery:1').some(value => value.jobId === 'obsolete-create')).toBe(true);
});
it('reopens a displaced task only after fresh source checks and preserves the newer candidate for later recovery', async () => {
  const first = deferred<any>(), second = deferred<any>(); streamHarness();
  const generate = vi.spyOn(api, 'generate').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  const poll = vi.spyOn(api, 'job').mockResolvedValue({ id: 'displaced-task', novel_id: 'recovery', chapter_id: 'recovery:1', status: 'COMPLETED', output: 'RECOVERED DISPLACED', base_chapter_version: 2 });
  const cancel = vi.spyOn(api, 'cancel').mockResolvedValue({});
  setup(); fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  navigateSecond(); act(() => useStudio.getState().setChapter('recovery:1'));
  fireEvent.click(screen.getByRole('button', { name: 'Audit generate' }));
  await act(async () => second.resolve({ job_id: 'newer-active', events_url: '/events', base_chapter_version: 3 }));
  await act(async () => first.resolve({ job_id: 'displaced-task', events_url: '/events', base_chapter_version: 2 }));
  expect(draftView()).toContain('newer-active');
  fireEvent.click(await screen.findByRole('button', { name: '重新打开保留任务' }));
  await waitFor(() => expect(draftView()).toContain('RECOVERED DISPLACED'));
  expect(draftView()).toContain('"acceptBlocked":true');
  expect(poll).toHaveBeenCalledWith('displaced-task', { sessionToken: '', actor: undefined, scope: undefined });
  expect(generationRecovery.history('file', 'recovery:1').some(value => value.jobId === 'newer-active')).toBe(true);
  expect(generate).toHaveBeenCalledTimes(2); expect(cancel).not.toHaveBeenCalled();
});
it.each(['denied', 'other-project', 'navigation'])('never exposes retained output after a %s recovery check', async outcome => {
  generationRecovery.save('file', recoverable('retained', 'COMPLETED'));
  generationRecovery.save('file', recoverable('active', 'COMPLETED'));
  const pending = deferred<any>(); vi.spyOn(api, 'job').mockResolvedValueOnce(taskState('active')).mockReturnValue(pending.promise);
  setup(); await waitFor(() => expect(draftView()).toContain('active'));
  fireEvent.click(screen.getByRole('button', { name: '重新打开保留任务' }));
  await waitFor(() => expect(api.job).toHaveBeenCalled());
  if (outcome === 'navigation') navigateSecond();
  await act(async () => {
    if (outcome === 'denied') pending.reject(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Denied' }));
    else pending.resolve({ id: 'retained', novel_id: outcome === 'other-project' ? 'secret-project' : 'recovery', chapter_id: 'recovery:1', status: 'COMPLETED', output: 'MUST NEVER EXPOSE', base_chapter_version: 3 });
  });
  expect(screen.queryByText(/MUST NEVER EXPOSE/)).toBeNull();
  expect(draftView()).not.toContain('MUST NEVER EXPOSE');
  if (outcome !== 'navigation') expect(draftView()).toContain('active');
});

it('AUDIT revalidates a completed current recovery task before presenting it as ready', async () => {
  generationRecovery.save('file', recoverable('revoked-current', 'COMPLETED'));
  const poll = vi.spyOn(api, 'job').mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Revoked' }));
  setup();
  await waitFor(() => expect(poll).toHaveBeenCalled());
  expect(draftView()).not.toContain('READY FIRST');
});
it.each(['single', 'variants'])('withholds cached %s output and original while authorization is pending or denied', async kind => {
  if (kind === 'single') generationRecovery.save('file', recoverable('withheld', 'COMPLETED'));
  else generationRecovery.save('file', { chapterId: 'recovery:1', variants: [{ id: 'withheld', variantIndex: 1, status: 'ready', output: 'READY FIRST', original: 'PRIVATE FIRST', baseChapterVersion: 3 }] });
  const pending = deferred<any>(); vi.spyOn(api, 'job').mockReturnValue(pending.promise);
  setup(true, true); await waitFor(() => expect(api.job).toHaveBeenCalled());
  expect(draftView()).toBe(''); expect(variantsView()).toBe('[]');
  expect(document.body.textContent).not.toContain('PRIVATE FIRST'); expect(document.body.textContent).not.toContain('READY FIRST');
  await act(async () => pending.reject(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'revoked' })));
  expect(draftView()).toBe(''); expect(variantsView()).toBe('[]');
  expect(generationRecovery.load('file', 'recovery:1')).toBeTruthy();
  expect(screen.getByRole('button', { name: '重新打开保留任务' })).toBeTruthy();
});
it.each(['single', 'variants'])('rejects source drift for current %s recovery without rendering its payload', async kind => {
  if (kind === 'single') generationRecovery.save('file', recoverable('drifted', 'COMPLETED'));
  else generationRecovery.save('file', { chapterId: 'recovery:1', variants: [{ id: 'drifted', variantIndex: 1, status: 'ready', output: 'OLD PRIVATE', original: 'PRIVATE FIRST', baseChapterVersion: 3 }] });
  vi.spyOn(api, 'job').mockResolvedValue({ ...taskState('drifted', 'COMPLETED', 'UNAUTHORIZED NEW'), chapter_id: 'some-other-chapter' });
  setup(); await waitFor(() => expect(api.job).toHaveBeenCalled());
  expect(draftView()).toBe(''); expect(variantsView()).toBe('[]');
  expect(document.body.textContent).not.toMatch(/OLD PRIVATE|PRIVATE FIRST|UNAUTHORIZED NEW/);
});
it('recovers offline current metadata through explicit recheck after permission returns, without new generation', async () => {
  generationRecovery.save('file', recoverable('offline-current', 'COMPLETED'));
  const poll = vi.spyOn(api, 'job').mockRejectedValueOnce(new TypeError('offline'));
  const generate = vi.spyOn(api, 'generate'), cancel = vi.spyOn(api, 'cancel');
  setup(); await screen.findByText(/生成草稿尚未通过权限与来源核对/);
  expect(draftView()).toBe('');
  poll.mockResolvedValue(taskState('offline-current', 'COMPLETED', 'VERIFIED CURRENT', 2));
  fireEvent.click(screen.getByRole('button', { name: '重新打开保留任务' }));
  await waitFor(() => expect(draftView()).toContain('VERIFIED CURRENT'));
  expect(draftView()).toContain('"acceptBlocked":true');
  expect(generate).not.toHaveBeenCalled(); expect(cancel).not.toHaveBeenCalled();
});
it.each(['single', 'variants'])('StrictMode revalidates completed %s once per observer before presenting fresh output', async kind => {
  if (kind === 'single') generationRecovery.save('file', recoverable('strict-current', 'COMPLETED'));
  else generationRecovery.save('file', { chapterId: 'recovery:1', variants: [{ id: 'strict-current', variantIndex: 1, status: 'ready', output: 'CACHED OLD', baseChapterVersion: 3 }] });
  const old = deferred<any>(), current = deferred<any>();
  const poll = vi.spyOn(api, 'job').mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  setup(true, true); await waitFor(() => expect(poll).toHaveBeenCalledTimes(2));
  await act(async () => old.resolve(taskState('strict-current', 'COMPLETED', 'STALE OBSERVER')));
  expect(draftView()).toBe(''); expect(variantsView()).toBe('[]');
  await act(async () => current.resolve(taskState('strict-current', 'COMPLETED', 'FRESH AUTHORIZED', 2)));
  await waitFor(() => expect(kind === 'single' ? draftView() : variantsView()).toContain('FRESH AUTHORIZED'));
  expect(kind === 'single' ? draftView() : variantsView()).toContain('"acceptBlocked":true');
  expect(document.body.textContent).not.toContain('STALE OBSERVER');
});
