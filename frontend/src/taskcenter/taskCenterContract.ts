import { ApiError } from '../api';
import {
  REVIEW_INBOX_ACTIONS, REVIEW_INBOX_APPROVAL_AUTHORITY, REVIEW_INBOX_BATCH_LIMIT, REVIEW_INBOX_BATCH_SEMANTICS,
  REVIEW_INBOX_PROMOTION_RECOVERY_STATES, REVIEW_INBOX_PROMOTION_STATUS,
  REVIEW_INBOX_ACTION_TOKEN, REVIEW_INBOX_STATUS_TOKEN, TASK_ACTIONS, TASK_ACTION_LIMITS, TASK_AUTOMATIC_RETRIES,
  TASK_CANCEL_LIMITS, TASK_CANCEL_REVISION, TASK_CENTER_BOUNDS, TASK_CENTER_ERROR_CODES, TASK_CENTER_STATUS_TOKEN,
  TASK_CENTER_TOKEN, TASK_EXECUTOR, TASK_FORMAL_DOMAINS, TASK_FORMAL_SOURCE_ONLY, TASK_PROVIDER_IDENTIFIER,
  TASK_REFRESH, TASK_ROUTE_STATES, TASK_SAFE_CODES, TASK_STATUS_SET, TASK_UNKNOWN_STATUS,
  TASK_CENTER_REASON_TOKEN,
  type ReviewActionRequest, type ReviewBatchReceipt, type ReviewBatchRequest, type ReviewBatchResult,
  type ReviewInboxAction, type ReviewInboxField, type ReviewInboxItem, type ReviewInboxProjection,
  type ReviewInboxPreview, type ReviewInboxUnavailable,
  type TaskCancelRequest, type TaskCancellationReceipt, type TaskCenterActionLimits, type TaskCenterCost,
  type TaskCenterHistoryEntry, type TaskCenterProgress, type TaskCenterScope,
  type TaskCenterSourcePointer, type TaskCenterStatus, type TaskCenterTask, type TaskCenterTaskAction,
  type TaskCenterTaskQuery, type TaskCenterTasksProjection, type TaskCenterTasksPage, type TaskCenterUnavailable,
  type ReviewInboxQuery,
} from './taskCenterTypes';

/**
 * 严格解码器：拒绝任何未知键、越界文本、控制字符、越界整数，以及内部自相矛盾的
 * 载荷。任务侧/审核侧的"形状非法"和"身份不一致"是两个不同的稳定机器码，因此
 * 共用原语先抛内部标记，再由入口包成对应的 `ApiError`。
 */
class ShapeViolation {
  constructor(readonly kind: 'invalid' | 'mismatch') {}
}
function invalid(): never { throw new ShapeViolation('invalid'); }
function mismatch(): never { throw new ShapeViolation('mismatch'); }
function checked<T>(family: 'tasks' | 'review', run: () => T): T {
  try {
    return run();
  } catch (reason) {
    if (!(reason instanceof ShapeViolation)) throw reason;
    throw family === 'tasks'
      ? reason.kind === 'mismatch'
        ? new ApiError({ status: 403, code: TASK_CENTER_ERROR_CODES.tasksScopeMismatch, message: '任务中心数据与当前项目或分支不一致，请重新打开。' })
        : new ApiError({ status: 200, code: TASK_CENTER_ERROR_CODES.tasksInvalid, message: '任务中心数据不可用或不是原服务声明的形状，请重新读取。' })
      : reason.kind === 'mismatch'
        ? new ApiError({ status: 403, code: TASK_CENTER_ERROR_CODES.inboxScopeMismatch, message: '审核收件箱数据与当前项目或分支不一致，请重新打开。' })
        : new ApiError({ status: 200, code: TASK_CENTER_ERROR_CODES.inboxInvalid, message: '审核收件箱数据不可用或不是原服务声明的形状，请重新读取。' });
  }
}

