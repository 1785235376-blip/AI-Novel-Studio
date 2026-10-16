// @vitest-environment jsdom
// Mount the original App, module switcher and workspaces. Only API timing is
// controlled here; real File/PG/browser acceptance is recorded separately.
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider, useIsFetching } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { api, type Actor, type Bootstrap, type Novel, type Scope } from './api';
import { useStudio } from './store';
import { recoveryKey } from './collaborationGuards';
import { rememberLocalStudioSelection } from './workspaceSelection';
import type { StudioOverview } from './creative/studioClient';
import * as shell from './ui/AppShell';
import * as tutorEntry from './interop/entry';
import * as independentWorkspace from './creative/IndependentStudioWorkspace';

const clients: QueryClient[] = [];
const project = 'navigation-project';
const actor: Actor = { id: 'author', displayName: 'Author', workspaceId: 'workspace' };
const scope: Scope = { workspaceId: 'workspace', projectId: project, storylineId: 'storyline', branchId: 'branch' };
type HeldOverview = { project: string; headers: Headers; signal?: AbortSignal | null; resolve: (value: Response) => void };
let held: HeldOverview[];
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});
function overview(id = project): StudioOverview {
  return { project: { id, title: `Project ${id}`, entry_kind: 'NEUTRAL_STUDIO' },
    preferences: { version: 0, intents: [], preset: 'BLANK', custom_intent: '' },
    capabilities: { manual_import: true, manual_export: true, can_mutate: true,
      model_required: false, chapter_required: false, media_validator_configured: false,
      asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(yes => { resolve = yes; });
  return { promise, resolve };
}
function seedFlags(query: QueryClient) {
  const state = useStudio.getState(), namespace = recoveryKey(state.scope, state.sessionToken) || 'file';
  query.setQueryData(['experimental-features', namespace], { experimental: true, default_enabled: false,
    features: { 'experimental.narrative_production_v2': true, 'experimental.workspace_tools_v2': true } });
}
function OriginalQueryTiming() {
  const count = useIsFetching({ queryKey: ['independent-project'] });
  return <output aria-label="Original overview queries pending">{count}</output>;
}
function mount(scoped: boolean | 'resolving' = false, strict = false) {
  if (scoped) useStudio.getState().setCollaboration('trusted-session', scoped === 'resolving' ? undefined : actor, scope);
  else useStudio.setState({ novelId: project });
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  clients.push(query); seedFlags(query);
  const tree = <QueryClientProvider client={query}><OriginalQueryTiming /><App /></QueryClientProvider>;
  const view = render(strict ? <StrictMode>{tree}</StrictMode> : tree);
  return { query, view };
}
const tab = (name: string) => within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name });
function selected(name: string) { expect(tab(name).getAttribute('aria-selected')).toBe('true'); }
async function request(index = 0) { await waitFor(() => expect(held.length).toBeGreaterThan(index)); return held[index]; }
async function release(row: HeldOverview, settleCurrent = true, value = overview(row.project)) {
  await act(async () => row.resolve(response(value)));
  // Observe the real QueryClient notification in mounted React before asserting
  // module state, rather than inspecting cache bytes ahead of React's render.
  if (settleCurrent) await waitFor(() => expect(screen.getByLabelText('Original overview queries pending').textContent).toBe('0'));
}
function change(query: QueryClient, token: string, nextActor: Actor | undefined, nextScope: Scope) {
  act(() => { useStudio.getState().setCollaboration(token, nextActor, nextScope); seedFlags(query); });
}

