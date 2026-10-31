// @vitest-environment jsdom
import { useMemo } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { api, type Chapter } from './api';
import { useStudio } from './store';
import { experimentalClient } from './experimental/api';
import { ProductionLineagePanel } from './experimental/ProductionLineagePanel';
import { MediaPanel } from './experimental/MediaPanel';
// Real App navigation and panel unmount with the real production and media panels. Only unrelated
// chrome/rich text and the lazy workbench selection are replaced.
vi.mock('./Editor', async original => ({ ...(await original<typeof import('./Editor')>()), ChapterEditor: ({ content }: any) => <textarea aria-label="Test chapter editor" readOnly value={content} /> }));
// [HERMIA-FE-20261031] App renders the AI panel inside the NovelAssist drawer; expose the mocked ai in tests.
vi.mock('./rebuild/novel/NovelAssist', () => ({ NovelAssist: ({ ai, extras }: any) => <aside>{ai}{extras}</aside> }));
vi.mock('./ui/AppShell', () => ({ AppShell: ({ main, status, sidebar, inspector }: any) => <>{sidebar}<main>{main}</main><aside>{inspector}</aside><footer>{status}</footer></> }));
vi.mock('./novel/AiWritingPanel', () => ({ AiWritingPanel: () => null }));
vi.mock('./novel/SourcePrivacyControl', () => ({ SourcePrivacyControl: () => null }));
vi.mock('./novel/ChapterTree', () => ({ ChapterTree: () => null }));
vi.mock('./ui/FeatureLauncher', async importOriginal => ({ ...(await importOriginal<typeof import('./ui/FeatureLauncher')>()),  FeatureLauncher: ({ onSelect }: any) => <button onClick={() => onSelect('experimental')}>Open production receipt</button> }));
vi.mock('./experimental/DeferredExperimentalWorkbench', () => ({ DeferredExperimentalWorkbench: ({ onNavigate, chapter, requestedTab, requestedTask }: any) => {
  const client = useMemo(() => experimentalClient('story', { sessionToken: '' }), []);
  return requestedTab === 'cover_storyboard_generation' ? <MediaPanel client={client} chapter={chapter} requestedTaskId={requestedTask?.authority === 'media' ? requestedTask.id : undefined} /> : <ProductionLineagePanel client={client} manifestsEnabled onNavigate={onNavigate} />;
} }));
function chapter(id = 'story:1', content = 'SAVED'): Chapter { return { id, novel_id: 'story', number: 1, title: 'Synthetic', content, document: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: content }] }] }, version: 3, word_count: content.length, status: 'DRAFT' }; }
const asset = { id: 'asset', label: 'Original input', kind: 'image', version: 1, digest: 'digest', deleted: false, integrity: 'VERIFIED', origin: 'ORIGINAL_INPUT', license: { label: 'Author declaration', source: '', note: '' }, operation: '', parents: [], sources: [], stale: false };
const manifest = { id: 'manifest', version: 1, status: 'RECORDED', created_at: '2026-10-16', task_id: 'original-task', task_version: 3, operation: 'cover_generation', input_digest: 'input', manifest_digest: 'manifest', adapter_id: 'mock-image-v1', model_id: null, parameters: { candidate_count: 1 }, seed: { value: null }, environment: null, input_versions: [{ kind: 'CHAPTER', id: 'story:2', version: 2, digest: 'a'.repeat(64) }], outputs: [] };
const task = { id: 'original-task', version: 4, status: 'SUCCEEDED', operation: 'cover_generation', brief_id: 'brief', production_replay_id: 'replay', source_digest: 'input' };
const clients: QueryClient[] = [];
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); useStudio.getState().setCollaboration(''); useStudio.setState({ novelId: 'story', chapterId: 'story:1', textModel: null });
  vi.spyOn(api, 'novels').mockResolvedValue([{ id: 'story', title: 'Synthetic' }] as any);
  vi.spyOn(api, 'chapters').mockResolvedValue([chapter(), chapter('story:2', 'TARGET')]);
  vi.spyOn(api, 'chapter').mockResolvedValue(chapter('story:2', 'TARGET'));
  vi.spyOn(api, 'legacyHistory').mockResolvedValue([]);
  vi.spyOn(api, 'novel').mockResolvedValue({ id: 'story', title: 'Synthetic' } as any);
  vi.spyOn(api, 'outline').mockResolvedValue({}); vi.spyOn(api, 'resource').mockResolvedValue([]); vi.spyOn(api, 'storyRoutes').mockResolvedValue([]);
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/production/assets') ? { items: [asset] } : url.endsWith('/production/assets/asset') ? asset : url.endsWith('/production/manifests') ? { items: [manifest] } : url.endsWith('/media/tasks') ? { items: [task] } : url.endsWith('/media/catalog') ? { screenplays: [], characters: [] } : { items: [] }))));
});
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });
it.each(['task', 'chapter'])('real App retains source declaration on cancelled leave and opens the explicit original %s', async destination => {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } }); clients.push(query);
  query.setQueryData(['novels'], [{ id: 'story', title: 'Synthetic' }]);
  query.setQueryData(['chapter', 'file', 'story:1'], chapter()); query.setQueryData(['chapter', 'file', 'story:2'], chapter('story:2', 'TARGET'));
  query.setQueryData(['chapters', 'file', 'story'], [chapter(), chapter('story:2', 'TARGET')]);
  query.setQueryData(['archived-chapters', 'file', 'story'], []); query.setQueryData(['text-models'], []);
  query.setQueryData(['media-tasks', 'story'], { audiobook: [], motion: [] });
  query.setQueryData(['writing-goal', 'story'], { current_words: 0, target_words: 0, current_chapters: 2, target_chapters: 0, words_progress: 0 });
  query.setQueryData(['experimental-features', 'file'], { experimental: true, default_enabled: false, features: { 'experimental.asset_lineage_v2': true, 'experimental.production_manifest_v2': true, 'experimental.cover_storyboard_generation': true, 'experimental.workspace_tools_v2': true } });
  render(<QueryClientProvider client={query}><App /></QueryClientProvider>);
  await screen.findByLabelText('Test chapter editor'); fireEvent.click(screen.getByRole('button', { name: 'Open production receipt' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Original input · v1' }));
  fireEvent.change(await screen.findByLabelText('许可使用备注'), { target: { value: 'UNSAVED DECLARATION' } });
  fireEvent.click(screen.getByRole('button', { name: /清单 cover_generation/ }));
  const label = destination === 'task' ? '打开确切原媒体任务' : '查看当前来源章节 story:2';
  fireEvent.click(screen.getByRole('button', { name: label }));
  expect(useStudio.getState().chapterId).toBe('story:1');
  fireEvent.click(screen.getByRole('button', { name: '留在此处' }));
  expect((screen.getByLabelText('许可使用备注') as HTMLTextAreaElement).value).toBe('UNSAVED DECLARATION');
  fireEvent.click(screen.getByRole('button', { name: label }));
  expect(screen.getByText(/章节入口显示当前正文/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: `确认离开并${label}` }));
  if (destination === 'task') {
    expect(await screen.findByText('已定位任务中心请求的原媒体任务。')).toBeTruthy();
    const record = screen.getByRole('article', { name: '媒体任务' });
    expect(record.getAttribute('aria-current')).toBe('true');
    expect(record.textContent).toContain('original-task');
  } else {
    await waitFor(() => expect(useStudio.getState().chapterId).toBe('story:2'));
    expect((screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement).value).toBe('TARGET');
  }
  expect(screen.queryByLabelText('许可使用备注')).toBeNull();
  expect(vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
});
