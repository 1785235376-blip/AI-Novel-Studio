import { describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import {
  reviewActionRequest, reviewBatchReceipt, reviewBatchRequest, reviewInboxProjection, taskCancelRequest,
  taskCancellationReceipt, taskCenterProjection,
} from './taskCenterContract';
import {
  FIXTURE_PROJECT, batchReceipt, cancelReceipt, projectedFeatureOwnedTask, projectedFormalTask, projectedTask,
  reviewInboxBatchItem, reviewInboxItem, reviewInboxResponse, tasksResponse,
} from './taskCenterFixtures';

/** 严格解码器用机器码报错：断言码，不断言文案。 */
function rejectionCode(run: () => unknown): string | undefined {
  try {
    run();
    return undefined;
  } catch (error) {
    return error instanceof ApiError ? error.problem.code : `NOT_AN_API_ERROR:${String(error)}`;
  }
}
const tasks = (value: unknown, project = FIXTURE_PROJECT) => taskCenterProjection(value, project);
const inbox = (value: unknown, project = FIXTURE_PROJECT) => reviewInboxProjection(value, project);

describe('task center contract against real projected_task shapes', () => {
  it('accepts the real WorkspaceToolsService.tasks() envelope and its owner facts', () => {
    const decoded = tasks(tasksResponse());
    expect(decoded.project_id).toBe(FIXTURE_PROJECT);
    expect(decoded.executor).toBe(false);
    expect(decoded.refresh).toBe('MANUAL');
    expect(decoded.automatic_retries).toBe(false);
    expect(decoded.truncated).toBe(false);
    expect(decoded.items).toHaveLength(1);
    expect(decoded.unavailable).toEqual([{ authority: 'exports', label: '导出任务', reason: 'SOURCE_UNAVAILABLE' }]);
  });

  it('keeps owner status, label, progress, actions and limits verbatim', () => {
    const task = tasks(tasksResponse()).items[0];
    expect(task.status).toBe('RUNNING');
    expect(task.raw_status).toBe('RUNNING');
    expect(task.stage_label).toBe('运行中');
    expect(task.progress).toEqual({ completed: 3, total: 8, unit: '分块' });
    expect(task.actions).toEqual(['open_source']);
    expect(task.action_limits.cancel).toBe('SOURCE_AUTHORITY_ONLY');
    expect(task.cost).toEqual({ estimate: null, actual: null, state: 'UNKNOWN' });
    expect(task.error_code).toBeNull();
    expect(task.source).toEqual({
      kind: 'feature', id: 'media-task-1', feature: 'cover_storyboard_generation', task_authority: 'media',
    });
  });

  it('accepts the author_generation owner_navigation shape and the formal-source shape', () => {
    const owned = tasks(tasksResponse({ items: [projectedFeatureOwnedTask()] })).items[0];
    expect(owned.owner_navigation?.task_authority).toBe('style_model_job');
    expect(owned.owner_navigation?.chapter_id).toBe('chapter-1');
    expect(owned.actions).toEqual(['open_source', 'cancel']);
    expect(owned.progress).toBeNull();
    expect(owned.stale).toBe(true);

    const formal = tasks(tasksResponse({ items: [projectedFormalTask()], unavailable: [] })).items[0];
    expect(formal.navigation_contract).toBe('FORMAL_SOURCE_ONLY');
    expect(formal.source_domain).toBe('visual_identity');
    expect(formal.source).toBeNull();
    // 正式领域把 RUNNING 覆盖成 UNKNOWN + 自己的阶段文案；两者都要原样保留。
    expect(formal.status).toBe('UNKNOWN');
    expect(formal.stage_label).toBe('等待原服务恢复');
    expect(formal.actions).toEqual([]);
  });

  it('surfaces a status the owner does not define as UNKNOWN without guessing', () => {
    const task = tasks(tasksResponse({ items: [projectedTask({ status: 'NOT_A_STAGE', stage_label: '未知阶段' })] })).items[0];
    expect(task.status).toBe('UNKNOWN');
    expect(task.raw_status).toBe('NOT_A_STAGE');
    expect(task.stage_label).toBe('未知阶段');
  });

  it('preserves the absence of progress instead of inventing 0%', () => {
    const task = tasks(tasksResponse({ items: [projectedTask({ progress: null })] })).items[0];
    expect(task.progress).toBeNull();
    expect(JSON.stringify(task)).not.toContain('"completed":0');
    // 一个不自洽的进度不是"缺省"，而是拒绝读取。
    expect(rejectionCode(() => tasks(tasksResponse({ items: [projectedTask({ progress: { completed: 9, total: 8, unit: '分块' } })] }))))
      .toBe('TASK_CENTER_PROJECTION_INVALID');
  });

  it('refuses any unknown key on the task projection or its envelope', () => {
    expect(rejectionCode(() => tasks({ ...tasksResponse(), extra: true }))).toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => tasks(tasksResponse({ items: [{ ...projectedTask(), note: 'x' }] }))))
      .toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => tasks(tasksResponse({ items: [{ ...projectedTask(), cost: { estimate: null, actual: null, state: 'UNKNOWN', currency: 'CNY' } }] }))))
      .toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => tasks(tasksResponse({ items: [projectedTask({ progress: { completed: 1, total: 2, unit: '分块', eta: 5 } })] }))))
      .toBe('TASK_CENTER_PROJECTION_INVALID');
  });

  it('refuses a cancel action that the owner limits contradict', () => {
    const contradictory = projectedTask({ actions: ['open_source', 'cancel'] });
    expect(rejectionCode(() => tasks(tasksResponse({ items: [contradictory] })))).toBe('TASK_CENTER_PROJECTION_INVALID');
    // 允许取消却没有 revision 也是不自洽：取消无法回传 expected_revision。
    const revisionless = projectedFeatureOwnedTask({ revision: undefined });
    expect(rejectionCode(() => tasks(tasksResponse({ items: [revisionless] })))).toBe('TASK_CENTER_PROJECTION_INVALID');
  });

  it('refuses malformed unavailable entries and an envelope that claims auto-refresh', () => {
    expect(rejectionCode(() => tasks(tasksResponse({ unavailable: [{ authority: 'exports', label: '导出任务' }] }))))
      .toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => tasks(tasksResponse({ unavailable: [{ authority: 'exports', label: '导出任务', reason: 'SOURCE_UNAVAILABLE', extra: 1 }] }))))
      .toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => tasks(tasksResponse({ executor: true })))).toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => tasks(tasksResponse({ refresh: 'AUTO' })))).toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => tasks(tasksResponse({ automatic_retries: true })))).toBe('TASK_CENTER_PROJECTION_INVALID');
  });

  it('verifies only the identity the payload really discloses', () => {
    // tasks() 本身不带项目身份：没有披露就如实 scope_verified=false。
    expect(tasks(tasksResponse()).scope_verified).toBe(false);
    expect(rejectionCode(() => tasks(tasksResponse({ items: [projectedTask({ source: { kind: 'feature', id: 'x', novel_id: 'other-project' } })] }))))
      .toBe('TASK_CENTER_SCOPE_MISMATCH');
    const same = tasks(tasksResponse({ items: [projectedTask({ source: { kind: 'feature', id: 'x', novel_id: FIXTURE_PROJECT } })] }));
    expect(same.scope_verified).toBe(true);
    expect(rejectionCode(() => taskCenterProjection(tasksResponse(), ''))).toBe('TASK_CENTER_PROJECTION_INVALID');
  });
});

