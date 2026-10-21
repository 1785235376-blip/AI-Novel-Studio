import {deriveFailedCanvasVideoDraft,type FailedCanvasVideoDraft,type FailedCanvasVideoOrigin} from './videoTaskRecovery';
import {useLayoutEffect,useRef,useState} from 'react';
import {ApiError,apiErrorView} from '../api';
import {canonicalExecutionImpact,type ExecutionImpactConfirmation} from '../experimental/executionImpact/executionImpact';
import {studioExecutionImpactGate,type StudioExecutionImpactGate,type StudioExecutionImpactInput} from './studioExecutionImpactGate';
import {useStudioProductionLeaveRisk} from './studioProductionLeaveRisk';
import {checkedCanvasVideoTaskCommand,checkedCanvasVideoTaskJob,checkedCanvasVideoTaskPreview,compileCanvasVideoTimeline,
  canvasVideoTrimTaskSource,type CanvasVideoTaskCommand,type CanvasVideoTaskPreview} from './canvasVideoTrimTask';
import type {CanvasImageTaskSession} from './canvasImageTask';
import type {StudioMediaExecutionProps} from './useStudioMediaExecution';
import type {ProductionJob,StudioProductionClient} from './studioProductionClient';
import type {StudioClient} from './studioClient';

export type StudioCanvasVideoTaskProps=Omit<StudioMediaExecutionProps,'assets'|'canvasImageTask'|'canvasAudioTrimTask'|'onJob'>&{
  task:CanvasImageTaskSession;provenanceAssets?:Pick<StudioClient,'asset'>;onJob?:(job:ProductionJob)=>void;
};
type Timeline=Awaited<ReturnType<StudioProductionClient['timelineGet']>>;
type Draft={in_ms:string;out_ms:string;include_audio?:boolean};
type Candidate={url:string;identity:string;generation:object;token:object};
type Operation={token:object;revision:number;client:StudioProductionClient;kind:string};
const canonical=canonicalExecutionImpact;
const identity=(job?:ProductionJob)=>job?canonical([job.owner,job.id,job.version,job.request_digest,job.output_candidate]):'';
const uncertainFailure=(error:unknown)=>!(error instanceof ApiError)||error.status===0||error.status>=500||[408,409,425,429].includes(error.status)||error.problem.code==='STUDIO_RESPONSE_INVALID';
const retired=()=>new ApiError({status:422,code:'STUDIO_EXECUTION_IMPACT_RETIRED',message:'本次输入核对已失效或已使用，请重新读取预览并明确确认；没有再次派发。'});
const invalid=(message:string)=>new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message});

