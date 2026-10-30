// @vitest-environment jsdom
// [HERMIA-FE-20261031 VERA-P2] App-level coverage for 01dd8918: an activated (NEUTRAL_STUDIO) project's IMAGE
// default lands on the formal image page, not the independent Studio shell; explicit asset handoff and other
// manual modules still use the shell. Mounts the real App; only API timing is controlled.
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

const studioModules = () => vi.mocked(independentWorkspace.IndependentStudioWorkspace).mock.calls.map(([props]) => props.module);
const imagePage = () => screen.queryAllByRole('toolbar', { name: '图片子入口' }).length > 0;

describe('activated project IMAGE routing (01dd8918)', () => {
  it('lands the neutral IMAGE default on the formal image page, not the Studio shell', async () => {
    mount(); await release(await request()); await waitFor(() => selected('图片'));
    await waitFor(() => expect(imagePage()).toBe(true));
    expect(studioModules()).not.toContain('IMAGE');
  });
  it('still opens the Studio shell for IMAGE when a saved asset was explicitly handed off', async () => {
    rememberLocalStudioSelection(project, 'IMAGE', 'handed-off-asset');
    mount(); await release(await request()); await waitFor(() => selected('图片'));
    await waitFor(() => expect(studioModules()).toContain('IMAGE'));
    expect(vi.mocked(independentWorkspace.IndependentStudioWorkspace).mock.calls.at(-1)![0].requestedAssetId).toBe('handed-off-asset');
    expect(imagePage()).toBe(false);
  });
  it('keeps VIDEO in the Studio shell for an activated project', async () => {
    mount(); await release(await request()); await waitFor(() => selected('图片'));
    fireEvent.click(tab('视频')); selected('视频');
    await waitFor(() => expect(studioModules().at(-1)).toBe('VIDEO'));
  });
});
