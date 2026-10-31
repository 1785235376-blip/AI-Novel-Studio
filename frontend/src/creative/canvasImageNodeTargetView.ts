import { ApiError } from '../api';
import { exactStudioProductionTask } from '../taskcenter/studioProductionTask';
import { assertCanvasImageNodeJob, canvasImageNodeInCommand, canonicalImageNode, verifyCanvasImageNodePrompt } from './canvasImageNode';
import type { CanvasImageNodeTargetSource } from './canvasImageNodeTargetObservation';
import type { StudioImageNodeTargetView, StudioImageNodeTargetViewPin, StudioProductionClient } from './studioProductionClient';

export type CanvasImageNodeTargetView = StudioImageNodeTargetView;
export type CanvasImageNodeTargetViewPin = StudioImageNodeTargetViewPin;
export type CanvasImageNodeTargetViewInput = {
  projectId: string; branchId: string | null;
  client: Pick<StudioProductionClient, 'observeImageNodeTarget' | 'readImageNodeTargetView'>;
  source: CanvasImageNodeTargetSource;
  /** The current-version pin from the still-current, explicitly opened observation snapshot. */
  pin: CanvasImageNodeTargetViewPin;
  read: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>;
  signal?: AbortSignal;
};
function retired(): never {
  throw new ApiError({status:409,code:'STUDIO_CANVAS_NODE_TARGET_VIEW_RETIRED',
    message:'原任务、核对快照或读取入口已经变化；没有改读其他版本。'});
}

/** Read the just-observed pin through its existing owner; never GET/admit/restore a canvas. */
export async function readCanvasImageNodeTargetView(input: CanvasImageNodeTargetViewInput): Promise<CanvasImageNodeTargetView> {
  const selected=structuredClone(input.source.job),key=input.source.key,sourceStamp=canonicalImageNode(input.source.job);
  const pin=structuredClone(input.pin),pinStamp=canonicalImageNode(input.pin),client=input.client,method=client.readImageNodeTargetView;
  const projectId=input.projectId,branchId=input.branchId,controller=new AbortController();
  const abort=()=>controller.abort();input.signal?.addEventListener('abort',abort,{once:true});
  if(input.signal?.aborted)controller.abort();
  const current=()=>{
    if(controller.signal.aborted)throw new DOMException('关联画布只读记录读取已取消。','AbortError');
    if(input.source.key!==key||canonicalImageNode(input.source.job)!==sourceStamp||input.source.isCurrent()!==true
      ||canonicalImageNode(input.pin)!==pinStamp||input.client!==client||client.readImageNodeTargetView!==method
      ||input.projectId!==projectId||input.branchId!==branchId)retired();
  };
  let timer:ReturnType<typeof setTimeout>|undefined,rejectAbort:(()=>void)|undefined;
  const cancelled=new Promise<never>((_resolve,reject)=>{
    rejectAbort=()=>reject(new DOMException('关联画布只读记录读取已取消。','AbortError'));
    controller.signal.addEventListener('abort',rejectAbort,{once:true});if(controller.signal.aborted)rejectAbort();
  });
  const timeout=new Promise<never>((_resolve,reject)=>{
    timer=setTimeout(()=>{reject(new ApiError({status:408,code:'STUDIO_CANVAS_NODE_TARGET_VIEW_TIMEOUT',
      message:'关联画布只读记录读取超时，本次未确认；没有改读其他版本或执行作品操作。'}));controller.abort();},15_000);
  });
  try{
    return await Promise.race([(async()=>{
      current();
      const binding=canvasImageNodeInCommand(selected.command);
      if(!key||!binding||selected.owner!=='image'||selected.novel_id!==projectId||selected.branch_id!==branchId
        ||binding.project_id!==projectId||(binding.scope.mode==='collaboration'?binding.scope.branch_id:null)!==branchId
        ||!pin||Object.keys(pin).length!==3||!['incarnation','version','definition_digest'].every(name=>Object.hasOwn(pin,name))
        ||pin.incarnation!==binding.incarnation||!Number.isSafeInteger(pin.version)||pin.version<binding.canvas_version||pin.version>21
        ||!/^[a-f0-9]{64}$/.test(pin.definition_digest)
        ||pin.version===binding.canvas_version&&pin.definition_digest!==binding.canvas_digest)retired();
      assertCanvasImageNodeJob(binding,selected);
      await verifyCanvasImageNodePrompt(selected.command!);current();
      if(!method)throw new ApiError({status:501,code:'STUDIO_CANVAS_NODE_TARGET_VIEW_UNAVAILABLE',
        message:'当前服务尚不支持关联画布的固定版本只读记录；没有改用其他读取入口。'});
      const result=await input.read(()=>{current();return method.call(client,selected,pin,controller.signal);},controller.signal);
      current();exactStudioProductionTask(result.job,selected,projectId,branchId);
      if(result.contract!=='studio-image-node-target-view/1'||result.automatic_actions!==false
        ||canonicalImageNode(result.target)!==canonicalImageNode(binding)||result.incarnation!==pin.incarnation
        ||result.canvas.id!==binding.canvas_id||result.canvas.project_id!==projectId
        ||canonicalImageNode(result.canvas.scope)!==canonicalImageNode(binding.scope)
        ||result.canvas.version!==pin.version||result.canvas.definition_digest!==pin.definition_digest
        ||result.canvas.execution_authority!==false||result.canvas.binary_content_verified!==false)retired();
      return structuredClone(result);
    })(),timeout,cancelled]);
  }finally{
    if(timer!==undefined)clearTimeout(timer);if(rejectAbort)controller.signal.removeEventListener('abort',rejectAbort);
    controller.abort();input.signal?.removeEventListener('abort',abort);
  }
}
