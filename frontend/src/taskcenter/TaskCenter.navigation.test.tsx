// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TaskCenter } from './TaskCenter';
import { reviewInboxProjection, taskCenterProjection } from './taskCenterContract';
import { FIXTURE_PROJECT, tasksResponse } from './taskCenterFixtures';
import type { TaskCenterClient } from './taskCenterTypes';
import { useTaskCenter } from './useTaskCenter';

function client() {
  return {
    readTasks: vi.fn(async () => taskCenterProjection(tasksResponse(), FIXTURE_PROJECT)),
    readInbox: vi.fn(async () => reviewInboxProjection({ items: [], total: 0, unavailable: [],
      approval_authority: 'DOMAIN_SERVICE', batch_semantics: 'PER_ITEM_CHECKPOINT' }, FIXTURE_PROJECT)),
    cancelTask: vi.fn(), reviewItem: vi.fn(), reviewBatch: vi.fn(),
  } satisfies TaskCenterClient;
}
function View({ api }: { api: TaskCenterClient }) {
  const controller = useTaskCenter({ identity: 'navigation-test', active: true, denied: false,
    busy: false, isCurrent: () => true, read: work => work(), mutate: work => work(), client: api });
  return <TaskCenter controller={controller} />;
}
const tab = (name: string) => screen.getByRole('tab', { name });

afterEach(cleanup);

describe('Task Center manual tab navigation', () => {
  it('links unique tabs and panels and keeps only the active tab in the tab sequence', async () => {
    const api = client();
    render(<View api={api} />);
    await waitFor(() => expect(api.readTasks).toHaveBeenCalledTimes(1));
    const tasks = tab('任务队列');
    const review = tab('审核收件箱');
    expect(tasks.getAttribute('tabindex')).toBe('0');
    expect(review.getAttribute('tabindex')).toBe('-1');
    for (const control of [tasks, review]) {
      expect(control.id).not.toBe('');
      const panel = document.getElementById(control.getAttribute('aria-controls') ?? '');
      expect(panel).not.toBeNull();
      expect(panel?.getAttribute('role')).toBe('tabpanel');
      expect(panel?.getAttribute('aria-labelledby')).toBe(control.id);
    }
    expect(screen.getAllByRole('tabpanel')).toHaveLength(1);
    expect(screen.getByRole('tabpanel', { name: '任务队列' })).toBeTruthy();
    expect(api.readInbox).not.toHaveBeenCalled();
  });

  it('wraps horizontal arrows and supports Home/End without activating or reading another queue', async () => {
    const api = client();
    render(<View api={api} />);
    await waitFor(() => expect(api.readTasks).toHaveBeenCalledTimes(1));
    const tasks = tab('任务队列');
    const review = tab('审核收件箱');
    tasks.focus();
    for (const [from, key, to] of [
      [tasks, 'ArrowRight', review], [review, 'ArrowRight', tasks],
      [tasks, 'ArrowLeft', review], [review, 'ArrowLeft', tasks],
      [tasks, 'End', review], [review, 'Home', tasks],
    ] as const) {
      expect(fireEvent.keyDown(from, { key })).toBe(false);
      expect(document.activeElement).toBe(to);
    }
    expect(tasks.getAttribute('aria-selected')).toBe('true');
    expect(api.readTasks).toHaveBeenCalledTimes(1);
    expect(api.readInbox).not.toHaveBeenCalled();
    expect(api.cancelTask).not.toHaveBeenCalled();
    expect(api.reviewItem).not.toHaveBeenCalled();
    expect(api.reviewBatch).not.toHaveBeenCalled();
  });

  it('leaves vertical arrows, Tab, and modified shortcuts to their native behavior', async () => {
    const api = client();
    render(<View api={api} />);
    await waitFor(() => expect(api.readTasks).toHaveBeenCalledTimes(1));
    const tasks = tab('任务队列');
    tasks.focus();
    for (const event of [{ key: 'ArrowDown' }, { key: 'ArrowUp' }, { key: 'Tab' },
      { key: 'ArrowLeft', altKey: true }, { key: 'Home', ctrlKey: true }, { key: 'End', metaKey: true }]) {
      expect(fireEvent.keyDown(tasks, event)).toBe(true);
      expect(document.activeElement).toBe(tasks);
    }
    expect(api.readInbox).not.toHaveBeenCalled();
  });

  it('activates only through the existing button action and keeps focus on the selected tab', async () => {
    const api = client();
    render(<View api={api} />);
    await waitFor(() => expect(api.readTasks).toHaveBeenCalledTimes(1));
    const tasks = tab('任务队列');
    const review = tab('审核收件箱');
    tasks.focus();
    fireEvent.keyDown(tasks, { key: 'ArrowRight' });
    expect(api.readInbox).not.toHaveBeenCalled();
    expect(review.tagName).toBe('BUTTON');
    expect(review.getAttribute('type')).toBe('button');
    fireEvent.click(review);
    await waitFor(() => expect(api.readInbox).toHaveBeenCalledTimes(1));
    expect(review.getAttribute('aria-selected')).toBe('true');
    expect(review.getAttribute('tabindex')).toBe('0');
    expect(tasks.getAttribute('tabindex')).toBe('-1');
    expect(document.activeElement).toBe(review);
    const panel = screen.getByRole('tabpanel', { name: '审核收件箱' });
    expect(panel.id).toBe(review.getAttribute('aria-controls'));
    expect(screen.getAllByRole('tabpanel')).toHaveLength(1);
    expect(api.cancelTask).not.toHaveBeenCalled();
    expect(api.reviewItem).not.toHaveBeenCalled();
    expect(api.reviewBatch).not.toHaveBeenCalled();
  });

  it('does not reuse tab or panel IDs across separate mounted workspaces', () => {
    render(<><View api={client()} /><View api={client()} /></>);
    const ids = screen.getAllByRole('tablist').flatMap(list => within(list).getAllByRole('tab')
      .flatMap(control => [control.id, control.getAttribute('aria-controls')]));
    expect(ids.every(Boolean)).toBe(true);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
