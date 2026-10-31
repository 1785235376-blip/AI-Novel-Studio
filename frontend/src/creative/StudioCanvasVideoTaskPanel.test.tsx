// @vitest-environment jsdom
// Software SDK receipts exercise the real React/proof flow. Native video processing is tested separately.
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {createHash,webcrypto} from 'node:crypto';
import {Blob as NativeBlob} from 'node:buffer';
import {ExecutionImpactPanel} from '../experimental/executionImpact/ExecutionImpactPanel';
import {StudioCanvasVideoTaskPanel} from './StudioCanvasVideoTaskPanel';
import {useStudioCanvasVideoTask,type StudioCanvasVideoTaskController,type StudioCanvasVideoTaskProps} from './useStudioCanvasVideoTask';
import {captureCanvasVideoTrimTask,checkedCanvasVideoTaskCommand,compileCanvasVideoTimeline,type CanvasVideoTaskCommand,type CanvasVideoTaskPreview} from './canvasVideoTrimTask';
import type {ProductionJob,ProductionRecipe,StudioProductionClient} from './studioProductionClient';
import type {CanvasViewRecord} from './studioCanvasViewClient';
import type {StudioAsset} from './studioClient';

const clone=<T,>(value:T):T=>structuredClone(value);
const hash=(value:string|Uint8Array)=>createHash('sha256').update(value).digest('hex');
const bytes=new Uint8Array([0,0,0,12,102,116,121,112,109,112,52,50]);
const candidateDigest=hash(bytes),project='synthetic-video-project',time='2026-01-01T00:00:00Z';
let state:StudioCanvasVideoTaskController,props:StudioCanvasVideoTaskProps,client:StudioProductionClient;
let storedTimeline:Awaited<ReturnType<StudioProductionClient['timelineGet']>>|undefined,requestIndex:number;
let jobs:Map<string,ProductionJob>,latestCommand:CanvasVideoTaskCommand;
const recipe=(command:CanvasVideoTaskCommand):ProductionRecipe=>({contract:'studio-execution-recipe/1',operation_id:command.operation_id,adapter:'LOCAL_FFMPEG',
  output_profile:'DELIVERY_H264_MP4',timeline:compileCanvasVideoTimeline(command.source_snapshots[0],command.parameters),export_profile:{preset:'DELIVERY_H264_MP4',video_bitrate_kbps:400,audio_bitrate_kbps:96,crf:23},automatic_fallback:false,recipe_digest:'e'.repeat(64)});
const digest=(command:CanvasVideoTaskCommand)=>hash(JSON.stringify(command));
function preview(command:CanvasVideoTaskCommand):CanvasVideoTaskPreview{return {contract:'studio-canvas-video-preview/1',novel_id:project,branch_id:null,command:clone(command),
  request_digest:digest(command),preview_digest:hash('preview:'+digest(command)),execution_recipe:recipe(command),execution_available:true,automatic_dispatch:false,product_acceptance:'LOCAL_REQUIRED'};}