describe('task center contract against real _normalize inbox items', () => {
  it('accepts UnifiedReviewInbox.list() with its approval authority and per-item batch semantics', () => {
    const decoded = inbox(reviewInboxResponse());
    expect(decoded.approval_authority).toBe('DOMAIN_SERVICE');
    expect(decoded.batch_semantics).toBe('PER_ITEM_CHECKPOINT');
    expect(decoded.total).toBe(2);
    // 被拒绝的领域必须保留：拒绝不是空收件箱。
    expect(decoded.unavailable).toEqual([{ domain: 'legacy_canon', reason: 'ORIGINAL_DOMAIN_ACCESS_REQUIRED' }]);
  });

  it('preserves the owner-declared item fields and drops domain-specific extras', () => {
    const media = inbox(reviewInboxResponse({ items: [reviewInboxItem()], unavailable: [] })).items[0];
    expect(media).toMatchObject({
      id: 'candidate-1', domain: 'media', status: 'PENDING_REVIEW', stale: false, version: 3,
      source: 'media-task-1', source_hash: 'f0e1d2c3'.repeat(8), created_by: 'local-author',
      privacy_state: 'LOCAL_ONLY', risk: 'GENERATED_MEDIA_REQUIRES_REVIEW',
      allowed_actions: ['approve', 'reject'], batch_actions: [], batch_safe: false,
    });
    expect(media.preview).toEqual({ kind: 'text', text: 'COVER candidate 1' });
    expect(media.source_versions).toEqual([{ key: 'brief:brief-1', value: '{"version":2,"digest":"' + 'b'.repeat(64) + '"}' }]);
    expect(media.target).toEqual([{ key: 'brief_id', value: 'brief-1' }, { key: 'asset_id', value: '' }]);
    expect(media.scope).toEqual({ mode: 'local', novel_id: FIXTURE_PROJECT });
    // 领域原始键（_normalize 的 deepcopy 结果）不进入模型，也不会被渲染。
    expect(Object.keys(media)).not.toContain('kind');
    expect(Object.keys(media)).not.toContain('task_id');
    expect(JSON.stringify(media)).not.toContain('candidate_index');
  });

  it('keeps the planning batch subset exactly as the owner intersected it', () => {
    const planning = inbox(reviewInboxResponse({ items: [reviewInboxBatchItem()], unavailable: [] })).items[0];
    expect(planning.domain).toBe('planning');
    expect(planning.allowed_actions).toEqual(['approve', 'reject']);
    expect(planning.batch_actions).toEqual(['reject']);
    expect(planning.batch_safe).toBe(true);
    expect(planning.privacy_state).toBe('UNKNOWN');
    expect(planning.created_by).toBe('UNKNOWN');
  });

  it('refuses malformed items, subset violations and a wrong envelope', () => {
    const foreign = { ...reviewInboxItem(), scope: { mode: 'local', novel_id: 'other-project' } };
    expect(rejectionCode(() => inbox(reviewInboxResponse({ items: [foreign], unavailable: [] }))))
      .toBe('REVIEW_INBOX_SCOPE_MISMATCH');
    const missingScope = { ...reviewInboxItem() } as Record<string, unknown>;
    delete missingScope.scope;
    expect(rejectionCode(() => inbox(reviewInboxResponse({ items: [missingScope], unavailable: [] }))))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    const foreignProject = { ...reviewInboxItem(), project: 'other-project' };
    expect(rejectionCode(() => inbox(reviewInboxResponse({ items: [foreignProject], unavailable: [] }))))
      .toBe('REVIEW_INBOX_SCOPE_MISMATCH');
    // batch_actions 必须是 allowed_actions 的子集。
    const notSubset = { ...reviewInboxBatchItem(), allowed_actions: ['approve'] };
    expect(rejectionCode(() => inbox(reviewInboxResponse({ items: [notSubset], unavailable: [] }))))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    // batch_safe 必须与 batch_actions 一致。
    const inconsistent = { ...reviewInboxItem(), batch_safe: true };
    expect(rejectionCode(() => inbox(reviewInboxResponse({ items: [inconsistent], unavailable: [] }))))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => inbox(reviewInboxResponse({ items: [reviewInboxItem({ version: 0 })], unavailable: [] }))))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => inbox({ ...reviewInboxResponse(), approval_authority: 'UI' })))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => inbox({ ...reviewInboxResponse(), batch_semantics: 'ALL_OR_NOTHING' })))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => inbox({ ...reviewInboxResponse(), extra: true })))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    // total 必须重算自实际返回的行数。
    expect(rejectionCode(() => inbox({ ...reviewInboxResponse(), total: 9 })))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => inbox(reviewInboxResponse({ unavailable: [{ domain: 'legacy_canon' }] }))))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
  });
});

