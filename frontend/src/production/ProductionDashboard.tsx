import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { ProductionAssetOverview } from './ProductionAssetOverview';
import { ProductionIntentEditor } from './ProductionIntentEditor';
import { WorkflowStatusBoard } from './WorkflowStatusBoard';
import type { ProductionWorkflowController } from './useProductionWorkflow';
import {
  PRODUCTION_WORKFLOW_MODULES, PRODUCTION_WORKFLOW_START_STATE_LABELS,
  type ProductionWorkflowAssetKind, type ProductionWorkflowModuleId, type ProductionWorkflowProjectStart,
} from './productionWorkflowTypes';
import './productionWorkflow.css';

function ProjectStart({ start, generatedAt }: { start: ProductionWorkflowProjectStart; generatedAt: string }) {
  return <section className="production-workflow-start" aria-label="项目开始状态">
    <header><h3>项目开始</h3>
      <Badge tone={start.state === 'STARTED' ? 'success' : start.state === 'READY' ? 'info' : 'neutral'}>{PRODUCTION_WORKFLOW_START_STATE_LABELS[start.state]}</Badge>
      <Badge tone="neutral">{start.entry_kind}</Badge>
    </header>
    <dl>
      <div><dt>已保存创作文档</dt><dd>{start.has_creative_documents ? '有' : '无'}</dd></div>
      <div><dt>项目身份</dt><dd>{start.incarnation ?? '尚未登记'}</dd></div>
      <div><dt>原入口</dt><dd>{start.start_action.method} {start.start_action.path}</dd></div>
      <div><dt>会话要求</dt><dd>{start.start_action.requires_original_host_session ? '需要原受信任会话' : '以原入口为准'}</dd></div>
      <div><dt>读取时间（UTC）</dt><dd>{generatedAt}</dd></div>
    </dl>
    <p>开始项目仍由原入口、受信任会话和既有权限决定；这里只描述该入口，不会代为创建项目。</p>
  </section>;
}

export type ProductionDashboardProps = {
  controller: ProductionWorkflowController;
  selectedModuleId: ProductionWorkflowModuleId;
  onSelectModule: (id: ProductionWorkflowModuleId) => void;
  selectedKind: ProductionWorkflowAssetKind;
  onSelectKind: (kind: ProductionWorkflowAssetKind) => void;
};

/**
 * Studio Dashboard content. It reads one advisory projection, lets the author edit the
 * neutral creative intent through the original CAS owner, and grants no execution.
 */
export function ProductionDashboard({ controller, selectedModuleId, onSelectModule, selectedKind, onSelectKind }: ProductionDashboardProps) {
  const projection = controller.projection;
  return <Panel title="Studio 看板" className="production-workflow-dashboard" aria-label="Studio 生产工作流看板"
    actions={<Button loading={controller.state === 'LOADING'} disabled={!controller.canRead} onClick={() => void controller.reload()}>重新读取工作流</Button>}>
    <p>把导演、分镜、图像、视频、音频、时间线和资产看成同一条工作流。本视图只读取原服务并显示建议：不创建任务、不执行模型、不改变审核状态，也不代表产品验收通过。</p>
    {controller.state === 'LOADING' && <StatusMessage>正在读取当前项目的生产工作流…</StatusMessage>}
    {controller.problem && controller.state !== 'READY' && <StatusMessage tone="error">{controller.problem.message} · {controller.problem.code}</StatusMessage>}
    {controller.state === 'IDLE' && <EmptyState title="尚未读取生产工作流" detail="打开这个视图后会读取一次；读取不会启动模型或任务。"/>}
    {controller.state === 'DENIED' && <EmptyState title="当前会话无权读取生产工作流" detail="先前数据已清除。重新核对当前项目、身份和分支后再打开。"/>}
    {controller.state === 'UNAVAILABLE' && <EmptyState title="生产工作流入口当前不可用" detail="请核对项目是否已通过原入口启用独立 Studio；不会自动启用或重建项目。"/>}
    {controller.state === 'ERROR' && <EmptyState title="生产工作流读取失败" detail="可以重新读取；不会自动重试，也不会改动项目。"/>}
    {projection && <>
      <ProjectStart start={projection.project_start} generatedAt={projection.generated_at}/>
      <ProductionIntentEditor controller={controller}/>
      <WorkflowStatusBoard modules={projection.modules} dashboard={projection.dashboard} selectedModuleId={selectedModuleId}
        onSelectModule={onSelectModule} busy={controller.saving}/>
      <ProductionAssetOverview overview={projection.asset_overview}/>
      <p className="production-workflow-dashboard__scope">共 {PRODUCTION_WORKFLOW_MODULES.length} 个模块；模板顺序与原服务集成顺序一致。</p>
    </>}
  </Panel>;
}
