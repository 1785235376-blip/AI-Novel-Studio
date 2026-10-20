import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { StudioCanvasImageTaskPanel } from './StudioCanvasImageTaskPanel';
import type { CanvasImageTaskOrigin, CanvasImageTaskSession } from './canvasImageTask';
import type { StudioGraphEditorProps } from './useStudioGraphEditorController';
import type { StudioAsset } from './studioClient';
import type { ProductionJob, StudioProductionClient } from './studioProductionClient';
import type { StudioProductionLeaveGuard } from './studioProductionLeaveRisk';
export type StudioDualCanvasTaskProps={productionTaskSource?:StudioProductionClient;productionTaskLeaveGuard?:StudioProductionLeaveGuard;
  onCanvasTaskApproved?:(job:ProductionJob)=>void|Promise<void>;onCanvasTaskUnavailable?:()=>void};
type Mode='CREATION'|'EXECUTION'|'COMPARE';
/** Presentation and session intent only; original owners keep all persistence and execution. */
export function useStudioDualCanvasTask(props:StudioGraphEditorProps&StudioDualCanvasTaskProps){
  const [mode,setMode]=useState<Mode>(props.client.graphs?.canvasViews&&!props.requestedGraphId?'CREATION':'EXECUTION');
  const [task,setTask]=useState<CanvasImageTaskSession>(),[approved,setApproved]=useState<ProductionJob>(),[taskDirty,setTaskDirty]=useState(false),[graphExecution,setGraphExecution]=useState(false);
  const live=useRef(props),taskRef=useRef(task),taskOwner=useRef<object>(),dirtyRef=useRef(taskDirty),alive=useRef(true);live.current=props;taskRef.current=task;dirtyRef.current=taskDirty;
  const values=[props.identity,props.client,props.productionTaskSource,props.active,props.denied,props.canMutate,props.canReview,JSON.stringify(props.draftOwner)],fence=useRef({values,token:{}});
  if(values.some((v,i)=>!Object.is(v,fence.current.values[i])))fence.current={values,token:{}};
  const token=fence.current.token,current=()=>alive.current&&token===fence.current.token&&live.current.active&&!live.current.denied&&live.current.isCurrent();
  useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  function begin(origin:CanvasImageTaskOrigin,asset:StudioAsset,isOriginCurrent:()=>boolean,resumeJob?:ProductionJob){
    if(!current()||!props.productionTaskSource||dirtyRef.current||!props.canMutate||props.busy||props.externalDirty||!isOriginCurrent())return;
    const id=crypto.randomUUID();const next:CanvasImageTaskSession={id,origin,asset,resumeJob,isOriginCurrent:()=>current()&&taskRef.current===next&&isOriginCurrent()};
    taskOwner.current=token;taskRef.current=next;setTask(next);setApproved(resumeJob?.status==='APPROVED'?resumeJob:undefined);setGraphExecution(false);setMode(resumeJob?.status==='APPROVED'?'CREATION':'EXECUTION');
  }
  const returned=()=>{if(current()){taskOwner.current=undefined;taskRef.current=undefined;dirtyRef.current=false;setTask(undefined);setApproved(undefined);setTaskDirty(false);setMode('CREATION');}};
  function frame(creation:ReactNode,sharedExecution:ReactNode,inspector:ReactNode,blocked:boolean){
    const taskCurrent=()=>current()&&taskOwner.current===token&&taskRef.current===task;
    const visibleTask=taskCurrent()?task:undefined;
    const taskContent=visibleTask&&props.productionTaskSource&&<StudioCanvasImageTaskPanel key={visibleTask.id} task={visibleTask} client={props.productionTaskSource} provenanceAssets={props.client}
      leaveGuard={props.productionTaskLeaveGuard} canMutate={props.canMutate&&!blocked} canReview={props.canReview&&!blocked} busy={props.busy} isBusy={props.isBusy}
      isCurrent={taskCurrent} read={props.read} mutate={props.mutate} onUnavailable={()=>props.onCanvasTaskUnavailable?.()}
      onDirtyChange={dirty=>{if(taskCurrent()){dirtyRef.current=dirty;setTaskDirty(dirty);}}}
      onApproved={async job=>{if(!taskCurrent())return;setApproved(job);setMode('CREATION');await live.current.onCanvasTaskApproved?.(job);}}/>;
    return {content:<section aria-label="Studio 双画布" style={{height:'100%',minHeight:0,minWidth:0,display:'grid',gridTemplateRows:'auto minmax(0,1fr)',gap:'var(--space-3)'}}>
      <Panel title="创作与执行"><div className="creative-actions">
        <Button aria-pressed={mode==='CREATION'} onClick={()=>setMode('CREATION')}>创作画布</Button>
        <Button aria-pressed={mode==='EXECUTION'} onClick={()=>setMode('EXECUTION')}>执行画布</Button>
        <Button aria-pressed={mode==='COMPARE'} onClick={()=>setMode('COMPARE')}>对照分屏</Button>
        <Button onClick={()=>{setGraphExecution(true);setMode('EXECUTION');}}>原执行图与模板入口</Button>
        {task&&graphExecution&&<Button onClick={()=>{setGraphExecution(false);setMode('EXECUTION');}}>返回所选卡片任务</Button>}
      </div><p>默认组织创作素材和作品位置；从已保存卡片创建任务后进入真实执行流程。只有“对照分屏”同时展开两层。</p>
      {graphExecution&&<StatusMessage>这里是原执行图草稿与模板入口。保存会形成原图的新版本，影响之后按该版本创建的运行；现有运行和共享模板仍按原发布入口管理。卡片任务参数不会写回这里。</StatusMessage>}</Panel>
      <div aria-label={mode==='COMPARE'?'双画布对照':'当前画布'} style={{minHeight:0,minWidth:0,display:'grid',gridTemplateRows:mode==='COMPARE'?'repeat(2,minmax(0,1fr))':'minmax(0,1fr)',gap:'var(--space-3)'}}>
        <div aria-label="创作层显示区" hidden={mode==='EXECUTION'} style={{minHeight:0,minWidth:0,overflow:'auto'}}>{creation}</div>
        <div aria-label="执行层显示区" hidden={mode==='CREATION'} style={{minHeight:0,minWidth:0,overflow:'auto'}}><div hidden={!task||graphExecution}>{taskContent}{task&&!visibleTask&&<StatusMessage tone="warning">原任务范围或权限已改变，任务不会重新发送。请返回创作画布核对；原请求仍按任务记录处理。</StatusMessage>}</div><div hidden={!!task&&!graphExecution}>{sharedExecution}</div></div>
      </div>
    </section>,inspector:mode!=='CREATION'&&(!task||graphExecution)?inspector:<Panel title="创作画布与任务位置"><p>{visibleTask?`所选任务固定返回卡片 ${visibleTask.origin.cardId}。审核和采用分别确认，其他卡片不受影响。`:'先组织并保存素材卡片，再选择一张图片进入单次任务。原素材、位置与创作关系独立于执行图。'}</p></Panel>};
  }
  function discard(){props.productionTaskLeaveGuard?.capture();taskOwner.current=undefined;taskRef.current=undefined;dirtyRef.current=false;setTask(undefined);setApproved(undefined);setTaskDirty(false);setGraphExecution(false);setMode('CREATION');}
  return {task,approved,taskDirty,begin,returned,frame,discard};
}
