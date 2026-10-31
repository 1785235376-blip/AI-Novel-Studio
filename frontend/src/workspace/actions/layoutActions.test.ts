// [HERMIA-FE-20261023 M1-s2] layout actions on the existing workbench ActionRegistry.
import {describe, expect, it} from 'vitest';
import {ActionRegistry, type ActionContext} from '../../workbench/actions';
import {LifecycleTracker} from '../../workbench/lifecycle';
import {createDefaultLayout, layoutReducer, type LayoutAction, type LayoutState} from '../layout/model';
import {SPECS} from '../layout/testSpecs';
import {actionIdForKey, LAYOUT_ACTION_IDS, normalizeShortcut, registerLayoutActions, shortcutFromEvent, ShortcutTable} from './layoutActions';

const VP = {width: 1440, height: 900};
function rig(table = new ShortcutTable()) {
  const tracker = new LifecycleTracker(); const registry = new ActionRegistry(tracker);
  let state: LayoutState = createDefaultLayout(SPECS, VP); const r = layoutReducer({specs: SPECS, viewport: VP});
  const log: LayoutAction[] = []; let resetAsked = 0;
  const reg = registerLayoutActions(registry, table, {
    getState: () => state, specs: SPECS, dispatch: a => { log.push(a); state = r(state, a); }, requestReset: () => { resetAsked++; },
  });
  const ctx = (targetId: string | null = null, input?: unknown): ActionContext => ({token: tracker.current(), targetId, targetVersion: null, permissions: new Set(), input});
  return {tracker, registry, reg, ctx, log, table, get state() { return state; }, get resetAsked() { return resetAsked; }};
}

describe('stable ids + registration', () => {
  it('registers the four stable ids; duplicate registration is rejected by the existing registry', () => {
    const t = rig();
    for (const id of Object.values(LAYOUT_ACTION_IDS)) expect(t.registry.get(id)?.id).toBe(id);
    expect(() => registerLayoutActions(t.registry, new ShortcutTable(), {getState: () => t.state, specs: SPECS, dispatch: () => {}, requestReset: () => {}})).toThrow(/duplicate action id/);
  });
  it('dispose unregisters and releases shortcuts', () => {
    const t = rig(); t.reg.dispose();
    expect(t.registry.get(LAYOUT_ACTION_IDS.reset)).toBeUndefined();
    expect(t.table.lookup('Mod+Alt+0')).toBeUndefined();
  });
});

describe('availability / disabled reason / execution', () => {
  it('reopen disabled with a Chinese reason while nothing is closed, and execute is blocked', async () => {
    const t = rig();
    expect(t.registry.availability(LAYOUT_ACTION_IDS.reopen, t.ctx())).toEqual({enabled: false, reason: '没有已关闭的面板'});
    expect(await t.registry.execute(LAYOUT_ACTION_IDS.reopen, t.ctx('tasks', 'tasks'))).toEqual({status: 'blocked', reason: '没有已关闭的面板'});
    expect(t.log).toHaveLength(0);
  });
  it('reopen + collapse + split + reset outcomes', async () => {
    const t = rig();
    // close via dispatch-equivalent: use toggleCollapse target reason first
    expect(t.registry.availability(LAYOUT_ACTION_IDS.toggleCollapse, t.ctx())).toEqual({enabled: false, reason: '先点一下要折叠的面板'});
    expect((await t.registry.execute(LAYOUT_ACTION_IDS.toggleCollapse, t.ctx('tasks'))).status).toBe('done');
    expect(t.state.frames.tasks.collapsed).toBe(true);
    expect(await t.registry.execute(LAYOUT_ACTION_IDS.split, t.ctx(null, 'split-v'))).toEqual({status: 'done', value: 'split-v'});
    expect(t.state.split).toBe('split-v');
    expect((await t.registry.execute(LAYOUT_ACTION_IDS.split, t.ctx(null, 'bogus'))).status).toBe('blocked');
    expect(await t.registry.execute(LAYOUT_ACTION_IDS.split, t.ctx())).toEqual({status: 'done', value: 'single'}); // cycles
    expect((await t.registry.execute(LAYOUT_ACTION_IDS.reset, t.ctx())).status).toBe('done');
    expect(t.resetAsked).toBe(1);
    expect(t.log.some(a => a.type === 'reset')).toBe(false); // reset itself waits for the confirm dialog
  });
});

