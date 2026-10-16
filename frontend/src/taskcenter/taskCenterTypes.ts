/**
 * UX-02 统一任务中心 / 审核收件箱 —— 冻结词表与共享类型。
 *
 * 这个目录是**消费者**：它不新增第二套任务队列、状态机或审核系统。下面每一个
 * 字面量都逐条来自真实原 owner，改动前请先改后端：
 *
 * - `TASK_OWNER_STAGES` / `TASK_OWNER_FORMAL_STAGES` 抄自
 *   `app/experimental/ux.py::STAGES` 与同文件 `projected_task()` 中对
 *   `formal_domain in {'research_analysis','visual_identity'}` 的覆盖分支
 *   （`REVIEWED → 已审核`、`INVALIDATED → 已失效`）。`projected_task` 会把任何不在
 *   这些词表里的状态归为 `UNKNOWN`，本模块的契约做同样的事，绝不猜测。
 * - `TASK_ACTIONS` 抄自 `projected_task()` 的 `actions` 构造
 *   （`['open_source'] + (['cancel'] if cancel_allowed else [])`）。
 * - `TASK_CANCEL_LIMITS` / `TASK_ACTION_LIMITS` / `TASK_RETRY_POLICY` 抄自
 *   `projected_task()` 的 `action_limits` / `retry_policy`。
 * - `TASK_SAFE_CODES` 抄自 `ux.py::SAFE_CODES`（另加 `safe_code()` 的
 *   `UNCLASSIFIED` 兜底值）。
 * - `TASK_REFRESH` / `TASK_EXECUTOR` / `TASK_AUTOMATIC_RETRIES` 抄自
 *   `WorkspaceToolsService.tasks()` 的返回体：原 owner 自己声明
 *   `refresh: 'MANUAL'`、`executor: False`、`automatic_retries: False`，所以界面
 *   不得自动重试，也不得比 owner 更频繁地刷新。
 * - 审核侧的字面量抄自 `app/experimental/inbox.py::UnifiedReviewInbox._normalize`
 *   / `list()` 与 `app/experimental/inbox_api.py` 的路由声明。
 *
 * **刻意不复制的东西**：`TaskReader.name`（任务权威）与审核 `domain` 由组合根在
 * `app/experimental/api.py` / `workspace_task_owners.py` 注册；审核领域注册表在
 * `app/experimental/api.py::bind_domain`。把这些注册表抄进前端就等于造第二个 owner，
 * 因此这里只保留取值语法，界面一律使用返回值里真实出现的取值的并集。
 */

/* ------------------------------------------------------------------ 任务状态 */

/** 状态码 → 原 owner 自己的中文标签（`ux.py::STAGES` 逐条转写，顺序同源文件）。 */
export const TASK_OWNER_STAGES = [
  ['ANALYZING', '分析中'],
  ['NEEDS_REVIEW', '需要审核'],
  ['QUEUED', '排队'],
  ['PENDING', '等待'],
  ['DRAFT', '草稿'],
  ['READY', '就绪'],
  ['RUNNING', '运行中'],
  ['WORKING', '运行中'],
  ['PROCESSING', '处理中'],
  ['PREPARED', '准备就绪'],
  ['GENERATING', '生成中'],
  ['SETTLING', '结算确认中'],
  ['ACCEPTING', '接受处理中'],
  ['ACCEPTANCE_UNCERTAIN', '接受结果未知'],
  ['VALIDATED', '待审核'],
  ['REVIEW', '待审核'],
  ['AWAITING_REVIEW', '待审核'],
  ['COMPLETED', '已完成'],
  ['SUCCEEDED', '已完成'],
  ['COMMITTED', '已应用'],
  ['ACCEPTED', '已接受'],
  ['APPROVED', '已批准'],
  ['REJECTED', '已拒绝'],
  ['FAILED', '失败'],
  ['CANCELLED', '已取消'],
  ['CANCELLING', '取消中'],
  ['PAUSED', '已暂停'],
  ['UNKNOWN', '结果未知'],
  ['WAITING_APPROVAL', '等待批准'],
  ['PENDING_REVIEW', '待审核'],
  ['REVIEW_REQUIRED', '需要审核'],
  ['RESULT_READY', '结果就绪'],
  ['PROPOSED', '建议待审'],
  ['PLANNED', '已规划'],
  ['PENDING_REWRITE', '等待改写'],
  ['APPLIED', '已应用'],
  ['NOT_CONFIGURED', '未配置'],
  ['INTERRUPTED', '等待恢复'],
  ['PARTIAL', '部分完成'],
  ['STALE', '来源过期'],
  ['APPLYING', '应用中'],
  ['APPROVING', '批准处理中'],
] as const;

