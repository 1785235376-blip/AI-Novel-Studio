// [HERMIA-FE-20261023 M1] Persistence / migration tests. Legacy inputs use the REAL formats written by
// src/workbench/layout.ts (saveLayout, schemaVersion 2 / migrate v1) and src/ui/AppShell.tsx (studio-inspector-*).
import {describe, expect, it} from 'vitest';
import {saveLayout, layoutKey} from '../../workbench/layout';
import {createDefaultLayout, layoutReducer} from './model';
import {
  loadWorkspaceLayout, saveWorkspaceLayout, serializeLayout, workspaceLayoutBackupKey, workspaceLayoutKey,
  legacyWorkbenchKeyV1, parseLayoutV3,
} from './persistence';
import {MemStorage, SCOPE, SPECS, VP} from './testSpecs';

describe('layout persistence v3', () => {
  it('M1-09 save → load round trip', () => {
    const st = new MemStorage(); const r = layoutReducer({specs: SPECS, viewport: VP});
    let s = r(createDefaultLayout(SPECS, VP), {type: 'dock', id: 'tasks', dock: 'right'});
    s = r(s, {type: 'resize', id: 'inspector', size: 400}); s = r(s, {type: 'split', mode: 'split-h'});
    expect(saveWorkspaceLayout(st, SCOPE, s)).toEqual({ok: true});
    const l = loadWorkspaceLayout(st, SCOPE, SPECS, VP);
    expect(l.source).toBe('v3'); expect(l.state.frames).toEqual(s.frames); expect(l.state.split).toBe('split-h');
  });
  it('M1-10 save failure returns status, state untouched', () => {
    const st = new MemStorage(); st.failSet = true;
    const res = saveWorkspaceLayout(st, SCOPE, createDefaultLayout(SPECS, VP));
    expect(res.ok).toBe(false);
  });
  it('M1-11 migrates real workbench v2 doc written by workbench/layout.ts saveLayout', () => {
    const st = new MemStorage();
    saveLayout(st, SCOPE, {schemaVersion: 2, mode: 'pro', maximized: null, placements: [
      {panelId: 'inspector', objectRef: null, dock: 'left', size: 300, collapsed: true},
      {panelId: 'tasks', objectRef: null, dock: 'right'},
    ]});
    const raw = st.getItem(layoutKey(SCOPE));
    const l = loadWorkspaceLayout(st, SCOPE, SPECS, VP);
    expect(l.source).toBe('migrated-workbench-v2');
    expect(l.state.frames.inspector).toMatchObject({dock: 'left', size: 300, collapsed: true});
    expect(l.state.frames.tasks.dock).toBe('right');
    expect(st.getItem(layoutKey(SCOPE))).toBe(raw); // legacy untouched
    expect(st.writes).toEqual([layoutKey(SCOPE)]);   // load wrote nothing
  });
  it('M1-11 migrates workbench v1 {panels:[{id,zone}]} and AppShell inspector keys', () => {
    const st = new MemStorage();
    st.setItem(legacyWorkbenchKeyV1(SCOPE), JSON.stringify({schemaVersion: 1, panels: [{id: 'outline', zone: 'right'}]}));
    expect(loadWorkspaceLayout(st, SCOPE, SPECS, VP).state.frames.outline.dock).toBe('right');
    const st2 = new MemStorage(); st2.setItem('studio-inspector-width', '420'); st2.setItem('studio-inspector-open', '0');
    const l = loadWorkspaceLayout(st2, SCOPE, SPECS, VP, {inspectorPanelId: 'inspector'});
    expect(l.source).toBe('migrated-inspector-keys');
    expect(l.state.frames.inspector).toMatchObject({dock: 'right', size: 420, collapsed: true});
  });
  it('M1-12 missing fields get safe defaults; extra fields kept', () => {
    const st = new MemStorage();
    st.setItem(workspaceLayoutKey(SCOPE), JSON.stringify({version: 3, panels: [{id: 'inspector'}], futureFlag: 7}));
    const l = loadWorkspaceLayout(st, SCOPE, SPECS, VP);
    expect(l.state.frames.inspector).toMatchObject({dock: 'right', size: 340, open: true, collapsed: false});
    expect(l.diagnostics.some(d => d.code === 'missing-panel-added' && d.panelId === 'canvas')).toBe(true);
    expect(parseLayoutV3(JSON.parse(st.getItem(workspaceLayoutKey(SCOPE))!), SPECS, VP).extra).toEqual({futureFlag: 7});
  });
  it('M1-13 unknown panel ids preserved and re-serialized', () => {
    const st = new MemStorage(); const ghost = {id: 'plugin.x', dock: 'left', size: 99, custom: {a: 1}};
    st.setItem(workspaceLayoutKey(SCOPE), JSON.stringify({version: 3, panels: [ghost]}));
    const l = loadWorkspaceLayout(st, SCOPE, SPECS, VP);
    expect(l.state.preserved['plugin.x']).toEqual(ghost);
    expect(JSON.parse(serializeLayout(l.state)).preserved['plugin.x']).toEqual(ghost);
  });
  it('M1-14 corrupt JSON → default + diagnostic; original kept, backup copied', () => {
    const st = new MemStorage(); st.setItem(workspaceLayoutKey(SCOPE), '{"version":3,"panels":[');
    const l = loadWorkspaceLayout(st, SCOPE, SPECS, VP);
    expect(l.source).toBe('fallback-corrupt'); expect(l.diagnostics[0].code).toBe('corrupt-json');
    expect(st.getItem(workspaceLayoutKey(SCOPE))).toBe('{"version":3,"panels":[');
    expect(st.getItem(workspaceLayoutBackupKey(SCOPE))).toBe('{"version":3,"panels":[');
    expect(l.state).toEqual(createDefaultLayout(SPECS, VP));
    for (const bad of ['null', '[]', '"x"', '{"version":99}']) {
      const s2 = new MemStorage(); s2.setItem(workspaceLayoutKey(SCOPE), bad);
      expect(loadWorkspaceLayout(s2, SCOPE, SPECS, VP).source).toBe('fallback-corrupt');
    }
  });
  it('M1-15 invalid size / dock fixed, valid parts kept', () => {
    const st = new MemStorage();
    st.setItem(workspaceLayoutKey(SCOPE), JSON.stringify({version: 3, split: 'split-v', panels: [
      {id: 'inspector', dock: 'nowhere', size: -5}, {id: 'outline', dock: 'right', size: 'big'}, {id: 'tasks', dock: 'left', size: 150},
      {id: 'canvas', dock: 'bottom'}]}));
    const l = loadWorkspaceLayout(st, SCOPE, SPECS, VP);
    expect(l.state.frames.inspector).toMatchObject({dock: 'right', size: 340});
    expect(l.state.frames.outline).toMatchObject({dock: 'right', size: 248});
    expect(l.state.frames.tasks).toMatchObject({dock: 'left', size: 150});
    expect(l.state.frames.canvas.dock).toBe('main');
    expect(l.state.split).toBe('split-v');
    expect(l.diagnostics.filter(d => d.code === 'invalid-dock').length).toBe(2);
  });
  it('M1-16 repeated migration is idempotent', () => {
    const st = new MemStorage();
    saveLayout(st, SCOPE, {schemaVersion: 2, mode: 'basic', maximized: null, placements: [
      {panelId: 'tasks', objectRef: null, dock: 'right', size: 260}, {panelId: 'tasks', objectRef: 'x', dock: 'left'}]});
    const a = loadWorkspaceLayout(st, SCOPE, SPECS, VP).state;
    st.setItem(workspaceLayoutKey(SCOPE), serializeLayout(a));
    const b = loadWorkspaceLayout(st, SCOPE, SPECS, VP).state;
    st.setItem(workspaceLayoutKey(SCOPE), serializeLayout(b));
    const c = loadWorkspaceLayout(st, SCOPE, SPECS, VP).state;
    expect(serializeLayout(b)).toBe(serializeLayout(a)); expect(serializeLayout(c)).toBe(serializeLayout(a));
    expect(a.frames.tasks).toMatchObject({dock: 'right', size: 260});
  });
  it('M1-17 migration throwing leaves raw data intact and writes nothing', () => {
    const st = new MemStorage(); st.setItem(layoutKey(SCOPE), '{"schemaVersion":2,"placements":[]}'); st.writes = [];
    const l = loadWorkspaceLayout(st, SCOPE, SPECS, VP, {migrate: () => { throw new Error('boom mid-migration'); }});
    expect(l.source).toBe('fallback-corrupt'); expect(l.diagnostics.some(d => d.code === 'migration-failed')).toBe(true);
    expect(st.getItem(layoutKey(SCOPE))).toBe('{"schemaVersion":2,"placements":[]}');
    expect(st.writes).toEqual([]);
  });
  it('M1-18 reset only affects the layout key, other storage untouched', () => {
    const st = new MemStorage(); st.setItem('draft:chapter1', 'my words'); st.setItem('studio-inspector-width', '400');
    const r = layoutReducer({specs: SPECS, viewport: VP});
    const s = r(r(createDefaultLayout(SPECS, VP), {type: 'close', id: 'tasks'}), {type: 'reset'});
    saveWorkspaceLayout(st, SCOPE, s);
    expect(st.getItem('draft:chapter1')).toBe('my words'); expect(st.getItem('studio-inspector-width')).toBe('400');
    expect(loadWorkspaceLayout(st, SCOPE, SPECS, VP).state.frames).toEqual(createDefaultLayout(SPECS, VP).frames);
  });
  it('scopes are isolated per project', () => {
    const st = new MemStorage(); const r = layoutReducer({specs: SPECS, viewport: VP});
    saveWorkspaceLayout(st, SCOPE, r(createDefaultLayout(SPECS, VP), {type: 'close', id: 'tasks'}));
    expect(loadWorkspaceLayout(st, {...SCOPE, projectId: 'p2'}, SPECS, VP).state.frames.tasks.open).toBe(true);
  });
});
