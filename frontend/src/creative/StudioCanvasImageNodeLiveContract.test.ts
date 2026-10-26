// Real API + Mock provider: responses captured from original app.main (backend 8ea45399, File storage) over loopback HTTP.
import {afterEach,expect,it,vi} from 'vitest';
import live from '../../../tests/fixtures/studio_dci_live_image_node.json';
import {verifyCanvasImageNodePrompt} from './canvasImageNode';
import {studioProductionClient,type MediaCommand,type ProductionJob} from './studioProductionClient';
const json=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json'}});
afterEach(()=>vi.unstubAllGlobals());
const L=live.api as unknown as Record<string,{status:number;body:any}>;
const project=L.novel.body.id as string;
// The sent request: the recorded command minus the backend's normalized null parameters.
const command=()=>{const c=structuredClone(L.preview.body.command);c.parameters=Object.fromEntries(Object.entries(c.parameters).filter(([,v])=>v!==null));return c as MediaCommand;};
function replay(map:(url:string,init:RequestInit)=>unknown){const f=vi.fn(async(url:string,init:RequestInit={})=>json(map(url,init)));vi.stubGlobal('fetch',f);return f;}
it('admits the real formal canvas_image_node job on list/get/create/execute/review without dropping provenance',async()=>{
 const c=studioProductionClient(project,{sessionToken:''});
 replay((url,init)=>url.endsWith('/preview')?L.preview.body:url.endsWith('/execute')?L.execute.body:url.endsWith('/review')?L.review.body:init.method==='POST'?L.create.body:url.includes('/jobs/image/')?L['get.final'].body:L.list.body);
 const pv=await c.preview(command());expect(pv.command.canvas_image_node).toEqual(L.preview.body.command.canvas_image_node);
 const q=await c.create(command(),pv.preview_digest);expect(q.command?.canvas_image_node).toEqual(L.create.body.command.canvas_image_node);
 const listed=await c.list();expect(listed.find(j=>j.id===q.id)?.command?.canvas_image_node).toEqual(L.create.body.command.canvas_image_node);
 const ex=await c.execute(q);expect(ex.status).toBe('AWAITING_REVIEW');
 const ap=await c.review(ex);expect(ap.status).toBe('APPROVED');expect(ap.command?.canvas_image_node).toEqual(L.create.body.command.canvas_image_node);
 expect((await c.get('image',q.id)).command?.canvas_image_node?.node_id).toBe('generation-node-one');
});
it('keeps paged list working with the formal field',async()=>{
 const c=studioProductionClient(project,{sessionToken:''});replay(()=>L['list.page'].body);
 const page=await c.listPage({owner:'image',limit:1,offset:0});expect(page.items).toHaveLength(1);expect(page.paging?.total).toBe(1);
});
it('rejects a tampered prompt digest / unknown binding field / mixed media field from the real response',async()=>{
 const c=studioProductionClient(project,{sessionToken:''});
 for(const mutate of [(v:any)=>{v.command.canvas_image_node.extra='x'},(v:any)=>{v.command.allow_cloud=true},(v:any)=>{v.command.canvas_return={}},(v:any)=>{v.command.canvas_image_node.project_id='other-project'}]){
  const bad=structuredClone(L['get.final'].body);mutate(bad);replay(()=>bad);
  await expect(c.get('image',bad.id)).rejects.toMatchObject({problem:{code:expect.stringMatching(/STUDIO_RESPONSE_INVALID|STUDIO_CANVAS_IMAGE_NODE_INVALID/)}});
 }
});
it('verifies the real prompt digest and rejects a tampered one',async()=>{
 await expect(verifyCanvasImageNodePrompt(L['get.final'].body.command)).resolves.toBeUndefined();
 const bad=structuredClone(L['get.final'].body.command);bad.canvas_image_node.prompt_digest='f'.repeat(64);
 await expect(verifyCanvasImageNodePrompt(bad)).rejects.toMatchObject({problem:{code:'STUDIO_CANVAS_IMAGE_NODE_INVALID'}});
 const edited=structuredClone(L['get.final'].body.command);edited.prompt='changed after review';
 await expect(verifyCanvasImageNodePrompt(edited)).rejects.toBeDefined();
});
it('rejects an action receipt whose node binding changed (ownership consistency)',async()=>{
 const c=studioProductionClient(project,{sessionToken:''});const bad=structuredClone(L.execute.body);bad.command.canvas_image_node.node_id='another-node';replay(()=>bad);
 await expect(c.execute(L.create.body as unknown as ProductionJob)).rejects.toBeDefined();
});
it('old jobs without the field remain compatible',async()=>{
 const c=studioProductionClient(project,{sessionToken:''});const old=structuredClone(L['get.final'].body);delete old.command.canvas_image_node;replay(()=>old);
 expect((await c.get('image',old.id)).command?.canvas_image_node).toBeUndefined();
});
