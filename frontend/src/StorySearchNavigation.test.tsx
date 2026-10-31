// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { StoryDatabasePanel } from './App';
import { api, type Chapter } from './api';
vi.mock('./novel/StoryDatabase', () => ({
  StoryDatabase: ({ activeKind }: any) => <p>Category: {activeKind}</p>,
  SceneEditor: ({ value }: any) => <input aria-label="Located scene" readOnly value={value?.title || ''} />,
  VolumeEditor: ({ value }: any) => <input aria-label="Located volume" readOnly value={value?.title || ''} />,
  CharacterEditor: () => null, CharacterConsistencyPanel: () => null, CharacterEvolutionPanel: () => null,
  ForeshadowingEditor: () => null, ForeshadowingTrackerPanel: () => null, LocationEditor: () => null, OutlineEditor: () => null,
  RelationshipEditor: () => null, RelationshipGraph: () => null, StoryRouteEditor: () => null, TimelineEditor: () => null,
  WorldSummaryEditor: () => null, WorldRulesPanel: () => null,
}));
vi.mock('./novel/EntityAssetPanel', () => ({ EntityAssetPanel: () => null }));
vi.mock('./novel/VisionAnalysisPanel', () => ({ VisionAnalysisPanel: () => null }));
const chapter = { id: 'n:1', novel_id: 'n', number: 1, content: '', title: 'Source', version: 1, word_count: 0, status: 'DRAFT' } as Chapter;
const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.forEach(client => client.clear()); clients.length = 0; vi.restoreAllMocks(); });
it('reads the original owner then selects the exact scene rather than opening the category title', async () => {
  vi.spyOn(api, 'novel').mockResolvedValue({ id: 'n', title: 'Synthetic' } as any);
  vi.spyOn(api, 'outline').mockResolvedValue({}); vi.spyOn(api, 'chapters').mockResolvedValue([chapter]);
  const resource = vi.spyOn(api, 'resource').mockImplementation(async (_nid, kind) => kind === 'scenes' ? [{ id: 'scene-specific', title: 'Exact target scene', chapter_id: 'n:1' }] : []);
  vi.spyOn(api, 'storyRoutes').mockResolvedValue([]);
  const query = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(query);
  render(<QueryClientProvider client={query}><StoryDatabasePanel chapter={chapter} target={{ requestId: 1, id: 'scene-specific', record_kind: 'scene' }} onOpenChapter={vi.fn()} /></QueryClientProvider>);
  await waitFor(() => expect((screen.getByLabelText('Located scene') as HTMLInputElement).value).toBe('Exact target scene'));
  expect(screen.getByText('已定位当前记录：Exact target scene。未更改资料。')).toBeTruthy();
  expect(resource).toHaveBeenCalledWith('n', 'scenes');
});
