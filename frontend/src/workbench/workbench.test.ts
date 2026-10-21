// [HERMIA-FE-20261022] Contract tests for workbench core. Real logic, no network mocks.
import {describe, expect, it} from 'vitest';
import {LifecycleTracker, bindConfirmation, checkConfirmation, guardLate, ActionRegistry, PanelRegistry, loadLayout, saveLayout, resetLayout, layoutKey, adaptToViewport, registerDemoExtension, registerFeaturePanels, DEMO_PANEL_ID, shouldHandleShortcut, type ActionContext} from './index';
import {FEATURE_GROUPS} from '../ui/FeatureLauncher';

class Mem { m = new Map<string, string>(); getItem(k: string) { return this.m.get(k) ?? null; } setItem(k: string, v: string) { this.m.set(k, v); } removeItem(k: string) { this.m.delete(k); } }
const scope = {userId: 'u1', projectId: 'p1', projectInstanceId: 'i1'};
const ctx = (t: LifecycleTracker, extra: Partial<ActionContext> = {}): ActionContext => ({token: t.current(), targetId: 'n1', targetVersion: 'v1', permissions: new Set(['canvas.read', 'task.run']), input: {a: 1}, ...extra});

describe('lifecycle epoch (§11.2)', () => {
  it('A→B→A produces a new epoch and invalidates the old confirmation', () => {
    const t = new LifecycleTracker(); t.update({projectId: 'A', jobId: 'j1'});
    const conf = bindConfirmation(t.current(), 'task.run', 'n1', 'v1', {a: 1});
    t.update({projectId: 'B', jobId: 'j1'}); t.update({projectId: 'A', jobId: 'j1'});
    expect(checkConfirmation(conf, t, 'task.run', 'n1', 'v1', {a: 1})).toEqual({ok: false, reason: 'lifecycle-changed'});
  });
  it('confirmation detects version/input/target changes; key order irrelevant', () => {
    const t = new LifecycleTracker(); t.update({projectId: 'A'});
    const c = bindConfirmation(t.current(), 'x', 'n1', 'v1', {a: 1, b: 2});
    expect(checkConfirmation(c, t, 'x', 'n1', 'v1', {b: 2, a: 1}).ok).toBe(true);
    expect(checkConfirmation(c, t, 'x', 'n1', 'v2', {a: 1, b: 2})).toMatchObject({reason: 'version-changed'});
    expect(checkConfirmation(c, t, 'x', 'n1', 'v1', {a: 9, b: 2})).toMatchObject({reason: 'input-changed'});
    expect(checkConfirmation(c, t, 'x', 'n2', 'v1', {a: 1, b: 2})).toMatchObject({reason: 'target-mismatch'});
  });
  it('late responses are dropped after context change', () => {
    const t = new LifecycleTracker(); t.update({projectId: 'A'}); const seen: number[] = [];
    const apply = guardLate<number>(t, t.current(), v => seen.push(v));
    t.update({projectId: 'B'}); expect(apply(1)).toBe(false); expect(seen).toEqual([]);
  });
});

