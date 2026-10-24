import { TaskCostReceiptView } from './TaskCostReceipt';
import { taskRecoveryGuidance } from './taskCostReceiptHelpers';
import { useState } from 'react';
import { problemText } from './problemText'; // [HERMIA-FE-20261024 M6]
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import {
  TASK_ACTION_LABELS, TASK_CANCEL_LIMIT_LABELS, TASK_CENTER_NOTICES, TASK_ROUTE_STATE_LABELS,
  TASK_STATUS_TONES, type TaskCenterTask,
} from './taskCenterTypes';
import type { TaskCenterController } from './useTaskCenter';
import { TaskStatusSummary } from './TaskStatusSummary';

function progressText(task: TaskCenterTask) {
  // 只有原 owner 同时给出 completed+total 时才显示量化进度；否则如实说"进度未知"。
  return task.progress
    ? `${task.progress.completed} / ${task.progress.total} ${task.progress.unit}`
    : TASK_CENTER_NOTICES.progressUnknown;
}

function TaskCard({ controller, task }: { controller: TaskCenterController; task: TaskCenterTask }) {
  const [confirming, setConfirming] = useState(false);
  const key = controller.taskKey(task);
  const result = controller.results[`cancel:${key}`];
  const pending = controller.pending[`cancel:${key}`] === true;
  const cancellable = task.actions.includes('cancel') && !!task.revision;
  const openable = task.actions.includes('open_source') && task.navigation_contract !== 'FORMAL_SOURCE_ONLY';
  const unknown = task.status === 'UNKNOWN';
  return <li>
    <article className="task-center-task" data-unknown={unknown ? 'true' : 'false'}
      aria-label={`任务 ${task.authority} ${task.id}`}>
      <header>
        <h4>{task.label}</h4>
        <Badge tone={TASK_STATUS_TONES[task.status]}>{task.stage_label}</Badge>
        <span className="task-center-task__code">{task.status}</span>
        {task.raw_status !== task.status && <Badge tone="warning">按结果未知处理（原状态 {task.raw_status}）</Badge>}
        {task.stale && <Badge tone="warning">来源已变化</Badge>}
        <span className="task-center-summary__meta">{task.authority} · {task.feature}</span>
      </header>
      <dl>
        <div><dt>任务 ID</dt><dd className="task-center-task__code">{task.id}</dd></div>
        <div><dt>进度</dt><dd>{progressText(task)}</dd></div>
        <div><dt>版本</dt><dd>{task.version ?? '原服务未提供'}</dd></div>
        <div><dt>取消修订</dt><dd className="task-center-task__code">{task.revision || '未提供（不能取消）'}</dd></div>
        <div><dt>Provider / Model</dt><dd>{task.provider_id ?? '未知'} · {task.model_id ?? '未知'}（{TASK_ROUTE_STATE_LABELS[task.route_state]}）</dd></div>
        <div><dt>费用</dt><dd>预估 {task.cost.estimate ?? '未知'} · 实际 {task.cost.actual ?? '未知'}（{task.cost.state}）</dd></div>
        <div><dt>错误码</dt><dd className="task-center-task__code">{task.error_code ?? '没有已登记的错误码'}</dd></div>
      </dl>
      {unknown && <StatusMessage tone="warning">{TASK_CENTER_NOTICES.unknownStatus}</StatusMessage>}
      {task.raw_status !== task.status && <StatusMessage tone="warning">{TASK_CENTER_NOTICES.statusNotOwnerDefined}</StatusMessage>}
      <p>{task.lifecycle}</p>
      <p>{taskRecoveryGuidance(task)}</p>
      <p className="task-center-task__limits">
        原来源声明的动作限额：重试 {task.action_limits.retry}、恢复 {task.action_limits.resume}、审核 {task.action_limits.review}（策略 {task.retry_policy}）。
        {TASK_CENTER_NOTICES.noAutoRetry}
      </p>
      {task.action_limits.cancel !== null && <p className="task-center-task__limits">{TASK_CANCEL_LIMIT_LABELS[task.action_limits.cancel]}</p>}
      {task.navigation_contract === 'FORMAL_SOURCE_ONLY'
        && <StatusMessage tone="warning">{TASK_CENTER_NOTICES.formalSourceOnly}（来源领域：{task.source_domain ?? '未知'}）</StatusMessage>}
      {task.history.length > 0 && <details>
        <summary>原服务报告的状态历史（{task.history.length} 条，不含时间戳）</summary>
        <ol>{task.history.map((entry, index) => <li key={index}>v{entry.version ?? '—'} · {entry.status}</li>)}</ol>
      </details>}
      <div className="task-center__actions">
        <Button disabled={!controller.canRead} aria-expanded={controller.costReceipt.selection?.task === task}
          onClick={() => void controller.costReceipt.read(task)}>查看原任务费用回执</Button>
        {openable && <Button disabled={!controller.canRead} onClick={() => controller.navigateTask(task)}>
          {TASK_ACTION_LABELS.open_source}
        </Button>}
        {cancellable && <Button variant="danger" disabled={pending || !controller.canRead} onClick={() => setConfirming(true)}>
          {TASK_ACTION_LABELS.cancel}
        </Button>}
        {!openable && task.navigation_contract !== 'FORMAL_SOURCE_ONLY' && <span>原服务没有声明可打开的来源动作，因此这里没有按钮。</span>}
      </div>
      <TaskCostReceiptView controller={controller} task={task}/>
      {confirming && <section className="task-center-batch" aria-label="确认取消原任务">
        <h4>取消 {task.label}（{task.authority} · {task.id}）？</h4>
        <p>{TASK_CENTER_NOTICES.cancelScope}</p>
        <p>请求会带上当前取消修订 {task.revision}；原任务服务可能已经进入终态，那时会显示"待确认"而不是已取消。</p>
        <div className="task-center__actions">
          <Button variant="danger" disabled={pending} onClick={() => { setConfirming(false); void controller.cancelTask(task); }}>确认请求取消</Button>
          <Button disabled={pending} onClick={() => setConfirming(false)}>继续保留任务</Button>
        </div>
      </section>}
      {result && result.kind === 'cancel' && <StatusMessage tone={result.state === 'FAILED' ? 'error' : result.termination_confirmed ? 'success' : 'warning'}>
        {result.notice}{result.state === 'FAILED' ? '' : result.termination_confirmed ? '' : ` ${TASK_CENTER_NOTICES.cancelScope}`}
      </StatusMessage>}
    </article>
  </li>;
}

