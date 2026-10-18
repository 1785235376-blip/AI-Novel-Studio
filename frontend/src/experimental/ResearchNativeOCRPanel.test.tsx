// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ResearchNativeOCRPanel } from './ResearchNativeOCRPanel';
import { experimentalClient } from './api';
import type { Source } from './researchLibraryClient';
const source: Source = { id:'image',version:1,title:'图片',author:'',source:'',source_version:'',usage_notes:'',access:'PRIVATE',format:'IMAGE',origin:'LOCAL_IMPORT',filename:'fixture.png',accessed_at:'',extraction_status:'OCR_NOT_CONFIGURED',paragraph_count:0,warnings:[],content_sha256:'a'.repeat(64) };
const client = (id='novel') => experimentalClient(id,{sessionToken:'trusted-session'});
const response = (value:unknown,status=200) => new Response(JSON.stringify(value),{status});
const route={provider_id:'local-tesseract-ocr',model_id:'eng',display_name:'English OCR',languages:['eng']};
const initial={id:'ocr-one',version:1,status:'DRAFT',request:{source_id:'image',source_version:1,operation:'OCR'}};
const preview={...initial,version:2,native_ocr_preview:{receipt_version:2,source_binding:{source_id:'image',source_version:1,source_digest:'a'.repeat(64)},provider_id:route.provider_id,model_id:route.model_id,language:'eng',expires_at:'2099-01-01T00:00:00Z',reviewed_preview_digest:'b'.repeat(64),external_provider_fee_microusd:0,host_compute_cost_included:false}};
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function fixture() {
 let saved:any=initial;const calls:{url:string;method:string;body:any}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,options:RequestInit)=>{
  const method=options.method||'GET',body=options.body?JSON.parse(String(options.body)):undefined;calls.push({url,method,body});
  if(url.endsWith('/status'))return response({native_ocr:{status:'CONFIGURED',routes:[route]}});
  if(url.endsWith('/jobs'))return response(method==='POST'?(saved=initial):{items:[saved]});
  if(url.endsWith('/native-preview'))return response(saved=preview);
  if(url.endsWith('/native-dispatch'))return response(saved={...preview,version:3,status:'RUNNING'});
  if(url.endsWith('/review'))return response(saved={...saved,version:saved.version+1,status:'REVIEWED'});
  return response(saved);
 }));
 return {calls,complete:()=>saved={...preview,version:4,status:'REVIEW_REQUIRED',result:{blocks:[{text:'STUDIO OCR 123',page:1,citation:{source_id:'image',source_version:1,source_digest:'a'.repeat(64),result_digest:'c'.repeat(64),layer:'RESEARCH_DERIVED'}}]}}};
}
it('requires reviewed preview, runs explicitly, refreshes and reviews saved result',async()=>{
 const f=fixture();render(<ResearchNativeOCRPanel client={client()} source={source}/>);
 fireEvent.click(await screen.findByRole('button',{name:'生成 OCR 执行预览'}));
 const execute=await screen.findByRole('button',{name:'确认执行 OCR'});
 expect((execute as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox',{name:'已核对来源与本地模型，同意执行本次 OCR'}));
 fireEvent.click(execute);
 await screen.findByText('RUNNING · v3');
 const dispatch=f.calls.find(c=>c.url.endsWith('/native-dispatch'))!;
 expect(dispatch.body.reviewed_preview_digest).toBe('b'.repeat(64));expect(dispatch.body.expected_version).toBe(2);
 f.complete();fireEvent.click(screen.getByRole('button',{name:'刷新 OCR 状态'}));
 await screen.findByText('STUDIO OCR 123');expect(screen.getByText(new RegExp('摘要 '+ 'c'.repeat(64)))).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'核对文字后标记已审核'}));
 await screen.findByText('REVIEWED · v5');
 expect(f.calls.filter(c=>c.url.endsWith('/native-dispatch'))).toHaveLength(1);
});
it('reopening reads existing receipt without replaying execution',async()=>{
 const f=fixture();f.complete();render(<ResearchNativeOCRPanel client={client()} source={source}/>);
 fireEvent.click(await screen.findByRole('button',{name:'打开 OCR 记录 ocr-one'}));
 await screen.findByText('STUDIO OCR 123');expect(f.calls.every(c=>c.method==='GET')).toBe(true);
});
it('changing project discards an in-flight preview and never sends a late dispatch',async()=>{
 let finish!:(value:Response)=>void;
 const fetch=vi.fn(async(url:string,options:RequestInit)=>{
  if(url.endsWith('/status'))return response({native_ocr:{status:'CONFIGURED',routes:[route]}});
  if(url.endsWith('/native-preview'))return new Promise<Response>(resolve=>{finish=resolve;});
  return response(options.method==='POST'?initial:{items:[]});
 });vi.stubGlobal('fetch',fetch);
 const view=render(<ResearchNativeOCRPanel client={client('first')} source={source}/>);
 fireEvent.click(await screen.findByRole('button',{name:'生成 OCR 执行预览'}));
 await waitFor(()=>expect(finish).toBeTruthy());
 view.rerender(<ResearchNativeOCRPanel client={client('second')} source={source}/>);
 finish(response(preview));await screen.findByRole('button',{name:'生成 OCR 执行预览'});
 await waitFor(()=>expect(screen.queryByRole('button',{name:'确认执行 OCR'})).toBeNull());
 expect(fetch.mock.calls.some(([url])=>url.endsWith('/native-dispatch'))).toBe(false);
});
it('an uncertain dispatch retry keeps the same application idempotency key',async()=>{
 const keys:string[]=[];let attempts=0;
 vi.stubGlobal('fetch',vi.fn(async(url:string,options:RequestInit)=>{
  if(url.endsWith('/status'))return response({native_ocr:{status:'CONFIGURED',routes:[route]}});
  if(url.endsWith('/native-preview'))return response(preview);
  if(url.endsWith('/native-dispatch')){
   keys.push(JSON.parse(String(options.body)).idempotency_key);
   if(++attempts===1)throw new Error('response lost');
   return response({...preview,version:3,status:'RUNNING'});
  }
  return response(options.method==='POST'?initial:{items:[]});
 }));
 render(<ResearchNativeOCRPanel client={client()} source={source}/>);
 fireEvent.click(await screen.findByRole('button',{name:'生成 OCR 执行预览'}));
 fireEvent.click(await screen.findByRole('checkbox',{name:'已核对来源与本地模型，同意执行本次 OCR'}));
 fireEvent.click(screen.getByRole('button',{name:'确认执行 OCR'}));
 await screen.findByText('读取或操作失败，请重试。');
 fireEvent.click(screen.getByRole('button',{name:'确认执行 OCR'}));
 await screen.findByText('RUNNING · v3');expect(keys).toHaveLength(2);expect(keys[0]).toBe(keys[1]);
});

it('rejects derived OCR citations bound to a different source digest',async()=>{
 const { currentOCR } = await import('./researchNativeOCRClient');
 const row={...initial,result:{blocks:[{text:'wrong',page:1,citation:{source_id:'image',source_version:1,source_digest:'d'.repeat(64),result_digest:'c'.repeat(64),layer:'RESEARCH_DERIVED' as const}}]}};
 expect(currentOCR(row,source)).toBe(false);
});
