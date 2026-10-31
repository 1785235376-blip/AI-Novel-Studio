// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { TaskOwnerResult, exactMediaOwnerRecord, mediaOwnerRoute } from './TaskOwnerResult';
import type { TaskCenterNavigationTarget } from './taskCenterTypes';
const task: TaskCenterNavigationTarget = { queue: 'TASKS', authority: 'media', task_id: 'task-1', feature: 'cover_storyboard_generation', label: '媒体', source: { kind: 'feature', id: 'task-1', feature: 'cover_storyboard_generation', task_authority: 'media' } };
const candidate: TaskCenterNavigationTarget = { queue: 'REVIEW', domain: 'media', item_id: 'candidate-1', version: 3, source: 'task-1', target: [] };
const owned = { novel_id: 'project', scope: { mode: 'local', novel_id: 'project' } };
const taskRow = { ...owned, id: 'task-1', version: 2, status: 'COMPLETED', operation: 'COVER', candidate_ids: ['candidate-1'] };
const candidateRow = { ...owned, id: 'candidate-1', version: 3, status: 'PENDING_REVIEW', task_id: 'task-1' };
const deferred = () => { let resolve!: (value: unknown) => void; const promise = new Promise<unknown>(r => { resolve = r; }); return { promise, resolve }; };
function mount(target: TaskCenterNavigationTarget = task, json = vi.fn().mockResolvedValue({ items: [taskRow] })) {
  const props = { projectId: 'project', identity: 'identity', target, transport: { json }, busy: false, isCurrent: () => true, read: <T,>(work: () => Promise<T>) => work(), onClose: vi.fn() };
  const view = render(<TaskOwnerResult {...props} />);
  return { ...view, props, json };
}
afterEach(cleanup);
describe('exact original media record reopening', () => {
  it('opens only the original task owner GET without a Studio production lookup or action', async () => {
    const state = mount(); await screen.findByText('原记录 task-1 · v2 · COMPLETED');
    expect(state.json.mock.calls).toHaveLength(1);
    expect(state.json).toHaveBeenCalledWith('/api/novels/project/experimental/media/tasks', 'GET', undefined, expect.any(AbortSignal));
  });
  it('opens the exact candidate version and source through the original proposal list', async () => {
    const state = mount(candidate, vi.fn().mockResolvedValue({ items: [candidateRow] }));
    await screen.findByText('原记录 candidate-1 · v3 · PENDING_REVIEW');
    expect(state.json.mock.calls[0][0]).toBe('/api/novels/project/experimental/media/proposals');
    expect(screen.queryByRole('button', { name: /批准|执行|重试/ })).toBeNull();
  });
  it.each([{ version: 4 }, { task_id: 'other' }])('refuses changed candidate %j without latest substitution', async patch => {
    mount(candidate, vi.fn().mockResolvedValue({ items: [{ ...candidateRow, ...patch }] }));
    await screen.findByText(/原候选版本或来源已变化/); expect(screen.queryByLabelText('已核对原媒体记录')).toBeNull();
  });
  it.each(['images', 'media_generation', 'author_generation', 'review_inbox'])('does not infer a production ID for %s', async authority => {
    const state = mount({ ...task, authority });
    expect(screen.getByText(/此来源没有接入/)).toBeTruthy(); expect(state.json).not.toHaveBeenCalled();
  });
  it('rejects a mismatched source pointer even for a recognized authority', () => {
    expect(mediaOwnerRoute({ ...task, source: { ...task.source, id: 'other' } })).toBeNull();
    expect(mediaOwnerRoute({ ...candidate, domain: 'planning' })).toBeNull();
  });
  it.each([[], [taskRow, taskRow], [{ ...taskRow, version: 0 }], [{ id: 'other', version: 2, status: 'COMPLETED' }]].map(items => ({ items })))('refuses missing/ambiguous/invalid records %j', ({ items }) => {
    expect(() => exactMediaOwnerRecord({ items }, task, 'project')).toThrow();
  });
  it('does not fetch automatically after failure, and allows explicit read retry', async () => {
    const json = vi.fn().mockRejectedValueOnce(new Error('sensitive internal details')).mockResolvedValue({ items: [taskRow] });
    mount(task, json); await screen.findByText(/原记录当前不可读/);
    expect(screen.queryByText('sensitive internal details')).toBeNull(); expect(json).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: '重新读取原记录' }));
    await screen.findByText('原记录 task-1 · v2 · COMPLETED'); expect(json).toHaveBeenCalledTimes(2);
  });
  it('honors denial with no fallback interface', async () => {
    const state = mount(task, vi.fn().mockRejectedValue(new ApiError({ status: 403, code: 'DENIED', message: 'denied' })));
    await screen.findByText(/原媒体服务拒绝读取/); expect(state.json).toHaveBeenCalledTimes(1);
  });
  it('coalesces repeated read clicks synchronously', async () => {
    const wait = deferred(), state = mount(task, vi.fn().mockReturnValue(wait.promise));
    fireEvent.click(screen.getByRole('button', { name: '重新读取原记录' }));
    fireEvent.click(screen.getByRole('button', { name: '重新读取原记录' })); expect(state.json).toHaveBeenCalledTimes(1);
    await act(async () => wait.resolve({ items: [taskRow] }));
  });
  it.each(['identity', 'target', 'client', 'busy', 'permission', 'unmount'])('discards late results across %s including ABA', async change => {
    const wait = deferred(), state = mount(task, vi.fn().mockReturnValue(wait.promise));
    await act(async () => {});
    if (change === 'unmount') state.unmount();
    else {
      const patch = change === 'identity' ? { identity: 'other' } : change === 'target' ? { target: candidate } : change === 'client' ? { transport: { json: vi.fn() } } : change === 'busy' ? { busy: true } : { isCurrent: () => false };
      state.rerender(<TaskOwnerResult {...state.props} {...patch} />);
      state.rerender(<TaskOwnerResult {...state.props} />);
    }
    await act(async () => wait.resolve({ items: [taskRow] }));
    expect(screen.queryByLabelText('已核对原媒体记录')).toBeNull(); expect(state.json).toHaveBeenCalledTimes(1);
  });
});


