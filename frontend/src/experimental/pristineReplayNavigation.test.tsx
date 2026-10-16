// @vitest-environment jsdom
import { StrictMode, useLayoutEffect } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PristineReplayNavigation, usePristineReplayNavigation } from './pristineReplayNavigation';
import { originalTaskTarget } from './productionReceiptReview';
import type { WorkspaceNavigation } from './uxClient';

afterEach(cleanup);
const click = (node: HTMLElement) => (node as unknown as Record<string, { onClick: () => void }>)[Object.keys(node).find(key => key.startsWith('__reactProps'))!].onClick;
function DuringLayoutCleanup({ attempt }: { attempt: () => void }) {
  useLayoutEffect(() => () => attempt(), [attempt]); return null;
}
function Harness({ target = originalTaskTarget('task'), receipt = 'receipt', disabled = false, navigate, unmountAttempt }: {
  target?: WorkspaceNavigation; receipt?: string; disabled?: boolean; navigate: (target: WorkspaceNavigation) => void; unmountAttempt?: () => void;
}) {
  const gate = usePristineReplayNavigation();
  return <><button onClick={gate.retire}>Enter editor</button><PristineReplayNavigation gate={gate} target={target} receiptIdentity={receipt} onNavigate={navigate} disabled={disabled} />{unmountAttempt && <DuringLayoutCleanup attempt={unmountAttempt} />}</>;
}
it.each(['target', 'receipt', 'callback', 'busy'])('rejects retained primary handlers after %s ABA', change => {
  const navigate = vi.fn(), changed = vi.fn();
  const original = { navigate, target: originalTaskTarget('task'), receipt: 'receipt', disabled: false };
  const view = render(<Harness {...original} />);
  const stale = click(screen.getByRole('button', { name: '审核重放产物' }));
  view.rerender(<Harness {...original} {...(change === 'target' ? { target: originalTaskTarget('other') } : change === 'receipt' ? { receipt: 'changed' } : change === 'callback' ? { navigate: changed } : { disabled: true })} />);
  act(() => stale());
  view.rerender(<Harness {...original} />); act(() => stale());
  expect(navigate).not.toHaveBeenCalled(); expect(changed).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '审核重放产物' }));
  expect(navigate).toHaveBeenCalledTimes(1);
});
it('retires authority admission during layout cleanup before any passive unmount cleanup', () => {
  const navigate = vi.fn(); let attempt = () => {};
  const view = render(<Harness navigate={navigate} unmountAttempt={() => attempt()} />);
  attempt = click(screen.getByRole('button', { name: '审核重放产物' }));
  view.unmount(); expect(navigate).not.toHaveBeenCalled();
});
it('supports StrictMode while consuming the pristine capability only once', () => {
  const navigate = vi.fn(); render(<StrictMode><Harness navigate={navigate} /></StrictMode>);
  const retained = click(screen.getByRole('button', { name: '审核重放产物' }));
  act(() => { retained(); retained(); });
  expect(navigate).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: '审核重放产物' }));
  expect(screen.getByRole('button', { name: '确认离开并审核重放产物' })).toBeTruthy();
  expect(navigate).toHaveBeenCalledTimes(1);
});
