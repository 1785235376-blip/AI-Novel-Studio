// @vitest-environment jsdom
// [HERMIA-FE-20261025 M10-purgefix] Vera final MUST-FIX: on the real ?uw=1 host, when a project leaves the novels list the
// current user's viewprefs/layout keys for it are removed and other users' keys are kept. Repro-first: fails on f778eaec
// (realUser derived via a sentinel projectId → scope-mismatch → null → purge never ran). Evidence: mock (jsdom, stubbed fetch).
import {StrictMode} from 'react';
import {act, cleanup, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreviewHost} from './identityBootstrap';
import {useStudio} from '../../store';
import {viewPrefsKey} from './viewPreferences';
import {workspaceLayoutKey} from '../layout/persistence';

class FakeRO { observe() {} unobserve() {} disconnect() {} }
const nv = (id: string) => ({id, title: `作品${id}`, genre: '', chapter_count: 0, word_count: 0, status: 'Writing'});
let novels = [nv('n1'), nv('n2')];
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
const BOOT = {actor: {actor_id: 'actor-1', session_id: 's', client_id: 'c'}, scope: {workspace_id: 'ws1', project_id: 'n1', storyline_id: 's1', branch_id: 'b1'}, capabilities: {}};
const own = {userId: 'actor-1', projectId: 'n2', projectInstanceId: 'ws1/s1/b1'};
const other = {...own, userId: 'actor-2'};
const keep = {...own, projectId: 'n1'};
beforeEach(() => {
  localStorage.clear(); novels = [nv('n1'), nv('n2')];
  vi.stubGlobal('ResizeObserver', FakeRO);
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/novels' ? json(novels) : /\/bootstrap$/.test(url) ? json(BOOT) : /chapters$/.test(url) ? json([]) : json({detail: 'nf'}, 404)));
  for (const s of [own, other, keep]) { localStorage.setItem(viewPrefsKey(s), '{"version":1,"viewports":{},"worksets":[]}'); localStorage.setItem(workspaceLayoutKey(s), '{}'); }
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); useStudio.setState({sessionToken: '', scope: undefined, actor: undefined}); });

it('host purges own keys of a project that left the list; other users and remaining projects are kept', async () => {
  useStudio.setState({sessionToken: 'tok', scope: {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'}, actor: undefined});
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  render(<StrictMode><QueryClientProvider client={qc}><UnifiedWorkspacePreviewHost /></QueryClientProvider></StrictMode>);
  await waitFor(() => expect(screen.getByTestId('uw-identity').dataset.identity).toBe('real'));
  expect(localStorage.getItem(viewPrefsKey(own))).not.toBeNull(); // first observation never purges
  novels = [nv('n1')];
  await act(async () => { await qc.invalidateQueries(); });
  await waitFor(() => expect(localStorage.getItem(viewPrefsKey(own))).toBeNull());
  expect(localStorage.getItem(workspaceLayoutKey(own))).toBeNull();
  expect(localStorage.getItem(viewPrefsKey(other))).not.toBeNull();
  expect(localStorage.getItem(workspaceLayoutKey(other))).not.toBeNull();
  expect(localStorage.getItem(viewPrefsKey(keep))).not.toBeNull();
});
