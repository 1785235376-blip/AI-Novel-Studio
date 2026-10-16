// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TaskCenterPanel } from './TaskCenter';
import { FIXTURE_PROJECT, projectedTask, tasksResponse } from './taskCenterFixtures';
import { ledgerRow, receiptTask } from './taskCostReceiptFixtures';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
afterEach(cleanup);

it('the real panel wires its independent companion to the same explicit read-only transport', async () => {
  const calls: { url: string; method: string }[] = [];
  const transport: StudioGraphTransport = { async json<T>(url: string, method = 'GET'): Promise<T> {
    calls.push({ url, method });
    if (url.includes('/workspace/tasks?')) return tasksResponse({ items: [projectedTask({ ...receiptTask, status: 'COMPLETED', stage_label: '已完成' })], unavailable: [] }) as T;
    if (url.endsWith('/model-broker/history')) return { ledger: [ledgerRow()], decisions: [] } as T;
    throw new Error('Unexpected transport path');
  } };
  const mutate = vi.fn();
  render(<TaskCenterPanel projectId={FIXTURE_PROJECT} transport={transport} identity="companion-panel" active denied={false} busy={false} isCurrent={() => true} read={work => work()} mutate={mutate} />);
  await screen.findByRole('article', { name: '任务 author_generation job-1' });
  expect(calls).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: '查看原任务费用回执' }));
  await screen.findByText('1.000001 USD（1000001 micro-USD）');
  expect(calls).toHaveLength(2);
  expect(calls[1]).toEqual({ url: `/api/novels/${FIXTURE_PROJECT}/experimental/model-broker/history`, method: 'GET' });
  expect(calls.every(call => call.method === 'GET')).toBe(true); expect(mutate).not.toHaveBeenCalled();
});