describe('original result identity and StrictMode', () => {
  it('opens once during StrictMode mount without needing a manual retry', async () => {
    const wait = deferred(), json = vi.fn().mockReturnValue(wait.promise);
    render(<StrictMode><TaskOwnerResult projectId="project" identity="identity" target={task} transport={{ json }} busy={false} isCurrent={() => true} read={work => work()} onClose={() => {}} /></StrictMode>);
    await act(async () => {}); expect(json).toHaveBeenCalledTimes(1);
    await act(async () => wait.resolve({ items: [taskRow] }));
    expect(screen.getByText('原记录 task-1 · v2 · COMPLETED')).toBeTruthy();
  });
  it.each([{ novel_id: 'foreign' }, { scope: { mode: 'local', novel_id: 'foreign' } }, { scope: undefined }, { scope: { mode: 'collaboration', novel_id: 'project', branch_id: 'foreign' } }])('refuses foreign or absent original scope %j', patch => {
    expect(() => exactMediaOwnerRecord({ items: [{ ...taskRow, ...patch }] }, task, 'project')).toThrow();
  });
  it('accepts only the exact collaboration scope', () => {
    const scope = { workspaceId: 'workspace', projectId: 'project', storylineId: 'storyline', branchId: 'branch' };
    const row = { ...taskRow, scope: { mode: 'collaboration', novel_id: 'project', workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch' } };
    expect(exactMediaOwnerRecord({ items: [row] }, task, 'project', scope)).toEqual(row);
    expect(() => exactMediaOwnerRecord({ items: [row] }, task, 'project', { ...scope, branchId: 'other' })).toThrow();
  });
  it('shows an explicit stale-source warning from the original owner', async () => {
    mount(candidate, vi.fn().mockResolvedValue({ items: [{ ...candidateRow, stale: true }] }));
    await screen.findByText(/原服务报告来源已过期/);
  });
});
