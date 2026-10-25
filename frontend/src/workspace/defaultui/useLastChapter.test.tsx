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
