// @vitest-environment jsdom
// Real App + EntryExperience interaction. Controlled original API promises expose ordering;
// this is a mounted regression, not real-backend acceptance.
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { api, ApiError, getCollaborationContext, type AdminWorkspace, type Novel } from './api';
import { useStudio } from './store';
import { rememberLocalWorkspaceSelection } from './workspaceSelection';

const clients: QueryClient[] = [];
const original = { id: 'local-control', title: 'Existing local production control', genre: '',
  word_count: 0, chapter_count: 0, status: 'Writing' } as Novel;
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); useStudio.getState().setCollaboration('');
  useStudio.setState({ novelId: '', chapterId: '', actor: undefined, scope: undefined, textModel: null });
  vi.spyOn(api, 'textModels').mockResolvedValue([]);
  vi.spyOn(api, 'chapters').mockResolvedValue([]);
  vi.spyOn(api, 'scopedChapters').mockResolvedValue([]);
  vi.spyOn(api, 'archivedChapters').mockResolvedValue([]);
  vi.spyOn(api, 'mediaTasks').mockResolvedValue({ novel_id: original.id, audiobook: [], motion: [] });
  vi.spyOn(api, 'writingGoal').mockResolvedValue({ current_words: 0, target_words: 0,
    current_chapters: 0, target_chapters: 0, words_progress: 0 } as never);
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ features: {}, items: [] }),
    { status: 200, headers: { 'Content-Type': 'application/json' } })));
});
afterEach(() => {
  cleanup(); clients.splice(0).forEach(client => client.clear());
  vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear();
  useStudio.getState().setCollaboration('');
});
function mount(mode: 'unavailable' | 'empty-hint' | 'saved-hint') {
  const query = new QueryClient({ defaultOptions: { queries: { retry: 1, retryDelay: 0, staleTime: Infinity },
    mutations: { retry: false } } }); clients.push(query);
  if (mode === 'unavailable') {
    // The real producer request still runs and reaches its existing unavailable/error state.
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ code: 'UNAUTHORIZED' }),
      { status: 401, headers: { 'Content-Type': 'application/json' } })));
  } else {
    query.setQueryData(['experimental-features', 'file'], { experimental: true, default_enabled: false,
      features: { 'experimental.workspace_tools_v2': true } });
    if (mode === 'saved-hint') rememberLocalWorkspaceSelection(original.id);
  }
  render(<QueryClientProvider client={query}><App /></QueryClientProvider>);
  return query;
}

describe('local automatic entry keeps original authority', () => {
  it.each(['unavailable', 'empty-hint', 'saved-hint'] as const)(
    'a late authenticated local-inventory retry cannot unmount the real connection UI (%s)', async mode => {
      const first = deferred<Novel[]>(), inventory = deferred<Novel[]>(), workspace = deferred<AdminWorkspace[]>();
      const observedTokens: string[] = [];
      const novels = vi.spyOn(api, 'novels').mockImplementation(() => {
        observedTokens.push(getCollaborationContext().sessionToken);
        return observedTokens.length === 1 ? first.promise : inventory.promise;
      });
      const admin = vi.spyOn(api, 'adminWorkspaces').mockImplementation(() => workspace.promise);
      const scope = { workspaceId: 'w', projectId: 'authorized-project', storylineId: 's', branchId: 'b' };
      vi.spyOn(api, 'adminWorkspaceNavigation').mockResolvedValue({ workspace_id: 'w', default_path: null,
        eligible_paths: [{ workspace_id: 'w', project_id: scope.projectId, storyline_id: 's', branch_id: 'b',
          project_name: 'Explicit authorized project' }] });
      vi.spyOn(api, 'bootstrap').mockResolvedValue({ actor: { actor_id: 'author', session_id: 'session', client_id: 'client' },
        scope: { workspace_id: 'w', project_id: scope.projectId, storyline_id: 's', branch_id: 'b' }, capabilities: {} });
      const query = mount(mode);
      await waitFor(() => expect(novels).toHaveBeenCalledTimes(1));
      // Use the actual entry controls; no store/token injection initiates this connection.
      fireEvent.click(screen.getByText('连接已有创作空间', { exact: true }));
      fireEvent.change(screen.getByLabelText('访问凭证', { exact: true }), { target: { value: 'new-trusted-session' } });
      fireEvent.click(screen.getByRole('button', { name: '连接创作空间' }));
      await waitFor(() => expect(admin).toHaveBeenCalledTimes(1));
      expect(useStudio.getState().sessionToken).toBe('');
      expect(getCollaborationContext().sessionToken).toBe('new-trusted-session');
      // A real query retry starts only after EntryExperience installed the candidate authority.
      await act(async () => first.reject(new ApiError({ status: 401, code: 'UNAUTHORIZED', message: 'retry' })));
      await waitFor(() => expect(novels).toHaveBeenCalledTimes(2));
      expect(observedTokens).toEqual(['', 'new-trusted-session']);
      await act(async () => inventory.resolve([original]));
      expect(query.getQueryData(['novels'])).toEqual([original]);
      expect(useStudio.getState().novelId).toBe('');
      expect(screen.getByLabelText('访问凭证', { exact: true })).toBeTruthy();
      // An unrelated query render must neither select the local novel nor reset candidate authority.
      act(() => query.setQueryData(['text-models'], []));
      expect(getCollaborationContext().sessionToken).toBe('new-trusted-session');
      await act(async () => workspace.resolve([{ id: 'w', name: 'My authorized workspace' }]));
      fireEvent.click(await screen.findByRole('button', { name: 'My authorized workspace' }));
      fireEvent.click(await screen.findByRole('button', { name: /Explicit authorized project/ }));
      await waitFor(() => expect(useStudio.getState().scope?.projectId).toBe(scope.projectId));
      expect(useStudio.getState().sessionToken).toBe('new-trusted-session');
      expect(useStudio.getState().novelId).toBe(scope.projectId);
      expect(api.bootstrap).toHaveBeenCalledWith(expect.objectContaining(scope));
    });
  it('keeps the existing first-local-novel behavior when authority has not changed', async () => {
    const inventory = deferred<Novel[]>(); vi.spyOn(api, 'novels').mockImplementation(() => inventory.promise);
    mount('unavailable'); await screen.findByLabelText('访问凭证', { exact: true });
    await act(async () => inventory.resolve([original]));
    await waitFor(() => expect(useStudio.getState().novelId).toBe(original.id));
    expect(getCollaborationContext().sessionToken).toBe('');
    expect(screen.queryByLabelText('访问凭证', { exact: true })).toBeNull();
  });
});
