/**
 * 真实形状夹具（协议夹具，不是运行时验收证据）。
 *
 * 两个 builder 逐字段复刻原 owner 的输出，字段名与键集合都由下面注释指出的函数产生；
 * 任何一侧改名/增删键都会让严格解码器的测试失败，而不是在浏览器里才暴露。
 *
 * - `projectedTask(...)` 复刻 `app/experimental/ux.py::projected_task(reader, row)`。
 * - `reviewInboxItem(...)` 复刻
 *   `app/experimental/inbox.py::UnifiedReviewInbox._normalize(binding, context, row)`，
 *   并保留 `app/experimental/media.py::MediaService.list_review_items` /
 *   `app/experimental/planning.py::PlanningService.list_review_items` 真实会带上的领域键。
 * - `tasksResponse()` / `reviewInboxResponse()` 复刻
 *   `WorkspaceToolsService.tasks()` / `UnifiedReviewInbox.list()` 的信封。
 */
import type { TaskCenterSourcePointer } from './taskCenterTypes';

export const FIXTURE_PROJECT = 'studio-project';
export const FIXTURE_REVISION = 'a1b2c3d4'.repeat(8);
export const FIXTURE_SOURCE_HASH = 'f0e1d2c3'.repeat(8);
/** `projected_task` 固定的 `lifecycle` 文案。 */
export const FIXTURE_LIFECYCLE = '面板关闭不取消任务；继续执行和重启恢复取决于原任务服务。';

export type RawTaskPointer = { source?: TaskCenterSourcePointer; owner_navigation?: TaskCenterSourcePointer };

/**
 * 一个 `TaskReader` 行经 `projected_task` 之后的完整形状。
 * `actions` 与 `action_limits.cancel` 的对应关系就是 owner 的 `cancel_allowed` 规则。
 */
export function projectedTask(overrides: Record<string, unknown> = {}) {
  return {
    // 默认值 = TaskReader('media', '封面与分镜', 'cover_storyboard_generation') 读到的
    // 一个 RUNNING 媒体任务：media 没有注册 cancel，所以 cancel 限额为 SOURCE_AUTHORITY_ONLY。
    source: {
      kind: 'feature', id: 'media-task-1', feature: 'cover_storyboard_generation', task_authority: 'media',
    },
    id: 'media-task-1',
    authority: 'media',
    label: '封面与分镜',
    status: 'RUNNING',
    stage_label: '运行中',
    version: 4,
    feature: 'cover_storyboard_generation',
    progress: { completed: 3, total: 8, unit: '分块' },
    history: [{ version: 4, status: 'RUNNING' }, { version: 3, status: 'QUEUED' }],
    stale: false,
    cost: { estimate: null, actual: null, state: 'UNKNOWN' },
    error_code: null,
    provider_id: 'local-image',
    model_id: 'mock-image-v1',
    route_state: 'OBSERVED',
    actions: ['open_source'],
    action_limits: {
      cancel: 'SOURCE_AUTHORITY_ONLY', retry: 'SOURCE_PREFLIGHT_REQUIRED',
      resume: 'SOURCE_RECOVERY_REQUIRED', review: 'SOURCE_REVIEW_REQUIRED',
    },
    retry_policy: 'SOURCE_AUTHORITY_ONLY',
    lifecycle: FIXTURE_LIFECYCLE,
    revision: FIXTURE_REVISION,
    ...overrides,
  };
}