function job(command:CanvasVideoTaskCommand,status:ProductionJob['status']='QUEUED',version=1):ProductionJob{
  const rendered=['SUCCEEDED','APPROVED'].includes(status);
  return {contract:'studio-production-job/1',owner:'timeline',id:'job-'+command.request_id,novel_id:project,branch_id:null,version,status,request_id:command.request_id,
    request_digest:digest(command),receipt_digest:rendered?'d'.repeat(64):null,operation_id:'m9.timeline.multitrack',command:null,provider:null,canvas_video:clone(command),
    timeline_snapshot:clone(command.timeline_snapshot),sources:clone(command.source_snapshots),execution_recipe:recipe(command),
    output_candidate:rendered?{id:'synthetic-video-candidate',version:1,digest:candidateDigest,kind:'video'}:null,
    media_measurement:rendered?{duration_ms:command.parameters.out_ms-command.parameters.in_ms,width:640,height:360,fps:25,video_codec:'h264',audio_codec:'aac',
      container:'mp4',sample_rate:48000,channels:2,byte_count:bytes.length,profile_validation:'NATIVE_FFPROBE_EXACT',render_profile:'STUDIO_MULTITRACK_LOCAL_FFMPEG_DELIVERY_H264_MP4',export_profile:{preset:'DELIVERY_H264_MP4',video_bitrate_kbps:400,audio_bitrate_kbps:96,crf:23}}:null,
    approved_asset_version:status==='APPROVED'?2:null,automatic_replay:false,remote_compute_may_continue:false,product_acceptance:'LOCAL_REQUIRED',created_at:time,updated_at:time};
}
beforeEach(()=>{
  jobs=new Map();storedTimeline=undefined;requestIndex=0;
  vi.stubGlobal('crypto',{subtle:webcrypto.subtle,randomUUID:()=>`video-request-${++requestIndex}`});
  vi.stubGlobal('Blob',NativeBlob);
  let candidateIndex=0;Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> `blob:synthetic-video-${++candidateIndex}`)});
  Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()});
  const asset:StudioAsset={id:'synthetic-video',novel_id:project,branch_id:null,kind:'video',media_type:'video/mp4',version:1,sha256:'a'.repeat(64),size:4000,filename:'synthetic-video.mp4',created_at:time,updated_at:time};
  const canvas:CanvasViewRecord={id:'synthetic-canvas',project_id:project,scope:{mode:'local',novel_id:project},version:1,definition_digest:'b'.repeat(64),created_at:time,updated_at:time,
    definition:{schema_version:1,title:'Synthetic video',viewport:{x:0,y:0,zoom:1},cards:[{id:'original-card',position:{x:44,y:66},asset:{asset_id:asset.id,version:1,digest:asset.sha256,kind:'video'}}]},
    reference_states:[{card_id:'original-card',state:'CURRENT_METADATA',filename:asset.filename}],execution_authority:false,binary_content_verified:false,capacity:{history_used:0,record_bytes:1000}};
  const origin=captureCanvasVideoTrimTask(canvas,'original-card',asset,'file:00000000-0000-0000-0000-000000000001');
  client={timelineSave:vi.fn(async(id:Parameters<StudioProductionClient['timelineSave']>[0],body:Parameters<StudioProductionClient['timelineSave']>[1])=>{
    const result={id:id??'synthetic-timeline',novel_id:project,branch_id:null,title:body.title,timeline:clone(body.timeline),version:body.expected_version+1,
      timeline_digest:hash(JSON.stringify(body.timeline)),created_at:time,updated_at:time};storedTimeline=result;return clone(result);
  }),timelineGet:vi.fn(async()=>clone(storedTimeline!)),canvasVideoPreview:vi.fn(async(command:CanvasVideoTaskCommand)=>{latestCommand=clone(command);return preview(command);}),
  canvasVideoQueue:vi.fn(async(command:CanvasVideoTaskCommand,reviewed:string)=>{expect(reviewed).toBe(preview(command).preview_digest);const row=job(command);jobs.set(row.id,row);return clone(row);}),
  canvasVideoExecute:vi.fn(async(original:ProductionJob)=>{const row=job(original.canvas_video!,'SUCCEEDED',original.version+2);jobs.set(row.id,row);return clone(row);}),
  get:vi.fn(async(_owner:ProductionJob['owner'],id:string)=>clone(jobs.get(id)!)),list:vi.fn(async()=>[...jobs.values()].map(clone)),
  candidate:vi.fn(async()=>new Blob([bytes],{type:'video/mp4'})),review:vi.fn(async(original:ProductionJob)=>{const row=job(original.canvas_video!,'APPROVED',original.version+1);jobs.set(row.id,row);return clone(row);}),
  } as unknown as StudioProductionClient;
  props={client,task:{id:'synthetic-task',origin,asset,isOriginCurrent:()=>true},canMutate:true,canReview:true,busy:false,isCurrent:()=>true,
    read:work=>work(),mutate:work=>work(),onDirtyChange:vi.fn(),onUnavailable:vi.fn(),onApproved:vi.fn()};
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
function Harness(){state=useStudioCanvasVideoTask(props);const impact=state.impact;return impact?<ExecutionImpactPanel input={impact.input} owner={impact}
  current={impact.current()} canConfirm={props.canMutate&&state.previewConfirmed} busy={state.locked} isCurrent={impact.current}
  onConfirm={proof=>void state.confirmImpact(impact,proof)}/>:null;}
