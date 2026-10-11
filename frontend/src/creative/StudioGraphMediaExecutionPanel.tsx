import { Badge, Button, StatusMessage } from '../ui/primitives';
import { MEDIA_OPERATION_LABELS, MEDIA_STATUS_LABELS } from './useStudioMediaExecution';
import { useStudioGraphMediaExecution, type StudioGraphMediaExecutionProps } from './useStudioGraphMediaExecution';

export type { GraphMediaAction, GraphMediaActionEvidence, StudioGraphMediaExecutionProps } from './useStudioGraphMediaExecution';

/** Replaceable presentation. Exact receipts, one-send reservations and private media lifetime remain in the headless controller. */
export function StudioGraphMediaExecutionPanel(props: StudioGraphMediaExecutionProps) {
  const state = useStudioGraphMediaExecution(props), preview = state.preview, execution = state.execution, job = state.job;
  const approved = state.run && !state.run.stale ? Object.entries(state.run.node_states).flatMap(([nodeId, node]) =>
    node.status === 'SUCCEEDED' && props.graph?.definition.nodes.some(value => value.id === nodeId && value.definition_id === 'media_review') && node.output?.asset
      ? [{ nodeId, asset: node.output.asset }] : []) : [];
  return <section className="studio-graph-model" aria-label="图媒体执行与审核">
    <h3>图媒体执行与审核</h3>
    <p>媒体节点使用已保存图的提示词、参数与来源版本。预览、仅入队、执行和审核分别确认；人工审核后才可作为下游素材。不会自动调用、轮询、重试或转到其他服务。</p>
    <p>本机能力与完整流程验收：待完成（LOCAL_REQUIRED）。</p>
    {state.error && <StatusMessage tone="error">{state.error}</StatusMessage>}
    {(state.uncertain || execution?.receipt_state === 'UNKNOWN_NO_AUTOMATIC_REPLAY') && <StatusMessage tone="warning">回执不确定，先读取原运行核对。相同任务和版本不会自动重发。</StatusMessage>}
    {!state.run && <p>先保存图并创建运行；创建运行不会调用媒体服务。</p>}
    {!!approved.length && <section aria-label="图中已审核入库素材"><h4>已审核入库素材</h4><ul>{approved.map(({ nodeId, asset }) => <li key={nodeId}>{nodeId} · {asset.asset_id} · v{asset.version} · {asset.kind}<details><summary>素材内容摘要</summary><code>{asset.digest}</code></details></li>)}</ul><p>可在原素材库中核对这些记录；图不会自动启动下游任务。</p></section>}
    {state.run && !state.nodes.length && <p>当前运行没有媒体节点，保留原文字节点流程。</p>}
    {!!state.nodes.length && <>
      <label>媒体节点<select value={state.selectedId} disabled={state.locked} onChange={event => state.chooseNode(event.target.value)}>
        {state.nodes.map(node => <option key={node.node_id} value={node.node_id}>{node.node_id} · {node.status}</option>)}
      </select></label>
      <div className="studio-graph-actions"><Button disabled={!state.canRead} loading={state.pendingKind === 'get'} onClick={() => void state.action('get')}>读取原运行核对</Button>
        <Button disabled={!state.canPreview} loading={state.pendingKind === 'preview'} onClick={() => void state.action('preview')}>预览当前媒体节点</Button></div>
      {state.node?.status === 'PENDING' && <p>先明确执行前置节点，到达媒体边界后再预览。</p>}
      {preview && <section aria-label="图媒体预览确认">
        <Badge tone="info">预览尚未调用媒体服务</Badge>
        <p>{MEDIA_OPERATION_LABELS[preview.command.operation_id]} · {preview.production_preview.provider
          ? `${preview.production_preview.provider.provider_id} / ${preview.production_preview.provider.model_id} · ${preview.production_preview.provider.local ? '本地' : '云端'}` : '本地处理'}</p>
        <details><summary>核对完整提示词、参数与来源</summary><pre>{JSON.stringify(preview.command, null, 2)}</pre></details>
        <details><summary>核对执行接口和工作流</summary><pre>{JSON.stringify(preview.production_preview.execution_recipe, null, 2)}</pre></details>
        {!execution && <><label><input type="checkbox" checked={state.previewReviewed} disabled={!state.canConfirm} onChange={event => state.confirmPreview(event.target.checked)} />已核对本次输入、来源版本、处理边界与服务配置</label>
          <Button disabled={!state.canDispatch} loading={state.pendingKind === 'dispatch'} onClick={() => void state.action('dispatch')}>仅入队当前媒体节点</Button></>}
      </section>}
      {execution && <section aria-label="图媒体任务回执">
        <Badge>{job ? MEDIA_STATUS_LABELS[job.status] : execution.status}</Badge>
        <p>原任务：{execution.job_id || '任务入队回执待核对'}{job ? ` · v${job.version}` : ''}</p>
        <p>回执：{execution.receipt_state} · {execution.send_reserved ? '已记录执行意图' : '尚未记录执行意图'}</p>
        {job?.error_code && <StatusMessage tone="warning">{job.error_code}</StatusMessage>}
        {job?.remote_compute_may_continue && <StatusMessage tone="warning">远端计算可能仍在继续。本地丢弃不代表远端服务已停止。</StatusMessage>}
        <div className="studio-graph-actions">
          <Button variant="primary" disabled={!state.canExecute} loading={state.pendingKind === 'execute'} onClick={() => void state.action('execute')}>明确执行该原任务一次</Button>
          <Button disabled={!state.canRefresh} loading={state.pendingKind === 'refresh'} onClick={() => void state.action('refresh')}>核对已知原任务结果</Button>
          <Button disabled={!state.canReconcile} loading={state.pendingKind === 'reconcile'} onClick={() => void state.action('reconcile')}>记录中断状态并核对</Button>
          <Button variant="danger" disabled={!state.canCancel} loading={state.pendingKind === 'cancel'} onClick={() => void state.action('cancel')}>取消当前运行并丢弃本地候选</Button>
        </div>
        {job?.output_candidate && <section aria-label="图媒体候选审核">
          <p>候选：{job.output_candidate.id} · v{job.output_candidate.version} · {job.output_candidate.kind}</p>
          <Button disabled={!state.canCandidate} loading={state.pendingKind === 'candidate'} onClick={() => void state.loadCandidate()}>读取候选并核对内容摘要</Button>
          {state.candidate && <>
            {state.candidate.kind === 'image' && <img src={state.candidate.url} alt="当前图媒体任务的私有候选" style={{ maxWidth: '100%', maxHeight: 'var(--layout-inspector-width)' }} />}
            {state.candidate.kind === 'video' && <video controls preload="metadata" src={state.candidate.url} style={{ maxWidth: '100%' }} />}
            {state.candidate.kind === 'audio' && <audio controls preload="metadata" src={state.candidate.url} />}
            <label><input type="checkbox" checked={state.outputReviewed} disabled={state.reviewDisabled || !state.reviewCurrent} onChange={event => state.confirmReview(event.target.checked)} />已查看该候选，并核对当前来源版本与审核结果</label>
            <Button variant="primary" disabled={!state.canReview} loading={state.pendingKind === 'review'} onClick={() => void state.action('review')}>审核入库并完成媒体审核节点</Button>
            <Button variant="danger" disabled={!state.canReject} loading={state.pendingKind === 'reject'} onClick={() => void state.action('reject')}>明确拒绝该候选并终止运行</Button>
          </>}
          {!state.reviewNodeId && <StatusMessage tone="warning">对应审核节点或图版本不可用，请先读取当前图与运行。</StatusMessage>}
        </section>}
        {job?.approved_asset_version && <p>已审核素材版本：v{job.approved_asset_version}。下游仍需核对当前版本，不自动执行。</p>}
      </section>}
    </>}
  </section>;
}
