// @vitest-environment jsdom
// [HERMIA-FE-20261025 M5] Counterexample found in the REAL browser run (shots/00-repro-preview-no-bootstrap-1366.png):
// ?uw=1 returns before LegacyApp's bootstrap, so a signed-in session + complete scope never gets the server actor and the
// whole loop stays "仅本次会话". Evidence kind: mock (fetch stub).
import {cleanup, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreviewHost} from '../state/identityBootstrap';
import {useStudio} from '../../store';

if (!(window as unknown as {PointerEvent?: unknown}).PointerEvent) (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
const SCOPE = {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'};
let calls: {url: string; method: string}[];
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
const initial = useStudio.getState();
let bootstrapStatus = 200;
beforeEach(() => {
  localStorage.clear(); calls = []; bootstrapStatus = 200;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({url: String(url), method: init?.method ?? 'GET'});
    if (url === '/api/novels') return json([{id: 'n1', title: '演示', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'}]);
    if (url === '/api/novels/n1/chapters') return json([]);
    if (String(url).endsWith('/bootstrap')) return bootstrapStatus === 200
      ? json({actor: {actor_id: 'u-server', session_id: 's', client_id: 'c'}, scope: {workspace_id: 'ws1', project_id: 'n1', storyline_id: 's1', branch_id: 'b1'}, capabilities: {}})
      : json({detail: 'no'}, bootstrapStatus);
    return json({detail: 'nf'}, 404);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); useStudio.setState(initial, true); });
const mount = () => render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><UnifiedWorkspacePreviewHost /></QueryClientProvider>);

it('signed-in session + complete scope ⇒ preview reads the server actor (GET bootstrap once) and the task list connects', async () => {
  useStudio.setState({sessionToken: 'tok', scope: SCOPE, actor: undefined});
  mount();
  await waitFor(() => expect(useStudio.getState().actor?.id).toBe('u-server'));
  await waitFor(() => expect(calls.some(c => c.url.includes('/experimental/workspace/tasks'))).toBe(true));
  expect(calls.filter(c => c.url.endsWith('/bootstrap'))).toHaveLength(1);
  expect(calls.every(c => c.method === 'GET')).toBe(true);
  expect(screen.queryByText(/仅本次会话/)).toBeNull();
});
it('bootstrap refused ⇒ stays 仅本次会话, never invents an actor', async () => {
  bootstrapStatus = 401;
  useStudio.setState({sessionToken: 'tok', scope: SCOPE, actor: undefined});
  mount();
  await waitFor(() => expect(calls.some(c => c.url.endsWith('/bootstrap'))).toBe(true));
  await new Promise(r => setTimeout(r, 50));
  expect(useStudio.getState().actor).toBeUndefined();
  expect(screen.getAllByText(/仅本次会话/).length).toBeGreaterThan(0);
});
it('no session token ⇒ no bootstrap read at all', async () => {
  useStudio.setState({sessionToken: '', scope: SCOPE, actor: undefined});
  mount(); await screen.findByTestId('dock-layout');
  await new Promise(r => setTimeout(r, 50));
  expect(calls.some(c => c.url.endsWith('/bootstrap'))).toBe(false);
});