/** 只接受这些键的对象；多一个键就是拒绝读取。 */
function object(value: unknown, allowed: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !allowed.includes(key))) invalid();
  return row;
}
/**
 * 审核项是 `inbox.py::_normalize` 对**领域原始行**的 `deepcopy(row)` 再 update，
 * 所以领域自己的键（`shot_id`、`title`、`promotion_state`…）必然存在。这里只校验
 * "它确实是个对象"，随后只读取 owner 自己写入的字段；领域键既不进入模型也不渲染。
 * 信封与任务投影仍然执行"多一个键就拒绝"。
 */
function tolerantObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  return value as Record<string, unknown>;
}
function text(value: unknown, maximum: number): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid();
  return value;
}
/** 有界的展示文本：允许空串（owner 会用空串表示"没有预览"），但拒绝控制字符。 */
function scalar(value: unknown, maximum: number): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') {
    if (value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid();
    return value;
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) invalid();
    return bounded(String(value), maximum);
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  let encoded: string;
  try { encoded = JSON.stringify(value) ?? ''; } catch { invalid(); }
  return bounded(encoded, maximum);
}
function bounded(value: string, maximum: number): string {
  if (value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid();
  return value;
}
/** 有界字符串（允许空串）：查询参数等"空即不过滤"的字段。 */
function queryText(value: unknown, maximum: number): string {
  if (typeof value !== 'string' || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid();
  return value;
}
function token(value: unknown, grammar: RegExp, maximum: number): string {  if (typeof value !== 'string' || value.length > maximum || !grammar.test(value)) invalid();
  return value;
}
function integer(value: unknown, maximum = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > maximum) invalid();
  return value;
}
function optionalInteger(value: unknown, maximum = Number.MAX_SAFE_INTEGER): number | null {
  return value === null || value === undefined ? null : integer(value, maximum);
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
/** 未在 owner 词表内的状态一律按 `UNKNOWN` 呈现，绝不猜测成其他阶段。 */
function statusOf(value: unknown): { status: TaskCenterStatus; raw: string } {
  const raw = token(value, TASK_CENTER_STATUS_TOKEN, TASK_CENTER_BOUNDS.status);
  return { status: (TASK_STATUS_SET.has(raw) ? raw : TASK_UNKNOWN_STATUS) as TaskCenterStatus, raw };
}
function unique<T>(values: T[]): T[] {
  if (new Set(values).size !== values.length) invalid();
  return values;
}
/** `ux.py::task_identifier`：只回显有界的 provider/model 标识，绝不回显 URL 或凭据。 */
function providerIdentifier(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const candidate = token(value, TASK_PROVIDER_IDENTIFIER, TASK_CENTER_BOUNDS.provider);
  if (candidate.includes('://')) invalid();
  if (['sk-', 'bearer ', 'token ', 'password', 'secret'].some(prefix => candidate.toLowerCase().startsWith(prefix))) invalid();
  return candidate;
}
/** owner 披露的键→基本类型映射（`projected_task` 的 source / owner_navigation）。 */
function pointer(value: unknown): TaskCenterSourcePointer | null {
  if (value === null || value === undefined) return null;
  const row = tolerantObject(value);
  const keys = Object.keys(row);
  if (keys.length > TASK_CENTER_BOUNDS.pointer_entries) invalid();
  const checked: Record<string, string | number | boolean | null> = {};
  for (const key of keys) {
    if (!TASK_CENTER_TOKEN.test(key) || key.length > TASK_CENTER_BOUNDS.pointer_key) invalid();
    const entry = row[key];
    if (entry === null) { checked[key] = null; continue; }
    if (typeof entry === 'string') { checked[key] = text(entry, TASK_CENTER_BOUNDS.pointer_value); continue; }
    if (typeof entry === 'number') { checked[key] = integer(entry); continue; }
    if (typeof entry === 'boolean') { checked[key] = entry; continue; }
    // 嵌套结构不属于来源指针契约：不猜，直接拒绝。
    invalid();
  }
  return Object.freeze(checked);
}
/** 有界的键→值清单：候选预览、来源版本、结果目标都用同一个规范化。 */
function fields(value: unknown, maximum: number): ReviewInboxField[] {
  const row = tolerantObject(value);
  const keys = Object.keys(row);
  if (keys.length > maximum) invalid();
  return keys.map(key => {
    if (!key.trim() || key.length > TASK_CENTER_BOUNDS.field_key || /[\u0000-\u001f\u007f]/.test(key)) invalid();
    return { key, value: scalar(row[key], TASK_CENTER_BOUNDS.field_value) };
  });
}
/** `_normalize` 的 scope 就是授权上下文本身；逐字复用生产的比较语义。 */
function scoped(value: unknown, projectId: string, expected?: TaskCenterScope): TaskCenterScope {
  const row = object(value, ['mode', 'novel_id', 'workspace_id', 'project_id', 'storyline_id', 'branch_id']);
  const scope: TaskCenterScope = {
    mode: enumerated(row.mode, ['local', 'collaboration'] as const),
    novel_id: text(row.novel_id, TASK_CENTER_BOUNDS.project_id),
  };
  for (const key of ['workspace_id', 'project_id', 'storyline_id', 'branch_id'] as const) {
    if (row[key] !== undefined) scope[key] = row[key] === null ? null : text(row[key], TASK_CENTER_BOUNDS.project_id);
  }
  if (scope.novel_id !== projectId) mismatch();
  const wanted = expected ?? { mode: 'local' as const, novel_id: projectId };
  if (scope.mode !== wanted.mode || scope.novel_id !== wanted.novel_id
    || (['workspace_id', 'project_id', 'storyline_id', 'branch_id'] as const).some(key => (scope[key] ?? null) !== (wanted[key] ?? null))) mismatch();
  return scope;
}

/* --------------------------------------------------------------- 任务投影 */

/** `projected_task()` 返回体的全部键（多一个即拒绝；见 `app/experimental/ux.py`）。 */
const TASK_KEYS = [
  'source', 'owner_navigation', 'id', 'authority', 'label', 'version', 'status', 'stage_label', 'feature', 'progress',
  'history', 'stale', 'cost', 'error_code', 'provider_id', 'model_id', 'route_state', 'actions', 'action_limits',
  'retry_policy', 'lifecycle', 'navigation_contract', 'source_domain', 'revision',
] as const;

function progress(value: unknown): TaskCenterProgress | null {
  // owner 只在 completed/total 都是整数且 0 <= completed <= total、total > 0 时给出进度；
  // 其余情况是 `null`。这里保持缺失语义，绝不补 0%。
  if (value === null || value === undefined) return null;
  const row = object(value, ['completed', 'total', 'unit']);
  const total = integer(row.total), completed = integer(row.completed);
  if (total <= 0 || completed > total) invalid();
  return { completed, total, unit: text(row.unit, TASK_CENTER_BOUNDS.unit) };
}
function history(value: unknown): TaskCenterHistoryEntry[] {
  return list(value, TASK_CENTER_BOUNDS.history).map(entry => {
    const row = object(entry, ['version', 'status']);
    return { version: optionalInteger(row.version), status: statusOf(row.status).status };
  });
}
function cost(value: unknown): TaskCenterCost {
  const row = object(value, ['estimate', 'actual', 'state']);
  if (row.state !== 'UNKNOWN') invalid();
  return { estimate: optionalInteger(row.estimate), actual: optionalInteger(row.actual), state: 'UNKNOWN' };
}
function actionLimits(value: unknown, actions: TaskCenterTaskAction[]): TaskCenterActionLimits {
  const row = object(value, ['cancel', 'retry', 'resume', 'review']);
  const cancel = row.cancel === null || row.cancel === undefined ? null : enumerated(row.cancel, TASK_CANCEL_LIMITS);
  if (row.retry !== TASK_ACTION_LIMITS.retry || row.resume !== TASK_ACTION_LIMITS.resume
    || row.review !== TASK_ACTION_LIMITS.review) invalid();
  // `projected_task` 只在允许取消时把 limits.cancel 置空；两者必须一致。
  if ((cancel === null) !== actions.includes('cancel')) invalid();
  return { cancel, retry: TASK_ACTION_LIMITS.retry, resume: TASK_ACTION_LIMITS.resume, review: TASK_ACTION_LIMITS.review };
}
function task(value: unknown): TaskCenterTask {
  const row = object(value, TASK_KEYS);
  const { status, raw } = statusOf(row.status);
  const actions = unique(list(row.actions, TASK_ACTIONS.length).map(entry => enumerated(entry, TASK_ACTIONS)));
  const limits = actionLimits(row.action_limits, actions);
  const navigationContract = row.navigation_contract === null || row.navigation_contract === undefined
    ? null : enumerated(row.navigation_contract, [TASK_FORMAL_SOURCE_ONLY] as const);
  const sourceDomain = row.source_domain === null || row.source_domain === undefined
    ? null : enumerated(row.source_domain, TASK_FORMAL_DOMAINS);
  const source = pointer(row.source);
  if (navigationContract === TASK_FORMAL_SOURCE_ONLY && (source !== null || sourceDomain === null)) invalid();
  if (navigationContract === TASK_FORMAL_SOURCE_ONLY && actions.includes('open_source')) invalid();
  const revision = row.revision === null || row.revision === undefined
    ? '' : token(row.revision, TASK_CANCEL_REVISION, 64);
  // 取消必须能原样回传 `TaskCancelIn.expected_revision`；没有合法 revision 就没有取消按钮。
  if (actions.includes('cancel') && !revision) invalid();
  if (row.retry_policy !== TASK_ACTION_LIMITS.retry_policy) invalid();
  const errorCode = row.error_code === null || row.error_code === undefined
    ? null : token(row.error_code, /^[A-Z][A-Z0-9_]{0,63}$/, TASK_CENTER_BOUNDS.error_code);
  if (errorCode !== null && !TASK_SAFE_CODES.includes(errorCode)) invalid();
  return {
    id: text(row.id, TASK_CENTER_BOUNDS.item_id),
    authority: token(row.authority, TASK_CENTER_TOKEN, TASK_CENTER_BOUNDS.authority),
    label: text(row.label, TASK_CENTER_BOUNDS.label),
    feature: token(row.feature, TASK_CENTER_TOKEN, TASK_CENTER_BOUNDS.feature),
    status, raw_status: raw,
    stage_label: text(row.stage_label, TASK_CENTER_BOUNDS.stage_label),
    version: optionalInteger(row.version),
    progress: progress(row.progress),
    history: history(row.history),
    stale: bool(row.stale),
    cost: cost(row.cost),
    error_code: errorCode,
    provider_id: providerIdentifier(row.provider_id),
    model_id: providerIdentifier(row.model_id),
    route_state: enumerated(row.route_state, TASK_ROUTE_STATES),
    actions,
    action_limits: limits,
    retry_policy: TASK_ACTION_LIMITS.retry_policy,
    lifecycle: text(row.lifecycle, TASK_CENTER_BOUNDS.lifecycle),
    source,
    owner_navigation: pointer(row.owner_navigation),
    navigation_contract: navigationContract,
    source_domain: sourceDomain,
    revision,
  };
}
/**
 * `WorkspaceToolsService.tasks()` 本身**不返回**项目/范围身份（项目只在 URL 上），
 * 因此这里只能核对来源指针真实披露的 `novel_id`/`branch_id`：披露了就必须一致，
 * 一个都没披露就如实返回 `scope_verified: false`，不假装核对过。
 */
function disclosedIdentity(items: TaskCenterTask[], projectId: string, expected?: TaskCenterScope): boolean {
  let verified = false;
  for (const item of items) {
    for (const candidate of [item.source, item.owner_navigation]) {
      if (!candidate) continue;
      const novel = candidate.novel_id, branch = candidate.branch_id;
      if (typeof novel === 'string') {
        if (novel !== projectId) mismatch();
        verified = true;
      }
      if (typeof branch === 'string') {
        if (branch !== (expected?.branch_id ?? null)) mismatch();
        verified = true;
      }
    }
  }
  return verified;
}

/** `GET …/experimental/workspace/tasks` 的严格投影（只读，绝无执行权）。 */
export function taskCenterProjection(value: unknown, projectId: string, expectedScope?: TaskCenterScope): TaskCenterTasksProjection {
  return checked('tasks', () => {
    if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > TASK_CENTER_BOUNDS.project_id) invalid();
    const row = object(value, ['items', 'unavailable', 'truncated', 'executor', 'refresh', 'automatic_retries', ...TASK_PAGE_KEYS]);
    if (row.executor !== TASK_EXECUTOR || row.refresh !== TASK_REFRESH
      || row.automatic_retries !== TASK_AUTOMATIC_RETRIES) invalid();
    const items = list(row.items, TASK_CENTER_BOUNDS.items).map(task);
    const unavailable: TaskCenterUnavailable[] = list(row.unavailable, TASK_CENTER_BOUNDS.unavailable).map(entry => {
      const source = object(entry, ['authority', 'label', 'reason']);
      return {
        authority: token(source.authority, TASK_CENTER_TOKEN, TASK_CENTER_BOUNDS.authority),
        label: text(source.label, TASK_CENTER_BOUNDS.label),
        reason: token(source.reason, TASK_CENTER_REASON_TOKEN, TASK_CENTER_BOUNDS.authority),
      };
    });
    const scopeVerified = disclosedIdentity(items, projectId, expectedScope);
    return {
      project_id: projectId, scope_verified: scopeVerified, items, unavailable,
      executor: TASK_EXECUTOR, refresh: TASK_REFRESH,
      automatic_retries: TASK_AUTOMATIC_RETRIES,
      ...pagedTasks(row, items.length),
    };
  });
}

/* [HERMIA-FE-CONTRACTS G-TC-1] 分页信封：只在 7 个分页键全部出现时采用；部分出现即拒绝（不猜）。 */
const TASK_PAGE_KEYS = ['observed_total', 'limit', 'offset', 'has_more', 'next_offset', 'source_truncated', 'coverage'] as const;
function pagedTasks(row: Record<string, unknown>, count: number): { page: TaskCenterTasksPage | null; truncated: boolean } {
  const present = TASK_PAGE_KEYS.filter(key => Object.hasOwn(row, key));
  if (!present.length) return { page: null, truncated: bool(row.truncated) };
  if (present.length !== TASK_PAGE_KEYS.length) invalid();
  const coverage = object(row.coverage, ['scope', 'completeness']);
  if (coverage.scope !== 'BOUNDED_AUTHORIZED_PROJECTION' || coverage.completeness !== 'NOT_ASSERTED') invalid();
  const limit = integer(row.limit, 100), offset = integer(row.offset, 1_000_000), observed = integer(row.observed_total);
  const hasMore = bool(row.has_more), sourceTruncated = bool(row.source_truncated);
  if (limit < 1 || count > limit || offset + count > observed) invalid();
  const next = row.next_offset === null ? null : integer(row.next_offset);
  if (hasMore ? next !== offset + count || next >= observed : next !== null) invalid();
  if (bool(row.truncated) !== (sourceTruncated || hasMore)) invalid();
  // 分页模式下旧的"达到上限"警告只跟随来源截断；还有下一页由加载更多表达。
  return { page: { observed_total: observed, limit, offset, has_more: hasMore, next_offset: next, source_truncated: sourceTruncated,
    completeness: 'NOT_ASSERTED' }, truncated: sourceTruncated };
}

/* ------------------------------------------------------------- 审核收件箱 */

/** `_normalize` 自己写入的字段；其余键是领域原始行，读取时忽略且不渲染。 */
const REVIEW_ITEM_KEYS = [
  'id', 'domain', 'novel_id', 'project', 'workspace', 'branch', 'scope', 'source', 'source_versions', 'source_hash',
  'created_by', 'status', 'stale', 'risk', 'privacy_state', 'preview', 'target', 'version', 'allowed_actions',
  'batch_safe', 'batch_actions',
] as const;

function reviewItem(value: unknown, projectId: string, expected?: TaskCenterScope): ReviewInboxItem {
  const row = tolerantObject(value);
  for (const key of REVIEW_ITEM_KEYS) if (row[key] === undefined) invalid();
  const id = text(row.id, TASK_CENTER_BOUNDS.item_id);
  const domain = token(row.domain, TASK_CENTER_TOKEN, TASK_CENTER_BOUNDS.domain);
  const novelId = text(row.novel_id, TASK_CENTER_BOUNDS.project_id);
  const project = text(row.project, TASK_CENTER_BOUNDS.project_id);
  if (novelId !== projectId || project !== projectId) mismatch();
  const scope = scoped(row.scope, projectId, expected);
  // `batch_actions` 由 owner 取 `allowed_actions` 与领域批量动作的交集，必须是子集。
  const allowed = unique(list(row.allowed_actions, TASK_CENTER_BOUNDS.allowed_actions)
    .map(entry => token(entry, REVIEW_INBOX_ACTION_TOKEN, TASK_CENTER_BOUNDS.allowed_actions)));
  const batch = unique(list(row.batch_actions, TASK_CENTER_BOUNDS.batch_actions)
    .map(entry => token(entry, REVIEW_INBOX_ACTION_TOKEN, TASK_CENTER_BOUNDS.batch_actions)));
  if (batch.some(action => !allowed.includes(action))) invalid();
  const rawPreview = row.preview;
  const preview: ReviewInboxPreview = typeof rawPreview === 'string'
    ? { kind: 'text', text: scalar(rawPreview, TASK_CENTER_BOUNDS.preview_text) }
    : { kind: 'fields', fields: fields(rawPreview, TASK_CENTER_BOUNDS.fields) };
  const rawTarget = tolerantObject(row.target);
  const targetNavigation = rawTarget.navigation_contract === undefined || rawTarget.navigation_contract === null
    ? null : token(rawTarget.navigation_contract, /^[A-Z][A-Z0-9_]{0,63}$/, TASK_CENTER_BOUNDS.authority);
  const batchSafe = bool(row.batch_safe);
  if (batchSafe !== (batch.length > 0)) invalid();
  // 领域自己的恢复状态（`media.py`）；只用于抑制普通审核按钮。
  const recoveryState = row.recovery_state === null || row.recovery_state === undefined
    ? null : token(row.recovery_state, /^[A-Z][A-Z0-9_]{0,63}$/, TASK_CENTER_BOUNDS.authority);
  const status = token(row.status, REVIEW_INBOX_STATUS_TOKEN, TASK_CENTER_BOUNDS.status);
  const promotionRecoveryRequired = status === REVIEW_INBOX_PROMOTION_STATUS
    || (recoveryState !== null && (REVIEW_INBOX_PROMOTION_RECOVERY_STATES as readonly string[]).includes(recoveryState));
  // `inbox_api.py::ReviewActionIn.expected_version` 是 `ge=1`。
  const version = integer(row.version);
  if (version < 1) invalid();
  return {
    id, domain,
    status,
    stale: bool(row.stale),
    preview,
    target: fields(rawTarget, TASK_CENTER_BOUNDS.fields),
    target_navigation_contract: targetNavigation,
    version,
    allowed_actions: allowed,
    batch_actions: batch,
    batch_safe: batchSafe,
    source: scalar(row.source, TASK_CENTER_BOUNDS.field_value),
    source_versions: fields(row.source_versions, TASK_CENTER_BOUNDS.fields),
    source_hash: scalar(row.source_hash, TASK_CENTER_BOUNDS.source_hash),
    privacy_state: scalar(row.privacy_state, TASK_CENTER_BOUNDS.field_value),
    risk: scalar(row.risk, TASK_CENTER_BOUNDS.field_value),
    created_by: scalar(row.created_by, TASK_CENTER_BOUNDS.actor),
    recovery_state: recoveryState,
    promotion_recovery_required: promotionRecoveryRequired,
    novel_id: novelId,
    project,
    workspace: row.workspace === null ? null : text(row.workspace, TASK_CENTER_BOUNDS.project_id),
    branch: row.branch === null ? null : text(row.branch, TASK_CENTER_BOUNDS.project_id),
    scope,
  };
}

/** `UnifiedReviewInbox.list()` 的严格投影：不可读领域必须保留，批量语义必须原样带出。 */
export function reviewInboxProjection(value: unknown, projectId: string, expectedScope?: TaskCenterScope): ReviewInboxProjection {
  return checked('review', () => {
    if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > TASK_CENTER_BOUNDS.project_id) invalid();
    const row = object(value, ['items', 'total', 'unavailable', 'approval_authority', 'batch_semantics']);
    if (row.approval_authority !== REVIEW_INBOX_APPROVAL_AUTHORITY
      || row.batch_semantics !== REVIEW_INBOX_BATCH_SEMANTICS) invalid();
    const items = list(row.items, TASK_CENTER_BOUNDS.items).map(entry => reviewItem(entry, projectId, expectedScope));
    const unavailable: ReviewInboxUnavailable[] = list(row.unavailable, TASK_CENTER_BOUNDS.unavailable).map(entry => {
      const source = object(entry, ['domain', 'reason']);
      return {
        domain: token(source.domain, TASK_CENTER_TOKEN, TASK_CENTER_BOUNDS.domain),
        reason: token(source.reason, TASK_CENTER_REASON_TOKEN, TASK_CENTER_BOUNDS.authority),
      };
    });
    const total = integer(row.total, TASK_CENTER_BOUNDS.items);
    // owner 的 `total` 就是本次返回的行数（过滤已在服务端完成）。
    if (total !== items.length) invalid();
    return {
      project_id: projectId, items, total, unavailable,
      approval_authority: REVIEW_INBOX_APPROVAL_AUTHORITY, batch_semantics: REVIEW_INBOX_BATCH_SEMANTICS,
    };
  });
}