/** `author_generation` + `experimental_origin='style_analysis_model'` 的 owner_navigation 分支。 */
export function projectedFeatureOwnedTask(overrides: Record<string, unknown> = {}) {
  const pointer = {
    kind: 'feature', id: 'style-task-1', feature: 'style_dna_v2', task_authority: 'style_model_job',
    chapter_id: 'chapter-1', version: 4,
  };
  return projectedTask({
    source: pointer,
    owner_navigation: pointer,
    id: 'style-task-1',
    authority: 'author_generation',
    label: '文风模型意见',
    feature: 'style_dna_v2',
    status: 'QUEUED',
    stage_label: '排队',
    version: 1,
    actions: ['open_source', 'cancel'],
    action_limits: {
      cancel: null, retry: 'SOURCE_PREFLIGHT_REQUIRED',
      resume: 'SOURCE_RECOVERY_REQUIRED', review: 'SOURCE_REVIEW_REQUIRED',
    },
    progress: null,
    history: [],
    stale: true,
    ...overrides,
  });
}

/**
 * `projected_task` 为正式来源检查器产出的形状：`source` 被 pop、状态被覆盖、
 * `open_source` 被移除。`review_domain='visual_identity'` 时原始状态 `RUNNING`
 * 会变成 `UNKNOWN` + `等待原服务恢复`。
 */
export function projectedFormalTask(overrides: Record<string, unknown> = {}) {
  return {
    id: 'receipt-1',
    authority: 'review_inbox',
    label: '原领域待审核项',
    status: 'UNKNOWN',
    stage_label: '等待原服务恢复',
    version: 2,
    feature: 'unified_review_inbox',
    progress: null,
    history: [],
    stale: false,
    cost: { estimate: null, actual: null, state: 'UNKNOWN' },
    error_code: null,
    provider_id: null,
    model_id: null,
    route_state: 'UNKNOWN',
    actions: [],
    action_limits: {
      cancel: 'SOURCE_AUTHORITY_ONLY', retry: 'SOURCE_PREFLIGHT_REQUIRED',
      resume: 'SOURCE_RECOVERY_REQUIRED', review: 'SOURCE_REVIEW_REQUIRED',
    },
    retry_policy: 'SOURCE_AUTHORITY_ONLY',
    lifecycle: '仅投影原回执；不会自动运行、恢复或批准。真实模型接入尚未配置，持久工作器未实现。',
    navigation_contract: 'FORMAL_SOURCE_ONLY',
    source_domain: 'visual_identity',
    revision: FIXTURE_REVISION,
    ...overrides,
  };
}

/** `WorkspaceToolsService.tasks()` 的返回体（含被拒绝来源的 unavailable 条目）。 */
export function tasksResponse(overrides: Record<string, unknown> = {}) {
  return {
    items: [projectedTask()],
    unavailable: [{ authority: 'exports', label: '导出任务', reason: 'SOURCE_UNAVAILABLE' }],
    truncated: false,
    executor: false,
    refresh: 'MANUAL',
    automatic_retries: false,
    ...overrides,
  };
}

/**
 * 一个 `_normalize` 之后的审核项。这里保留媒体领域真实带上的键
 * （`list_review_items` 的 `{**row, ...}` 展开），证明领域键既不被模型采纳也不被渲染。
 */
export function reviewInboxItem(overrides: Record<string, unknown> = {}) {
  return {
    // ---- 领域原始行（media.py::list_review_items 展开的 media proposal 行）----
    id: 'candidate-1',
    task_id: 'media-task-1',
    brief_id: 'brief-1',
    kind: 'COVER',
    candidate_index: 0,
    status: 'PENDING_REVIEW',
    stale: false,
    version: 3,
    history: [],
    updated_at: '2026-10-14T09:41:59+00:00',
    recovery_required: false,
    recovery_state: null,
    promotion_asset_id: null,
    // ---- _normalize 写入/覆盖的字段 ----
    domain: 'media',
    novel_id: FIXTURE_PROJECT,
    project: FIXTURE_PROJECT,
    workspace: null,
    branch: null,
    scope: { mode: 'local', novel_id: FIXTURE_PROJECT },
    source: 'media-task-1',
    source_versions: { 'brief:brief-1': { version: 2, digest: 'b'.repeat(64) } },
    source_hash: FIXTURE_SOURCE_HASH,
    created_by: 'local-author',
    risk: 'GENERATED_MEDIA_REQUIRES_REVIEW',
    privacy_state: 'LOCAL_ONLY',
    preview: 'COVER candidate 1',
    target: { brief_id: 'brief-1', asset_id: null },
    allowed_actions: ['approve', 'reject'],
    batch_safe: false,
    batch_actions: [],
    ...overrides,
  };
}

