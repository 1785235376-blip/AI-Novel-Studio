import { describe, expect, it } from 'vitest';
import { receiptAmount, taskCostReceipt, taskRecoveryGuidance } from './taskCostReceiptHelpers';
import { taskCenterProjection } from './taskCenterContract';
import { FIXTURE_PROJECT, projectedTask, tasksResponse } from './taskCenterFixtures';

import { ledgerRow, receiptTask, receiptScope } from './taskCostReceiptFixtures';
const decode = (ledger: unknown) => taskCostReceipt({ ledger }, receiptTask, FIXTURE_PROJECT, receiptScope);
describe('exact original-job cost receipt contract', () => {
  it('matches only exact original identity, ignores unrelated rows, and preserves units', () => {
    expect(decode([ledgerRow({ job_id: 'job-10' }), ledgerRow()])).toMatchObject({ kind: 'RECEIPT', jobId: 'job-1', actual: 1000001, estimate: 1200001, priceVersion: 2, synthetic: false });
    expect(decode([ledgerRow({ job_id: 'job-10' })])).toEqual({ kind: 'UNKNOWN', reason: 'MISSING' });
    expect(decode([ledgerRow(), ledgerRow({ id: 'reservation-2' })])).toEqual({ kind: 'UNKNOWN', reason: 'AMBIGUOUS' });
    expect(taskCostReceipt({ ledger: [ledgerRow()] }, { ...receiptTask, authority: 'media' }, FIXTURE_PROJECT, receiptScope)).toEqual({ kind: 'UNKNOWN', reason: 'UNSUPPORTED' });
  });
  it('retains UNKNOWN_UPSTREAM, null and explicit synthetic/released zero separately', () => {
    expect(decode([ledgerRow({ status: 'UNKNOWN_UPSTREAM', cost_state: 'UNKNOWN_UPSTREAM', actual_microusd: null })])).toMatchObject({ kind: 'RECEIPT', actual: null, costState: 'UNKNOWN_UPSTREAM' });
    expect(decode([ledgerRow({ status: 'RELEASED', cost_state: 'NOT_DISPATCHED', dispatched: false, actual_microusd: 0 })])).toMatchObject({ kind: 'RECEIPT', actual: 0 });
    expect(decode([ledgerRow({ cost_state: 'KNOWN_SYNTHETIC_ZERO', actual_microusd: 0, reserve_microusd: 0,
      price: { currency: 'USD', reserve_microusd: 0, source: 'Builtin deterministic adapter; no provider invoice', actual_known_zero: true, applicability: 'synthetic_provider_fee_only' } })])).toMatchObject({ kind: 'RECEIPT', actual: 0, synthetic: true });
    expect(decode([ledgerRow({ status: 'DISPATCHED', cost_state: 'UNKNOWN', actual_microusd: null, reserve_microusd: null, price: null })])).toMatchObject({ kind: 'RECEIPT', actual: null, estimate: null, synthetic: null });
    expect(receiptAmount(null)).toBe('未知');
    expect(receiptAmount(0)).toBe('0.000000 USD（0 micro-USD）');
    expect(receiptAmount(1)).toBe('0.000001 USD（1 micro-USD）');
    expect(receiptAmount(1000000000000)).toBe('1000000.000000 USD（1000000000000 micro-USD）');
  });
  it.each([
    { novel_id: 'other' }, { scope: { ...receiptScope, branch_id: 'foreign' } }, { currency: 'EUR' },
    { actual_microusd: undefined }, { actual_microusd: NaN }, { actual_microusd: true }, { actual_microusd: -1 },
    { reserve_microusd: 0.5 }, { reserve_microusd: 1e13 }, { provider_id: '<script>' }, { price: undefined },
    { status: 'UNKNOWN_UPSTREAM', cost_state: 'UNKNOWN_UPSTREAM' },
    { cost_state: 'KNOWN_SYNTHETIC_ZERO', actual_microusd: 0 },
    { status: 'RELEASED', cost_state: 'NOT_DISPATCHED', actual_microusd: 0 },
    { status: 'FUTURE_STATE' }, { status: 'toString' }, { price: null },
    { dispatched: false }, { status: 'DISPATCHED', cost_state: 'UNKNOWN', actual_microusd: null }, { price: { currency: 'USD', reserve_microusd: 1200001, source: '\nsecret' } },
  ])('fails closed for malformed/mismatched receipt %j', patch => {
    expect(decode([ledgerRow(patch)])).toEqual({ kind: 'UNKNOWN', reason: 'INVALID' });
  });
  it('rejects unreadable shapes and bounded history overflow', () => {
    for (const value of [null, {}, [null], Array.from({ length: 101 }, () => ledgerRow())]) {
      expect(decode(value)).toEqual({ kind: 'UNKNOWN', reason: 'INVALID' });
    }
  });
  it('uses owner policy and actual progress without promising checkpoint resume', () => {
    const task = taskCenterProjection(tasksResponse({ items: [projectedTask()] }), FIXTURE_PROJECT).items[0];
    expect(taskRecoveryGuidance(task)).toContain('已完成 3 / 8 分块；这不证明存在持久检查点');
    expect(taskRecoveryGuidance({ ...task, progress: null })).toContain('未报告可量化进度');
    expect(taskRecoveryGuidance(task)).toContain('重试需原服务预检');
  });
});
