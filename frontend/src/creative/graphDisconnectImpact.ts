import type { StudioGraphCatalogDefinition,StudioGraphDefinition } from './studioGraphTypes';
/** Structural reachability only; not a model judgment or run/cost prediction. */
export function graphDisconnectImpact(source:StudioGraphDefinition,edgeId:string,definitions:readonly StudioGraphCatalogDefinition[]){
 const edge=source.edges.find(row=>row.id===edgeId);if(!edge)throw new Error('连接已经变化。');
 const definition={...structuredClone(source),edges:source.edges.filter(row=>row.id!==edgeId).map(row=>({...row}))};
 const visited=new Set<string>(),pending=[edge.target_node_id];
 while(pending.length){const id=pending.pop()!;if(visited.has(id))continue;visited.add(id);pending.push(...source.edges.filter(row=>row.source_node_id===id).map(row=>row.target_node_id));}
 const missing=(graph:StudioGraphDefinition)=>graph.nodes.filter(node=>node.enabled).flatMap(node=>{
  const spec=definitions.find(value=>value.id===node.definition_id);if(!spec)throw new Error('节点目录不完整。');
  return spec.inputs.filter(port=>port.required&&!graph.edges.some(link=>link.target_node_id===node.id&&link.target_port===port.id&&graph.nodes.some(parent=>parent.id===link.source_node_id&&parent.enabled))).map(port=>`${node.id}.${port.id}`);
 });
 const before=new Set(missing(source));
 return{edge:{...edge},definition,affected:source.nodes.filter(node=>visited.has(node.id)).map(node=>node.id),newMissing:missing(definition).filter(value=>!before.has(value)),unaffected:source.nodes.filter(node=>!visited.has(node.id)).map(node=>node.id)};
}