/**
 * `planning` 领域：`bind_domain('planning', ..., ('reject',))` 使
 * `_normalize` 得到 `batch_actions=['reject']`、`batch_safe=True`。
 * 该领域没有 privacy_state，于是落到 `_normalize` 的 'UNKNOWN' 默认值。
 */
export function reviewInboxBatchItem(overrides: Record<string, unknown> = {}) {
  const domain: Record<string, unknown> = {
    id: 'proposal-1',
    node_id: 'node-1',
    graph_id: 'graph-1',
    title: '结构化规划提案',
    status: 'REVIEW',
    stale: false,
    version: 5,
    sources: { 'chapter:1': { version: 7, digest: 'c'.repeat(64) } },
    safe_batch: false,
    domain: 'planning',
    source: 'structured_planning',
    preview: '结构化规划提案',
    target: { node_id: 'node-1', graph_id: 'graph-1' },
    source_versions: { 'chapter:1': { version: 7, digest: 'c'.repeat(64) } },
    risk: 'PLANNING_ONLY',
    allowed_actions: ['approve', 'reject'],
    ...overrides,
  };
  return {
    ...domain,
    // `_normalize` 在领域键之后统一覆盖/补齐的部分。
    novel_id: FIXTURE_PROJECT,
    project: FIXTURE_PROJECT,
    workspace: null,
    branch: null,
    scope: { mode: 'local', novel_id: FIXTURE_PROJECT },
    source_hash: (domain.source_hash as string | undefined) ?? FIXTURE_SOURCE_HASH,
    created_by: (domain.created_by as string | undefined) ?? 'UNKNOWN',
    privacy_state: (domain.privacy_state as string | undefined) ?? 'UNKNOWN',
    batch_safe: true,
    batch_actions: ['reject'],
  };
}

/** `UnifiedReviewInbox.list()` 的返回体：拒绝的领域必须出现在 unavailable 里。 */
export function reviewInboxResponse(overrides: Record<string, unknown> = {}) {
  const items = overrides.items ?? [reviewInboxItem(), reviewInboxBatchItem()];
  return {
    items,
    total: Array.isArray(items) ? items.length : 0,
    unavailable: [{ domain: 'legacy_canon', reason: 'ORIGINAL_DOMAIN_ACCESS_REQUIRED' }],
    approval_authority: 'DOMAIN_SERVICE',
    batch_semantics: 'PER_ITEM_CHECKPOINT',
    ...overrides,
  };
}

/** `WorkspaceToolsService.cancel_task()` 的返回体：只有版本信号，没有终止证明。 */
export function cancelReceipt(overrides: Record<string, unknown> = {}) {
  return {
    item: projectedTask({ actions: ['open_source'], status: 'CANCELLING', stage_label: '取消中' }),
    cancellation_requested: true,
    executor: false,
    ...overrides,
  };
}

/** `UnifiedReviewInbox.batch()` 的返回体（PARTIAL：成功项已提交，失败项需人工重选）。 */
export function batchReceipt(overrides: Record<string, unknown> = {}) {
  return {
    status: 'PARTIAL',
    results: [
      { domain: 'planning', id: 'proposal-1', status: 'SUCCEEDED', result: { status: 'REJECTED' } },
      { domain: 'planning', id: 'proposal-2', status: 'FAILED', code: 'HTTP_409' },
    ],
    remaining: 1,
    retry: 'REFRESH_AND_SELECT_FAILED_ITEMS',
    ...overrides,
  };
}