describe('task center local request shapes', () => {
  it('accepts the frozen cancel revision and refuses anything else', () => {
    expect(taskCancelRequest({ expected_revision: 'a1b2c3d4'.repeat(8) })).toEqual({ expected_revision: 'a1b2c3d4'.repeat(8) });
    expect(rejectionCode(() => taskCancelRequest({ expected_revision: 'a'.repeat(63) }))).toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => taskCancelRequest({ expected_revision: 'A'.repeat(64) }))).toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => taskCancelRequest({ expected_revision: 'a'.repeat(64), force: true }))).toBe('TASK_CENTER_PROJECTION_INVALID');
  });

  it('bounds the review action and the batch item set', () => {
    expect(reviewActionRequest({ expected_version: 3 })).toEqual({ expected_version: 3 });
    expect(rejectionCode(() => reviewActionRequest({ expected_version: 0 }))).toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => reviewActionRequest({ expected_version: 1, action: 'approve' }))).toBe('REVIEW_INBOX_PROJECTION_INVALID');
    const item = { domain: 'planning', id: 'proposal-1', action: 'reject', expected_version: 5 };
    expect(reviewBatchRequest({ items: [item] }).items).toEqual([item]);
    expect(rejectionCode(() => reviewBatchRequest({ items: [] }))).toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => reviewBatchRequest({ items: [item, { ...item, id: 'proposal-2' }, { ...item }] })))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => reviewBatchRequest({ items: [{ ...item, action: 'archive' }] })))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => reviewBatchRequest({ items: Array.from({ length: 51 }, (_, index) => ({ ...item, id: `p-${index}` })) })))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
  });
});

