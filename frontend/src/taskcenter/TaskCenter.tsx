import { useMemo } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import type { CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { createTaskCenterClient } from './taskCenterClient';
import { TASK_CENTER_QUEUE_LABELS, type TaskCenterQueue } from './taskCenterTypes';
import { useTaskCenter, type TaskCenterController, type TaskCenterControllerProps } from './useTaskCenter';
import { ReviewInbox } from './ReviewInbox';
import { TaskList } from './TaskList';
import './taskCenter.css';

/**
 * UX-02 统一任务中心。它只消费既有 owner：
 * `WorkspaceToolsService.tasks` / `cancel_task`（`GET/POST …/experimental/workspace/tasks`）
 * 与 `UnifiedReviewInbox`（`…/experimental/review-inbox`），不新增队列、状态机或审核系统。
 *
 * 挂载方式（主代理在 `IndependentStudioWorkspace.tsx` 里二选一）：
 *
 * 1) 复用与 `ProductionDashboard` 相同的数据接缝：
 *    const taskCenterClient = useMemo(() => createTaskCenterClient(projectId,
 *      studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined }), context.scope),
 *      [projectId, context.sessionToken, context.actor?.id, context.scope?.workspaceId,
 *       context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
 *    const taskCenter = useTaskCenter({ identity: cacheKey, active: tasksView && !denied && !identityRetired,
 *      denied: denied || identityRetired, busy, isCurrent: current, read: guarded, mutate: graphMutation,
 *      client: taskCenterClient, onNavigate: rememberTarget, onUnavailable: deny });
 *    <TaskCenter controller={taskCenter} />
 *
 * 2) 或者一行版本：<TaskCenterPanel projectId={projectId} transport={studioTransport({...context})}
 *      scope={context.scope} identity={cacheKey} active={tasksView} denied={denied || identityRetired}
 *      busy={busy} isCurrent={current} read={guarded} mutate={graphMutation}
 *      onNavigate={rememberTarget} onUnavailable={deny} />
 *
 * 这里的导航只发出回调（原任务 id + 来源指针），不会自己跳转，也不会重新提交模型或重新渲染。
 */
export function TaskCenter({ controller }: { controller: TaskCenterController }) {
  const queue: TaskCenterQueue = controller.queue;
  return <Panel title="统一任务中心" className="task-center" aria-label="统一任务中心"
    actions={<Button loading={controller.state === 'LOADING'} disabled={!controller.canRead}
      onClick={() => void controller.reload()}>重新读取当前队列</Button>}>
    <div className="task-center__tabs" role="tablist" aria-label="任务中心队列">
      {(['TASKS', 'REVIEW'] as const).map(value => <Button key={value} role="tab"
        aria-selected={queue === value} variant={queue === value ? 'primary' : 'secondary'}
        onClick={() => controller.setQueue(value)}>{TASK_CENTER_QUEUE_LABELS[value]}</Button>)}
    </div>
    <p>把原任务服务的任务与原领域的待审候选放在一处：状态、进度、来源与可用动作全部照原服务显示，不新增第二套队列或审核。执行已完成不等于交付，取消与重试都由原任务服务决定。</p>
    {controller.notice && <StatusMessage>{controller.notice}</StatusMessage>}
    {queue === 'TASKS' ? <TaskList controller={controller}/> : <ReviewInbox controller={controller}/>}
  </Panel>;
}

export type TaskCenterPanelProps = Omit<TaskCenterControllerProps, 'client'> & {
  projectId: string;
  /** 与 `productionWorkflowClient` 相同的注入传输（例如 `studioTransport(context)`）。 */
  transport: StudioGraphTransport;
  scope?: CollaborationContext['scope'];
};

/**
 * 自包含挂载：自己构造客户端与控制器，便于在既有工作区里一行接入。
 * 传输对象每次渲染都可能是新实例，因此客户端按捕获到的分支身份重建；
 * 读取仍然只由控制器的按需刷新触发，不会因为重建而多发请求。
 */
export function TaskCenterPanel({ projectId, transport, scope, ...rest }: TaskCenterPanelProps) {
  const client = useMemo(() => createTaskCenterClient(projectId, transport, scope),
    [projectId, transport, scope?.workspaceId, scope?.projectId, scope?.storylineId, scope?.branchId]);
  const controller = useTaskCenter({ ...rest, client });
  return <TaskCenter controller={controller}/>;
}
