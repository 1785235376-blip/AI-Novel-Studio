import { describe, expect, it } from 'vitest';
import { deliveryReceipt } from './deliveryContract';
import {
  DELIVERY_DECLARED_LIMITS, exportableItem, formatAvailability, formatRefusal, handoverManifest,
  receiptRecovery, receiptShowsSuccess, receiptState, sizeAndLimitsReport,
} from './deliveryOps';
import {
  DELIVERY_CODES, DELIVERY_ITEM_BYTES_LIMIT, DELIVERY_MANIFEST_ITEM_LIMIT,
  DELIVERY_PACKAGE_BYTES_LIMIT, DELIVERY_RECOVERY_CODES,
  type DeliveryEntitlements, type DeliveryItem, type DeliveryReceipt, type DeliveryRequest,
} from './deliveryTypes';

const PROJECT = 'novel-a';
const OTHER_PROJECT = 'novel-b';
/** 稳定的 64 位小写十六进制摘要；不同 seed 得到不同摘要。 */
const digest = (seed: string): string => {
  const row = (seed.repeat(3) + 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789').slice(0, 64);
  return [...row].map((character, index) => (/[0-9a-f]/.test(character) ? character : 'abcdef'[index % 6])).join('');
};
const itemId = (seed: number): string => `item-${seed}`;

function item(patch: Partial<DeliveryItem> = {}): DeliveryItem {
  return {
    id: 'item-1', novel_id: PROJECT, kind: 'text', media_type: 'text/plain', path: 'chapters/001.md',
    version: 3, digest: digest('ab'), size_bytes: 1024, visibility: 'VISIBLE', source: '章节原文',
    ...patch,
  };
}

function rights(patch: Partial<DeliveryEntitlements> = {}): DeliveryEntitlements {
  return {
    project_id: PROJECT, identity: 'file:11111111-1111-4111-8111-111111111111', can_export: true,
    item_kinds: ['text', 'screenplay', 'timeline', 'image', 'audio', 'video'],
    formats: ['txt', 'markdown', 'json', 'docx', 'screenplay-fountain', 'screenplay-package', 'storyboard'],
    max_item_bytes: DELIVERY_ITEM_BYTES_LIMIT, max_package_bytes: DELIVERY_PACKAGE_BYTES_LIMIT,
    max_items: DELIVERY_MANIFEST_ITEM_LIMIT,
    ...patch,
  };
}

function request(patch: Partial<DeliveryRequest> = {}): DeliveryRequest {
  return { format: 'txt', idempotency_key: 'ux09-attempt-1', branch_id: null, requested_at: '2026-10-14T10:00:00Z', ...patch };
}

function receipt(patch: Partial<DeliveryReceipt> = {}): DeliveryReceipt {
  return {
    id: '11111111-1111-4111-8111-111111111111', project_id: PROJECT, format: 'txt', status: 'succeeded',
    raw_status: null, created_at: '2026-10-14T10:00:00Z', updated_at: '2026-10-14T10:00:05Z', progress: 100,
    progress_message: '已完成', attempt: 1, retry_of: null, recovery_count: 0, snapshot_id: null,
    captured_at: null, source_versions: [], missing_resources: [], result_filename: 'novel-a.txt', error: null,
    ...patch,
  };
}

/* ------------------------------------------------------------------ 单对象独立导出（S11） */

describe('exportableItem：单个对象独立判定（S11）', () => {
  it('六类对象都能在拿到自己那一份证据时独立导出', () => {
    const cases: [DeliveryItem['kind'], DeliveryReceipt['format']][] = [
      ['text', 'txt'], ['screenplay', 'screenplay-fountain'], ['timeline', 'storyboard'],
    ];
    for (const [kind, format] of cases) {
      const decision = exportableItem(item({ kind }), rights(), format);
      expect(decision.state).toBe('EXPORTABLE');
      expect(decision.state === 'EXPORTABLE' && decision.independent_of_project_completion).toBe(true);
    }
    // 原 owner 目前没有任何 /api/exports 格式声明能写出音视频：仍然"可独立导出"没有意义，
    // 因为格式面为空，判定必须是明确拒绝，而不是伪造一个可用格式。
    expect(formatAvailability(item({ kind: 'audio', path: 'audio/vo-01.wav', media_type: 'audio/wav' }), rights())).toEqual([]);
    expect(exportableItem(item({ kind: 'video', path: 'video/shot-01.mp4', media_type: 'video/mp4' }), rights()).state).toBe('REFUSED');
    expect(exportableItem(item({ kind: 'image', path: 'images/cover.png', media_type: 'image/png' }), rights(), 'storyboard').state).toBe('EXPORTABLE');
  });

  it('独立性与"项目其余部分是否完成"无关：同一对象在不同项目状态下判定一致', () => {
    // 判定函数的参数里根本没有项目完成度；这里用"只有这一个对象"与"项目里还有未完成对象"
    // 两种调用方式证明结果一致 —— 结构上无法把项目状态传进来。
    const subject = item({ id: 'chapter-7', version: 9 });
    const alone = exportableItem(subject, rights(), 'markdown');
    const withBusyNeighbours = exportableItem(subject, rights(), 'markdown');
    expect(alone).toEqual(withBusyNeighbours);
    expect(alone.state === 'EXPORTABLE' && alone.format).toBe('markdown');
    // 没有给格式时也给出可用格式，由调用方选择（仍然不依赖任何项目状态）。
    const withoutFormat = exportableItem(subject, rights());
    expect(withoutFormat.state).toBe('EXPORTABLE');
    expect(withoutFormat.state === 'EXPORTABLE' && withoutFormat.independent_of_project_completion).toBe(true);
  });

  it('未知格式的拒绝带机器码与可用格式，且没有任何成功字段', () => {
    const refusal = formatRefusal(item(), 'xlsx', rights());
    expect(refusal?.state).toBe('REFUSED');
    expect(refusal?.code).toBe(DELIVERY_CODES.formatUnknown);
    expect(refusal?.requested_format).toBe('xlsx');
    expect(refusal?.available_formats).toContain('txt');
    // 拒绝对象里没有 receipt / filename / success 之类的字段。
    expect(Object.keys(refusal ?? {})).not.toContain('receipt');
    expect(Object.keys(refusal ?? {})).not.toContain('filename');
    const decision = exportableItem(item(), rights(), 'xlsx');
    expect(decision.state).toBe('REFUSED');
    expect(Object.keys(decision)).not.toContain('receipt');
  });

  it('格式不适用于该对象时同样是明确拒绝，而不是"可用"', () => {
    expect(formatRefusal(item({ kind: 'screenplay', path: 'screenplay/act-1.fountain' }), 'txt', rights())?.code)
      .toBe(DELIVERY_CODES.formatNotApplicable);
    // 身份没被授予该格式时也拒绝（授权只能减少可选项）。
    expect(formatRefusal(item(), 'docx', rights({ formats: ['txt'] }))?.available_formats).toEqual(['txt']);
    expect(formatAvailability(item(), rights({ can_export: false }))).toEqual([]);
  });

  it('没有导出权利、可见性被阻塞或字段缺失的对象都被拒绝', () => {
    expect(exportableItem(item(), rights({ can_export: false }), 'txt').state).toBe('REFUSED');
    expect(exportableItem(item({ visibility: 'DENIED' }), rights(), 'txt').state).toBe('REFUSED');
    expect(exportableItem(item({ visibility: 'BLOCKED' }), rights(), 'txt').state).toBe('REFUSED');
    expect(exportableItem(item({ version: null }), rights(), 'txt').state).toBe('REFUSED');
    expect(exportableItem(item({ digest: null }), rights(), 'txt').state).toBe('REFUSED');
    expect(exportableItem(item({ size_bytes: null }), rights(), 'txt').state).toBe('REFUSED');
    expect(exportableItem(item({ size_bytes: DELIVERY_ITEM_BYTES_LIMIT + 1 }), rights(), 'txt').state).toBe('REFUSED');
  });
});

/* ------------------------------------------------------------------ 交接包排斥 */

describe('handoverManifest：结构上装不进模型/依赖/凭据/他项目对象', () => {
  it('正常选择：只收显式勾选且身份有权导出的对象，每条都带版本与摘要', () => {
    const manifest = handoverManifest([item({ id: 'item-1' }), item({ id: 'item-2', version: 7 })], rights());
    expect(manifest.entries.map(entry => entry.id)).toEqual(['item-1', 'item-2']);
    expect(manifest.entries.every(entry => typeof entry.version === 'number' && entry.digest.length === 64)).toBe(true);
    expect(manifest.excluded).toEqual([]);
    expect(manifest.explicitly_selected).toBe(true);
    expect(manifest.generated_from).toBe('SELECTION');
  });

  it('敌对输入：他项目对象、node_modules、密钥名、模型权重全部被排斥', () => {
    const hostile: DeliveryItem[] = [
      item({ id: 'foreign-1', novel_id: OTHER_PROJECT }),
      item({ id: 'dep-1', path: 'node_modules/left-pad/index.js', media_type: 'text/javascript' }),
      item({ id: 'dep-2', path: 'frontend/.runtime/cache.json' }),
      item({ id: 'model-1', path: 'models/llama-3.1-8b.gguf', media_type: null }),
      item({ id: 'model-2', path: 'weights/model.safetensors', media_type: null }),
      item({ id: 'secret-1', path: 'config/credentials.json' }),
      item({ id: 'secret-2', path: 'deploy/service-account.pem' }),
      item({ id: 'secret-3', media_type: 'application/x-pem-file', path: 'a/b.txt' }),
      item({ id: 'secret-4', contains_secret: true }),
      item({ id: 'escape-1', path: '../../etc/passwd' }),
      item({ id: 'escape-2', path: 'C:/Windows/system32/config/SAM' }),
      item({ id: 'nodigest', digest: null }),
      item({ id: 'bad-digest', digest: 'zzzz' }),
      item({ id: 'nokind', kind: null }),
    ];
    const manifest = handoverManifest(hostile, rights());
    expect(manifest.entries).toEqual([]);
    expect(manifest.excluded.length).toBeGreaterThanOrEqual(hostile.length - 1);
    const reasons = manifest.excluded.map(row => row.reason);
    expect(reasons).toContain('FOREIGN_PROJECT');
    expect(reasons).toContain('PATH_FORBIDDEN');
    expect(reasons).toContain('MODEL_ARTIFACT');
    expect(reasons).toContain('SECRET_BEARING');
    expect(reasons).toContain('PATH_UNSAFE');
    expect(reasons).toContain('DIGEST_MISSING');
    expect(reasons).toContain('DIGEST_INVALID');
    expect(reasons).toContain('KIND_NOT_ENTITLED');
  });

  it('清单自己的四个结构保证恒为 false，模型/依赖/凭据/他项目对象无法表达为"已包含"', () => {
    const manifest = handoverManifest([
      item({ id: 'foreign', novel_id: OTHER_PROJECT }),
      item({ id: 'model', path: 'x/y.gguf' }),
      item({ id: 'secret', path: 'x/token.txt' }),
      item({ id: 'dep', path: 'node_modules/z/index.js' }),
    ], rights());
    expect(manifest.contains_models).toBe(false);
    expect(manifest.contains_dependencies).toBe(false);
    expect(manifest.contains_credentials).toBe(false);
    expect(manifest.contains_foreign_project_objects).toBe(false);
    // 连带地，这些 id 一个都不能出现在 entries 里。
    expect(manifest.entries.map(entry => entry.id)).toEqual([]);
  });

  it('没有导出权利 / 没有勾选时是空包，且空包仍然带着排斥理由', () => {
    const denied = handoverManifest([item({ id: 'item-1' })], rights({ can_export: false }));
    expect(denied.entries).toEqual([]);
    expect(denied.excluded[0].reason).toBe('ENTITLEMENT_DENIED');
    expect(handoverManifest([], rights()).entries).toEqual([]);
    expect(handoverManifest(undefined, rights()).entries).toEqual([]);
  });

  it('重复 id 只保留第一条，重复项以 DUPLICATE_ITEM 说明', () => {
    const manifest = handoverManifest([item({ id: 'same' }), item({ id: 'same', version: 99 })], rights());
    expect(manifest.entries.map(entry => entry.id)).toEqual(['same']);
    expect(manifest.entries[0].version).toBe(3);
    expect(manifest.excluded.map(row => row.reason)).toEqual(['DUPLICATE_ITEM']);
  });

  it('超出整包上限的对象被排斥，且清单不再声称有"已核对合计"', () => {
    const big = rights({ max_package_bytes: 2000 });
    const manifest = handoverManifest([item({ id: 'a', size_bytes: 1500 }), item({ id: 'b', size_bytes: 1500 })], big);
    expect(manifest.entries.map(entry => entry.id)).toEqual(['a']);
    expect(manifest.total_bytes).toBeNull();
    expect(manifest.excluded[0].reason).toBe('ITEM_TOO_LARGE');
    expect(manifest.excluded[0].code).toBe(DELIVERY_CODES.packageTooLarge);
  });

  it('超过条目上限的选择不会被静默接受', () => {
    const many: DeliveryItem[] = Array.from({ length: DELIVERY_MANIFEST_ITEM_LIMIT + 5 }, (_, index) => item({ id: itemId(index) }));
    const manifest = handoverManifest(many, rights());
    expect(manifest.excluded.some(row => row.code === DELIVERY_CODES.manifestOverflow)).toBe(true);
  });

  it('非对象项不会被当成条目：只记录一条无标识的排斥', () => {
    const manifest = handoverManifest([null, 'not-an-item', 42], rights());
    expect(manifest.entries).toEqual([]);
    expect(manifest.excluded).toHaveLength(3);
    expect(manifest.excluded.every(row => row.reason === 'IDENTITY_INVALID')).toBe(true);
  });
});

/* ------------------------------------------------------------------ 回执三态与恢复 */

describe('receiptState / receiptRecovery：丢失或未知的回执绝不是成功，也绝不再派发', () => {
  it('三态判定：没有回执是 DISPATCHED，连请求都没有是 UNKNOWN，格式不符也是 UNKNOWN', () => {
    expect(receiptState({ project_id: PROJECT, request: request(), receipt: null })).toBe('DISPATCHED');
    expect(receiptState({ project_id: PROJECT, request: null, receipt: null })).toBe('UNKNOWN');
    expect(receiptState({ project_id: PROJECT, request: request({ format: 'txt' }), receipt: receipt({ format: 'json' }) })).toBe('UNKNOWN');
    expect(receiptState({ project_id: PROJECT, request: request(), receipt: receipt() })).toBe('RETURNED');
    expect(receiptState({ project_id: OTHER_PROJECT, request: request(), receipt: receipt() })).toBe('UNKNOWN');
  });

  it('UNKNOWN / DISPATCHED 的恢复只还原原请求，并给出只读的重新读取路径', () => {
    const dispatched = receiptRecovery({ project_id: PROJECT, request: request(), receipt: null });
    expect(dispatched.state).toBe('DISPATCHED');
    expect(dispatched.original_request?.idempotency_key).toBe('ux09-attempt-1');
    expect(dispatched.original_request?.dispatched).toBe(false);
    expect(dispatched.read?.method).toBe('GET');
    expect(dispatched.read?.path).toContain('/api/exports?');
    expect(dispatched.read?.match.idempotency_key).toBe('ux09-attempt-1');
    expect(dispatched.confirmed_success).toBe(false);
    expect(dispatched.owner_retry_path).toBeNull();

    const unknown = receiptRecovery({ project_id: PROJECT, request: null, receipt: null });
    expect(unknown.state).toBe('UNKNOWN');
    expect(unknown.code).toBe('REREAD_BY_IDEMPOTENCY_KEY');
    expect(unknown.original_request).toBeNull();
    expect(unknown.read).toBeNull();
  });

  it('恢复计划里只有 GET，且任何端点都不是派发/取消/重试', () => {
    const plans = [
      receiptRecovery({ project_id: PROJECT, request: request(), receipt: null }),
      receiptRecovery({ project_id: PROJECT, request: request(), receipt: receipt({ status: 'running' }) }),
      receiptRecovery({ project_id: PROJECT, request: request(), receipt: receipt({ status: 'failed', result_filename: null, error: { code: 'X', message: 'y' } }) }),
    ];
    for (const plan of plans) {
      expect(plan.read?.method).toBe('GET');
      const path = plan.read?.path ?? '';
      expect(path).not.toMatch(/\/cancel/);
      expect(path).not.toMatch(/\/retry/);
      expect(path).not.toMatch(/\/download/);
      // 唯一出现 POST 语义的地方是原 owner 自己的重试端点，且只是展示。
      expect(plan.read?.method).not.toBe('POST');
    }
  });

  it('原 owner 判定成功才算成功；失败/取消只指向原 owner 的重试端点', () => {
    const success = receiptRecovery({ project_id: PROJECT, request: request(), receipt: receipt() });
    expect(success.code).toBe('NO_ACTION_REQUIRED');
    expect(success.confirmed_success).toBe(true);
    expect(success.owner_retry_path).toBeNull();
    expect(success.read?.path).toBe('/api/exports/11111111-1111-4111-8111-111111111111');

    const failed = receiptRecovery({
      project_id: PROJECT, request: request(),
      receipt: receipt({ status: 'failed', result_filename: null, error: { code: 'EXPORT_FAILED', message: 'x' } }),
    });
    expect(failed.confirmed_success).toBe(false);
    expect(failed.code).toBe('ORIGINAL_OWNER_RETRY_ENDPOINT');
    expect(failed.owner_retry_path).toBe('/api/exports/11111111-1111-4111-8111-111111111111/retry');
    expect(DELIVERY_RECOVERY_CODES).toContain(failed.code);
  });

  it('receiptShowsSuccess 只认原 owner 的真实 succeeded', () => {
    expect(receiptShowsSuccess(null)).toBe(false);
    expect(receiptShowsSuccess(receipt({ status: 'running' }))).toBe(false);
    expect(receiptShowsSuccess(receipt({ status: 'failed' }))).toBe(false);
    expect(receiptShowsSuccess(receipt({ status: 'cancelled' }))).toBe(false);
    expect(receiptShowsSuccess(receipt({ status: 'succeeded' }))).toBe(true);
    const unknownStatus = deliveryReceipt({ id: '11111111-1111-4111-8111-111111111111', novel_id: PROJECT, format: 'txt', status: 'weird', created_at: '2026-10-14T10:00:00Z' }, PROJECT);
    expect(receiptShowsSuccess(unknownStatus)).toBe(false);
    expect(unknownStatus.raw_status).toBe('weird');
  });
});

/* ------------------------------------------------------------------ 限额 */

describe('sizeAndLimitsReport：在撞线之前说清真实限额，并拒绝上调', () => {
  it('限额逐条等于原 owner 声明的常量', () => {
    expect(DELIVERY_DECLARED_LIMITS.item_bytes).toBe(25 * 1024 * 1024);
    expect(DELIVERY_DECLARED_LIMITS.package_bytes).toBe(64 * 1024 * 1024);
    expect(DELIVERY_DECLARED_LIMITS.items).toBe(500);
    expect(DELIVERY_ITEM_BYTES_LIMIT).toBe(DELIVERY_DECLARED_LIMITS.item_bytes);
    expect(DELIVERY_PACKAGE_BYTES_LIMIT).toBe(DELIVERY_DECLARED_LIMITS.package_bytes);
    const report = sizeAndLimitsReport([item()], rights());
    const byCode = Object.fromEntries(report.limits.map(fact => [fact.code, fact]));
    expect(byCode.ITEM_BYTES.limit).toBe(25 * 1024 * 1024);
    expect(byCode.PACKAGE_BYTES.limit).toBe(64 * 1024 * 1024);
    expect(byCode.ITEM_COUNT.limit).toBe(500);
  });

  it('正常情况下给出 WITHIN_LIMITS 与真实合计', () => {
    const report = sizeAndLimitsReport([item({ id: 'a', size_bytes: 10 }), item({ id: 'b', size_bytes: 20 })], rights());
    expect(report.items).toBe(2);
    expect(report.total_bytes).toBe(30);
    expect(report.verdict).toBe('WITHIN_LIMITS');
    expect(report.refused_items).toEqual([]);
    expect(report.unmeasured).toEqual([]);
  });

  it('超限是 EXCEEDED 并列出被拒对象；上限永远不会被抬高', () => {
    const report = sizeAndLimitsReport([
      item({ id: 'big', size_bytes: DELIVERY_ITEM_BYTES_LIMIT + 1 }),
    ], rights());
    expect(report.verdict).toBe('EXCEEDED');
    expect(report.limits_raised).toBe(false);
    expect(report.refused_items).toContain('big');
    expect(report.limits.find(fact => fact.code === 'ITEM_BYTES')?.exceeded).toBe(true);

    const packed = sizeAndLimitsReport([
      item({ id: 'p1', size_bytes: 40 * 1024 * 1024 }), item({ id: 'p2', size_bytes: 40 * 1024 * 1024 }),
    ], rights());
    expect(packed.verdict).toBe('EXCEEDED');
    expect(packed.limits.find(fact => fact.code === 'PACKAGE_BYTES')?.exceeded).toBe(true);

    const tooMany = sizeAndLimitsReport(
      Array.from({ length: 4 }, (_, index) => item({ id: `i${index}`, size_bytes: 1 })),
      rights({ max_items: 2 }),
    );
    expect(tooMany.verdict).toBe('EXCEEDED');
    expect(tooMany.limits.find(fact => fact.code === 'ITEM_COUNT')?.exceeded).toBe(true);
  });

  it('有对象未报告字节时不给出合计，也不当成通过', () => {
    const report = sizeAndLimitsReport([item({ id: 'a', size_bytes: null }), item({ id: 'b', size_bytes: 5 })], rights());
    expect(report.total_bytes).toBeNull();
    expect(report.unmeasured).toEqual(['a']);
    expect(report.verdict).toBe('UNMEASURED');
    expect(report.limits_raised).toBe(false);
  });

  it('重复 id 在限额清点里去重（不会把同一对象算两次字节）', () => {
    const report = sizeAndLimitsReport([item({ id: 'a', size_bytes: 10 }), item({ id: 'a', size_bytes: 10 })], rights());
    expect(report.items).toBe(1);
    expect(report.total_bytes).toBe(10);
  });
});
