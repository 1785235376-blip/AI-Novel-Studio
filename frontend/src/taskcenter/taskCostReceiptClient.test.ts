import { expect, it, vi } from 'vitest';
import { createTaskCenterClient } from './taskCenterClient';
import { createTaskCostReceiptClient } from './taskCostReceiptClient';
import { ledgerRow, receiptTask } from './taskCostReceiptFixtures';
import { FIXTURE_PROJECT } from './taskCenterFixtures';

it('keeps the receipt reader on a genuinely independent interface', async () => {
  const json = vi.fn().mockResolvedValue({ ledger: [ledgerRow()], decisions: [] });
  const owner = createTaskCenterClient(FIXTURE_PROJECT, { json });
  const companion = createTaskCostReceiptClient(FIXTURE_PROJECT, { json });
  expect(Reflect.ownKeys(owner)).toEqual(['readTasks', 'readInbox', 'cancelTask', 'reviewItem', 'reviewBatch']);
  expect('readCostReceipt' in owner).toBe(false);
  expect(Object.getOwnPropertyDescriptor(owner, 'readCostReceipt')).toBeUndefined();
  expect(Reflect.ownKeys(companion)).toEqual(['readCostReceipt']);
  expect(await companion.readCostReceipt(receiptTask)).toMatchObject({ kind: 'RECEIPT' });
  expect(json).toHaveBeenCalledTimes(1);
  expect(Reflect.ownKeys(owner)).toEqual(['readTasks', 'readInbox', 'cancelTask', 'reviewItem', 'reviewBatch']);
});
