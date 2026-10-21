/** Synthetic browser response fixture of the original panel. No API/FFmpeg/model is called here. */
import {createRoot} from 'react-dom/client';
import {AppShell} from '../ui/AppShell';
import {StudioMediaExecutionPanel} from './StudioMediaExecutionPanel';
import {studioProductionClient,type MediaCommand,type ProductionJob} from './studioProductionClient';
import {checkedCanvasReturnBinding} from './studioCanvasReturnBinding';
import {templateGraph} from './workflowTaskTemplate/canvasAudioWorkflowTemplate.testFixtures';
import native from './fixtures/canvasAudioTrim.native.json';
import '../ui/ui.css';import '../ui/fixture.css';import '../ui/desktop-craft.css';import './creative.css';
export function mount(){
 const calls={preview:0,create:0,execute:0,get:0},commands:MediaCommand[]=[];
 const binding=checkedCanvasReturnBinding(structuredClone(native.command.canvas_return));
 const failed={...structuredClone(native.queued),status:'FAILED',version:3,output_candidate:null,receipt_digest:null,approved_asset_version:null,error_code:'TEST_LOCAL_FAILURE'} as unknown as ProductionJob;
 let saved:MediaCommand|undefined;
 const canonical=(v:unknown)=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
 const hash=async(v:unknown)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(v))))).map(x=>x.toString(16).padStart(2,'0')).join('');
 async function receipt(kind:'preview'|'queued'|'executed',command:MediaCommand){const row:any=structuredClone(native[kind]);row.request_id=command.request_id;row.command=structuredClone(command);row.command.source_snapshots=row.command.source_snapshots.map((s:any)=>({...s,reference_only:true}));row.execution_recipe.parameters=structuredClone(command.parameters);row.request_digest=await hash(command);if(kind==='preview')row.preview_digest=await hash(['preview',command]);else row.id='job-'+command.request_id;return row;}
 window.fetch=async(input:RequestInfo|URL,init:RequestInit={})=>{
  const url=String(input),body=init.body?JSON.parse(String(init.body)):undefined;let value:unknown;
  if(url.endsWith('/providers'))value={items:[],automatic_runtime_start:false,health_probed:false,credentials_read:false};
  else if(url.endsWith('/preview')){calls.preview++;commands.push(structuredClone(body));value=await receipt('preview',body);}
  else if(url.endsWith('/jobs')&&init.method==='POST'){calls.create++;saved=structuredClone(body.command);value=await receipt('queued',saved!);}
  else if(url.endsWith('/execute')){calls.execute++;value=await receipt('executed',saved!);}
  else if(url.includes('/jobs/audio/')){calls.get++;value=saved?await receipt('queued',saved):failed;}
  else throw new Error('Unexpected synthetic fixture request '+url);
  return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
 };
 (window as any).__cycle2={calls,commands};
 const graph=templateGraph();graph.project_id=binding.project_id;graph.scope=binding.scope;graph.definition.nodes=graph.definition.nodes.slice(0,2);
 const owner={projectId:binding.project_id,incarnation:binding.incarnation,actorId:'local-check',actorWorkspaceId:'',mode:'local' as const,workspaceId:'',storylineId:'',branchId:''};
 const task={source:binding.source,returnBinding:binding,isCurrent:()=>true};
 const host=document.createElement('div');document.body.replaceChildren(host);
 createRoot(host).render(<AppShell module="AUDIO" onModuleChange={()=>{}} actor="本地组件检查" scope={{workspace:'创作工作区',project:'双画布实际入口',storyline:'主线',branch:'合成检查'}}
 sidebar={<p>原媒体控制器与严格 SDK；本夹具只有合成回执，不调用处理器。</p>}
 main={<div style={{height:'100%',overflow:'auto',minWidth:0}}><StudioMediaExecutionPanel client={studioProductionClient(binding.project_id,{sessionToken:''})} assets={[structuredClone(native.source)]} canMutate canReview busy={false} isCurrent={()=>true} read={f=>f()} mutate={f=>f()} onDirtyChange={()=>{}} onUnavailable={()=>{}} canvasAudioTrimTask={task}
 audioWorkflowTemplates={{owner,list:async()=>[structuredClone(graph)],read:async()=>structuredClone(graph)}} externalJob={new URLSearchParams(location.search).has('recovery')?failed:undefined}/></div>}
 inspector={<p>显式预览、两阶段输入确认、原请求及模板版本。没有模型推理。</p>} status="本地合成回执 UI 检查"/>);
}
