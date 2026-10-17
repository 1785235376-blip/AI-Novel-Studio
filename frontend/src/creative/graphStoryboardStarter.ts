import { graphId, connectionIssue, graphCatalogForSchema } from './graphDraft';
import { checkedStoryboardReceipt, type StoryboardReceipt } from './studioStoryboardContract';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphNode } from './studioGraphTypes';
/** Assemble existing exact source pins; never invent shots or relax review admission. */
export function buildStoryboardVideoStarter(draft:StudioGraphDefinition,catalog:StudioGraphCatalog,value:StoryboardReceipt,shotId:string,makeId=graphId):StudioGraphDefinition{
 if(draft.schema_version!==5||catalog.capabilities.video_graph!==true)throw new Error('先明确选择原视频图 v5；不会自动升级或转换图。');
 if(draft.nodes.length||draft.edges.length)throw new Error('分镜起步方案只加入空图。');
 const receipt=checkedStoryboardReceipt(value),shot=receipt.shots.find(row=>row.shot_id===shotId);
 if(!receipt.approved||!shot)throw new Error('请选择当前已审核分镜中的确切镜头。');
 const definitions=graphCatalogForSchema(catalog.definitions,5);
 if(!['storyboard_plan','storyboard_shot','video_generate','media_review'].every(id=>definitions.some(row=>row.id===id)))throw new Error('当前目录缺少原视频工作流节点。');
 const nodes:StudioGraphNode[]=[
  {id:makeId('storyboard'),definition_id:'storyboard_plan',definition_version:1,enabled:true,position:{x:40,y:80},parameters:{document_snapshot:{...receipt.document_snapshot}}},
  {id:makeId('shot'),definition_id:'storyboard_shot',definition_version:1,enabled:true,position:{x:460,y:80},parameters:{shot_id:shot.shot_id,shot_version:shot.shot_version,shot_digest:shot.shot_digest}},
  {id:makeId('video'),definition_id:'video_generate',definition_version:1,enabled:true,position:{x:880,y:80},parameters:{operation_id:'m7.video.t2v',provider_id:'',model_id:'',prompt:'',parameters:{},allow_cloud:false,license_note:'',bind_shot:true}},
  {id:makeId('review'),definition_id:'media_review',definition_version:1,enabled:true,position:{x:1300,y:80},parameters:{}},
 ];
 if(new Set(nodes.map(node=>node.id)).size!==4)throw new Error('起步节点标识重复，未应用。');
 const next:StudioGraphDefinition={...structuredClone(draft),nodes,edges:[]};
 for(const [source,target,output,input] of [[0,1,'storyboard','storyboard'],[1,2,'shot','shot'],[2,3,'candidate','candidate']] as const){
  const edge={id:makeId('edge'),source_node_id:nodes[source].id,source_port:output,target_node_id:nodes[target].id,target_port:input};
  const issue=connectionIssue(next,catalog.definitions,edge);if(issue)throw new Error(issue);next.edges.push(edge);
 }
 // Original Add Node also retains incomplete provider/model fields locally.
 // Original Save/execution validates the filled configuration and current source again.
 return next;
}
