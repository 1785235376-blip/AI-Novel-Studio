import { ledgerRow, receiptTask } from './taskCostReceiptFixtures';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type CollaborationContext } from '../api';
import { studioTransport } from '../creative/studioClient';
import { createTaskCenterClient } from './taskCenterClient';
import {
  FIXTURE_PROJECT, FIXTURE_REVISION, batchReceipt, cancelReceipt, reviewInboxBatchItem, reviewInboxItem,
  reviewInboxResponse, tasksResponse,
} from './taskCenterFixtures';

/** 协议夹具只证明客户端接缝，不构成运行时验收。 */
const tasksBase = `/api/novels/${FIXTURE_PROJECT}/experimental/workspace/tasks`;
const inboxBase = `/api/novels/${FIXTURE_PROJECT}/experimental/review-inbox`;
const reviewRequest = { domain: 'planning', id: 'proposal-1', action: 'reject', expected_version: 5 } as const;

async function refusalOf(work: Promise<unknown>): Promise<ApiError> {
  try { await work; } catch (reason) { return reason as ApiError; }
  throw new Error('expected this call to be refused');
}

beforeEach(() => { vi.unstubAllGlobals(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('task center client seam', () => {
  it('exposes original owner operations plus the read-only receipt companion', async () => {
    const json = vi.fn()
      .mockResolvedValueOnce(tasksResponse()).mockResolvedValueOnce(cancelReceipt())
      .mockResolvedValueOnce(reviewInboxResponse()).mockResolvedValueOnce({ status: 'APPROVED' })
      .mockResolvedValueOnce(batchReceipt());
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json });
    expect(Object.keys(client)).toEqual(['readCostReceipt', 'readTasks', 'readInbox', 'cancelTask', 'reviewItem', 'reviewBatch']);

    const tasks = await client.readTasks({ q: '', failed_only: false });
    expect(json).toHaveBeenNthCalledWith(1, `${tasksBase}?q=&failed_only=false`, 'GET', undefined, undefined);
    expect(tasks.items[0].authority).toBe('media');

    const cancelled = await client.cancelTask({ authority: 'media', id: 'media-task-1', revision: FIXTURE_REVISION });
    expect(json).toHaveBeenNthCalledWith(2, `${tasksBase}/media/media-task-1/cancel`, 'POST',
      { expected_revision: FIXTURE_REVISION }, undefined);
    expect(cancelled.cancellation_requested).toBe(true);
    expect(cancelled.termination_confirmed).toBe(false);

    const inbox = await client.readInbox({ domain: 'planning', status: 'REVIEW', search: '提案' });
    expect(json).toHaveBeenNthCalledWith(3,
      `${inboxBase}?domain=planning&status=REVIEW&search=${encodeURIComponent('提案')}`, 'GET', undefined, undefined);
    expect(inbox.batch_semantics).toBe('PER_ITEM_CHECKPOINT');
    expect(inbox.unavailable).toEqual([{ domain: 'legacy_canon', reason: 'ORIGINAL_DOMAIN_ACCESS_REQUIRED' }]);

    const reviewed = await client.reviewItem(inbox.items[0], 'approve');
    expect(json).toHaveBeenNthCalledWith(4, `${inboxBase}/media/candidate-1/approve`, 'POST', { expected_version: 3 }, undefined);
    expect(reviewed).toEqual({ domain: 'media', id: 'candidate-1', action: 'approve', accepted: true });

    const batch = await client.reviewBatch({ items: [{ ...reviewRequest }] });
    expect(json).toHaveBeenNthCalledWith(5, `${inboxBase}/batch`, 'POST', { items: [{ ...reviewRequest }] }, undefined);
    expect(batch.results.map(row => row.status)).toEqual(['SUCCEEDED', 'FAILED']);
    expect(batch.retry).toBe('REFRESH_AND_SELECT_FAILED_ITEMS');
  });

  it('refuses invalid local requests before they reach the original owner', async () => {
    const json = vi.fn();
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json });
    const cancels = [
      { authority: 'media', id: 'media-task-1', revision: '' },
      { authority: 'media', id: 'media-task-1', revision: 'A'.repeat(64) },
      { authority: 'media', id: 'media-task-1', revision: 'a'.repeat(63) },
    ];
    for (const candidate of cancels) {
      const caught = await refusalOf(client.cancelTask(candidate));
      expect(caught.problem.code).toBe('TASK_CENTER_CANCEL_LOCAL_INVALID');
    }
    // 路由 Literal 之外的动作用于原领域自己的界面，绝不从这里发出。
    const unroutable = await refusalOf(client.reviewItem({ domain: 'media', id: 'candidate-1', version: 3 },
      'archive' as never));
    expect(unroutable.problem.code).toBe('REVIEW_INBOX_ACTION_LOCAL_INVALID');
    const duplicate = await refusalOf(client.reviewBatch({ items: [{ ...reviewRequest }, { ...reviewRequest }] }));
    expect(duplicate.problem.code).toBe('REVIEW_INBOX_BATCH_LOCAL_INVALID');
    const zeroVersion = await refusalOf(client.reviewItem({ domain: 'media', id: 'candidate-1', version: 0 }, 'approve'));
    expect(zeroVersion.problem.code).toBe('REVIEW_INBOX_ACTION_LOCAL_INVALID');
    expect(json).not.toHaveBeenCalled();
  });

  it('bounds the query parameters the owner itself bounds', async () => {
    const json = vi.fn();
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json });
    expect((await refusalOf(client.readTasks({ q: 'x'.repeat(161), failed_only: true }))).problem.code)
      .toBe('TASK_CENTER_QUERY_LOCAL_INVALID');
    expect((await refusalOf(client.readInbox({ domain: '', status: '', search: 'x'.repeat(401) }))).problem.code)
      .toBe('REVIEW_INBOX_QUERY_LOCAL_INVALID');
    expect((await refusalOf(client.readInbox({ domain: 'Planning', status: '', search: '' }))).problem.code)
      .toBe('REVIEW_INBOX_QUERY_LOCAL_INVALID');
    expect(json).not.toHaveBeenCalled();
  });

  it('maps the original owner error codes to bounded user text', async () => {
    const json = vi.fn();
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json });
    const cases: [ApiError, string, string][] = [
      [new ApiError({ status: 409, code: 'EXPERIMENTAL_VERSION_CONFLICT', message: 'raw conflict' }), 'EXPERIMENTAL_VERSION_CONFLICT', '版本已经变化'],
      [new ApiError({ status: 409, code: 'EXPERIMENTAL_SOURCE_STALE', message: 'raw stale' }), 'EXPERIMENTAL_SOURCE_STALE', '来源或任务状态已变化'],
      [new ApiError({ status: 404, code: 'EXPERIMENTAL_NOT_FOUND', message: 'raw missing' }), 'EXPERIMENTAL_NOT_FOUND', '当前不可用'],
      [new ApiError({ status: 422, code: 'EXPERIMENTAL_INVALID', message: 'raw invalid' }), 'EXPERIMENTAL_INVALID', '未接受本次操作'],
      [new ApiError({ status: 404, code: 'EXPERIMENTAL_FEATURE_DISABLED', message: 'raw flag' }), 'EXPERIMENTAL_FEATURE_DISABLED', '未启用'],
      [new ApiError({ status: 403, code: 'REVIEW_AUTHORITY_CHANGED', message: 'raw authority' }), 'REVIEW_AUTHORITY_CHANGED', '审核身份已经变化'],
    ];
    for (const [failure, code, text] of cases) {
      json.mockRejectedValueOnce(failure);
      const caught = await refusalOf(client.reviewItem({ domain: 'media', id: 'candidate-1', version: 3 }, 'approve'));
      expect(caught).toBeInstanceOf(ApiError);
      expect(caught.problem.code).toBe(code);
      expect(caught.problem.status).toBe(failure.status);
      expect(caught.message).toContain(text);
      expect(caught.message).not.toContain('raw');
    }
    json.mockRejectedValueOnce(new ApiError({ status: 500, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }));
    expect((await refusalOf(client.readTasks({ q: '', failed_only: false }))).message).toBe('请求未完成。');
    json.mockRejectedValueOnce(new ApiError({ status: 403, code: 'UNLISTED_CODE', message: 'raw denied' }));
    expect((await refusalOf(client.readInbox({ domain: '', status: '', search: '' }))).message).toContain('无权读取或操作');
  });

  it('refuses a response that is not the frozen projection', async () => {
    const json = vi.fn().mockResolvedValue({ ...tasksResponse(), executor: true });
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json });
    expect((await refusalOf(client.readTasks({ q: '', failed_only: false }))).problem.code)
      .toBe('TASK_CENTER_PROJECTION_INVALID');
    json.mockResolvedValue({ ...batchReceipt(), status: 'COMPLETED' });
    expect((await refusalOf(client.reviewBatch({ items: [{ ...reviewRequest }] }))).problem.code)
      .toBe('REVIEW_INBOX_BATCH_RESPONSE_INVALID');
    json.mockResolvedValue({ ...reviewInboxResponse(), approval_authority: 'UI' });
    expect((await refusalOf(client.readInbox({ domain: '', status: '', search: '' }))).problem.code)
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
  });

  it('captures the collaboration scope and rejects an unrelated captured project', async () => {
    const scope = { workspaceId: 'workspace', projectId: FIXTURE_PROJECT, storylineId: 'storyline', branchId: 'branch' };
    const json = vi.fn().mockResolvedValue(tasksResponse());
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json }, scope);
    scope.branchId = 'changed-after-capture';
    expect((await client.readTasks({ q: '', failed_only: false })).items).toHaveLength(1);

    const transport = vi.fn();
    const unrelated = createTaskCenterClient(FIXTURE_PROJECT, { json: transport }, { ...scope, projectId: 'other-project' });
    for (const call of [
      unrelated.readTasks({ q: '', failed_only: false }),
      unrelated.readInbox({ domain: '', status: '', search: '' }),
      unrelated.cancelTask({ authority: 'media', id: 'media-task-1', revision: FIXTURE_REVISION }),
      unrelated.reviewItem({ domain: 'media', id: 'candidate-1', version: 1 }, 'approve'),
      unrelated.reviewBatch({ items: [{ ...reviewRequest }] }),
    ]) {
      await expect(call).rejects.toThrow(ApiError);
    }
    expect(transport).not.toHaveBeenCalled();
  });

  it('sends the original session, branch and idempotency headers through the Studio transport', async () => {
    const projectId = 'studio / project';
    const scope: CollaborationContext['scope'] = { workspaceId: 'w', projectId, storylineId: 's', branchId: 'branch' };
    const calls: [string, RequestInit][] = [];
    // 收件箱项自带授权 scope：协作模式下必须逐字匹配捕获到的 workspace/storyline/branch。
    const captured = { mode: 'collaboration', novel_id: projectId, workspace_id: 'w', storyline_id: 's', branch_id: 'branch' };
    const inbox = reviewInboxResponse({
      items: [reviewInboxItem(), reviewInboxBatchItem()]
        .map(row => ({ ...row, novel_id: projectId, project: projectId, scope: captured })),
    });
    const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
      calls.push([url, init]);
      return {
        ok: true, status: 200,
        json: async () => url.endsWith('/batch') ? batchReceipt()
          : url.includes('/tasks?') ? tasksResponse()
            : url.includes('/cancel') ? cancelReceipt() : inbox,
      };
    });
    vi.stubGlobal('fetch', fetchMock);
    const client = createTaskCenterClient(projectId, studioTransport({ sessionToken: 'session-original', scope }), scope);
    await client.readTasks({ q: 'a b', failed_only: true });
    await client.cancelTask({ authority: 'media', id: 'media-task-1', revision: FIXTURE_REVISION });
    await client.readInbox({ domain: 'media', status: '', search: '' });
    const base = `/api/novels/${encodeURIComponent(projectId)}/experimental`;
    expect(calls.map(([url]) => url)).toEqual([
      `${base}/workspace/tasks?q=a+b&failed_only=true`,
      `${base}/workspace/tasks/media/media-task-1/cancel`,
      `${base}/review-inbox?domain=media`,
    ]);
    expect(calls.map(([, init]) => init.method)).toEqual(['GET', 'POST', 'GET']);
    for (const [, init] of calls) {
      expect(init.headers).toMatchObject({
        'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch', 'X-Request-ID': expect.any(String),
      });
    }
    expect((calls[0][1].headers as Record<string, string>)['Idempotency-Key']).toBeUndefined();
    expect((calls[1][1].headers as Record<string, string>)['Idempotency-Key']).toEqual(expect.any(String));
    expect(JSON.parse(String(calls[1][1].body))).toEqual({ expected_revision: FIXTURE_REVISION });
  });
});


