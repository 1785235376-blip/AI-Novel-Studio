import { useState } from 'react';
import { ApiError, apiErrorView, type ModelCenterModel } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { blockerText } from './WorkflowStatusBoard';
import type { ProductionWorkflowController } from './useProductionWorkflow';
import {
  PRODUCTION_WORKFLOW_ASSET_KINDS, PRODUCTION_WORKFLOW_ASSET_KIND_LABELS, PRODUCTION_WORKFLOW_STATUS_LABELS,
  PRODUCTION_WORKFLOW_STATUS_TONES,
  type ProductionWorkflowAssetKind, type ProductionWorkflowModuleId,
} from './productionWorkflowTypes';

/** Existing Model Center read only: registered runtime models are observed, never loaded here. */
export type ProductionModelSource = { load: () => Promise<ModelCenterModel[]> };
type ModelState = 'IDLE' | 'LOADING' | 'READY' | 'EMPTY' | 'ERROR' | 'DENIED';

function ModelAvailability({ source }: { source?: ProductionModelSource }) {
  const [state, setState] = useState<ModelState>('IDLE'), [models, setModels] = useState<ModelCenterModel[]>([]), [problem, setProblem] = useState('');
  const read = async () => {
    if (!source || state === 'LOADING') return;
    setState('LOADING'); setProblem('');
    try {
      const items = await source.load();
      setModels(items); setState(items.length ? 'READY' : 'EMPTY');
    } catch (reason) {
      setModels([]);
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) { setState('DENIED'); return; }
      setProblem(apiErrorView(reason, '模型可用性读取失败，请稍后重试。').message); setState('ERROR');
    }
  };
  return <section className="production-workflow-models" aria-label="模型可用性">
    <header><h3>模型可用性</h3><Button loading={state === 'LOADING'} disabled={!source || state === 'LOADING'} onClick={() => void read()}>读取模型可用性</Button></header>
    <p>只读取既有模型注册表与观察到的状态；此处不加载、不启动、不下载任何模型。</p>
    {!source && <p>当前工作区未提供模型注册表读取入口。</p>}
    {state === 'EMPTY' && <EmptyState title="尚未登记模型" detail="注册本地模型后会显示在这里，本视图不会代为安装。"/>}
    {state === 'DENIED' && <StatusMessage tone="warning">当前会话无权读取模型注册表。重新核对身份与范围后再试。</StatusMessage>}
    {state === 'ERROR' && <StatusMessage tone="error">{problem}</StatusMessage>}
    {models.length > 0 && <ul>
      {models.map(model => <li key={model.id}>
        <strong>{model.display_name}</strong>
        <Badge tone={model.status === 'READY' ? 'success' : model.status === 'INCOMPATIBLE' ? 'error' : 'warning'}>{model.status}</Badge>
        <span>{model.runtime_type} · {model.verified ? '已通过当前验证' : model.historically_validated ? '仅有历史验证' : '未验证'}</span>
      </li>)}
    </ul>}
  </section>;
}

export type ProductionInspectorPanelProps = {
  controller: ProductionWorkflowController;
  selectedModuleId: ProductionWorkflowModuleId;
  selectedKind: ProductionWorkflowAssetKind;
  onSelectKind: (kind: ProductionWorkflowAssetKind) => void;
  modelSource?: ProductionModelSource;
};

/** Selected module/asset detail, its next action, the asset browser and model availability. */
export function ProductionInspectorPanel({ controller, selectedModuleId, selectedKind, onSelectKind, modelSource }: ProductionInspectorPanelProps) {
  const projection = controller.projection;
  const module = projection?.modules.find(item => item.id === selectedModuleId);
  return <Panel title="制作模块" className="production-workflow-inspector" aria-label="Studio 生产工作流检查器">
    {!projection ? <p>读取 Studio 看板后，这里显示所选模块、素材类别与建议的下一步。</p> : <>
      <section aria-label="所选模块">
        {module ? <>
          <header><h3>{module.label}</h3><Badge tone={PRODUCTION_WORKFLOW_STATUS_TONES[module.status]}>{PRODUCTION_WORKFLOW_STATUS_LABELS[module.status]}</Badge></header>
          <dl>
            <div><dt>原服务</dt><dd>{module.owner}</dd></div>
            <div><dt>文档</dt><dd>{module.document_count}</dd></div>
            <div><dt>素材</dt><dd>{module.asset_count}</dd></div>
            <div><dt>任务</dt><dd>{module.job_count}</dd></div>
          </dl>
          {module.blocked_reasons.length > 0
            ? <StatusMessage tone="warning">受阻原因：{module.blocked_reasons.map(blockerText).join(' ')}（{module.blocked_reasons.join('、')}）</StatusMessage>
            : <p>此模块当前没有报告受阻原因；不代表已通过验收。</p>}
          <p>建议下一步：{module.next_action ?? '原服务未声明下一步。'}</p>
          <p>核对与执行仍由原服务负责；此面板不会创建任务、不会改变审核状态。</p>
        </> : <p>所选模块不在本次读取结果中，请重新读取工作流。</p>}
      </section>
      <section className="production-workflow-assets" aria-label="素材浏览器">
        <h3>素材浏览器</h3>
        <p>共 {projection.asset_overview.total} 项 · 待审核私有候选 {projection.asset_overview.private_pending_review} · 已审核 {projection.asset_overview.reviewed}</p>
        <ul aria-label="素材类别">
          {PRODUCTION_WORKFLOW_ASSET_KINDS.map(kind => <li key={kind}>
            <Button variant={selectedKind === kind ? 'primary' : 'secondary'} aria-pressed={selectedKind === kind}
              onClick={() => onSelectKind(kind)}>{PRODUCTION_WORKFLOW_ASSET_KIND_LABELS[kind]} · {projection.asset_overview.by_kind[kind]} 项</Button>
          </li>)}
        </ul>
        <p>当前类别：{PRODUCTION_WORKFLOW_ASSET_KIND_LABELS[selectedKind]} · {projection.asset_overview.by_kind[selectedKind]} 项。列表可在原素材工作区中查看与导出。</p>
      </section>
      <ModelAvailability source={modelSource}/>
    </>}
  </Panel>;
}