/** 任务队列：过滤在按需刷新时生效；按钮可用性只看原 owner 的 `actions`。 */
export function TaskList({ controller, panelId, labelledBy }: {
  controller: TaskCenterController; panelId?: string; labelledBy?: string;
}) {
  const { filters, setFilters } = controller;
  return <section className="task-center__queue" role="tabpanel" id={panelId} aria-labelledby={labelledBy} aria-label="任务队列">
    <form className="task-center__filters" onSubmit={event => { event.preventDefault(); controller.applyFilters(); }}>
      <label className="task-center__field"><span>按任务 ID、类型或阶段搜索</span>
        <input maxLength={160} value={filters.query} onChange={event => setFilters({ query: event.target.value })} />
      </label>
      <label className="task-center__field"><span>模块 / 权威（本地过滤）</span>
        <select value={filters.module} onChange={event => setFilters({ module: event.target.value })}>
          <option value="">全部模块</option>
          {controller.moduleOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <label className="task-center__field"><span>状态（本地过滤）</span>
        <select value={filters.status} onChange={event => setFilters({ status: event.target.value })}>
          <option value="">全部状态</option>
          {controller.statusOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
          {!!filters.status && !controller.statusOptions.some(option => option.value === filters.status)
            && <option value={filters.status}>{filters.status}</option>}
        </select>
      </label>
      <label className="task-center__check">
        <input type="checkbox" checked={filters.failed_only}
          onChange={event => setFilters({ failed_only: event.target.checked })} />只看失败或结果未知
      </label>
      <div className="task-center__actions">
        <Button type="submit" loading={controller.tasksState === 'LOADING'} disabled={!controller.canRead}>应用筛选并读取</Button>
        <Button type="button" onClick={controller.resetFilters}>清除筛选</Button>
        <Button type="button" onClick={() => void controller.reload()} disabled={!controller.canRead}>重新读取</Button>
      </div>
    </form>
    {controller.filtersDirty && <StatusMessage>筛选已修改，尚未应用；这里不会自动轮询，也不会自动重试。</StatusMessage>}
    <p>任务 ID、标签与阶段由原任务服务读取；模块与状态是本地过滤（端点没有这些参数）。取消只请求原任务服务，已完成的结果不会被撤销。</p>
    <TaskStatusSummary controller={controller}/>
    {controller.tasksState === 'LOADING' && <StatusMessage>正在读取当前项目的原任务投影…</StatusMessage>}
    {controller.tasksProblem && <StatusMessage tone="error">{/* [HERMIA-FE-20261024 M6] human text only; raw code kept as data-error-code for diagnostics */}<span data-error-code={controller.tasksProblem.code}>{problemText(controller.tasksProblem)}</span></StatusMessage>}
    {controller.tasksState === 'IDLE' && <EmptyState title="尚未读取任务队列" detail="打开队列后会读取一次；读取不会启动模型或任务。"/>}
    {controller.tasksState === 'EMPTY' && <EmptyState title="当前筛选下没有任务记录" detail="原服务返回了空队列且没有不可读来源；这不是权限被拒绝。"/>}
    {controller.tasksState === 'DENIED' && !controller.tasksProblem && <>
      <EmptyState title="所有来源当前都不可读" detail="原任务服务拒绝了这些来源；空列表不代表没有任务。"/>
      {controller.tasks?.unavailable.map(entry => <StatusMessage tone="warning" key={entry.authority}>
        {entry.label}（{entry.authority}）当前不可读：{entry.reason}。其他来源仍然可用。
      </StatusMessage>)}
    </>}
    {controller.tasksState === 'DENIED' && controller.tasksProblem && <EmptyState title="当前会话无权读取任务队列" detail="先前数据已清除。重新核对项目、身份和分支后再打开。"/>}
    {controller.tasksState === 'FAILED' && <EmptyState title="任务队列读取失败" detail="可以重新读取；不会自动重试，也不会改动任何任务。"/>}
    {controller.tasksState === 'READY' && <>
      {controller.tasksState === 'READY' && controller.tasks?.truncated && <StatusMessage tone="warning">显示范围达到上限；更早的记录请进入原任务工具查找。</StatusMessage>}
      {!!controller.tasks?.unavailable.length && <StatusMessage tone="warning">
        {TASK_CENTER_NOTICES.unavailableNotFullQueue}：
        {controller.tasks.unavailable.map(entry => `${entry.label}（${entry.reason}）`).join('、')}
      </StatusMessage>}
      {controller.visibleTasks.length === 0
        ? <EmptyState title="当前模块/状态过滤下没有记录" detail="原服务的返回里有任务，但都被本地过滤条件排除了。清除筛选可以看到全部。"/>
        : <ul className="task-center-list">{controller.visibleTasks.map(task =>
          <TaskCard key={controller.taskKey(task)} controller={controller} task={task}/>)}</ul>}
    </>}
  </section>;
}
