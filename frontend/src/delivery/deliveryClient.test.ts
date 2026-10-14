// @vitest-environment jsdom
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { createDeliveryClient } from './deliveryClient';
import { deliveryReceipt, deliveryReceiptPage } from './deliveryContract';
import { DELIVERY_CODES, type DeliveryClient, type DeliveryReceipt } from './deliveryTypes';
import { useDelivery } from './useDelivery';

const PROJECT = 'novel-a';
const JOB = '11111111-1111-4111-8111-111111111111';

function wireJob(patch: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: JOB, novel_id: PROJECT, format: 'txt', status: 'queued',
    created_at: '2026-10-14T10:00:00Z', updated_at: '2026-10-14T10:00:00Z',
    progress: 0, progress_message: '排队中', retry_of: null, attempt: 1, cancel_requested: false,
    recovery_count: 0, snapshot_id: null, source_versions: {}, captured_at: null,
    missing_resources: [], result: null, error: null,
    ...patch,
  };
}

type Calls = { url: string; method: string | undefined; body: unknown; signal: AbortSignal | undefined; idempotencyKey: string | undefined }[];

function transport(handler: (url: string, method?: string) => unknown): { transport: StudioGraphTransport; calls: Calls } {
  const calls: Calls = [];
  const fake: StudioGraphTransport = {
    json: async <T,>(url: string, method?: string, body?: unknown, signal?: AbortSignal, idempotencyKey?: string): Promise<T> => {
      calls.push({ url, method, body, signal, idempotencyKey });
      return handler(url, method) as T;
    },
  };
  return { transport: fake, calls };
}

/** 把解码后的事实映射回原 owner 的线上形状（只保留线上下发过的键）。 */
function toWire(patch: Partial<DeliveryReceipt>): Record<string, unknown> {
  const wire: Record<string, unknown> = {};
  for (const key of ['id', 'format', 'status', 'created_at', 'updated_at', 'progress', 'progress_message', 'attempt', 'recovery_count'] as const) {
    if (patch[key] !== undefined) wire[key] = patch[key];
  }
  if (patch.raw_status !== undefined && patch.raw_status !== null) wire.status = patch.raw_status;
  if (patch.result_filename !== undefined) {
    wire.result = patch.result_filename === null ? null : { format: 'txt', filename: patch.result_filename };
  }
  if (patch.error !== undefined) wire.error = patch.error;
  return wire;
}

/**
 * 构造一条已经解码的回执。线上与解码后的两套字段都由同一个 patch 推导，
 * 因此不可能构造出"线上说 succeeded、解码后说 failed"这种自相矛盾的回执。
 */
const receipt = (patch: Partial<DeliveryReceipt> = {}): DeliveryReceipt => {
  const wire = toWire(patch);
  const succeeded = (wire.status ?? 'succeeded') === 'succeeded';
  return deliveryReceipt(wireJob({
    status: 'succeeded', progress: 100, result: { format: 'txt', filename: 'a.txt' }, error: null,
    ...wire,
    ...(succeeded ? {} : { result: null }),
  }), PROJECT);
};

afterEach(() => { vi.restoreAllMocks(); });

