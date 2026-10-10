// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {RevisionComparisonModelPanel} from './RevisionComparisonModelPanel';
import {revisionIntelligenceClient,type VersionComparison} from './revisionIntelligenceClient';
import {experimentalClient} from './api';
const api=()=>revisionIntelligenceClient(experimentalClient('n',{sessionToken:'host'}));
const row={id:'c',version:1,status:'REVIEW',stale:false,title:'Compare',comparison:{chapter_id:'chapter',current_version:3,before_version:2,after_version:3},before_text:'旧文',after_text:'新文',diff:[],diff_method:'EXACT',model_called:false,semantic_execution:'NOT_REQUESTED'} as unknown as VersionComparison;
const route={route_id:'local',provider_id:'mock',model_id:'mock-writer',display_name:'Synthetic',available:true,synthetic:true,reasons:[]};
const preview={preview_digest:'a'.repeat(64),execution_available:true,quality_verification:'SYNTHETIC_PROTOCOL_ONLY',request:{prompt:'Exact A/B versions',context:{}},sources:{versions:{before:{version:2},after:{version:3}}},broker:{chosen:route},budget:{version:1},max_output_bytes:32768,timeout_seconds:120,excluded:[]};
const reply=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('reads no model until requested, exact preview needs distinct consent and version receipt',async()=>{
 const fetch=vi.fn(async(url:string)=>reply(url.endsWith('/catalog')?{routes:[route]}:url.endsWith('/preview')?{...row,version:2,model_preview:preview}:{...row,version:4,model_preview:preview,model_execution:{job_id:'job',status:'QUEUED',receipt_state:'RECORDED'}}));
 vi.stubGlobal('fetch',fetch);const changed=vi.fn();const view=render(<RevisionComparisonModelPanel api={api()} row={row} onChanged={changed}/>);
 expect(fetch).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'查看已注册版本比较模型'}));
 fireEvent.change(await screen.findByLabelText('本地版本比较模型'),{target:{value:'local'}});fireEvent.click(screen.getByRole('button',{name:'准备准确版本模型预览'}));
 await waitFor(()=>expect(changed).toHaveBeenCalledTimes(1));view.rerender(<RevisionComparisonModelPanel api={api()} row={changed.mock.calls[0][0]} onChanged={changed}/>);
 const send=screen.getByRole('button',{name:'明确发送此次本地版本比较'});expect((send as HTMLButtonElement).disabled).toBe(true);
 expect((screen.getByLabelText('准确版本模型请求') as HTMLTextAreaElement).value).toContain('Exact A/B versions');
 fireEvent.click(screen.getByLabelText('已核对原版本全文、模型身份与零费用预占'));fireEvent.click(send);fireEvent.click(send);
 await waitFor(()=>expect(fetch.mock.calls.filter(([url])=>url.endsWith('/dispatch'))).toHaveLength(1));
});
it('marks executed opinions separately and accepts only metadata through owning API',async()=>{
 const fetch=vi.fn(async(_url:string)=>reply({...row,version:6}));vi.stubGlobal('fetch',fetch);
 const opinion={id:'o',kind:'EMOTIONAL_TONE_CHANGED',explanation:'合成解释',before_version:2,after_version:3,before_quote:'旧文',before_start:0,after_quote:'新文',after_start:0,decision:'PENDING',source:'EXECUTED_MODEL_ASSESSMENT' as const,model:{provider_id:'mock',model_id:'mock-writer',synthetic:true},quality_verification:'SYNTHETIC_PROTOCOL_ONLY'};
 const value={...row,version:5,model_assessments:[opinion],model_execution:{job_id:'job',status:'COMPLETED',receipt_state:'RECORDED',model_called:true,usage_state:'KNOWN'}};
 const changed=vi.fn();render(<RevisionComparisonModelPanel api={api()} row={value} onChanged={changed}/>);
 expect(screen.getByText('Model-derived · 实际原模型任务')).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'接受为解读（不改稿）'}));
 await waitFor(()=>expect(changed).toHaveBeenCalledTimes(1));expect(fetch.mock.calls[0][0]).toContain('/model/opinions/o/accept');expect(fetch.mock.calls[0][0]).not.toContain('/generation/');
});
it('late catalog after unmount does not deliver result or send anything',async()=>{
 let finish:(response:Response)=>void=()=>{};const fetch=vi.fn(async()=>new Promise<Response>(resolve=>{finish=resolve;}));vi.stubGlobal('fetch',fetch);
 const changed=vi.fn();const view=render(<RevisionComparisonModelPanel api={api()} row={row} onChanged={changed}/>);
 fireEvent.click(screen.getByRole('button',{name:'查看已注册版本比较模型'}));view.unmount();finish(reply({routes:[route]}));await Promise.resolve();expect(changed).not.toHaveBeenCalled();expect(fetch).toHaveBeenCalledTimes(1);
});
it('unknown and stale model execution offers cancellation but never replay or old source text',async()=>{
 const fetch=vi.fn(async(_url:string)=>reply({...row,stale:true}));vi.stubGlobal('fetch',fetch);const changed=vi.fn();
 render(<RevisionComparisonModelPanel api={api()} row={{...row,stale:true,model_preview:preview,model_execution:{job_id:'old-job',status:'UNKNOWN',receipt_state:'UNKNOWN_NO_AUTOMATIC_REPLAY',model_called:false,usage_state:'UNKNOWN'}}} onChanged={changed}/>);
 expect(screen.queryByLabelText('准确版本模型请求')).toBeNull();expect(screen.queryByRole('button',{name:'明确发送此次本地版本比较'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'取消原版本模型任务'}));await waitFor(()=>expect(changed).toHaveBeenCalledTimes(1));expect(fetch.mock.calls[0][0]).toContain('/model/cancel');
});