async function configured(){
  const view=render(<Harness/>);act(()=>{state.changeParameter('in_ms','1000');state.changeParameter('out_ms','1600');});
  await act(async()=>state.apply());expect(state.timeline?.version,state.error).toBe(1);return view;
}
async function inspected(){await act(async()=>state.inspect());expect(state.preview,state.error).toBeTruthy();act(()=>state.confirmPreview(true));}
async function confirm(kind:'CREATE'|'EXECUTE'){
  expect(state.impact?.input.boundary.kind).toBe(kind);const check=screen.getByLabelText('已核对本次输入变化与影响范围');
  await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));fireEvent.click(check);fireEvent.click(screen.getByRole('button',{name:'确认本次输入核对'}));
  await waitFor(()=>expect(kind==='CREATE'?state.canCreate:state.canExecute).toBe(true));
}
async function queued(){const view=await configured();await inspected();await confirm('CREATE');await act(async()=>state.create());expect(state.selected?.status,state.error).toBe('QUEUED');return view;}
async function succeeded(){const view=await queued();await inspected();await confirm('EXECUTE');await act(async()=>state.execute());expect(state.selected?.status,state.error).toBe('SUCCEEDED');return view;}
// Metadata events are explicitly simulated here; these bytes are not a browser-playable native render.
function syntheticDecodedMedia(candidate:NonNullable<StudioCanvasVideoTaskController['candidate']>,overrides:Partial<{currentSrc:string;readyState:number;videoWidth:number;videoHeight:number;duration:number}>={},video=document.createElement('video')){
  video.src=candidate.url;
  for(const [key,value] of Object.entries({currentSrc:candidate.url,readyState:2,videoWidth:640,videoHeight:360,duration:0.6,...overrides}))Object.defineProperty(video,key,{configurable:true,value});
  return video;
}
function decodeCurrent(){const candidate=state.candidate!;expect(candidate).toBeTruthy();act(()=>state.mediaLoaded(candidate,syntheticDecodedMedia(candidate)));expect(state.candidateReady,state.error).toBe(true);}