/**
 * `projected_task()` 为两个正式来源检查器额外产出的两个状态：它们不在 `STAGES` 里，
 * 只在 `formal_domain in {'research_analysis','visual_identity'}` 时出现。
 */
export const TASK_OWNER_FORMAL_STAGES = [
  ['REVIEWED', '已审核'],
  ['INVALIDATED', '已失效'],
] as const;

export type TaskCenterStatus =
  | typeof TASK_OWNER_STAGES[number][0]
  | typeof TASK_OWNER_FORMAL_STAGES[number][0];

/** 原 owner 会输出的全部状态码（`STAGES` + 两个正式领域覆盖值）。 */
export const TASK_STATUS_CODES: readonly TaskCenterStatus[] = [
  ...TASK_OWNER_STAGES.map(row => row[0]),
  ...TASK_OWNER_FORMAL_STAGES.map(row => row[0]),
];

export const TASK_STATUS_LABELS: Readonly<Record<TaskCenterStatus, string>> = Object.freeze(Object.fromEntries([
  ...TASK_OWNER_STAGES, ...TASK_OWNER_FORMAL_STAGES,
].map(row => [row[0], row[1]])) as Record<TaskCenterStatus, string>);

/** 冻结集合：`projected_task` 之外的取值一律按 `UNKNOWN` 呈现。 */
export const TASK_STATUS_SET: ReadonlySet<string> = Object.freeze(new Set<string>(TASK_STATUS_CODES));

/** 原 owner 未定义状态时的唯一表示。绝不猜测成其他阶段。 */
export const TASK_UNKNOWN_STATUS = 'UNKNOWN' as const;

/**
 * 任务的阶段→徽标语气。纯呈现映射，不改变状态本身；界面始终同时显示 owner 的
 * 原始状态码与 `stage_label`。
 */
export const TASK_STATUS_TONES: Readonly<Record<TaskCenterStatus, 'neutral' | 'info' | 'success' | 'warning' | 'error'>> =
  Object.freeze({
    ANALYZING: 'info', NEEDS_REVIEW: 'warning', QUEUED: 'info', PENDING: 'info', DRAFT: 'neutral', READY: 'info',
    RUNNING: 'info', WORKING: 'info', PROCESSING: 'info', PREPARED: 'info', GENERATING: 'info', SETTLING: 'warning',
    ACCEPTING: 'info', ACCEPTANCE_UNCERTAIN: 'warning', VALIDATED: 'warning', REVIEW: 'warning', AWAITING_REVIEW: 'warning',
    COMPLETED: 'success', SUCCEEDED: 'success', COMMITTED: 'success', ACCEPTED: 'success', APPROVED: 'success',
    REJECTED: 'error', FAILED: 'error', CANCELLED: 'neutral', CANCELLING: 'warning', PAUSED: 'warning',
    UNKNOWN: 'warning', WAITING_APPROVAL: 'warning', PENDING_REVIEW: 'warning', REVIEW_REQUIRED: 'warning',
    RESULT_READY: 'warning', PROPOSED: 'warning', PLANNED: 'info', PENDING_REWRITE: 'warning', APPLIED: 'success',
    NOT_CONFIGURED: 'neutral', INTERRUPTED: 'warning', PARTIAL: 'warning', STALE: 'warning', APPLYING: 'info',
    APPROVING: 'warning', REVIEWED: 'success', INVALIDATED: 'error',
  });

