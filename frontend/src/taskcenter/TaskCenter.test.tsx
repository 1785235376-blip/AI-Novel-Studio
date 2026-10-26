// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { TaskCenter } from './TaskCenter';
import { reviewInboxProjection, taskCenterProjection } from './taskCenterContract';
import {
  FIXTURE_PROJECT, reviewInboxBatchItem, reviewInboxItem, tasksResponse, projectedFormalTask, projectedTask,
} from './taskCenterFixtures';
import type { TaskCenterClient, TaskCenterTasksProjection } from './taskCenterTypes';
import { useTaskCenter, type TaskCenterControllerProps } from './useTaskCenter';

const tasks = (overrides: Record<string, unknown> = {}): TaskCenterTasksProjection =>
  taskCenterProjection(tasksResponse(overrides), FIXTURE_PROJECT);
const inbox = (overrides: Record<string, unknown> = {}) => reviewInboxProjection({
  items: [reviewInboxItem(), reviewInboxBatchItem()], total: 2, unavailable: [],
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
      status: 'COMPLETED' as const,
      results: [
        { domain: 'planning', id: 'proposal-1', status: 'SUCCEEDED' as const },
        { domain: 'planning', id: 'proposal-2', status: 'SUCCEEDED' as const },
      ], remaining: 0, retry: null, batch_semantics: 'PER_ITEM_CHECKPOINT' as const,
    })),
    ...patch,
  };
  return { client: client as unknown as TaskCenterClient, ...client };
}
const props = (client: TaskCenterClient, patch: Partial<TaskCenterControllerProps> = {}): TaskCenterControllerProps => ({
  identity: 'taskcenter-view', active: true, denied: false, busy: false, isCurrent: () => true,
  read: work => work(), mutate: work => work(), client, ...patch,
});
function View({ client, patch = {} }: { client: TaskCenterClient; patch?: Partial<TaskCenterControllerProps> }) {
  const controller = useTaskCenter(props(client, patch));
  return <TaskCenter controller={controller}/>;
}
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
const queryButton = (name: string | RegExp) => screen.queryByRole('button', { name });
const tab = (name: string | RegExp) => screen.getByRole('tab', { name }) as HTMLButtonElement;

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('task center view', () => {
  it('shows the owner stage labels and never invents a percentage or ETA', async () => {
    const { client } = fakeClient();
    const { container } = render(<View client={client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    expect(container.textContent).toContain('运行中');
    expect(container.textContent).toContain('RUNNING');
    expect(container.textContent).toContain('3 / 8 分块');
    expect(container.textContent).toContain('执行状态 · 原任务投影');
    expect(container.textContent).not.toContain('%');
    expect(container.textContent).not.toContain('剩余时间');
    expect(container.textContent).not.toContain('预计完成');
    cleanup();

    const withoutProgress = fakeClient({
      readTasks: vi.fn(async () => tasks({ items: [projectedTask({ progress: null })], unavailable: [] })),
    });
    const second = render(<View client={withoutProgress.client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    expect(second.container.textContent).toContain('进度未知（原服务未提供已完成/总数）');
    expect(second.container.textContent).toContain('原服务未报告可量化进度，因此不显示百分比或预计时间。');
  });

  it('renders a status the owner does not define as the honest UNKNOWN state', async () => {
    const { client } = fakeClient({
      readTasks: vi.fn(async () => tasks({ items: [projectedTask({ status: 'SOMETHING_NEW', stage_label: '未知阶段' })], unavailable: [] })),
    });
    const { container } = render(<View client={client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    expect(container.textContent).toContain('结果未知');
    expect(container.textContent).toContain('按结果未知处理（原状态 SOMETHING_NEW）');
    expect(container.textContent).toContain('原服务未给出确定状态，按“结果未知”显示；不会猜测进度或结果。');
    expect(container.textContent).toContain('原服务返回了未定义状态，已按“结果未知”处理，没有猜测成其他阶段。');
  });

  it('keeps execution and the review outcome in separate blocks', async () => {
    const { client } = fakeClient();
    const { container } = render(<View client={client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    expect(container.textContent).toContain('执行状态 · 原任务投影');
    expect(container.textContent).toContain('审核结果 · 统一审核收件箱');
    expect(container.textContent).toContain('尚未读取审核收件箱');
    fireEvent.click(tab('审核收件箱'));
    await screen.findByRole('article', { name: '审核项 media candidate-1' });
    expect(container.textContent).toContain('本页共 2 条审核项');
    expect(container.textContent).toContain('不代表交付');
    expect(container.textContent).not.toContain('已交付');
    expect(container.textContent).not.toContain('正式资产');
    expect(container.textContent).toContain('逐项 checkpoint');
  });

  it('never collapses an unreadable source into an empty queue', async () => {
    const denied = fakeClient({
      readTasks: vi.fn(async () => tasks({
        items: [], unavailable: [{ authority: 'exports', label: '导出任务', reason: 'SOURCE_UNAVAILABLE' }],
      })),
    });
    const view = render(<View client={denied.client}/>);
    await waitFor(() => expect(view.container.textContent).toContain('所有来源当前都不可读'));
    expect(view.container.textContent).toContain('导出任务（exports）当前不可读：SOURCE_UNAVAILABLE');
    expect(view.container.textContent).not.toContain('当前筛选下没有任务记录');
    cleanup();

    const empty = fakeClient({ readTasks: vi.fn(async () => tasks({ items: [], unavailable: [] })) });
    const emptyView = render(<View client={empty.client}/>);
    await waitFor(() => expect(emptyView.container.textContent).toContain('当前筛选下没有任务记录'));
    cleanup();

    const failed = fakeClient({
      readTasks: vi.fn(async () => { throw new ApiError({ status: 500, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }); }),
    });
    const failedView = render(<View client={failed.client}/>);
    await waitFor(() => expect(failedView.container.textContent).toContain('任务队列读取失败'));
    // [HERMIA-FE-20261024 M6] was: visible text contains the raw code. Now: the human message is shown, the raw code is
    // not visible text, and it is still exposed (exactly) as data-error-code for diagnostics.
    const taskAlert = failedView.container.querySelector('[data-error-code]');
    expect(taskAlert?.textContent).toBe('请求未完成。'); // [HERMIA-FE-20261024 M6-fix] exact sentence
    expect(failedView.container.textContent).not.toContain('STUDIO_REQUEST_FAILED');
    expect(failedView.container.querySelector('[data-error-code]')?.getAttribute('data-error-code')).toBe('STUDIO_REQUEST_FAILED');
    expect(failedView.container.textContent).not.toContain('当前筛选下没有任务记录');
  });

  // [HERMIA-FE-20261024 M6-fix] ReviewInbox alert matches TaskList: human sentence only, raw code only in data-error-code.
  it('review inbox read failure shows human text and keeps the code only in data-error-code', async () => {
    const failed = fakeClient({
      readInbox: vi.fn(async () => { throw new ApiError({ status: 500, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }); }),
    });
    const view = render(<View client={failed.client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.click(tab('审核收件箱'));
    await waitFor(() => expect(view.container.querySelector('[data-error-code]')).not.toBeNull());
    const alert = view.container.querySelector('[data-error-code]');
    expect(alert?.getAttribute('data-error-code')).toBe('STUDIO_REQUEST_FAILED');
    expect(alert?.textContent).toBe('请求未完成。');
    expect(view.container.textContent).not.toContain('STUDIO_REQUEST_FAILED');
  });

  it('takes button availability from the owner actions only', async () => {
    const { client, cancelTask } = fakeClient();
    const { container } = render(<View client={client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    // media 没有注册 cancel：界面里不能出现取消按钮。
    expect(queryButton('请求取消原任务')).toBeNull();
    expect(container.textContent).toContain('当前来源没有通用取消接口');
    cleanup();

    const cancellable = fakeClient({
      readTasks: vi.fn(async () => tasks({
        items: [projectedTask({
          actions: ['open_source', 'cancel'],
          action_limits: {
            cancel: null, retry: 'SOURCE_PREFLIGHT_REQUIRED',
            resume: 'SOURCE_RECOVERY_REQUIRED', review: 'SOURCE_REVIEW_REQUIRED',
          },
        })], unavailable: [],
      })),
    });
    const view = render(<View client={cancellable.client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.click(button('请求取消原任务'));
    const confirm = screen.getByRole('region', { name: '确认取消原任务' });
    expect(confirm.textContent).toContain('取消只作用于这一条原任务');
    expect(confirm.textContent).toContain('media · media-task-1');
    fireEvent.click(within(confirm).getByRole('button', { name: '确认请求取消' }));
    await waitFor(() => expect(cancellable.cancelTask).toHaveBeenCalledTimes(1));
    expect(cancellable.cancelTask.mock.calls[0][0]).toMatchObject({ authority: 'media', id: 'media-task-1' });
    // 取消请求已发送、终止未确认：绝不显示干净的"已取消"。
    await waitFor(() => expect(view.container.textContent).toContain('取消请求已发送/待确认'));
    expect(view.container.textContent).toContain('原任务尚未确认终止');
    expect(view.container.textContent).toContain('“重试生成”和“恢复原任务”是两个独立动作');
    void cancelTask;
  });

  it('emits a navigation callback instead of navigating, and never for a formal receipt', async () => {
    const onNavigate = vi.fn();
    const { client } = fakeClient({
      readTasks: vi.fn(async () => tasks({ items: [projectedTask(), projectedFormalTask()], unavailable: [] })),
    });
    render(<View client={client} patch={{ onNavigate }}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.click(button('定位原任务结果'));
    expect(onNavigate).toHaveBeenCalledWith(expect.objectContaining({
      queue: 'TASKS', task_id: 'media-task-1',
      source: expect.objectContaining({ kind: 'feature', id: 'media-task-1' }),
    }));
    // 正式来源回执没有来源指针：既没有按钮，也不发出导航。
    const formal = screen.getByRole('article', { name: '任务 review_inbox receipt-1' });
    expect(within(formal).queryByRole('button', { name: '定位原任务结果' })).toBeNull();
    expect(formal.textContent).toContain('不会伪造导航目标');
    expect(onNavigate).toHaveBeenCalledTimes(1);
  });

  it('shows the exact batch item set before submitting and keeps per-item results', async () => {
    const { client } = fakeClient();
    render(<View client={client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.click(tab('审核收件箱'));
    await screen.findByRole('article', { name: '审核项 planning proposal-1' });
    expect(screen.queryByRole('button', { name: /批量/ })).toBeNull();
    const planning = screen.getByRole('article', { name: '审核项 planning proposal-1' });
    fireEvent.click(within(planning).getByLabelText('加入批量集合'));
    const batch = screen.getByRole('region', { name: '批量审核' });
    expect(batch.textContent).toContain('planning:proposal-1');
    expect(batch.textContent).toContain('v5');
    fireEvent.click(within(batch).getByRole('button', { name: '批量驳回本次候选（1 项）' }));
    await waitFor(() => expect(client.reviewBatch).toHaveBeenCalledWith({
      items: [{ domain: 'planning', id: 'proposal-1', action: 'reject', expected_version: 5 }],
    }));
    await waitFor(() => expect(screen.getByRole('region', { name: '批量驳回本次候选逐项结果' })).toBeTruthy());
  });

  it('renders the owner stages, stale source and unreadable source distinctly', async () => {
    const { client } = fakeClient({
      readTasks: vi.fn(async () => tasks({
        items: [
          projectedTask({ id: 'queued-1', status: 'QUEUED', stage_label: '排队', progress: null }),
          projectedTask({ id: 'preparing-1', status: 'PREPARED', stage_label: '准备就绪', progress: null }),
          projectedTask({ id: 'review-1', status: 'AWAITING_REVIEW', stage_label: '待审核', progress: null }),
          projectedTask({ id: 'failed-1', status: 'FAILED', stage_label: '失败', progress: null, error_code: 'TIMEOUT' }),
          projectedTask({ id: 'cancelling-1', status: 'CANCELLING', stage_label: '取消中', progress: null }),
          projectedTask({ id: 'cancelled-1', status: 'CANCELLED', stage_label: '已取消', progress: null }),
          projectedTask({ id: 'stale-1', status: 'STALE', stage_label: '来源过期', progress: null, stale: true }),
        ],
        unavailable: [{ authority: 'agents', label: 'Agent 任务', reason: 'SOURCE_UNAVAILABLE' }],
      })),
    });
    const { container } = render(<View client={client}/>);
    await screen.findByRole('article', { name: '任务 media queued-1' });
    for (const stage of ['排队', '准备就绪', '待审核', '失败', '取消中', '已取消', '来源过期']) {
      expect(container.textContent).toContain(stage);
    }
    expect(container.textContent).toContain('TIMEOUT');
    // 源状态 STALE 与 stale 布尔标记是两件事，两个都要显示。
    expect(screen.getByRole('article', { name: '任务 media stale-1' }).textContent).toContain('来源已变化');
    // 不可读来源与"没有任务"是两回事。
    expect(container.textContent).toContain('Agent 任务（SOURCE_UNAVAILABLE）');
    expect(container.textContent).toContain('这里不是完整队列');
    expect(container.textContent).not.toContain('当前筛选下没有任务记录');
    expect(container.textContent).not.toContain('当前筛选下没有可统计的任务状态');
  });

  it('keeps cancelling one original task separate from transfers and from other tasks', async () => {
    const cancellable = fakeClient({
      readTasks: vi.fn(async () => tasks({
        items: [projectedTask({
          actions: ['open_source', 'cancel'],
          action_limits: {
            cancel: null, retry: 'SOURCE_PREFLIGHT_REQUIRED',
            resume: 'SOURCE_RECOVERY_REQUIRED', review: 'SOURCE_REVIEW_REQUIRED',
          },
        })], unavailable: [],
      })),
    });
    render(<View client={cancellable.client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.click(button('请求取消原任务'));
    const confirm = screen.getByRole('region', { name: '确认取消原任务' });
    expect(confirm.textContent).toContain('不影响其他任务、已发送的传输或已完成的结果');
    expect(confirm.textContent).toContain('原任务服务可能已经进入终态');
  });

  it('takes the review buttons from allowed_actions and suppresses them during owner recovery', async () => {
    const { client, reviewItem } = fakeClient();
    render(<View client={client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.click(tab('审核收件箱'));
    const mediaArticle = await screen.findByRole('article', { name: '审核项 media candidate-1' });
    fireEvent.click(within(mediaArticle).getByRole('button', { name: '查看候选详情' }));
    const detail = screen.getByRole('region', { name: '审核项详情 media candidate-1' });
    expect(within(detail).getByRole('button', { name: '采纳为正式结果' })).toBeTruthy();
    expect(within(detail).getByRole('button', { name: '驳回本次候选' })).toBeTruthy();
    expect(within(detail).queryByRole('button', { name: '重开审核' })).toBeNull();
    expect(detail.textContent).toContain('提交决定时会绑定当前候选版本 v3');
    fireEvent.click(within(detail).getByRole('button', { name: '采纳为正式结果' }));
    await waitFor(() => expect(reviewItem).toHaveBeenCalledWith({ domain: 'media', id: 'candidate-1', version: 3 }, 'approve'));
    await waitFor(() => expect((within(screen.getByRole('region', { name: '审核项详情 media candidate-1' }))
      .getByRole('button', { name: '采纳为正式结果' }) as HTMLButtonElement).disabled).toBe(true));
    expect(screen.getByRole('region', { name: '审核项详情 media candidate-1' }).textContent)
      .toContain('已提交过决定');
    cleanup();

    // 领域要求自己的恢复流程：普通审核按钮必须消失。
    const recovering = fakeClient({
      readInbox: vi.fn(async () => inbox({
        items: [reviewInboxItem({ status: 'APPROVING', recovery_state: 'RESUME_APPROVAL' })], total: 1,
      })),
    });
    render(<View client={recovering.client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.click(tab('审核收件箱'));
    fireEvent.click(within(await screen.findByRole('article', { name: '审核项 media candidate-1' }))
      .getByRole('button', { name: '查看候选详情' }));
    const recovery = screen.getByRole('region', { name: '审核项详情 media candidate-1' });
    expect(within(recovery).queryByRole('button', { name: '采纳为正式结果' })).toBeNull();
    expect(recovery.textContent).toContain('不会自动重试、恢复或批准');
    cleanup();

    // allowed_actions 为空：只读。
    const readOnly = fakeClient({
      readInbox: vi.fn(async () => inbox({ items: [reviewInboxItem({ allowed_actions: [] })], total: 1 })),
    });
    render(<View client={readOnly.client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.click(tab('审核收件箱'));
    fireEvent.click(within(await screen.findByRole('article', { name: '审核项 media candidate-1' }))
      .getByRole('button', { name: '查看候选详情' }));
    expect(screen.getByRole('region', { name: '审核项详情 media candidate-1' }).textContent)
      .toContain('原 owner 没有声明可用的审核动作，因此这里没有按钮');
  });

  it('keeps the task filters explicit and local for module/status', async () => {
    const { client, readTasks } = fakeClient({
      readTasks: vi.fn(async () => tasks({
        items: [
          projectedTask(),
          projectedTask({ id: 'style-task-1', authority: 'author_generation', feature: 'style_dna_v2', status: 'FAILED', stage_label: '失败' }),
        ], unavailable: [],
      })),
    });
    render(<View client={client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.change(screen.getByLabelText('状态（本地过滤）'), { target: { value: 'FAILED' } });
    expect(screen.getByText(/筛选已修改，尚未应用/)).toBeTruthy();
    fireEvent.click(button('应用筛选并读取'));
    await waitFor(() => expect(screen.queryByRole('article', { name: '任务 media media-task-1' })).toBeNull());
    expect(screen.getByRole('article', { name: '任务 author_generation style-task-1' })).toBeTruthy();
    // 本地状态过滤不产生新请求（端点没有状态参数，不能伪造）。
    expect(readTasks).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByLabelText('只看失败或结果未知'));
    fireEvent.click(button('应用筛选并读取'));
    await waitFor(() => expect(readTasks).toHaveBeenCalledTimes(2));
    expect(readTasks).toHaveBeenLastCalledWith({ q: '', failed_only: true }, expect.any(AbortSignal));
  });
});
