import { Fragment } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../../ui/primitives';
import { MEDIA_STATUS_LABELS } from '../../creative/useStudioMediaExecution';
import { useExecutionProvenance, type ExecutionProvenanceProps } from './useExecutionProvenance';
import { isExecutionIdentifier } from './executionProvenanceModel';

export type { ExecutionProvenanceProps } from './useExecutionProvenance';
const fields = { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 3fr)', gap: 'var(--space-2)', margin: 0 } as const;
const value = { minWidth: 0, margin: 0 };
const digest = (hash: unknown) => typeof hash === 'string' && /^[a-f0-9]{64}$/.test(hash);

/** Detail slot for original standalone Job receipts; graph projections are not this contract. */
export function ExecutionProvenancePanel(props: ExecutionProvenanceProps) {
  const state = useExecutionProvenance(props), view = state.view, job = view?.execution;
  const origin = props.origin, recorded = job?.canvasReturn;
  const matchingOrigin = job && origin && origin.projectId === props.selection.projectId
    && isExecutionIdentifier(origin.canvasId) && isExecutionIdentifier(origin.cardId) && Number.isSafeInteger(origin.canvasVersion) && origin.canvasVersion > 0
    && digest(origin.canvasDigest) && origin.source.kind === 'image' && isExecutionIdentifier(origin.source.asset_id)
    && Number.isSafeInteger(origin.source.version) && origin.source.version > 0 && digest(origin.source.digest)
    && job.sources.some(source => source.kind === 'ASSET' && source.id === origin.source.asset_id
      && source.version === origin.source.version && source.digest === origin.source.digest);
  return <Panel title="执行来源与失败恢复" aria-label="执行来源与失败恢复"
    style={{ minWidth: 0, maxWidth: '100%', overflowWrap: 'anywhere' }}
    actions={<Button disabled={state.blocked || state.pending} loading={state.pending} onClick={() => void state.load()}>
      {job ? '重新读取执行来源' : '读取执行来源'}
    </Button>}>
    <p>只读取当前范围的原 Job 与可读资产。单次任务记录与共享工作流模板分开；本面板不修改模板或触发生成。</p>
    {state.pending && <StatusMessage>正在读取原任务来源…</StatusMessage>}
    {view?.error && <StatusMessage tone="error">{view.error}</StatusMessage>}
    {(!props.active || props.denied || !props.isCurrent()) && <StatusMessage tone="warning">当前项目或身份不可用，先前来源已隐藏。</StatusMessage>}
    {!job && !view?.error && !state.pending && !state.blocked && <EmptyState title="尚未读取执行来源" detail="请明确读取原任务。没有来源字段时会保留缺失，不从配方、素材声明或模拟状态补全。" />}
    {job && <>
      <p><Badge tone={job.status === 'UNKNOWN' || job.status === 'FAILED' ? 'warning' : 'info'}>{MEDIA_STATUS_LABELS[job.status]}</Badge> <code>{job.status}</code></p>
      <dl style={fields}>
        <dt>原 Job ID</dt><dd style={value}><code>{job.jobId}</code></dd>
        <dt>原 request ID</dt><dd style={value}><code>{job.requestId}</code></dd>
        <dt>当前读取版本</dt><dd style={value}>v{job.version} · 所选记录 v{props.selection.job.version}</dd>
        <dt>原操作</dt><dd style={value}><code>{job.operationId}</code></dd>
        <dt>请求摘要</dt><dd style={value}><code>{job.requestDigest}</code></dd>
        <dt>回执摘要</dt><dd style={value}><code>{job.receiptDigest ?? '未记录'}</code></dd>
        <dt>原错误代码</dt><dd style={value}><code>{job.errorCode ?? '未提供可显示的错误代码'}</code></dd>
      </dl>
      {job.version !== props.selection.job.version && <StatusMessage tone="warning">原 Job 版本已变化。这里展示本次读取的版本，不沿用旧执行、审核或采用确认。</StatusMessage>}
      <h3>服务与执行参数</h3>
      <p>{job.executionKind}</p>
      {job.provider ? <dl style={fields}>
        <dt>Provider</dt><dd style={value}><code>{job.provider.providerId}</code></dd>
        <dt>Model</dt><dd style={value}><code>{job.provider.modelId}</code></dd>
        <dt>路由摘要</dt><dd style={value}><code>{job.provider.routeDigest}</code></dd>
      </dl> : <p>原回执未提供可显示的服务/模型身份，或该字段已隐藏。</p>}
      {job.parameters.length ? <dl aria-label="记录的执行参数" style={fields}>{job.parameters.map(parameter => <Fragment key={parameter.name}>
        <dt><code>{parameter.name}</code></dt><dd style={value}>{parameter.value}</dd>
      </Fragment>)}</dl> : <p>未记录可显示的执行参数。</p>}
      <p>仅显示原请求的安全数值和枚举参数；提示词、凭据、URL 和原始错误内容不在诊断中展开。未填写的参数不会补成默认值。</p>
      <h3>执行时输入快照</h3>
      {!job.sources.length && <p>未记录输入快照，不代表不存在其他依赖。</p>}
      <ul aria-label="执行时输入快照">{job.sources.map((source, index) => <li key={index}>
        <code>{source.kind} · {source.id}</code> · v{source.version}<p>记录摘要 <code>{source.digest}</code></p>
      </li>)}</ul>
      <p>这些是执行时的 id/version/digest；当前资产可能已变化，本面板不会用新版本替代旧快照。</p>
      <h3>候选、正式资产与作品采用</h3>
      {job.candidate ? <p>原候选 <code>{job.candidate.id}</code> · 候选 v{job.candidate.version} · <code>{job.candidate.digest}</code></p>
        : <p>未记录输出候选。</p>}
      {job.approvedAssetVersion ? <p>原 Job 记录的正式审核版本 v{job.approvedAssetVersion}。{view?.assetNote}</p>
        : <StatusMessage tone="warning">没有可核验的正式审核版本。候选不能当作已审核资产或已采用成果。</StatusMessage>}
      {view?.approved && <p>已核验正式资产 <code>{view.approved.id}</code> · v{view.approved.version} · <code>{view.approved.digest}</code></p>}
      <p>采用到作品：未提供持久的采用回执，不能据“审核入库”推断已经回填卡片。</p>
      <h3>原作品锚点</h3>
      {recorded ? <>
        <p>原 Job 已持久记录位置绑定：画布 <code>{recorded.canvas_id}</code> · v{recorded.canvas_version} · <code>{recorded.canvas_digest}</code>；卡片 <code>{recorded.card_id}</code>。</p>
        <p>原输入资产 <code>{recorded.source.id}</code> · v{recorded.source.version} · <code>{recorded.source.digest}</code>。</p>
        <p>存储代际 <code>{recorded.incarnation}</code>。绑定记录保留创建时的位置与源版本；当前权限、画布 CAS、卡片和源 pin 必须在原回流入口重新核验。</p>
        <StatusMessage tone="warning">持久绑定不代表已回填，也不授权重放或自动采用。画布或源版本发生变化时，保留候选并阻断旧位置回流。</StatusMessage>
      </> : matchingOrigin && origin ? <>
        <p>宿主提供的本会话捕获：画布 <code>{origin.canvasId}</code> · v{origin.canvasVersion} · <code>{origin.canvasDigest}</code>；卡片 <code>{origin.cardId}</code>。</p>
        <p>原采用资产 <code>{origin.source.asset_id}</code> · v{origin.source.version} · <code>{origin.source.digest}</code>。</p>
        <StatusMessage tone="warning">{props.isOriginCurrent?.() ? '宿主确认原会话锚点仍有效。' : '原会话锚点已变化或当前有效性未核验。'}原 Job 没有持久 canvas/card origin，跨会话不能恢复此位置；不会根据相同输入资产猜位置。</StatusMessage>
      </> : <p>没有与本次任务输入匹配的会话锚点。原 Job 未记录持久 canvas/card origin，不能定位或猜测作品位置。</p>}
      <h3>恢复诊断</h3>
      <StatusMessage tone="warning">{job.recoveryReason}</StatusMessage>
      {job.remoteComputeMayContinue && <StatusMessage tone="warning">原 owner 提示远端计算可能仍在继续；本地状态不代表远端已经停止。</StatusMessage>}
      <p>重新读取只调用原 GET。此处没有失败重试、重放、审核或采用动作；需要恢复时在原入口核对状态和支持的操作。</p>
    </>}
  </Panel>;
}