describe('read-only task receipt transport', () => {
  it('uses only the original scoped history GET, preserves signal, never reads media', async () => {
    const json = vi.fn().mockResolvedValue({ ledger: [ledgerRow()], decisions: [] });
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json });
    const signal = new AbortController().signal;
    expect(await client.readCostReceipt!(receiptTask, signal)).toMatchObject({ kind: 'RECEIPT' });
    expect(json).toHaveBeenCalledWith(`/api/novels/${FIXTURE_PROJECT}/experimental/model-broker/history`, 'GET', undefined, signal);
    expect(await client.readCostReceipt!({ ...receiptTask, authority: 'media' })).toMatchObject({ kind: 'UNKNOWN', reason: 'UNSUPPORTED' });
    expect(await client.readCostReceipt!({ ...receiptTask, id: '' })).toMatchObject({ kind: 'UNKNOWN', reason: 'INVALID' });
    expect(json).toHaveBeenCalledTimes(1);
  });
  it.each([401, 403, 404, 500])('keeps owner read failure %s unknown without fallback or raw text', async status => {
    const json = vi.fn().mockRejectedValue(new ApiError({ status, code: 'SECRET', message: 'private upstream text' }));
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json });
    expect(await client.readCostReceipt!(receiptTask)).toEqual({ kind: 'UNKNOWN', reason: 'UNREADABLE' });
    expect(json).toHaveBeenCalledTimes(1);
  });
  it('rejects foreign captured scope before reading and rejects foreign returned scope', async () => {
    const json = vi.fn().mockResolvedValue({ ledger: [ledgerRow()] });
    const client = createTaskCenterClient(FIXTURE_PROJECT, { json }, { workspaceId: 'w', projectId: 'foreign', storylineId: 's', branchId: 'b' });
    expect(await client.readCostReceipt!(receiptTask)).toEqual({ kind: 'UNKNOWN', reason: 'UNREADABLE' });
    expect(json).not.toHaveBeenCalled();
    const scoped = createTaskCenterClient(FIXTURE_PROJECT, { json }, { workspaceId: 'w', projectId: FIXTURE_PROJECT, storylineId: 's', branchId: 'b' });
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
  const client = createTaskCenterClient(FIXTURE_PROJECT, studioTransport(context), scope);
  expect(await client.readCostReceipt!(receiptTask)).toMatchObject({ kind: 'RECEIPT' });
  expect(fetch).toHaveBeenCalledTimes(1);
  const init = fetch.mock.calls[0]?.[1] as RequestInit;
  expect(init.method).toBe('GET');
  expect(new Headers(init.headers).get('X-Session-Token')).toBe('session-original');
  expect(new Headers(init.headers).get('X-Branch-Id')).toBe('b');
});
