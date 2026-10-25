// @vitest-environment jsdom
// [HERMIA-FE-CONTRACTS G-PURGE-1] Real ?uw=1 host: a changed project.incarnation (overview) means a different project ⇒ own geometry purged.
// 404/500 overview is never "deleted". Evidence: mock (jsdom, stubbed fetch).
import {StrictMode} from 'react';
import {act, cleanup, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreviewHost} from './identityBootstrap';
import {useStudio} from '../../store';
import {viewPrefsKey} from './viewPreferences';
import {workspaceLayoutKey} from '../layout/persistence';
import {incarnationLedgerKey} from './projectIncarnation';

class FakeRO { observe() {} unobserve() {} disconnect() {} }
const nv = (id: string) => ({id, title: `作品${id}`, genre: '', chapter_count: 0, word_count: 0, status: 'Writing'});
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
const BOOT = {actor: {actor_id: 'actor-1', session_id: 's', client_id: 'c'}, scope: {workspace_id: 'ws1', project_id: 'n1', storyline_id: 's1', branch_id: 'b1'}, capabilities: {}};
const own = {userId: 'actor-1', projectId: 'n1', projectInstanceId: 'ws1/s1/b1'};
const other = {...own, userId: 'actor-2'};
let overview: 'A' | 'B' | 404 | 500 = 'A';
const ov = (inc: string) => ({project: {id: 'n1', title: 't', entry_kind: 'NEUTRAL_STUDIO', incarnation: `file:${inc}`},
  preferences: {version: 1, intents: [], preset: 'IMAGE', custom_intent: ''}, capabilities: {can_mutate: true, can_review: true, manual_import: true,
    manual_export: true, chapter_required: false, model_required: false, media_validator_configured: true, asset_kinds: ['image'], intent_is_permission: false}});
beforeEach(() => {
  localStorage.clear(); overview = 'A';
  vi.stubGlobal('ResizeObserver', FakeRO);
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/novels' ? json([nv('n1')]) : /\/bootstrap$/.test(url) ? json(BOOT)
    : url === '/api/projects/n1/studio' ? (typeof overview === 'number' ? json({detail: 'x'}, overview) : json(ov(overview)))
    : /chapters$/.test(url) ? json([]) : json({detail: 'nf'}, 404)));
  for (const s of [own, other]) { localStorage.setItem(viewPrefsKey(s), '{"version":1,"viewports":{"image":{"x":7,"y":7,"zoom":1}},"worksets":[]}'); localStorage.setItem(workspaceLayoutKey(s), '{}'); }
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); useStudio.setState({sessionToken: '', scope: undefined, actor: undefined}); });
const mount = async () => {
  useStudio.setState({sessionToken: 'tok', scope: {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'}, actor: undefined});
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  const view = render(<StrictMode><QueryClientProvider client={qc}><UnifiedWorkspacePreviewHost /></QueryClientProvider></StrictMode>);
  await waitFor(() => expect(screen.getByTestId('uw-identity').dataset.identity).toBe('real'));
  return view;
};
const settle = () => act(async () => { await new Promise(r => setTimeout(r, 80)); });

it('first incarnation is recorded without purging; a later different incarnation purges own geometry only', async () => {
  const v = await mount(); await settle();
  await waitFor(() => expect(localStorage.getItem(incarnationLedgerKey('actor-1', 'n1'))).toBe('file:A'));
  expect(localStorage.getItem(workspaceLayoutKey(own))).not.toBeNull();
  v.unmount(); overview = 'B';
  await mount(); await settle();
  await waitFor(() => expect(localStorage.getItem(incarnationLedgerKey('actor-1', 'n1'))).toBe('file:B'));
  expect(localStorage.getItem(workspaceLayoutKey(own))).toBeNull();
  // [Vera MUST-FIX 1] the remount must not write project A's in-memory viewport back into the just-cleared viewprefs.
  await settle();
  const vp = localStorage.getItem(viewPrefsKey(own));
  expect(vp === null || !/"x":7/.test(vp)).toBe(true);
  expect(localStorage.getItem(viewPrefsKey(other))).toContain('"x":7');
});
it.each([404, 500] as const)('overview %s is not deletion: nothing purged, ledger untouched', async status => {
  localStorage.setItem(incarnationLedgerKey('actor-1', 'n1'), 'file:A');
  overview = status;
  await mount(); await settle();
  expect(localStorage.getItem(workspaceLayoutKey(own))).not.toBeNull();
  expect(localStorage.getItem(viewPrefsKey(own))).not.toBeNull();
  expect(localStorage.getItem(incarnationLedgerKey('actor-1', 'n1'))).toBe('file:A');
});
it('[M14] without a real identity (仅本次会话) the overview is never read and the ledger is never written', async () => {
  useStudio.setState({sessionToken: '', scope: undefined, actor: undefined});
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  render(<StrictMode><QueryClientProvider client={qc}><UnifiedWorkspacePreviewHost /></QueryClientProvider></StrictMode>);
  await waitFor(() => expect(screen.getByTestId('uw-identity').dataset.identity).not.toBe('real'));
  await settle(); await settle();
  const urls = (fetch as unknown as {mock: {calls: unknown[][]}}).mock.calls.map(c => String(c[0]));
  expect(urls.some(u => u === '/api/novels')).toBe(true); // the host did render and read the project list
  expect(urls.filter(u => u.endsWith('/studio'))).toEqual([]);
  expect(localStorage.getItem(incarnationLedgerKey('actor-1', 'n1'))).toBeNull();
});
it('[M14b] a session token alone (bootstrap failed ⇒ no real actor) never reads the overview nor writes the ledger', async () => {
  const base = fetch as unknown as (url: string) => Promise<Response>;
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (/\/bootstrap$/.test(url) ? json({detail: 'down'}, 500) : base(url))));
  useStudio.setState({sessionToken: 'tok', scope: {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'}, actor: undefined});
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  render(<StrictMode><QueryClientProvider client={qc}><UnifiedWorkspacePreviewHost /></QueryClientProvider></StrictMode>);
  await settle(); await settle();
  expect(screen.getByTestId('uw-identity').dataset.identity).not.toBe('real');
  const urls = (fetch as unknown as {mock: {calls: unknown[][]}}).mock.calls.map(c => String(c[0]));
  expect(urls.some(u => /\/bootstrap$/.test(u))).toBe(true); // the token was really used for bootstrap
  expect(urls.filter(u => u.endsWith('/studio'))).toEqual([]);
  expect(localStorage.getItem(incarnationLedgerKey('actor-1', 'n1'))).toBeNull();
});
