import { ApiError } from '../api';
import { exactStudioProductionTask, type StudioProductionTask } from '../taskcenter/studioProductionTask';
import { assertCanvasImageNodeJob, canvasImageNodeInCommand, canonicalImageNode, verifyCanvasImageNodePrompt } from './canvasImageNode';
import type { StudioImageNodeTargetObservation, StudioProductionClient } from './studioProductionClient';

/** An ephemeral selector ticket. It grants no creation, execution, save or restore action. */
export type CanvasImageNodeTargetSource = { job: StudioProductionTask; key: string; isCurrent: () => boolean };
export type CanvasImageNodeTargetObservationInput = {
  projectId: string; branchId: string | null;
  client: Pick<StudioProductionClient, 'observeImageNodeTarget'>;
  source: CanvasImageNodeTargetSource;
  read: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>;
  signal?: AbortSignal;
};
export type CanvasImageNodeTargetObservation = StudioImageNodeTargetObservation;

function retired(): never {
  throw new ApiError({ status: 409, code: 'STUDIO_CANVAS_NODE_TARGET_RETIRED',
    message: '原任务选择、项目或读取入口已经变化；未核对其他作品位置。' });
}

/** One existing-owner-only metadata observation. No admission, overview, GET fallback or polling. */
export async function readCanvasImageNodeTarget(input: CanvasImageNodeTargetObservationInput): Promise<CanvasImageNodeTargetObservation> {
  const selected=structuredClone(input.source.job),key=input.source.key,client=input.client,method=client.observeImageNodeTarget;
  const projectId=input.projectId,branchId=input.branchId,sourceStamp=canonicalImageNode(input.source.job);
  const controller=new AbortController();
  const abort=()=>controller.abort();
  input.signal?.addEventListener('abort',abort,{once:true});
  if(input.signal?.aborted)controller.abort();
  const current=()=>{
    if(controller.signal.aborted)throw new DOMException('原作品保存状态读取已取消。','AbortError');
    if(input.source.key!==key||canonicalImageNode(input.source.job)!==sourceStamp||!input.source.isCurrent()
      ||input.client!==client||client.observeImageNodeTarget!==method||input.projectId!==projectId||input.branchId!==branchId)retired();
  };
  let timer:ReturnType<typeof setTimeout>|undefined,rejectAbort:(()=>void)|undefined;
  const cancelled=new Promise<never>((_resolve,reject)=>{
    rejectAbort=()=>reject(new DOMException('原作品保存状态读取已取消。','AbortError'));
    controller.signal.addEventListener('abort',rejectAbort,{once:true});
    if(controller.signal.aborted)rejectAbort();
  });
  const timeout=new Promise<never>((_resolve,reject)=>{
    timer=setTimeout(()=>{reject(new ApiError({status:408,code:'STUDIO_CANVAS_NODE_TARGET_TIMEOUT',
      message:'原作品保存状态读取超时，本次未确认；没有发起任何作品或任务操作。'}));controller.abort();},15_000);
  });
  try {
    return await Promise.race([(async()=>{
      current();
      const binding=canvasImageNodeInCommand(selected.command);
      if(!key||!binding||selected.owner!=='image'||selected.novel_id!==projectId||selected.branch_id!==branchId
        ||binding.project_id!==projectId||(binding.scope.mode==='collaboration'?binding.scope.branch_id:null)!==branchId)retired();
      assertCanvasImageNodeJob(binding,selected);
      await verifyCanvasImageNodePrompt(selected.command!);current();
      if(!method)throw new ApiError({status:501,code:'STUDIO_CANVAS_NODE_TARGET_UNAVAILABLE',
        message:'当前服务尚不支持只读核对原作品保存状态；没有使用其他读取或恢复入口替代。'});
      const result=await input.read(()=>{current();return method.call(client,selected,controller.signal);},controller.signal);
      current();
      exactStudioProductionTask(result.job,selected,projectId,branchId);
      if(canonicalImageNode(result.target)!==canonicalImageNode(binding)||result.incarnation!==binding.incarnation
        ||result.automatic_actions!==false)retired();
      return structuredClone(result);
    })(),timeout,cancelled]);
  }finally{
    if(timer!==undefined)clearTimeout(timer);
    if(rejectAbort)controller.signal.removeEventListener('abort',rejectAbort);
    controller.abort();input.signal?.removeEventListener('abort',abort);
  }
}
