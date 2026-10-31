import { ApiError } from '../api';
import {
  DELIVERY_BOUNDS, DELIVERY_CODES, DELIVERY_DIGEST, DELIVERY_FORMAT_IDS, DELIVERY_IDENTITY_TOKEN,
  DELIVERY_IDEMPOTENCY_KEY, DELIVERY_ITEM_ID, DELIVERY_ITEM_KINDS, DELIVERY_ITEM_VISIBILITIES,
  DELIVERY_JOB_ID, DELIVERY_JOB_STATUSES, DELIVERY_MANIFEST_ITEM_LIMIT, DELIVERY_SAFE_PATH,
  type DeliveryAttempt, type DeliveryEntitlements, type DeliveryFormatId, type DeliveryItem,
  type DeliveryItemKind, type DeliveryItemVisibility, type DeliveryJson, type DeliveryMissingResource,
  type DeliveryReceipt, type DeliveryReceiptError, type DeliveryReceiptPage, type DeliveryRequest,
  type DeliveryScope, type DeliverySourceVersion,
} from './deliveryTypes';

/**
 * 绝不信任返回的形状：未知键、无界文本、控制字符、越界整数、重复取值、他项目/他分支
 * 身份、自相矛盾的回执都是被拒绝的读取。严格解码器只认原 owner 真实下发过的键
 * （见 `deliveryTypes.ts` 顶部对 `_normalise_job()` / `public()` 的引用）。
 *
 * 与 `productionWorkflowContract.ts` 的关键差别：这里**没有任何写接口的解码器**。
 * 本目录不派发导出，因此也没有"请求体校验"这一类函数。
 */

function invalid(): never {
  throw new ApiError({ status: 200, code: DELIVERY_CODES.receiptInvalid, message: '导出回执数据不可用，请重新读取。' });
}
function mismatch(): never {
  throw new ApiError({ status: 403, code: DELIVERY_CODES.scopeMismatch, message: '导出交付与当前项目或分支不一致，请重新打开。' });
}
function object(value: unknown, allowed: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !allowed.includes(key))) invalid();
  return row;
}
function text(value: unknown, maximum: number): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid();
  return value;
}
function optionalText(value: unknown, maximum: number): string | null {
  if (value === undefined || value === null) return null;
  return text(value, maximum);
}
function integer(value: unknown, maximum = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > maximum) invalid();
  return value;
}
function bool(value: unknown): boolean {
  if (typeof value !== 'boolean') invalid();
  return value;
}
function list(value: unknown, maximum: number): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) invalid();
  return value;
}
function enumerated<T extends string>(value: unknown, allowed: readonly T[]): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) invalid();
  return value as T;
}
function timestamp(value: unknown): string {
  const stamp = text(value, DELIVERY_BOUNDS.timestamp);
  if (Number.isNaN(Date.parse(stamp))) invalid();
  return stamp;
}
function token(value: unknown, maximum: number, pattern: RegExp): string {
  const raw = text(value, maximum);
  if (!pattern.test(raw)) invalid();
  return raw;
}
function unique(values: readonly string[]): void {
  if (new Set(values).size !== values.length) invalid();
}

/* ------------------------------------------------------------------ 身份 */

/** 一个 `file:<uuid>` / `postgres:<id>` 形态的 owner 身份令牌，绝不是裸路径。 */
export function deliveryIdentity(value: unknown): string {
  return token(value, DELIVERY_BOUNDS.id, DELIVERY_IDENTITY_TOKEN);
}

export function deliveryProjectId(value: unknown): string {
  return token(value, DELIVERY_BOUNDS.project_id, DELIVERY_IDENTITY_TOKEN);
}

/** `/api/exports/{job_id}` 的回执 id（`ExportJobService.create()` 写入的 UUID4）。 */
export function deliveryJobId(value: unknown): string {
  return token(value, 36, DELIVERY_JOB_ID);
}

/**
 * 原 owner 归一化后的规范格式 id。别名（`md`/`text`/`word`/`screenplay-standard`）会被
 * `create()` 改写，所以到达界面时只会是规范写法；这里额外接纳别名只会伪造格式。
 */
export function deliveryFormatId(value: unknown): DeliveryFormatId {
  if (typeof value !== 'string' || !(DELIVERY_FORMAT_IDS as readonly string[]).includes(value)) {
    throw new ApiError({ status: 200, code: DELIVERY_CODES.formatUnknown, message: '原导出服务不认识这个导出格式。' });
  }
  return value as DeliveryFormatId;
}