describe('action registry (§7.2)', () => {
  it('re-checks lifecycle at execution and after await (late result → stale)', async () => {
    const t = new LifecycleTracker(); t.update({projectId: 'A'}); const r = new ActionRegistry(t);
    let release!: () => void; let calls = 0;
    r.register({id: 'task.run', label: 'run', surfaces: ['button'], run: () => { calls++; return new Promise(res => { release = () => res('ok'); }); }});
    const c = ctx(t); const p = r.execute('task.run', c);
    expect(await r.execute('task.run', c)).toEqual({status: 'duplicate'});
    t.update({projectId: 'B'}); release();
    expect(await p).toEqual({status: 'stale'}); expect(calls).toBe(1);
    expect(await r.execute('task.run', c)).toEqual({status: 'stale'});
  });
  it('permission + confirmation gates; shortcut path uses same execute', async () => {
    const t = new LifecycleTracker(); t.update({projectId: 'A'}); const r = new ActionRegistry(t); let n = 0;
    r.register({id: 'adopt', label: '采用结果', surfaces: ['button', 'shortcut'], permissions: ['review.adopt'], requiresConfirmation: true, run: async () => ++n});
    expect(await r.execute('adopt', ctx(t))).toMatchObject({status: 'blocked', reason: '缺少权限：review.adopt'});
    const c = ctx(t, {permissions: new Set(['review.adopt'])});
    expect(await r.execute('adopt', c)).toEqual({status: 'needs-confirmation'});
    const conf = bindConfirmation(c.token, 'adopt', 'n1', 'v1', {a: 1});
    expect(await r.execute('adopt', {...c, input: {a: 2}}, {confirmation: conf})).toMatchObject({status: 'blocked'});
    expect(await r.execute('adopt', c, {confirmation: conf})).toEqual({status: 'done', value: 1}); expect(n).toBe(1);
  });
  it('shortcuts are ignored during IME composition and in text inputs', () => {
    expect(shouldHandleShortcut({isComposing: true})).toBe(false);
    expect(shouldHandleShortcut({keyCode: 229})).toBe(false);
    expect(shouldHandleShortcut({target: {tagName: 'textarea'}})).toBe(false);
    expect(shouldHandleShortcut({target: {isContentEditable: true}})).toBe(false);
    expect(shouldHandleShortcut({target: {tagName: 'DIV'}})).toBe(true);
  });
});

describe('panels + layout (§7.1)', () => {
  it('bridges every existing FeatureLauncher id losslessly', async () => {
    const t = new LifecycleTracker(); const p = new PanelRegistry(); const a = new ActionRegistry(t); const opened: string[] = [];
    registerFeaturePanels(p, a, id => opened.push(id));
    const ids = FEATURE_GROUPS.flatMap(g => g.items.map(i => i.id));
    expect(p.list().map(d => d.id).sort()).toEqual([...ids].sort());
    expect(a.list('commandSearch', ctx(t)).length).toBe(ids.length);
    await a.execute('panel.open.history', ctx(t)); expect(opened).toEqual(['history']);
  });
  it('corrupt JSON / unknown schema recover to default; scopes isolated; reset only touches layout', () => {
    const p = new PanelRegistry(); p.register({id: 'history', kind: 'feature', title: 'h', capability: 'connected', instancing: 'singleton', docks: ['main', 'right'], defaultDock: 'main'});
    const st = new Mem(); st.setItem(layoutKey(scope), '{bad'); st.setItem('poemseed.draft.x', 'draft');
    expect(loadLayout(st, scope, p)).toMatchObject({recovered: true, layout: {placements: []}});
    st.setItem(layoutKey(scope), JSON.stringify({schemaVersion: 99})); expect(loadLayout(st, scope, p).recovered).toBe(true);
    saveLayout(st, scope, {schemaVersion: 2, mode: 'pro', maximized: 'history', placements: [{panelId: 'history', objectRef: null, dock: 'right', accessToken: 'SECRET', signedUrl: 'x'} as never]});
    expect(st.getItem(layoutKey(scope))).not.toMatch(/SECRET|signedUrl/);
    expect(loadLayout(st, scope, p).layout).toMatchObject({mode: 'pro', maximized: 'history', placements: [{panelId: 'history', dock: 'right'}]});
    expect(loadLayout(st, {...scope, projectInstanceId: 'i2'}, p).layout.placements).toEqual([]);
    resetLayout(st, scope); expect(st.getItem(layoutKey(scope))).toBeNull(); expect(st.getItem('poemseed.draft.x')).toBe('draft');
  });
  it('migrates v1, drops removed panels and deleted objects, collapses on narrow screens', () => {
    const p = new PanelRegistry(); p.register({id: 'history', kind: 'feature', title: 'h', capability: 'connected', instancing: 'singleton', docks: ['main', 'right'], defaultDock: 'main'});
    const st = new Mem(); st.setItem(layoutKey(scope), JSON.stringify({schemaVersion: 1, panels: [{id: 'history', zone: 'right'}, {id: 'gone', zone: 'left'}]}));
    const r = loadLayout(st, scope, p); expect(r.droppedPanels).toEqual(['gone']); expect(r.layout.placements[0].dock).toBe('right');
    expect(adaptToViewport(r.layout, 1024).placements[0].collapsed).toBe(true);
  });
});

