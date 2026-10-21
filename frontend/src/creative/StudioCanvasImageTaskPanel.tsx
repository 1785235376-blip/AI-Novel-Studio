import { StudioCanvasVideoTaskPanel } from './StudioCanvasVideoTaskPanel';
import { useMemo, useState } from 'react';
import { Badge, Button, Panel } from '../ui/primitives';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { StudioExecutionRecipePanel } from './StudioExecutionRecipePanel';
import { canvasAudioTrimTaskSource } from './canvasAudioTrimTask';
import { canvasImageTaskSource, type CanvasImageTaskSession } from './canvasImageTask';
import type { StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { ProductionJob } from './studioProductionClient';
import type { StudioClient, StudioAsset } from './studioClient';
import { ExecutionProvenancePanel } from '../experimental/executionProvenance/ExecutionProvenancePanel';

export function StudioCanvasImageTaskPanel({task,provenanceAssets,taskAssets,onReadTaskAssets,...props}:Omit<StudioMediaExecutionProps,'assets'|'canvasImageTask'|'canvasAudioTrimTask'|'onJob'>&{task:CanvasImageTaskSession;provenanceAssets?:Pick<StudioClient,'asset'>;taskAssets?:StudioAsset[];onReadTaskAssets?:()=>void}) {
  const [job,setJob]=useState<ProductionJob|undefined>(task.resumeJob);
  const audio=task.asset.kind==='audio';
  const binding=useMemo(()=>task.asset.kind==='video'?undefined:({source:(audio?canvasAudioTrimTaskSource:canvasImageTaskSource)(task.origin.source),returnBinding:task.origin.binding,isCurrent:task.isOriginCurrent}),[task]);
  if(task.asset.kind==='video')return <StudioCanvasVideoTaskPanel key={task.id} {...props} task={task} provenanceAssets={provenanceAssets}/>;
  return <section aria-label="所选卡片的执行画布">
    <Panel title={audio?"本次音频截取任务 · 影响范围":"本次图像任务 · 影响范围"}>
      <p><Badge>单次任务草稿</Badge> 原位置 <code>{task.origin.canvasId}</code> · v{task.origin.canvasVersion} · 卡片 <code>{task.origin.cardId}</code></p>
      <p>只使用原{audio?'音频':'图片'} <code>{task.origin.source.asset_id}</code> · v{task.origin.source.version}。本次最多产生 1 个候选；预览、入队、实际执行和审核仍分别明确确认。</p>
      <p>下面参数只写入本次原 Job，不修改原执行图或共享工作流模板。创作关系不转换成执行节点。审核入库后，还需核验并明确采用到上述卡片；坐标和分组保留，其他作品位置不变。</p>
      {audio?<p>本次支持起止毫秒范围、增益与线性淡入淡出，使用原本地 FFmpeg 输出 PCM16 WAV（48000 Hz、双声道），最长 120 秒。不会调用 TTS 或模型；真实时长、采样率、声道和字节以执行后测量为准。</p>:<p>本次可明确选择原本地 Comfy SD 图生图，或明确选择本地 CPU 二值遮罩抠图／双层 PNG 合成。CPU 路径不调用模型、不做自动语义分割；原图与另一个输入的确切版本分别核对。合成仅支持同尺寸图片在原点对齐，可调层顺序、显隐和透明度，不支持位移或缩放。云接口内部不可见步骤保持不可见。</p>}
    </Panel>
    {!audio&&onReadTaskAssets&&<Button disabled={props.busy||!props.isCurrent()} onClick={onReadTaskAssets}>读取原图与当前图片素材版本</Button>}
    <StudioMediaExecutionPanel {...props} {...(audio?{canvasAudioTrimTask:binding}:{canvasImageTask:binding})} assets={audio?[task.asset]:taskAssets??[task.asset]} externalJob={task.resumeJob} onJob={setJob}/>
    {job&&<ExecutionProvenancePanel selection={{projectId:task.origin.projectId,branchId:job.branch_id,identity:task.id,job:{owner:job.owner,id:job.id,version:job.version,request_id:job.request_id,request_digest:job.request_digest}}}
      production={props.client} assets={provenanceAssets} active={props.isCurrent()&&task.isOriginCurrent()} denied={false}
      busy={props.busy} isCurrent={()=>props.isCurrent()&&task.isOriginCurrent()} read={props.read}
      origin={task.origin} isOriginCurrent={task.isOriginCurrent} onUnavailable={props.onUnavailable}/>}
    {job&&<StudioExecutionRecipePanel recipe={job.execution_recipe} operationId={job.operation_id} current={props.isCurrent()}/>}
  </section>;
}