/** `projected_task()` 里 `actions` 允许出现的全部取值。按钮可用性只看这个列表。 */
export const TASK_ACTIONS = ['open_source', 'cancel'] as const;
export type TaskCenterTaskAction = typeof TASK_ACTIONS[number];
export const TASK_ACTION_LABELS: Readonly<Record<TaskCenterTaskAction, string>> = Object.freeze({
  open_source: '定位原任务结果', cancel: '请求取消原任务',
});

/** `projected_task()` 的 `route_state`。`REQUESTED` 只表示"请求过的路线"，不是已执行。 */
export const TASK_ROUTE_STATES = ['OBSERVED', 'REQUESTED', 'UNKNOWN'] as const;
export type TaskCenterRouteState = typeof TASK_ROUTE_STATES[number];
export const TASK_ROUTE_STATE_LABELS: Readonly<Record<TaskCenterRouteState, string>> = Object.freeze({
  OBSERVED: '原任务已记录实际路线', REQUESTED: '仅为请求路线，尚未证明实际执行', UNKNOWN: '原服务未报告模型路线',
});

/** `projected_task()` 的 `action_limits.cancel` 取值（`null` 表示可取消）。 */
export const TASK_CANCEL_LIMITS = [
  'RECEIPT_CAPACITY_EXHAUSTED', 'ORIGIN_COORDINATOR_REQUIRED', 'TERMINAL_OR_UNSUPPORTED', 'SOURCE_AUTHORITY_ONLY',
] as const;
export type TaskCenterCancelLimit = typeof TASK_CANCEL_LIMITS[number];
export const TASK_CANCEL_LIMIT_LABELS: Readonly<Record<TaskCenterCancelLimit, string>> = Object.freeze({
  RECEIPT_CAPACITY_EXHAUSTED: '原回执已无可用取消修订容量；需在原领域创建新回执，不会自动重放。',
  ORIGIN_COORDINATOR_REQUIRED: '此任务由原批处理协调器管理；请在原批次中取消，这里不代为取消。',
  TERMINAL_OR_UNSUPPORTED: '当前阶段不能取消；终态结果保留。',
  SOURCE_AUTHORITY_ONLY: '当前来源没有通用取消接口；请在原工具查看可用操作，这里不提供取消按钮。',
});

/** `projected_task()` 固定的 `action_limits.retry/resume/review` 与 `retry_policy`。 */
export const TASK_ACTION_LIMITS = Object.freeze({
  retry: 'SOURCE_PREFLIGHT_REQUIRED', resume: 'SOURCE_RECOVERY_REQUIRED', review: 'SOURCE_REVIEW_REQUIRED',
  retry_policy: 'SOURCE_AUTHORITY_ONLY',
} as const);

/** `WorkspaceToolsService.tasks()` 自己声明的刷新/执行事实。界面不得超出它。 */
export const TASK_REFRESH = 'MANUAL' as const;
export const TASK_EXECUTOR = false as const;
export const TASK_AUTOMATIC_RETRIES = false as const;

/** `ux.py::SAFE_CODES` 的逐条转写，另加 `safe_code()` 的兜底 `UNCLASSIFIED`。 */
export const TASK_SAFE_CODES: readonly string[] = Object.freeze([
  'TIMEOUT', 'CANCELLED', 'PERMISSION_DENIED', 'VERSION_CONFLICT', 'SOURCE_STALE', 'ADAPTER_REQUIRED',
  'PROVIDER_UNAVAILABLE', 'NETWORK_ERROR', 'EXPERIMENTAL_SOURCE_STALE', 'EXPERIMENTAL_VERSION_CONFLICT',
  'MEDIA_TASK_TRANSITION_INVALID', 'UNCLASSIFIED',
]);

