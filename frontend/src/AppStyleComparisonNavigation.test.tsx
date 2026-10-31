// @vitest-environment jsdom
import { useMemo } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { api, type Chapter } from './api';
import { useStudio } from './store';
import { experimentalClient } from './experimental/api';
import { StyleAnalysisPanel } from './experimental/StyleAnalysisPanel';
// Real App navigation and panel unmount with the real Style panel. Only unrelated
// chrome/rich text and the lazy workbench selection are replaced.
vi.mock('./Editor', async original => ({ ...(await original<typeof import('./Editor')>()), ChapterEditor: ({ content }: any) => <textarea aria-label="Test chapter editor" readOnly value={content} /> }));
// [HERMIA-FE-20261031] App renders the AI panel inside the NovelAssist drawer; expose the mocked ai in tests.
vi.mock('./rebuild/novel/NovelAssist', () => ({ NovelAssist: ({ ai, extras }: any) => <aside>{ai}{extras}</aside> }));
vi.mock('./ui/AppShell', () => ({ AppShell: ({ main, status, sidebar, inspector }: any) => <>{sidebar}<main>{main}</main><aside>{inspector}</aside><footer>{status}</footer></> }));
vi.mock('./novel/AiWritingPanel', () => ({ AiWritingPanel: () => null }));
vi.mock('./novel/SourcePrivacyControl', () => ({ SourcePrivacyControl: () => null }));
vi.mock('./novel/ChapterTree', () => ({ ChapterTree: () => null }));
vi.mock('./ui/FeatureLauncher', async importOriginal => ({ ...(await importOriginal<typeof import('./ui/FeatureLauncher')>()),  FeatureLauncher: ({ onSelect }: any) => <button onClick={() => onSelect('experimental')}>Open style comparison</button> }));
vi.mock('./experimental/DeferredExperimentalWorkbench', () => ({ DeferredExperimentalWorkbench: ({ onNavigate, chapter }: any) => {
  const client = useMemo(() => experimentalClient('story', { sessionToken: '' }), []);
  return <StyleAnalysisPanel client={client} chapter={chapter} onNavigate={onNavigate} />;
} }));
function chapter(id = 'story:1', content = 'SAVED'): Chapter { return { id, novel_id: 'story', number: 1, title: 'Synthetic', content, document: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: content }] }] }, version: 3, word_count: content.length, status: 'DRAFT' }; }
const profile = { id: 'profile', version: 1, title: '风格', instructions: '短句', rules: [], chapter_ids: ['story:1'], character_ids: [], status: 'DRAFT' };
const metrics = { sentence_length_mean: { numerator: 3, denominator: 1 } };
const report = { id: 'report', version: 1, style_id: 'profile', style_version: 1, language: 'zh', stale: false, metrics, samples: [], limitations: [], comparison: { chapter_id: 'story:2', expected_version: 3, language: 'zh', comparable: true, metrics, paragraphs: [], paragraphs_truncated: false, interpretation: 'RAW_COUNT_DIFFERENCES_NOT_QUALITY_OR_NORMALIZED_DRIFT' }, model_assessments: [{ id: 'opinion', category: 'RHYTHM', interpretation: '人工待核对', boundary: '未校准', evidence: [], origin: 'MODEL_DERIVED', decision: 'PENDING', model: { provider_id: 'synthetic', model_id: 'fixture' }, quality_verification: 'SYNTHETIC_PROTOCOL_ONLY', review_history: [] }] };
const clients: QueryClient[] = [];
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); useStudio.getState().setCollaboration(''); useStudio.setState({ novelId: 'story', chapterId: 'story:1', textModel: null });
  vi.spyOn(api, 'novels').mockResolvedValue([{ id: 'story', title: 'Synthetic' }] as any);
  vi.spyOn(api, 'chapters').mockResolvedValue([chapter(), chapter('story:2', 'TARGET')]);
  vi.spyOn(api, 'chapter').mockResolvedValue(chapter('story:2', 'TARGET'));
  vi.spyOn(api, 'legacyHistory').mockResolvedValue([]);
  vi.spyOn(api, 'novel').mockResolvedValue({ id: 'story', title: 'Synthetic' } as any);
  vi.spyOn(api, 'outline').mockResolvedValue({}); vi.spyOn(api, 'resource').mockResolvedValue([]); vi.spyOn(api, 'storyRoutes').mockResolvedValue([]);
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/style-analysis/catalog') ? { styles: [profile], chapters: [chapter()], characters: [], operations: ['continue'] } : url.endsWith('/style-analysis/analyses') ? { items: [report] } : []))));
});
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });
it('real App keeps profile and feedback drafts on cancel, and only confirmed leave unmounts the style owner', async () => {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } }); clients.push(query);
  query.setQueryData(['novels'], [{ id: 'story', title: 'Synthetic' }]);
  query.setQueryData(['chapter', 'file', 'story:1'], chapter()); query.setQueryData(['chapter', 'file', 'story:2'], chapter('story:2', 'TARGET'));
  query.setQueryData(['chapters', 'file', 'story'], [chapter(), chapter('story:2', 'TARGET')]);
  query.setQueryData(['archived-chapters', 'file', 'story'], []); query.setQueryData(['text-models'], []);
  query.setQueryData(['media-tasks', 'story'], { audiobook: [], motion: [] });
  query.setQueryData(['writing-goal', 'story'], { current_words: 0, target_words: 0, current_chapters: 2, target_chapters: 0, words_progress: 0 });
  query.setQueryData(['experimental-features', 'file'], { experimental: true, default_enabled: false, features: { 'experimental.style_dna_v2': true, 'experimental.workspace_tools_v2': true } });
  render(<QueryClientProvider client={query}><App /></QueryClientProvider>);
  await screen.findByLabelText('Test chapter editor'); fireEvent.click(screen.getByRole('button', { name: 'Open style comparison' }));
  fireEvent.click(await screen.findByRole('button', { name: '编辑风格 风格' }));
  fireEvent.change(screen.getByLabelText('可复用风格指令（最多 120 字）'), { target: { value: 'UNSAVED PROFILE' } });
  fireEvent.change(screen.getByLabelText('文风意见审核理由 opinion'), { target: { value: 'UNSAVED FEEDBACK' } });
  fireEvent.click(screen.getByRole('button', { name: '打开比较目标原章节 v3' }));
  expect(useStudio.getState().chapterId).toBe('story:1');
  fireEvent.click(screen.getByRole('button', { name: '取消离开，保留文风输入' }));
  expect((screen.getByLabelText('可复用风格指令（最多 120 字）') as HTMLTextAreaElement).value).toBe('UNSAVED PROFILE');
  expect((screen.getByLabelText('文风意见审核理由 opinion') as HTMLTextAreaElement).value).toBe('UNSAVED FEEDBACK');
  fireEvent.click(screen.getByRole('button', { name: '打开比较目标原章节 v3' }));
  fireEvent.click(screen.getByRole('button', { name: '确认放弃未保存文风输入并打开章节' }));
  await waitFor(() => expect(useStudio.getState().chapterId).toBe('story:2'));
  expect(screen.queryByLabelText('文风意见审核理由 opinion')).toBeNull();
  expect(screen.queryByLabelText('可复用风格指令（最多 120 字）')).toBeNull();
  expect((screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement).value).toBe('TARGET');
  expect(vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
});
