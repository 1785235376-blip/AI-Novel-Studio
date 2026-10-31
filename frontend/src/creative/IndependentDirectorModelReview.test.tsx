// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { IndependentDirectorModelReview } from './IndependentDirectorModelReview';
import { createDirectorModelClient } from './directorModelClient';
import type { CreativeDocument } from './types';
import captured from './directorModelActionWire.testFixture.json';
afterEach(cleanup);
const p=captured.preview.receipt;
function setup(options:{uncertain?:boolean}={}){
 const requests:{path:string;method:string;body:unknown}[]=[];
 const json=vi.fn(async(path:string,method:string,body:unknown)=>{
   requests.push({path,method,body}); const suffix=path.split('/').at(-1);
   if(suffix==='preview')return structuredClone(captured.preview);
   if(suffix==='dispatch'||suffix==='status')return structuredClone(captured.completed_status);
   if(suffix==='prepare-review'||suffix==='pending-review')return structuredClone(captured.pending);
   if(suffix==='review'&&options.uncertain)throw new Error('lost response');
   if(['review','reconcile-review','adopted-draft'].includes(suffix!))return structuredClone(captured.adopted);
   throw new Error('Unexpected endpoint');
 });
 const model=createDirectorModelClient(captured.preview.project_id,{json:json as never});
 const creative={export:vi.fn(async()=>({document:structuredClone(captured.draft) as unknown as CreativeDocument,document_digest:captured.adopted.receipt.document.digest,format:'creative-json/1',boundary:'original-owner'}))};
 const props={model,creative,proposal:{id:p.proposal_id,version:p.version-1,title:captured.submitted_review.title},
 source:{id:p.source_document_id,version:p.source_version,digest:p.source_digest},routes:[{route_id:p.route_id,provider_id:p.provider_id,model_id:p.model_id,synthetic:false,available:true,reasons:[]}],
 canMutate:true,disabled:false,onDocument:vi.fn(),onPending:vi.fn(),onDenied:vi.fn()};
 return {props,json,requests};
}
const click=(name:string)=>fireEvent.click(screen.getByRole('button',{name}));
async function prepare(){
 fireEvent.change(screen.getByLabelText('独立导演本地路由'),{target:{value:p.route_id}});
 click('预览独立分镜模型输入');await screen.findByText('预览尚未调用模型');
 fireEvent.click(screen.getByLabelText('已核对输入，允许调用一次本地模型'));click('调用一次独立导演模型');
 await screen.findByText('COMPLETED');click('准备原模型结果供人工审核');await screen.findByLabelText('模型导演草稿标题');
}
function approve(){fireEvent.click(screen.getByLabelText('已核对来源、理由和假设，创建独立导演草稿'));click('采用模型审核结果');}
it('runs explicit captured preview, model, human review and exact reopen with no construction-time request',async()=>{
 const e=setup();render(<IndependentDirectorModelReview {...e.props}/>);expect(e.json).not.toHaveBeenCalled();
 await prepare();expect(e.requests.map(r=>r.path.split('/').at(-1))).toEqual(['preview','dispatch','prepare-review']);
 expect(e.props.onDocument).not.toHaveBeenCalled();approve();await screen.findByText('已采用为独立导演 DRAFT，画布尚未保存。');
 expect(e.props.onDocument).not.toHaveBeenCalled();click('核对并打开模型导演草稿');await waitFor(()=>expect(e.props.onDocument).toHaveBeenCalledTimes(1));
 expect(e.props.onDocument.mock.calls[0][1]).toEqual({id:captured.adopted.receipt.document.document_id,version:captured.adopted.receipt.document.version,digest:captured.adopted.receipt.document.digest});
 expect(e.requests.filter(r=>r.method==='POST').map(r=>r.path.split('/').at(-1))).toEqual(['preview','dispatch','prepare-review','review']);
 expect(e.props.creative.export).toHaveBeenCalledTimes(1);
 expect(e.requests.find(r=>r.path.endsWith('/review'))?.body).toEqual(captured.submitted_review);
});
it('retains uncertain review content and reconciles exact submission without resubmitting',async()=>{
 const e=setup({uncertain:true});render(<IndependentDirectorModelReview {...e.props}/>);await prepare();
 approve();await screen.findByText('lost response');
 const title=screen.getByLabelText('模型导演草稿标题') as HTMLInputElement;expect(title.value).toBe(captured.submitted_review.title);expect(title.closest('fieldset')?.disabled).toBe(true);
 click('读取原模型任务状态');await waitFor(()=>expect(e.requests.filter(r=>r.path.endsWith('/status'))).toHaveLength(1));
 expect((screen.getByLabelText('模型导演草稿标题') as HTMLInputElement).value).toBe(captured.submitted_review.title);
 click('只读核对刚才的审核提交');await screen.findByText('已采用为独立导演 DRAFT，画布尚未保存。');
 const writes=e.requests.filter(r=>r.path.endsWith('/review'));expect(writes).toHaveLength(1);
 expect(e.requests.find(r=>r.path.endsWith('/reconcile-review'))?.body).toEqual(writes[0].body);
});
it('clears private content on denied read and does not keep an actionable old UI',async()=>{
 const e=setup();render(<IndependentDirectorModelReview {...e.props}/>);await prepare();
 e.json.mockRejectedValueOnce(new ApiError({status:403,code:'DENIED',message:'revoked'}));click('读取原模型任务状态');
 await screen.findByText('原模型审核已拒绝访问。请重新验证身份后打开。');expect(screen.queryByLabelText('模型导演草稿标题')).toBeNull();expect(screen.queryByRole('button')).toBeNull();expect(e.props.onDenied).toHaveBeenCalledTimes(1);
});
it('drops late preview across authority A→denied→A and requires a new explicit gesture',async()=>{
 const e=setup();let resolve!:(value:typeof captured.preview)=>void;e.json.mockImplementationOnce(()=>new Promise(yes=>{resolve=yes;}));
 const view=render(<IndependentDirectorModelReview {...e.props}/>);fireEvent.change(screen.getByLabelText('独立导演本地路由'),{target:{value:p.route_id}});click('预览独立分镜模型输入');
 view.rerender(<IndependentDirectorModelReview {...e.props} canMutate={false}/>);view.rerender(<IndependentDirectorModelReview {...e.props}/>);
 await act(async()=>resolve(captured.preview));expect(screen.queryByText('预览尚未调用模型')).toBeNull();expect(e.json).toHaveBeenCalledTimes(1);
});
it('does not discard edited local review when a read finds another adoption',async()=>{
 const e=setup();render(<IndependentDirectorModelReview {...e.props}/>);await prepare();
 fireEvent.change(screen.getByLabelText('模型导演草稿标题'),{target:{value:'Unsaved local review'}});
 const remote=structuredClone(captured.completed_status) as unknown as {receipt:Record<string,unknown>};
 remote.receipt={...remote.receipt,phase:'ADOPTED_DRAFT',version:captured.adopted.receipt.approved_version,adoption:captured.adopted.receipt};
 e.json.mockResolvedValueOnce(remote as never);click('读取原模型任务状态');
 await screen.findByText('ADOPTED_DRAFT');
 expect((screen.getByLabelText('模型导演草稿标题') as HTMLInputElement).value).toBe('Unsaved local review');
 expect(e.props.onDocument).not.toHaveBeenCalled();expect(screen.queryByRole('button',{name:'核对并打开模型导演草稿'})).toBeNull();
});
it('does not dispatch before explicit preview consent and deduplicates a rapid preview gesture',async()=>{
 const e=setup();render(<IndependentDirectorModelReview {...e.props}/>);
 expect((screen.getByRole('button',{name:'预览独立分镜模型输入'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('独立导演本地路由'),{target:{value:p.route_id}});
 click('预览独立分镜模型输入');click('预览独立分镜模型输入');await screen.findByText('预览尚未调用模型');
 expect(e.requests).toHaveLength(1);expect((screen.getByRole('button',{name:'调用一次独立导演模型'}) as HTMLButtonElement).disabled).toBe(true);
});
it('retains draft if explicitly confirmed conflict recovery cannot read the original receipt',async()=>{
 const e=setup();render(<IndependentDirectorModelReview {...e.props}/>);await prepare();
 fireEvent.change(screen.getByLabelText('模型导演草稿标题'),{target:{value:'Keep this draft'}});
 // The unchanged fixture status is COMPLETED while local preparation already exists: treat it as conflict.
 click('读取原模型任务状态');await screen.findByText('原任务状态已变化，本地审核仍保留。');
 fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并读取当前原任务'));
 e.json.mockRejectedValueOnce(new Error('read offline'));click('按确认重新读取原任务');await screen.findByText('read offline');
 expect((screen.getByLabelText('模型导演草稿标题') as HTMLInputElement).value).toBe('Keep this draft');
 expect(e.requests.filter(r=>r.path.endsWith('/review'))).toHaveLength(0);
});
