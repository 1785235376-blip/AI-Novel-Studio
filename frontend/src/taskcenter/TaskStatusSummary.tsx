import { Badge } from '../ui/primitives';
import { TASK_CENTER_NOTICES } from './taskCenterTypes';
import type { TaskCenterController } from './useTaskCenter';
import { t as i18nT } from '../i18n'; // [HERMIA-FE-20261025 MERGE-FEC i18n]

/**
 * 执行状态与审核结果是**两个分开的区块**：
 * - 左边来自 `WorkspaceToolsService.tasks`（执行/阶段事实）；
 * - 右边来自 `UnifiedReviewInbox`（候选与审核结果）。
 * 执行已完成 ≠ 已交付：候选在通过原领域审核前不会出现在任何交付状态里。
 */
export function TaskStatusSummary({ controller }: { controller: TaskCenterController }) {
  const summary = controller.summary;
  const review = controller.reviewSummary;
  const tasksRead = controller.tasks !== undefined;
  const inboxRead = controller.inbox !== undefined;
  return <section className="task-center-summary" aria-label="任务与审核状态概览">
    <h3>状态概览</h3>
    <div className="task-center-summary__block" role="group" aria-label="执行状态（原任务投影）">
      <h4>执行状态 · 原任务投影</h4>
      {!tasksRead && <p>尚未读取任务队列。切换到「任务队列」时才会读取一次。</p>}
      {tasksRead && <>
        {summary.by_status.length
          ? <ul className="task-center-summary__counts">{summary.by_status.map(row => <li key={row.status}>
            <Badge>{row.label}</Badge><span className="task-center-summary__meta">{row.status} × {row.count}</span>
          </li>)}</ul>
          : <p>当前筛选下没有可统计的任务状态。</p>}
        <p className="task-center-summary__meta">{i18nT('fc.tc.summaryMeta', { prefix: i18nT(controller.paging ? 'fc.tc.summaryLoaded' : 'fc.tc.summaryTotal'), total: summary.total, noProgress: summary.without_progress, stale: summary.stale_source, unavailable: summary.unavailable })}{summary.truncated ? i18nT('fc.tc.summaryTruncated') : ''}</p>
        <p>刷新策略：{summary.refresh}（原服务自己声明）；自动重试：{summary.automatic_retries ? '存在' : '不存在'}。读取只在按需刷新或切换队列时发生，没有轮询。</p>
      </>}
      <p>{TASK_CENTER_NOTICES.noProgressClaim}</p>
    </div>
    <div className="task-center-summary__block" role="group" aria-label="审核结果（统一审核收件箱）">
      <h4>审核结果 · 统一审核收件箱</h4>
      {!inboxRead && <p>尚未读取审核收件箱。切换到「审核收件箱」时才会读取一次。</p>}
      {inboxRead && <>
        <p className="task-center-summary__meta">审核项 {review.total} 条 · 来源已变化 {review.stale} 条 · 不可读领域 {review.unavailable} 个</p>
        <p>审批权属：{review.approval_authority === 'DOMAIN_SERVICE' ? '原领域服务' : review.approval_authority}；批量语义：逐项 checkpoint（{review.batch_semantics}），不是全有或全无。</p>
        <p>{TASK_CENTER_NOTICES.executionIsNotDelivery}</p>
      </>}
    </div>
  </section>;
}
