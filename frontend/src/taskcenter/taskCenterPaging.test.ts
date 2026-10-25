import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { createTaskCenterClient } from './taskCenterClient';
import { taskCenterProjection } from './taskCenterContract';
import { FIXTURE_PROJECT, projectedTask, tasksResponse } from './taskCenterFixtures';

/** [HERMIA-FE-CONTRACTS G-TC-1] 合同夹具，仅证明前端接缝，不构成运行时验收。 */
const base = `/api/novels/${FIXTURE_PROJECT}/experimental/workspace/tasks`;
const paged = (o: Record<string, unknown> = {}) => tasksResponse({
  observed_total: 3, limit: 2, offset: 0, has_more: true, next_offset: 2, source_truncated: false, truncated: true,
  coverage: { scope: 'BOUNDED_AUTHORIZED_PROJECTION', completeness: 'NOT_ASSERTED' },
  items: [projectedTask(), projectedTask({ id: 'media-task-2' })], ...o,
});

describe('G-TC-1 paged task projection', () => {
  it('sends limit/offset only when explicitly requested', async () => {
    const json = vi.fn().mockResolvedValueOnce(tasksResponse()).mockResolvedValueOnce(paged());
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json });
    expect((await client.readTasks({ q: '', failed_only: false })).page).toBeNull();
    expect(json.mock.calls[0][0]).toBe(`${base}?q=&failed_only=false`);
    const value = await client.readTasks({ q: '', failed_only: false, limit: 2, offset: 0 });
    expect(json.mock.calls[1][0]).toBe(`${base}?q=&failed_only=false&limit=2&offset=0`);
    expect(value.page).toEqual({ observed_total: 3, limit: 2, offset: 0, has_more: true, next_offset: 2,
      source_truncated: false, completeness: 'NOT_ASSERTED' });
    // 分页模式下旧 truncated 警告只跟随 source_truncated
    expect(value.truncated).toBe(false);
  });
  it('rejects out-of-range paging locally without a request', async () => {
    const json = vi.fn();
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json });
    await expect(client.readTasks({ q: '', failed_only: false, limit: 101, offset: 0 })).rejects.toBeInstanceOf(ApiError);
    await expect(client.readTasks({ q: '', failed_only: false, limit: 10, offset: -1 })).rejects.toBeInstanceOf(ApiError);
    expect(json).not.toHaveBeenCalled();
  });
  it('falls back gracefully to an old unpaged response', async () => {
    const json = vi.fn().mockResolvedValueOnce(tasksResponse({ truncated: true }));
    const value = await createTaskCenterClient(FIXTURE_PROJECT, { json }).readTasks({ q: '', failed_only: false, limit: 50, offset: 0 });
    expect(value.page).toBeNull();
    expect(value.truncated).toBe(true);
  });
  it('retries once without paging when the server refuses the paging query', async () => {
    const json = vi.fn()
      .mockRejectedValueOnce(new ApiError({ status: 422, code: 'EXPERIMENTAL_INVALID', message: 'TASKCENTER_QUERY_INVALID' } as never))
      .mockResolvedValueOnce(tasksResponse());
    const value = await createTaskCenterClient(FIXTURE_PROJECT, { json }).readTasks({ q: '', failed_only: false, limit: 50, offset: 0 });
    expect(json).toHaveBeenCalledTimes(2);
    expect(json.mock.calls[1][0]).toBe(`${base}?q=&failed_only=false`);
    expect(value.page).toBeNull();
  });
  it('rejects inconsistent paging metadata and never asserts completeness', () => {
    expect(() => taskCenterProjection(paged({ has_more: false, next_offset: 2 }), FIXTURE_PROJECT)).toThrow();
    expect(() => taskCenterProjection(paged({ coverage: { scope: 'BOUNDED_AUTHORIZED_PROJECTION', completeness: 'COMPLETE' } }), FIXTURE_PROJECT)).toThrow();
    expect(() => taskCenterProjection(paged({ observed_total: 1 }), FIXTURE_PROJECT)).toThrow();
    const last = taskCenterProjection(paged({ has_more: false, next_offset: null, truncated: false, offset: 2, observed_total: 4 }), FIXTURE_PROJECT);
    expect(last.page?.completeness).toBe('NOT_ASSERTED');
  });
});
