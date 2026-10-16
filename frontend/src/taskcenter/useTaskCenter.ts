import { useTaskCostReceipt } from './useTaskCostReceipt';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import {
  EMPTY_TASK_CENTER_FILTER, REVIEW_INBOX_ACTION_LABELS, REVIEW_INBOX_ACTIONS, TASK_CENTER_ERROR_CODES,
  TASK_CENTER_NOTICES, TASK_STATUS_CODES, TASK_STATUS_LABELS,
  type ReviewInboxAction, type ReviewInboxItem, type ReviewInboxProjection, type TaskCenterActionResult,
  type TaskCenterClient, type TaskCenterFilter, type TaskCenterNavigationTarget,
  type TaskCenterProblem, type TaskCenterQueue, type TaskCenterSurfaceState, type TaskCenterTask,
  type TaskCenterTasksProjection,
} from './taskCenterTypes';

const READ_FAILURE = TASK_CENTER_NOTICES.tasksReadFailure;
const INBOX_FAILURE = TASK_CENTER_NOTICES.inboxReadFailure;

export type TaskCenterControllerProps = {
  /** 稳定的工作区/分支身份；变化会丢弃此前读到的一切。 */
  identity: string;
  /** 视图在屏幕上。关闭的视图永远不发起读取，也没有任何定时器。 */
  active: boolean;
  denied: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  mutate: <T>(work: () => Promise<T>) => Promise<T>;
  client: TaskCenterClient;
  /** 导航只能由调用方执行：这里只发出原 owner 的 id 与来源指针。 */
  onNavigate?: (target: TaskCenterNavigationTarget) => void;
  onUnavailable?: () => void;
};

export type TaskCenterModuleOption = { value: string; label: string };
export type TaskCenterSummary = {
  total: number;
  by_status: { status: string; label: string; count: number }[];
  without_progress: number;
  stale_source: number;
  unavailable: number;
  truncated: boolean;
  /** 由 owner 自己声明的刷新策略（`refresh: 'MANUAL'`）。 */
  refresh: 'MANUAL';
  automatic_retries: false;
};
export type ReviewInboxSummary = {
  total: number;
  unavailable: number;
  /** 只针对当前勾选的候选计算：owner 的 `batch_actions` 与实际选择共同决定。 */
  selected_batch_actions: ReviewInboxAction[];
  stale: number;
  approval_authority: 'DOMAIN_SERVICE';
  batch_semantics: 'PER_ITEM_CHECKPOINT';
};

function problemOf(reason: unknown, fallback: string, fallbackCode: string): TaskCenterProblem {
  // 只渲染传输层自己的有界文案；本地异常绝不原样回显。
  return reason instanceof ApiError
    ? { code: reason.problem.code, message: apiErrorView(reason, fallback).message }
    : { code: fallbackCode, message: fallback };
}
const taskKey = (task: Pick<TaskCenterTask, 'authority' | 'id'>) => `${task.authority}:${task.id}`;
const itemKey = (item: Pick<ReviewInboxItem, 'domain' | 'id'>) => `${item.domain}:${item.id}`;
const surface = (items: number, unavailable: number): TaskCenterSurfaceState =>
  items > 0 ? 'READY' : unavailable > 0 ? 'DENIED' : 'EMPTY';

/** 只读可用性推导：按钮的唯一来源是 owner 的 `allowed_actions` / `batch_actions`。 */
export function reviewActionAvailability(item: ReviewInboxItem): ReviewInboxAction[] {
  // 领域要求走自己的恢复流程时，普通审核按钮一律不出现（见 PromotionRecovery.tsx 的同一抑制条件）。
  if (item.promotion_recovery_required) return [];
  return REVIEW_INBOX_ACTIONS.filter(action => item.allowed_actions.includes(action)
    && !(action === 'approve' && item.stale));
}
export function batchActionAvailability(items: ReviewInboxItem[]): ReviewInboxAction[] {
  if (!items.length || items.some(item => item.promotion_recovery_required)) return [];
  const shared = REVIEW_INBOX_ACTIONS.filter(action => items.every(item => item.batch_actions.includes(action)
    && !(action === 'approve' && item.stale)));
  return shared;
}
const requestKeyOf = (identity: string, queue: TaskCenterQueue, filters: TaskCenterFilter) => queue === 'TASKS'
  ? `${identity}|q=${filters.query}|failed=${filters.failed_only}`
  : `${identity}|domain=${filters.module}|status=${filters.status}|search=${filters.query}`;

