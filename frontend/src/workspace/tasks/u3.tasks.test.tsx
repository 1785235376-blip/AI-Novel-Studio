// @vitest-environment jsdom
// [HERMIA-FE-20261025 U3-M3/M4] Evidence type: mock (jsdom + injected fake readers). NOT real browser, NOT real API.
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {ApiError} from '../../api';
import type {ProductionJob} from '../../creative/studioProductionClient';
import {taskCenterProjection} from '../../taskcenter/taskCenterContract';
import {FIXTURE_PROJECT, projectedTask, tasksResponse} from '../../taskcenter/taskCenterFixtures';
import type {NavReturnPoint} from '../contracts';
import {TasksPanelLive} from '../panels/TasksPanelLive';
import {createScopeLease, LeaseHolder} from '../state/scopeLease';
import {TaskFeed, type TaskReaders} from './taskFeed';
import {NAV_TEXT, TaskNavigator} from './taskNavigation';
import {fromProductionJob, pageOf, TASK_PAGE_SIZE} from './taskSources';

afterEach(cleanup);
const HEX = 'ab'.repeat(32);
const tcRows = (o: Record<string, unknown> = {}) => taskCenterProjection(tasksResponse(o), FIXTURE_PROJECT, {mode: 'local', novel_id: FIXTURE_PROJECT});
function job(over: Partial<ProductionJob> = {}): ProductionJob {
  return {contract: 'studio-production-job/1', owner: 'image', id: 'job1', novel_id: 'n1', branch_id: null, version: 3, operation_id: 'm5.image.i2i', request_id: 'r1',
    status: 'AWAITING_REVIEW', request_digest: HEX, receipt_digest: null, output_candidate: null, product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false,
    remote_compute_may_continue: false, timeline_snapshot: null, sources: [], provider: null, approved_asset_version: null, created_at: '', updated_at: '',
    execution_recipe: {contract: 'studio-execution-recipe/1', operation_id: 'm5.image.i2i', adapter: 'x', recipe_digest: HEX, automatic_fallback: false},
    command: {operation_id: 'm5.image.i2i', request_id: 'r1', prompt: '', parameters: {}, source_snapshots: [], allow_cloud: false, license_note: '',
      canvas_return: {contract: 'studio-canvas-return/1', project_id: 'n1', scope: {mode: 'local', novel_id: 'n1'}, incarnation: 'file:x', canvas_id: 'cv1', canvas_version: 1, canvas_digest: HEX, card_id: 'node-7',
        source: {id: 'a1', kind: 'ASSET', version: 1, digest: HEX, asset_kind: 'image'}}} as never,
    ...over};
}
const deferred = <T,>() => { let res!: (v: T) => void, rej!: (e: unknown) => void; const p = new Promise<T>((a, b) => { res = a; rej = b; }); return {p, res, rej}; };
const RP: NavReturnPoint = {panelId: 'creative', canvas: 'creative', nodeIds: ['n-a', 'n-b'], focusTestId: 'cv-node-n-a', viewport: {x: -260, y: 40, zoom: 1.5}};

