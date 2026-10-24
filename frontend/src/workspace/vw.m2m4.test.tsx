// @vitest-environment jsdom
// [HERMIA-FE-20261024 VW-M2/M3/M4] worksets, DockLayout consumer API, registry actions, panel focus, views dialog.
// jsdom component/protocol tests only — NOT a real-browser run.
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {useEffect, useState} from 'react';
import {DockLayout, type DockLayoutApi, type PanelRenderApi} from './layout/DockLayout';
import {MemStorage, SCOPE, SPECS, VP} from './layout/testSpecs';
import {captureWorkset, deleteWorkset, renameWorkset, resolveWorkset, validateWorksetName, WORKSET_LIMIT} from './layout/worksets';
import {createDefaultLayout, layoutReducer} from './layout/model';
import {ActionRegistry} from '../workbench/actions';
import {LifecycleTracker} from '../workbench/lifecycle';
import {ShortcutTable, registerLayoutActions} from './actions/layoutActions';
import {registerStudioPreviewActions} from './panels/studioPreviewPanels';
import {registerViewActions, VIEW_ACTION_IDS, VIEW_SHORTCUTS} from './actions/viewActions';
import {createViewPreferences} from './state/viewPreferences';
import {createPanelFocusTracker} from './state/panelFocus';
import {WorkspaceViewsPanel} from './panels/WorkspaceViewsPanel';

afterEach(cleanup);
const env = {specs: SPECS, viewport: VP};

describe('[VW-M2] workset model', () => {
  const st = createDefaultLayout(SPECS, VP);
  it('validates names (empty, too long, duplicate case-insensitive) and the count limit', () => {
    expect(validateWorksetName('  ', []).ok).toBe(false);
    expect(validateWorksetName('x'.repeat(41), []).ok).toBe(false);
    const one = captureWorkset(st, '写作', []); if (!one.ok) throw 0;
    expect(captureWorkset(st, ' 写作 ', one.value).ok).toBe(false);
    let list = one.value;
    for (let i = 1; i < WORKSET_LIMIT; i++) { const r = captureWorkset(st, `v${i}`, list); if (!r.ok) throw r.reason; list = r.value; }
    const over = captureWorkset(st, 'more', list); expect(over.ok).toBe(false);
  });
  it('stores geometry only and round-trips through the original v3 codec; rename/delete', () => {
    const moved = layoutReducer(env)(st, {type: 'dock', id: SPECS[0].id, dock: 'float'});
    const r = captureWorkset({...moved, focusId: SPECS[0].id}, 'A', []); if (!r.ok) throw 0;
    expect(JSON.parse(r.value[0].layout).focusId ?? null).toBeNull();
    const back = resolveWorkset(r.value[0], SPECS, VP, st); if (!back.ok) throw 0;
    expect(back.value.frames[SPECS[0].id].dock).toBe('float');
    const rn = renameWorkset(r.value, r.value[0].id, 'B'); expect(rn.ok && rn.value[0].name).toBe('B');
    expect(deleteWorkset(r.value, 'nope').ok).toBe(false);
    expect(resolveWorkset({...r.value[0], layout: '{bad'}, SPECS, VP, st).ok).toBe(false);
  });
});

function Editor({api}: {api: PanelRenderApi}) {
  const [t, setT] = useState('');
  useEffect(() => api.registerDirty({isDirty: () => t !== '', save: async () => {}, discard: () => setT('')}), [api, t]);
  return <textarea aria-label="草稿" value={t} onChange={e => setT(e.target.value)} />;
}
function mount() {
  let api: DockLayoutApi | null = null;
  const editorId = SPECS.find(s => s.defaultDock !== 'main')!.id;
  const u = render(<DockLayout specs={SPECS} scope={SCOPE} storage={new MemStorage()} viewport={VP} onLayoutApi={a => { api = a; }}
    renderPanel={(id, a) => id === editorId ? <Editor api={a} /> : <p>{id}</p>} />);
  return {...u, api: () => api!, editorId};
}