export function deliveryScope(value: unknown, projectId: string, expected?: DeliveryScope): DeliveryScope {
  const row = object(value, ['mode', 'novel_id', 'workspace_id', 'project_id', 'storyline_id', 'branch_id']);
  const scope: DeliveryScope = {
    mode: enumerated(row.mode, ['local', 'collaboration'] as const),
    novel_id: deliveryProjectId(row.novel_id),
  };
  for (const key of ['workspace_id', 'project_id', 'storyline_id', 'branch_id'] as const) {
    if (row[key] !== undefined) scope[key] = optionalText(row[key], DELIVERY_BOUNDS.project_id);
  }
  if (scope.novel_id !== projectId) mismatch();
  const wanted = expected ?? { mode: 'local' as const, novel_id: projectId };
  if (scope.mode !== wanted.mode
    || (['workspace_id', 'project_id', 'storyline_id', 'branch_id'] as const).some(key => (scope[key] ?? null) !== (wanted[key] ?? null))) mismatch();
  return scope;
}

/* ------------------------------------------------------------------ 回执 */

/**
 * `source_versions` 是原 owner 从快照里整段复制的**不透明映射**（`snapshot.get(
 * "source_versions", {})`），它的键是数据而不是信封字段，因此这里不接受"未知键"判据；
 * 但每个键与每个值仍然有界，且只保留标量（结构值一律拒绝，绝不转成 `[object Object]`）。
 */
function sourceVersions(value: unknown): DeliverySourceVersion[] {
  if (value === undefined || value === null) return [];
  if (typeof value !== 'object' || Array.isArray(value)) invalid();
  const rows = Object.entries(value as Record<string, unknown>).map(([key, raw]) => {
    const name = text(key, DELIVERY_BOUNDS.label);
    if (typeof raw === 'number') {
      if (!Number.isFinite(raw)) invalid();
      return { key: name, value: raw };
    }
    if (typeof raw === 'string') return { key: name, value: text(raw, DELIVERY_BOUNDS.message) };
    if (typeof raw === 'boolean') return { key: name, value: raw ? 'true' : 'false' };
    invalid();
  });
  if (rows.length > 64) invalid();
  unique(rows.map(entry => entry.key));
  return rows;
}

function missingResources(value: unknown, maximum: number): DeliveryMissingResource[] {
  if (value === undefined || value === null) return [];
  return list(value, maximum).map(entry => {
    const row = object(entry, ['id', 'reason']);
    return { id: text(row.id, DELIVERY_BOUNDS.id), reason: optionalText(row.reason, DELIVERY_BOUNDS.message) };
  });
}

function receiptError(value: unknown): DeliveryReceiptError | null {
  if (value === undefined || value === null) return null;
  const row = object(value, ['code', 'message']);
  return { code: text(row.code, DELIVERY_BOUNDS.label), message: text(row.message, DELIVERY_BOUNDS.message) };
}

/**
 * 一条 `ExportJobService` 的公开回执行。`public()` 只移除 `snapshot` / `idempotency_key`
 * / `artifact`（以及结果体里的 `content` / `content_base64`），所以键集可以逐条核对。
 *
 * 重要的**缺失即缺失**：没有 `result.filename` 的 `succeeded` 回执保留
 * `result_filename: null`，绝不补一个文件名；未知状态码保留 `raw_status`，界面按
 * "结果未知"呈现（`status: 'queued'` 只是"未终结"的保守呈现），绝不猜测成完成。
 */
