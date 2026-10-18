// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AIDirectorPanel } from './AIDirectorPanel';
import { creativeClient, type DirectorProposal } from './client';
import { newDocument, newScene, type CreativeDocument } from './types';
import captured from './directorScreenplayWire.testFixture.json';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const p=captured.preview.receipt;
function setup({enabled=true,privateRow=false}={}){
 const scene={...newScene(1),id:'scene-one'};
 const source:CreativeDocument={...newDocument('SCREENPLAY'),source_independent:true,id:p.source_document_id,version:p.source_version,title:'Independent board',status:'DRAFT',actor_id:'author',created_at:'',updated_at:'',source_evidence:{},scenes:captured.source.scenes,shots:[]};
 const row:DirectorProposal={id:p.proposal_id,version:p.version-1,title:captured.submitted_review.title,status:privateRow?'MODEL_UNAVAILABLE':'NEEDS_REVIEW',source_document_id:source.id,source_version:source.version,source_digest:p.source_digest,director_notes:[],output_digest:'a'.repeat(64),provenance:{source_mode:'SCREENPLAY',model_called:false},...(privateRow?{unavailable_reason:'CREATIVE_DIRECTOR_EXECUTION_UNAVAILABLE'}:{})};
 const requests:{url:string;method:string;body:unknown}[]=[];
 const fetch=vi.fn(async(url:string,init:RequestInit={})=>{
   requests.push({url,method:init.method||'GET',body:init.body?JSON.parse(String(init.body)):undefined});
   let value:unknown;
   if(url.endsWith('/director-proposals'))value={items:[row]};
   else if(url.endsWith('/model-capabilities'))value=enabled?{independent_screenplay_contract:'CREATIVE_DIRECTOR_SCREENPLAY_MODEL_V2'}:{};
   else if(url.endsWith('/model-routes'))value={items:[{route_id:p.route_id,provider_id:p.provider_id,model_id:p.model_id,synthetic:false,available:true,reasons:[]}]};
   else if(url.endsWith('/model-v2/preview'))value=captured.preview;
   else if(url.endsWith('/model-v2/dispatch'))value=captured.completed_status;
   else if(url.endsWith('/model-v2/prepare-review'))value=captured.pending;
   else if(url.endsWith('/model-v2/review')||url.endsWith('/model-v2/adopted-draft'))value=captured.adopted;
   else if(url.endsWith('/export'))value={document:captured.document,document_digest:captured.adopted.receipt.document.digest,format:'creative-json/1',boundary:'original-owner'};
   else throw new Error('Unexpected request '+url);
   return {ok:true,status:200,json:async()=>structuredClone(value)};
 });vi.stubGlobal('fetch',fetch);
 const client=creativeClient(captured.preview.project_id,{sessionToken:'',localHostToken:'fixture-session'});
 const props={client,documents:[source],canMutate:true,modelAuthority:true,onDocument:vi.fn(),onDenied:vi.fn(),onPendingChange:vi.fn()};
 const view=render(<AIDirectorPanel {...props}/>);return {props,view,requests,fetch,row};
}
const click=(name:string)=>fireEvent.click(screen.getByRole('button',{name}));
async function select(){fireEvent.click(await screen.findByRole('button',{name:new RegExp(captured.submitted_review.title)}));}
it('mounts the versioned view only after explicit capability read and hands exact adopted pin to original parent',async()=>{
 const e=setup();await select();expect(e.requests.filter(r=>r.url.endsWith('/model-capabilities'))).toHaveLength(0);
 click('打开独立剧本模型审核');await screen.findByRole('region',{name:'独立剧本模型导演审核'});
 expect(e.requests.every(r=>r.method==='GET')).toBe(true);expect(screen.queryByLabelText('导演建议审核')).toBeNull();
 fireEvent.change(screen.getByLabelText('独立导演本地路由'),{target:{value:p.route_id}});click('预览独立剧本模型输入');await screen.findByText('预览尚未调用模型');
 fireEvent.click(screen.getByLabelText('已核对输入，允许调用一次本地模型'));click('调用一次独立导演模型');await screen.findByText('COMPLETED');
 click('准备原模型结果供人工审核');await screen.findByLabelText('模型导演草稿标题');
 expect((screen.getByRole('button',{name:'准备待审导演建议'}) as HTMLButtonElement).disabled).toBe(true);
 expect(e.props.onPendingChange).toHaveBeenLastCalledWith(true);
 fireEvent.change(screen.getByLabelText('模型 1 导演意图'),{target:{value:captured.submitted_review.director_notes[0].note}});
 fireEvent.click(screen.getByLabelText('已核对来源、理由和假设，创建独立导演草稿'));click('采用模型审核结果');await screen.findByText('已采用为独立导演 DRAFT，画布尚未保存。');
 click('核对并打开模型导演草稿');await waitFor(()=>expect(e.props.onDocument).toHaveBeenCalledTimes(1));
 expect(e.props.onDocument.mock.calls[0][1]).toEqual({id:captured.adopted.receipt.document.document_id,version:captured.adopted.receipt.document.version,digest:captured.adopted.receipt.document.digest});
 const writes=e.requests.filter(r=>r.method==='POST');expect(writes).toHaveLength(4);expect(writes.every(r=>r.url.includes('/model-v2/'))).toBe(true);
 expect(writes.at(-1)?.body).toEqual(captured.submitted_review);
});
it('does not fall back to legacy model writes when the host has not advertised this contract',async()=>{
 const e=setup({enabled:false});await select();const originalRouteReads=e.requests.filter(r=>r.url.endsWith('/model-routes')).length;click('打开独立剧本模型审核');await screen.findByText('当前主机尚未启用独立剧本模型审核能力。');
 expect(screen.queryByRole('region',{name:'独立剧本模型导演审核'})).toBeNull();expect(e.requests.every(r=>r.method==='GET')).toBe(true);
 expect(e.requests.filter(r=>r.url.endsWith('/model-routes'))).toHaveLength(originalRouteReads);
});
it('does not label an original private task as uncalled rule output or expose legacy adoption',async()=>{
 setup({privateRow:true});await select();await screen.findByText(/此建议包含独立模型任务/);
 expect(screen.queryByText('本地规则辅助 · 未调用模型')).toBeNull();expect(screen.queryByRole('button',{name:'审核并采用'})).toBeNull();
 click('打开独立剧本模型审核');await screen.findByRole('region',{name:'独立剧本模型导演审核'});
 expect(screen.getByRole('button',{name:'读取原模型任务状态'})).toBeTruthy();
});
