// [HERMIA-FE-20261024 VW-M1] adapter protocol tests (injected scope; these do not prove real-host cold restore).
import {describe, expect, it, vi} from 'vitest';
import {createViewPreferences, viewPrefsKey, type ViewPrefsHost} from './viewPreferences';

function mem(init: Record<string, string> = {}) {
  const m = new Map(Object.entries(init));
  const st = {getItem: vi.fn((k: string) => m.get(k) ?? null), setItem: vi.fn((k: string, v: string) => { m.set(k, v); }), removeItem: vi.fn((k: string) => { m.delete(k); })};
  return {st, m};
}
const A = {userId: 'u1', projectId: 'p-a', projectInstanceId: 'inst-1'};
const B = {userId: 'u1', projectId: 'p-b', projectInstanceId: 'inst-1'};
const host = (p: Partial<ViewPrefsHost>): ViewPrefsHost => ({scope: A, storage: null, isCurrent: () => true, persist: true, ...p});
const VP = {x: 10, y: -20, zoom: 1.5};

describe('[VW-M1] view preferences adapter', () => {
  it('no scope / placeholder scope / persist=false / no storage ⇒ session only, zero writes', () => {
    const {st} = mem();
    for (const h of [host({scope: null, storage: st}), host({scope: {userId: 'local', projectId: 'preview', projectInstanceId: 'preview'}, storage: st}),
      host({storage: st, persist: false}), host({storage: null})]) {
      const p = createViewPreferences(h);
      expect(p.status().mode).toBe('session');
      expect(p.setViewport('image', VP)).toBe(true);
      expect(p.getViewport('image')).toEqual(VP);
      expect(p.key).toBeNull();
    }
    expect(st.setItem).not.toHaveBeenCalled();
    expect(st.getItem).not.toHaveBeenCalled();
  });
  it('persists only whitelisted fields under its own key; cold reopen restores; A/B isolated', () => {
    const {st, m} = mem({other: 'keep', 'poemseed.workspace.layout.v3::u1::p-a::inst-1': 'LAYOUT'});
    const a = createViewPreferences(host({storage: st}));
    a.setViewport('image', {...VP, prompt: 'secret', nodes: [1]} as never);
    a.setViewport('video', {x: 1, y: 2, zoom: 0.5});
    const raw = m.get(viewPrefsKey(A))!;
    expect(JSON.parse(raw)).toEqual({version: 1, viewports: {image: VP, video: {x: 1, y: 2, zoom: 0.5}}, worksets: []});
    expect(raw).not.toContain('secret');
    expect(m.get('other')).toBe('keep'); expect(m.get('poemseed.workspace.layout.v3::u1::p-a::inst-1')).toBe('LAYOUT');
    const a2 = createViewPreferences(host({storage: st}));
    expect(a2.getViewport('image')).toEqual(VP); expect(a2.restoredFromStorage('image')).toBe(true);
    const b = createViewPreferences(host({scope: B, storage: st}));
    expect(b.getViewport('image')).toBeUndefined();
    const inst2 = createViewPreferences(host({scope: {...A, projectInstanceId: 'inst-2'}, storage: st}));
    expect(inst2.getViewport('image')).toBeUndefined();
  });
  it('rejects non-finite / out-of-range viewports and keeps the previous value', () => {
    const p = createViewPreferences(host({storage: mem().st}));
    p.setViewport('image', VP);
    for (const bad of [{x: NaN, y: 0, zoom: 1}, {x: 0, y: Infinity, zoom: 1}, {x: 0, y: 0, zoom: 0}, {x: 0, y: 0, zoom: 99}, {x: 2e6, y: 0, zoom: 1}])
      expect(p.setViewport('image', bad)).toBe(false);
    expect(p.getViewport('image')).toEqual(VP);
  });
  it('corrupt / future version: raw left byte-identical, adapter session-only (no overwrite)', () => {
    for (const raw of ['{not json', JSON.stringify({version: 9, viewports: {image: VP}}), JSON.stringify([1])]) {
      const {st, m} = mem({[viewPrefsKey(A)]: raw});
      const p = createViewPreferences(host({storage: st}));
      expect(p.status().mode).toBe('session');
      p.setViewport('image', {x: 0, y: 0, zoom: 1});
      expect(m.get(viewPrefsKey(A))).toBe(raw);
      expect(st.setItem).not.toHaveBeenCalled();
    }
  });
  it('read throws ⇒ session view, no write', () => {
    const st = {getItem: () => { throw new Error('denied'); }, setItem: vi.fn(), removeItem: vi.fn()};
    const p = createViewPreferences(host({storage: st}));
    expect(p.status()).toEqual({mode: 'session', reason: 'read-failed'});
    expect(p.setViewport('image', VP)).toBe(true); expect(p.getViewport('image')).toEqual(VP);
    expect(st.setItem).not.toHaveBeenCalled();
  });
  it('quota / write rejection keeps the session value and reports write-failed; later success recovers', () => {
    let fail = true;
    const {st, m} = mem();
    st.setItem.mockImplementation((k: string, v: string) => { if (fail) throw new DOMException('quota', 'QuotaExceededError'); m.set(k, v); });
    const p = createViewPreferences(host({storage: st}));
    p.setViewport('image', VP);
    expect(p.getViewport('image')).toEqual(VP);
    expect(p.status().reason).toBe('write-failed');
    fail = false; p.setViewport('image', {x: 1, y: 1, zoom: 1});
    expect(p.status()).toEqual({mode: 'persistent', reason: 'ok'});
    expect(JSON.parse(m.get(viewPrefsKey(A))!).viewports.image).toEqual({x: 1, y: 1, zoom: 1});
  });
  it('late callback after the lease moved writes nothing', () => {
    let cur = true;
    const {st} = mem();
    const p = createViewPreferences(host({storage: st, isCurrent: () => cur}));
    cur = false;
    expect(p.setViewport('image', VP)).toBe(false);
    expect(p.getViewport('image')).toBeUndefined();
    expect(st.setItem).not.toHaveBeenCalled();
  });
  it('resetViewport clears only that canvas preference', () => {
    const {st, m} = mem({keep: '1'});
    const p = createViewPreferences(host({storage: st}));
    p.setViewport('image', VP); p.setViewport('video', VP);
    p.resetViewport('image');
    expect(JSON.parse(m.get(viewPrefsKey(A))!).viewports).toEqual({video: VP});
    expect(m.get('keep')).toBe('1'); expect(st.removeItem).not.toHaveBeenCalled();
  });
});
describe('[VW-fix1 P3] placeholder scopes never touch storage', () => {
  it.each([['local', 'preview', 'preview'], ['', 'p', 'i'], ['u', 'preview', 'x'], ['anonymous', 'p', 'i'], ['u', 'p', 'unknown']])('%s/%s/%s', (userId, projectId, projectInstanceId) => {
    const {st} = mem();
    const p = createViewPreferences({scope: {userId, projectId, projectInstanceId}, storage: st, isCurrent: () => true, persist: true});
    p.setViewport('image', VP); p.setWorksets([]); p.resetViewport('image');
    expect(p.status().mode).toBe('session'); expect(p.key).toBeNull();
    expect(st.setItem).not.toHaveBeenCalled(); expect(st.getItem).not.toHaveBeenCalled(); expect(st.removeItem).not.toHaveBeenCalled();
  });
});
