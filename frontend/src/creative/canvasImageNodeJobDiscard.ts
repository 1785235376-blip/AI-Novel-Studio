import { ApiError } from '../api';
import { assertCanvasImageNodeJob, canvasImageNodeInCommand, canonicalImageNode, checkedCanvasImageNodeBinding, verifyCanvasImageNodePrompt } from './canvasImageNode';
import type { CanvasImageNodeTargetSource } from './canvasImageNodeTargetObservation';
import { checkedImageNodeJobProjection, checkedStudioImageNodeJobDiscard, studioImageNodeJobProjection,
  type StudioImageNodeJobDiscard, type StudioImageNodeJobObservation, type StudioProductionClient } from './studioProductionClient';

export const CANVAS_IMAGE_NODE_JOB_DISCARD_NOT_SENT='STUDIO_CANVAS_NODE_JOB_DISCARD_NOT_SENT';
export type CanvasImageNodeJobDiscardOutcome =
  | {state:'CONFIRMED';receipt:StudioImageNodeJobDiscard}
  | {state:'UNKNOWN';code:'STUDIO_CANVAS_NODE_JOB_DISCARD_UNKNOWN'|'STUDIO_CANVAS_NODE_JOB_DISCARD_BOUNDARY_UNVERIFIED';message:string}
  | {state:'BLOCKED';code:'STUDIO_CANVAS_NODE_JOB_DISCARD_CLAIMED';message:string};
export type CanvasImageNodeJobDiscardInput = {
  projectId:string;branchId:string|null;
  client:Pick<StudioProductionClient,'observeImageNodeJob'|'discardImageNodeJob'>;
  source:CanvasImageNodeTargetSource;
  observation:StudioImageNodeJobObservation;
  mutate:<T>(work:()=>Promise<T>,signal?:AbortSignal)=>Promise<T>;
  /** The current source, permission, accepted observation and confirmation serial, excluding claim membership. */
  isCurrent:()=>boolean;
  confirmed:()=>boolean;
  /** Workspace-owned ephemeral Set keyed by project/incarnation/Job/version/request digest, not panel key. */
  claim:()=>boolean;
  signal?:AbortSignal;
};

/** Eligibility is not authority or confirmation; no read or mutation occurs here. */
export function canDiscardCanvasImageNodeJob(observation:StudioImageNodeJobObservation|undefined):boolean {
  try{
    if(!observation||Object.keys(observation).length!==6
      ||!['contract','job','target','incarnation','canvas_read','automatic_actions'].every(key=>Object.hasOwn(observation,key))
      ||observation.contract!=='studio-image-node-job-observation/1'||observation.canvas_read!==false||observation.automatic_actions!==false)return false;
    const job=checkedImageNodeJobProjection(observation.job),target=checkedCanvasImageNodeBinding(observation.target);
    return job.status==='QUEUED'&&job.attempt===0&&job.output_candidate===null&&job.receipt_digest===null
      &&job.approved_asset_version===null&&job.version<Number.MAX_SAFE_INTEGER&&target.project_id===job.novel_id
      &&(target.scope.mode==='collaboration'?target.scope.branch_id:null)===job.branch_id&&observation.incarnation===target.incarnation
      &&canonicalImageNode(canvasImageNodeInCommand(job.command))===canonicalImageNode(target);
  }catch{return false;}
}
function notSent():never {
  throw new ApiError({status:409,code:CANVAS_IMAGE_NODE_JOB_DISCARD_NOT_SENT,
    message:'本次放弃操作未发送。请重新读取原任务并确认当前范围、权限与本次操作。'});
}