/** `projected_task()` 的 `navigation_contract`：来源指针被刻意移除，不许伪造导航目标。 */
export const TASK_FORMAL_SOURCE_ONLY = 'FORMAL_SOURCE_ONLY' as const;
/** `projected_task()` 的 `source_domain` 可能取值（正式来源检查器）。 */
export const TASK_FORMAL_DOMAINS = ['research_analysis', 'visual_identity'] as const;

/* ------------------------------------------------------------------ 审核收件箱 */

/** `inbox.py::list()` 自己声明的审批权属：动作永远转交原领域服务。 */
export const REVIEW_INBOX_APPROVAL_AUTHORITY = 'DOMAIN_SERVICE' as const;
/** `inbox.py::list()` 自己声明的批量语义：逐项 checkpoint，绝不是全有或全无。 */
export const REVIEW_INBOX_BATCH_SEMANTICS = 'PER_ITEM_CHECKPOINT' as const;
/** `inbox.py::list()` 对原领域拒绝访问时的 unavailable 原因码。 */
export const REVIEW_INBOX_DENIED_REASON = 'ORIGINAL_DOMAIN_ACCESS_REQUIRED' as const;
/** `inbox_api.py` 路由字面量：只有这三个动作可以走统一收件箱。 */
export const REVIEW_INBOX_ACTIONS = ['approve', 'reject', 'reopen'] as const;
export type ReviewInboxAction = typeof REVIEW_INBOX_ACTIONS[number];
export const REVIEW_INBOX_ACTION_LABELS: Readonly<Record<ReviewInboxAction, string>> = Object.freeze({
  approve: '采纳为正式结果', reject: '驳回本次候选', reopen: '重开审核',
});
/** `inbox_api.py::BatchIn` 的上限。 */
export const REVIEW_INBOX_BATCH_LIMIT = 50;
/**
 * 领域自己有"批准写入中断"的恢复流程（`app/experimental/media.py` 写入
 * `recovery_required` / `recovery_state`，已落地的消费者
 * `frontend/src/experimental/PromotionRecovery.tsx::needsPromotionRecovery` 据此
 * 抑制普通审核按钮）。这里只**复述**该抑制条件：它只能让界面少一个按钮，
 * 绝不会多出一个动作。
 */
export const REVIEW_INBOX_PROMOTION_STATUS = 'APPROVING' as const;
export const REVIEW_INBOX_PROMOTION_RECOVERY_STATES = [
  'RESUME_APPROVAL', 'SOURCE_CHANGED_RECONCILIATION_REQUIRED',
] as const;

/* ------------------------------------------------------------------ 取值语法 */

/** 任务权威/feature/审核领域的语法（组合根注册的取值，不在前端复制注册表）。 */
export const TASK_CENTER_TOKEN = /^[a-z][a-z0-9_]{0,63}$/;
/** owner 自己写的大写机器码（unavailable 的 reason、恢复状态等）。 */
export const TASK_CENTER_REASON_TOKEN = /^[A-Z][A-Z0-9_]{0,63}$/;
/** 任务状态码语法（`projected_task` 会先 `.upper()`）。 */
export const TASK_CENTER_STATUS_TOKEN = /^[A-Z0-9_]{1,64}$/;
/** 审核项状态语法：领域自己的词表，原样保留（**不**翻译成任务阶段）。 */
export const REVIEW_INBOX_STATUS_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
/** 审核动作语法。 */
export const REVIEW_INBOX_ACTION_TOKEN = /^[a-z][a-z0-9_]{0,31}$/;
/** `TaskCancelIn.expected_revision` 的语法（`projected_task` 的 `revision = digest(result)`）。 */
export const TASK_CANCEL_REVISION = /^[a-f0-9]{64}$/;
/** `TaskReader` 允许回显的 provider/model 标识（`ux.py::task_identifier`）。 */
export const TASK_PROVIDER_IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:/@+ -]{0,159}$/;