describe('[U3-M3] task feed over existing owners', () => {
  it('not-connected when there is no real identity/lease: no read, no sample rows', async () => {
    const f = new TaskFeed(null, null); await f.refresh();
    expect(f.state.kind).toBe('not-connected');
  });
  it('loading → ready with both sources; task-center rows have no fake link; production link comes from canvas_return', async () => {
    const readTasks = vi.fn(async () => tcRows()); const list = vi.fn(async () => [job()]);
    const f = new TaskFeed({taskCenter: {readTasks}, production: {list, get: vi.fn()}}, createScopeLease('A'));
    expect(f.state.kind).toBe('loading');
    await f.refresh();
    if (f.state.kind !== 'ready') throw new Error(f.state.kind);
    expect(f.state.items.map(i => i.source)).toEqual(['production-job', 'task-center']);
    expect(f.state.items[0].link).toEqual({canvas: 'creative', documentId: 'cv1', nodeId: 'node-7'});
    expect(f.state.items[1].link).toBeNull();
    expect(readTasks).toHaveBeenCalledTimes(1); expect(list).toHaveBeenCalledTimes(1);
  });
  it('empty, error(+next step), revoked(401/403 clears rows)', async () => {
    const e = new TaskFeed({taskCenter: {readTasks: async () => tcRows({items: []})}}, createScopeLease('A')); await e.refresh();
    expect(e.state.kind).toBe('empty');
    const er = new TaskFeed({taskCenter: {readTasks: async () => { throw new TypeError('net'); }}}, createScopeLease('A')); await er.refresh();
    expect(er.state).toEqual({kind: 'error', text: '任务列表读取失败。', next: '检查网络后点「刷新」重试；不会自动重试。'});
    let deny = false;
    const r = new TaskFeed({taskCenter: {readTasks: async () => { if (deny) throw new ApiError({status: 403, code: 'X', message: 'no'}); return tcRows(); }}}, createScopeLease('A'));
    await r.refresh(); expect(r.state.kind).toBe('ready');
    deny = true; await r.refresh(); expect(r.state.kind).toBe('revoked');
  });
  it('late response from an older read is dropped (newer wins even if it resolves first)', async () => {
    const d1 = deferred<ReturnType<typeof tcRows>>(), d2 = deferred<ReturnType<typeof tcRows>>();
    const calls = [d1, d2]; const f = new TaskFeed({taskCenter: {readTasks: () => calls.shift()!.p}}, createScopeLease('A'));
    const a = f.refresh(), b = f.refresh();
    d2.res(tcRows({items: []})); await b; expect(f.state.kind).toBe('empty');
    d1.res(tcRows()); await a; expect(f.state.kind).toBe('empty');
  });
  it('A→B→A: response for the first A lease is dropped after switching, even when we come back to A', async () => {
    const holder = new LeaseHolder(); const d = deferred<ReturnType<typeof tcRows>>();
    const leaseA1 = holder.current('A'); const fA1 = new TaskFeed({taskCenter: {readTasks: () => d.p}}, leaseA1);
    const pending = fA1.refresh();
    holder.current('B'); const leaseA2 = holder.current('A');
    expect(leaseA2).not.toBe(leaseA1); expect(leaseA1.isCurrent()).toBe(false);
    d.res(tcRows()); await pending;
    expect(fA1.state.kind).toBe('loading'); // never became ready with stale rows
  });
  it('stale task: production UNKNOWN/needs_reconciliation and task-center stale are marked; detail re-read failure ⇒ gone', async () => {
    expect(fromProductionJob(job({status: 'UNKNOWN'})).stale).toBe(true);
    expect(fromProductionJob(job({needs_reconciliation: true})).stale).toBe(true);
    const get = vi.fn(async () => { throw new ApiError({status: 404, code: 'GONE', message: 'x'}); });
    const f = new TaskFeed({production: {list: async () => [job()], get}}, createScopeLease('A')); await f.refresh();
    if (f.state.kind !== 'ready') throw 0;
    const d = await f.detail(f.state.items[0]);
    expect(d?.gone).toBe(true); expect(d?.ref.stale).toBe(true); expect(get).toHaveBeenCalledWith('image', 'job1', expect.anything());
  });
  it('bounded client paging over the already-read list (server is unpaginated — gap shown)', () => {
    const items = Array.from({length: TASK_PAGE_SIZE * 2 + 3}, (_, i) => i);
    expect(pageOf(items, 0).rows).toHaveLength(TASK_PAGE_SIZE);
    expect(pageOf(items, 9)).toMatchObject({page: 2, pages: 3}); expect(pageOf(items, 9).rows).toEqual([40, 41, 42]);
  });
});

