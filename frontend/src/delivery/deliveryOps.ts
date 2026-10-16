import {
  DELIVERY_CODES, DELIVERY_DIGEST, DELIVERY_EXCLUSION_REASON_LABELS, DELIVERY_FORBIDDEN_EXTENSIONS,
  DELIVERY_FORBIDDEN_MEDIA_TYPES, DELIVERY_FORBIDDEN_PATH_SEGMENTS, DELIVERY_FORMAT_KINDS,
  DELIVERY_FORMAT_IDS, DELIVERY_ITEM_BYTES_LIMIT, DELIVERY_ITEM_ID, DELIVERY_MANIFEST_ITEM_LIMIT,
  DELIVERY_NOTICES, DELIVERY_SAFE_PATH, DELIVERY_SECRET_NAME_HINTS, DELIVERY_PACKAGE_BYTES_LIMIT,
  type DeliveryEntitlements, type DeliveryExclusionReason, type DeliveryFormatId, type DeliveryFormatRefusal,
  type DeliveryItem, type DeliveryItemExportDecision, type DeliveryItemKind, type DeliveryLimitFact,
  type DeliveryReadPlan, type DeliveryReceipt, type DeliveryReceiptState, type DeliveryRecovery,
  type DeliveryRequest, type DeliverySizeLimitsReport, type HandoverEntry, type HandoverExclusion,
  type HandoverManifest,
} from './deliveryTypes';

/**
 * UX-09 纯函数层 —— 只做判定与清点，**没有任何**派发、调度、轮询或重试。
 *
 * 三个不可违反的性质（都由测试断言）：
 *
 * 1. **单对象独立（S11）**：`exportableItem()` 的签名里没有"项目其余部分"这个参数 ——
 *    它只看一个对象、这份授权，以及（可选）一个格式。因此"项目还没做完"在结构上
 *    无法影响"这一个对象能不能导出"。
 * 2. **格式拒绝不可伪造成成功**：`DeliveryItemExportDecision` 是判别联合，拒绝分支
 *    没有 `receipt`、没有文件名、也没有 `format`；`formatRefusal()` 只会返回
 *    `state: 'REFUSED'`。没有任何返回值能同时表示"被拒绝"和"导出成功"。
 * 3. **交接包结构上装不进模型/依赖/凭据/他项目对象**：`handoverManifest()` 逐条**排斥**
 *    （默认不放行），并且清单类型把 `contains_models` / `contains_dependencies` /
 *    `contains_credentials` / `contains_foreign_project_objects` 固定为 `false`。
 */

/* ------------------------------------------------------------------ 名称与路径判据 */

const lower = (value: string): string => value.toLowerCase();

/** 名称里是否出现凭据线索（只看名字与路径，**从不**读取内容）。 */
function secretBearing(item: DeliveryItem): boolean {
  if (item.contains_secret === true) return true;
  const probes = [item.id, item.path ?? '', item.media_type ?? '', item.source ?? '']
    .map(lower).filter(Boolean);
  const name = probes.join(' ');
  if (DELIVERY_SECRET_NAME_HINTS.some(hint => name.includes(hint))) return true;
  // `.env` / `.env.local` / `.env.production` 这类点文件。
  return /(^|[/ .])\.?env(\.|$|\/)/.test(name);
}

/** 路径里是否有一段属于依赖/构建/缓存目录。 */
function forbiddenPathSegment(item: DeliveryItem): boolean {
  const path = item.path;
  if (!path) return false;
  const segments = path.split(/[\\/]+/).map(lower).filter(Boolean);
  if (segments.length > 12) return true;
  return segments.some(segment => (DELIVERY_FORBIDDEN_PATH_SEGMENTS as readonly string[]).includes(segment));
}

/** 是否像模型权重/编译产物（后缀判据；`models--` 这类缓存前缀也命中）。 */
function modelArtifact(item: DeliveryItem): boolean {
  const path = item.path;
  if (!path) return false;
  const name = lower(path);
  if (/(^|\/)(models--|blobs\/|snapshots\/)/.test(name)) return true;
  const segments = name.split('/');
  const last = segments[segments.length - 1] ?? '';
  const extension = last.includes('.') ? last.slice(last.lastIndexOf('.') + 1) : '';
  return !!extension && (DELIVERY_FORBIDDEN_EXTENSIONS as readonly string[]).includes(extension);
}

