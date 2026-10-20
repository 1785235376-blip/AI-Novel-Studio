import {parseBriefModelCandidate} from './briefModelCandidate';
import type {BriefText} from './personalSkillBrief';
import type {StudioGraphRecord,StudioGraphRun} from '../creative/studioGraphTypes';
export type GraphBriefSource={kind:'PERSONAL_REVIEWED_GRAPH_TEXT_REFERENCE';project_id:string;graph_id:string;graph_version:number;graph_digest:string;run_id:string;run_version:number;review_node_id:string;text_sha256:string;origin:'USER_SUPPLIED'|'MANUAL'|'MODEL_PROPOSAL';publisher_verified:false;execution_authority:false;content_may_be_edited:true};
export type ReviewedGraphBrief={text:BriefText;source:GraphBriefSource};
export type BriefGraphReader={list?:()=>Promise<{items:StudioGraphRecord[]}>;runs?:(id:string)=>Promise<{items:StudioGraphRun[]}>;get:(id:string)=>Promise<StudioGraphRecord>;getRun:(id:string)=>Promise<StudioGraphRun>};
const fail=():never=>{throw new Error('需要当前项目中未过期、成功完成的 schema 3 创作图及原人工审核节点；来源或审核回执已改变时请重新读取。');};
export async function readReviewedGraphBrief(client:BriefGraphReader,runId:string,nodeId:string):Promise<ReviewedGraphBrief>{
 if(!/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(runId)||!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(nodeId))fail();
 const first=await client.getRun(runId),graph=await client.get(first.graph_id),run=await client.getRun(runId),latest=await client.get(first.graph_id);
 if(first.id!==runId||run.id!==runId||run.version!==first.version||graph.id!==run.graph_id||latest.id!==graph.id||graph.version!==latest.version||graph.definition_digest!==latest.definition_digest||graph.version!==run.graph_version||graph.definition.schema_version!==3||run.project_id!==graph.project_id||JSON.stringify(run.scope)!==JSON.stringify(graph.scope)||JSON.stringify(latest.scope)!==JSON.stringify(graph.scope)||run.stale||run.status!=='SUCCEEDED'||run.reviewed!==true)fail();
 const node=graph.definition.nodes.find(n=>n.id===nodeId),state=run.node_states[nodeId];
 if(!node||!node.enabled||node.definition_id!=='human_review'||state?.status!=='SUCCEEDED'||!state.output?.reviewed_draft||state.error)fail();
 const draft=state.output!.reviewed_draft!,text=parseBriefModelCandidate(draft.text);
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(draft.text)))).map(x=>x.toString(16).padStart(2,'0')).join('');
 return {text,source:{kind:'PERSONAL_REVIEWED_GRAPH_TEXT_REFERENCE',project_id:run.project_id,graph_id:graph.id,graph_version:graph.version,graph_digest:graph.definition_digest,run_id:run.id,run_version:run.version,review_node_id:nodeId,text_sha256:digest,origin:draft.origin,publisher_verified:false,execution_authority:false,content_may_be_edited:true}};
}
