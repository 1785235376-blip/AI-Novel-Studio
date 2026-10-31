// [HERMIA-FE-20261025 M5] Proves the mock payloads pass the REAL client parsers (so the browser run exercises real parsing).
import {createBackend} from './mockBackend.mjs';
import {studioProductionClient} from '../../src/creative/studioProductionClient';
import {studioClient, studioTransport} from '../../src/creative/studioClient';
import {createTaskCenterClient} from '../../src/taskcenter/taskCenterClient';
const b = createBackend(); const P = b.d.P;
(globalThis as any).fetch = async (url: string, init?: RequestInit) => { const [s, j] = b.handle(init?.method ?? 'GET', String(url), init?.body ? JSON.parse(String(init.body)) : null);
  return new Response(JSON.stringify(j), {status: s, headers: {'Content-Type': 'application/json'}}); };
const ctx = {sessionToken: 'tok', actor: {id: 'u-m5', displayName: 'u', workspaceId: 'ws1'}, scope: b.d.SCOPE};
const step = async (n: string, f: () => Promise<unknown>) => { try { const r: any = await f(); console.log('OK ', n, JSON.stringify(r)?.slice(0, 120)); } catch (e: any) { console.log('ERR', n, e?.message, e?.code); } };
const pc = studioProductionClient(P, ctx as any), sc = studioClient(P, ctx as any);
await step('tasks', () => createTaskCenterClient(P, studioTransport(ctx as any), ctx.scope).readTasks({q: '', failed_only: false}));
await step('jobs', () => pc.list()); await step('job get', () => pc.get('audio' as any, b.d.jobs[0].id)); await step('providers', () => pc.providers());
await step('canvas', () => sc.graphs.canvasViews.get(b.st.canvas.id)); await step('history', () => sc.graphs.canvasViews.history(b.st.canvas.id)); await step('assets', () => sc.assets(false));
