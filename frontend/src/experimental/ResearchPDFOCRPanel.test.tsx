// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ResearchNativeOCRPanel } from './ResearchNativeOCRPanel';
import { currentOCR, researchNativeOCRClient } from './researchNativeOCRClient';
import { experimentalClient } from './api';
import type { Source } from './researchLibraryClient';
const source: Source = { id:'pdf',version:1,title:'PDF',author:'',source:'',source_version:'',usage_notes:'',access:'PRIVATE',format:'PDF',origin:'LOCAL_IMPORT',filename:'fixture.pdf',accessed_at:'',extraction_status:'OCR_NOT_CONFIGURED',paragraph_count:0,warnings:[],content_sha256:'a'.repeat(64) };
const client=experimentalClient('novel',{sessionToken:'trusted-session'});
const response=(value:unknown)=>new Response(JSON.stringify(value));
const route={provider_id:'pdf-ocr',model_id:'eng',display_name:'PDF OCR',languages:['eng'],source_kind:'PDF'};
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('selects one explicit page and only the PDF route before manual dispatch',async()=>{
 const calls:{url:string;body:any}[]=[];let saved:any;
 vi.stubGlobal('fetch',vi.fn(async(url:string,options:RequestInit)=>{
  const body=options.body?JSON.parse(String(options.body)):undefined;calls.push({url,body});
  if(url.endsWith('/status'))return response({native_ocr:{status:'CONFIGURED',routes:[{...route,provider_id:'image-only',source_kind:'IMAGE',display_name:'Image OCR'},route]}});
  if(url.endsWith('/jobs')){
   if(options.method==='POST')return response(saved={id:'one',version:1,status:'DRAFT',request:body});
   return response({items:[]});
  }
  if(url.endsWith('/native-preview'))return response(saved={...saved,version:2,native_ocr_preview:{receipt_version:2,source_binding:{source_id:'pdf',source_version:1,source_digest:'a'.repeat(64),page:saved.request.pages[0]},provider_id:route.provider_id,model_id:'eng',language:'eng',expires_at:'2099-01-01T00:00:00Z',reviewed_preview_digest:'b'.repeat(64)}});
  if(url.endsWith('/native-dispatch'))return response({...saved,version:3,status:'RUNNING'});
  return response(saved);
 }));
 render(<ResearchNativeOCRPanel client={client} source={source}/>);
 fireEvent.change(screen.getByRole('spinbutton'),{target:{value:'2'}});
 fireEvent.click(await screen.findByRole('button',{name:'生成 OCR 执行预览'}));
 expect(screen.queryByRole('option',{name:'Image OCR'})).toBeNull();
 const execute=await screen.findByRole('button',{name:'确认执行 OCR'});
 expect((execute as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox',{name:'已核对来源与本地模型，同意执行本次 OCR'}));fireEvent.click(execute);
 await screen.findByText('RUNNING · v3');
 expect(calls.find(c=>c.url.endsWith('/jobs')&&c.body)?.body.pages).toEqual([2]);
 expect(calls.find(c=>c.url.endsWith('/native-preview'))?.body.provider_id).toBe('pdf-ocr');
 expect(calls.filter(c=>c.url.endsWith('/native-dispatch'))).toHaveLength(1);
});
it('changing page discards an in-flight preview and cannot execute the old page',async()=>{
 let finish!:(value:Response)=>void;const calls:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,options:RequestInit)=>{
  calls.push(url);
  if(url.endsWith('/status'))return response({native_ocr:{status:'CONFIGURED',routes:[route]}});
  if(url.endsWith('/native-preview'))return new Promise<Response>(resolve=>{finish=resolve;});
  if(options.method==='POST')return response({id:'old',version:1,status:'DRAFT',request:{source_id:'pdf',source_version:1,operation:'OCR',pages:[1]}});
  return response({items:[]});
 }));
 render(<ResearchNativeOCRPanel client={client} source={source}/>);
 fireEvent.click(await screen.findByRole('button',{name:'生成 OCR 执行预览'}));
 await waitFor(()=>expect(finish).toBeTruthy());
 fireEvent.change(screen.getByRole('spinbutton'),{target:{value:'2'}});
 finish(response({id:'old',version:2,status:'DRAFT',request:{source_id:'pdf',source_version:1,operation:'OCR',pages:[1]},native_ocr_preview:{receipt_version:2,source_binding:{source_id:'pdf',source_version:1,source_digest:'a'.repeat(64),page:1},provider_id:route.provider_id,model_id:'eng',language:'eng',expires_at:'2099-01-01T00:00:00Z',reviewed_preview_digest:'b'.repeat(64)}}));
 await screen.findByRole('button',{name:'生成 OCR 执行预览'});
 expect(screen.queryByRole('button',{name:'确认执行 OCR'})).toBeNull();expect(calls.some(x=>x.endsWith('/native-dispatch'))).toBe(false);
});
it('client rejects omitted PDF page and mismatched result citation page',()=>{
 expect(()=>researchNativeOCRClient(client).create(source)).toThrow(/页码/);
 const row={id:'one',version:1,status:'REVIEW_REQUIRED',request:{source_id:'pdf',source_version:1,operation:'OCR',pages:[2]},result:{blocks:[{text:'text',page:2,citation:{source_id:'pdf',source_version:1,source_digest:'a'.repeat(64),result_digest:'b'.repeat(64),layer:'RESEARCH_DERIVED' as const,page:1}}]}};
 expect(currentOCR(row,source,2)).toBe(false);row.result.blocks[0].citation.page=2;expect(currentOCR(row,source,2)).toBe(true);expect(currentOCR(row,source,1)).toBe(false);
});
