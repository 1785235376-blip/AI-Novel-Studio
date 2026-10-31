import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { useStudioWorkspaceOperations, type StudioWorkspaceOperationControllerProps } from './useStudioWorkspaceOperations';
import { STUDIO_PRODUCTION_STAGES, STUDIO_PRODUCTION_STAGE_LABELS, type StudioProductionOperation,
  type StudioWorkspaceProductionContracts } from './studioWorkspaceOperationTypes';
import './studioWorkspaceOperations.css';

export type StudioWorkspaceOperationPanelProps = StudioWorkspaceOperationControllerProps & {
  /** Existing guarded navigation only; switching a view never grants execution. */
  onOpenSurface?: (view: 'ASSETS' | 'GRAPH') => void;
};

const BLOCKER_LABELS: Record<string, string> = {
  WINDOWS_PRODUCT_ACCEPTANCE_LOCAL_REQUIRED: '完整产品验收仍需在 Windows 上完成。',
  ORIGINAL_OWNER_ADAPTER_REQUIRED: '此操作还需要接入原服务，当前只有接口预留。',
  ORIGINAL_JOB_AND_RECEIPT_REQUIRED: '需要从原任务入口核对运行与结果回执。',
  HUMAN_REVIEW_REQUIRED: '产物仍需人工核对和审核。',
  V2_GRAPH_IMAGE_EXECUTION_NOT_ENABLED: '图片处理尚未接入此创作图。',
  V2_GRAPH_VIDEO_EXECUTION_NOT_ENABLED: '视频生成尚未接入此创作图。',
  V2_GRAPH_AUDIO_OWNER_NOT_CONNECTED: '声音处理尚未接入此创作图。',
  V2_GRAPH_T2I_OWNER_NOT_CONNECTED: '文字生成图片尚未连接执行服务。',
  V2_GRAPH_I2I_OWNER_NOT_CONNECTED: '参考图生成图片尚未连接执行服务。',
  V2_GRAPH_T2V_OWNER_NOT_CONNECTED: '文字生成视频尚未连接执行服务。',
  V2_GRAPH_I2V_OWNER_NOT_CONNECTED: '参考图生成视频尚未连接执行服务。',
  V2_GRAPH_V2V_OWNER_NOT_CONNECTED: '视频转换尚未连接执行服务。',
  MUSIC_GENERATION_OWNER_NOT_CONNECTED: '音乐生成尚未连接执行服务。',
  SOUND_EFFECT_GENERATION_OWNER_NOT_CONNECTED: '音效生成尚未连接执行服务。',
  AUDIO_TRIM_OWNER_NOT_CONNECTED: '音频裁剪尚未连接执行服务。',
  MULTITRACK_NLE_OWNER_NOT_CONNECTED: '真正的多轨剪辑、预览和渲染尚未接入。',
  V2_EDITING_SOURCE_CAS_ADAPTER_REQUIRED: '剪辑操作还需要接入原素材版本校验。',
};

function RequirementList({ title, items }: { title: string; items: string[] }) {
  return <section><h4>{title}</h4>{items.length ? <ul>{items.map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}</ul> : <p>本接口未声明要求；不代表已经满足条件。</p>}</section>;
}
function OperationContract({ operation, schemas }: { operation: StudioProductionOperation; schemas: StudioWorkspaceProductionContracts['interface_schemas'] }) {
  return <article className="studio-production-operation" aria-label={`${operation.title}操作契约`}>
    <header><h3>{operation.title}</h3><Badge tone="warning">{operation.capability_status === 'EXISTING_OWNER_CONTRACT' ? '已有操作 · 使用原入口' : '预留接口 · 尚不可执行'}</Badge></header>
    <p>真实验收待本地完成；本接口不评价验收结果。</p>
    {!operation.owner && <p>当前 V2 接口尚未接入对应执行服务；可核对要求，暂不能从此接口创建或执行任务。</p>}
    <StatusMessage tone="warning">{[...new Set(operation.blocked_reasons.map(reason => BLOCKER_LABELS[reason] ?? '尚有未满足的条件，请核对高级契约。'))].join(' ')}</StatusMessage>
    <div className="studio-production-requirements">
      <RequirementList title="输入" items={operation.input_requirements}/><RequirementList title="来源与版本" items={operation.source_requirements}/>
      <RequirementList title="产物" items={operation.output_requirements}/><RequirementList title="审核" items={operation.review_requirements}/>
    </div>
    <details><summary>核对原服务接口与限制</summary>
      <p>操作标识：<code>{operation.id}</code></p>
      {operation.owner && <dl><div><dt>原有服务</dt><dd>{operation.owner.module} · {operation.owner.class_name}</dd></div><div><dt>原有方法</dt><dd>{operation.owner.methods.join('、') || '未声明'}</dd></div></dl>}
      <p>下列接口为契约描述，不提供执行入口。实际操作仍需原入口、可信会话、权限、版本及输入审核。</p>
      {operation.actions.length ? <ul className="studio-production-actions">{operation.actions.map(action => <li key={action.id}>
        <strong>{action.id}</strong> · <code>{action.method} {action.path}</code>
        <p>权限：{action.permission} · 服务方法：{action.owner_method} · 输入契约：{action.input_schema ?? '未声明'} · {action.requires_original_host_session ? '要求原可信会话' : '会话约束以原入口为准'}。</p>
        <ul>{action.conditions.map((condition, index) => <li key={`${index}:${condition}`}>{condition}</li>)}</ul>
      </li>)}</ul> : <p>尚无原服务动作。</p>}
      <section><h4>预留的结构化接口</h4><p>下列字段约束描述后续适配边界，不是原执行入口接受的输入，也不是创建任务的表单。</p>
        <dl>{(Object.keys(operation.interface_contracts) as (keyof StudioProductionOperation['interface_contracts'])[]).map(key => {
          const reference = operation.interface_contracts[key], schema = schemas[reference], properties = schema.properties;
          return <div key={key}><dt>{({ source_snapshot: '来源快照', intent: '操作意图', result: '产物回执', rights: '许可与授权', timing: '时基与范围', tracks: '轨道约束' })[key]}</dt>
            <dd><code>{reference}</code> · {properties && typeof properties === 'object' && !Array.isArray(properties) ? Object.keys(properties).join('、') : '未声明字段'}</dd></div>;
        })}</dl>
      </section>
      <p>缺项标识：{operation.blocked_reasons.join('、')}</p>
      <RequirementList title="边界与未完成能力" items={operation.limitations}/>
    </details>
  </article>;
}