export const TASK_CENTER_BOUNDS = Object.freeze({
  project_id: 240, label: 120, feature: 64, authority: 64, stage_label: 64, status: 64,
  lifecycle: 500, error_code: 64, provider: 160, unit: 16, pointer_key: 64, pointer_value: 240,
  pointer_entries: 24, fields: 32, field_key: 64, field_value: 500, preview_text: 2000,
  item_id: 240, domain: 80, source_hash: 128, actor: 160, query: 160, inbox_search: 400,
  items: 500, unavailable: 64, history: 10, allowed_actions: 32, batch_actions: 32,
  batch_results: 50, notice: 500, created_at: 64,
} as const);

/** 传输层必须回传的稳定机器码；界面文案按码映射，绝不直接渲染服务端正文。 */
export const TASK_CENTER_ERROR_CODES = Object.freeze({
  tasksInvalid: 'TASK_CENTER_PROJECTION_INVALID',
  tasksScopeMismatch: 'TASK_CENTER_SCOPE_MISMATCH',
  tasksReadFailed: 'TASK_CENTER_READ_FAILED',
  tasksQueryLocalInvalid: 'TASK_CENTER_QUERY_LOCAL_INVALID',
  cancelLocalInvalid: 'TASK_CENTER_CANCEL_LOCAL_INVALID',
  cancelReceiptInvalid: 'TASK_CENTER_CANCEL_RECEIPT_INVALID',
  inboxInvalid: 'REVIEW_INBOX_PROJECTION_INVALID',
  inboxScopeMismatch: 'REVIEW_INBOX_SCOPE_MISMATCH',
  inboxReadFailed: 'REVIEW_INBOX_READ_FAILED',
  inboxQueryLocalInvalid: 'REVIEW_INBOX_QUERY_LOCAL_INVALID',
  reviewLocalInvalid: 'REVIEW_INBOX_ACTION_LOCAL_INVALID',
  batchLocalInvalid: 'REVIEW_INBOX_BATCH_LOCAL_INVALID',
  batchInvalid: 'REVIEW_INBOX_BATCH_RESPONSE_INVALID',
  // 原 owner / 传输层会真实抛出的码，客户端只负责换成有界的用户文案。
  versionConflict: 'EXPERIMENTAL_VERSION_CONFLICT',
  sourceStale: 'EXPERIMENTAL_SOURCE_STALE',
  notFound: 'EXPERIMENTAL_NOT_FOUND',
  invalid: 'EXPERIMENTAL_INVALID',
  featureDisabled: 'EXPERIMENTAL_FEATURE_DISABLED',
  authorityChanged: 'WORKSPACE_AUTHORITY_CHANGED',
  reviewAuthorityChanged: 'REVIEW_AUTHORITY_CHANGED',
  branchScopeRequired: 'BRANCH_SCOPE_REQUIRED',
} as const);

