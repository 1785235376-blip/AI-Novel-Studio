// @vitest-environment jsdom
// [HERMIA-FE-20261025 M10-purgeguard] Vera re-review MUST-FIX (empty list) + mutation killers. Base copied from u1.purge.host.test: on the real ?uw=1 host, when a project leaves the novels list the
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
let novels: unknown[] = [nv('n1'), nv('n2')]; let fail = false;
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
const BOOT = {actor: {actor_id: 'actor-1', session_id: 's', client_id: 'c'}, scope: {workspace_id: 'ws1', project_id: 'n1', storyline_id: 's1', branch_id: 'b1'}, capabilities: {}};
const own = {userId: 'actor-1', projectId: 'n2', projectInstanceId: 'ws1/s1/b1'};
const other = {...own, userId: 'actor-2'};
const keep = {...own, projectId: 'n1'};
beforeEach(() => {
  localStorage.clear(); novels = [nv('n1'), nv('n2')]; fail = false;
  vi.stubGlobal('ResizeObserver', FakeRO);
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/novels' ? (fail ? json({detail: 'boom'}, 500) : json(novels)) : /\/bootstrap$/.test(url) ? json(BOOT) : /chapters$/.test(url) ? json([]) : json({detail: 'nf'}, 404)));
  for (const s of [own, other, keep]) { localStorage.setItem(viewPrefsKey(s), '{"version":1,"viewports":{},"worksets":[]}'); localStorage.setItem(workspaceLayoutKey(s), '{}'); }
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); useStudio.setState({sessionToken: '', scope: undefined, actor: undefined}); });

const ownN1 = keep;
const mount = async () => {
  useStudio.setState({sessionToken: 'tok', scope: {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'}, actor: undefined});
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  render(<StrictMode><QueryClientProvider client={qc}><UnifiedWorkspacePreviewHost /></QueryClientProvider></StrictMode>);
  await waitFor(() => expect(screen.getByTestId('uw-identity').dataset.identity).toBe('real'));
  const list = async (v: unknown[] | 'fail') => { if (v === 'fail') fail = true; else { fail = false; novels = v; } await act(async () => { await qc.invalidateQueries(); }); await new Promise(r => setTimeout(r, 60)); };
  return list;
};
const has = (s: typeof own) => localStorage.getItem(viewPrefsKey(s)) !== null && localStorage.getItem(workspaceLayoutKey(s)) !== null;

it('Vera repro: [n1,n2] → [n1] → 200 [] does NOT wipe own keys of every seen project', async () => {
  const list = await mount();
  await list([nv('n1')]);
  await list([]);
  expect(has(ownN1)).toBe(true);
  expect(has(own)).toBe(true); // n2 missing once only; empty list is not evidence
});
it('two consecutive non-empty lists missing a project purge it (own only); a 500 in between neither confirms nor resets', async () => {
  const list = await mount();
  await list([nv('n1')]);       // n2 missing once → pending
  expect(has(own)).toBe(true);
  await list('fail');           // load failure: no information
  await list([nv('n1')]);       // second successful list missing n2 → purge
  await waitFor(() => expect(localStorage.getItem(viewPrefsKey(own))).toBeNull());
  expect(localStorage.getItem(workspaceLayoutKey(own))).toBeNull();
  expect(has(other)).toBe(true); expect(has(ownN1)).toBe(true);
});
it('an empty list breaks the confirmation streak', async () => {
  const list = await mount();
  await list([nv('n1')]); await list([]); await list([nv('n1')]);
  expect(has(own)).toBe(true);  // only one confirmation since the empty list
  await list([nv('n1')]);
  await waitFor(() => expect(has(own)).toBe(false));
});
it('re-rendering on a project switch is not a second observation (one fetch = one piece of evidence)', async () => {
  novels = [nv('n1'), nv('n2'), nv('n3')];
  const list = await mount();
  await list([nv('n1'), nv('n3')]);  // n2 missing once → pending
  const sel = await screen.findByLabelText('选择作品') as HTMLSelectElement;
  await act(async () => { const {fireEvent} = await import('@testing-library/react'); fireEvent.change(sel, {target: {value: 'n3'}}); });
  await new Promise(r => setTimeout(r, 60));
  await act(async () => { const {fireEvent} = await import('@testing-library/react'); fireEvent.change(sel, {target: {value: 'n1'}}); });
  await new Promise(r => setTimeout(r, 60));
  expect(sel.value).toBe('n1');
  expect(has(own)).toBe(true);       // still only one confirmation
  await list([nv('n1'), nv('n3')]);  // a real second fetch confirms
  await waitFor(() => expect(has(own)).toBe(false));
});
