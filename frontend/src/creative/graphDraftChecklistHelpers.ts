import { checkedStudioGraphDraft } from './studioGraphClient';
import { connectionIssue, graphCatalogForSchema } from './graphDraft';
import type { StudioGraphCatalogDefinition, StudioGraphDefinition } from './studioGraphTypes';
export type GraphDraftHint = { key:string; nodeId?:string; message:string; kind:'configuration'|'connection'|'execution' };
/** Read-only authoring guidance. The existing client decoder remains the sole shape verdict. */
export function graphDraftChecklist(draft:StudioGraphDefinition,catalog:readonly StudioGraphCatalogDefinition[]){
 let contractValid=false;
 try{checkedStudioGraphDraft(draft);contractValid=true;}catch{/* Never expose decoder payload or source text. */}
 const hints:GraphDraftHint[]=[];
 const definitions=graphCatalogForSchema(catalog,draft.schema_version);
 for(const node of draft.nodes){
  const parameters=node.parameters;
  if(['image_generate','image_upscale','video_generate','media_generate'].includes(node.definition_id)
    && !(node.definition_id==='media_generate'&&parameters.operation_id==='m8.audio.trim')){
   for(const [field,label] of [['provider_id','服务商'],['model_id','模型']] as const)
    if(typeof parameters[field]!=='string'||!parameters[field]?.trim())hints.push({key:`${node.id}:${field}`,nodeId:node.id,kind:'configuration',message:`请明确配置${label}；不会替你选择或转云端。`});
  }
  // Missing execution inputs do not make an intentionally disconnected draft unsavable.
  if(node.enabled)for(const port of definitions.find(row=>row.id===node.definition_id)?.inputs||[]){
   if(port.required&&!draft.edges.some(edge=>edge.target_node_id===node.id&&edge.target_port===port.id))
    hints.push({key:`${node.id}:input:${port.id}`,nodeId:node.id,kind:'execution',message:`运行前需要连接 ${port.id} 输入（${port.type}）；空接线仍可作为草稿编辑。`});
  }
 }
 for(const edge of draft.edges){
  const issue=connectionIssue({...draft,edges:draft.edges.filter(row=>row!==edge)},catalog,edge);
  if(issue)hints.push({key:`edge:${edge.id}`,nodeId:draft.nodes.some(row=>row.id===edge.target_node_id)?edge.target_node_id:undefined,kind:'connection',message:issue});
 }
 return {contractValid,hints};
}
