// @vitest-environment jsdom
// [HERMIA-FE-20261024 M0] Deterministic lifecycle diagnostics for the receipt companion case that failed once in the
// independent 63-file run (TaskCenter.additive.test.tsx:72). Every response is a manually controlled deferred promise,
// so these cases do not depend on timers or machine load. They are diagnostics/counterexamples, not a claim of a fix.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { TaskCenter } from './TaskCenter';
import { taskCenterProjection } from './taskCenterContract';
import { FIXTURE_PROJECT, projectedTask, tasksResponse } from './taskCenterFixtures';
import { ledgerRow, receiptScope, receiptTask } from './taskCostReceiptFixtures';
import { taskCostReceipt, type TaskCostReceipt } from './taskCostReceiptHelpers';
import type { TaskCenterClient } from './taskCenterTypes';
import { useTaskCenter, type TaskCenterControllerProps } from './useTaskCenter';

function deferred<T>() {
  let resolve!: (v: T) => void; let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
const AMOUNT = '1.000001 USD（1000001 micro-USD）';
const completed = () => taskCenterProjection(tasksResponse({ items: [projectedTask({ ...receiptTask, status: 'COMPLETED', stage_label: '已完成' })], unavailable: [] }), FIXTURE_PROJECT);
const okReceipt = (): TaskCostReceipt => taskCostReceipt({ ledger: [ledgerRow()] }, receiptTask, FIXTURE_PROJECT, receiptScope);

function client(readTasks: () => Promise<unknown>) {
  return { readTasks: vi.fn(readTasks), readInbox: vi.fn(), cancelTask: vi.fn(), reviewItem: vi.fn(), reviewBatch: vi.fn() } as unknown as TaskCenterClient & { readTasks: ReturnType<typeof vi.fn> };
}
function View({ c, patch }: { c: TaskCenterClient; patch: Partial<TaskCenterControllerProps> }) {
  const controller = useTaskCenter({ identity: 'taskcenter-view', active: true, denied: false, busy: false, isCurrent: () => true,
    read: work => work(), mutate: work => work(), client: c, ...patch });
  return <TaskCenter controller={controller}/>;
}
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('[M0] receipt companion lifecycle (deterministic deferred)', () => {
  it('shows the amount only after the explicit read resolves, then keeps task info on a later failed read', async () => {
    const c = client(async () => completed());
    const first = deferred<TaskCostReceipt>(), second = deferred<TaskCostReceipt>();
    const readCostReceipt = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    render(<View c={c} patch={{ costReceiptClient: { readCostReceipt } }}/>);
    await screen.findByRole('article', { name: '任务 author_generation job-1' });
    expect(readCostReceipt).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '查看原任务费用回执' }));
    expect(readCostReceipt).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(AMOUNT)).toBeNull();
    await act(async () => { first.resolve(okReceipt()); await first.promise; });
    expect(screen.getByText(AMOUNT)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '重新读取此费用回执' }));
    await act(async () => { second.resolve({ kind: 'UNKNOWN', reason: 'UNREADABLE' } as TaskCostReceipt); await second.promise; });
    expect(screen.getByText(/费用 UNKNOWN（未知）：原 broker 回执当前不可读/)).toBeTruthy();
    expect(screen.queryByText(AMOUNT)).toBeNull();
    expect(screen.getByRole('article', { name: '任务 author_generation job-1' }).textContent).toContain('COMPLETED');
    expect(c.readTasks).toHaveBeenCalledTimes(1);
  });

  it('a rejected read becomes UNKNOWN without losing the task row', async () => {
    const c = client(async () => completed());
    const d = deferred<TaskCostReceipt>();
    render(<View c={c} patch={{ costReceiptClient: { readCostReceipt: vi.fn(() => d.promise) } }}/>);
    await screen.findByRole('article', { name: '任务 author_generation job-1' });
    fireEvent.click(screen.getByRole('button', { name: '查看原任务费用回执' }));
    await act(async () => { d.reject(new Error('boom secret')); await d.promise.catch(() => {}); });
    expect(screen.queryByText(AMOUNT)).toBeNull();
    expect(document.body.textContent).not.toContain('secret');
    expect(screen.getByRole('article', { name: '任务 author_generation job-1' })).toBeTruthy();
  });

  it('a late response after unmount writes nothing (no act warning, no throw)', async () => {
    const c = client(async () => completed());
    const d = deferred<TaskCostReceipt>();
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    const view = render(<View c={c} patch={{ costReceiptClient: { readCostReceipt: vi.fn(() => d.promise) } }}/>);
    await screen.findByRole('article', { name: '任务 author_generation job-1' });
    fireEvent.click(screen.getByRole('button', { name: '查看原任务费用回执' }));
    view.unmount();
    await act(async () => { d.resolve(okReceipt()); await d.promise; });
    expect(err).not.toHaveBeenCalled();
  });

  it('ABA: response for identity A arriving after A→B→A is dropped (companion closed by identity change)', async () => {
    const c = client(async () => completed());
    const d = deferred<TaskCostReceipt>();
    const readCostReceipt = vi.fn(() => d.promise);
    const costReceiptClient = { readCostReceipt };
    const view = render(<View c={c} patch={{ costReceiptClient, identity: 'A' }}/>);
    await screen.findByRole('article', { name: '任务 author_generation job-1' });
    fireEvent.click(screen.getByRole('button', { name: '查看原任务费用回执' }));
    view.rerender(<View c={c} patch={{ costReceiptClient, identity: 'B' }}/>); await flush();
    view.rerender(<View c={c} patch={{ costReceiptClient, identity: 'A' }}/>); await flush();
    await act(async () => { d.resolve(okReceipt()); await d.promise; });
    expect(screen.queryByText(AMOUNT)).toBeNull();
  });

  it('documented design boundary: a companion-client identity change while the read is pending drops the in-flight receipt', async () => {
    // Paths that hide the amount after an explicit read: companion close on identity/active/denied/client/enabled/
    // visible-task-array change. The original test keeps all of these stable (one readTasks, stable client), so this
    // does NOT prove the observed failure's cause; it pins the behaviour so a future change is visible.
    const lists = [deferred<unknown>(), deferred<unknown>()];
    let n = 0;
    const c = client(() => lists[n++].promise);
    const d = deferred<TaskCostReceipt>();
    const view = render(<View c={c} patch={{ costReceiptClient: { readCostReceipt: vi.fn(() => d.promise) } }}/>);
    await flush();
    await act(async () => { lists[0].resolve(completed()); await lists[0].promise; });
    fireEvent.click(screen.getByRole('button', { name: '查看原任务费用回执' }));
    view.rerender(<View c={c} patch={{ costReceiptClient: { readCostReceipt: vi.fn(() => d.promise) } }}/>);
    await act(async () => { d.resolve(okReceipt()); await d.promise; });
    // costReceiptClient identity change bumps the companion epoch → receipt dropped, task row kept.
    expect(screen.queryByText(AMOUNT)).toBeNull();
    expect(screen.getByRole('article', { name: '任务 author_generation job-1' })).toBeTruthy();
  });
});