describe('extension proof (§7.4)', () => {
  it('demo panel/action are hidden in production and work in dev with disabled reason + dispose', async () => {
    const t = new LifecycleTracker(); t.update({projectId: 'A'});
    const prodP = new PanelRegistry(false), prodA = new ActionRegistry(t, false); registerDemoExtension(prodP, prodA, []);
    expect(prodP.has(DEMO_PANEL_ID)).toBe(false); expect(prodA.list('contextMenu', ctx(t))).toEqual([]);
    const log: string[] = []; const p = new PanelRegistry(true), a = new ActionRegistry(t, true); const off = registerDemoExtension(p, a, log);
    expect(a.availability('dev.demo.inspect', ctx(t, {targetId: null}))).toEqual({enabled: false, reason: '请先选中一个节点'});
    expect(await a.execute('dev.demo.inspect', ctx(t))).toEqual({status: 'done', value: 'n1'});
    const key = p.instanceKey(DEMO_PANEL_ID, 'n1'); p.get(DEMO_PANEL_ID)!.onDispose!(key);
    expect(log).toEqual(['inspect:n1', 'dispose:dev.demo.extension#n1']); off(); expect(p.has(DEMO_PANEL_ID)).toBe(false);
  });
});

describe('novel action aliases (H-P0-01 / N-P0-02)', () => {
  it('registers novel aliases that open history/creation/story/check', async () => {
    const opened: string[] = [];
    const t = new LifecycleTracker(); t.update({projectId: 'p'});
    const p = new PanelRegistry(); const a = new ActionRegistry(t);
    const {registerNovelActionAliases, isNovelPanel} = await import('./novelActions');
    registerFeaturePanels(p, a, id => opened.push(id));
    const focused: string[] = [];
    registerNovelActionAliases(a, id => opened.push(id), tgt => focused.push(tgt));
    expect(isNovelPanel('history')).toBe(true);
    expect(isNovelPanel('diagnostics')).toBe(false);
    expect(isNovelPanel('write')).toBe(true);
    const c = ctx(t, {targetId: null, permissions: new Set()});
    expect(await a.execute('novel.open.revisionHistory', c)).toEqual({status: 'done', value: 'history'});
    expect(await a.execute('novel.open.creationWorkbench', c)).toEqual({status: 'done', value: 'creation'});
    expect(await a.execute('novel.open.continuityCheck', c)).toEqual({status: 'done', value: 'check'});
    expect(await a.execute('novel.open.aiWritingSurface', c)).toEqual({status: 'done', value: 'write'});
    expect(await a.execute('novel.open.writingShell', c)).toEqual({status: 'done', value: 'write'});
    expect(await a.execute('novel.open.storyPlanning', c)).toEqual({status: 'done', value: 'story'});
    expect(await a.execute('novel.open.pendingCanon', c)).toEqual({status: 'done', value: 'check'});
    expect(await a.execute('novel.open.workflowSurface', c)).toEqual({status: 'done', value: 'workflow'});
    expect(await a.execute('novel.focus.aiWriting', c)).toEqual({status: 'done', value: 'aiWriting'});
    expect(await a.execute('novel.focus.editor', c)).toEqual({status: 'done', value: 'editor'});
    expect(focused).toEqual(['aiWriting', 'editor']);
    expect(opened).toEqual(['history', 'creation', 'check', 'write', 'write', 'story', 'check', 'workflow', 'write', 'write']);
  });
});
