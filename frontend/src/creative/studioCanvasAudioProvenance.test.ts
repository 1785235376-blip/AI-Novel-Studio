import {expect,it} from 'vitest';
import {checkedCanvasAudioProvenance,sameCanvasAudioProvenance} from './studioCanvasAudioProvenance';
import {createStudioGraphClient} from './studioGraphClient';
import {templateGraph,templateOwner} from './workflowTaskTemplate/canvasAudioWorkflowTemplate.testFixtures';
import {captureCanvasAudioWorkflowTemplate} from './workflowTaskTemplate/canvasAudioWorkflowTemplate';
const base=()=>({operation_id:'m8.audio.trim',request_id:'new',canvas_return:{source:{asset_kind:'audio'}},derived_from:{owner:'audio',job_id:'parent',job_version:2,request_id:'old',request_digest:'a'.repeat(64),receipt_digest:null}});
it.each(['owner','job_version','request_id','request_digest','receipt_digest','extra'])('strictly rejects malformed %s in provenance',key=>{
 const c:any=base();c.derived_from[key]=key==='job_version'?0:key==='request_id'?'new':key==='receipt_digest'?'not-digest':'bad';expect(()=>checkedCanvasAudioProvenance(c)).toThrow();
});
it('includes every source field in exact echo equality and refuses unsupported operation',()=>{
 const c=base();expect(sameCanvasAudioProvenance(c,structuredClone(c))).toBe(true);const b=structuredClone(c);b.derived_from.job_version++;expect(sameCanvasAudioProvenance(c,b)).toBe(false);expect(()=>checkedCanvasAudioProvenance({...c,operation_id:'m5.image.i2i'})).toThrow();expect(()=>checkedCanvasAudioProvenance({...c,derived_from:null})).toThrow();
});
it('decodes actual schema3 trim null defaults through original list/get and captures only real range',async()=>{
 const graph=templateGraph();graph.definition.nodes=graph.definition.nodes.slice(0,2);
 const parameters=graph.definition.nodes[1].parameters.parameters!;
 for(const k of ['width','height','steps','seed','cfg','negative_prompt','size','quality','duration_seconds','frame_rate','voice_id','speech_rate'])parameters[k]=null;
 const client=createStudioGraphClient(templateOwner.projectId,{}, {json:async<T,>(url:string)=>structuredClone(url.endsWith('/graphs')?{items:[graph]}:graph) as T});
 const list=await client.list(),read=await client.get(graph.id);expect(list.items[0].definition_digest).toBe(graph.definition_digest);
 expect(captureCanvasAudioWorkflowTemplate(read,'trim',templateOwner).parameters).toEqual({in_ms:100,out_ms:900});
});
it.each([7,'unsupported'])('continues to reject non-null unsupported Graph cfg %s',async value=>{
 const graph=templateGraph();graph.definition.nodes=graph.definition.nodes.slice(0,2);graph.definition.nodes[1].parameters.parameters!.cfg=value;
 const client=createStudioGraphClient(templateOwner.projectId,{}, {json:async<T,>()=>structuredClone(graph) as T});await expect(client.get(graph.id)).rejects.toThrow();
});