it('requires both real owner confirmations even for direct actions and consumes each only once',async()=>{
  await configured();await inspected();const oldCreate=state.create;
  await act(async()=>oldCreate());expect(client.canvasVideoQueue).not.toHaveBeenCalled();expect(client.canvasVideoExecute).not.toHaveBeenCalled();
  await confirm('CREATE');await act(async()=>Promise.all([oldCreate(),oldCreate()]));expect(client.canvasVideoQueue).toHaveBeenCalledTimes(1);expect(state.selected?.status).toBe('QUEUED');
  await act(async()=>state.execute());expect(client.canvasVideoExecute).not.toHaveBeenCalled();
  await inspected();await confirm('EXECUTE');const execute=state.execute;await act(async()=>Promise.all([execute(),execute()]));
  expect(client.canvasVideoExecute).toHaveBeenCalledTimes(1);expect(state.selected?.status,state.error).toBe('SUCCEEDED');
  await act(async()=>{await execute();await oldCreate();});expect(client.canvasVideoQueue).toHaveBeenCalledTimes(1);expect(client.canvasVideoExecute).toHaveBeenCalledTimes(1);
});
it('invalidates an old confirmation across parameter A/B/A, supports undo/redo and requires a new saved request',async()=>{
  await configured();await inspected();await confirm('CREATE');const oldGate=state.impact!,oldCreate=state.create,oldRequest=latestCommand.request_id;
  act(()=>state.changeParameter('out_ms','1640'));expect(oldGate.current()).toBe(false);
  act(()=>state.undo());expect(state.draft.out_ms).toBe('1600');expect(oldGate.current()).toBe(false);
  act(()=>state.redo());expect(state.draft.out_ms).toBe('1640');act(()=>state.undo());
  await act(async()=>oldCreate());expect(client.canvasVideoQueue).not.toHaveBeenCalled();
  await act(async()=>state.apply());expect(state.timeline?.version).toBe(2);await inspected();expect(latestCommand.request_id).not.toBe(oldRequest);
  await confirm('CREATE');await act(async()=>state.create());expect(client.canvasVideoQueue).toHaveBeenCalledTimes(1);
});
it.each(['CREATE','EXECUTE'] as const)('rejects changed source pin at the last %s mutate callback, including observed A/B/A',async kind=>{
  if(kind==='CREATE')await configured();else await queued();await inspected();await confirm(kind);
  let release!:()=>Promise<void>;
  props.mutate=<T,>(work:()=>Promise<T>)=>new Promise<T>((resolve,reject)=>{release=async()=>{try{resolve(await work());}catch(error){reject(error);}};});
  const operation=kind==='CREATE'?state.create:state.execute;let pending!:Promise<void>;act(()=>{pending=operation();});
  const old=props.task.asset.sha256;props.task.asset.sha256='c'.repeat(64);expect(state.current()).toBe(false);props.task.asset.sha256=old;
  await act(async()=>{await release();await pending;});expect(state.current()).toBe(false);
  if(kind==='CREATE')expect(client.canvasVideoQueue).not.toHaveBeenCalled();else expect(client.canvasVideoExecute).not.toHaveBeenCalled();
});
it('retires client A/B/A without rerender after the mismatch is observed',async()=>{
  await configured();await inspected();await confirm('CREATE');const gate=state.impact!,create=state.create;
  props.client={...client};expect(gate.current()).toBe(false);props.client=client;expect(gate.current()).toBe(false);
  await act(async()=>create());expect(client.canvasVideoQueue).not.toHaveBeenCalled();
});
it('blocks UNKNOWN replay, preserving the original request and only allowing explicit reads',async()=>{
  await queued();await inspected();await confirm('EXECUTE');
  vi.mocked(client.canvasVideoExecute).mockImplementation(async original=>{const row=job(original.canvas_video!,'UNKNOWN',original.version+1);jobs.set(row.id,row);return row;});
  const execute=state.execute;await act(async()=>execute());expect(state.selected?.status).toBe('UNKNOWN');expect(state.uncertain).toBe(true);
  await act(async()=>{await execute();await state.inspect();await state.create();});expect(client.canvasVideoExecute).toHaveBeenCalledTimes(1);expect(client.canvasVideoQueue).toHaveBeenCalledTimes(1);
  await act(async()=>state.readJob());expect(state.selected?.status).toBe('UNKNOWN');expect(client.canvasVideoExecute).toHaveBeenCalledTimes(1);
});
it('reopens QUEUED through the original GET/Timeline and re-confirms execute without another queue',async()=>{
  const first=await queued(),saved=clone(state.selected!);first.unmount();props.task={...props.task,resumeJob:saved};
  const calls=vi.mocked(client.canvasVideoQueue).mock.calls.length;render(<Harness/>);expect(state.impact).toBeUndefined();expect(client.canvasVideoExecute).not.toHaveBeenCalled();
  await act(async()=>state.readJob());expect(state.selected?.status,state.error).toBe('QUEUED');await inspected();await confirm('EXECUTE');
  await act(async()=>state.execute());expect(client.canvasVideoQueue).toHaveBeenCalledTimes(calls);expect(client.canvasVideoExecute).toHaveBeenCalledTimes(1);
});
it('rejects a changed saved timeline and never silently rebinds the old Job',async()=>{
  const first=await queued(),saved=clone(state.selected!);first.unmount();storedTimeline={...storedTimeline!,version:2};props.task={...props.task,resumeJob:saved};
  render(<Harness/>);await act(async()=>state.readJob());expect(state.error).toContain('原时间线或来源配置已改变');expect(state.impact).toBeUndefined();
  await act(async()=>state.execute());expect(client.canvasVideoExecute).not.toHaveBeenCalled();
});
it('ignores a late old-client Job read before further Timeline or source access',async()=>{
  const first=await queued(),saved=clone(state.selected!);first.unmount();props.task={...props.task,resumeJob:saved};
  let finish!:(value:ProductionJob)=>void;vi.mocked(client.get).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
  const view=render(<Harness/>);let pending!:Promise<void>;act(()=>{pending=state.readJob();});await waitFor(()=>expect(finish).toBeTypeOf('function'));
  props.client={...client};view.rerender(<Harness/>);props.client=client;view.rerender(<Harness/>);const reads=vi.mocked(client.timelineGet).mock.calls.length;
  await act(async()=>{finish(saved);await pending;});expect(client.timelineGet).toHaveBeenCalledTimes(reads);expect(state.impact).toBeUndefined();expect(client.canvasVideoExecute).not.toHaveBeenCalled();
});
it('rejects blank or off-grid parameters before saving the original Timeline',async()=>{
  render(<Harness/>);act(()=>state.changeParameter('in_ms',''));await act(async()=>state.apply());
  expect(state.error).toContain('明确的整数毫秒');expect(client.timelineSave).not.toHaveBeenCalled();
  act(()=>{state.changeParameter('in_ms','0');state.changeParameter('out_ms','1001');});await act(async()=>state.apply());
  expect(state.error).toBeTruthy();expect(client.timelineSave).not.toHaveBeenCalled();expect(client.canvasVideoQueue).not.toHaveBeenCalled();
});
it('keeps a digest-mismatched candidate unreviewable and preserves the original successful Job',async()=>{
  await succeeded();vi.mocked(client.candidate).mockResolvedValue(new Blob([new Uint8Array(bytes.length).fill(7)],{type:'video/mp4'}));
  await act(async()=>state.loadCandidate());expect(state.error).toContain('候选字节摘要与原 Job 不一致');expect(state.candidate).toBeUndefined();
  act(()=>state.confirmReview(true));await act(async()=>state.review());expect(client.review).not.toHaveBeenCalled();expect(state.selected?.status).toBe('SUCCEEDED');
});
it('requires explicit candidate review acknowledgement and consumes duplicate review clicks only once',async()=>{
  await succeeded();await act(async()=>state.loadCandidate());expect(state.candidate,state.error).toBeTruthy();
  await act(async()=>state.review());expect(client.review).not.toHaveBeenCalled();act(()=>state.confirmReview(true));expect(state.canReview).toBe(false);
  decodeCurrent();act(()=>state.confirmReview(true));
  const review=state.review;await act(async()=>Promise.all([review(),review()]));expect(client.review).toHaveBeenCalledTimes(1);expect(props.onApproved).toHaveBeenCalledTimes(1);
});
it('rejects a deleted or replaced original target at the last review callback without adopting the candidate',async()=>{
  await succeeded();await act(async()=>state.loadCandidate());decodeCurrent();act(()=>state.confirmReview(true));let release!:()=>Promise<void>;
  props.mutate=<T,>(work:()=>Promise<T>)=>new Promise<T>((resolve,reject)=>{release=async()=>{try{resolve(await work());}catch(error){reject(error);}};});
  let pending!:Promise<void>;act(()=>{pending=state.review();});const current=props.task.isOriginCurrent;props.task.isOriginCurrent=()=>false;
  expect(state.current()).toBe(false);props.task.isOriginCurrent=current;await act(async()=>{await release();await pending;});
  expect(state.current()).toBe(false);expect(client.review).not.toHaveBeenCalled();expect(props.onApproved).not.toHaveBeenCalled();expect(state.selected?.status).toBe('SUCCEEDED');
});
it.each([{videoWidth:0},{videoWidth:320},{duration:0.641}])('rejects decoded video metadata %j before review',async metadata=>{
  await succeeded();await act(async()=>state.loadCandidate());const candidate=state.candidate!;
  act(()=>{state.mediaLoaded(candidate,syntheticDecodedMedia(candidate,metadata));state.confirmReview(true);});await act(async()=>state.review());
  expect(state.candidateReady).toBe(false);expect(state.error).toContain('尚未解码');expect(client.review).not.toHaveBeenCalled();expect(props.onApproved).not.toHaveBeenCalled();
});
it('ignores old-candidate loadeddata and error events rather than unlocking the next candidate',async()=>{
  await succeeded();await act(async()=>state.loadCandidate());const old=state.candidate!,loaded=state.mediaLoaded,failed=state.mediaFailed;
  await act(async()=>state.loadCandidate());const next=state.candidate!;expect(next.url).not.toBe(old.url);
  act(()=>{loaded(old,syntheticDecodedMedia(old));failed(old);state.confirmReview(true);});
  expect(state.candidate).toBe(next);expect(state.candidateReady).toBe(false);expect(state.canReview).toBe(false);await act(async()=>state.review());expect(client.review).not.toHaveBeenCalled();
  act(()=>state.mediaLoaded(next,syntheticDecodedMedia(next,{currentSrc:old.url})));expect(state.candidateReady).toBe(false);
  decodeCurrent();act(()=>state.confirmReview(true));expect(state.canReview).toBe(true);
});
it('rechecks decoded readiness at the actual review callback after a playback error',async()=>{
  await succeeded();await act(async()=>state.loadCandidate());decodeCurrent();act(()=>state.confirmReview(true));const candidate=state.candidate!;let release!:()=>Promise<void>;
  props.mutate=<T,>(work:()=>Promise<T>)=>new Promise<T>((resolve,reject)=>{release=async()=>{try{resolve(await work());}catch(error){reject(error);}};});
  let pending!:Promise<void>;act(()=>{pending=state.review();});act(()=>state.mediaFailed(candidate));await act(async()=>{await release();await pending;});
  expect(client.review).not.toHaveBeenCalled();expect(props.onApproved).not.toHaveBeenCalled();expect(state.candidateReady).toBe(false);
});
it('uses the visible panel through saved config, preview, queue, execute, digest review and explicit approval',async()=>{
  render(<StudioCanvasVideoTaskPanel {...props}/>);
  expect(screen.getByText(/默认输出静音音轨/)).toBeTruthy();expect(client.timelineSave).not.toHaveBeenCalled();expect(client.canvasVideoQueue).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('来源起点（毫秒）'),{target:{value:'1000'}});fireEvent.change(screen.getByLabelText('来源终点（毫秒）'),{target:{value:'1600'}});
  fireEvent.click(screen.getByRole('button',{name:'应用截取配置'}));await screen.findByText(/已应用到本次原时间线版本/);
  async function confirmVisible(){
    fireEvent.click(screen.getByRole('button',{name:'读取视频截取预览'}));const ack=await screen.findByLabelText('已核对本次视频范围、来源和重新编码边界');fireEvent.click(ack);
    const impact=screen.getByLabelText('已核对本次输入变化与影响范围');await waitFor(()=>expect((impact as HTMLInputElement).disabled).toBe(false));fireEvent.click(impact);fireEvent.click(screen.getByRole('button',{name:'确认本次输入核对'}));
  }
  await confirmVisible();const queue=screen.getByRole('button',{name:'仅创建视频任务并入队'});await waitFor(()=>expect((queue as HTMLButtonElement).disabled).toBe(false));fireEvent.click(queue);
  await screen.findByText(/已保存原 Job 入队回执/);expect(client.canvasVideoExecute).not.toHaveBeenCalled();
  await confirmVisible();const execute=screen.getByRole('button',{name:'明确执行本次视频截取'});await waitFor(()=>expect((execute as HTMLButtonElement).disabled).toBe(false));fireEvent.click(execute);
  fireEvent.click(await screen.findByRole('button',{name:'读取并核对候选视频'}));const review=await screen.findByLabelText('已查看本次视频候选，确认审核当前 Job 版本与输出摘要');
  expect((review as HTMLInputElement).disabled).toBe(true);const video=document.querySelector('video')!;
  syntheticDecodedMedia({url:video.src} as NonNullable<StudioCanvasVideoTaskController['candidate']>,{},video);fireEvent.loadedData(video);
  expect((review as HTMLInputElement).disabled).toBe(false);
  fireEvent.click(review);fireEvent.click(screen.getByRole('button',{name:'明确审核视频并入素材库'}));
  await waitFor(()=>expect(props.onApproved).toHaveBeenCalledTimes(1));expect(client.review).toHaveBeenCalledTimes(1);expect(client.canvasVideoExecute).toHaveBeenCalledTimes(1);
  expect(vi.mocked(props.onApproved!).mock.calls[0][0].status).toBe('APPROVED');
});