/** 界面自己说的话（有界、可测）。owner 的原文另有字段承载，不在这里改写。 */
export const TASK_CENTER_NOTICES = Object.freeze({
  tasksReadFailure: '任务中心读取失败，请稍后重新核对。',
  inboxReadFailure: '审核收件箱读取失败，请稍后重新核对。',
  progressUnknown: '进度未知（原服务未提供已完成/总数）',
  unknownStatus: '原服务未给出确定状态，按“结果未知”显示；不会猜测进度或结果。',
  statusNotOwnerDefined: '原服务返回了未定义状态，已按“结果未知”处理，没有猜测成其他阶段。',
  cancelPending: '取消请求已发送/待确认：原任务尚未确认终止，请重新读取核对。',
  cancelConfirmed: '原任务已确认取消。',
  cancelFailed: '取消请求未完成，任务状态以原服务为准。',
  cancelScope: '取消只作用于这一条原任务，不影响其他任务、已发送的传输或已完成的结果。',
  formalSourceOnly: '此回执只有正式来源契约：原 owner 已移除来源指针，这里不会伪造导航目标。',
  reviewSubmitting: '已把决定转交原领域审核服务。',
  reviewDuplicateGuard: '同一候选已提交过决定；请先重新读取版本，不会重复创建正式结果。',
  batchPreviewTitle: '本次将逐项提交的候选（提交前请核对完整集合）',
  batchPerItem: '批量按逐项 checkpoint 处理：每项独立成功或失败，不是全有或全无；成功项不会自动重试。',
  batchReselectFailed: '重试只能由你显式重新勾选失败项；不会自动重发。',
  unavailableNotFullQueue: '部分来源当前不可读，这里不是完整队列。',
  executionIsNotDelivery: '执行已完成不代表交付：候选仍需通过原领域审核，这里不显示交付状态。',
  noAutoRetry: '“重试生成”和“恢复原任务”是两个独立动作，由原来源服务执行；这里不会自动重试、也不会自动恢复。',
  noProgressClaim: '原服务未报告可量化进度，因此不显示百分比或预计时间。',
} as const);

/* ------------------------------------------------------------------ 数据形状 */

export type TaskCenterScope = {
  mode: 'local' | 'collaboration';
  novel_id: string;
  workspace_id?: string | null;
  project_id?: string | null;
  storyline_id?: string | null;
  branch_id?: string | null;
};

/** 原 owner 披露的来源指针（`projected_task` 的 `source` / `owner_navigation`）。 */
export type TaskCenterSourcePointer = Readonly<Record<string, string | number | boolean | null>>;

export type TaskCenterProgress = { completed: number; total: number; unit: string };
export type TaskCenterHistoryEntry = { version: number | null; status: TaskCenterStatus };
export type TaskCenterCost = { estimate: number | null; actual: number | null; state: 'UNKNOWN' };
export type TaskCenterActionLimits = {
  cancel: TaskCenterCancelLimit | null; retry: string; resume: string; review: string;
};

export type TaskCenterTask = {
  id: string;
  authority: string;
  label: string;
  feature: string;
  /** owner 词表内则原样，否则一律 `UNKNOWN`（绝不猜测）。 */
  status: TaskCenterStatus;
  /** 线上原样返回的状态码；与 `status` 不同即说明 owner 未定义它。 */
  raw_status: string;
  /** owner 自己的阶段文案，原样保留（正式领域会给出 `等待原服务恢复`）。 */
  stage_label: string;
  version: number | null;
  /** 只有 owner 同时给出 completed+total 时才存在；缺失保持 `null`，不补 0%。 */
  progress: TaskCenterProgress | null;
  history: TaskCenterHistoryEntry[];
  stale: boolean;
  cost: TaskCenterCost;
  error_code: string | null;
  provider_id: string | null;
  model_id: string | null;
  route_state: TaskCenterRouteState;
  /** 唯一按钮来源：owner 的 `actions`。 */
  actions: TaskCenterTaskAction[];
  action_limits: TaskCenterActionLimits;
  retry_policy: 'SOURCE_AUTHORITY_ONLY';
  lifecycle: string;
  source: TaskCenterSourcePointer | null;
  owner_navigation: TaskCenterSourcePointer | null;
  navigation_contract: typeof TASK_FORMAL_SOURCE_ONLY | null;
  source_domain: string | null;
  /** `projected_task` 的 `revision = digest(result)`，取消时必须原样回传。 */
  revision: string;
};

export type TaskCenterUnavailable = { authority: string; label: string; reason: string };

export type TaskCenterTasksProjection = {
  project_id: string;
  /** `WorkspaceToolsService.tasks()` 不返回项目/范围身份；只有来源指针披露时才能核对。 */
  scope_verified: boolean;
  items: TaskCenterTask[];
  unavailable: TaskCenterUnavailable[];
  truncated: boolean;
  /** owner 自己声明的三件事，界面据此禁止自动轮询与自动重试。 */
  executor: false;
  refresh: 'MANUAL';
  automatic_retries: false;
};