/** 相对路径是否安全（无绝对路径、盘符、UNC、`..`、控制字符）。 */
function unsafePath(item: DeliveryItem): boolean {
  const path = item.path;
  if (path === null) return false;
  if (/[\u0000-\u001f\u007f]/.test(path)) return true;
  if (path.startsWith('/') || path.startsWith('\\') || /^[A-Za-z]:/.test(path)) return true;
  if (path.startsWith('~')) return true;
  if (path.split(/[\\/]+/).some(segment => segment === '..' || segment === '.')) return true;
  // 反斜杠分隔的 Windows 相对路径等价于正斜杠：先归一化再核对语法。
  return !DELIVERY_SAFE_PATH.test(path.replace(/\\/g, '/'));
}

/* ------------------------------------------------------------------ 格式解析 */

export type DeliveryFormatCatalog = readonly (DeliveryFormatId | string)[];

function isFormatId(value: string): value is DeliveryFormatId {
  return (DELIVERY_FORMAT_IDS as readonly string[]).includes(value);
}

/** 格式 → 适用对象种类的唯一查表入口；未知格式的适用面是**空**，不是"全部"。 */
function kindsOf(format: string): readonly DeliveryItemKind[] {
  return isFormatId(format) ? DELIVERY_FORMAT_KINDS[format] : [];
}

/** 该格式是否被这份授权允许；`formats` 缺省时退回原 owner 自己的适用面。 */
function formatPermitted(format: string, entitlements: DeliveryEntitlements): boolean {
  return entitlements.can_export && entitlements.formats.includes(format as DeliveryFormatId);
}

/**
 * 对**某一个对象**而言，当前真正可用的格式列表。
 *
 * 原 owner 是格式可用性的唯一权威（`ExportJobService.create()` 用 `SUPPORTED` 判定并
 * 抛出 `ValueError("unsupported export format")`；`tests/test_export_jobs.py::
 * test_export_job_rejects_unknown_format` 就是这条）。这里的列表只做两件事：
 * 复述原 owner 声明的适用面，并与当前身份被授予的 `formats` 取交集 —— 它只会**减少**
 * 可选项，永远不会凭空造出一个右上角写着"可用"的假格式。
 */
export function formatAvailability(item: DeliveryItem, entitlements: DeliveryEntitlements): DeliveryFormatId[] {
  if (!entitlements.can_export || item.kind === null) return [];
  return entitlements.formats.filter(format =>
    DELIVERY_FORMAT_KINDS[format].includes(item.kind as DeliveryItemKind));
}

/**
 * 对某一个对象的显式格式拒绝。可用时为 `null`；不可用时返回的 `state` 恒为 `'REFUSED'`。
 * 拒绝里带着 `available_formats`，因此操作者总能看到下一步能选什么。
 */
export function formatRefusal(
  item: DeliveryItem, format: string, entitlements: DeliveryEntitlements,
): DeliveryFormatRefusal | null {
  const available = formatAvailability(item, entitlements);
  if (formatPermitted(format, entitlements) && item.kind !== null
    && DELIVERY_FORMAT_KINDS[format as DeliveryFormatId].includes(item.kind)) return null;
  const unknown = !isFormatId(format);
  return {
    state: 'REFUSED',
    code: unknown ? DELIVERY_CODES.formatUnknown : DELIVERY_CODES.formatNotApplicable,
    message: unknown
      ? `原导出服务不认识格式“${format}”，未创建任何导出任务。`
      : item.kind === null
        ? '这个对象没有声明种类，无法证明该格式能写出它，因此未创建任何导出任务。'
        : `格式“${format}”不适用于${item.kind === null ? '该对象' : item.kind}，未创建任何导出任务。`,
    requested_format: format,
    available_formats: available,
  };
}

/* ------------------------------------------------------------------ 单对象判定 / 排斥 */

type Rejection = { reason: DeliveryExclusionReason; code: string; message: string };