/** One explicit original-owner discard. No retry, durable marker, Canvas read or remote-stop claim. */
export async function discardCanvasImageNodeJob(input:CanvasImageNodeJobDiscardInput):Promise<CanvasImageNodeJobDiscardOutcome> {
  const controller=new AbortController(),externalSignal=input.signal,abort=()=>controller.abort();
  let timer:ReturnType<typeof setTimeout>|undefined,rejectAbort:(()=>void)|undefined;
  let invoked=false,sent=false,hookCalls=0,claimAttempted=false,blocked=false;
  const claim=input.claim;
  const reserveUnknown=()=>{
    // This records a potential invocation, not proof of HTTP dispatch or successful cancellation.
    if(!claimAttempted){claimAttempted=true;try{claim();}catch{/* The outcome remains unknown. */}}
  };
  try{
    externalSignal?.addEventListener('abort',abort,{once:true});if(externalSignal?.aborted)controller.abort();
    const source=input.source,selected=structuredClone(source.job),key=source.key,sourceStamp=canonicalImageNode(source.job),sourceCurrent=source.isCurrent;
    const accepted=input.observation,observation=structuredClone(accepted),observationStamp=canonicalImageNode(accepted);
    const projectId=input.projectId,branchId=input.branchId,client=input.client,method=client.discardImageNodeJob,
      observeMethod=client.observeImageNodeJob,mutate=input.mutate,isCurrent=input.isCurrent,confirmed=input.confirmed;
    const current=()=>{
      if(controller.signal.aborted)throw new DOMException('原任务放弃操作已取消等待。','AbortError');
      if(input.source!==source||input.source.key!==key||input.source.isCurrent!==sourceCurrent||sourceCurrent()!==true
        ||canonicalImageNode(input.source.job)!==sourceStamp||input.observation!==accepted||canonicalImageNode(input.observation)!==observationStamp
        ||input.projectId!==projectId||input.branchId!==branchId||input.client!==client||client.discardImageNodeJob!==method
        ||client.observeImageNodeJob!==observeMethod||input.mutate!==mutate||input.isCurrent!==isCurrent||isCurrent()!==true
        ||input.confirmed!==confirmed||input.claim!==claim||input.signal!==externalSignal)notSent();
    };
    const confirmation=()=>{if(confirmed()!==true)notSent();};
    const cancelled=new Promise<never>((_resolve,reject)=>{
      rejectAbort=()=>reject(new DOMException('原任务放弃操作已取消等待。','AbortError'));
      controller.signal.addEventListener('abort',rejectAbort,{once:true});if(controller.signal.aborted)rejectAbort();
    });
    const timeout=new Promise<never>((_resolve,reject)=>{
      timer=setTimeout(()=>{reject(new ApiError({status:408,code:'STUDIO_CANVAS_NODE_JOB_DISCARD_TIMEOUT',
        message:'放弃操作的等待已超时，本次未取得可核对回执。'}));controller.abort();},15_000);
    });
    return await Promise.race([(async():Promise<CanvasImageNodeJobDiscardOutcome>=>{
      current();confirmation();
      const target=canvasImageNodeInCommand(selected.command),projection=studioImageNodeJobProjection(selected);
      if(!key||!target||selected.owner!=='image'||selected.novel_id!==projectId||selected.branch_id!==branchId
        ||target.project_id!==projectId||(target.scope.mode==='collaboration'?target.scope.branch_id:null)!==branchId
        ||!canDiscardCanvasImageNodeJob(observation)||canonicalImageNode(observation.job)!==canonicalImageNode(projection)
        ||canonicalImageNode(observation.target)!==canonicalImageNode(target)||observation.incarnation!==target.incarnation)notSent();
      assertCanvasImageNodeJob(target,selected);
      await verifyCanvasImageNodePrompt(selected.command!);current();confirmation();
      if(!method)notSent();
      const beforeDispatch=()=>{
        hookCalls++;if(hookCalls!==1)notSent();
        current();confirmation();
        claimAttempted=true;
        if(claim()!==true){blocked=true;throw new ApiError({status:409,code:'STUDIO_CANVAS_NODE_JOB_DISCARD_CLAIMED',
          message:'同一任务快照已有操作登记；没有再次发送，请从原任务列表读取核对。'});}
        sent=true;
      };
      const receipt=await mutate(()=>{
        current();confirmation();if(invoked)notSent();
        invoked=true;
        // The Host's write guard must also finish when an embedded method ignores abort.
        return Promise.race([method.call(client,selected,controller.signal,beforeDispatch),timeout,cancelled]);
      },controller.signal);
      current();confirmation();
      if(!invoked||hookCalls!==1||!sent)notSent();
      const verified=checkedStudioImageNodeJobDiscard(receipt,projection);
      return {state:'CONFIRMED',receipt:verified};
    })(),timeout,cancelled]);
  }catch(error){
    if(blocked)return {state:'BLOCKED',code:'STUDIO_CANVAS_NODE_JOB_DISCARD_CLAIMED',
      message:'同一任务快照已有操作登记，不能再次确认或发送。请从原任务列表读取同一任务的新版本核对。'};
    if(invoked){
      reserveUnknown();
      return {state:'UNKNOWN',code:sent&&hookCalls===1?'STUDIO_CANVAS_NODE_JOB_DISCARD_UNKNOWN':'STUDIO_CANVAS_NODE_JOB_DISCARD_BOUNDARY_UNVERIFIED',
        message:'本次是否已提交或完成尚未确认，不能再次发送。请从原任务列表重新读取同一任务核对；未确认远端计算已停止。'};
    }
    throw new ApiError({status:error instanceof ApiError?error.status:409,code:CANVAS_IMAGE_NODE_JOB_DISCARD_NOT_SENT,
      message:'本次放弃操作未发送。请重新读取原任务并确认当前范围、权限与本次操作。'});
  }finally{
    // Settle the inner Host-work race before detaching the shared abort listener.
    controller.abort();
    if(timer!==undefined)clearTimeout(timer);if(rejectAbort)controller.signal.removeEventListener('abort',rejectAbort);
    externalSignal?.removeEventListener('abort',abort);
  }
}
