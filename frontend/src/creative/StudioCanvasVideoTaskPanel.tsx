import {CanvasVideoFailedRecoveryPanel} from './videoTaskRecovery';
import {canvasVideoTrimTaskSource} from './canvasVideoTrimTask';
import {CanvasVideoAudioControls} from './CanvasVideoAudioControls';
import {Badge,Button,Panel,StatusMessage} from '../ui/primitives';
import {ExecutionImpactPanel} from '../experimental/executionImpact/ExecutionImpactPanel';
import {ExecutionProvenancePanel} from '../experimental/executionProvenance/ExecutionProvenancePanel';
import {StudioExecutionRecipePanel} from './StudioExecutionRecipePanel';
import {useStudioCanvasVideoTask,type StudioCanvasVideoTaskProps} from './useStudioCanvasVideoTask';

export function StudioCanvasVideoTaskPanel(props:StudioCanvasVideoTaskProps){
  const state=useStudioCanvasVideoTask(props),job=state.selected,impact=state.impact,candidate=state.candidate;
  return <section aria-label="所选卡片的执行画布">
    <Panel title="本次视频截取任务 · 影响范围">
      <p><Badge>单次任务草稿</Badge> 原位置 <code>{props.task.origin.canvasId}</code> · v{props.task.origin.canvasVersion} · 卡片 <code>{props.task.origin.cardId}</code></p>
      <p>只使用原视频 <code>{props.task.origin.source.asset_id}</code> · v{props.task.origin.source.version}，最多产生 1 个候选。应用配置只保存原时间线；预览、入队、实际执行、审核与原卡片采用分别明确确认。</p>
      <p>只修改本次任务，不修改共享工作流模板，也不把创作关系转换成执行节点。</p>
      <StatusMessage>使用原本地 FFmpeg 重新编码为 640×360、25fps H.264 MP4；默认输出静音音轨；明确保留源音轨时，截取原第一条音轨并重新编码为 AAC。无可用源音轨时拒绝执行。起止时间以 40ms 为步长，最长 120 秒。不会调用生成模型；费用、运行时长及资源估算未知。</StatusMessage>
    </Panel>
    <Panel title="视频截取配置" className="studio-graph-run">
      {state.error&&<StatusMessage tone="error">{state.error}</StatusMessage>}
      {state.notice&&<StatusMessage>{state.notice}</StatusMessage>}
      {!state.current()&&<StatusMessage tone="warning">原卡片、范围、来源或权限已改变，请返回创作画布重新核对。旧确认不会恢复。</StatusMessage>}
      {state.uncertain&&<StatusMessage tone="warning">操作结果尚未确认，已阻止继续发送。请读取原任务记录；不会自动重试或采用。</StatusMessage>}
      {state.derivedFrom&&<p>本次派生来源：<code>{state.derivedFrom.job_id}</code> · v{state.derivedFrom.job_version}。保留原请求与参数记录，本次配置另存独立时间线。</p>}
      <fieldset disabled={!state.canEdit}><legend>本次原视频范围</legend>
        <label>来源起点（毫秒）<input type="number" min={0} step={40} value={state.draft.in_ms} onChange={event=>state.changeParameter('in_ms',event.target.value)}/></label>
        <label>来源终点（毫秒）<input type="number" min={40} step={40} value={state.draft.out_ms} onChange={event=>state.changeParameter('out_ms',event.target.value)}/></label>
      </fieldset>
      <CanvasVideoAudioControls value={state.draft.include_audio===true} disabled={!state.canEdit} isCurrent={state.current} onChange={state.changeAudio}/>
      <div className="creative-actions">
        <Button disabled={!state.canUndo} onClick={state.undo}>撤销截取修改</Button><Button disabled={!state.canRedo} onClick={state.redo}>重做截取修改</Button>
        <Button disabled={!state.canApply} loading={state.pending==='SAVE'} onClick={()=>void state.apply()}>应用截取配置</Button>
        <Button disabled={!state.canInspect} loading={state.pending==='PREVIEW'} onClick={()=>void state.inspect()}>读取视频截取预览</Button>
      </div>
      {state.timeline&&<p>本次原时间线 <code>{state.timeline.id}</code> · v{state.timeline.version}；保存和重开仍使用原版本与摘要。</p>}
      {state.preview&&<section aria-label="视频截取预览确认"><p>输入摘要 <code>{state.preview.request_digest}</code></p>
        {!state.preview.execution_available&&<StatusMessage tone="warning">当前执行能力不可用，不能入队或执行。</StatusMessage>}
        <label><input type="checkbox" checked={state.previewConfirmed} disabled={state.locked||!state.current()} onChange={event=>state.confirmPreview(event.target.checked)}/>已核对本次视频范围、来源和重新编码边界</label>
      </section>}
      {impact&&<ExecutionImpactPanel input={impact.input} owner={impact} current={impact.current()} canConfirm={props.canMutate&&state.previewConfirmed}
        busy={state.locked} isCurrent={impact.current} onConfirm={proof=>void state.confirmImpact(impact,proof)}/>}
      <div className="creative-actions">
        <Button disabled={!state.canCreate} loading={state.pending==='QUEUE'} onClick={()=>void state.create()}>仅创建视频任务并入队</Button>
        <Button disabled={!state.canExecute} loading={state.pending==='EXECUTE'} onClick={()=>void state.execute()}>明确执行本次视频截取</Button>
        <Button disabled={state.locked||!state.current()} loading={state.pending==='GET'} onClick={()=>void state.readJob()}>读取原视频任务与配置</Button>
      </div>
      {job&&<section aria-label="原视频任务回执"><p>原 Job <code>{job.id}</code> · v{job.version} · {job.status}</p>
        <p>请求 <code>{job.request_id}</code>。重新读取不会执行、审核或采用；UNKNOWN、失败和已完成任务不会从这里重放。</p>
        {job.status==='QUEUED'&&<p>执行前请再次读取原截取预览并核对本次输入。</p>}
        {['FAILED','UNKNOWN'].includes(job.status)&&<CanvasVideoFailedRecoveryPanel job={job} task={{source:canvasVideoTrimTaskSource(props.task.origin.source),returnBinding:props.task.origin.binding,isCurrent:state.current}}
          owner={props.client} current={state.current()} busy={state.locked||state.uncertain} canMutate={props.canMutate} isCurrent={state.current}
          newRequestId={()=>crypto.randomUUID()} onDerive={state.prepareFailedVideo} onRead={state.readJob}/>}
        {['FAILED','UNKNOWN','RUNNING','REVIEWING','CANCELLED'].includes(job.status)&&<StatusMessage tone="warning">当前状态不能继续执行或重试，请通过原记录核对。</StatusMessage>}
        {job.media_measurement&&<p>实际输出：{job.media_measurement.duration_ms} 毫秒 · {job.media_measurement.width}×{job.media_measurement.height} · {job.media_measurement.fps} fps · {job.media_measurement.byte_count} 字节。</p>}
        {['SUCCEEDED','AWAITING_REVIEW'].includes(job.status)&&<Button disabled={state.locked||state.uncertain||!state.current()} onClick={()=>void state.loadCandidate()}>读取并核对候选视频</Button>}
      </section>}
      {candidate&&<section aria-label="视频候选人工审核"><video controls playsInline src={candidate.url} style={{maxWidth:'100%'}} onLoadedData={event=>state.mediaLoaded(candidate,event.currentTarget)} onError={()=>state.mediaFailed(candidate)}/>
        {!state.candidateReady&&<StatusMessage>等待浏览器解码本次候选画面；尺寸与时长通过原任务测量核对后才能明确审核。</StatusMessage>}
        <label><input type="checkbox" checked={state.reviewConfirmed} disabled={state.locked||!props.canReview||!state.candidateReady} onChange={event=>state.confirmReview(event.target.checked)}/>已查看本次视频候选，确认审核当前 Job 版本与输出摘要</label>
        <Button disabled={!state.canReview} loading={state.pending==='REVIEW'} onClick={()=>void state.review()}>明确审核视频并入素材库</Button>
      </section>}
    </Panel>
    {job&&<ExecutionProvenancePanel selection={{projectId:props.task.origin.projectId,branchId:job.branch_id,identity:props.task.id,
      job:{owner:job.owner,id:job.id,version:job.version,request_id:job.request_id,request_digest:job.request_digest}}}
      production={props.client} assets={props.provenanceAssets} active={props.isCurrent()&&props.task.isOriginCurrent()} denied={false} busy={props.busy}
      isCurrent={()=>props.isCurrent()&&props.task.isOriginCurrent()} read={props.read} origin={props.task.origin} isOriginCurrent={props.task.isOriginCurrent} onUnavailable={props.onUnavailable}/>}
    {job&&<StudioExecutionRecipePanel recipe={job.execution_recipe} operationId={job.operation_id} current={props.isCurrent()&&props.task.isOriginCurrent()}/>}
  </section>;
}
