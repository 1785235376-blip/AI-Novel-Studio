import { graphMissingInputs, graphReachableNodes } from './graphNodeStateImpact';
import type { StudioGraphCatalogDefinition,StudioGraphDefinition } from './studioGraphTypes';
/** Structural reachability only; not a model judgment or run/cost prediction. */
export function graphDisconnectImpact(source:StudioGraphDefinition,edgeId:string,definitions:readonly StudioGraphCatalogDefinition[]){
 const edge=source.edges.find(row=>row.id===edgeId);if(!edge)throw new Error('连接已经变化。');
 const definition={...structuredClone(source),edges:source.edges.filter(row=>row.id!==edgeId).map(row=>({...row}))};
 const affected=graphReachableNodes(source,[edge.target_node_id]);
 const before=new Set(graphMissingInputs(source,definitions));
 return{edge:{...edge},definition,affected:affected,newMissing:graphMissingInputs(definition,definitions).filter(value=>!before.has(value)),unaffected:source.nodes.filter(node=>!affected.includes(node.id)).map(node=>node.id)};
}