/* ------------------------------------------------------------- 写入前校验 */

/** `TaskCancelIn`：只允许 `expected_revision`，且必须是 `digest()` 的 64 位十六进制。 */
export function taskCancelRequest(value: unknown): TaskCancelRequest {
  return checked('tasks', () => {
    const row = object(value, ['expected_revision']);
    return { expected_revision: token(row.expected_revision, TASK_CANCEL_REVISION, 64) };
  });
}

/** `ReviewActionIn`：只允许 `expected_version`，且 `ge=1`。 */
export function reviewActionRequest(value: unknown): ReviewActionRequest {
  return checked('review', () => {
    const row = object(value, ['expected_version']);
    const version = integer(row.expected_version);
    if (version < 1) invalid();
    return { expected_version: version };
  });
}

/** `BatchIn`：1–50 项、动作限 `approve|reject|reopen`、同一项不得重复提交。 */
export function reviewBatchRequest(value: unknown): ReviewBatchRequest {
  return checked('review', () => {
    const row = object(value, ['items']);
    const entries = list(row.items, REVIEW_INBOX_BATCH_LIMIT);
    if (!entries.length) invalid();
    const items = entries.map(entry => {
      const source = object(entry, ['domain', 'id', 'action', 'expected_version']);
      const version = integer(source.expected_version);
      if (version < 1) invalid();
      return {
        domain: token(source.domain, TASK_CENTER_TOKEN, TASK_CENTER_BOUNDS.domain),
        id: text(source.id, TASK_CENTER_BOUNDS.item_id),
        action: enumerated(source.action, REVIEW_INBOX_ACTIONS) as ReviewInboxAction,
        expected_version: version,
      };
    });
    if (new Set(items.map(item => `${item.domain}:${item.id}`)).size !== items.length) invalid();
    return { items };
  });
}

