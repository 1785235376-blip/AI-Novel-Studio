import { describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import {
  deliveryAttempt, deliveryDigest, deliveryEntitlements, deliveryFormatId, deliveryItem, deliveryItems,
  deliveryJobId, deliveryProjectId, deliveryReceipt, deliveryReceiptPage, deliveryRequest, deliverySafePath,
  deliveryScope,
} from './deliveryContract';
import { DELIVERY_CODES, DELIVERY_ITEM_BYTES_LIMIT, DELIVERY_PACKAGE_BYTES_LIMIT, type DeliveryItem } from './deliveryTypes';

const PROJECT = 'novel-a';
const JOB = '11111111-1111-4111-8111-111111111111';
const OTHER_JOB = '22222222-2222-4222-8222-222222222222';

/** 严格解码器用机器码报错：断言码，不断言文案。 */
function rejectionCode(run: () => unknown): string | undefined {
  try {
    run();
    return undefined;
  } catch (error) {
    return error instanceof ApiError ? error.problem.code : `NOT_AN_API_ERROR:${String(error)}`;
  }
}

/**
 * 一条 `ExportJobService.public()` 真实会下发的回执行：`_normalise_job()` 的固定键集
 * 去掉 `snapshot` / `idempotency_key` / `artifact`，再加上从快照复制的
 * `source_versions` / `captured_at`，以及结果体里去掉 `content*` 的 `result`。
 */
function jobWire(patch: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: JOB, novel_id: PROJECT, format: 'txt', status: 'succeeded',
    created_at: '2026-10-14T10:00:00Z', updated_at: '2026-10-14T10:00:05Z',
    progress: 100, progress_message: '已完成', retry_of: null, attempt: 1, cancel_requested: false,
    recovery_count: 0, snapshot_id: 'snap-1', source_versions: { manuscript: 12, branch: 'main' },
    captured_at: '2026-10-14T09:59:58Z',
    missing_resources: [], permission_context: { mode: 'local', novel_id: PROJECT },
    result: { format: 'txt', filename: 'novel-a.txt', media_type: 'text/plain', size: 42, sha256: 'a'.repeat(64) },
    error: null, started_at: '2026-10-14T10:00:01Z', finished_at: '2026-10-14T10:00:05Z',
    ...patch,
  };
}

