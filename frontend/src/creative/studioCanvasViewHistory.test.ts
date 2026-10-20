import { expect,it,vi } from 'vitest';
import { createStudioGraphClient } from './studioGraphClient';
import type { CanvasDefinition } from './studioCanvasViewClient';
const definition:CanvasDefinition={schema_version:1,title:'First',cards:[],viewport:{x:0,y:0,zoom:1}};
const snapshot=(version:number)=>({version,definition:{...definition,title:version===1?'First':'Second'},definition_digest:(version===1?'a':'b').repeat(64),reference_states:[],created_at:'created',updated_at:'updated',can_restore:version===1});
const source=()=>({project_id:'project',scope:{mode:'local',novel_id:'project'},id:'view',incarnation:'incarnation-one',current_version:2,current_definition_digest:'b'.repeat(64),items:[snapshot(1),snapshot(2)],restore_policy:'CURRENT_METADATA_ONLY',execution_authority:false,binary_content_verified:false});
const restored=()=>({project_id:'project',scope:{mode:'local',novel_id:'project'},id:'view',version:3,definition,definition_digest:'a'.repeat(64),reference_states:[],created_at:'created',updated_at:'updated',execution_authority:false,binary_content_verified:false,capacity:{history_used:2,record_bytes:1000}});
function setup(value:any){const json=vi.fn().mockResolvedValue(value);return {json,client:createStudioGraphClient('project',{}, {json}).canvasViews};}
it('queries strict scoped history then captures the reviewed incarnation and target for new-version restore',async()=>{
 const {json,client}=setup(source());const h=await client.history('view');expect(json).toHaveBeenLastCalledWith('/api/projects/project/studio/canvas-views/view/history','GET',undefined,undefined);
 let resolve!:(value:any)=>void;json.mockImplementationOnce(()=>new Promise(r=>{resolve=r}));const pending=client.restore(h,1);h.incarnation='changed';h.items[0].definition.title='mutated';
 expect(json.mock.calls[1][2]).toEqual({expected_version:2,expected_definition_digest:'b'.repeat(64),expected_incarnation:'incarnation-one',restore_version:1,restore_definition_digest:'a'.repeat(64)});
 resolve(restored());const value=await pending;expect(value.version).toBe(3);expect(value.definition.title).toBe('First');
});
it.each(['project','scope','version','duplicate','digest','incarnation','execution','policy','eligible'] as const)('rejects malformed or wrong-owner history %s',async kind=>{
 const h:any=source();if(kind==='project')h.project_id='other';if(kind==='scope')h.scope.mode='collaboration';if(kind==='version')h.current_version=3;if(kind==='duplicate')h.items[1].version=1;if(kind==='digest')h.current_definition_digest='c'.repeat(64);if(kind==='incarnation')h.incarnation='';if(kind==='execution')h.execution_authority=true;if(kind==='policy')h.restore_policy='LATEST_ASSET';if(kind==='eligible')h.items[1].can_restore=true;
 await expect(setup(h).client.history('view')).rejects.toThrow();
});
it('exposes masked unavailable history but never sends its restoration or a current-version restore',async()=>{
 const h:any=source();h.items[0].definition.cards=[{id:'Card',position:{x:0,y:0}}];h.items[0].reference_states=[{card_id:'Card',state:'UNAVAILABLE'}];h.items[0].can_restore=false;
 const {client,json}=setup(h);const parsed=await client.history('view');expect(parsed.items[0].definition.cards[0].asset).toBeUndefined();await expect(client.restore(parsed,1)).rejects.toThrow();await expect(client.restore(parsed,2)).rejects.toThrow();expect(json).toHaveBeenCalledTimes(1);
});
it.each(['version','digest','id','content'] as const)('rejects a restore response that reuses old preview identity or changes %s',async kind=>{
 const {client,json}=setup(source());const h=await client.history('view'),r:any=restored();if(kind==='version')r.version=1;if(kind==='digest')r.definition_digest='c'.repeat(64);if(kind==='id')r.id='other';if(kind==='content')r.definition={...r.definition,title:'unexpected'};json.mockResolvedValueOnce(r);await expect(client.restore(h,1)).rejects.toThrow();
});