/**
 * 任务中心控制器：两个队列各自独立的显式状态，过滤只在按需刷新时生效，
 * 没有任何轮询、没有定时器，面板关闭就停止读取。
 */
export function useTaskCenter(props: TaskCenterControllerProps) {
  const [queue, setQueueState] = useState<TaskCenterQueue>('TASKS');
  const [filters, setFiltersState] = useState<TaskCenterFilter>(EMPTY_TASK_CENTER_FILTER);
  const [applied, setApplied] = useState<TaskCenterFilter>(EMPTY_TASK_CENTER_FILTER);
  const [tasks, setTasks] = useState<TaskCenterTasksProjection>();
  const [inbox, setInbox] = useState<ReviewInboxProjection>();
  const [tasksState, setTasksState] = useState<TaskCenterSurfaceState>('IDLE');
  const [reviewState, setReviewState] = useState<TaskCenterSurfaceState>('IDLE');
  const [tasksProblem, setTasksProblem] = useState<TaskCenterProblem>();
  const [reviewProblem, setReviewProblem] = useState<TaskCenterProblem>();
  const [results, setResults] = useState<Record<string, TaskCenterActionResult>>({});
  const [pending, setPending] = useState<Record<string, true>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [openItem, setOpenItem] = useState('');
  const [notice, setNotice] = useState('');

  const alive = useRef(true), epoch = useRef(0), revoked = useRef(false);
  const abort = useRef<AbortController>();
  const loaded = useRef<{ TASKS: string; REVIEW: string }>({ TASKS: '', REVIEW: '' });
  const running = useRef<Record<string, boolean>>({});
  const latest = useRef(props);
  const appliedRef = useRef(applied);
  const resultsRef = useRef(results);
  latest.current = props; appliedRef.current = applied; resultsRef.current = results;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; abort.current?.abort(); }; }, []);

  const admit = useCallback(() => alive.current && !revoked.current && latest.current.active
    && !latest.current.denied && latest.current.isCurrent(), []);

  const revoke = useCallback(() => {
    revoked.current = true;
    setTasks(undefined); setInbox(undefined); setResults({}); setSelected([]); setOpenItem(''); setNotice('');
    setTasksProblem(undefined); setReviewProblem(undefined);
    setTasksState('DENIED'); setReviewState('DENIED');
    latest.current.onUnavailable?.();
  }, []);

  const readTasks = useCallback(async (silent = false) => {
    const captured = latest.current;
    if (!admit() || (!silent && (captured.busy || running.current.tasks))) return;
    const controller = new AbortController();
    abort.current?.abort(); abort.current = controller;
    const request = ++epoch.current;
    if (!silent) { running.current.tasks = true; setTasksProblem(undefined); setTasksState('LOADING'); }
    try {
      const value = await captured.read(() => captured.client.readTasks({
        q: appliedRef.current.query, failed_only: appliedRef.current.failed_only,
      }, controller.signal));
      if (request !== epoch.current || !admit()) return;
      setTasks(value);
      setTasksState(surface(value.items.length, value.unavailable.length));
      setTasksProblem(undefined);
    } catch (reason) {
      if (request !== epoch.current || controller.signal.aborted || !alive.current) return;
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) { revoke(); return; }
      if (silent) return;
      setTasksProblem(problemOf(reason, READ_FAILURE, TASK_CENTER_ERROR_CODES.tasksReadFailed));
      setTasksState('FAILED');
    } finally { if (request === epoch.current) running.current.tasks = false; }
  }, [admit, revoke]);

  const readInbox = useCallback(async (silent = false) => {
    const captured = latest.current;
    if (!admit() || (!silent && (captured.busy || running.current.review))) return;
    const controller = new AbortController();
    abort.current?.abort(); abort.current = controller;
    const request = ++epoch.current;
    if (!silent) { running.current.review = true; setReviewProblem(undefined); setReviewState('LOADING'); }
    try {
      const value = await captured.read(() => captured.client.readInbox({
        domain: appliedRef.current.module, status: appliedRef.current.status, search: appliedRef.current.query,
      }, controller.signal));
      if (request !== epoch.current || !admit()) return;
      setInbox(value);
      setReviewState(surface(value.items.length, value.unavailable.length));
      setReviewProblem(undefined);
    } catch (reason) {
      if (request !== epoch.current || controller.signal.aborted || !alive.current) return;
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) { revoke(); return; }
      if (silent) return;
      setReviewProblem(problemOf(reason, INBOX_FAILURE, TASK_CENTER_ERROR_CODES.inboxReadFailed));
      setReviewState('FAILED');
    } finally { if (request === epoch.current) running.current.review = false; }
  }, [admit, revoke]);

  useEffect(() => {
    epoch.current++; abort.current?.abort(); running.current = {}; loaded.current = { TASKS: '', REVIEW: '' };
    revoked.current = props.denied;
    setTasks(undefined); setInbox(undefined); setResults({}); setPending({}); setSelected([]); setOpenItem('');
    setTasksProblem(undefined); setReviewProblem(undefined); setNotice('');
    setTasksState(props.denied ? 'DENIED' : 'IDLE');
    setReviewState(props.denied ? 'DENIED' : 'IDLE');
  }, [props.identity, props.denied]);

  // 按需读取：只有可见队列、身份/过滤器组合第一次出现时才读一次；没有任何轮询。
  const desired = requestKeyOf(props.identity, queue, applied);
  useEffect(() => {
    if (!props.active || props.denied) return;
    if (loaded.current[queue] === desired) return;
    loaded.current[queue] = desired;
    if (queue === 'TASKS') void readTasks(); else void readInbox();
  }, [desired, props.active, props.denied, queue, readTasks, readInbox]);

  const setQueue = useCallback((next: TaskCenterQueue) => { if (alive.current) setQueueState(next); }, []);
  const setFilters = useCallback((patch: Partial<TaskCenterFilter>) => {
    if (!alive.current) return;
    setFiltersState(previous => ({ ...previous, ...patch }));
  }, []);
  const applyFilters = useCallback(() => {
    if (!alive.current || revoked.current || !latest.current.active || latest.current.denied) return;
    const next = { ...filters };
    setApplied(next); appliedRef.current = next;
    // 任务队列的模块/状态是本地过滤，端点没有这些参数：值只用于呈现，不伪造请求参数。
    const key = requestKeyOf(latest.current.identity, queue, next);
    if (loaded.current[queue] === key) return;
    // 先登记新的请求键，再显式读取一次；效果里的守卫因此不会重复发起同一个请求。
    loaded.current[queue] = key;
    if (queue === 'TASKS') void readTasks(); else void readInbox();
  }, [filters, queue, readTasks, readInbox]);
  const resetFilters = useCallback(() => {
    if (!alive.current) return;
    setFiltersState(EMPTY_TASK_CENTER_FILTER); setApplied(EMPTY_TASK_CENTER_FILTER);
    appliedRef.current = EMPTY_TASK_CENTER_FILTER;
    loaded.current[queue] = requestKeyOf(latest.current.identity, queue, EMPTY_TASK_CENTER_FILTER);
    if (queue === 'TASKS') void readTasks(); else void readInbox();
  }, [queue, readTasks, readInbox]);
  const reload = useCallback(() => {
    if (!admit() || latest.current.busy) return;
    loaded.current[queue] = requestKeyOf(latest.current.identity, queue, appliedRef.current);
    setNotice('');
    if (queue === 'TASKS') return readTasks(); else return readInbox();
  }, [admit, queue, readTasks, readInbox]);

  /** 每个动作都走同一个互斥闸门（原工作区的 `mutate`），结果逐项保留。 */
  const run = useCallback(async (key: string, work: () => Promise<void>) => {
    const captured = latest.current;
    if (!admit() || captured.busy || running.current[key]) return;
    running.current[key] = true;
    setPending(previous => ({ ...previous, [key]: true }));
    try { await captured.mutate(work); }
    finally {
      delete running.current[key];
      if (alive.current) setPending(previous => { const next = { ...previous }; delete next[key]; return next; });
    }
  }, [admit]);

  const cancelTask = useCallback((task: TaskCenterTask) => {
    const key = `cancel:${taskKey(task)}`;
    setNotice('');
    return run(key, async () => {
      setResults(previous => ({
        ...previous,
        [key]: { key, kind: 'cancel', state: 'RUNNING', notice: '', termination_confirmed: false },
      }));
      try {
        const receipt = await latest.current.client.cancelTask(task);
        if (!alive.current || !latest.current.isCurrent()) return;
        const message = receipt.termination_confirmed ? TASK_CENTER_NOTICES.cancelConfirmed : TASK_CENTER_NOTICES.cancelPending;
        setResults(previous => ({
          ...previous,
          [key]: {
            key, kind: 'cancel', state: 'SUCCEEDED', notice: message,
            termination_confirmed: receipt.termination_confirmed, item: receipt.item,
          },
        }));
        setNotice(`${message} ${TASK_CENTER_NOTICES.cancelScope}`);
        // 状态改变后静默重读一次，保持版本与 revision 新鲜（不是轮询）。
        void readTasks(true);
      } catch (reason) {
        if (!alive.current) return;
        if (reason instanceof ApiError && [401, 403].includes(reason.status)) { revoke(); return; }
        const problem = problemOf(reason, TASK_CENTER_NOTICES.cancelFailed, TASK_CENTER_ERROR_CODES.cancelLocalInvalid);
        setResults(previous => ({
          ...previous,
          [key]: { key, kind: 'cancel', state: 'FAILED', notice: problem.message, termination_confirmed: false },
        }));
        setNotice(problem.message);
        // 版本/来源冲突：重新读取同一个原任务，绝不自动重试取消。
        if (reason instanceof ApiError && reason.status === 409) void readTasks(true);
      }
    });
  }, [readTasks, revoke, run]);

  const reviewItem = useCallback((item: ReviewInboxItem, action: ReviewInboxAction) => {
    const key = `review:${itemKey(item)}`;
    const allowed = reviewActionAvailability(item);
    if (!allowed.includes(action)) {
      setNotice(item.promotion_recovery_required
        ? '此候选的原领域要求先完成它自己的恢复流程，因此这里不显示普通审核按钮。'
        : '此动作不在原 owner 声明的可用动作里，因此没有按钮。');
      return Promise.resolve();
    }
    // 同一候选版本已经提交过决定就不再发第二次：重复提交不能制造第二份正式结果。
    const previousResult = resultsRef.current[key];
    if (previousResult?.kind === 'review' && previousResult.state === 'SUCCEEDED'
      && previousResult.expected_version === item.version) {
      setNotice(TASK_CENTER_NOTICES.reviewDuplicateGuard);
      return Promise.resolve();
    }
    setNotice('');
    return run(key, async () => {
      setResults(previous => ({ ...previous, [key]: { key, kind: 'review', state: 'RUNNING', action, notice: '', expected_version: item.version } }));
      try {
        await latest.current.client.reviewItem({ domain: item.domain, id: item.id, version: item.version }, action);
        if (!alive.current || !latest.current.isCurrent()) return;
        const message = `${TASK_CENTER_NOTICES.reviewSubmitting}（${REVIEW_INBOX_ACTION_LABELS[action]}）`;
        setResults(previous => ({
          ...previous,
          [key]: { key, kind: 'review', state: 'SUCCEEDED', action, notice: message, expected_version: item.version },
        }));
        setNotice(message);
        // 成功的决定会改变版本：静默重读，避免第二次提交制造重复的正式结果。
        void readInbox(true);
      } catch (reason) {
        if (!alive.current) return;
        if (reason instanceof ApiError && [401, 403].includes(reason.status)) { revoke(); return; }
        const problem = problemOf(reason, '审核决定未提交，请重新读取候选后核对。', TASK_CENTER_ERROR_CODES.reviewLocalInvalid);
        setResults(previous => ({
          ...previous,
          [key]: { key, kind: 'review', state: 'FAILED', action, notice: problem.message, expected_version: item.version },
        }));
        setNotice(problem.message);
        if (reason instanceof ApiError && reason.status === 409) void readInbox(true);
      }
    });
  }, [readInbox, revoke, run]);

  const reviewBatch = useCallback((items: ReviewInboxItem[], action: ReviewInboxAction) => {
    const key = `batch:${action}`;
    const allowed = batchActionAvailability(items);
    if (!items.length || !allowed.includes(action)) {
      setNotice('所选候选并非都允许这个批量动作，因此没有提交。');
      return Promise.resolve();
    }
    setNotice('');
    return run(key, async () => {
      setResults(previous => ({ ...previous, [key]: { key, kind: 'batch', state: 'RUNNING', action, notice: '' } }));
      try {
        const receipt = await latest.current.client.reviewBatch({
          items: items.map(item => ({ domain: item.domain, id: item.id, action, expected_version: item.version })),
        });
        if (!alive.current || !latest.current.isCurrent()) return;
        const failed = receipt.results.filter(row => row.status === 'FAILED').length;
        const message = `${receipt.status} · 逐项结果 ${receipt.results.length} 条，失败 ${failed} 条，未处理 ${receipt.remaining} 条。${TASK_CENTER_NOTICES.batchReselectFailed}`;
        setResults(previous => ({
          ...previous,
          [key]: { key, kind: 'batch', state: receipt.status === 'COMPLETED' ? 'SUCCEEDED' : 'FAILED', action, notice: message, receipt },
        }));
        setNotice(message);
        setSelected([]);
        void readInbox(true);
      } catch (reason) {
        if (!alive.current) return;
        if (reason instanceof ApiError && [401, 403].includes(reason.status)) { revoke(); return; }
        const problem = problemOf(reason, '批量审核结果未确认，请逐项核对后再决定。', TASK_CENTER_ERROR_CODES.batchLocalInvalid);
        setResults(previous => ({ ...previous, [key]: { key, kind: 'batch', state: 'FAILED', action, notice: problem.message } }));
        setNotice(problem.message);
        if (reason instanceof ApiError && reason.status === 409) void readInbox(true);
      }
    });
  }, [readInbox, revoke, run]);

  const navigateTask = useCallback((task: TaskCenterTask) => {
    if (!admit()) return;
    if (task.navigation_contract === 'FORMAL_SOURCE_ONLY') { setNotice(TASK_CENTER_NOTICES.formalSourceOnly); return; }
    // 查同一个原任务：只发出它自己的来源指针，不重新提交模型、不重新渲染。
    latest.current.onNavigate?.({
      queue: 'TASKS', authority: task.authority, task_id: task.id, label: task.label, feature: task.feature,
      source: task.owner_navigation ?? task.source,
    });
  }, [admit]);
  const navigateItem = useCallback((item: ReviewInboxItem) => {
    if (!admit()) return;
    latest.current.onNavigate?.({
      queue: 'REVIEW', domain: item.domain, item_id: item.id, version: item.version,
      source: item.source, target: item.target,
    });
  }, [admit]);

  const toggleSelected = useCallback((key: string) => {
    if (!alive.current) return;
    setSelected(previous => previous.includes(key) ? previous.filter(value => value !== key) : [...previous, key]);
  }, []);
  const clearSelection = useCallback(() => { if (alive.current) setSelected([]); }, []);
  const selectAllBatchSafe = useCallback((action: ReviewInboxAction) => {
    if (!alive.current || !inbox) return;
    setSelected(inbox.items.filter(item => batchActionAvailability([item]).includes(action)).map(itemKey));
  }, [inbox]);
  /** owner 的重试要求是 REFRESH_AND_SELECT_FAILED_ITEMS：只能由用户显式重新勾选失败项。 */
  const selectFailedFromLastBatch = useCallback((action: ReviewInboxAction) => {
    if (!alive.current || !inbox) return;
    const receipt = results[`batch:${action}`];
    if (receipt?.kind !== 'batch' || !receipt.receipt) return;
    const failed = new Set(receipt.receipt.results.filter(row => row.status === 'FAILED').map(row => `${row.domain}:${row.id}`));
    setSelected(inbox.items.filter(item => failed.has(itemKey(item))
      && batchActionAvailability([item]).includes(action)).map(itemKey));
    setNotice('已仅重新勾选上一次失败且当前仍允许该动作的候选；不会自动重发。');
  }, [inbox, results]);

  const visibleTasks = useMemo(() => (tasks?.items ?? []).filter(task =>
    (!applied.module || task.feature === applied.module || task.authority === applied.module)
    && (!applied.status || task.status === applied.status)), [tasks, applied.module, applied.status]);

  const summary: TaskCenterSummary = useMemo(() => {
    const counts = new Map<string, number>();
    for (const task of visibleTasks) counts.set(task.status, (counts.get(task.status) ?? 0) + 1);
    return {
      total: visibleTasks.length,
      by_status: TASK_STATUS_CODES.filter(code => counts.has(code)).map(code => ({
        status: code, label: TASK_STATUS_LABELS[code], count: counts.get(code) ?? 0,
      })),
      without_progress: visibleTasks.filter(task => task.progress === null).length,
      stale_source: visibleTasks.filter(task => task.stale).length,
      unavailable: tasks?.unavailable.length ?? 0,
      truncated: tasks?.truncated ?? false,
      refresh: 'MANUAL',
      automatic_retries: false,
    };
  }, [visibleTasks, tasks]);

  const moduleOptions: TaskCenterModuleOption[] = useMemo(() => {
    const byFeature = new Map<string, Set<string>>();
    for (const task of tasks?.items ?? []) {
      if (!byFeature.has(task.feature)) byFeature.set(task.feature, new Set());
      byFeature.get(task.feature)?.add(task.authority);
    }
    return [...byFeature.entries()]
      .map(([feature, authorities]) => ({ value: feature, label: `${feature}（${[...authorities].sort().join('、')}）` }))
      .sort((left, right) => left.value.localeCompare(right.value));
  }, [tasks]);
  const statusOptions: TaskCenterModuleOption[] = useMemo(() => {
    const observed = new Set((tasks?.items ?? []).map(task => task.status));
    return TASK_STATUS_CODES.filter(code => observed.has(code))
      .map(code => ({ value: code, label: `${TASK_STATUS_LABELS[code]}（${code}）` }));
  }, [tasks]);
  const domainOptions: TaskCenterModuleOption[] = useMemo(() => {
    const domains = new Set<string>();
    for (const item of inbox?.items ?? []) domains.add(item.domain);
    for (const entry of inbox?.unavailable ?? []) domains.add(entry.domain);
    return [...domains].sort().map(domain => ({ value: domain, label: domain }));
  }, [inbox]);

  const selectedItems = useMemo(() => (inbox?.items ?? []).filter(item => selected.includes(itemKey(item))), [inbox, selected]);
  const reviewSummary: ReviewInboxSummary = useMemo(() => ({
    total: inbox?.total ?? 0,
    unavailable: inbox?.unavailable.length ?? 0,
    selected_batch_actions: batchActionAvailability(selectedItems),
    stale: (inbox?.items ?? []).filter(item => item.stale).length,
    approval_authority: 'DOMAIN_SERVICE',
    batch_semantics: 'PER_ITEM_CHECKPOINT',
  }), [inbox, selectedItems]);

  const costReceipt = useTaskCostReceipt(props, visibleTasks, queue === 'TASKS' && tasksState === 'READY');

  const state = queue === 'TASKS' ? tasksState : reviewState;
  const problem = queue === 'TASKS' ? tasksProblem : reviewProblem;
  const canRead = !props.denied && !revoked.current && props.active && !props.busy && state !== 'LOADING';

  return {
    costReceipt,
    queue, setQueue,
    filters, setFilters, applyFilters, resetFilters,
    filtersDirty: filters.query !== applied.query || filters.failed_only !== applied.failed_only
      || filters.module !== applied.module || filters.status !== applied.status,
    state, problem, notice, canRead,
    tasks, inbox, tasksState, reviewState, tasksProblem, reviewProblem,
    visibleTasks, summary, moduleOptions, statusOptions, domainOptions,
    reviewSummary, selected, selectedItems, openItem, setOpenItem,
    results, pending,
    reload, cancelTask, reviewItem, reviewBatch, navigateTask, navigateItem,
    toggleSelected, clearSelection, selectAllBatchSafe, selectFailedFromLastBatch,
    taskKey, itemKey,
  };
}
export type TaskCenterController = ReturnType<typeof useTaskCenter>;