describe('deliveryContract：严格解码原导出服务的公开回执', () => {
  it('接受真实的 ExportJobService.public() 形状（含快照与结果事实）', () => {
    const receipt = deliveryReceipt(jobWire(), PROJECT);
    expect(receipt.id).toBe(JOB);
    expect(receipt.project_id).toBe(PROJECT);
    expect(receipt.format).toBe('txt');
    expect(receipt.status).toBe('succeeded');
    expect(receipt.raw_status).toBeNull();
    expect(receipt.progress).toBe(100);
    expect(receipt.result_filename).toBe('novel-a.txt');
    expect(receipt.attempt).toBe(1);
    expect(receipt.source_versions).toEqual([{ key: 'manuscript', value: 12 }, { key: 'branch', value: 'main' }]);
    expect(receipt.captured_at).toBe('2026-10-14T09:59:58Z');
    expect(receipt.recovery_count).toBe(0);
    expect(receipt.error).toBeNull();
  });

  it('缺失即缺失：没有 updated_at/attempt/progress 时给出保守缺省，绝不编造成功', () => {
    const receipt = deliveryReceipt({
      id: JOB, novel_id: PROJECT, format: 'txt', status: 'queued', created_at: '2026-10-14T10:00:00Z',
    }, PROJECT);
    expect(receipt.updated_at).toBe('2026-10-14T10:00:00Z');
    expect(receipt.progress).toBe(0);
    expect(receipt.progress_message).toBe('');
    expect(receipt.attempt).toBe(1);
    expect(receipt.retry_of).toBeNull();
    expect(receipt.snapshot_id).toBeNull();
    expect(receipt.captured_at).toBeNull();
    expect(receipt.result_filename).toBeNull();
    expect(receipt.source_versions).toEqual([]);
    expect(receipt.missing_resources).toEqual([]);
  });

  it('原 owner 未定义的状态码不猜测：raw_status 保留，status 保守为未终结', () => {
    const receipt = deliveryReceipt(jobWire({ status: 'SOMETHING_NEW', result: null }), PROJECT);
    expect(receipt.raw_status).toBe('SOMETHING_NEW');
    expect(receipt.status).toBe('queued');
    expect(receipt.result_filename).toBeNull();
  });

  it('未知键、他项目、内嵌快照、非法取值全部是拒绝的读取', () => {
    expect(rejectionCode(() => deliveryReceipt(jobWire({ extra: true }), PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceipt(jobWire(), 'novel-b'))).toBe(DELIVERY_CODES.scopeMismatch);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ snapshot: { chapters: [] } }), PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ idempotency_key: 'k' }), PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ artifact: { path: 'x' } }), PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ progress: 101 }), PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ progress: 1.5 }), PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ id: 'not-a-uuid' }), PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ format: 'xlsx' }), PROJECT))).toBe(DELIVERY_CODES.formatUnknown);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ status: '' }), PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ error: { code: 'X', message: 'y' }, status: 'succeeded' }), PROJECT))).toBeUndefined();
    expect(rejectionCode(() => deliveryReceipt(jobWire({ status: 'failed', result: null, error: { code: 'X' } }), PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceipt(jobWire({ status: 'failed', result: null, error: { code: 'X', message: 'y' } }), PROJECT))).toBeUndefined();
  });

  it('一页历史：形状、去重与 next_offset 都被核验', () => {
    const page = deliveryReceiptPage({ items: [jobWire(), jobWire({ id: OTHER_JOB, status: 'failed', result: null, error: { code: 'E', message: 'm' } })], next_offset: 50 }, PROJECT);
    expect(page.items).toHaveLength(2);
    expect(page.next_offset).toBe(50);
    expect(deliveryReceiptPage({ items: [], next_offset: null }, PROJECT).next_offset).toBeNull();
    expect(rejectionCode(() => deliveryReceiptPage({ items: [] }, PROJECT))).toBeUndefined();
    expect(rejectionCode(() => deliveryReceiptPage({ items: [jobWire(), jobWire()], next_offset: null }, PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceiptPage({ items: [], next_offset: -1 }, PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryReceiptPage({ items: [], next_offset: null, total: 0 }, PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
  });

  it('请求与尝试：幂等键语法被核验，缺失回执保持 null', () => {
    const attempt = deliveryAttempt({
      project_id: PROJECT,
      request: { format: 'txt', idempotency_key: 'ux09-1', branch_id: null, requested_at: '2026-10-14T10:00:00Z' },
      receipt: null,
    }, PROJECT);
    expect(attempt.receipt).toBeNull();
    expect(attempt.request.format).toBe('txt');
    expect(rejectionCode(() => deliveryRequest({ format: 'txt', idempotency_key: 'bad key!', branch_id: null, requested_at: '2026-10-14T10:00:00Z' }))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryAttempt({ project_id: 'novel-b', request: { format: 'txt', idempotency_key: 'k', branch_id: null, requested_at: '2026-10-14T10:00:00Z' }, receipt: null }, PROJECT))).toBe(DELIVERY_CODES.scopeMismatch);
  });

  it('对象解码：缺失字段保持 null，控制字符与未知键被拒绝', () => {
    const decoded: DeliveryItem = deliveryItem({ id: 'item-1', novel_id: PROJECT, kind: 'text' });
    expect(decoded.version).toBeNull();
    expect(decoded.digest).toBeNull();
    expect(decoded.size_bytes).toBeNull();
    expect(decoded.path).toBeNull();
    expect(decoded.visibility).toBeNull();
    expect(decoded.media_type).toBeNull();
    expect(rejectionCode(() => deliveryItem({ id: 'x', unexpected: 1 }))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryItem({ id: 'bad\u0000id' }))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryItem({ id: 'x', kind: 'podcast' }))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryItem({ id: 'x', version: -1 }))).toBe(DELIVERY_CODES.receiptInvalid);
    // `payload` 只作保留，永不参与交接包组装。
    expect(deliveryItem({ id: 'x', payload: { nested: ['a', 1, true, null] } }).payload).toEqual({ nested: ['a', 1, true, null] });
    expect(rejectionCode(() => deliveryItem({ id: 'x', payload: { deep: { a: { b: { c: { d: { e: 1 } } } } } } }))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(deliveryItems([{ id: 'a' }, { id: 'b' }])).toHaveLength(2);
  });

  it('授权解码：拒绝自相矛盾（没有权利却列出种类/格式）', () => {
    const grants = deliveryEntitlements({
      project_id: PROJECT, identity: 'file:abc', can_export: true, item_kinds: ['text'],
      formats: ['txt'], max_item_bytes: DELIVERY_ITEM_BYTES_LIMIT, max_package_bytes: DELIVERY_PACKAGE_BYTES_LIMIT, max_items: 500,
    }, PROJECT);
    expect(grants.can_export).toBe(true);
    expect(grants.item_kinds).toEqual(['text']);
    expect(grants.formats).toEqual(['txt']);
    expect(rejectionCode(() => deliveryEntitlements({
      project_id: PROJECT, identity: 'file:abc', can_export: false, item_kinds: ['text'],
      formats: ['txt'], max_item_bytes: 1, max_package_bytes: 1, max_items: 1,
    }, PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryEntitlements({
      project_id: PROJECT, identity: 'file:abc', can_export: true, item_kinds: ['text', 'text'],
      formats: [], max_item_bytes: 1, max_package_bytes: 1, max_items: 1,
    }, PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryEntitlements({
      project_id: PROJECT, identity: '/home/me/.ssh/id_rsa', can_export: true, item_kinds: [],
      formats: [], max_item_bytes: 1, max_package_bytes: 1, max_items: 1,
    }, PROJECT))).toBe(DELIVERY_CODES.receiptInvalid);
  });

  it('身份解码：只接受有界的 owner 令牌，并核对项目/分支范围', () => {
    expect(deliveryProjectId('novel-a')).toBe(PROJECT);
    expect(rejectionCode(() => deliveryProjectId(''))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryProjectId('a'.repeat(300)))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryProjectId('/abs/path'))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(deliveryJobId(JOB)).toBe(JOB);
    expect(rejectionCode(() => deliveryJobId('job-1'))).toBe(DELIVERY_CODES.receiptInvalid);
    expect(rejectionCode(() => deliveryFormatId('md'))).toBe(DELIVERY_CODES.formatUnknown);
    expect(deliveryFormatId('markdown')).toBe('markdown');
    expect(deliveryScope({ mode: 'local', novel_id: PROJECT }, PROJECT).mode).toBe('local');
    expect(rejectionCode(() => deliveryScope({ mode: 'local', novel_id: 'novel-b' }, PROJECT))).toBe(DELIVERY_CODES.scopeMismatch);
    expect(rejectionCode(() => deliveryScope({ mode: 'collaboration', novel_id: PROJECT, branch_id: 'b1' }, PROJECT))).toBe(DELIVERY_CODES.scopeMismatch);
    expect(deliveryScope({ mode: 'collaboration', novel_id: PROJECT, branch_id: 'b1' }, PROJECT, { mode: 'collaboration', novel_id: PROJECT, branch_id: 'b1' }).branch_id).toBe('b1');
  });

  it('路径与摘要判据：安全相对路径与 SHA-256', () => {
    expect(deliverySafePath('chapters/001.md')).toBe(true);
    expect(deliverySafePath('../escape.md')).toBe(false);
    expect(deliverySafePath('/etc/passwd')).toBe(false);
    expect(deliverySafePath('C:/x')).toBe(false);
    expect(deliveryDigest('a'.repeat(64))).toBe(true);
    expect(deliveryDigest('A'.repeat(64))).toBe(false);
    expect(deliveryDigest('a'.repeat(63))).toBe(false);
  });
});