describe('deliveryClient：只读的原 owner 端点消费', () => {
  it('只暴露两个读取方法；没有任何写入口（派发/取消/重试/下载都不存在）', () => {
    const { transport: fake } = transport(() => ({}));
    const client = createDeliveryClient(PROJECT, fake);
    expect(Object.keys(client).sort()).toEqual(['readReceipt', 'readReceipts']);
    const surface = client as unknown as Record<string, unknown>;
    for (const forbidden of ['create', 'dispatch', 'export', 'start', 'cancel', 'retry', 'download', 'mutate', 'post']) {
      expect(surface[forbidden]).toBeUndefined();
    }
  });

  it('两个读取都走 GET，且路径就是原 owner 的既有端点', async () => {
    const { transport: fake, calls } = transport(url => (url.startsWith('/api/exports?')
      ? { items: [wireJob()], next_offset: null } : wireJob()));
    const client = createDeliveryClient(PROJECT, fake);
    const page = await client.readReceipts();
    const single = await client.readReceipt(JOB);
    expect(page.items).toHaveLength(1);
    expect(single.id).toBe(JOB);
    expect(calls).toHaveLength(2);
    expect(calls.every(call => call.method === 'GET')).toBe(true);
    expect(calls.every(call => call.body === undefined)).toBe(true);
    expect(calls.every(call => call.idempotencyKey === undefined)).toBe(true);
    expect(calls[0].url).toBe(`/api/exports?novel_id=${PROJECT}&limit=50`);
    expect(calls[1].url).toBe(`/api/exports/${JOB}`);
  });

  it('协作范围会带上分支参数，并拒绝属于别的项目/分支的身份', async () => {
    const { transport: fake, calls } = transport(() => ({ items: [], next_offset: null }));
    const client = createDeliveryClient(PROJECT, fake, {
      workspaceId: 'w1', projectId: PROJECT, storylineId: 's1', branchId: 'b1',
    });
    await client.readReceipts();
    expect(calls[0].url).toContain('branch_id=b1');

    const foreign = createDeliveryClient(PROJECT, fake, {
      workspaceId: 'w1', projectId: 'novel-b', storylineId: 's1', branchId: 'b1',
    });
    await expect(foreign.readReceipts()).rejects.toBeInstanceOf(ApiError);
    await expect(foreign.readReceipt(JOB)).rejects.toMatchObject({ problem: { code: DELIVERY_CODES.scopeMismatch } });
  });

  it('回执 id 不合法时在本地就拒绝，绝不发出请求', async () => {
    const { transport: fake, calls } = transport(() => wireJob());
    const client = createDeliveryClient(PROJECT, fake);
    await expect(client.readReceipt('not-a-uuid')).rejects.toMatchObject({ problem: { code: DELIVERY_CODES.receiptInvalid } });
    expect(calls).toHaveLength(0);
  });

  it('未知键或他项目的回执不会被解码成成功', async () => {
    const { transport: fake } = transport(() => wireJob({ extra: 1 }));
    await expect(createDeliveryClient(PROJECT, fake).readReceipt(JOB)).rejects.toMatchObject({ problem: { code: DELIVERY_CODES.receiptInvalid } });
    const other = transport(() => wireJob({ novel_id: 'novel-b' }));
    await expect(createDeliveryClient(PROJECT, other.transport).readReceipt(JOB)).rejects.toMatchObject({ problem: { code: DELIVERY_CODES.scopeMismatch } });
    const page = deliveryReceiptPage({ items: [], next_offset: null }, PROJECT);
    expect(page.items).toEqual([]);
  });
});

/* ------------------------------------------------------------------ 控制器 */

function client(overrides: Partial<{ receipts: unknown; error: unknown }> = {}): { client: DeliveryClient; readReceipts: ReturnType<typeof vi.fn>; readReceipt: ReturnType<typeof vi.fn> } {
  const readReceipts = vi.fn(async () => {
    if (overrides.error) throw overrides.error;
    return deliveryReceiptPage(overrides.receipts ?? { items: [wireJob({ status: 'running' })], next_offset: null }, PROJECT);
  });
  const readReceipt = vi.fn(async () => receipt());
  return { client: { readReceipts, readReceipt }, readReceipts, readReceipt };
}

const props = (patch: Record<string, unknown> = {}) => ({
  identity: 'file:abc', active: true, denied: false, busy: false, isCurrent: () => true,
  read: <T,>(work: () => Promise<T>): Promise<T> => work(),
  ...patch,
});

