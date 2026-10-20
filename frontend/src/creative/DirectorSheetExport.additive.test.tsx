// @vitest-environment jsdom
import {webcrypto} from 'node:crypto';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {creativeClient} from './client';
import {DirectorSheetExportPanel} from './DirectorSheetExportPanel';
import {newDocument,type CreativeDocument} from './types';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.clearAllMocks();});
const document={...newDocument('DIRECTOR'),id:'saved-director',version:2} as CreativeDocument;
it('uses exact original source/version GET and verifies CSV bytes before return',async()=>{
 vi.stubGlobal('crypto',webcrypto);const bytes=new TextEncoder().encode('\ufeff"direction"\r\n"中文"\r\n'),hash=Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');
 const headers={'Content-Type':'text/csv; charset=utf-8','X-Creative-Document-Version':'2','X-Creative-Document-Digest':'a'.repeat(64),'X-Content-SHA256':hash};
 const fetch=vi.fn(async(_url:string,_init:RequestInit)=>new Response(bytes,{headers}));vi.stubGlobal('fetch',fetch);const client=creativeClient('project',{sessionToken:'synthetic'});
 const result=await client.directorSheetExport(document);expect(result.blob.type).toBe('text/csv');expect(fetch.mock.calls[0][0]).toContain('/documents/saved-director/director-sheet-export?expected_version=2');
 fetch.mockImplementation(async()=>new Response('tampered',{headers}));await expect(client.directorSheetExport(document)).rejects.toThrow(/校验/);
});
it('downloads only explicitly and discards response after availability ABA',async()=>{
 let resolve!:(v:any)=>void;const request=vi.fn(()=>new Promise<any>(yes=>{resolve=yes;}));const props={document,available:true,isCurrent:()=>true,request,onDenied:vi.fn()};const view=render(<DirectorSheetExportPanel {...props}/>);
 expect(request).not.toHaveBeenCalled();fireEvent.click(screen.getByText('导出已保存导演调度 CSV'));view.rerender(<DirectorSheetExportPanel {...props} available={false}/>);view.rerender(<DirectorSheetExportPanel {...props}/>);
 const receipt={blob:new Blob(['CSV']),filename:'director.csv',documentVersion:2,documentDigest:'a'.repeat(64),sha256:'b'.repeat(64)};
 await act(async()=>resolve(receipt));expect(downloadPortableBlob).not.toHaveBeenCalled();fireEvent.click(screen.getByText('导出已保存导演调度 CSV'));await act(async()=>resolve(receipt));expect(downloadPortableBlob).toHaveBeenCalledTimes(1);
});
