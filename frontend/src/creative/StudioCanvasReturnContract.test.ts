import {afterEach,expect,it,vi} from 'vitest';
import bound from '../../../tests/fixtures/studio_dual_canvas_loop.json';
import legacy from '../../../tests/fixtures/studio_canvas_return_legacy.json';
import {studioProductionClient,type MediaCommand,type ProductionJob} from './studioProductionClient';
import {canvasReturnInCommand,sameCanvasReturn} from './studioCanvasReturnBinding';
const json=(v:unknown)=>new Response(JSON.stringify(v),{headers:{'Content-Type':'application/json'}});
const fresh=(value:typeof bound.command|typeof legacy.command):MediaCommand=>{const c:any=structuredClone(value);if(!c.image_references?.length)delete c.image_references;return c;};
afterEach(()=>vi.unstubAllGlobals());
it('preserves the actual legacy File owner preview/create/get/execute/review receipts without a return field',async()=>{
 const p=legacy,client=studioProductionClient(p.project,{sessionToken:''}),command=fresh(p.command);
 const fetcher=vi.fn(async(url:string,init:RequestInit={})=>json(url.endsWith('/preview')?p.preview:url.endsWith('/execute')?p.executed:url.endsWith('/review')?p.approved:init.method==='POST'?p.queued:p.approved));vi.stubGlobal('fetch',fetcher);
 expect(canvasReturnInCommand((await client.preview(command)).command)).toBeUndefined();const queued=await client.create(command,p.preview.preview_digest);
 const executed=await client.execute(queued);const approved=await client.review(executed);expect((await client.get('image',approved.id)).status).toBe('APPROVED');
 expect(fetcher.mock.calls.every(([,init])=>!init?.body||!String(init?.body).includes('canvas_return'))).toBe(true);
});
it('decodes the actual bound preview and persisted Job without dropping the complete origin',async()=>{
 const client=studioProductionClient(bound.project,{sessionToken:''});vi.stubGlobal('fetch',vi.fn(async(url:string)=>json(url.endsWith('/preview')?bound.preview:bound.approved)));
 expect((await client.preview(fresh(bound.command))).command.canvas_return).toEqual(bound.command.canvas_return);
 expect((await client.get('image',bound.approved.id)).command?.canvas_return).toEqual(bound.command.canvas_return);
});
it.each(['card_id','canvas_digest','incarnation'])('rejects changed %s in preview/create/action receipts',async field=>{
 const client=studioProductionClient(bound.project,{sessionToken:''}),command=fresh(bound.command);
 const mutate=(value:any)=>{const v=structuredClone(value);v.command.canvas_return[field]=field==='canvas_digest'?'f'.repeat(64):field==='incarnation'?'file:00000000-0000-0000-0000-000000000000':'other-card';return v;};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>json(mutate(url.endsWith('/preview')?bound.preview:url.endsWith('/execute')?bound.executed:bound.queued))));
 await expect(client.preview(command)).rejects.toMatchObject({problem:{code:'STUDIO_RESPONSE_INVALID'}});await expect(client.create(command,bound.preview.preview_digest)).rejects.toMatchObject({problem:{code:'STUDIO_RESPONSE_INVALID'}});
 await expect(client.execute(bound.queued as unknown as ProductionJob)).rejects.toMatchObject({problem:{code:'STUDIO_RESPONSE_INVALID'}});
});
it('rejects cross-project bindings before any transport call',async()=>{
 const command=structuredClone(bound.command);command.canvas_return.project_id='other-project';command.canvas_return.scope={mode:'local',novel_id:'other-project'};
 const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);const client=studioProductionClient(bound.project,{sessionToken:''});
 await expect(client.preview(command as unknown as MediaCommand)).rejects.toBeDefined();await expect(client.create(command as unknown as MediaCommand,bound.preview.preview_digest)).rejects.toBeDefined();expect(fetcher).not.toHaveBeenCalled();
});
it.each(['null','version-bool','source-pin','scope-extra','unknown-contract'])('refuses malformed binding %s',mode=>{
 const command:any=structuredClone(bound.command);
 if(mode==='null')command.canvas_return=null;
 if(mode==='version-bool')command.canvas_return.canvas_version=true;
 if(mode==='source-pin')command.canvas_return.source.digest='f'.repeat(64);
 if(mode==='scope-extra')command.canvas_return.scope.credentials='never-accepted';
 if(mode==='unknown-contract')command.canvas_return.contract='unknown/1';
 expect(()=>canvasReturnInCommand(command)).toThrow();
});
it('normalizes absent reference-only source defaults without weakening the complete binding comparison',()=>{
 const original=structuredClone(bound.command),same:any=structuredClone(original);same.canvas_return.source.reference_only=true;
 expect(sameCanvasReturn(original,same)).toBe(true);same.canvas_return.canvas_version++;expect(sameCanvasReturn(original,same)).toBe(false);
});
