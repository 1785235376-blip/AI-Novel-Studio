// @vitest-environment jsdom
// [HERMIA-FE-20261024 M2-s1fix2] the microtask-deferred on-demand read is cancelled by effect cleanup: a queue that is
// shown and left again before microtasks run (TASKS → REVIEW → TASKS in one task) must not be read.
import { act, cleanup, renderHook } from '@testing-library/react';
import { flushSync } from 'react-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { FIXTURE_PROJECT, tasksResponse } from './taskCenterFixtures';
import { taskCenterProjection } from './taskCenterContract';
import type { TaskCenterClient } from './taskCenterTypes';
import { useTaskCenter, type TaskCenterControllerProps } from './useTaskCenter';
afterEach(cleanup);

it('a superseded deferred read is cancelled (no read for a queue left within the same task)', async () => {
  const readTasks = vi.fn(async () => taskCenterProjection(tasksResponse(), FIXTURE_PROJECT));
  const readInbox = vi.fn(async () => { throw new Error('must not read'); });
  const client = { readTasks, readInbox, cancelTask: vi.fn(), reviewItem: vi.fn(), reviewBatch: vi.fn() } as unknown as TaskCenterClient;
  const props: TaskCenterControllerProps = { identity: 'a', active: true, denied: false, busy: false, isCurrent: () => true,
    read: work => work(), mutate: work => work(), client };
  const view = renderHook((p: TaskCenterControllerProps) => useTaskCenter(p), { initialProps: props });
  await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  expect(readTasks).toHaveBeenCalledTimes(1);
  act(() => {
    flushSync(() => view.result.current.setQueue('REVIEW'));
    flushSync(() => view.result.current.setQueue('TASKS'));
  });
  await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  expect(readInbox).not.toHaveBeenCalled();
  expect(readTasks).toHaveBeenCalledTimes(1);
});
