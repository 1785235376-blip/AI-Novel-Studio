import { Badge, Button, StatusMessage } from '../ui/primitives';
import {
  PRODUCTION_WORKFLOW_STATUS_LABELS, PRODUCTION_WORKFLOW_STATUS_TONES,
  type ProductionWorkflowDashboard, type ProductionWorkflowModule, type ProductionWorkflowModuleId,
} from './productionWorkflowTypes';

/** Bounded, user-facing text per original blocker code. An unknown code is never hidden. */
const BLOCKER_LABELS: Record<string, string> = {
  PRIVATE_CANDIDATES_AWAITING_REVIEW: '有私有候选等待人工复核。',
  WINDOWS_PRODUCT_ACCEPTANCE_LOCAL_REQUIRED: '完整产品验收仍需在 Windows 上完成。',
  ORIGINAL_OWNER_ADAPTER_REQUIRED: '此模块还需要接入原服务。',
  ORIGINAL_JOB_AND_RECEIPT_REQUIRED: '需要从原任务入口核对运行与结果回执。',
};
export const blockerText = (reason: string) => BLOCKER_LABELS[reason] ?? '尚有未满足的条件，请核对原服务状态。';

export type WorkflowStatusBoardProps = {
  modules: ProductionWorkflowModule[];
  dashboard: ProductionWorkflowDashboard;
  selectedModuleId: ProductionWorkflowModuleId;
  onSelectModule: (id: ProductionWorkflowModuleId) => void;
  busy?: boolean;
  denied?: boolean;
};

/** Read-only board. Selecting a module never starts, retries or approves anything. */
export function WorkflowStatusBoard({ modules, dashboard, selectedModuleId, onSelectModule, busy, denied }: WorkflowStatusBoardProps) {
  return <section className="production-workflow-board" aria-label="七个制作模块状态">
    <header>
      <h3>模块工作流</h3>
      <p>已开始 {dashboard.stages_started} / {dashboard.stages_total} · 已审核 {dashboard.stages_reviewed} · 待审核私有候选 {dashboard.open_reviews} · 受阻模块 {dashboard.blocked_stages.length}</p>
    </header>
    <ol className="production-workflow-board__list">
      {modules.map(module => <li key={module.id}>
        <article className="production-workflow-module" data-blocked={module.blocked_reasons.length > 0} aria-label={`${module.label}模块`}>
          <header>
            <Button variant={selectedModuleId === module.id ? 'primary' : 'secondary'} aria-pressed={selectedModuleId === module.id}
              disabled={!!busy || !!denied} onClick={() => onSelectModule(module.id)}>{module.label}</Button>
            <Badge tone={PRODUCTION_WORKFLOW_STATUS_TONES[module.status]}>{PRODUCTION_WORKFLOW_STATUS_LABELS[module.status]}</Badge>
          </header>
          <dl>
            <div><dt>文档</dt><dd>{module.document_count}</dd></div>
            <div><dt>素材</dt><dd>{module.asset_count}</dd></div>
            <div><dt>任务</dt><dd>{module.job_count}</dd></div>
          </dl>
          <p className="production-workflow-module__owner">原服务：{module.owner}</p>
          {module.blocked_reasons.length > 0 && <StatusMessage tone="warning">
            {module.blocked_reasons.map(blockerText).join(' ')}
            <span className="production-workflow-module__codes"> · 缺项标识：{module.blocked_reasons.join('、')}</span>
          </StatusMessage>}
          {module.next_action && <p>建议下一步：{module.next_action}</p>}
        </article>
      </li>)}
    </ol>
  </section>;
}
