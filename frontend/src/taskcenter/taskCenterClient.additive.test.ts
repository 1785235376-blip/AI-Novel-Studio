// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { ledgerRow, receiptTask } from './taskCostReceiptFixtures';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { studioTransport } from '../creative/studioClient';
import { createTaskCostReceiptClient } from './taskCostReceiptClient';
import { FIXTURE_PROJECT } from './taskCenterFixtures';

beforeEach(() => { vi.unstubAllGlobals(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('read-only task receipt transport', () => {
  it('uses only the original scoped history GET, preserves signal, never reads media', async () => {
    const json = vi.fn().mockResolvedValue({ ledger: [ledgerRow()], decisions: [] });
    const client = createTaskCostReceiptClient(FIXTURE_PROJECT, { json });
    const signal = new AbortController().signal;
    expect(await client.readCostReceipt!(receiptTask, signal)).toMatchObject({ kind: 'RECEIPT' });
    expect(json).toHaveBeenCalledWith(`/api/novels/${FIXTURE_PROJECT}/experimental/model-broker/history`, 'GET', undefined, signal);
    expect(await client.readCostReceipt!({ ...receiptTask, authority: 'media' })).toMatchObject({ kind: 'UNKNOWN', reason: 'UNSUPPORTED' });
    expect(await client.readCostReceipt!({ ...receiptTask, id: '' })).toMatchObject({ kind: 'UNKNOWN', reason: 'INVALID' });
    expect(json).toHaveBeenCalledTimes(1);
  });
  it.each([401, 403, 404, 500])('keeps owner read failure %s unknown without fallback or raw text', async status => {
    const json = vi.fn().mockRejectedValue(new ApiError({ status, code: 'SECRET', message: 'private upstream text' }));
    const client = createTaskCostReceiptClient(FIXTURE_PROJECT, { json });
    expect(await client.readCostReceipt!(receiptTask)).toEqual({ kind: 'UNKNOWN', reason: 'UNREADABLE' });
    expect(json).toHaveBeenCalledTimes(1);
  });
  it('rejects foreign captured scope before reading and rejects foreign returned scope', async () => {
    const json = vi.fn().mockResolvedValue({ ledger: [ledgerRow()] });
    const client = createTaskCostReceiptClient(FIXTURE_PROJECT, { json }, { workspaceId: 'w', projectId: 'foreign', storylineId: 's', branchId: 'b' });
    expect(await client.readCostReceipt!(receiptTask)).toEqual({ kind: 'UNKNOWN', reason: 'UNREADABLE' });
    expect(json).not.toHaveBeenCalled();
    const scoped = createTaskCostReceiptClient(FIXTURE_PROJECT, { json }, { workspaceId: 'w', projectId: FIXTURE_PROJECT, storylineId: 's', branchId: 'b' });
    expect(await scoped.readCostReceipt!(receiptTask)).toEqual({ kind: 'UNKNOWN', reason: 'INVALID' });
  });
});

it('receipt history retains the existing captured actor session and branch transport', async () => {
  const scope = { workspaceId: 'w', projectId: FIXTURE_PROJECT, storylineId: 's', branchId: 'b' };
  const context = { sessionToken: 'session-original', scope };
  const fetch = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ ledger: [ledgerRow({ scope: {
    mode: 'collaboration', novel_id: FIXTURE_PROJECT, workspace_id: 'w', storyline_id: 's', branch_id: 'b',
  } })] }), { status: 200 }));
  vi.stubGlobal('fetch', fetch);
  const client = createTaskCostReceiptClient(FIXTURE_PROJECT, studioTransport(context), scope);
  expect(await client.readCostReceipt!(receiptTask)).toMatchObject({ kind: 'RECEIPT' });
  expect(fetch).toHaveBeenCalledTimes(1);
  const init = fetch.mock.calls[0]?.[1] as RequestInit;
  expect(init.method).toBe('GET');
  expect(new Headers(init.headers).get('X-Session-Token')).toBe('session-original');
  expect(new Headers(init.headers).get('X-Branch-Id')).toBe('b');
});