/** `WorkspaceToolsService.cancel_task()` 的回执：只有版本信号，没有终止证明。 */
export function taskCancellationReceipt(
  value: unknown, projectId: string, expectedScope?: TaskCenterScope,
): TaskCancellationReceipt {
  return checked('tasks', () => {
    const row = object(value, ['item', 'cancellation_requested', 'executor']);
    if (row.cancellation_requested !== true || row.executor !== TASK_EXECUTOR) invalid();
    const item = task(row.item);
    disclosedIdentity([item], projectId, expectedScope);
    return {
      item, cancellation_requested: true, executor: TASK_EXECUTOR,
      // 只有原 owner 自己的状态是 CANCELLED 才算确认终止；否则是"待确认"。
      termination_confirmed: item.status === 'CANCELLED',
    };
  });
}

/** `UnifiedReviewInbox.batch()` 的回执：逐项结果必须自洽（成功项不会自动重试）。 */
export function reviewBatchReceipt(value: unknown): ReviewBatchReceipt {
  return checked('review', () => {
    const row = object(value, ['status', 'results', 'remaining', 'retry']);
    const status = enumerated(row.status, ['COMPLETED', 'PARTIAL', 'FAILED'] as const);
    const results: ReviewBatchResult[] = list(row.results, REVIEW_INBOX_BATCH_LIMIT).map(entry => {
      const source = object(entry, ['domain', 'id', 'status', 'result', 'code']);
      const result = enumerated(source.status, ['SUCCEEDED', 'FAILED'] as const);
      const base = {
        domain: token(source.domain, TASK_CENTER_TOKEN, TASK_CENTER_BOUNDS.domain),
        id: text(source.id, TASK_CENTER_BOUNDS.item_id),
        status: result,
      } as ReviewBatchResult;
      // 成功项可能带有领域自己的 result 载荷：不读取也不渲染；失败项必须给出机器码。
      if (result === 'FAILED') base.code = token(source.code, /^[A-Za-z0-9_]{1,64}$/, 64);
      return base;
    });
    const remaining = integer(row.remaining, REVIEW_INBOX_BATCH_LIMIT * 50);
    if (['COMPLETED', 'PARTIAL'].includes(status) && results.length < 2) invalid();
    if (status === 'COMPLETED' && (remaining !== 0 || results.some(entry => entry.status === 'FAILED'))) invalid();
    if (status !== 'COMPLETED' && results[results.length - 1]?.status !== 'FAILED') invalid();
    const retry = row.retry === undefined ? null : enumerated(row.retry, ['REFRESH_AND_SELECT_FAILED_ITEMS'] as const);
    return { status, results, remaining, retry, batch_semantics: REVIEW_INBOX_BATCH_SEMANTICS };
  });
}

