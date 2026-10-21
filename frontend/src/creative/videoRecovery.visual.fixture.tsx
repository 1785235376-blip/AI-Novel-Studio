/** Browser replay of this slice's generated CPU capture; does not run a processor or API. */
import {createRoot} from 'react-dom/client';
import {AppShell} from '../ui/AppShell';
import {StudioCanvasVideoTaskPanel} from './StudioCanvasVideoTaskPanel';
import {studioProductionClient} from './studioProductionClient';
import '../ui/ui.css';import '../ui/fixture.css';import '../ui/desktop-craft.css';import './creative.css';
export function mount(){
 const native=(window as any).__videoRecoveryNative;
 if(native?.contract!=='synthetic-video-derived-recovery-proof/1'||native.real_cpu_ffmpeg!==true)throw new Error('Run the native derived test capture first.');
 const calls={save:0,preview:0,queue:0,execute:0,candidate:0,review:0,get:0};
 const b=native.derived_command.canvas_return;let job=native.parent_failed;
 const canonical=(v:unknown)=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
 const equal=(a:unknown,b:unknown)=>{if(canonical(a)!==canonical(b))throw new Error('Replay request differs from original CPU capture: '+canonical({actual:a,expected:b}));};
 Object.defineProperty(crypto,'randomUUID',{value:()=>native.derived_command.request_id,configurable:true});
 window.fetch=async(input:RequestInfo|URL,init:RequestInit={})=>{
  const url=String(input),body=init.body?JSON.parse(String(init.body)):undefined;let value:unknown;(window as any).__videoRecovery.requests.push({url,method:init.method,body});
  if(url.endsWith('/timelines')&&init.method==='POST'){equal(body.timeline,native.child_timeline.timeline);if(body.expected_version!==0)throw new Error('Parent timeline must not be edited');calls.save++;value=native.child_timeline;}
  else if(url.includes('/timelines/'))value=native.child_timeline;
  else if(url.endsWith('/canvas-video/preview')){equal(body,native.derived_command);calls.preview++;value=native.preview;}
  else if(url.endsWith('/canvas-video/queue')){equal(body.command,native.derived_command);if(body.reviewed_preview_digest!==native.preview.preview_digest)throw new Error('Preview changed');calls.queue++;value=job=native.queued;}
  else if(url.endsWith('/execute')){if(body.expected_version!==native.queued.version||body.expected_request_digest!==native.queued.request_digest)throw new Error('Queue changed');calls.execute++;value=job=native.executed;}
  else if(url.endsWith('/candidate')){calls.candidate++;return new Response(Uint8Array.from(atob(native.candidate_base64),(c)=>c.charCodeAt(0)),{headers:{'Content-Type':'video/mp4'}});}
  else if(url.endsWith('/review')){if(body.expected_version!==native.executed.version||body.reviewed_output_digest!==native.executed.output_candidate.digest)throw new Error('Candidate changed');calls.review++;value=job=native.approved;}
  else if(url.includes('/jobs/timeline/')){calls.get++;value=job;}
  else throw new Error('Unexpected local replay request '+url);
  return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
 };
 (window as any).__videoRecovery={calls,requests:[]};
 const host=document.createElement('div');document.body.replaceChildren(host);
 createRoot(host).render(<AppShell module="VIDEO" onModuleChange={()=>{}} actor="本地组件检查" scope={{workspace:'创作工作区',project:'视频失败恢复',storyline:'主线',branch:'CPU 回执重放'}}
 sidebar={<p>原视频 Job 与 Timeline。此页面重放合成短片的 CPU 回执；不调用服务或模型。</p>}
 main={<div style={{height:'100%',overflow:'auto',minWidth:0}}><StudioCanvasVideoTaskPanel client={studioProductionClient(b.project_id,{sessionToken:''})}
 task={{id:'native-video-recovery',asset:native.source_asset,origin:{projectId:b.project_id,canvasId:b.canvas_id,canvasVersion:b.canvas_version,canvasDigest:b.canvas_digest,cardId:b.card_id,source:{asset_id:b.source.id,kind:'video',version:b.source.version,digest:b.source.digest},binding:b},resumeJob:native.parent_failed,isOriginCurrent:()=>true}}
 canMutate canReview busy={false} isCurrent={()=>true} read={f=>f()} mutate={f=>f()} onDirtyChange={()=>{}} onUnavailable={()=>{}}/></div>}
 inspector={<p>原失败记录保留，新草稿独立保存；先审核候选，再由原画布显式采用。</p>} status="本地 CPU 回执重放 · 浏览器实际解码"/>);
}
