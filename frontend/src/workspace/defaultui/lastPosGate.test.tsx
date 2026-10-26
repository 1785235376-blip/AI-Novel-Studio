// @vitest-environment jsdom
// [UWPORT-P1 tests] App-level gate + status hint (Vera mutants M4/M5/M6/M7 + P1-1 error-as-pending, P3 timeout).
import {afterEach, describe, expect, it, vi} from 'vitest';
import {act, cleanup, render, screen} from '@testing-library/react';
import {lastChapterIdentityPending as gate, lastPosStatus, LASTPOS_TIMEOUT_MS} from './lastPosGate';
import {translate} from '../../i18n';

afterEach(cleanup);
const zh = (k: Parameters<typeof translate>[1]) => translate('zh-CN', k);
const en = (k: Parameters<typeof translate>[1]) => translate('en', k);
describe('lastChapterIdentityPending (App gate)', () => {
  it('settled identity with matching actor ⇒ not pending (kills "always true")', () => {
    expect(gate({isLoading: false, isError: false, bootstrapActorId: 'u1', actorId: 'u1'})).toBe(false);
    expect(gate({isLoading: false, isError: false, bootstrapActorId: undefined, actorId: undefined})).toBe(false);
  });
  it('bootstrap loading ⇒ pending (kills M4 gate≡false, M5 drop isLoading)', () => {
    expect(gate({isLoading: true, isError: false, actorId: undefined})).toBe(true);
  });
  it('bootstrap actor not yet in store ⇒ pending (kills M6 drop mismatch)', () => {
    expect(gate({isLoading: false, isError: false, bootstrapActorId: 'u1', actorId: undefined})).toBe(true);
    expect(gate({isLoading: false, isError: false, bootstrapActorId: 'u2', actorId: 'u1'})).toBe(true);
  });
  it('P1-1: bootstrap errored with token/scope ⇒ pending (session memory must not pick/write)', () => {
    expect(gate({isLoading: false, isError: true, actorId: undefined})).toBe(true);
  });
});
describe('lastPosStatus (status bar hint)', () => {
  it('session mode shows 仅本次会话 (kills M7 drop session hint); real shows nothing', () => {
    render(<>{lastPosStatus('p1', 'session', false, zh)}</>);
    expect(screen.getByTestId('dui-lastpos-session').textContent).toContain('仅本次会话');
    cleanup();
    render(<>{lastPosStatus('p1', 'real', false, zh)}</>);
    expect(screen.queryByTestId('dui-lastpos-session')).toBeNull();
    expect(screen.queryByTestId('dui-lastpos-pending')).toBeNull();
    cleanup();
    render(<>{lastPosStatus('', 'session', false, zh)}</>);
    expect(screen.queryByTestId('dui-lastpos-session')).toBeNull();
  });
  it('P3: pending shows loading, then a timeout hint; failure says so; en translated', () => {
    vi.useFakeTimers();
    try {
      render(<>{lastPosStatus('p1', 'pending', false, zh)}</>);
      const el = screen.getByTestId('dui-lastpos-pending');
      expect(el.dataset.state).toBe('loading'); expect(el.textContent).toContain('正在确认账号');
      act(() => { vi.advanceTimersByTime(LASTPOS_TIMEOUT_MS + 1); });
      expect(el.dataset.state).toBe('timeout'); expect(el.textContent).toContain('手动选择章节');
      cleanup();
      render(<>{lastPosStatus('p1', 'pending', true, en)}</>);
      expect(screen.getByTestId('dui-lastpos-pending').dataset.state).toBe('failed');
      expect(screen.getByTestId('dui-lastpos-pending').textContent).toMatch(/Account check failed/);
    } finally { vi.useRealTimers(); }
  });
});
