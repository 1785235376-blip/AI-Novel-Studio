// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useTaskCenter, type TaskCenterControllerProps } from './useTaskCenter';
import { taskCenterProjection } from './taskCenterContract';
import { FIXTURE_PROJECT, projectedTask, tasksResponse } from './taskCenterFixtures';
import type { TaskCenterClient } from './taskCenterTypes';
import type { TaskCostReceipt } from './taskCostReceipt';
const projection = () => taskCenterProjection(tasksResponse({ items: ['job-1', 'job-2'].map(id =>
  projectedTask({ id, authority: 'author_generation' })), unavailable: [] }), FIXTURE_PROJECT);
const unknown: TaskCostReceipt = { kind: 'UNKNOWN', reason: 'MISSING' };
const deferred = () => { let resolve!: (value: TaskCostReceipt) => void; const promise = new Promise<TaskCostReceipt>(r => { resolve = r; }); return { resolve, promise }; };
function setup(readCostReceipt = vi.fn(async () => unknown)) {
  const client = { readTasks: vi.fn(async () => projection()), readInbox: vi.fn(async () => { throw new Error('unavailable fixture'); }), readCostReceipt } as unknown as TaskCenterClient;
  const props: TaskCenterControllerProps = { identity: 'project-A', active: true, denied: false, busy: false,
    isCurrent: () => true, read: work => work(), mutate: vi.fn(), client };
  const hook = renderHook((p: TaskCenterControllerProps) => useTaskCenter(p), { initialProps: props });
  return { ...hook, props, client, readCostReceipt };
}
afterEach(cleanup);
describe('selected task cost receipt controller', () => {
  it('reads only on explicit selection; selection and close suppress late results', async () => {
    const a = deferred(), b = deferred(); const read = vi.fn().mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise); const h = setup(read);
    await waitFor(() => expect(h.result.current.visibleTasks).toHaveLength(2));
    expect(read).not.toHaveBeenCalled();
    const [first, second] = h.result.current.visibleTasks;
    act(() => { void h.result.current.costReceipt.read(first); });
    expect(h.result.current.costReceipt.selection?.loading).toBe(true);
    act(() => { void h.result.current.costReceipt.read(second); });
    expect(read.mock.calls[0][1].aborted).toBe(true);
    await act(async () => { a.resolve(unknown); });
    expect(h.result.current.costReceipt.selection?.task).toBe(second);
    expect(h.result.current.costReceipt.selection?.loading).toBe(true);
    act(() => h.result.current.costReceipt.close());
    await act(async () => { b.resolve(unknown); });
    expect(h.result.current.costReceipt.selection).toBeUndefined();
    expect(h.props.mutate).not.toHaveBeenCalled();
  });
  it.each(['identity', 'inactive', 'denied', 'stale', 'queue', 'reload'])('suppresses late results after %s', async change => {
    const pending = deferred(); const read = vi.fn(() => pending.promise); const h = setup(read);
    await waitFor(() => expect(h.result.current.visibleTasks).toHaveLength(2));
    act(() => { void h.result.current.costReceipt.read(h.result.current.visibleTasks[0]); });
    if (change === 'queue') act(() => h.result.current.setQueue('REVIEW'));
    else if (change === 'reload') await act(async () => { await h.result.current.reload(); });
    else h.rerender({ ...h.props, ...(change === 'identity' ? { identity: 'project-B' }
      : change === 'inactive' ? { active: false } : change === 'denied' ? { denied: true } : { isCurrent: () => false }) });
    expect(h.result.current.costReceipt.selection).toBeUndefined();
    await act(async () => { pending.resolve(unknown); });
    expect(h.result.current.costReceipt.selection).toBeUndefined();
    expect(read).toHaveBeenCalledTimes(1);
  });
  it('isolates failed reads, keeps task info, and refreshes only explicitly', async () => {
    const read = vi.fn().mockRejectedValueOnce(new Error('secret')).mockResolvedValueOnce(unknown); const h = setup(read);
    await waitFor(() => expect(h.result.current.visibleTasks).toHaveLength(2));
    const task = h.result.current.visibleTasks[0];
    await act(async () => { await h.result.current.costReceipt.read(task); });
    expect(h.result.current.costReceipt.selection?.receipt).toEqual({ kind: 'UNKNOWN', reason: 'UNREADABLE' });
    expect(h.result.current.tasksState).toBe('READY');
    expect(h.result.current.visibleTasks[0]).toBe(task);
    await act(async () => { await h.result.current.costReceipt.read(task); });
    expect(h.result.current.costReceipt.selection?.receipt).toEqual(unknown);
    expect(read).toHaveBeenCalledTimes(2);
  });
  it('rejects invisible task objects and busy sessions without a request', async () => {
    const h = setup(); await waitFor(() => expect(h.result.current.visibleTasks).toHaveLength(2));
    await act(async () => { await h.result.current.costReceipt.read({ ...h.result.current.visibleTasks[0] }); });
    h.rerender({ ...h.props, busy: true });
    await act(async () => { await h.result.current.costReceipt.read(h.result.current.visibleTasks[0]); });
    expect(h.readCostReceipt).not.toHaveBeenCalled();
  });
});