/* ----------------------------------------------------------------- 过滤器 */

/**
 * 本地查询参数的有界化。两个端点的上限来自原 owner 自己：
 * `ux_api.py::tasks(q: Query('', max_length=160))`、`inbox_api.py::inbox(search: Query(None, max_length=400))`。
 */
export function taskCenterTaskQuery(value: unknown): TaskCenterTaskQuery {
  return checked('tasks', () => {
    const row = object(value, ['q', 'failed_only', 'limit', 'offset']);
    const base = { q: queryText(row.q, TASK_CENTER_BOUNDS.query), failed_only: bool(row.failed_only) };
    if (row.limit === undefined && row.offset === undefined) return base;
    const limit = row.limit === undefined ? 50 : integer(row.limit, 100), offset = row.offset === undefined ? 0 : integer(row.offset, 1_000_000);
    if (limit < 1) invalid();
    return { ...base, limit, offset };
  });
}

export function reviewInboxQuery(value: unknown): ReviewInboxQuery {
  return checked('review', () => {
    const row = object(value, ['domain', 'status', 'search']);
    const domain = queryText(row.domain, TASK_CENTER_BOUNDS.domain);
    // 空串代表"不过滤"；否则必须是 owner 注册的领域标识语法。
    if (domain && !TASK_CENTER_TOKEN.test(domain)) invalid();
    return {
      domain,
      status: queryText(row.status, TASK_CENTER_BOUNDS.status),
      search: queryText(row.search, TASK_CENTER_BOUNDS.inbox_search),
    };
  });
}