describe('task center receipts', () => {
  it('never reports a bare CANCELLED when the original task has not confirmed termination', () => {
    const pending = taskCancellationReceipt(cancelReceipt(), FIXTURE_PROJECT);
    expect(pending.cancellation_requested).toBe(true);
    expect(pending.executor).toBe(false);
    expect(pending.item.status).toBe('CANCELLING');
    expect(pending.termination_confirmed).toBe(false);
    const confirmed = taskCancellationReceipt(cancelReceipt({
      item: projectedTask({ status: 'CANCELLED', stage_label: '已取消', actions: ['open_source'] }),
    }), FIXTURE_PROJECT);
    expect(confirmed.termination_confirmed).toBe(true);
    expect(rejectionCode(() => taskCancellationReceipt(cancelReceipt({ cancellation_requested: false }), FIXTURE_PROJECT)))
      .toBe('TASK_CENTER_PROJECTION_INVALID');
    expect(rejectionCode(() => taskCancellationReceipt({ ...cancelReceipt(), executor: true }, FIXTURE_PROJECT)))
      .toBe('TASK_CENTER_PROJECTION_INVALID');
  });

  it('re-derives the per-item batch outcome instead of trusting the label', () => {
    const partial = reviewBatchReceipt(batchReceipt());
    expect(partial.status).toBe('PARTIAL');
    expect(partial.retry).toBe('REFRESH_AND_SELECT_FAILED_ITEMS');
    expect(partial.batch_semantics).toBe('PER_ITEM_CHECKPOINT');
    expect(partial.results).toEqual([
      { domain: 'planning', id: 'proposal-1', status: 'SUCCEEDED' },
      { domain: 'planning', id: 'proposal-2', status: 'FAILED', code: 'HTTP_409' },
    ]);
    const completed = reviewBatchReceipt({
      status: 'COMPLETED', results: [
        { domain: 'planning', id: 'p-1', status: 'SUCCEEDED', result: { ok: true } },
        { domain: 'planning', id: 'p-2', status: 'SUCCEEDED' },
      ], remaining: 0,
    });
    expect(completed.retry).toBeNull();
    // 一个自称 COMPLETED 却含失败项的回执是自相矛盾的。
    expect(rejectionCode(() => reviewBatchReceipt({
      status: 'COMPLETED', results: batchReceipt().results, remaining: 0,
    }))).toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => reviewBatchReceipt({ ...batchReceipt(), status: 'COMPLETED' })))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
    expect(rejectionCode(() => reviewBatchReceipt({ ...batchReceipt(), extra: 1 })))
      .toBe('REVIEW_INBOX_PROJECTION_INVALID');
  });
});