/** Session presentation over the original Timeline/Job owners; no transport or queue lives here. */
export function useStudioCanvasVideoTask(props:StudioCanvasVideoTaskProps){
  const initial=props.task.resumeJob?.canvas_video?.parameters;
  const [draft,setDraft]=useState<Draft>({in_ms:String(initial?.in_ms??0),out_ms:String(initial?.out_ms??1000),...(initial?.include_audio===undefined?{}:{include_audio:initial.include_audio})});
  const [timeline,setTimeline]=useState<Timeline>(),[preview,setPreview]=useState<CanvasVideoTaskPreview>();
  const [selected,setSelected]=useState<ProductionJob|undefined>(props.task.resumeJob),[pending,setPending]=useState<string>();
  const [candidate,setCandidate]=useState<Candidate>(),[candidateReady,setCandidateReady]=useState(false),[previewConfirmed,setPreviewConfirmed]=useState(false),[reviewConfirmed,setReviewConfirmed]=useState(false);
  const [derivedFrom,setDerivedFrom]=useState<FailedCanvasVideoOrigin|undefined>(props.task.resumeJob?.canvas_video?.derived_from);
  const derivedOrigin=useRef(derivedFrom),derivedRequest=useRef<string>(),derivedParent=useRef<ProductionJob>();
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[uncertain,setUncertain]=useState(false),[,refresh]=useState(0);
  const latest=useRef(props);latest.current=props;
  const alive=useRef(true),draftRef=useRef(draft),timelineRef=useRef(timeline),previewRef=useRef(preview),jobRef=useRef(selected),candidateRef=useRef(candidate),decodedCandidate=useRef<object>();
  const revision=useRef(0),slot=useRef<Operation>(),impactRef=useRef<StudioExecutionImpactGate>(),uncertainRef=useRef(false);
  const previewConsent=useRef(false),reviewConsent=useRef(false),savedDraft=useRef(''),request=useRef<string>(),attempt=useRef<{command:CanvasVideoTaskCommand;digest:string}>();
  const history=useRef<{past:Draft[];future:Draft[]}>({past:[],future:[]}),sent=useRef(new Set<string>());
  const assetStamp=()=>canonical({origin:latest.current.task.origin,asset:latest.current.task.asset});
  const methods=()=>[latest.current.client.canvasVideoPreview,latest.current.client.canvasVideoQueue,latest.current.client.canvasVideoExecute,
    latest.current.client.timelineSave,latest.current.client.timelineGet,latest.current.client.get,latest.current.client.review,latest.current.client.candidate,latest.current.client.timelineList,latest.current.client.list];
  const stamp=assetStamp(),values=[props.client,props.task,props.canMutate,props.canReview,stamp,...methods()];
  const fence=useRef({values,token:{},stamp,retired:false});
  if(values.some((value,index)=>!Object.is(value,fence.current.values[index]))){
    impactRef.current?.retire();impactRef.current=undefined;previewRef.current=undefined;previewConsent.current=false;
    candidateRef.current=undefined;decodedCandidate.current=undefined;reviewConsent.current=false;savedDraft.current='';
    fence.current={values,token:{},stamp,retired:false};
  }
  const generation=fence.current,token=generation.token;
  function current(){
    if(generation.retired)return false;
    try{
      if(!alive.current||fence.current!==generation||!latest.current.isCurrent()||!latest.current.task.isOriginCurrent()
        ||assetStamp()!==generation.stamp||latest.current.client!==generation.values[0]||latest.current.task!==generation.values[1]
        ||latest.current.canMutate!==generation.values[2]||latest.current.canReview!==generation.values[3]
        ||methods().some((method,index)=>method!==generation.values[index+5]))generation.retired=true;
    }catch{generation.retired=true;}
    return !generation.retired;
  }
  useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;impactRef.current?.retire();};},[]);
  useLayoutEffect(()=>()=>{if(candidate?.url)URL.revokeObjectURL(candidate.url);},[candidate?.url]);
  const busy=()=>!!slot.current||latest.current.busy||!!latest.current.isBusy?.();
  function clearCandidate(){candidateRef.current=undefined;decodedCandidate.current=undefined;setCandidate(undefined);setCandidateReady(false);reviewConsent.current=false;setReviewConfirmed(false);}
  function clearPreview(){impactRef.current?.retire();impactRef.current=undefined;previewRef.current=undefined;setPreview(undefined);previewConsent.current=false;setPreviewConfirmed(false);}
  function markUncertain(value:boolean){uncertainRef.current=value;setUncertain(value);if(value)clearPreview();}
  const leaveGuard=useStudioProductionLeaveRisk(props.leaveGuard,()=>({unknown:uncertainRef.current||jobRef.current?.status==='UNKNOWN'||!!slot.current&&['QUEUE','EXECUTE','REVIEW'].includes(slot.current.kind),
    requests:jobRef.current?[{requestId:jobRef.current.request_id,owner:'timeline',operationId:'m9.timeline.multitrack'}]:attempt.current?[{requestId:attempt.current.command.request_id,owner:'timeline',operationId:'m9.timeline.multitrack'}]:[]}));
  function fail(reason:unknown,fallback:string,sentMutation=false){
    if(reason instanceof ApiError&&[401,403,404,410].includes(reason.status)){
      leaveGuard?.capture();generation.retired=true;clearPreview();clearCandidate();latest.current.onUnavailable();
    }
    setError(apiErrorView(reason,fallback).message);
    if(sentMutation&&uncertainFailure(reason))markUncertain(true);
  }
  function begin(kind:string){if(!current()||busy())return;const value={token,revision:revision.current,client:latest.current.client,kind};slot.current=value;setPending(kind);setError('');setNotice('');return value;}
  const live=(value:Operation)=>current()&&slot.current===value&&value.token===token&&value.client===latest.current.client&&value.revision===revision.current;
  function finish(value:Operation){if(slot.current===value){slot.current=undefined;if(alive.current)setPending(undefined);}}
  function dirty(value:boolean){latest.current.onDirtyChange(value);}
  function edit(next:Draft,record=true){
    if(!current()||busy()||!latest.current.canMutate||jobRef.current||uncertainRef.current)return;
    if(canonical(next)===canonical(draftRef.current))return;
    if(record){history.current.past.push({...draftRef.current});history.current.past=history.current.past.slice(-20);history.current.future=[];}
    revision.current++;draftRef.current=next;setDraft(next);clearPreview();clearCandidate();request.current=undefined;dirty(true);
  }
  function changeParameter(name:'in_ms'|'out_ms',value:string){edit({...draftRef.current,[name]:value});}
  function changeAudio(value:boolean){if(typeof value==='boolean')edit({...draftRef.current,include_audio:value});}
  const editable=()=>current()&&!busy()&&latest.current.canMutate&&!jobRef.current&&!uncertainRef.current;
  function undo(){if(!editable())return;const next=history.current.past.pop();if(!next)return;history.current.future.push({...draftRef.current});edit(next,false);}
  function redo(){if(!editable())return;const next=history.current.future.pop();if(!next)return;history.current.past.push({...draftRef.current});edit(next,false);}
  function parameters(){
    if(!draftRef.current.in_ms.trim()||!draftRef.current.out_ms.trim())throw new Error('请填写明确的整数毫秒起止时间。');
    return {in_ms:Number(draftRef.current.in_ms),out_ms:Number(draftRef.current.out_ms),
      ...(draftRef.current.include_audio===undefined?{}:{include_audio:draftRef.current.include_audio})};
  }
  function command():CanvasVideoTaskCommand{
    const row=timelineRef.current,binding=latest.current.task.origin.binding;
    if(!row||!binding||savedDraft.current!==canonical(draftRef.current)||!request.current)throw new Error('请先明确应用当前截取配置。');
    return checkedCanvasVideoTaskCommand({contract:'studio-canvas-video-trim/1',operation_id:'m9.timeline.multitrack',request_id:request.current,
      provider_id:null,model_id:null,prompt:'',allow_cloud:false,license_note:'',parameters:parameters(),
      source_snapshots:[canvasVideoTrimTaskSource(latest.current.task.origin.source)],canvas_return:binding,
      timeline_snapshot:{id:row.id,version:row.version,digest:row.timeline_digest},...(derivedOrigin.current?{derived_from:derivedOrigin.current}:{})});
  }
  function checkedJob(value:unknown){
    const row=checkedCanvasVideoTaskJob(value);
    if(canonical(row.canvas_video.canvas_return)!==canonical(latest.current.task.origin.binding))throw invalid('任务的持久原位置不属于当前卡片。');
    return row;
  }
  function adoptJob(job:ProductionJob){jobRef.current=job;setSelected(job);latest.current.onJob?.(job);clearCandidate();}
  function input():StudioExecutionImpactInput|undefined{
    const value=previewRef.current;if(!value)return;
    const job=jobRef.current,binding=value.command.canvas_return;
    try{
      if(canonical(value.command)!==canonical(command()))return;
      if(job&&(job.status!=='QUEUED'||job.request_digest!==value.request_digest||canonical(checkedJob(job).canvas_video)!==canonical(value.command)
        ||canonical(job.execution_recipe)!==canonical(value.execution_recipe)))return;
      return {scope:{novel_id:binding.project_id,branch_id:binding.scope.mode==='collaboration'?binding.scope.branch_id??null:null,incarnation:binding.incarnation},
        command:value.command,recipe:value.execution_recipe,...(job?{previousJob:job}:derivedParent.current?{previousJob:derivedParent.current}:{}),editScope:'TASK',
        boundary:job?{kind:'EXECUTE',job:{id:job.id,owner:job.owner,version:job.version,request_digest:job.request_digest}}:{kind:'CREATE'},preview:value};
    }catch{return;}
  }
  function prepareImpact(){
    impactRef.current?.retire();const value=input();if(!value){impactRef.current=undefined;return;}
    const capturedRevision=revision.current;
    impactRef.current=studioExecutionImpactGate(value,input,()=>current()&&revision.current===capturedRevision&&latest.current.canMutate&&!uncertainRef.current);
  }
  async function confirmImpact(gate:StudioExecutionImpactGate,proof:ExecutionImpactConfirmation){
    if(impactRef.current!==gate||busy())return;if(await gate.confirm(proof)){if(impactRef.current===gate)refresh(v=>v+1);}
  }
  function confirmPreview(checked:boolean){if(!current()||busy())return;previewConsent.current=checked;setPreviewConfirmed(checked);if(!checked){clearPreview();}}
  function prepareFailedVideo(value:FailedCanvasVideoDraft){
    const job=jobRef.current;
    if(!current()||busy()||!latest.current.canMutate||uncertainRef.current||!job||job.status!=='FAILED')return;
    checkedJob(job);
    const expected=deriveFailedCanvasVideoDraft(job,{source:canvasVideoTrimTaskSource(latest.current.task.origin.source),
      returnBinding:latest.current.task.origin.binding,isCurrent:current},value.request_id);
    if(canonical(value)!==canonical(expected))throw invalid('派生来源或新草稿已改变，请重新核对原失败记录。');
    const next:Draft={in_ms:String(expected.parameters.in_ms),out_ms:String(expected.parameters.out_ms),
      ...(expected.parameters.include_audio===undefined?{}:{include_audio:expected.parameters.include_audio})};
    revision.current++;clearPreview();clearCandidate();
    derivedOrigin.current=structuredClone(expected.derived_from);setDerivedFrom(derivedOrigin.current);
    derivedRequest.current=expected.request_id;derivedParent.current=structuredClone(job);
    request.current=undefined;attempt.current=undefined;savedDraft.current='';history.current={past:[],future:[]};
    timelineRef.current=undefined;setTimeline(undefined);jobRef.current=undefined;setSelected(undefined);
    draftRef.current=next;setDraft(next);dirty(true);
    setNotice('已准备新身份的视频派生草稿；请明确应用到独立时间线，再预览、确认入队和确认执行。原失败任务保持不变。');
  }
  async function listDrafts():Promise<Timeline[]>{
    if(!current()||busy()||uncertainRef.current)throw retired();
    const value=begin('DRAFT_LIST');if(!value)throw retired();
    try{
      const result=await latest.current.read(async()=>{
        if(!live(value))throw retired();const rows=await value.client.timelineList();if(!live(value))throw retired();
        const jobs=await value.client.list();if(!live(value))throw retired();
        return rows.items.filter(row=>{
          const c=row.canvas_video_draft;
          return c?.derived_from&&c.timeline_snapshot.version===row.version&&c.timeline_snapshot.digest===row.timeline_digest
            &&canonical(c.canvas_return)===canonical(latest.current.task.origin.binding)
            &&canonical(c.source_snapshots[0])===canonical(canvasVideoTrimTaskSource(latest.current.task.origin.source))
            &&!jobs.some(job=>job.request_id===c.request_id);
        });
      });
      if(!live(value))throw retired();return result;
    }finally{finish(value);}
  }
  async function resumeDraft(listed:Timeline){
    if(!current()||busy()||!latest.current.canMutate||uncertainRef.current||jobRef.current&&jobRef.current.status!=='FAILED')throw retired();
    if(!jobRef.current&&(revision.current>0||timelineRef.current||derivedOrigin.current))throw invalid('当前已有本次任务草稿；请保留当前输入，不会被另一个草稿覆盖。');
    const expected=structuredClone(listed);
    const value=begin('DRAFT_RESUME');if(!value)throw retired();
    try{
      const result=await latest.current.read(async()=>{
        if(!live(value))throw retired();const row=await value.client.timelineGet(expected.id);if(!live(value))throw retired();
        if(canonical(row)!==canonical(expected))throw invalid('所选草稿版本或输入已改变，请重新读取列表。');
        const c=row.canvas_video_draft;
        if(!c?.derived_from||c.timeline_snapshot.id!==row.id||c.timeline_snapshot.version!==row.version||c.timeline_snapshot.digest!==row.timeline_digest
          ||canonical(c.canvas_return)!==canonical(latest.current.task.origin.binding)
          ||canonical(row.timeline)!==canonical(compileCanvasVideoTimeline(c.source_snapshots[0],c.parameters)))throw retired();
        const parent=checkedJob(await value.client.get('timeline',c.derived_from.job_id));if(!live(value))throw retired();
        const original=deriveFailedCanvasVideoDraft(parent,{source:canvasVideoTrimTaskSource(latest.current.task.origin.source),returnBinding:latest.current.task.origin.binding,isCurrent:current},c.request_id);
        if(canonical(original.derived_from)!==canonical(c.derived_from))throw invalid('原失败来源已改变，保留草稿但不能恢复派发。');
        const jobs=await value.client.list();if(!live(value))throw retired();
        if(jobs.some(job=>job.request_id===c.request_id))throw invalid('该请求已有原 Job；请读取原任务，不会作为未入队草稿再次发送。');
        return {row,command:c,parent};
      });
      if(!live(value))throw retired();const c=result.command;
      revision.current++;clearPreview();clearCandidate();
      const next:Draft={in_ms:String(c.parameters.in_ms),out_ms:String(c.parameters.out_ms),...(c.parameters.include_audio===undefined?{}:{include_audio:c.parameters.include_audio})};
      draftRef.current=next;setDraft(next);timelineRef.current=result.row;setTimeline(result.row);savedDraft.current=canonical(next);
      request.current=c.request_id;derivedRequest.current=c.request_id;derivedOrigin.current=c.derived_from;setDerivedFrom(c.derived_from);derivedParent.current=structuredClone(result.parent);
      jobRef.current=undefined;setSelected(undefined);attempt.current=undefined;history.current={past:[],future:[]};markUncertain(false);dirty(false);
      setNotice('已恢复原 Timeline 版本中的输入草稿；没有恢复旧授权，仍需重新预览并分别确认入队和执行。');
    }finally{finish(value);}
  }
  async function apply(){
    if(!latest.current.canMutate||jobRef.current||uncertainRef.current)return;const value=begin('SAVE');if(!value)return;
    let sentMutation=false;
    try{
      const compiled=compileCanvasVideoTimeline(canvasVideoTrimTaskSource(latest.current.task.origin.source),parameters());
      const old=timelineRef.current;
      const metadata=derivedOrigin.current?{contract:'studio-canvas-video-draft/1' as const,request_id:derivedRequest.current!,parameters:parameters(),source_snapshots:[canvasVideoTrimTaskSource(latest.current.task.origin.source)] as [ReturnType<typeof canvasVideoTrimTaskSource>],canvas_return:latest.current.task.origin.binding! as CanvasVideoTaskCommand['canvas_return'],derived_from:derivedOrigin.current}:undefined;
      const row=await latest.current.mutate(()=>{if(!live(value))throw retired();sentMutation=true;return value.client.timelineSave(old?.id,{title:'本次视频卡片截取',timeline:compiled,expected_version:old?.version??0,...(metadata?{canvas_video_draft:metadata}:{})});});
      if(!live(value))return;if(canonical(row.timeline)!==canonical(compiled))throw invalid('原时间线保存回执与截取配置不一致。');
      timelineRef.current=row;setTimeline(row);savedDraft.current=canonical(draftRef.current);request.current=derivedRequest.current??crypto.randomUUID();clearPreview();history.current={past:[],future:[]};dirty(false);setNotice('已应用到本次原时间线版本；尚未创建或执行 Job。');
    }catch(reason){if(live(value))fail(reason,'本次配置保存未确认，请读取原记录核对。',sentMutation);}finally{finish(value);}
  }
  async function inspect(){
    if(!latest.current.canMutate||uncertainRef.current||jobRef.current&&jobRef.current.status!=='QUEUED')return;
    const value=begin('PREVIEW');if(!value)return;clearPreview();
    try{
      const requested=command();
      const row=await latest.current.read(()=>{if(!live(value))throw retired();return value.client.canvasVideoPreview(requested);});
      if(!live(value))return;
      const checked=checkedCanvasVideoTaskPreview(row,requested),job=jobRef.current;
      if(job&&(job.request_digest!==checked.request_digest||canonical(job.execution_recipe)!==canonical(checked.execution_recipe)))throw invalid('原入队任务与重新读取的预览不一致。');
      previewRef.current=checked;setPreview(checked);prepareImpact();setNotice('已读取原截取预览，仍须核对本次输入并明确确认。');
    }catch(reason){if(live(value))fail(reason,'本次截取预览读取失败。');}finally{finish(value);}
  }
  async function dispatch(kind:'CREATE'|'EXECUTE'){
    if(!current()||!latest.current.canMutate||uncertainRef.current||!previewConsent.current)return;
    const gate=impactRef.current,preview=previewRef.current,job=jobRef.current;
    if(!gate||gate.input.boundary.kind!==kind||!gate.ready()||!preview?.execution_available||kind==='CREATE'&&job||kind==='EXECUTE'&&job?.status!=='QUEUED')return;
    const key=kind==='CREATE'?canonical([kind,preview.command.request_id,preview.request_digest]):canonical([kind,identity(job)]);
    if(sent.current.has(key))return;const value=begin(kind==='CREATE'?'QUEUE':'EXECUTE');if(!value)return;
    let sentMutation=false;const originalIdentity=identity(job);
    try{
      const row=await latest.current.mutate(()=>{
        if(!live(value)||impactRef.current!==gate||identity(jobRef.current)!==originalIdentity||gate.input.boundary.kind!==kind||!gate.consume())throw retired();
        sent.current.add(key);sentMutation=true;attempt.current={command:preview.command,digest:preview.request_digest};
        return kind==='CREATE'?value.client.canvasVideoQueue(preview.command,preview.preview_digest):value.client.canvasVideoExecute(job!);
      });
      if(!live(value))return;const checked=checkedJob(row);
      if(checked.request_digest!==preview.request_digest||canonical(checked.canvas_video)!==canonical(preview.command)||canonical(checked.execution_recipe)!==canonical(preview.execution_recipe)
        ||job&&(checked.id!==job.id||checked.version<job.version))throw invalid('原视频任务身份、版本或配方不一致，请读取原记录。');
      adoptJob(checked);markUncertain(checked.status==='UNKNOWN');clearPreview();dirty(false);
      setNotice(kind==='CREATE'?'已保存原 Job 入队回执，尚未执行。请重新读取并确认执行预览。':'已收到原 CPU 处理回执；候选仍需读取、人工审核和明确采用。');
    }catch(reason){if(live(value)){if(!sentMutation||!uncertainFailure(reason))sent.current.delete(key);fail(reason,'发送结果未确认，请读取原任务；不会自动重发。',sentMutation);}}finally{finish(value);}
  }
  async function readJob(){
    const value=begin('GET');if(!value)return;clearPreview();clearCandidate();
    try{
      const original=jobRef.current,attempted=attempt.current;
      if(original)checkedJob(original);
      const row=await latest.current.read(async()=>{
        let requested=original;
        if(!requested&&attempted){const jobs=await value.client.list();if(!live(value))throw retired();const matches=jobs.filter(job=>job.request_id===attempted.command.request_id&&job.request_digest===attempted.digest);if(matches.length===1)requested=checkedJob(matches[0]);}
        if(!requested)throw new Error('尚未找到唯一原任务回执；保留不确定状态，不会再次发送。');
        const checked=checkedJob(await value.client.get('timeline',requested.id));if(!live(value))throw retired();
        if(checked.request_digest!==requested.request_digest||canonical(checked.canvas_video)!==canonical(checkedJob(requested).canvas_video))throw invalid('原任务请求已改变。');
        const source=await value.client.timelineGet(checked.canvas_video.timeline_snapshot.id);if(!live(value))throw retired();
        if(source.version!==checked.canvas_video.timeline_snapshot.version||source.timeline_digest!==checked.canvas_video.timeline_snapshot.digest
          ||canonical(source.timeline)!==canonical(compileCanvasVideoTimeline(checked.canvas_video.source_snapshots[0],checked.canvas_video.parameters)))throw invalid('原时间线或来源配置已改变；候选保留，不会重新绑定。');
        return {job:checked,timeline:source};
      });
      if(!live(value))return;adoptJob(row.job);timelineRef.current=row.timeline;setTimeline(row.timeline);
      const next={in_ms:String(row.job.canvas_video.parameters.in_ms),out_ms:String(row.job.canvas_video.parameters.out_ms),
        ...(row.job.canvas_video.parameters.include_audio===undefined?{}:{include_audio:row.job.canvas_video.parameters.include_audio})};draftRef.current=next;setDraft(next);savedDraft.current=canonical(next);request.current=row.job.request_id;
      derivedOrigin.current=row.job.canvas_video.derived_from;setDerivedFrom(derivedOrigin.current);derivedRequest.current=row.job.request_id;derivedParent.current=undefined;
      history.current={past:[],future:[]};markUncertain(['UNKNOWN','RUNNING','REVIEWING'].includes(row.job.status));dirty(false);setNotice('已读取原 Job 和保存配置；没有创建、执行、审核或采用。');
    }catch(reason){if(live(value))fail(reason,'原视频任务读取失败；不会重新发送。');}finally{finish(value);}
  }
  async function loadCandidate(){
    const job=jobRef.current;if(!job||!['SUCCEEDED','AWAITING_REVIEW'].includes(job.status)||!job.output_candidate||uncertainRef.current)return;
    const value=begin('CANDIDATE');if(!value)return;clearCandidate();const captured=identity(job);
    try{
      checkedJob(job);const blob=await latest.current.read(()=>value.client.candidate(job));if(!live(value)||identity(jobRef.current)!==captured)return;
      if(!blob.size||blob.size>25*1024*1024||blob.type!=='video/mp4'||blob.size!==job.media_measurement?.byte_count)throw invalid('候选类型或字节数与原测量不一致。');
      const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await blob.arrayBuffer())),byte=>byte.toString(16).padStart(2,'0')).join('');
      if(!live(value)||identity(jobRef.current)!==captured)return;if(digest!==job.output_candidate.digest)throw invalid('候选字节摘要与原 Job 不一致。');
      const next={url:URL.createObjectURL(blob),identity:captured,generation:token,token:{}};candidateRef.current=next;setCandidate(next);
    }catch(reason){if(live(value))fail(reason,'候选读取未通过核验。');}finally{finish(value);}
  }
  function decoded(expected:Candidate){return current()&&candidateRef.current===expected&&decodedCandidate.current===expected.token&&expected.generation===token&&expected.identity===identity(jobRef.current);}
  function mediaLoaded(expected:Candidate,media:HTMLVideoElement){
    if(!current()||candidateRef.current!==expected||expected.generation!==token||expected.identity!==identity(jobRef.current))return;
    const measurement=jobRef.current?.media_measurement;
    if(media.currentSrc!==expected.url||media.src!==expected.url||media.readyState<2||!measurement
      ||!media.videoWidth||!media.videoHeight||media.videoWidth!==measurement.width||media.videoHeight!==measurement.height
      ||typeof measurement.duration_ms!=='number'||!Number.isFinite(measurement.duration_ms)
      ||!Number.isFinite(media.duration)||media.duration<=0||Math.abs(media.duration-measurement.duration_ms/1000)>0.040001){
      decodedCandidate.current=undefined;setCandidateReady(false);reviewConsent.current=false;setReviewConfirmed(false);
      setError('候选视频尚未解码出与原测量一致的画面和时长，当前不能审核。');return;
    }
    decodedCandidate.current=expected.token;setCandidateReady(true);setError('');
  }
  function confirmReview(checked:boolean){if(!current()||busy()||!latest.current.canReview)return;const candidate=candidateRef.current;reviewConsent.current=checked&&!!candidate&&decoded(candidate);setReviewConfirmed(reviewConsent.current);}
  async function review(){
    const job=jobRef.current,captured=candidateRef.current;if(!job||!captured||!decoded(captured)||!reviewConsent.current||!latest.current.canReview||uncertainRef.current||captured.identity!==identity(job))return;
    const key=canonical(['REVIEW',identity(job)]);if(sent.current.has(key))return;const value=begin('REVIEW');if(!value)return;let sentMutation=false;
    try{
      const row=await latest.current.mutate(()=>{
        if(!live(value)||identity(jobRef.current)!==captured.identity||!decoded(captured)||!reviewConsent.current)throw retired();
        checkedJob(job);sent.current.add(key);sentMutation=true;return value.client.review(job);
      });
      if(!live(value))return;const checked=checkedJob(row);
      if(checked.id!==job.id||checked.request_digest!==job.request_digest||checked.version<job.version||checked.status!=='APPROVED'
        ||canonical(checked.canvas_video)!==canonical(checkedJob(job).canvas_video))throw invalid('审核回执与原视频任务不一致，请重新读取。');
      adoptJob(checked);markUncertain(false);setNotice('已明确审核入库；仍需核验并采用到记录中的原卡片。');
      try{void Promise.resolve(latest.current.onApproved?.(checked)).catch(()=>{if(current())setError('审核已记录，但素材刷新未完成，请重新读取。');});}catch{setError('审核已记录，但素材刷新未完成，请重新读取。');}
    }catch(reason){if(live(value)){if(!sentMutation||!uncertainFailure(reason))sent.current.delete(key);fail(reason,'审核结果未确认，请读取原记录。',sentMutation);}}finally{finish(value);}
  }
  function mediaFailed(expected:Candidate|undefined=candidateRef.current){if(!current()||!expected||candidateRef.current!==expected)return;clearCandidate();setError('候选视频无法播放，当前不能审核，请重新读取原任务。');}
  const locked=busy(),valid=current(),impact=impactRef.current;
  return {draft,timeline,derivedFrom,prepareFailedVideo,listDrafts,resumeDraft,generation:token,preview:previewRef.current===preview?preview:undefined,selected,pending,error,notice,uncertain,
    candidate:candidate?.generation===token&&candidateRef.current===candidate?candidate:undefined,candidateReady:candidateReady&&!!candidate&&decodedCandidate.current===candidate.token,impact,locked,current,
    canEdit:valid&&props.canMutate&&!locked&&!selected&&!uncertain,canUndo:valid&&props.canMutate&&!locked&&!selected&&!uncertain&&history.current.past.length>0,
    canRedo:valid&&props.canMutate&&!locked&&!selected&&!uncertain&&history.current.future.length>0,canApply:valid&&props.canMutate&&!locked&&!selected&&!uncertain,
    canInspect:valid&&props.canMutate&&!locked&&!uncertain&&!!timelineRef.current&&savedDraft.current===canonical(draftRef.current)&&(!selected||selected.status==='QUEUED'),
    canCreate:valid&&!locked&&!uncertain&&!selected&&previewConsent.current&&!!previewRef.current?.execution_available&&impact?.input.boundary.kind==='CREATE'&&impact.ready(),
    canExecute:valid&&!locked&&!uncertain&&selected?.status==='QUEUED'&&previewConsent.current&&impact?.input.boundary.kind==='EXECUTE'&&impact.ready(),
    canReview:valid&&props.canReview&&!locked&&!uncertain&&!!candidate&&decoded(candidate)&&reviewConsent.current,
    previewConfirmed,reviewConfirmed,changeParameter,changeAudio,undo,redo,apply,inspect,confirmPreview,confirmImpact,create:()=>dispatch('CREATE'),execute:()=>dispatch('EXECUTE'),readJob,loadCandidate,confirmReview,review,mediaLoaded,mediaFailed};
}
export type StudioCanvasVideoTaskController=ReturnType<typeof useStudioCanvasVideoTask>;