describe('[VW-M2] DockLayout consumer API', () => {
  it('apply replaces layout via reducer; blocked with no change when it would close a dirty panel', () => {
    const {api, editorId} = mount();
    const closed = layoutReducer(env)(api().getState(), {type: 'close', id: editorId});
    fireEvent.change(screen.getByLabelText('草稿'), {target: {value: 'x'}});
    const before = JSON.stringify(api().getState());
    let r!: ReturnType<DockLayoutApi['apply']>; act(() => { r = api().apply(closed); });
    expect(r.ok).toBe(false); expect(!r.ok && r.reason).toMatch(/未保存/);
    expect(JSON.stringify(api().getState())).toBe(before);
    expect(screen.getByLabelText('草稿')).toHaveProperty('value', 'x');
    fireEvent.change(screen.getByLabelText('草稿'), {target: {value: ''}});
    act(() => { r = api().apply(closed); });
    expect(r.ok).toBe(true); expect(api().getState().frames[editorId].open).toBe(false);
  });
  it('api is withdrawn on unmount', () => {
    let api: DockLayoutApi | null = null;
    const u = render(<DockLayout specs={SPECS} scope={SCOPE} storage={new MemStorage()} viewport={VP} onLayoutApi={a => { api = a; }} renderPanel={id => <p>{id}</p>} />);
    expect(api).not.toBeNull(); u.unmount(); expect(api).toBeNull();
  });
});

function setupActions() {
  const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker); const table = new ShortcutTable();
  const prefs = createViewPreferences({scope: null, storage: null, isCurrent: () => true, persist: false});
  const msgs: string[] = [];
  const m = mount();
  const ctx = (input?: unknown) => ({token: tracker.current(), targetId: null, targetVersion: null, permissions: new Set<string>(), input});
  const r = registerViewActions(reg, table, {layout: () => m.api(), prefs: () => prefs, focus: () => null, openViews: () => {}, onChange: s => msgs.push(s)});
  return {reg, table, prefs, msgs, m, ctx, r};
}

describe('[VW-M2] registry actions', () => {
  it('save → change → apply restores; session wording; rename/delete', async () => {
    const {reg, prefs, msgs, m, ctx} = setupActions();
    expect((await reg.execute(VIEW_ACTION_IDS.save, ctx('写作'))).status).toBe('done');
    expect(msgs.at(-1)).toMatch(/仅本次会话/);
    const id = prefs.getWorksets()[0].id; const saved = JSON.stringify(m.api().getState().frames);
    act(() => { m.api().apply(layoutReducer(env)(m.api().getState(), {type: 'dock', id: m.editorId, dock: 'float'})); });
    expect(JSON.stringify(m.api().getState().frames)).not.toBe(saved);
    let res; await act(async () => { res = await reg.execute(VIEW_ACTION_IDS.apply, ctx(id)); });
    expect(res).toMatchObject({status: 'done'});
    expect(m.api().getState().frames[m.editorId].dock).toBe(JSON.parse(saved)[m.editorId].dock);
    expect((await reg.execute(VIEW_ACTION_IDS.save, ctx('写作'))).status).toBe('error');
    expect((await reg.execute(VIEW_ACTION_IDS.rename, ctx({id, name: '审稿'}))).status).toBe('done');
    expect(prefs.getWorksets()[0].name).toBe('审稿');
    expect((await reg.execute(VIEW_ACTION_IDS.remove, ctx(id))).status).toBe('done');
    expect(prefs.getWorksets()).toEqual([]);
    expect((await reg.execute(VIEW_ACTION_IDS.apply, ctx(id))).status).toBe('error');
  });
  it('shortcuts claim without conflicts alongside layout + studio actions and reserved Mod+K', () => {
    const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker); const table = new ShortcutTable();
    const host = {getState: () => createDefaultLayout(SPECS, VP), specs: SPECS, dispatch: () => {}, requestReset: () => {}};
    const l = registerLayoutActions(reg, table, host as never);
    const s = registerStudioPreviewActions(reg, table, {getNovelId: () => null, getSelectedNode: () => null, onLinked: () => {}, showPanel: async () => null});
    const v = registerViewActions(reg, table, {layout: () => null, prefs: () => createViewPreferences({scope: null, storage: null, isCurrent: () => true, persist: false}), focus: () => null, openViews: () => {}, onChange: () => {}});
    expect(v.conflicts).toEqual([]); expect(s.conflicts).toEqual([]);
    expect((l as {conflicts?: unknown[]}).conflicts ?? []).toEqual([]);
    for (const [id, sc] of Object.entries(VIEW_SHORTCUTS)) expect(table.lookup(sc!)).toBe(id);
  });
  it('without layout the actions are disabled with a reason', async () => {
    const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker);
    registerViewActions(reg, new ShortcutTable(), {layout: () => null, prefs: () => createViewPreferences({scope: null, storage: null, isCurrent: () => true, persist: false}), focus: () => null, openViews: () => {}, onChange: () => {}});
    const r = await reg.execute(VIEW_ACTION_IDS.nextPanel, {token: tracker.current(), targetId: null, targetVersion: null, permissions: new Set()});
    expect(r).toEqual({status: 'blocked', reason: '布局还没有准备好'});
  });
});