/** 单对象的排斥判据。返回 `null` 表示这一条**可以**进入交接包。 */
function rejectItem(item: DeliveryItem, entitlements: DeliveryEntitlements): Rejection | null {
  const end = (reason: DeliveryExclusionReason, code: string): Rejection =>
    ({ reason, code, message: DELIVERY_EXCLUSION_REASON_LABELS[reason] });
  // 授权本身：没有导出权利时，一切都排斥（但理由要说清是"权利"而不是"对象坏了"）。
  if (!entitlements.can_export) return end('ENTITLEMENT_DENIED', DELIVERY_CODES.itemNotExportable);
  // 他项目对象：先判身份，任何"借来的 id"都进不来。
  if (item.novel_id === null || item.novel_id !== entitlements.project_id) {
    return end('FOREIGN_PROJECT', DELIVERY_CODES.itemForeignProject);
  }
  if (secretBearing(item)) return end('SECRET_BEARING', DELIVERY_CODES.secretBearing);
  if (modelArtifact(item)) return end('MODEL_ARTIFACT', DELIVERY_CODES.modelArtifact);
  if (forbiddenPathSegment(item)) return end('PATH_FORBIDDEN', DELIVERY_CODES.pathForbidden);
  if (unsafePath(item)) return end('PATH_UNSAFE', DELIVERY_CODES.pathUnsafe);
  if (!DELIVERY_ITEM_ID.test(item.id)) return end('IDENTITY_INVALID', DELIVERY_CODES.itemInvalid);
  if (item.kind === null) return end('KIND_NOT_ENTITLED', DELIVERY_CODES.itemKindUnavailable);
  if (!entitlements.item_kinds.includes(item.kind)) return end('KIND_NOT_ENTITLED', DELIVERY_CODES.itemNotExportable);
  if (item.media_type !== null && (DELIVERY_FORBIDDEN_MEDIA_TYPES as readonly string[]).includes(item.media_type)) {
    return end('MEDIA_TYPE_FORBIDDEN', DELIVERY_CODES.secretBearing);
  }
  if (item.visibility !== null && item.visibility !== 'VISIBLE') {
    return end('VISIBILITY_NOT_EXPORTABLE', DELIVERY_CODES.itemNotExportable);
  }
  if (item.version === null || !Number.isSafeInteger(item.version) || item.version < 1) {
    return end('VERSION_MISSING', DELIVERY_CODES.itemInvalid);
  }
  if (item.digest === null) return end('DIGEST_MISSING', DELIVERY_CODES.itemInvalid);
  if (!DELIVERY_DIGEST.test(item.digest)) return end('DIGEST_INVALID', DELIVERY_CODES.itemInvalid);
  if (item.size_bytes === null || !Number.isSafeInteger(item.size_bytes) || item.size_bytes < 0) {
    return end('SIZE_INVALID', DELIVERY_CODES.itemInvalid);
  }
  if (item.size_bytes > entitlements.max_item_bytes) return end('ITEM_TOO_LARGE', DELIVERY_CODES.itemTooLarge);
  return null;
}

/**
 * 单个对象能否独立导出（S11）。
 *
 * 只看这一个对象 + 这份授权（+ 可选的一个格式）。**没有**项目完成度、其他对象、
 * 任务队列或"整包是否齐备"这些参数 —— 因此单个对象是否可导出，在类型层面就不依赖
 * 项目其余部分是否完成。缺参数时返回 `available_formats` 供操作者选择。
 */
export function exportableItem(
  item: DeliveryItem, entitlements: DeliveryEntitlements, format?: string,
): DeliveryItemExportDecision {
  const rejected = rejectItem(item, entitlements);
  const refused = (reason: DeliveryExclusionReason | null, code: string, message: string): DeliveryItemExportDecision =>
    ({ state: 'REFUSED', item_id: item.id, kind: item.kind, code, message, reason, available_formats: formatAvailability(item, entitlements) });
  if (rejected) return refused(rejected.reason, rejected.code, rejected.message);
  if (format !== undefined) {
    const refusal = formatRefusal(item, format, entitlements);
    if (refusal) return refused(null, refusal.code, refusal.message);
  }
  if (!entitlements.formats.length) {
    return refused(null, DELIVERY_CODES.formatNotApplicable, '当前身份没有任何可用导出格式，未创建任何导出任务。');
  }
  const chosen = format ?? entitlements.formats.find(candidate =>
    item.kind !== null && DELIVERY_FORMAT_KINDS[candidate].includes(item.kind));
  if (!chosen) {
    return refused(null, DELIVERY_CODES.itemKindUnavailable, '原导出服务当前没有能写出这类对象的格式，未创建任何导出任务。');
  }
  return {
    state: 'EXPORTABLE', item_id: item.id, kind: item.kind as DeliveryItemKind,
    format: chosen as DeliveryFormatId, independent_of_project_completion: true,
  };
}

/* ------------------------------------------------------------------ 工程交接清单 */

