// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import {
  FIXTURE_PROJECT, FIXTURE_REVISION, cancelReceipt, projectedFormalTask, projectedTask, reviewInboxBatchItem,
  reviewInboxItem, tasksResponse,
} from './taskCenterFixtures';
import { reviewInboxProjection, taskCenterProjection } from './taskCenterContract';
import type { ReviewInboxItem, TaskCenterClient, TaskCenterTask, TaskCenterTasksProjection } from './taskCenterTypes';
import {
  batchActionAvailability, reviewActionAvailability, useTaskCenter, type TaskCenterControllerProps,
} from './useTaskCenter';

const tasks = (overrides: Record<string, unknown> = {}): TaskCenterTasksProjection =>
  taskCenterProjection(tasksResponse(overrides), FIXTURE_PROJECT);
const inbox = (overrides: Record<string, unknown> = {}) => reviewInboxProjection({
  items: [reviewInboxItem(), reviewInboxBatchItem()], total: 2,
  unavailable: [{ domain: 'legacy_canon', reason: 'ORIGINAL_DOMAIN_ACCESS_REQUIRED' }],
  approval_authority: 'DOMAIN_SERVICE', batch_semantics: 'PER_ITEM_CHECKPOINT', ...overrides,
}, FIXTURE_PROJECT);

type Fake = {
  readTasks: ReturnType<typeof vi.fn>; readInbox: ReturnType<typeof vi.fn>;
  cancelTask: ReturnType<typeof vi.fn>; reviewItem: ReturnType<typeof vi.fn>; reviewBatch: ReturnType<typeof vi.fn>;
};
function fakeClient(patch: Partial<Fake> = {}) {
  const client: Fake = {
    readTasks: vi.fn(async () => tasks()),
    readInbox: vi.fn(async () => inbox()),
    cancelTask: vi.fn(async () => ({
      item: taskCenterProjection(tasksResponse({
        items: [projectedTask({ status: 'CANCELLING', stage_label: '取消中' })],
      }), FIXTURE_PROJECT).items[0],
      cancellation_requested: true as const, executor: false as const, termination_confirmed: false,
    })),
    reviewItem: vi.fn(async () => ({
      domain: 'media', id: 'candidate-1', action: 'approve' as const, accepted: true as const,
    })),
    reviewBatch: vi.fn(async () => ({
      status: 'COMPLETED' as const, results: [
        { domain: 'planning', id: 'proposal-1', status: 'SUCCEEDED' as const },
        { domain: 'planning', id: 'proposal-2', status: 'SUCCEEDED' as const },
      ], remaining: 0, retry: null, batch_semantics: 'PER_ITEM_CHECKPOINT' as const,
    })),
    ...patch,
  };
  return { client: client as unknown as TaskCenterClient, ...client };
}
const props = (client: TaskCenterClient, patch: Partial<TaskCenterControllerProps> = {}): TaskCenterControllerProps => ({
  identity: 'taskcenter-session', active: true, denied: false, busy: false, isCurrent: () => true,
  read: work => work(), mutate: work => work(), client, ...patch,
});
const mount = (client: TaskCenterClient, patch: Partial<TaskCenterControllerProps> = {}) =>
  renderHook((value: TaskCenterControllerProps) => useTaskCenter(value), { initialProps: props(client, patch) });
const settle = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); }); };
const first = (view: { result: { current: ReturnType<typeof useTaskCenter> } }): TaskCenterTask => {
  const task = view.result.current.visibleTasks[0];
  if (!task) throw new Error('expected one visible task');
  return task;
};

afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('task center controller', () => {
  it('reads the visible queue once and never while the panel is closed or hidden', async () => {
    vi.useFakeTimers();
    const { client, readTasks, readInbox } = fakeClient();
    const view = mount(client, { active: false });
    expect(view.result.current.tasksState).toBe('IDLE');
    // 面板关闭：一个请求都不发，也没有任何定时器在跑。
    await act(async () => { vi.advanceTimersByTime(60000); });
    expect(readTasks).not.toHaveBeenCalled();
    expect(readInbox).not.toHaveBeenCalled();
    view.rerender(props(client, { active: true }));
    await settle();
    expect(view.result.current.tasksState).toBe('READY');
    expect(readTasks).toHaveBeenCalledTimes(1);
    expect(readTasks).toHaveBeenCalledWith({ q: '', failed_only: false }, expect.any(AbortSignal));
    // 打开后也不轮询：一分钟的假时钟里没有新的读取。
    await act(async () => { vi.advanceTimersByTime(60000); });
    await settle();
    expect(readTasks).toHaveBeenCalledTimes(1);
    expect(readInbox).not.toHaveBeenCalled();
    // 关掉再打开不会重复读取同一个组合（内容仍在屏幕上）。
    view.rerender(props(client, { active: false }));
    view.rerender(props(client, { active: true }));
    await settle();
    expect(readTasks).toHaveBeenCalledTimes(1);
  });

  it('switches to the review inbox on demand and keeps both queue states separate', async () => {
    const { client, readTasks, readInbox } = fakeClient();
    const view = mount(client);
    await waitFor(() => expect(view.result.current.tasksState).toBe('READY'));
    act(() => view.result.current.setQueue('REVIEW'));
    await waitFor(() => expect(view.result.current.reviewState).toBe('READY'));
    expect(readInbox).toHaveBeenCalledTimes(1);
    expect(view.result.current.reviewSummary.batch_semantics).toBe('PER_ITEM_CHECKPOINT');
    expect(view.result.current.reviewSummary.approval_authority).toBe('DOMAIN_SERVICE');
    expect(readTasks).toHaveBeenCalledTimes(1);
    // 回到任务队列不会重复读取已经读过的组合。
    act(() => view.result.current.setQueue('TASKS'));
    await settle();
    expect(readTasks).toHaveBeenCalledTimes(1);
  });

  it('applies the task filters on demand and filters module/status locally', async () => {
    const { client, readTasks } = fakeClient();
    readTasks.mockResolvedValue(tasks({
      items: [
        projectedTask(),
        projectedTask({
          id: 'style-task-1', authority: 'author_generation', feature: 'style_dna_v2',
          status: 'FAILED', stage_label: '失败', progress: null,
        }),
      ],
    }));
    const view = mount(client);
    await waitFor(() => expect(view.result.current.tasksState).toBe('READY'));
    expect(view.result.current.visibleTasks).toHaveLength(2);
    act(() => view.result.current.setFilters({ module: 'style_dna_v2' }));
    expect(view.result.current.filtersDirty).toBe(true);
    // 本地模块过滤不产生新请求：端点没有模块参数，不能伪造。
    act(() => view.result.current.applyFilters());
    await settle();
    expect(readTasks).toHaveBeenCalledTimes(1);
    expect(view.result.current.filtersDirty).toBe(false);
    expect(view.result.current.visibleTasks.map(task => task.id)).toEqual(['style-task-1']);
    act(() => view.result.current.setFilters({ module: '', status: 'FAILED' }));
    act(() => view.result.current.applyFilters());
    await settle();
    expect(view.result.current.visibleTasks.map(task => task.id)).toEqual(['style-task-1']);
    // failed_only 是 owner 自己的参数：必须触发一次带参读取。
    act(() => view.result.current.setFilters({ failed_only: true, status: '' }));
    act(() => view.result.current.applyFilters());
    await waitFor(() => expect(readTasks).toHaveBeenCalledTimes(2));
    expect(readTasks).toHaveBeenLastCalledWith({ q: '', failed_only: true }, expect.any(AbortSignal));
    expect(view.result.current.summary.total).toBe(2);
    expect(view.result.current.summary.by_status.map(row => row.status)).toEqual(['RUNNING', 'FAILED']);
    expect(view.result.current.summary.without_progress).toBe(1);
  });

  it('never collapses an unreadable or failed read into an empty queue', async () => {
    const denied = fakeClient({
      readTasks: vi.fn(async () => tasks({
        items: [], unavailable: [{ authority: 'exports', label: '导出任务', reason: 'SOURCE_UNAVAILABLE' }],
      })),
    });
    const deniedView = mount(denied.client);
    await waitFor(() => expect(deniedView.result.current.tasksState).toBe('DENIED'));
    expect(deniedView.result.current.visibleTasks).toHaveLength(0);
    expect(deniedView.result.current.tasksProblem).toBeUndefined();
    expect(deniedView.result.current.tasks?.unavailable).toHaveLength(1);
    cleanup();

    const empty = fakeClient({ readTasks: vi.fn(async () => tasks({ items: [], unavailable: [] })) });
    const emptyView = mount(empty.client);
    await waitFor(() => expect(emptyView.result.current.tasksState).toBe('EMPTY'));
    expect(emptyView.result.current.tasksProblem).toBeUndefined();
    cleanup();

    const failed = fakeClient({
      readTasks: vi.fn(async () => { throw new ApiError({ status: 500, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }); }),
    });
    const failedView = mount(failed.client);
    await waitFor(() => expect(failedView.result.current.tasksState).toBe('FAILED'));
    expect(failedView.result.current.tasksProblem).toEqual({ code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' });
    expect(failedView.result.current.tasks).toBeUndefined();
  });

  it('reaches DENIED, clears everything and stops reading after authority loss', async () => {
    const onUnavailable = vi.fn();
    const { client, readTasks } = fakeClient({
      readTasks: vi.fn(async () => { throw new ApiError({ status: 403, code: 'FORBIDDEN', message: 'denied' }); }),
    });
    const view = mount(client, { onUnavailable });
    await waitFor(() => expect(view.result.current.tasksState).toBe('DENIED'));
    expect(view.result.current.tasks).toBeUndefined();
    expect(view.result.current.canRead).toBe(false);
    expect(onUnavailable).toHaveBeenCalledTimes(1);
    await act(async () => { await view.result.current.reload(); });
    expect(readTasks).toHaveBeenCalledTimes(1);
  });

  it('never reports a bare CANCELLED while the original task is unconfirmed', async () => {
    const { client, readTasks } = fakeClient();
    const view = mount(client);
    await waitFor(() => expect(view.result.current.tasksState).toBe('READY'));
    await act(async () => { await view.result.current.cancelTask(first(view)); });
    const key = 'cancel:media:media-task-1';
    const result = view.result.current.results[key];
    if (result?.kind !== 'cancel') throw new Error('expected a cancel result');
    expect(result.state).toBe('SUCCEEDED');
    expect(result.termination_confirmed).toBe(false);
    expect(result.notice).toContain('取消请求已发送/待确认');
    expect(view.result.current.notice).toContain('取消只作用于这一条原任务');
    // 状态改变后静默重读一次，保持 revision 新鲜——不是轮询。
    await waitFor(() => expect(readTasks).toHaveBeenCalledTimes(2));
    cleanup();

    // 版本冲突：保留失败结果并静默重读，绝不自动重试取消。
    const conflicted = fakeClient({
      cancelTask: vi.fn(async () => {
        throw new ApiError({ status: 409, code: 'EXPERIMENTAL_SOURCE_STALE', message: '来源或任务状态已变化，请重新读取后核对。' });
      }),
    });
    const conflictedView = mount(conflicted.client);
    await waitFor(() => expect(conflictedView.result.current.tasksState).toBe('READY'));
    await act(async () => { await conflictedView.result.current.cancelTask(first(conflictedView)); });
    expect(conflictedView.result.current.results[key]?.state).toBe('FAILED');
    expect(conflicted.cancelTask).toHaveBeenCalledTimes(1);
    expect(conflictedView.result.current.notice).toContain('来源或任务状态已变化');
    await waitFor(() => expect(conflicted.readTasks).toHaveBeenCalledTimes(2));
    expect(cancelReceipt().cancellation_requested).toBe(true);
    expect(FIXTURE_REVISION).toHaveLength(64);
  });

  it('binds the candidate version on review and refuses a duplicate submit', async () => {
    const { client, readInbox } = fakeClient();
    const view = mount(client);
    await waitFor(() => expect(view.result.current.tasksState).toBe('READY'));
    act(() => view.result.current.setQueue('REVIEW'));
    await waitFor(() => expect(view.result.current.reviewState).toBe('READY'));
    const item = view.result.current.inbox?.items[0] as ReviewInboxItem;
    expect(reviewActionAvailability(item)).toEqual(['approve', 'reject']);
    await act(async () => { await view.result.current.reviewItem(item, 'approve'); });
    expect(client.reviewItem).toHaveBeenCalledWith({ domain: 'media', id: 'candidate-1', version: 3 }, 'approve');
    const result = view.result.current.results['review:media:candidate-1'];
    if (result?.kind !== 'review') throw new Error('expected a review result');
    expect(result.expected_version).toBe(3);
    expect(result.state).toBe('SUCCEEDED');
    // 同一版本再提交一次：本地拦住，不产生第二份正式结果。
    await act(async () => { await view.result.current.reviewItem(item, 'approve'); });
    expect(client.reviewItem).toHaveBeenCalledTimes(1);
    expect(view.result.current.notice).toContain('已提交过决定');
    await waitFor(() => expect(readInbox).toHaveBeenCalledTimes(2));
  });

  it('keeps per-item batch results and only re-selects failed items on demand', async () => {
    const partial = {
      status: 'PARTIAL' as const,
      results: [
        { domain: 'planning', id: 'proposal-1', status: 'SUCCEEDED' as const },
        { domain: 'planning', id: 'proposal-2', status: 'FAILED' as const, code: 'HTTP_409' },
      ],
      remaining: 1, retry: 'REFRESH_AND_SELECT_FAILED_ITEMS' as const, batch_semantics: 'PER_ITEM_CHECKPOINT' as const,
    };
    const { client } = fakeClient({ reviewBatch: vi.fn(async () => partial) });
    const view = mount(client);
    await waitFor(() => expect(view.result.current.tasksState).toBe('READY'));
    act(() => view.result.current.setQueue('REVIEW'));
    await waitFor(() => expect(view.result.current.reviewState).toBe('READY'));
    const rows = view.result.current.inbox?.items ?? [];
    act(() => view.result.current.selectAllBatchSafe('reject'));
    expect(view.result.current.selected).toEqual(['planning:proposal-1']);
    // owner 只允许 planning 批量 reject：混合集合被本地拒绝，一个请求都没发。
    await act(async () => { await view.result.current.reviewBatch(rows, 'reject'); });
    expect(client.reviewBatch).not.toHaveBeenCalled();
    const planning = rows.filter(row => row.domain === 'planning');
    expect(batchActionAvailability(planning)).toEqual(['reject']);
    await act(async () => { await view.result.current.reviewBatch(planning, 'reject'); });
    const receipt = view.result.current.results['batch:reject'];
    if (receipt?.kind !== 'batch') throw new Error('expected a batch result');
    expect(receipt.receipt?.results.map(row => row.status)).toEqual(['SUCCEEDED', 'FAILED']);
    expect(receipt.receipt?.retry).toBe('REFRESH_AND_SELECT_FAILED_ITEMS');
    expect(view.result.current.notice).toContain('不会自动重发');
    expect(view.result.current.selected).toEqual([]);
  });

  it('emits a navigation callback for the same original task and never for a formal receipt', async () => {
    const onNavigate = vi.fn();
    const { client } = fakeClient({
      readTasks: vi.fn(async () => tasks({ items: [projectedTask(), projectedFormalTask()], unavailable: [] })),
    });
    const view = mount(client, { onNavigate });
    await waitFor(() => expect(view.result.current.tasksState).toBe('READY'));
    const [media, formal] = view.result.current.visibleTasks;
    act(() => view.result.current.navigateTask(media));
    expect(onNavigate).toHaveBeenCalledWith({
      queue: 'TASKS', authority: 'media', task_id: 'media-task-1', label: '封面与分镜',
      feature: 'cover_storyboard_generation',
      source: { kind: 'feature', id: 'media-task-1', feature: 'cover_storyboard_generation', task_authority: 'media' },
    });
    act(() => view.result.current.navigateTask(formal));
    expect(onNavigate).toHaveBeenCalledTimes(1);
    expect(view.result.current.notice).toContain('不会伪造导航目标');
    expect(formal.actions).toEqual([]);
    expect(first(view).revision).toBe(FIXTURE_REVISION);
    expect(view.result.current.taskKey(media)).toBe('media:media-task-1');
  });
});