describe('[VW-M4] panel focus', () => {
  it('next/prev cycles rendered panel regions; returnToLast goes back; hidden panel explained', () => {
    const {container} = render(<div>{['a', 'b', 'c'].map(id => <section key={id} role="region" aria-label={id} tabIndex={-1} data-panel-id={id}><button>{id}-btn</button></section>)}</div>);
    const t = createPanelFocusTracker(() => container, id => `面板${id}`);
    expect(t.next(1)).toEqual({ok: true, id: 'a'});
    expect(t.next(1)).toEqual({ok: true, id: 'b'});
    expect(t.next(-1)).toEqual({ok: true, id: 'a'});
    expect(t.next(-1)).toEqual({ok: true, id: 'c'});
    expect(t.returnToLast()).toEqual({ok: true, id: 'a'});
    screen.getByText('b-btn').focus(); // focus inside a panel counts
    expect(t.current()).toBe('b');
    container.querySelector('[data-panel-id="a"]')!.remove();
    const r = t.returnToLast(); expect(r.ok).toBe(false); expect(!r.ok && r.reason).toMatch(/面板a.*没有显示/);
    t.dispose();
  });
});

describe('[VW-M2] views dialog', () => {
  it('session mode is labelled, save goes through the registry, Escape closes', async () => {
    const {reg, prefs, ctx} = setupActions();
    let closed = false;
    render(<WorkspaceViewsPanel prefs={prefs} actions={reg} ctx={ctx} onClose={() => { closed = true; }} />);
    expect(screen.getByTestId('uw-views-mode').textContent).toMatch(/仅本次会话/);
    expect(screen.getByRole('button', {name: '保存到本次会话'})).toBeTruthy();
    expect(screen.queryByRole('button', {name: '保存当前布局'})).toBeNull();
    fireEvent.change(screen.getByLabelText('视图名称'), {target: {value: '写作'}});
    fireEvent.click(screen.getByRole('button', {name: '保存到本次会话'}));
    await waitFor(() => expect(screen.getByRole('button', {name: '应用视图「写作」'})).toBeTruthy());
    fireEvent.click(screen.getByRole('button', {name: '删除视图「写作」'}));
    expect(screen.getByText(/确定删除「写作」/)).toBeTruthy();
    fireEvent.keyDown(screen.getByTestId('uw-views'), {key: 'Escape'});
    expect(closed).toBe(true);
    expect(document.body.textContent).not.toMatch(/ws-[a-z0-9]+-/);
  });
});
