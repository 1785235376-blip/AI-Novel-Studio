/** Local UI fixture. Replays this task's synthetic owned CPU capture; no processor/API is called. */
import {createRoot} from 'react-dom/client';
import {useState} from 'react';
import {AppShell} from '../ui/AppShell';
import {StudioCanvasImageTaskPanel} from './StudioCanvasImageTaskPanel';
import {CanvasImageTaskReturn} from './CanvasImageTaskReturn';
import {MediaCanvasHistoryPanel} from './MediaCanvasHistoryPanel';
import {studioClient} from './studioClient';
import {studioProductionClient,type MediaCommand,type ProductionJob} from './studioProductionClient';
import {captureCanvasImageTask} from './canvasImageTask';
import type {CanvasViewRecord} from './studioCanvasViewClient';
import '../ui/ui.css';import '../ui/fixture.css';import '../ui/desktop-craft.css';import './creative.css';
declare global{interface Window{__maskNative:any;__maskCheck:any}}
export function mount(){
 const n=window.__maskNative,binding=n.command.canvas_return,project=binding.project_id;
 const calls={preview:0,create:0,execute:0,review:0,candidate:0,save:0,restore:0,get:0},commands:MediaCommand[]=[];
 let saved:MediaCommand|undefined,phase:'queued'|'executed'|'approved'='queued',canvas=structuredClone(n.canvas_before);
 const clone=<T,>(v:T):T=>structuredClone(v);
 const canonical=(v:unknown)=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
 function receipt(kind:'preview'|'queued'|'executed'|'approved',command:MediaCommand){
  const row=clone(n[kind]);row.request_id=command.request_id;row.command=clone(command);
  row.command.source_snapshots=row.command.source_snapshots.map((s:any)=>({...s,reference_only:true}));
  return row;
 }
 window.fetch=async(input:RequestInfo|URL,init:RequestInit={})=>{
  const url=String(input),body=init.body?JSON.parse(String(init.body)):undefined;let value:unknown;
  if(url.endsWith('/providers'))value={items:[],automatic_runtime_start:false,health_probed:false,credentials_read:false};
  else if(url.endsWith('/preview')){calls.preview++;commands.push(clone(body));value=receipt('preview',body);}
  else if(url.endsWith('/jobs')&&init.method==='POST'){calls.create++;saved=clone(body.command);value=receipt('queued',saved!);}
  else if(url.endsWith('/execute')){calls.execute++;phase='executed';value=receipt('executed',saved!);}
  else if(url.endsWith('/review')){calls.review++;phase='approved';value=receipt('approved',saved!);}
  else if(url.endsWith('/candidate')){calls.candidate++;return new Response(Uint8Array.from(atob(n.candidate_png_base64),(v:string)=>v.charCodeAt(0)),{headers:{'Content-Type':'image/png'}});}
  else if(url.includes('/jobs/image/')){calls.get++;value=receipt(phase,saved!);}
  else if(url.endsWith('/assets/'+n.source.id))value=n.source;
  else if(url.endsWith('/assets/'+n.formal.id))value=n.formal;
  else if(url.endsWith('/canvas-views/'+canvas.id+'/history'))value={...clone(n.history),current_version:canvas.version,current_definition_digest:canvas.definition_digest,items:n.history.items.filter((v:any)=>v.version<=canvas.version).map((v:any)=>({...v,can_restore:v.version!==canvas.version&&v.can_restore}))};
  else if(url.endsWith('/canvas-views/'+canvas.id+'/restore')){calls.restore++;canvas=clone(n.restored);value=canvas;}
  else if(url.endsWith('/canvas-views/'+canvas.id)){
   if(init.method==='PUT'){calls.save++;if(body.expected_version!==1||canonical(body.definition)!==canonical(n.canvas_after.definition))throw new Error('Fixture expected exact original-card CAS replacement');canvas=clone(n.canvas_after);}
   value=canvas;
  }else throw new Error('Unexpected synthetic fixture request '+url);
  return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
 };
 window.__maskCheck={calls,commands};
 const client=studioClient(project,{sessionToken:''}),production=studioProductionClient(project,{sessionToken:''});
 const task={id:'mask-card-task',origin:captureCanvasImageTask(n.canvas_before,binding.card_id,n.source,binding.incarnation),asset:n.source,isOriginCurrent:()=>true};
 const read=async<T,>(f:()=>Promise<T>)=>f(),owner={};
 function Harness(){
  const [approved,setApproved]=useState<ProductionJob>(),[base,setBase]=useState<CanvasViewRecord>(clone(n.canvas_before)),[done,setDone]=useState(false);
  return <AppShell module="IMAGE" onModuleChange={()=>{}} actor="本地组件检查" scope={{workspace:'创作工作区',project:'用户遮罩卡片任务',storyline:'主线',branch:'合成回执'}}
   sidebar={<p>保存的图像卡片与手绘遮罩。UI 回执来自本轮自建像素样本；这里不运行处理器。</p>}
   main={<div style={{height:'100%',overflow:'auto',minWidth:0}}><p aria-label="原卡片当前版本">原卡片画布 v{base.version}；另一张卡片及坐标保留。</p>
    {!done&&<StudioCanvasImageTaskPanel task={task} taskAssets={[clone(n.source),clone(n.mask)]} client={production} canMutate canReview busy={false} isCurrent={()=>true} read={read} mutate={read} onDirtyChange={()=>{}} onUnavailable={()=>{}} onApproved={job=>setApproved(job)}/>}
    {approved&&!done&&<CanvasImageTaskReturn task={task} approved={approved} client={client} production={production} disabled={false} canMutate isCurrent={()=>true} read={read} mutate={read} onAdopt={setBase} onUncertain={()=>{throw new Error('Unexpected fixture uncertainty');}} onComplete={()=>setDone(true)}/>}
    {done&&<MediaCanvasHistoryPanel base={base} client={client.graphs.canvasViews!} owner={owner} incarnation={binding.incarnation} canMutate externalDirty={false} busy={false} isCurrent={()=>true} read={read} mutate={read} onAdopt={setBase} onUncertain={()=>{throw new Error('Unexpected fixture history uncertainty');}}/>}
   </div>}
   inspector={<p>用户提供二值 mask：白色保留，黑色透明。不执行 AI 自动语义分割。</p>} status="本地 UI 合成回执检查；真实 CPU 像素证据单列"/>;
 }
 createRoot(document.getElementById('root')!).render(<Harness/>);
}