it('applies optional source audio through undo, new proof and a reopened original Job without replay',async()=>{
 const view=await configured();expect(state.draft.include_audio).toBeUndefined();
 act(()=>state.changeAudio(true));await act(async()=>state.apply());await inspected();await confirm('CREATE');
 expect(latestCommand.parameters.include_audio).toBe(true);
 expect((storedTimeline!.timeline.tracks[0].clips[0] as {include_audio:boolean}).include_audio).toBe(true);
 const oldGate=state.impact!,oldCreate=state.create;
 act(()=>state.changeAudio(false));expect(oldGate.current()).toBe(false);
 act(()=>state.undo());expect(state.draft.include_audio).toBe(true);expect(oldGate.current()).toBe(false);
 await act(async()=>oldCreate());expect(client.canvasVideoQueue).not.toHaveBeenCalled();
 await act(async()=>state.apply());await inspected();await confirm('CREATE');await act(async()=>state.create());
 expect(state.selected?.canvas_video?.parameters.include_audio).toBe(true);
 const saved=clone(state.selected!);view.unmount();props.task={...props.task,resumeJob:saved};render(<Harness/>);
 expect(state.draft.include_audio).toBe(true);expect(state.impact).toBeUndefined();expect(client.canvasVideoExecute).not.toHaveBeenCalled();
 await act(async()=>state.readJob());expect(state.draft.include_audio).toBe(true);
 await inspected();await confirm('EXECUTE');await act(async()=>state.execute());
 expect(client.canvasVideoQueue).toHaveBeenCalledTimes(1);expect(client.canvasVideoExecute).toHaveBeenCalledTimes(1);
});
