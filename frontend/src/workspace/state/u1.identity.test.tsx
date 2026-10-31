// @vitest-environment jsdom
// [HERMIA-FE-20261025 U1-M1/M2] identity, lease retirement (ABA, delete→recreate), cold reopen restore.
import {describe, expect, it, vi} from 'vitest';
import {renderHook} from '@testing-library/react';
import {createScopeLease, LeaseHolder, resolveWorkspaceIdentity} from './scopeLease';
import {createViewPreferences, viewPrefsKey} from './viewPreferences';
import {useViewPreferences} from './useViewPreferences';

const collab = {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'};
const mem = () => { const m = new Map<string, string>(); const writes: string[] = [];
  return {m, writes, st: {getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => { writes.push(k); m.set(k, v); }, removeItem: (k: string) => { m.delete(k); }}}; };

describe('U1-M1 identity', () => {
  it('never fabricates a user id: missing/placeholder actor ⇒ session-only', () => {
    for (const actorId of [undefined, null, '', '  ', 'local-author', 'local', 'anonymous']) {
      const r = resolveWorkspaceIdentity({actorId, collabScope: collab, projectId: 'n1'});
      expect(r.kind).toBe('session');
      expect(r).toMatchObject({reason: 'no-actor'});
    }
  });
  it('incomplete collaboration scope ⇒ session-only (no-instance); no project ⇒ no-project', () => {
    expect(resolveWorkspaceIdentity({actorId: 'u1', collabScope: {workspaceId: 'ws1'}, projectId: 'n1'})).toMatchObject({kind: 'session', reason: 'no-instance'});
    expect(resolveWorkspaceIdentity({actorId: 'u1', collabScope: collab, projectId: null})).toMatchObject({kind: 'session', reason: 'no-project'});
  });
  it('real identity scope uses the bootstrap actor + server project id + workspace/storyline/branch', () => {
    const r = resolveWorkspaceIdentity({actorId: 'u1', collabScope: collab, projectId: 'n1', clientId: 'c1'});
    expect(r.kind).toBe('real');
    if (r.kind === 'real') expect(r.scope).toEqual({userId: 'u1', projectId: 'n1', projectInstanceId: 'ws1/s1/b1'});
  });
  it('account / client switch changes the lease key', () => {
    const a = resolveWorkspaceIdentity({actorId: 'u1', collabScope: collab, projectId: 'n1', clientId: 'c1'}).key;
    expect(resolveWorkspaceIdentity({actorId: 'u2', collabScope: collab, projectId: 'n1', clientId: 'c1'}).key).not.toBe(a);
    expect(resolveWorkspaceIdentity({actorId: 'u1', collabScope: collab, projectId: 'n1', clientId: 'c2'}).key).not.toBe(a);
  });
});

describe('U1-M1 lease retirement', () => {
  it('A→B→A: first A lease stays retired; its guarded callback, deferred save and signal are dead', () => {
    vi.useFakeTimers();
    try {
      const h = new LeaseHolder();
      const a1 = h.current('A'); const late = vi.fn(); const deferred = vi.fn();
      const cb = a1.guard(late); a1.defer(100, deferred);
      h.current('B'); const a2 = h.current('A');
      expect(a2).not.toBe(a1); expect(a2.epoch).toBeGreaterThan(a1.epoch);
      expect(a1.isCurrent()).toBe(false); expect(a1.signal.aborted).toBe(true);
      cb('late'); vi.advanceTimersByTime(200);
      expect(late).not.toHaveBeenCalled(); expect(deferred).not.toHaveBeenCalled();
      expect(a2.isCurrent()).toBe(true);
    } finally { vi.useRealTimers(); }
  });
  it('invalidate (permission revoked / logout) retires without a successor', () => {
    const h = new LeaseHolder(); const l = h.current('A'); h.invalidate();
    expect(l.isCurrent()).toBe(false); expect(h.current('A')).not.toBe(l);
  });
  it('retired lease refuses new deferred work', () => {
    vi.useFakeTimers();
    try { const l = createScopeLease('X'); l.retire(); const f = vi.fn(); l.defer(1, f); vi.advanceTimersByTime(5); expect(f).not.toHaveBeenCalled(); }
    finally { vi.useRealTimers(); }
  });
});

describe('U1-M1 hook: ABA late callback (counterexample repro)', () => {
  it('a late viewport callback from the FIRST activation of A is dropped after A→B→A', () => {
    const {result, rerender} = renderHook((p: {k: string}) => useViewPreferences({scope: null, storage: null, persist: false, sessionKey: p.k}), {initialProps: {k: 'A'}});
    const firstA = result.current;
    firstA.setViewport('image', {x: 10, y: 10, zoom: 1});
    rerender({k: 'B'}); rerender({k: 'A'});
    const secondA = result.current;
    // session value carried over A→B→A
    expect(secondA.getViewport('image')).toEqual({x: 10, y: 10, zoom: 1});
    // late callback bound to the first A adapter must not land
    expect(firstA.setViewport('image', {x: 999, y: 999, zoom: 2})).toBe(false);
    expect(secondA.getViewport('image')).toEqual({x: 10, y: 10, zoom: 1});
  });
});

describe('U1-M2 cold reopen / isolation / migration / corruption / failure / reset', () => {
  const A = {userId: 'u1', projectId: 'n1', projectInstanceId: 'ws1/s1/b1'};
  const host = (o: Partial<Parameters<typeof createViewPreferences>[0]> = {}) => ({scope: A, storage: null, isCurrent: () => true, persist: true, ...o});
  it('cold reopen restores viewports + worksets from storage', () => {
    const {st} = mem();
    const p = createViewPreferences(host({storage: st}));
    p.setViewport('image', {x: 1, y: 2, zoom: 1.5});
    p.setWorksets([{id: 'w1', name: '写作', createdAt: 1, layout: '{}'}]);
    const reopened = createViewPreferences(host({storage: st}));
    expect(reopened.origin).toBe('storage');
    expect(reopened.getViewport('image')).toEqual({x: 1, y: 2, zoom: 1.5});
    expect(reopened.getWorksets().map(w => w.name)).toEqual(['写作']);
    expect(reopened.restoredFromStorage('image')).toBe(true);
  });
  it('identity isolation: another user, same project ⇒ nothing restored', () => {
    const {st} = mem();
    createViewPreferences(host({storage: st})).setViewport('image', {x: 1, y: 2, zoom: 1});
    expect(createViewPreferences(host({storage: st, scope: {...A, userId: 'u2'}})).getViewport('image')).toBeUndefined();
  });
  it('delete → recreate with the same name: new server id ⇒ old prefs do not resurrect', () => {
    const {st} = mem();
    createViewPreferences(host({storage: st})).setViewport('image', {x: 5, y: 5, zoom: 1});
    const recreated = createViewPreferences(host({storage: st, scope: {...A, projectId: 'n1-new-id'}}));
    expect(recreated.getViewport('image')).toBeUndefined();
    expect(recreated.origin).toBe('default');
  });
  it('v0 (unversioned) doc is migrated on read; bytes unchanged until a user change', () => {
    const {st, m, writes} = mem();
    const raw = JSON.stringify({viewports: {image: {x: 3, y: 4, zoom: 1}}, worksets: []});
    m.set(viewPrefsKey(A), raw);
    const p = createViewPreferences(host({storage: st}));
    expect(p.origin).toBe('migrated'); expect(p.getViewport('image')).toEqual({x: 3, y: 4, zoom: 1});
    expect(writes).toEqual([]); expect(m.get(viewPrefsKey(A))).toBe(raw);
    p.setViewport('video', {x: 0, y: 0, zoom: 1});
    expect(JSON.parse(m.get(viewPrefsKey(A))!).version).toBe(1);
  });
  it('corrupt data: session-only, original bytes kept, reset does not delete it', () => {
    const {st, m} = mem(); m.set(viewPrefsKey(A), '{not json');
    const p = createViewPreferences(host({storage: st}));
    expect(p.status()).toEqual({mode: 'session', reason: 'corrupt'});
    expect(p.setViewport('image', {x: 1, y: 1, zoom: 1})).toBe(true);
    expect(m.get(viewPrefsKey(A))).toBe('{not json');
    expect(p.resetAll()).toBe(true); expect(m.get(viewPrefsKey(A))).toBe('{not json'); expect(p.getViewport('image')).toBeUndefined();
  });
  it('storage write failure keeps the session value and reports write-failed', () => {
    const st = {getItem: () => null, setItem: () => { throw new Error('quota'); }, removeItem: () => {}};
    const p = createViewPreferences(host({storage: st}));
    expect(p.setViewport('image', {x: 1, y: 1, zoom: 1})).toBe(true);
    expect(p.status().reason).toBe('write-failed'); expect(p.getViewport('image')).toEqual({x: 1, y: 1, zoom: 1});
  });
  it('reset default removes only this scope key', () => {
    const {st, m} = mem(); m.set('other', 'x');
    const p = createViewPreferences(host({storage: st})); p.setViewport('image', {x: 1, y: 1, zoom: 1});
    expect(p.resetAll()).toBe(true);
    expect(m.has(viewPrefsKey(A))).toBe(false); expect(m.get('other')).toBe('x');
    expect(createViewPreferences(host({storage: st})).origin).toBe('default');
  });
  it('stores UI geometry only: no token / prompt / task fields survive a write', () => {
    const {st, m} = mem();
    const p = createViewPreferences(host({storage: st}));
    p.setWorksets([{id: 'w', name: 'n', createdAt: 1, layout: '{}', token: 'SECRET', prompt: 'p'} as never]);
    const txt = m.get(viewPrefsKey(A))!;
    expect(txt).not.toContain('SECRET'); expect(txt).not.toContain('prompt');
  });
});
