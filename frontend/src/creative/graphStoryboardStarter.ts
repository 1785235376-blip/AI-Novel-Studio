import { graphId, connectionIssue, graphCatalogForSchema } from './graphDraft';
import { checkedStoryboardReceipt, type StoryboardReceipt } from './studioStoryboardContract';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphNode } from './studioGraphTypes';
/** Assemble existing exact source pins; never invent shots or relax review admission. */
export const MAX_STORYBOARD_VIDEO_BRANCHES = 4;
export function buildStoryboardVideoStarter(draft:StudioGraphDefinition,catalog:StudioGraphCatalog,value:StoryboardReceipt,shotId:string,makeId=graphId):StudioGraphDefinition{
 return buildStoryboardVideoBranches(draft,catalog,value,[shotId],makeId);
}
export function buildStoryboardVideoBranches(draft:StudioGraphDefinition,catalog:StudioGraphCatalog,value:StoryboardReceipt,shotIds:readonly string[],makeId=graphId):StudioGraphDefinition{
 if(draft.schema_version!==5||catalog.capabilities.video_graph!==true)throw new Error('先明确选择原视频图 v5；不会自动升级或转换图。');
 if(draft.nodes.length||draft.edges.length)throw new Error('分镜起步方案只加入空图。');
 const receipt=checkedStoryboardReceipt(value);
 if(!Array.isArray(shotIds)||!shotIds.length||shotIds.length>MAX_STORYBOARD_VIDEO_BRANCHES||new Set(shotIds).size!==shotIds.length)throw new Error('请明确选择 1–4 个不重复的原镜头；不会自动截断。');
 const shots=receipt.shots.filter(row=>shotIds.includes(row.shot_id)).sort((a,b)=>a.shot.number-b.shot.number);
 if(!receipt.approved||shots.length!==shotIds.length)throw new Error('请选择当前已审核分镜中的确切镜头。');
 const definitions=graphCatalogForSchema(catalog.definitions,5);
 if(!['storyboard_plan','storyboard_shot','video_generate','media_review'].every(id=>definitions.some(row=>row.id===id)))throw new Error('当前目录缺少原视频工作流节点。');
 const nodes:StudioGraphNode[]=[
  {id:makeId('storyboard'),definition_id:'storyboard_plan',definition_version:1,enabled:true,position:{x:40,y:80},parameters:{document_snapshot:{...receipt.document_snapshot}}},
 ];
 for(const [index,shot] of shots.entries()){
 const y=80+index*240;
 nodes.push(
  {id:makeId('shot'),definition_id:'storyboard_shot',definition_version:1,enabled:true,position:{x:460,y},parameters:{shot_id:shot.shot_id,shot_version:shot.shot_version,shot_digest:shot.shot_digest}},
  {id:makeId('video'),definition_id:'video_generate',definition_version:1,enabled:true,position:{x:880,y},parameters:{operation_id:'m7.video.t2v',provider_id:'',model_id:'',prompt:'',parameters:{},allow_cloud:false,license_note:'',bind_shot:true}},
  {id:makeId('review'),definition_id:'media_review',definition_version:1,enabled:true,position:{x:1300,y},parameters:{}},
 );
 }
 if(new Set(nodes.map(node=>node.id)).size!==nodes.length)throw new Error('起步节点标识重复，未应用。');
 const next:StudioGraphDefinition={...structuredClone(draft),nodes,edges:[]};
 for(let shotIndex=1;shotIndex<nodes.length;shotIndex+=3){
 for(const [source,target,output,input] of [[0,shotIndex,'storyboard','storyboard'],[shotIndex,shotIndex+1,'shot','shot'],[shotIndex+1,shotIndex+2,'candidate','candidate']] as const){
  const edge={id:makeId('edge'),source_node_id:nodes[source].id,source_port:output,target_node_id:nodes[target].id,target_port:input};
  if(nodes.some(node=>node.id===edge.id)||next.edges.some(row=>row.id===edge.id))throw new Error('起步连线标识重复，未应用。');
  const issue=connectionIssue(next,catalog.definitions,edge);if(issue)throw new Error(issue);next.edges.push(edge);
 }
 }
 // Original Add Node also retains incomplete provider/model fields locally.
 // Original Save/execution validates the filled configuration and current source again.
 return next;
}
