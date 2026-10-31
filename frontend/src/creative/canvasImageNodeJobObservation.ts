import { ApiError } from '../api';
import { assertCanvasImageNodeJob, canvasImageNodeInCommand, canonicalImageNode, verifyCanvasImageNodePrompt } from './canvasImageNode';
import type { CanvasImageNodeTargetSource } from './canvasImageNodeTargetObservation';
import { studioImageNodeJobProjection, type StudioImageNodeJobObservation, type StudioProductionClient } from './studioProductionClient';

export type CanvasImageNodeJobObservation = StudioImageNodeJobObservation;
export type CanvasImageNodeJobObservationInput = {
  projectId: string; branchId: string | null;
  client: Pick<StudioProductionClient, 'observeImageNodeJob'>;
  source: CanvasImageNodeTargetSource;
  read: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>;
  signal?: AbortSignal;
};
function retired(): never {
  throw new ApiError({status:409,code:'STUDIO_CANVAS_NODE_JOB_OBSERVATION_RETIRED',
    message:'原任务选择、项目或读取入口已经变化；没有改读其他任务或作品。'});
}

/** Read one fixed Job projection; never reads/adopts its historical Canvas or a result asset. */
export async function readCanvasImageNodeJobObservation(input: CanvasImageNodeJobObservationInput): Promise<CanvasImageNodeJobObservation> {
  const selected=structuredClone(input.source.job),key=input.source.key,sourceStamp=canonicalImageNode(input.source.job);
  const projectId=input.projectId,branchId=input.branchId,client=input.client,method=client.observeImageNodeJob,read=input.read;
  const controller=new AbortController(),abort=()=>controller.abort();
  input.signal?.addEventListener('abort',abort,{once:true});if(input.signal?.aborted)controller.abort();
  const current=()=>{
    if(controller.signal.aborted)throw new DOMException('原图片节点任务元数据读取已取消。','AbortError');
    if(input.source.key!==key||canonicalImageNode(input.source.job)!==sourceStamp||input.source.isCurrent()!==true
      ||input.projectId!==projectId||input.branchId!==branchId||input.client!==client
      ||client.observeImageNodeJob!==method||input.read!==read)retired();
  };
  let timer:ReturnType<typeof setTimeout>|undefined,rejectAbort:(()=>void)|undefined;
  const cancelled=new Promise<never>((_resolve,reject)=>{
    rejectAbort=()=>reject(new DOMException('原图片节点任务元数据读取已取消。','AbortError'));
    controller.signal.addEventListener('abort',rejectAbort,{once:true});if(controller.signal.aborted)rejectAbort();
  });
  const timeout=new Promise<never>((_resolve,reject)=>{
    timer=setTimeout(()=>{reject(new ApiError({status:408,code:'STUDIO_CANVAS_NODE_JOB_OBSERVATION_TIMEOUT',
      message:'原任务元数据读取超时，本次未确认；没有读取画布、重新派发或执行任务操作。'}));controller.abort();},15_000);
  });
  try{
    return await Promise.race([(async()=>{
      current();
      const target=canvasImageNodeInCommand(selected.command);
      if(!key||!target||selected.owner!=='image'||selected.novel_id!==projectId||selected.branch_id!==branchId
        ||target.project_id!==projectId||(target.scope.mode==='collaboration'?target.scope.branch_id:null)!==branchId)retired();
      assertCanvasImageNodeJob(target,selected);
      const projection=studioImageNodeJobProjection(selected);
      await verifyCanvasImageNodePrompt(selected.command!);current();
      if(!method)throw new ApiError({status:501,code:'STUDIO_CANVAS_NODE_JOB_OBSERVATION_UNAVAILABLE',
        message:'当前服务尚不支持原任务的独立元数据核对；没有使用画布或其他任务读取入口替代。'});
      const result=await read(()=>{current();return method.call(client,selected,controller.signal);},controller.signal);
      current();
      if(Object.keys(result).length!==6
        ||!['contract','job','target','incarnation','canvas_read','automatic_actions'].every(name=>Object.hasOwn(result,name))
        ||result.contract!=='studio-image-node-job-observation/1'||result.canvas_read!==false||result.automatic_actions!==false
        ||canonicalImageNode(result.job)!==canonicalImageNode(projection)||canonicalImageNode(result.target)!==canonicalImageNode(target)
        ||result.incarnation!==target.incarnation)retired();
      const observation:CanvasImageNodeJobObservation={contract:'studio-image-node-job-observation/1',job:projection,target,
        incarnation:target.incarnation,canvas_read:false,automatic_actions:false};
      return structuredClone(observation);
    })(),timeout,cancelled]);
  }finally{
    if(timer!==undefined)clearTimeout(timer);if(rejectAbort)controller.signal.removeEventListener('abort',rejectAbort);
    controller.abort();input.signal?.removeEventListener('abort',abort);
  }
}