export function deliveryReceipt(value: unknown, projectId: string): DeliveryReceipt {
  const row = object(value, [
    'id', 'novel_id', 'format', 'status', 'created_at', 'updated_at', 'progress', 'progress_message',
    'retry_of', 'attempt', 'cancel_requested', 'recovery_count', 'snapshot_id',
    'source_versions', 'captured_at', 'missing_resources', 'result', 'error',
    'started_at', 'finished_at', 'recovered_at',
    // `_normalise_job()` 保留的本地授权标签：它会被原 owner 自己核对，本目录只按其存在
    // 接受，从不读取、也从不渲染其中任何内容。
    'permission_context',
  ]);
  if (deliveryProjectId(row.novel_id) !== projectId) mismatch();
  // `public()` 保证这三样不下发；出现它们说明这不是真回执，宁可拒绝也不猜测。
  if (row.snapshot !== undefined || row.artifact !== undefined || row.idempotency_key !== undefined) invalid();
  if (row.cancel_requested !== undefined && row.cancel_requested !== null) bool(row.cancel_requested);
  if (typeof row.status !== 'string' || !row.status.trim()) invalid();
  const rawStatus = text(row.status, DELIVERY_BOUNDS.label);
  const known = (DELIVERY_JOB_STATUSES as readonly string[]).includes(rawStatus);
  const result = row.result === undefined || row.result === null ? null : object(row.result, ['format', 'filename', 'media_type', 'size', 'sha256', 'content_encoding']);
  if (result) {
    deliveryFormatId(result.format);
    if (result.content_encoding !== undefined) optionalText(result.content_encoding, DELIVERY_BOUNDS.label);
    if (result.media_type !== undefined) optionalText(result.media_type, DELIVERY_BOUNDS.media_type);
    if (result.size !== undefined) integer(result.size);
    if (result.sha256 !== undefined) token(result.sha256, DELIVERY_BOUNDS.digest, DELIVERY_DIGEST);
  }
  const retryOf = row.retry_of === undefined || row.retry_of === null ? null : deliveryJobId(row.retry_of);
  const snapshotId = row.snapshot_id === undefined || row.snapshot_id === null
    ? null : token(row.snapshot_id, DELIVERY_BOUNDS.id, /^[A-Za-z0-9][A-Za-z0-9:._-]*$/);
  return {
    id: deliveryJobId(row.id),
    project_id: projectId,
    format: String(deliveryFormatId(row.format)),
    status: known ? (rawStatus as DeliveryReceipt['status']) : 'queued',
    raw_status: known ? null : rawStatus,
    created_at: timestamp(row.created_at),
    updated_at: row.updated_at === undefined ? timestamp(row.created_at) : timestamp(row.updated_at),
    progress: row.progress === undefined ? 0 : integer(row.progress, 100),
    progress_message: row.progress_message === undefined ? '' : optionalText(row.progress_message, DELIVERY_BOUNDS.label) ?? '',
    attempt: row.attempt === undefined ? 1 : Math.max(1, integer(row.attempt, 1000)),
    retry_of: retryOf,
    recovery_count: row.recovery_count === undefined ? 0 : integer(row.recovery_count, 1000),
    snapshot_id: snapshotId,
    captured_at: row.captured_at === undefined || row.captured_at === null ? null : timestamp(row.captured_at),
    source_versions: sourceVersions(row.source_versions),
    missing_resources: missingResources(row.missing_resources, 512),
    result_filename: result && result.filename !== undefined && result.filename !== null
      ? text(result.filename, DELIVERY_BOUNDS.label) : null,
    // 只有原 owner 自己声明成功时，"没有错误"才是事实；未终结或失败一律保留它的 error。
    error: known && rawStatus === 'succeeded' ? null : receiptError(row.error),
  };
}

/** `/api/exports` 的一页：`{items, next_offset}`（`ExportJobService.list()` 的返回体）。 */
export function deliveryReceiptPage(value: unknown, projectId: string): DeliveryReceiptPage {
  const row = object(value, ['items', 'next_offset']);
  const items = list(row.items, 100).map(entry => deliveryReceipt(entry, projectId));
  unique(items.map(item => item.id));
  const next = row.next_offset === undefined || row.next_offset === null ? null : integer(row.next_offset, 1_000_000);
  return { items, next_offset: next };
}

/* ------------------------------------------------------------------ 请求与尝试 */

/** 已离开本机的既有导出请求。它是**记录**，不是可重放的命令。 */
export function deliveryRequest(value: unknown): DeliveryRequest {
  const row = object(value, ['format', 'idempotency_key', 'branch_id', 'requested_at']);
  return {
    format: deliveryFormatId(row.format),
    idempotency_key: token(row.idempotency_key, DELIVERY_BOUNDS.idempotency_key, DELIVERY_IDEMPOTENCY_KEY),
    branch_id: optionalText(row.branch_id, DELIVERY_BOUNDS.project_id),
    requested_at: timestamp(row.requested_at),
  };
}

export function deliveryAttempt(value: unknown, projectId: string): DeliveryAttempt {
  const row = object(value, ['project_id', 'request', 'receipt']);
  if (deliveryProjectId(row.project_id) !== projectId) mismatch();
  return {
    project_id: projectId,
    request: deliveryRequest(row.request),
    receipt: row.receipt === undefined || row.receipt === null ? null : deliveryReceipt(row.receipt, projectId),
  };
}

/* ------------------------------------------------------------------ 对象与授权 */

function deliveryJson(value: unknown, depth: number): DeliveryJson {
  if (depth > 4) invalid();
  if (value === null || typeof value === 'boolean') return value;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) invalid();
    return value;
  }
  if (typeof value === 'string') return text(value, DELIVERY_BOUNDS.message);
  if (Array.isArray(value)) {
    if (value.length > 32) invalid();
    return value.map(entry => deliveryJson(entry, depth + 1));
  }
  if (typeof value === 'object') {
    const row = value as Record<string, unknown>;
    if (Object.keys(row).length > 32) invalid();
    return Object.fromEntries(Object.entries(row).map(([key, entry]) => [
      text(key, DELIVERY_BOUNDS.label), deliveryJson(entry, depth + 1),
    ]));
  }
  invalid();
}

