// [HERMIA-FE-20261025 U1-M2 INT] delete → recreate (even with a REUSED server id) must not resurrect old geometry.
import {describe, expect, it} from 'vitest';
import {createViewPreferences, viewPrefsKey} from './viewPreferences';
import {workspaceLayoutBackupKey, workspaceLayoutKey} from '../layout/persistence';
import {ProjectPresence, purgeProjectGeometry} from './projectPurge';

function store() { const m = new Map<string, string>();
  return {m, s: {get length() { return m.size; }, key: (i: number) => [...m.keys()][i] ?? null, getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => { m.set(k, v); }, removeItem: (k: string) => { m.delete(k); }}}; }
const A = {userId: 'u1', projectId: 'n1', projectInstanceId: 'ws1/s1/b1'};

describe('no resurrection after project disappearance', () => {
  it('counterexample: without purge, a reused id resurrects old prefs', () => {
    const {s} = store();
    createViewPreferences({scope: A, storage: s, isCurrent: () => true, persist: true}).setViewport('image', {x: 9, y: 9, zoom: 1});
    // project deleted, server recreates with the same id: old data comes back
    expect(createViewPreferences({scope: A, storage: s, isCurrent: () => true, persist: true}).getViewport('image')).toEqual({x: 9, y: 9, zoom: 1});
  });
  it('purge on disappearance removes only own keys of that project', () => {
    const {m, s} = store();
    createViewPreferences({scope: A, storage: s, isCurrent: () => true, persist: true}).setViewport('image', {x: 9, y: 9, zoom: 1});
    m.set(workspaceLayoutKey(A), '{}'); m.set(workspaceLayoutBackupKey(A), '{}');
    const other = {...A, userId: 'u2'}; m.set(viewPrefsKey(other), '{"version":1}');
    const n2 = {...A, projectId: 'n2'}; m.set(viewPrefsKey(n2), '{"version":1}');
    m.set('poemseed.rebuild.canvas.image.n1', '{"nodes":[]}');
    const pres = new ProjectPresence('u1');
    expect(pres.observe(['n1', 'n2'])).toEqual([]);
    expect(pres.observe(['n2'])).toEqual([]); // [HERMIA-FE-20261025 M10-purgeguard] missing once = pending only
    const gone = pres.observe(['n2']); expect(gone).toEqual(['n1']);
    expect(purgeProjectGeometry(s, 'u1', 'n1').sort()).toEqual([viewPrefsKey(A), workspaceLayoutKey(A), workspaceLayoutBackupKey(A)].sort());
    expect(m.has(viewPrefsKey(other))).toBe(true); expect(m.has(viewPrefsKey(n2))).toBe(true); expect(m.has('poemseed.rebuild.canvas.image.n1')).toBe(true);
    // recreated with the same id ⇒ default
    expect(createViewPreferences({scope: A, storage: s, isCurrent: () => true, persist: true}).origin).toBe('default');
  });
  it('[M10-purgeguard] empty list never purges, keeps seen, resets pending; reappearing project is not purged', () => {
    const p = new ProjectPresence('u1');
    expect(p.observe(['a', 'b', 'c'])).toEqual([]);
    expect(p.observe(['a', 'c'])).toEqual([]);
    expect(p.observe([])).toEqual([]);
    expect(p.observe(['a', 'c'])).toEqual([]);
    expect(p.observe(['a', 'b', 'c'])).toEqual([]);
    expect(p.observe(['a'])).toEqual([]);
    expect(p.observe(['a'])).toEqual(['b', 'c']);
  });
  it('first observation never purges; storage throwing ⇒ no-op', () => {
    expect(new ProjectPresence('u1').observe([])).toEqual([]);
    expect(purgeProjectGeometry({get length(): number { throw new Error('x'); }, key: () => null, removeItem: () => {}}, 'u1', 'n1')).toEqual([]);
  });
});