describe('reopen after close', () => {
  it('reopens the requested closed panel, blocks a non-closed one', async () => {
    const tracker = new LifecycleTracker(); const registry = new ActionRegistry(tracker);
    const r = layoutReducer({specs: SPECS, viewport: VP});
    let state = r(r(createDefaultLayout(SPECS, VP), {type: 'close', id: 'tasks'}), {type: 'close', id: 'outline'});
    registerLayoutActions(registry, new ShortcutTable(), {getState: () => state, specs: SPECS, dispatch: a => { state = r(state, a); }, requestReset: () => {}});
    const ctx = (input?: unknown): ActionContext => ({token: tracker.current(), targetId: (input as string) ?? null, targetVersion: null, permissions: new Set(), input});
    expect(await registry.execute(LAYOUT_ACTION_IDS.reopen, ctx('canvas'))).toEqual({status: 'blocked', reason: '这个面板没有关闭'});
    expect(await registry.execute(LAYOUT_ACTION_IDS.reopen, ctx('outline'))).toEqual({status: 'done', value: 'outline'});
    expect(state.frames.outline.open).toBe(true); expect(state.frames.tasks.open).toBe(false);
  });
});

describe('running state + double-trigger guard', () => {
  it('same-tick second trigger is a duplicate and has no side effect; pending clears after', async () => {
    const t = rig();
    const p1 = t.registry.execute(LAYOUT_ACTION_IDS.split, t.ctx(null, 'split-h'));
    expect(t.registry.isPending(LAYOUT_ACTION_IDS.split, null)).toBe(true);
    const p2 = t.registry.execute(LAYOUT_ACTION_IDS.split, t.ctx(null, 'split-v'));
    expect(await p2).toEqual({status: 'duplicate'});
    expect((await p1).status).toBe('done');
    expect(t.state.split).toBe('split-h');
    expect(t.registry.isPending(LAYOUT_ACTION_IDS.split, null)).toBe(false);
    expect(t.log.filter(a => a.type === 'split')).toHaveLength(1);
  });
  it('stale lifecycle token is not executed', async () => {
    const t = rig(); const old = t.ctx(null, 'split-h'); t.tracker.invalidate();
    expect(await t.registry.execute(LAYOUT_ACTION_IDS.split, old)).toEqual({status: 'stale'});
    expect(t.state.split).toBe('single');
  });
});

describe('shortcuts', () => {
  it('normalizes', () => {
    expect(normalizeShortcut('ctrl+alt+s')).toBe('Mod+Alt+S');
    expect(normalizeShortcut('Alt+Cmd+0')).toBe('Mod+Alt+0');
    expect(shortcutFromEvent({key: 'ß', code: 'KeyS', metaKey: true, altKey: true})).toBe('Mod+Alt+S');
    expect(shortcutFromEvent({key: 'Alt', altKey: true})).toBeNull();
  });
  it('conflict with a reserved / other owner is detected; action stays registered without a key', () => {
    const t = rig(new ShortcutTable({'Mod+K': 'command-search', 'Mod+Alt+C': 'other'}));
    expect(t.reg.conflicts).toEqual([{actionId: LAYOUT_ACTION_IDS.toggleCollapse, shortcut: 'Mod+Alt+C', conflictWith: 'other'}]);
    expect(t.registry.get(LAYOUT_ACTION_IDS.toggleCollapse)?.shortcut).toBeUndefined();
    expect(t.table.lookup('Mod+Alt+C')).toBe('other');
    const tbl = new ShortcutTable(); expect(tbl.claim('Mod+K', 'x')).toEqual({ok: false, conflictWith: 'command-search (ui/AppShell.tsx)'});
  });
  it('ignores editable targets and IME composition', () => {
    const t = rig(); const ids = Object.values(LAYOUT_ACTION_IDS);
    const ev = {key: 's', code: 'KeyS', ctrlKey: true, altKey: true};
    expect(actionIdForKey({...ev, target: {tagName: 'BODY'}}, t.table, ids)).toBe(LAYOUT_ACTION_IDS.split);
    expect(actionIdForKey({...ev, target: {tagName: 'TEXTAREA'}}, t.table, ids)).toBeNull();
    expect(actionIdForKey({...ev, target: {tagName: 'INPUT'}}, t.table, ids)).toBeNull();
    expect(actionIdForKey({...ev, target: {isContentEditable: true}}, t.table, ids)).toBeNull();
    expect(actionIdForKey({...ev, isComposing: true}, t.table, ids)).toBeNull();
    expect(actionIdForKey({key: 's', code: 'KeyS', target: {tagName: 'BODY'}}, t.table, ids)).toBeNull(); // no modifier
  });
});