/** 单条选择最多包含多少对象；与 `DELIVERY_MANIFEST_ITEM_LIMIT` 同源。 */
export const DELIVERY_SELECTION_LIMIT = DELIVERY_MANIFEST_ITEM_LIMIT;

function exclusionOf(item: DeliveryItem, rejection: Rejection | null, override?: DeliveryExclusionReason): HandoverExclusion {
  const reason = override ?? rejection?.reason ?? 'IDENTITY_INVALID';
  return {
    id: item.id.length <= 255 ? item.id : null,
    kind: item.kind,
    reason,
    code: override === 'DUPLICATE_ITEM' ? DELIVERY_CODES.itemDuplicate : (rejection?.code ?? DELIVERY_CODES.itemInvalid),
    message: DELIVERY_EXCLUSION_REASON_LABELS[reason],
  };
}

/**
 * 工程交接包清单。
 *
 * 只包含**被显式勾选**、且当前身份**有权导出**的对象；每一条都带原 owner 声明的
 * `version` 与 `digest`。其余一律进入 `excluded[]` 并说明原因。下面的排斥是**默认拒绝**：
 * 模型权重、依赖目录、凭据/密钥、他项目对象、无法核对版本或摘要的对象都进不来。
 */
export function handoverManifest(selection: unknown, entitlements: DeliveryEntitlements): HandoverManifest {
  const rows = Array.isArray(selection) ? selection : [];
  const entries: HandoverEntry[] = [];
  const excluded: HandoverExclusion[] = [];
  const seen = new Set<string>();
  let total = 0;
  let measured = true;
  for (const raw of rows.slice(0, DELIVERY_MANIFEST_ITEM_LIMIT)) {
    const item = raw as DeliveryItem;
    if (!item || typeof item !== 'object' || typeof item.id !== 'string') {
      excluded.push({
        id: null, kind: null, reason: 'IDENTITY_INVALID', code: DELIVERY_CODES.itemInvalid,
        message: DELIVERY_EXCLUSION_REASON_LABELS.IDENTITY_INVALID,
      });
      continue;
    }
    const rejection = rejectItem(item, entitlements);
    if (rejection) { excluded.push(exclusionOf(item, rejection)); continue; }
    if (seen.has(item.id)) { excluded.push(exclusionOf(item, null, 'DUPLICATE_ITEM')); continue; }
    seen.add(item.id);
    const size = item.size_bytes as number;
    // 超限也照样进 excluded[]：清单里不会出现一条"装不进去却列在里面"的条目。
    if (total + size > entitlements.max_package_bytes) {
      excluded.push(exclusionOf(item, {
        reason: 'ITEM_TOO_LARGE', code: DELIVERY_CODES.packageTooLarge,
        message: DELIVERY_EXCLUSION_REASON_LABELS.ITEM_TOO_LARGE,
      }));
      measured = false;
      continue;
    }
    total += size;
    entries.push({
      id: item.id, kind: item.kind as DeliveryItemKind, version: item.version as number,
      digest: item.digest as string, size_bytes: size, media_type: item.media_type, path: item.path,
    });
  }
  if (rows.length > DELIVERY_MANIFEST_ITEM_LIMIT) {
    excluded.push({
      id: null, kind: null, reason: 'DUPLICATE_ITEM', code: DELIVERY_CODES.manifestOverflow,
      message: `一次选择最多清点 ${DELIVERY_MANIFEST_ITEM_LIMIT} 个对象，超出部分未进入交接包。`,
    });
  }
  return {
    project_id: entitlements.project_id,
    identity: entitlements.identity,
    generated_from: 'SELECTION',
    entries,
    excluded,
    total_bytes: measured ? total : null,
    explicitly_selected: true,
    contains_models: false,
    contains_dependencies: false,
    contains_credentials: false,
    contains_foreign_project_objects: false,
  };
}

/* ------------------------------------------------------------------ 回执状态与恢复 */

/**
 * 回执三态。
 *
 * - `RETURNED`：确实拿到了属于本次请求的回执（原 owner 的状态才是结论）。
 * - `DISPATCHED`：请求已经离开本机，但还没有回执 —— **不是成功**。
 * - `UNKNOWN`：连"请求已经离开本机"都无法确认（没有请求记录，或回执与本请求不匹配）。
 *
 * `receipt` 与 `request` 的格式/项目不一致时判为 `UNKNOWN`：宁可承认"不知道"，
 * 也绝不把一条别的请求的回执渲染成这一次的成功。
 */