/**
 * 一个候选对象。`path` / `version` / `digest` / `size_bytes` / `visibility` / `kind` /
 * `novel_id` 缺失时保持 `null` —— 由 `handoverManifest()` 把它们记入 `excluded[]`，
 * 而不是在这里猜测一个值。`payload` 只用于保留未知事实，永不进入交接包。
 */
export function deliveryItem(value: unknown): DeliveryItem {
  const row = object(value, [
    'id', 'novel_id', 'kind', 'media_type', 'path', 'version', 'digest', 'size_bytes', 'visibility',
    'source', 'contains_secret', 'payload',
  ]);
  const kind = row.kind === undefined || row.kind === null ? null : enumerated<DeliveryItemKind>(row.kind, DELIVERY_ITEM_KINDS);
  const visibility = row.visibility === undefined || row.visibility === null
    ? null : enumerated<DeliveryItemVisibility>(row.visibility, DELIVERY_ITEM_VISIBILITIES);
  const path = row.path === undefined || row.path === null ? null : text(row.path, DELIVERY_BOUNDS.path);
  if (row.version !== undefined && row.version !== null) integer(row.version, 1_000_000);
  if (row.size_bytes !== undefined && row.size_bytes !== null) integer(row.size_bytes, 1_099_511_627_776);
  if (row.digest !== undefined && row.digest !== null) text(row.digest, DELIVERY_BOUNDS.digest);
  const item: DeliveryItem = {
    id: text(row.id, DELIVERY_BOUNDS.id),
    novel_id: row.novel_id === undefined || row.novel_id === null ? null : deliveryProjectId(row.novel_id),
    kind,
    media_type: optionalText(row.media_type, DELIVERY_BOUNDS.media_type),
    path,
    version: row.version === undefined || row.version === null ? null : integer(row.version, 1_000_000),
    digest: row.digest === undefined || row.digest === null ? null : text(row.digest, DELIVERY_BOUNDS.digest),
    size_bytes: row.size_bytes === undefined || row.size_bytes === null ? null : integer(row.size_bytes, 1_099_511_627_776),
    visibility,
    source: optionalText(row.source, DELIVERY_BOUNDS.message),
  };
  if (row.contains_secret !== undefined && row.contains_secret !== null) item.contains_secret = bool(row.contains_secret);
  if (row.payload !== undefined) item.payload = deliveryJson(row.payload, 0);
  return item;
}

export function deliveryItems(value: unknown): DeliveryItem[] {
  return list(value, DELIVERY_MANIFEST_ITEM_LIMIT).map(deliveryItem);
}

/**
 * 当前身份的导出授权。原 owner 是权利的**唯一**来源：这里只核对它自述的事实，
 * 并拒绝自相矛盾的形状（没有权利却列出了可导出的种类/格式）。
 */
export function deliveryEntitlements(value: unknown, projectId: string): DeliveryEntitlements {
  const row = object(value, [
    'project_id', 'identity', 'can_export', 'item_kinds', 'formats',
    'max_item_bytes', 'max_package_bytes', 'max_items',
  ]);
  if (deliveryProjectId(row.project_id) !== projectId) mismatch();
  const canExport = bool(row.can_export);
  const kinds = list(row.item_kinds, DELIVERY_ITEM_KINDS.length).map(entry => enumerated<DeliveryItemKind>(entry, DELIVERY_ITEM_KINDS));
  const formats = list(row.formats, DELIVERY_FORMAT_IDS.length).map(deliveryFormatId);
  unique(kinds);
  unique(formats);
  if (!canExport && (kinds.length || formats.length)) invalid();
  return {
    project_id: projectId,
    identity: deliveryIdentity(row.identity),
    can_export: canExport,
    item_kinds: kinds,
    formats,
    max_item_bytes: integer(row.max_item_bytes),
    max_package_bytes: integer(row.max_package_bytes),
    max_items: integer(row.max_items, DELIVERY_MANIFEST_ITEM_LIMIT),
  };
}

/** 路径是否满足本项目内安全相对路径的语法（`handoverManifest()` 的另一半判据）。 */
export function deliverySafePath(value: string): boolean {
  return DELIVERY_SAFE_PATH.test(value);
}

/** 摘要是否是可核对的 SHA-256。 */
export function deliveryDigest(value: string): boolean {
  return DELIVERY_DIGEST.test(value);
}

/** 本目录自己生成的对象 id 语法（测试与夹具用，不参与线上解码）。 */
export function deliveryItemId(value: unknown): string {
  return token(value, DELIVERY_BOUNDS.id, DELIVERY_ITEM_ID);
}