export type ReviewInboxField = { key: string; value: string };
export type ReviewInboxPreview =
  | { kind: 'text'; text: string }
  | { kind: 'fields'; fields: ReviewInboxField[] };

export type ReviewInboxItem = {
  id: string;
  domain: string;
  /** 领域自己的状态词表，原样保留；不映射到任务阶段。 */
  status: string;
  stale: boolean;
  /** 候选预览：owner 给字符串就是文本，给结构就转成有界字段。 */
  preview: ReviewInboxPreview;
  target: ReviewInboxField[];
  target_navigation_contract: string | null;
  /** `inbox_api.py::ReviewActionIn.expected_version`，提交决定时必须原样回传。 */
  version: number;
  allowed_actions: string[];
  /** owner 与领域批量的交集，`batch_actions` 只可能是 `allowed_actions` 的子集。 */
  batch_actions: string[];
  batch_safe: boolean;
  source: string;
  source_versions: ReviewInboxField[];
  source_hash: string;
  privacy_state: string;
  risk: string;
  created_by: string;
  /** 领域自己的恢复状态（媒体批准中断用）；为 null 表示领域没有声明。 */
  recovery_state: string | null;
  /** 由 owner 状态 + 领域恢复状态推出：为 true 时不显示普通审核按钮，必须回原领域完成恢复。 */
  promotion_recovery_required: boolean;
  novel_id: string;
  project: string;
  workspace: string | null;
  branch: string | null;
  scope: TaskCenterScope;
};

export type ReviewInboxUnavailable = { domain: string; reason: string };

export type ReviewInboxProjection = {
  project_id: string;
  items: ReviewInboxItem[];
  total: number;
  /** 被拒绝/不可读的领域必须保留：拒绝不是空收件箱。 */
  unavailable: ReviewInboxUnavailable[];
  approval_authority: 'DOMAIN_SERVICE';
  /** 逐项 checkpoint，绝不是全有或全无。 */
  batch_semantics: 'PER_ITEM_CHECKPOINT';
};

/** 取消回执：`WorkspaceToolsService.cancel_task()` 只返回版本与信号，不返回终止证明。 */
export type TaskCancellationReceipt = {
  item: TaskCenterTask;
  cancellation_requested: true;
  executor: false;
  /**
   * 只有原 owner 自己的状态已经变成 `CANCELLED` 时才算确认终止；否则是
   * "已发送请求、待确认"，界面不得显示干净的 CANCELLED。
   */
  termination_confirmed: boolean;
};

export type ReviewActionReceipt = { domain: string; id: string; action: ReviewInboxAction; accepted: true };

export type ReviewBatchResult = { domain: string; id: string; status: 'SUCCEEDED' | 'FAILED'; code?: string };
export type ReviewBatchReceipt = {
  status: 'COMPLETED' | 'PARTIAL' | 'FAILED';
  results: ReviewBatchResult[];
  remaining: number;
  retry: 'REFRESH_AND_SELECT_FAILED_ITEMS' | null;
  batch_semantics: 'PER_ITEM_CHECKPOINT';
};

/* ------------------------------------------------------------------ 输入形状 */

export type TaskCenterTaskQuery = { q: string; failed_only: boolean };
export type ReviewInboxQuery = { domain: string; status: string; search: string };
export type TaskCancelRequest = { expected_revision: string };
export type ReviewActionRequest = { expected_version: number };
export type ReviewBatchItemRequest = {
  domain: string; id: string; action: ReviewInboxAction; expected_version: number;
};
export type ReviewBatchRequest = { items: ReviewBatchItemRequest[] };

/* ------------------------------------------------------------------ 客户端 */