export function receiptState(attempt: {
  project_id: string; request: DeliveryRequest | null; receipt: DeliveryReceipt | null;
}): DeliveryReceiptState {
  if (!attempt || typeof attempt !== 'object') return 'UNKNOWN';
  // 没有请求记录：连"已经离开本机"都无法确认（哪怕意外带了一条回执，也无法证明它属于本次请求）。
  if (!attempt.request) return 'UNKNOWN';
  const receipt = attempt.receipt;
  if (!receipt) return 'DISPATCHED';
  if (receipt.project_id !== attempt.project_id) return 'UNKNOWN';
  if (receipt.format !== attempt.request.format) return 'UNKNOWN';
  return 'RETURNED';
}

function timestampOf(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

/**
 * 恢复指令：**复原原请求**，而不是再派发一次。
 *
 * - `UNKNOWN` → 按同一个 `Idempotency-Key` + `format` 重新**读取** `/api/exports`
 *   （原 owner 的 `create()` 对 24 小时内的同 key 调用直接返回同一条记录，因此
 *   即便有人手动重发也只会拿到同一个任务；本目录连发都不发）。
 * - `DISPATCHED` → 按回执 id 重新读取同一条任务。
 * - `RETURNED` → 若原 owner 判定失败/取消，`owner_retry_path` **只用于展示**：
 *   重试由原 owner 的端点执行，本目录不调用它。
 *
 * 返回的 `read.method` 结构上恒为 `'GET'`，`original_request.dispatched` 恒为 `false`：
 * 这里没有任何路径能产生第二次派发。
 */
export function receiptRecovery(attempt: {
  project_id: string; request: DeliveryRequest | null; receipt: DeliveryReceipt | null;
}): DeliveryRecovery {
  const state = receiptState(attempt);
  const request = attempt?.request ?? null;
  const receipt = attempt?.receipt ?? null;
  const original = request
    ? { ...request, dispatched: false as const }
    : null;
  const projectId = attempt?.project_id ?? '';
  const history: DeliveryReadPlan | null = request ? {
    method: 'GET',
    path: `/api/exports?novel_id=${encodeURIComponent(projectId)}&limit=50`,
    match: { format: request.format, idempotency_key: request.idempotency_key, branch_id: request.branch_id },
  } : null;
  const byReceipt: DeliveryReadPlan | null = receipt ? {
    method: 'GET', path: `/api/exports/${encodeURIComponent(receipt.id)}`,
    match: { format: receipt.format, idempotency_key: request?.idempotency_key ?? '', branch_id: request?.branch_id ?? null },
  } : null;
  if (state === 'UNKNOWN') {
    return {
      state,
      code: 'REREAD_BY_IDEMPOTENCY_KEY',
      instruction: request
        ? '原请求参数已保留：请按同一个幂等键重新读取原回执，核对它是否已经在原导出服务里存在；本目录不会再次派发。'
        : '既没有请求记录也没有回执，无法确认是否派发过；请先在原导出服务查询该项目的历史，本目录不会再次派发。',
      original_request: original,
      read: history,
      owner_retry_path: null,
      confirmed_success: false,
    };
  }
  if (state === 'DISPATCHED') {
    return {
      state,
      code: 'REREAD_ORIGINAL_JOB',
      instruction: '请求已离开本机但结果未确认：请重新读取原任务回执；在拿到回执之前，这里不会显示成功。',
      original_request: original,
      read: history,
      owner_retry_path: null,
      confirmed_success: false,
    };
  }
  const success = receipt?.status === 'succeeded';
  const terminal = receipt?.status === 'failed' || receipt?.status === 'cancelled' || success;
  return {
    state,
    code: success ? 'NO_ACTION_REQUIRED' : terminal ? 'ORIGINAL_OWNER_RETRY_ENDPOINT' : 'REREAD_ORIGINAL_JOB',
    instruction: success
      ? '原导出服务已确认完成；下载与验收由原 owner 负责。'
      : terminal
        ? '原导出服务判定这次尝试未成功：需要重试时请使用原 owner 的重试端点，本目录不会代为派发。'
        : '回执已返回但尚未终结：请重新读取原任务回执，直到原 owner 给出确定状态。',
    original_request: original,
    read: byReceipt,
    owner_retry_path: terminal && !success ? `/api/exports/${encodeURIComponent(receipt?.id ?? '')}/retry` : null,
    confirmed_success: success,
  };
}

/** 回执是否可以被显示成"完成"：只有原 owner 的真实 succeeded 回执才是。 */
export function receiptShowsSuccess(receipt: DeliveryReceipt | null): boolean {
  return receipt !== null && receipt.status === 'succeeded';
}

/* ------------------------------------------------------------------ 限额报告 */

/**
 * 在**撞上**限额之前把真实限额说清楚，并拒绝上调。
 *
 * 上限来自原 owner（`app/export_formats.py::MAX_RESOURCE_BYTES` /
 * `MAX_PACKAGE_RESOURCE_BYTES`，`ExportJobService.MAX_RESULT_BYTES`）。`limits_raised`
 * 恒为 `false`，没有任何参数能改它；超限时结论是 `EXCEEDED` 且列出被拒对象，
 * 而不是悄悄丢掉几条把包装下。
 */
export function sizeAndLimitsReport(selection: unknown, entitlements: DeliveryEntitlements): DeliverySizeLimitsReport {
  const rows = (Array.isArray(selection) ? selection : []).slice(0, DELIVERY_MANIFEST_ITEM_LIMIT) as DeliveryItem[];
  const seen = new Set<string>();
  const ids: string[] = [];
  const unmeasured: string[] = [];
  const refused: string[] = [];
  let total = 0;
  let over = false;
  const counting = entitlements.max_items > 0 ? entitlements.max_items : DELIVERY_MANIFEST_ITEM_LIMIT;
  for (const item of rows) {
    if (!item || typeof item !== 'object' || typeof item.id !== 'string' || seen.has(item.id)) continue;
    seen.add(item.id);
    if (Number.isSafeInteger(item.size_bytes) && (item.size_bytes as number) >= 0) total += item.size_bytes as number;
    else unmeasured.push(item.id);
    if (Number.isSafeInteger(item.size_bytes) && (item.size_bytes as number) > entitlements.max_item_bytes) {
      over = true; refused.push(item.id);
    }
  }
  ids.push(...seen);
  const countExceeded = seen.size > counting;
  if (countExceeded) {
    refused.push(...[...seen].filter(id => !refused.includes(id)));
    over = true;
  }
  const packageExceeded = total > entitlements.max_package_bytes;
  if (packageExceeded) {
    over = true;
    for (const id of seen) if (!refused.includes(id)) refused.push(id);
  }
  const limits: DeliveryLimitFact[] = [
    {
      code: 'ITEM_BYTES', limit: entitlements.max_item_bytes,
      observed: rows.reduce((peak: number, item) => (item && Number.isSafeInteger(item.size_bytes)
        ? Math.max(peak, item.size_bytes as number) : peak), 0),
      exceeded: rows.some(item => item && Number.isSafeInteger(item.size_bytes) && (item.size_bytes as number) > entitlements.max_item_bytes),
      label: `单个对象上限 ${entitlements.max_item_bytes} 字节（原 owner 声明）`,
    },
    {
      code: 'PACKAGE_BYTES', limit: entitlements.max_package_bytes, observed: total,
      exceeded: packageExceeded, label: `整包上限 ${entitlements.max_package_bytes} 字节（原 owner 声明）`,
    },
    {
      code: 'ITEM_COUNT', limit: counting, observed: seen.size, exceeded: countExceeded,
      label: `一次最多 ${counting} 个对象（原 owner 声明）`,
    },
  ];
  const verdict: DeliverySizeLimitsReport['verdict'] = over ? 'EXCEEDED' : unmeasured.length ? 'UNMEASURED' : 'WITHIN_LIMITS';
  return {
    items: seen.size,
    total_bytes: unmeasured.length ? null : total,
    unmeasured,
    limits,
    verdict,
    limits_raised: false,
    refused_items: ids.filter(id => refused.includes(id)),
  };
}

/** 界面文案：原 owner 自己声明的三条限额，供面板在不撞线之前就展示。 */
export const DELIVERY_DECLARED_LIMITS = Object.freeze({
  item_bytes: DELIVERY_ITEM_BYTES_LIMIT,
  package_bytes: DELIVERY_PACKAGE_BYTES_LIMIT,
  items: DELIVERY_MANIFEST_ITEM_LIMIT,
  notice: DELIVERY_NOTICES.limitsAreOwnerDeclared,
} as const);