describe('useDelivery：显式状态，永不把未知回执显示成成功', () => {
  it('空历史是 EMPTY；有回执是 READY；并且只读一次（没有任何轮询）', async () => {
    const empty = client({ receipts: { items: [], next_offset: null } });
    const first = renderHook(() => useDelivery({ ...props(), client: empty.client }));
    await waitFor(() => expect(first.result.current.state).toBe('EMPTY'));
    expect(empty.readReceipts).toHaveBeenCalledTimes(1);

    const some = client();
    const second = renderHook(() => useDelivery({ ...props(), client: some.client }));
    await waitFor(() => expect(second.result.current.state).toBe('READY'));
    expect(second.result.current.receipts).toHaveLength(1);
    expect(second.result.current.confirmedSuccessIds).toEqual([]);
  });

  it('403 的读取是 DENIED（不是 EMPTY），并发出 onUnavailable', async () => {
    const onUnavailable = vi.fn();
    const denied = client({ error: new ApiError({ status: 403, code: 'PERMISSION_DENIED', message: 'no' }) });
    const { result } = renderHook(() => useDelivery({ ...props({ onUnavailable }), client: denied.client }));
    await waitFor(() => expect(result.current.state).toBe('DENIED'));
    expect(result.current.receipts).toEqual([]);
    expect(result.current.page).toBeUndefined();
    expect(onUnavailable).toHaveBeenCalledTimes(1);
  });

  it('denied / 未激活 / busy 的挂载不发起任何读取', async () => {
    const a = client();
    renderHook(() => useDelivery({ ...props({ denied: true }), client: a.client }));
    const b = client();
    renderHook(() => useDelivery({ ...props({ active: false }), client: b.client }));
    const c = client();
    renderHook(() => useDelivery({ ...props({ busy: true }), client: c.client }));
    await Promise.resolve();
    expect(a.readReceipts).not.toHaveBeenCalled();
    expect(b.readReceipts).not.toHaveBeenCalled();
    expect(c.readReceipts).not.toHaveBeenCalled();
  });

  it('登记一次派发后：回执未知，恢复只重新读取，绝不再次派发', async () => {
    const fake = client({ receipts: { items: [], next_offset: null } });
    const { result } = renderHook(() => useDelivery({ ...props(), client: fake.client }));
    await waitFor(() => expect(result.current.state).toBe('EMPTY'));
    const before = fake.readReceipts.mock.calls.length;

    const request = { format: 'txt' as const, idempotency_key: 'ux09-1', branch_id: null, requested_at: '2026-10-14T10:00:00Z' };
    await waitFor(async () => {
      result.current.trackAttempt(request, PROJECT);
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current.attempts).toHaveLength(1));
    // 登记本身不是网络动作。
    expect(fake.readReceipts.mock.calls.length).toBe(before);

    const recovery = result.current.recoveryOfKey('ux09-1');
    expect(recovery.state).toBe('DISPATCHED');
    expect(recovery.original_request?.idempotency_key).toBe('ux09-1');
    expect(recovery.original_request?.dispatched).toBe(false);
    expect(recovery.read?.method).toBe('GET');
    expect(recovery.confirmed_success).toBe(false);
    expect(result.current.confirmedSuccessIds).toEqual([]);
  });

  it('恢复读取到 succeeded 回执才出现确认成功；读到 running 仍不算成功', async () => {
    const fake = client({ receipts: { items: [], next_offset: null } });
    const { result } = renderHook(() => useDelivery({ ...props(), client: fake.client }));
    await waitFor(() => expect(result.current.state).toBe('EMPTY'));
    const request = { format: 'txt' as const, idempotency_key: 'ux09-2', branch_id: null, requested_at: '2026-10-14T10:00:00Z' };
    await waitFor(() => { result.current.trackAttempt(request, PROJECT); });
    fake.readReceipt.mockResolvedValueOnce(receipt({ status: 'running', progress: 40, result_filename: null }));
    await waitFor(async () => { await result.current.recover('ux09-2', JOB); });
    await waitFor(() => expect(result.current.attempts[0]?.receipt?.status).toBe('running'));
    expect(result.current.confirmedSuccessIds).toEqual([]);

    fake.readReceipt.mockResolvedValueOnce(receipt({ status: 'succeeded' }));
    await waitFor(async () => { await result.current.recover('ux09-2', JOB); });
    await waitFor(() => expect(result.current.attempts[0]?.receipt?.status).toBe('succeeded'));
    expect(result.current.confirmedSuccessIds).toEqual([JOB]);
    expect(fake.readReceipt).toHaveBeenCalledTimes(2);
  });

  it('恢复失败时保留原请求并说明不会再次派发', async () => {
    const fake = client({ receipts: { items: [], next_offset: null } });
    const { result } = renderHook(() => useDelivery({ ...props(), client: fake.client }));
    await waitFor(() => expect(result.current.state).toBe('EMPTY'));
    await waitFor(() => { result.current.trackAttempt({ format: 'txt', idempotency_key: 'ux09-3', branch_id: null, requested_at: '2026-10-14T10:00:00Z' }, PROJECT); });
    fake.readReceipt.mockRejectedValueOnce(new ApiError({ status: 404, code: 'EXPORT_NOT_FOUND', message: 'x' }));
    await waitFor(async () => { await result.current.recover('ux09-3', JOB); });
    await waitFor(() => expect(result.current.notice).toContain('不会再次派发'));
    expect(result.current.attempts[0]?.receipt).toBeNull();
    expect(result.current.confirmedSuccessIds).toEqual([]);
  });
});
