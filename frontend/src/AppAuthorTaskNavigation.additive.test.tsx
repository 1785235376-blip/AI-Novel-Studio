// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { api, type Chapter } from './api';
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
vi.mock('./ui/FeatureLauncher', async importOriginal => ({ ...(await importOriginal<typeof import('./ui/FeatureLauncher')>()),  FeatureLauncher: ({ onSelect }: any) => <button onClick={() => onSelect('experimental')}>Open broker</button> }));
vi.mock('./experimental/DeferredExperimentalWorkbench', () => ({ DeferredExperimentalWorkbench: ({ onNavigate, requestedTask, requestedTab }: any) => <>
  <output aria-label="Exact original target">{JSON.stringify({ requestedTask, requestedTab })}</output>
  <button onClick={() => onNavigate({ kind: 'feature', id: 'proposal-1', feature: 'advanced_planning_v2', task_authority: 'planning_proposal' })}>Open original proposal</button>
  <button onClick={() => onNavigate({ kind: 'feature', id: 'run-1', feature: 'story_simulator_v2', task_authority: 'simulator_run' })}>Open original simulator</button>
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
const clients: QueryClient[] = [];
let navigationController: AbortController | undefined;
function setup(enabled = true, strict = false, linked = false) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } }); clients.push(query);
  query.setQueryData(['novels'], [{ id: 'recovery', title: 'Synthetic' }]);
  query.setQueryData(['chapter', 'file', 'recovery:1'], chapter());
  query.setQueryData(['chapter', 'file', 'recovery:2'], chapter('SECOND', 10, 'recovery:2'));
  query.setQueryData(['chapters', 'file', 'recovery'], [chapter(), chapter('SECOND', 10, 'recovery:2')]);
  query.setQueryData(['archived-chapters', 'file', 'recovery'], []);
  query.setQueryData(['text-models'], []);
  query.setQueryData(['media-tasks', 'recovery'], { audiobook: [], motion: [] });
  query.setQueryData(['writing-goal', 'recovery'], { current_words: 0, target_words: 10, current_chapters: 2, target_chapters: 3, words_progress: 0 });
  query.setQueryData(['experimental-features', 'file'], { experimental: enabled, default_enabled: false, features: { 'experimental.writing_recovery_v2': false, 'experimental.model_broker_v2': false, 'experimental.workspace_tools_v2': enabled, 'experimental.advanced_planning_v2': linked, 'experimental.story_simulator_v2': linked } });
  const app = <QueryClientProvider client={query}><App /></QueryClientProvider>;
  const view = render(strict ? <StrictMode>{app}</StrictMode> : app);
  return { query, view };
}
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

it('preserves exact simulator/planning navigation when workspace tools are off', async () => {
  setup(false, false, true); await openTasks();
  fireEvent.click(screen.getByRole('button', { name: 'Open original proposal' }));
  await waitFor(() => expect(JSON.parse(screen.getByLabelText('Exact original target').textContent || '{}')).toMatchObject({ requestedTab: 'advanced_planning_v2', requestedTask: { id: 'proposal-1', authority: 'planning_proposal' } }));
  fireEvent.click(screen.getByRole('button', { name: 'Open original simulator' }));
  await waitFor(() => expect(JSON.parse(screen.getByLabelText('Exact original target').textContent || '{}')).toMatchObject({ requestedTab: 'story_simulator_v2', requestedTask: { id: 'run-1', authority: 'simulator_run' } }));
  expect(api.generate).not.toHaveBeenCalled(); expect(api.accept).not.toHaveBeenCalled();
});