beforeEach(() => {
  held = []; localStorage.clear(); sessionStorage.clear(); useStudio.getState().setCollaboration('');
  useStudio.setState({ novelId: '', chapterId: '', actor: undefined, scope: undefined, textModel: null });
  vi.spyOn(shell, 'AppShell'); vi.spyOn(tutorEntry, 'useLocalTutorIntegration');
  vi.spyOn(independentWorkspace, 'IndependentStudioWorkspace');
  vi.spyOn(api, 'novels').mockResolvedValue([{ id: project, title: 'Navigation project' }] as Novel[]);
  vi.spyOn(api, 'textModels').mockResolvedValue([]);
  vi.spyOn(api, 'chapters').mockResolvedValue([]);
  vi.spyOn(api, 'scopedChapters').mockResolvedValue([]);
  vi.spyOn(api, 'archivedChapters').mockResolvedValue([]);
  // Keep bootstrap actor installation outside this controlled overview experiment.
  vi.spyOn(api, 'bootstrap').mockImplementation(() => new Promise(() => {}));
  vi.spyOn(api, 'mediaTasks').mockResolvedValue({ novel_id: project, audiobook: [], motion: [] });
  vi.spyOn(api, 'writingGoal').mockResolvedValue({ current_words: 0, target_words: 0,
    current_chapters: 0, target_chapters: 0, words_progress: 0 } as never);
  vi.stubGlobal('fetch', vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
    const match = String(url).match(/^\/api\/projects\/([^/]+)\/studio$/);
    if (match) return new Promise<Response>(resolve => held.push({ project: decodeURIComponent(match[1]),
      headers: new Headers(init?.headers), signal: init?.signal, resolve }));
    // Unrelated owners fail closed; no fabricated creative/model output is used.
    return Promise.resolve(response({ code: 'NOT_CONFIGURED', message: 'Outside navigation timing test' }, 404));
  }));
});
afterEach(() => {
  cleanup(); clients.splice(0).forEach(query => query.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals();
  localStorage.clear(); sessionStorage.clear(); useStudio.getState().setCollaboration('');
});

describe('App module navigation during delayed original overview', () => {
  it('counts an explicit click on the already-selected NOVEL as intent', async () => {
    mount(); const pending = await request(); selected('小说');
    fireEvent.click(tab('小说')); await release(pending);
    await waitFor(() => expect(screen.getByRole('button', { name: '打开 V2 创作工作台' })).toBeTruthy());
    selected('小说');
  });
  it('keeps the last rapid choice through the original ModuleWorkspace switcher', async () => {
    mount(); const pending = await request();
    fireEvent.click(tab('图片')); selected('图片');
    fireEvent.click(tab('视频')); selected('视频');
    fireEvent.click(tab('小说')); selected('小说');
    await release(pending); selected('小说');
  });
  it('keeps VIDEO when the neutral overview arrives after IMAGE to VIDEO', async () => {
    mount(); const pending = await request();
    fireEvent.click(tab('图片')); fireEvent.click(tab('视频'));
    await release(pending); selected('视频');
  });
  it('routes a real CreativeWorkspace module click through the same App intent', async () => {
    mount(); const pending = await request();
    fireEvent.click(screen.getByRole('button', { name: '打开 V2 创作工作台' }));
    fireEvent.click(tab('视频')); selected('视频');
    await release(pending); selected('视频');
  });
  it('keeps the explicitly opened CreativeWorkspace on NOVEL without requiring another top-level tab click', async () => {
    mount(); const pending = await request();
    fireEvent.click(screen.getByRole('button', { name: '打开 V2 创作工作台' }));
    expect(screen.getByRole('tablist', { name: '创作模式' })).toBeTruthy();
    await release(pending); selected('小说');
    expect(screen.getByRole('tablist', { name: '创作模式' })).toBeTruthy();
  });
  it('preserves the neutral IMAGE default when there has been no explicit choice', async () => {
    mount(); await release(await request()); await waitFor(() => selected('图片'));
  });
  it('restores the original local VIDEO hint without treating it as a user choice in another project', async () => {
    rememberLocalStudioSelection(project, 'VIDEO');
    const { query } = mount(); await release(await request()); await waitFor(() => selected('视频'));
    act(() => useStudio.getState().setNovel('next-project'));
    // The old IndependentStudio may also read its overview; locate the actual new owner.
    await waitFor(() => expect(held.some(row => row.project === 'next-project')).toBe(true));
    const next = held.find(row => row.project === 'next-project')!; await release(next);
    await waitFor(() => selected('图片'));
    expect(query.getQueryCache().findAll({ queryKey: ['independent-project'] }).length).toBeGreaterThan(1);
  });
  it('does not let automatic default count as intent, and still honors navigation from IndependentStudio', async () => {
    mount(); await release(await request()); await waitFor(() => selected('图片'));
    fireEvent.click(tab('视频')); fireEvent.click(tab('小说')); selected('小说');
    // Refetching the original query cannot apply the default a second time.
    const current = clients[0]; await act(async () => { void current.invalidateQueries({ queryKey: ['independent-project'] }); });
    await waitFor(() => expect(held.length).toBeGreaterThan(2));
    await release(held[held.length - 1]); selected('小说');
  });
  it('starts a fresh intent lifetime on a real App remount (refresh equivalent)', async () => {
    const first = mount(); const old = await request(); fireEvent.click(tab('小说')); first.view.unmount();
    const start = held.length; mount(); const fresh = await request(start);
    await release(old, false); selected('小说');
    await release(fresh); await waitFor(() => selected('图片'));
  });
  it('retains an explicit same-value choice under StrictMode', async () => {
    mount(false, true); await request(); fireEvent.click(tab('小说'));
    for (const row of [...held]) await release(row, false);
    await waitFor(() => expect(screen.getByLabelText('Original overview queries pending').textContent).toBe('0'));
    selected('小说');
  });
  it('counts the original authorized interop OPEN_PROJECT route as explicit NOVEL intent', async () => {
    mount(true); const pending = await request();
    const host = vi.mocked(tutorEntry.useLocalTutorIntegration).mock.calls.at(-1)![0];
    await act(async () => host.onNavigate({ action: 'OPEN_PROJECT', project_id: project,
      scope: { workspace_id: scope.workspaceId, project_id: project, storyline_id: scope.storylineId,
        branch_id: scope.branchId } }, new AbortController().signal));
    await release(pending); selected('小说');
  });
  it.each([['media', '资产'], ['workflow', '工作流'], ['model-center', '主控']])(
    'retains the original authorized interop feature route %s', async (feature, name) => {
      mount(true); const pending = await request();
      const host = vi.mocked(tutorEntry.useLocalTutorIntegration).mock.calls.at(-1)![0];
      await act(async () => host.onNavigate({ action: 'OPEN_FEATURE', feature, project_id: project,
        scope: { workspace_id: scope.workspaceId, project_id: project, storyline_id: scope.storylineId,
          branch_id: scope.branchId } }, new AbortController().signal));
      selected(name); await release(pending); selected(name);
    });
  it('keeps module intent when the selected chapter changes inside the same project authority', async () => {
    mount(); const pending = await request(); fireEvent.click(tab('小说'));
    act(() => useStudio.getState().setChapter('another-chapter'));
    await release(pending); selected('小说');
    expect(held.filter(row => row.project === project)).toHaveLength(1);
  });
  it('rejects a module callback captured before A to B to A without consuming the new default', async () => {
    const { query } = mount(true); const firstA = await request();
    const oldNavigate = vi.mocked(shell.AppShell).mock.calls.at(-1)![0].onModuleChange;
    change(query, 'trusted-session', actor, { ...scope, branchId: 'other-branch' }); const b = await request(1);
    change(query, 'trusted-session', actor, scope); const newA = await request(2);
    act(() => oldNavigate('VIDEO')); selected('小说');
    await release(firstA, false); await release(b, false); selected('小说');
    await release(newA); await waitFor(() => selected('图片'));
  });
  it('preserves a cold-entry NOVEL click and its callback when the original bootstrap first resolves actor', async () => {
    const bootstrap = deferred<Bootstrap>(); vi.mocked(api.bootstrap).mockReturnValue(bootstrap.promise);
    // Reproduce Entry's actual onEnter shape: same authorized connection, actor
    // is installed later by App's original bootstrap effect.
    mount('resolving'); const beforeActor = await request();
    fireEvent.click(tab('小说'));
    const unresolvedNavigate = vi.mocked(shell.AppShell).mock.calls.at(-1)![0].onModuleChange;
    await act(async () => bootstrap.resolve({ actor: { actor_id: actor.id, session_id: 'session', client_id: 'client' },
      scope: { workspace_id: scope.workspaceId, project_id: project, storyline_id: scope.storylineId, branch_id: scope.branchId }, capabilities: {} }));
    await waitFor(() => expect(useStudio.getState().actor?.id).toBe(actor.id)); const current = await request(1);
    await release(beforeActor, false); await release(current); selected('小说');
    // A pending navigation owned by this same entry remains valid after its
    // first actor resolution; a different known actor is covered separately.
    act(() => unresolvedNavigate('VIDEO')); selected('视频');
  });
  it('still applies the original default after first bootstrap actor resolution without a user choice', async () => {
    const bootstrap = deferred<Bootstrap>(); vi.mocked(api.bootstrap).mockReturnValue(bootstrap.promise);
    mount('resolving'); const beforeActor = await request();
    await act(async () => bootstrap.resolve({ actor: { actor_id: actor.id, session_id: 'session', client_id: 'client' },
      scope: { workspace_id: scope.workspaceId, project_id: project, storyline_id: scope.storylineId, branch_id: scope.branchId }, capabilities: {} }));
    const current = await request(1); await release(beforeActor, false); selected('小说');
    await release(current); await waitFor(() => selected('图片'));
  });
  it('uses the fresh unscoped session transport without putting bearer tokens in query keys', async () => {
    const { query } = mount(); const old = await request(); fireEvent.click(tab('视频'));
    act(() => { useStudio.getState().setCollaboration('next-local-session'); useStudio.getState().setNovel(project); seedFlags(query); });
    const current = await request(1);
    expect(current.headers.get('X-Session-Token')).toBe('next-local-session');
    expect(JSON.stringify(query.getQueryCache().findAll({ queryKey: ['independent-project'] }).map(row => row.queryKey)))
      .not.toContain('next-local-session');
    await release(old, false); selected('视频'); await release(current); await waitFor(() => selected('图片'));
  });
  it('does not consume default initialization on a rejected wrong-project overview', async () => {
    const { query } = mount(); await release(await request(), true, overview('wrong-project')); selected('小说');
    await act(async () => { void query.invalidateQueries({ queryKey: ['independent-project'] }); });
    await release(await request(1)); await waitFor(() => selected('图片'));
  });
  it.each(['project', 'branch'] as const)('does not pass the previous local asset hint into a different %s after an explicit module choice', async kind => {
    rememberLocalStudioSelection(project, 'VIDEO', 'previous-project-private-asset');
    const { query } = mount(); await release(await request()); await waitFor(() => selected('视频'));
    const originalProps = vi.mocked(independentWorkspace.IndependentStudioWorkspace).mock.calls.at(-1)![0];
    expect(originalProps.requestedAssetId).toBe('previous-project-private-asset');
    const start = held.length;
    if (kind === 'project') act(() => useStudio.getState().setNovel('next-project'));
    else change(query, 'trusted-session', actor, scope);
    await request(start); fireEvent.click(tab('视频'));
    await act(async () => {});
    for (const pending of held.slice(start)) await release(pending, false);
    await waitFor(() => expect(screen.getByLabelText('Original overview queries pending').textContent).toBe('0'));
    const currentProps = vi.mocked(independentWorkspace.IndependentStudioWorkspace).mock.calls.at(-1)![0];
    expect(currentProps.projectId).toBe(kind === 'project' ? 'next-project' : project);
    expect(currentProps.requestedAssetId).toBeUndefined();
  });
  it('keeps a current-entry asset hint through explicit IndependentStudio navigation', async () => {
    rememberLocalStudioSelection(project, 'VIDEO', 'same-entry-asset');
    mount(); await release(await request()); await waitFor(() => selected('视频'));
    fireEvent.click(tab('图片')); fireEvent.click(tab('视频'));
    expect(vi.mocked(independentWorkspace.IndependentStudioWorkspace).mock.calls.at(-1)![0].requestedAssetId).toBe('same-entry-asset');
  });
  it('starts a new default lifetime after the original project-choice action and an explicit reopen', async () => {
    mount(); await release(await request()); await waitFor(() => selected('图片'));
    fireEvent.click(tab('视频'));
    const oldNavigate = vi.mocked(shell.AppShell).mock.calls.at(-1)![0].onModuleChange;
    fireEvent.click(screen.getByRole('button', { name: '返回项目列表' }));
    await waitFor(() => expect(useStudio.getState().novelId).toBe(''));
    const start = held.length;
    fireEvent.click(await screen.findByRole('button', { name: 'Navigation project' }));
    await request(start); selected('视频');
    act(() => oldNavigate('NOVEL')); selected('视频');
    for (const pending of held.slice(start)) await release(pending, false);
    await waitFor(() => selected('图片'));
  });
  it('rejects a pre-switch callback even when A to B to A is batched without an intermediate render', async () => {
    const { query } = mount(true); const firstA = await request();
    const oldNavigate = vi.mocked(shell.AppShell).mock.calls.at(-1)![0].onModuleChange;
    act(() => {
      useStudio.getState().setCollaboration('trusted-session', actor, { ...scope, branchId: 'other-branch' });
      useStudio.getState().setCollaboration('trusted-session', actor, scope);
      seedFlags(query);
    });
    const newA = await request(1);
    act(() => oldNavigate('VIDEO')); selected('小说');
    await release(firstA, false); selected('小说');
    await release(newA); await waitFor(() => selected('图片'));
  });
  it.each(['project', 'branch', 'storyline', 'workspace', 'actor', 'actor-workspace', 'session'] as const)(
    'does not reuse old intent or an old overview across a changed %s identity', async kind => {
      const { query } = mount(true); const old = await request(); fireEvent.click(tab('视频'));
      const nextScope = { ...scope }, nextActor = { ...actor }; let nextToken = 'trusted-session';
      if (kind === 'project') nextScope.projectId = 'next-project';
      if (kind === 'branch') nextScope.branchId = 'next-branch';
      if (kind === 'storyline') nextScope.storylineId = 'next-storyline';
      if (kind === 'workspace') nextScope.workspaceId = 'next-workspace';
      if (kind === 'actor') nextActor.id = 'next-author';
      if (kind === 'actor-workspace') nextActor.workspaceId = 'next-actor-workspace';
      if (kind === 'session') nextToken = 'next-trusted-session';
      change(query, nextToken, nextActor, nextScope); const fresh = await request(1);
      await release(old, false); selected('视频');
      await release(fresh); await waitFor(() => selected('图片'));
    });
  it('does not let a previous branch response replace a new branch explicit same-value NOVEL choice', async () => {
    const { query } = mount(true); const old = await request();
    change(query, 'trusted-session', actor, { ...scope, branchId: 'next-branch' }); const fresh = await request(1);
    fireEvent.click(tab('小说')); await release(old, false); selected('小说');
    await release(fresh); selected('小说');
  });
  it('does not reuse the first A response or intent after A to B to A', async () => {
    const { query } = mount(true); const firstA = await request(); fireEvent.click(tab('视频'));
    change(query, 'trusted-session', actor, { ...scope, branchId: 'other-branch' }); const b = await request(1);
    change(query, 'trusted-session', actor, scope); const newA = await request(2);
    await release(firstA, false); await release(b, false); selected('视频');
    await release(newA); await waitFor(() => selected('图片'));
  });
});
