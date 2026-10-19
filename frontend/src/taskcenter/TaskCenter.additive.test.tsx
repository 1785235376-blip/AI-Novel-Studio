// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { TaskCenter } from './TaskCenter';
import { reviewInboxProjection, taskCenterProjection } from './taskCenterContract';
import { FIXTURE_PROJECT, reviewInboxBatchItem, reviewInboxItem, tasksResponse, projectedTask } from './taskCenterFixtures';
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

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('original task receipt companion view', () => {
  it('shows receipt evidence and preserves task info on a later failed read', async () => {
    const { ledgerRow, receiptTask, receiptScope } = await import('./taskCostReceiptFixtures');
    const { taskCostReceipt } = await import('./taskCostReceiptHelpers');
    const fake = fakeClient({ readTasks: vi.fn(async () => tasks({ items: [projectedTask({ ...receiptTask, status: 'COMPLETED', stage_label: '已完成' })], unavailable: [] })) });
    const readCostReceipt = vi.fn().mockResolvedValueOnce(taskCostReceipt({ ledger: [ledgerRow()] }, receiptTask, FIXTURE_PROJECT, receiptScope))
      .mockResolvedValueOnce({ kind: 'UNKNOWN', reason: 'UNREADABLE' });
    const costReceiptClient = { readCostReceipt };
    const view = render(<View client={fake.client} patch={{ costReceiptClient }}/>);
    await screen.findByRole('article', { name: '任务 author_generation job-1' });
    expect(readCostReceipt).not.toHaveBeenCalled();
    fireEvent.click(button('查看原任务费用回执'));
    await screen.findByText('1.000001 USD（1000001 micro-USD）');
    expect(view.container.textContent).toContain('1.200001 USD（1200001 micro-USD）');
    expect(view.container.textContent).toContain('不是提供商发票或账单');
    expect(view.container.textContent).toContain('非合成价格记录');
    expect(view.container.textContent).toContain('Published price fixture');
    fireEvent.click(button('重新读取此费用回执'));
    await screen.findByText(/费用 UNKNOWN（未知）：原 broker 回执当前不可读/);
    expect(screen.queryByText('1.000001 USD（1000001 micro-USD）')).toBeNull();
    expect(screen.getByRole('article', { name: '任务 author_generation job-1' }).textContent).toContain('COMPLETED');
    expect(view.container.textContent).not.toContain('secret');
    fireEvent.click(button('关闭费用回执'));
    expect(screen.queryByRole('region', { name: '原任务费用回执 job-1' })).toBeNull();
    expect(fake.cancelTask).not.toHaveBeenCalled(); expect(fake.reviewItem).not.toHaveBeenCalled();
  });
  it('keeps unsupported media unknown with useful recovery guidance', async () => {
    const fake = fakeClient(); render(<View client={fake.client}/>);
    await screen.findByRole('article', { name: '任务 media media-task-1' });
    fireEvent.click(screen.getAllByRole('button', { name: '查看原任务费用回执' })[0]);
    await screen.findByText(/媒体等来源仍为未知/);
    expect(screen.getByRole('article', { name: '任务 media media-task-1' }).textContent).toContain('已完成 3 / 8 分块；这不证明存在持久检查点');
  });
});

it.each(['UNKNOWN_UPSTREAM', 'KNOWN_SYNTHETIC_ZERO'])('renders %s without implying an invoice or enabling retry', async costState => {
  const { ledgerRow, receiptTask, receiptScope } = await import('./taskCostReceiptFixtures');
  const { taskCostReceipt } = await import('./taskCostReceiptHelpers');
  const fake = fakeClient({ readTasks: vi.fn(async () => tasks({ items: [projectedTask(receiptTask)], unavailable: [] })) });
  const row = costState === 'UNKNOWN_UPSTREAM'
    ? ledgerRow({ status: 'UNKNOWN_UPSTREAM', cost_state: costState, actual_microusd: null })
    : ledgerRow({ cost_state: costState, actual_microusd: 0, reserve_microusd: 0,
      price: { currency: 'USD', reserve_microusd: 0, source: 'Synthetic fixture', applicability: 'synthetic_provider_fee_only', actual_known_zero: true } });
  const costReceiptClient = { readCostReceipt: vi.fn(async () => taskCostReceipt({ ledger: [row] }, receiptTask, FIXTURE_PROJECT, receiptScope)) };
  const view = render(<View client={fake.client} patch={{ costReceiptClient }}/>);
  await screen.findByRole('article', { name: '任务 author_generation job-1' });
  fireEvent.click(button('查看原任务费用回执'));
  await screen.findByText(costState);
  if (costState === 'UNKNOWN_UPSTREAM') expect(view.container.textContent).toContain('实际费用 UNKNOWN（未知），不代表免费');
  else {
    expect(screen.getAllByText('0.000000 USD（0 micro-USD）')).toHaveLength(2);
    expect(view.container.textContent).toContain('合成零费用不是提供商账单');
  }
  expect(screen.queryByRole('button', { name: /^(重试|恢复)/ })).toBeNull();
});