/** 与 `productionWorkflowClient.ts` 同一个注入形状（见 `studioGraphClient.ts`）。 */
export type TaskCenterClient = {
  /** Optional read-only companion; aggregate task projection stays unchanged. */
  readCostReceipt?: (task: Pick<TaskCenterTask, 'authority' | 'id'>, signal?: AbortSignal) => Promise<import('./taskCostReceipt').TaskCostReceipt>;
  readTasks: (query: TaskCenterTaskQuery, signal?: AbortSignal) => Promise<TaskCenterTasksProjection>;
  readInbox: (query: ReviewInboxQuery, signal?: AbortSignal) => Promise<ReviewInboxProjection>;
  cancelTask: (
    task: Pick<TaskCenterTask, 'authority' | 'id' | 'revision'>, signal?: AbortSignal,
  ) => Promise<TaskCancellationReceipt>;
  reviewItem: (
    item: Pick<ReviewInboxItem, 'domain' | 'id' | 'version'>, action: ReviewInboxAction, signal?: AbortSignal,
  ) => Promise<ReviewActionReceipt>;
  reviewBatch: (request: ReviewBatchRequest, signal?: AbortSignal) => Promise<ReviewBatchReceipt>;
};

/* ------------------------------------------------------------------ 界面状态 */

/** 显式数据面状态：`EMPTY` 只表示"读成功且真的没有内容"，绝不吞掉 DENIED。 */
export type TaskCenterSurfaceState = 'IDLE' | 'LOADING' | 'READY' | 'EMPTY' | 'DENIED' | 'FAILED';
export type TaskCenterProblem = { code: string; message: string };
export type TaskCenterQueue = 'TASKS' | 'REVIEW';
export const TASK_CENTER_QUEUE_LABELS: Readonly<Record<TaskCenterQueue, string>> = Object.freeze({
  TASKS: '任务队列', REVIEW: '审核收件箱',
});

export type TaskCenterFilter = {
  /** 任务：owner 的 `q`（服务端匹配 id/label/stage_label）。收件箱：owner 的 `search`。 */
  query: string;
  /** 任务：owner 的 `failed_only`。 */
  failed_only: boolean;
  /** 任务：本地按 `feature`/`authority` 过滤（端点没有模块参数，故不伪造请求参数）。收件箱：owner 的 `domain`。 */
  module: string;
  /** 任务：本地按 owner 状态码过滤。收件箱：owner 的 `status`（领域词表，原样透传）。 */
  status: string;
};

export const EMPTY_TASK_CENTER_FILTER: TaskCenterFilter =
  Object.freeze({ query: '', failed_only: false, module: '', status: '' });

/** 导航只能由调用方执行：这里只发出原 owner 的 id 与来源指针。 */
export type TaskCenterNavigationTarget =
  | {
      queue: 'TASKS'; authority: string; task_id: string; label: string; feature: string;
      source: TaskCenterSourcePointer | null;
    }
  | {
      queue: 'REVIEW'; domain: string; item_id: string; version: number; source: string;
      target: ReviewInboxField[];
    };

export type TaskCenterActionState = 'RUNNING' | 'SUCCEEDED' | 'FAILED';

/** 每条动作的结果都按 `authority:id`（任务）/`domain:id`（审核）逐项保留。 */
export type TaskCenterActionResult =
  | {
      key: string; kind: 'cancel'; state: TaskCenterActionState; notice: string;
      termination_confirmed: boolean; item?: TaskCenterTask;
    }
  | {
      key: string; kind: 'review'; state: TaskCenterActionState; action: ReviewInboxAction; notice: string;
      /** 提交时绑定的候选版本：同一版本不会再提交一次，避免重复创建正式结果。 */
      expected_version: number;
    }
  | {
      key: string; kind: 'batch'; state: TaskCenterActionState; action: ReviewInboxAction;
      notice: string; receipt?: ReviewBatchReceipt;
    };
