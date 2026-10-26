// @vitest-environment jsdom
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {renderHook} from '@testing-library/react';
import {useLastChapter} from './useLastChapter';
import {__resetLastPositionSession} from './lastPosition';

const scope = {workspaceId: 'w', projectId: 'p1', storylineId: 's', branchId: 'b'};
const rows = [{id: 'c1'}, {id: 'c2'}];
describe('useLastChapter (default UI wiring)', () => {
  beforeEach(() => { __resetLastPositionSession(); localStorage.clear(); });
  it('reopen with real identity selects the remembered chapter instead of the first', () => {
    const setChapter = vi.fn();
    const a = renderHook(p => useLastChapter(p), {initialProps: {actorId: 'u1', scope, novelId: 'p1', chapterId: 'c2', rows, setChapter}});
    a.unmount(); __resetLastPositionSession();
    renderHook(() => useLastChapter({actorId: 'u1', scope, novelId: 'p1', chapterId: '', rows, setChapter}));
    expect(setChapter).toHaveBeenCalledWith('c2');
  });
  it('no identity ⇒ session only, first chapter after reload, nothing written', () => {
    const setChapter = vi.fn();
    renderHook(() => useLastChapter({actorId: undefined, scope: undefined, novelId: 'p1', chapterId: 'c2', rows, setChapter}));
    expect(localStorage.length).toBe(0); __resetLastPositionSession();
    const r = renderHook(() => useLastChapter({actorId: undefined, scope: undefined, novelId: 'p1', chapterId: '', rows, setChapter}));
    expect(setChapter).toHaveBeenLastCalledWith('c1');
    expect(r.result.current).toBe('session');
  });
  it('does nothing until chapters are loaded', () => {
    const setChapter = vi.fn();
    renderHook(() => useLastChapter({actorId: 'u1', scope, novelId: 'p1', chapterId: '', rows: undefined, setChapter}));
    expect(setChapter).not.toHaveBeenCalled();
  });
  it('P0 race: identity arriving late (2.5s) neither picks by session memory nor writes the real key', async () => {
    vi.useFakeTimers();
    try {
      localStorage.setItem('poemseed.default.lastpos.v1::u1::p1::w%2Fs%2Fb', JSON.stringify({v: 1, chapterId: 'c2'}));
      let chapterId = ''; const setChapter = vi.fn((id: string) => { chapterId = id; });
      const rows3 = [{id: 'c1'}, {id: 'c2'}, {id: 'c3'}];
      const props = () => ({actorId: late ? 'u1' : undefined, scope, novelId: 'p1', chapterId, rows: rows3, setChapter, identityPending: !late});
      let late = false;
      const r = renderHook(() => useLastChapter(props()));
      expect(setChapter).not.toHaveBeenCalled();
      expect(r.result.current).toBe('pending');
      await vi.advanceTimersByTimeAsync(2500);
      late = true; r.rerender();
      expect(setChapter).toHaveBeenCalledTimes(1);
      expect(setChapter).toHaveBeenCalledWith('c2');
      r.rerender();
      expect(JSON.parse(localStorage.getItem('poemseed.default.lastpos.v1::u1::p1::w%2Fs%2Fb')!).chapterId).toBe('c2');
      expect(r.result.current).toBe('real');
    } finally { vi.useRealTimers(); }
  });
  it('pending never writes even if a chapter is already selected', () => {
    renderHook(() => useLastChapter({actorId: 'u1', scope, novelId: 'p1', chapterId: 'c1', rows, setChapter: vi.fn(), identityPending: true}));
    expect(localStorage.length).toBe(0);
  });
});

describe('useLastChapter owner rule (Vera P1-1 / P2)', () => {
  const K1 = 'poemseed.default.lastpos.v1::u1::p1::w%2Fs%2Fb', KB = 'poemseed.default.lastpos.v1::uB::p1::w%2Fs%2Fb';
  const rows3 = [{id: 'c1'}, {id: 'c2'}, {id: 'c3'}];
  beforeEach(() => { __resetLastPositionSession(); localStorage.clear(); });
  function harness(init: {actorId?: string; pending?: boolean}) {
    const st = {actorId: init.actorId, pending: !!init.pending, chapterId: ''};
    const setChapter = vi.fn((id: string) => { st.chapterId = id; });
    const r = renderHook(() => useLastChapter({actorId: st.actorId, scope, novelId: 'p1', chapterId: st.chapterId, rows: rows3, setChapter, identityPending: st.pending}));
    const settle = () => { for (let i = 0; i < 4; i++) r.rerender(); };
    return {st, setChapter, r, settle};
  }
  it('session-mode auto pick (after failed bootstrap) is never written to the real user when identity recovers', () => {
    localStorage.setItem(K1, JSON.stringify({v: 1, chapterId: 'c3'}));
    const h = harness({actorId: undefined}); h.settle();
    expect(h.st.chapterId).toBe('c1');
    h.st.actorId = 'u1'; h.settle();
    expect(JSON.parse(localStorage.getItem(K1)!).chapterId).toBe('c3');
    expect(h.st.chapterId).toBe('c3'); // re-picked from the real user's memory
  });
  it('a chapter clicked while identity was pending is not written once identity resolves', () => {
    localStorage.setItem(K1, JSON.stringify({v: 1, chapterId: 'c3'}));
    const h = harness({actorId: undefined, pending: true});
    h.st.chapterId = 'c2'; h.settle();
    h.st.actorId = 'u1'; h.st.pending = false; h.settle();
    expect(JSON.parse(localStorage.getItem(K1)!).chapterId).toBe('c3');
  });
  it('explicit click under the real identity is written', () => {
    const h = harness({actorId: 'u1'}); h.settle();
    h.st.chapterId = 'c2'; h.settle();
    expect(JSON.parse(localStorage.getItem(K1)!).chapterId).toBe('c2');
  });
  it('P2: mid-session A→B resets the chapter; A\'s ch3 is never written to B\'s key', () => {
    localStorage.setItem(K1, JSON.stringify({v: 1, chapterId: 'c3'}));
    const h = harness({actorId: 'u1'}); h.settle();
    expect(h.st.chapterId).toBe('c3');
    h.st.actorId = 'uB'; h.settle();
    expect(h.st.chapterId).toBe('c1');
    expect(JSON.parse(localStorage.getItem(KB) ?? 'null')?.chapterId ?? 'c1').toBe('c1');
    // also after a user click under A
    h.st.actorId = 'u1'; h.settle(); h.st.chapterId = 'c2'; h.settle();
    h.st.actorId = 'uB'; h.settle();
    expect(JSON.parse(localStorage.getItem(KB) ?? 'null')?.chapterId ?? 'none').not.toBe('c2');
  });
});
