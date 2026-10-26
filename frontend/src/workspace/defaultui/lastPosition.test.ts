import {beforeEach, describe, expect, it} from 'vitest';
import {__resetLastPositionSession, LAST_POSITION_TEXT, lastPositionKey, pickChapter, rememberChapter, recallChapter} from './lastPosition';
import {resolveWorkspaceIdentity} from '../state/scopeLease';

const mem = () => { const m = new Map<string, string>(); return {m, getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => { m.set(k, v); }}; };
const scope = {workspaceId: 'w', projectId: 'p1', storylineId: 's', branchId: 'b'};
const real = (projectId = 'p1') => resolveWorkspaceIdentity({actorId: 'u1', collabScope: {...scope, projectId}, projectId});
const rows = [{id: 'c1'}, {id: 'c2'}, {id: 'c3'}];

describe('default UI last position', () => {
  beforeEach(() => __resetLastPositionSession());
  it('real identity: remembers chapter per user/project/instance and restores it', () => {
    const st = mem();
    expect(rememberChapter(st, real(), 'c2')).toBe('saved');
    expect(recallChapter(st, real())).toBe('c2');
    expect(pickChapter(rows, recallChapter(st, real()))).toBe('c2');
    expect([...st.m.keys()]).toEqual([lastPositionKey((real() as unknown as {scope: never}).scope)]);
  });
  it('different project never sees another project position', () => {
    const st = mem(); rememberChapter(st, real('p1'), 'c2');
    expect(recallChapter(st, real('p2'))).toBeNull();
  });
  it('session identity: zero storage writes, memory only (仅本次会话)', () => {
    const st = mem(); const ses = resolveWorkspaceIdentity({actorId: null, collabScope: null, projectId: 'p1'});
    expect(rememberChapter(st, ses, 'c3')).toBe('session');
    expect(st.m.size).toBe(0);
    expect(recallChapter(st, ses)).toBe('c3');
    expect(LAST_POSITION_TEXT.session).toContain('仅本次会话');
  });
  it('deleted chapter is not resurrected: falls back to first', () => {
    expect(pickChapter(rows, 'gone')).toBe('c1');
    expect(pickChapter([], 'c1')).toBeNull();
  });
  it('corrupt / future data is left untouched and ignored', () => {
    const st = mem(); const k = lastPositionKey((real() as unknown as {scope: never}).scope);
    st.m.set(k, '{bad'); expect(recallChapter(st, real())).toBeNull(); expect(st.m.get(k)).toBe('{bad');
    st.m.set(k, JSON.stringify({v: 2, chapterId: 'c2'})); expect(recallChapter(st, real())).toBeNull();
    expect(rememberChapter(st, real(), 'c3')).toBe('session'); expect(st.m.get(k)).toContain('"v":2');
  });
  it('storage failure keeps session value', () => {
    const st = {getItem: () => { throw new Error('x'); }, setItem: () => { throw new Error('x'); }};
    expect(rememberChapter(st, real(), 'c2')).toBe('write-failed');
    expect(recallChapter(st, real())).toBe('c2');
  });
});
