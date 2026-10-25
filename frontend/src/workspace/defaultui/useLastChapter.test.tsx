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
});