/** Existing shell consumer. Rendering or switching stages never invokes an operation. */
export function StudioWorkspaceOperationPanel(props: StudioWorkspaceOperationPanelProps) {
  const operation = useStudioWorkspaceOperations(props);
  return <Panel title="制作操作" className="studio-production-contracts" aria-label="Studio 制作操作契约"
    actions={<Button loading={operation.state === 'LOADING'} disabled={!operation.canRead} onClick={() => void operation.reload()}>重新读取操作契约</Button>}>
    <p>核对文字、图片、导演、视频、声音和剪辑的原服务、输入与审核边界。框架准备不代表真实能力通过，执行仍由原服务负责。</p>
    <nav className="studio-production-stages" aria-label="制作阶段">{STUDIO_PRODUCTION_STAGES.map(stage => <Button key={stage}
      aria-current={operation.selectedStage === stage ? 'page' : undefined} disabled={props.denied || operation.state === 'DENIED'}
      variant={operation.selectedStage === stage ? 'primary' : 'secondary'} onClick={() => operation.selectStage(stage)}>{stage} · {STUDIO_PRODUCTION_STAGE_LABELS[stage]}</Button>)}</nav>
    {props.onOpenSurface && <div className="studio-production-stages">
      <Button disabled={props.busy || props.denied || operation.state === 'DENIED'} onClick={() => props.onOpenSurface?.('ASSETS')}>打开素材工作区</Button>
      {operation.selectedStage === 'M4' && <Button disabled={props.busy || props.denied || operation.state === 'DENIED'} onClick={() => props.onOpenSurface?.('GRAPH')}>打开创作图</Button>}
    </div>}
    {operation.state === 'LOADING' && <StatusMessage>正在读取当前项目的制作操作契约…</StatusMessage>}
    {operation.problem && operation.state !== 'DENIED' && <StatusMessage tone="error">{operation.problem.message} · {operation.problem.code}</StatusMessage>}
    {operation.state === 'DENIED' && <EmptyState title="当前会话无权读取制作操作" detail="先前契约已清除。重新核对当前项目、身份和分支后再打开。"/>}
    {operation.state === 'IDLE' && <EmptyState title="尚未读取操作契约" detail="当前操作结束后，可以重新读取；读取不会启动模型或任务。"/>}
    {operation.state === 'UNAVAILABLE' && <EmptyState title="制作操作入口当前不可用" detail="请核对项目是否已通过原入口启用独立 Studio；不会自动启用或重建项目。"/>}
    {(operation.state === 'READY' || operation.state === 'EMPTY') && <>
      <p>验收顺序：{operation.contracts?.acceptance_sequence.join(' → ')}。浏览后续阶段不会跳过真实验收，也不会改变权限。</p>
      {operation.stage.operations.length && operation.contracts ? operation.stage.operations.map(item => <OperationContract key={item.id} operation={item} schemas={operation.contracts!.interface_schemas}/>)
        : <EmptyState title={`${operation.stage.label}尚无已返回契约`} detail="未返回契约不代表能力可用，也不会创建占位任务。"/>}
    </>}
  </Panel>;
}
