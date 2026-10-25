// @vitest-environment jsdom
// [HERMIA-FE-20261025 U1fix] Vera MUST-FIX 1/2 + P2 (review of 8996f553). Repro-first: each case failed on 575501b9.
import {StrictMode, createElement, type ReactNode} from 'react';
import {describe, expect, it} from 'vitest';
import {renderHook, act} from '@testing-library/react';
import {createViewPreferences, viewPrefsKey} from './viewPreferences';
import {useViewPreferences} from './useViewPreferences';
import {resolveWorkspaceIdentity} from './scopeLease';
import {ActionRegistry} from '../../workbench/actions';
import {LifecycleTracker} from '../../workbench/lifecycle';
import {ShortcutTable} from '../actions/layoutActions';
import {registerViewActions, VIEW_ACTION_IDS} from '../actions/viewActions';
import type {ViewPrefs} from './viewPreferences';
import {createDefaultLayout} from '../layout/model';
import {SPECS, VP} from '../layout/testSpecs';

const A = {userId: 'u1', projectId: 'n1', projectInstanceId: 'ws1/s1/b1'};
const W1 = {id: 'w1', name: '工作W1', createdAt: 1, layout: '{}'};
const mem = (fail = false) => { const m = new Map<string, string>(); let failing = fail;
  return {m, setFail: (f: boolean) => { failing = f; }, st: {getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => { if (failing) throw new DOMException('quota', 'QuotaExceededError'); m.set(k, v); }, removeItem: (k: string) => { m.delete(k); }}}; };

describe('U1fix MUST-FIX 1: no lost update between consumers of the same scope key', () => {
  it('save workset (adapter X) → pan (adapter Y, same key) → cold reopen keeps the workset AND the viewport', () => {
    const {m, st} = mem();
    const x = createViewPreferences({scope: A, storage: st, persist: true, isCurrent: () => true});
    const y = createViewPreferences({scope: A, storage: st, persist: true, isCurrent: () => true});
    expect(x.setWorksets([W1])).toBe('saved');
    expect(y.setViewport('image', {x: -160, y: 70, zoom: 1})).toBe(true);
    const cold = createViewPreferences({scope: A, storage: st, persist: true, isCurrent: () => true});
    expect(cold.getWorksets().map(w => w.name)).toEqual(['工作W1']);
    expect(cold.getViewport('image')).toEqual({x: -160, y: 70, zoom: 1});
    expect(JSON.parse(m.get(viewPrefsKey(A))!).worksets).toHaveLength(1);
  });
});

describe('U1fix MUST-FIX 2: setWorksets outcome is distinguished', () => {
  it('session scope: kept in memory, outcome "session", zero writes', () => {
    const {m, st} = mem();
    const p = createViewPreferences({scope: null, storage: st, persist: false, isCurrent: () => true});
    expect(p.setWorksets([W1])).toBe('session'); expect(p.getWorksets()).toHaveLength(1); expect(m.size).toBe(0);
  });
  it('write failure (quota): kept in memory, outcome "write-failed"', () => {
    const {st} = mem(true);
    const p = createViewPreferences({scope: A, storage: st, persist: true, isCurrent: () => true});
    expect(p.setWorksets([W1])).toBe('write-failed'); expect(p.getWorksets()).toHaveLength(1);
  });
  it('[P2 mutation M7] not-current: discarded, memory unchanged, no write', () => {
    const {m, st} = mem();
    const p = createViewPreferences({scope: A, storage: st, persist: true, isCurrent: () => false});
    expect(p.setWorksets([W1])).toBe('not-current'); expect(p.getWorksets()).toEqual([]); expect(m.size).toBe(0);
    const s = createViewPreferences({scope: null, storage: st, persist: false, isCurrent: () => false});
    expect(s.setWorksets([W1])).toBe('not-current'); expect(s.getWorksets()).toEqual([]);
  });
  it('StrictMode (dev mount→unmount→mount) does not leave the hook with a retired lease', () => {
    const wrapper = ({children}: {children: ReactNode}) => createElement(StrictMode, null, children);
    const {result} = renderHook(() => useViewPreferences({scope: null, storage: null, persist: false, sessionKey: 'n1'}), {wrapper});
    let r: string | undefined; act(() => { r = result.current.setWorksets([W1]); });
    expect(r).toBe('session'); expect(result.current.getWorksets()).toHaveLength(1);
  });
  const run = async (prefs: ViewPrefs, layoutOk = true) => {
    const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker); const msgs: string[] = [];
    const state = createDefaultLayout(SPECS, VP);
    registerViewActions(reg, new ShortcutTable(), {layout: () => (layoutOk ? {getState: () => state} as never : null), prefs: () => prefs, focus: () => null, openViews: () => {}, onChange: s => msgs.push(s)});
    const res = await reg.execute(VIEW_ACTION_IDS.save, {token: tracker.current(), targetId: null, targetVersion: null, permissions: new Set<string>(), input: '写作'});
    return {res, msgs};
  };
  it('save action messages: session / write-failed / not-current', async () => {
    const s = await run(createViewPreferences({scope: null, storage: null, persist: false, isCurrent: () => true}));
    expect(s.res.status).toBe('done'); expect(s.msgs.at(-1)).toBe('已保存视图「写作」（仅本次会话有效，关闭页面后不保留）。');
    const {st} = mem(true);
    const f = await run(createViewPreferences({scope: A, storage: st, persist: true, isCurrent: () => true}));
    expect(f.res.status).toBe('done');
    expect(f.msgs.at(-1)).toBe('已保存视图「写作」，但没能写入本机存储（可能已满）：本次会话里仍可使用，关闭页面后不保留。可清理浏览器存储后再保存一次。');
    const n = await run(createViewPreferences({scope: A, storage: mem().st, persist: true, isCurrent: () => false}));
    expect(n.res.status).toBe('error'); expect(String((n.res as {error: Error}).error.message)).toBe('项目已经切换，这次修改已丢弃，没有保存。');
  });
});

describe('U1fix P2', () => {
  it('[mutation M5] newer-version data is rejected with reason future-version and bytes kept', () => {
    const {m, st} = mem(); const raw = JSON.stringify({version: 2, viewports: {image: {x: 1, y: 2, zoom: 1}}, worksets: [W1]});
    m.set(viewPrefsKey(A), raw);
    const p = createViewPreferences({scope: A, storage: st, persist: true, isCurrent: () => true});
    expect(p.status()).toEqual({mode: 'session', reason: 'future-version'});
    expect(p.getViewport('image')).toBeUndefined(); expect(p.getWorksets()).toEqual([]);
    p.setViewport('image', {x: 5, y: 5, zoom: 1}); expect(m.get(viewPrefsKey(A))).toBe(raw);
  });
  it('collabScope.projectId ≠ selected project ⇒ not a real identity (no mixed scope)', () => {
    const r = resolveWorkspaceIdentity({actorId: 'u1', collabScope: {workspaceId: 'ws1', projectId: 'n9', storylineId: 's1', branchId: 'b1'}, projectId: 'n1'});
    expect(r).toMatchObject({kind: 'session', reason: 'scope-mismatch'});
    expect(resolveWorkspaceIdentity({actorId: 'u1', collabScope: {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'}, projectId: 'n1'}).kind).toBe('real');
  });
});
