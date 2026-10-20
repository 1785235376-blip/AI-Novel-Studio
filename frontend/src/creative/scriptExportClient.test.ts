// @vitest-environment node
import { createHash } from 'node:crypto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { creativeClient, type ScriptExportFormat } from './client';
import { newDocument, type CreativeDocument } from './types';
const source={...newDocument('SCRIPT'),id:'script / 1',version:2,script:{purpose:'CUSTOM',body:'  原文\n\n'}} as CreativeDocument;
const bytes=new TextEncoder().encode(source.script!.body), hash=createHash('sha256').update(bytes).digest('hex');
afterEach(()=>vi.unstubAllGlobals());
describe('Script export shares authenticated byte verification',()=>{
 it.each<[ScriptExportFormat,string,string]>([['txt','text/plain','txt'],['markdown','text/markdown','md'],['docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document','docx']])('requests %s with exact saved version and receipt',async(format,mime,extension)=>{
  const fetch=vi.fn(async(_url:RequestInfo|URL,_init?:RequestInit)=>new Response(bytes,{headers:{'Content-Type':mime,'X-Content-SHA256':hash,'X-Creative-Document-Version':'2','X-Creative-Document-Digest':'a'.repeat(64)}}));vi.stubGlobal('fetch',fetch);
  const result=await creativeClient('project',{sessionToken:'captured'}).scriptExport(source,format);expect(fetch.mock.calls[0][0]).toContain(`/script%20%2F%201/script-export?format=${format}&expected_version=2`);expect(fetch.mock.calls[0][1]?.headers).toMatchObject({'X-Session-Token':'captured'});expect(result.filename).toBe(`creative-script-v2.${extension}`);expect(await result.blob.text()).toBe(source.script!.body);
 });
 it('rejects a different document type before making any request',async()=>{const fetch=vi.fn();vi.stubGlobal('fetch',fetch);await expect(creativeClient('p',{sessionToken:'captured'}).scriptExport({...source,mode:'SCREENPLAY'},'txt')).rejects.toThrow();expect(fetch).not.toHaveBeenCalled();});
 it('rejects corrupt response bytes rather than offering an unchecked download',async()=>{vi.stubGlobal('fetch',vi.fn(async()=>new Response('corrupt',{headers:{'Content-Type':'text/plain','X-Content-SHA256':hash,'X-Creative-Document-Version':'2','X-Creative-Document-Digest':'a'.repeat(64)}})));await expect(creativeClient('p',{sessionToken:'captured'}).scriptExport(source,'txt')).rejects.toMatchObject({problem:{code:'CREATIVE_EXPORT_RECEIPT_INVALID'}});});
});