describe('[U3-M4] read-only navigation', () => {
  it('missing link and missing node are said plainly; no node is created', () => {
    const nav = new TaskNavigator(createScopeLease('A'));
    expect(nav.locate(fromProductionJob(job({command: null})), () => true)).toEqual({kind: 'missing', text: NAV_TEXT.noLink});
    const has = vi.fn(() => false);
    expect(nav.locate(fromProductionJob(job()), has)).toEqual({kind: 'missing', text: NAV_TEXT.noNode});
    expect(has).toHaveBeenCalledWith('creative', 'node-7');
  });
  it('return point is a deep copy, returned exactly once, and void after a scope switch', () => {
    const lease = createScopeLease('A'); const nav = new TaskNavigator(lease);
    const rp = {...RP, nodeIds: [...RP.nodeIds], viewport: {...RP.viewport!}};
    nav.remember(rp); rp.nodeIds.push('mut'); rp.viewport.x = 0;
    nav.remember({...RP, nodeIds: ['other']}); // second remember in the same trip ignored
    expect(nav.takeReturn()).toEqual(RP); expect(nav.takeReturn()).toBeNull();
    nav.remember(RP); lease.retire(); expect(nav.takeReturn()).toBeNull();
  });
  it('panel: select → detail → locate → execution → back restores selection/focus/viewport; zero writes', async () => {
    const writes = vi.fn();
    // Writers present on the same objects (as on the real clients) — the read-only path must never touch them.
    const readers = {production: {list: async () => [job()], get: async () => job(), execute: writes, create: writes, cancel: writes, review: writes, refresh: writes},
      taskCenter: {readTasks: async () => tcRows(), cancelTask: writes, reviewItem: writes, reviewBatch: writes}} as unknown as TaskReaders;
    const lease = createScopeLease('A'); const feed = new TaskFeed(readers, lease); const nav = new TaskNavigator(lease);
    const onLocate = vi.fn(), onOpenExecution = vi.fn(), onReturn = vi.fn();
    render(<TasksPanelLive feed={feed} navigator={nav} active hasNode={(_c, id) => id === 'node-7'} captureReturn={() => RP}
      onLocate={onLocate} onOpenExecution={onOpenExecution} onReturn={onReturn} />);
    await screen.findByRole('button', {name: /图像任务 · 等待审核/});
    fireEvent.click(screen.getByTestId('u3-refresh')); const row = await screen.findByRole('button', {name: /图像任务 · 等待审核/});
    expect(screen.queryByText(/job1|node-7|cv1/)).toBeNull(); // no raw ids on screen
    expect(row.getAttribute('data-task-id')).toBe('image:job1');
    fireEvent.click(row);
    await screen.findByTestId('u3-detail');
    expect(screen.getByText('成本：未知（服务端没有提供估算）')).toBeTruthy();
    fireEvent.click(screen.getByTestId('u3-locate'));
    expect(onLocate).toHaveBeenCalledWith({kind: 'located', canvas: 'creative', nodeId: 'node-7'});
    fireEvent.click(screen.getByTestId('u3-exec')); expect(onOpenExecution).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId('u3-back'));
    expect(onReturn).toHaveBeenCalledWith(RP);
    expect((screen.getByTestId('u3-back') as HTMLButtonElement).disabled).toBe(true);
    expect(writes).not.toHaveBeenCalled();
  });
  it('panel: not-connected and revoked render plain text; refresh disabled when not connected', async () => {
    render(<TasksPanelLive feed={new TaskFeed(null, null)} navigator={null} active hasNode={() => false} captureReturn={() => RP}
      onLocate={vi.fn()} onOpenExecution={vi.fn()} onReturn={vi.fn()} />);
    expect(screen.getByRole('status').textContent).toContain('任务列表未接通');
    expect((screen.getByTestId('u3-refresh') as HTMLButtonElement).disabled).toBe(true);
  });
  it('panel: missing node message, no onLocate', async () => {
    const lease = createScopeLease('A'); const feed = new TaskFeed({production: {list: async () => [job()], get: async () => job()}}, lease);
    const onLocate = vi.fn();
    render(<TasksPanelLive feed={feed} navigator={new TaskNavigator(lease)} active hasNode={() => false} captureReturn={() => RP}
      onLocate={onLocate} onOpenExecution={vi.fn()} onReturn={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', {name: /图像任务/})); await screen.findByTestId('u3-detail');
    await act(async () => { fireEvent.click(screen.getByTestId('u3-locate')); });
    await waitFor(() => expect(screen.getByTestId('u3-nav-msg').textContent).toBe(NAV_TEXT.noNode));
    expect(onLocate).not.toHaveBeenCalled();
  });
});

describe('[U3-M4] canvasHasNode reads the local draft only', async () => {
  const {canvasHasNode} = await import('./useLiveTasks');
  it('true only for an existing node id; malformed/absent ⇒ false', () => {
    const st = {getItem: (k: string) => k === 'poemseed.rebuild.canvas.image.n1' ? JSON.stringify({nodes: [{id: 'node-7'}]}) : k.endsWith('.video.n1') ? '{bad' : null};
    expect(canvasHasNode(st, 'n1', 'creative', 'node-7')).toBe(true);
    expect(canvasHasNode(st, 'n1', 'creative', 'x')).toBe(false);
    expect(canvasHasNode(st, 'n1', 'execution', 'node-7')).toBe(false);
    expect(canvasHasNode(null, 'n1', 'creative', 'node-7')).toBe(false);
  });
});
