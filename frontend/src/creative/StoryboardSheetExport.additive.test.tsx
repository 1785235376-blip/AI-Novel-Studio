// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { creativeClient } from './client';
import { DirectorSheetExportPanel } from './DirectorSheetExportPanel';
import { newDocument, type CreativeDocument } from './types';
import { downloadPortableBlob } from '../experimental/portableProjectsClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.clearAllMocks();});
const document={...newDocument('STORYBOARD'),id:'saved-board',version:3} as CreativeDocument;
it('uses the original authenticated versioned sheet GET and rejects tampered bytes',async()=>{
 vi.stubGlobal('crypto',webcrypto);
 const bytes=new TextEncoder().encode('\ufeff"shot_number"\r\n"1"\r\n');
 const hash=Buffer.from(await webcrypto.subtle.digest('SHA-256',bytes)).toString('hex');
 const headers={'Content-Type':'text/csv; charset=utf-8','X-Creative-Document-Version':'3','X-Creative-Document-Digest':'a'.repeat(64),'X-Content-SHA256':hash};
 const fetch=vi.fn(async(_url:string,_init:RequestInit)=>new Response(bytes,{headers}));vi.stubGlobal('fetch',fetch);
 const client=creativeClient('project',{sessionToken:'fixture-token'});
 const result=await client.storyboardSheetExport(document);
 expect(fetch.mock.calls[0][0]).toContain('/documents/saved-board/storyboard-sheet-export?expected_version=3');
 expect(fetch.mock.calls[0][1].method).toBe('GET');expect(result.filename).toBe('creative-storyboard-sheet-v3.csv');
 fetch.mockImplementation(async()=>new Response('changed',{headers}));await expect(client.storyboardSheetExport(document)).rejects.toThrow(/校验/);
 await expect(client.storyboardSheetExport({...document,mode:'DIRECTOR'})).rejects.toThrow(/校验/);
});
it('reuses explicit guarded download control for storyboard without automatically exporting',async()=>{
 const request=vi.fn(async()=>({blob:new Blob(['csv']),filename:'board.csv',documentVersion:3,documentDigest:'a'.repeat(64),sha256:'b'.repeat(64)}));
 const current=vi.fn(()=>true);
 const view=render(<DirectorSheetExportPanel sheetKind="STORYBOARD" document={document} available isCurrent={current} request={request} onDenied={vi.fn()} />);
 expect(request).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'导出已保存分镜清单 CSV'}));
 await waitFor(()=>expect(downloadPortableBlob).toHaveBeenCalledTimes(1));
 expect(request).toHaveBeenCalledWith(document,expect.any(AbortSignal));
 view.rerender(<DirectorSheetExportPanel sheetKind="STORYBOARD" document={document} available={false} isCurrent={current} request={request} onDenied={vi.fn()} />);
 fireEvent.click(screen.getByRole('button',{name:'导出已保存分镜清单 CSV'}));expect(request).toHaveBeenCalledTimes(1);
});
