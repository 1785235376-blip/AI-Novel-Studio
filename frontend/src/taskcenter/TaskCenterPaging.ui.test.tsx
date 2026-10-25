// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TaskCenter } from './TaskCenter';
import { reviewInboxProjection, taskCenterProjection } from './taskCenterContract';
import { FIXTURE_PROJECT, projectedTask, tasksResponse } from './taskCenterFixtures';
import type { TaskCenterClient } from './taskCenterTypes';
import { useTaskCenter } from './useTaskCenter';

const page = (ids: string[], o: Record<string, unknown>) => taskCenterProjection(tasksResponse({
  items: ids.map(id => projectedTask({ id })), truncated: Boolean(o.has_more) || Boolean(o.source_truncated),
  source_truncated: false, coverage: { scope: 'BOUNDED_AUTHORIZED_PROJECTION', completeness: 'NOT_ASSERTED' }, ...o,
}), FIXTURE_PROJECT);
function View({ client }: { client: TaskCenterClient }) {
  const controller = useTaskCenter({ identity: 'p', active: true, denied: false, busy: false, isCurrent: () => true,
    read: w => w(), mutate: w => w(), client, pageSize: 2 });
  return <TaskCenter controller={controller}/>;
}
afterEach(cleanup);

describe('G-TC-1 task center paging UI', () => {
  it('shows loaded count, appends on load-more and never claims completeness', async () => {
    const readTasks = vi.fn()
      .mockResolvedValueOnce(page(['t1', 't2'], { observed_total: 3, limit: 2, offset: 0, has_more: true, next_offset: 2 }))
      .mockResolvedValueOnce(page(['t3'], { observed_total: 3, limit: 2, offset: 2, has_more: false, next_offset: null }));
    const client = { readTasks, readInbox: vi.fn(async () => reviewInboxProjection({ items: [], total: 0, unavailable: [],
      approval_authority: 'DOMAIN_SERVICE', batch_semantics: 'PER_ITEM_CHECKPOINT' }, FIXTURE_PROJECT)) } as unknown as TaskCenterClient;
    render(<View client={client}/>);
    expect((await screen.findByTestId('tc-paging')).textContent).toMatch(/已加载 2 条/);
    expect(readTasks.mock.calls[0][0]).toEqual({ q: '', failed_only: false, limit: 2, offset: 0 });
    expect(document.body.textContent).not.toMatch(/共 \d+ 条/);
    fireEvent.click(screen.getByRole('button', { name: '加载更多任务' }));
    await waitFor(() => expect(screen.getByTestId('tc-paging').textContent).toMatch(/已加载 3 条/));
    expect(readTasks.mock.calls[1][0]).toEqual({ q: '', failed_only: false, limit: 2, offset: 2 });
    expect(screen.queryByRole('button', { name: '加载更多任务' })).toBeNull();
    expect(screen.getByText(/不代表已列出全部历史任务/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/全部加载|已全部|加载完毕/);
  });
});
