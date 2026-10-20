import {buildGraphStarter,graphStarterAvailable} from './graphStarter';
import {graphId,connectionIssue} from './graphDraft';
import {checkedLocalGraphDefinition} from './studioGraphLocalDraft';
import {graphNoteDefinitionBytes} from './graphCanvasNotesHelpers';
import {IMAGE_REFERENCE_PURPOSES,type ImageReferencePurpose} from './studioImageRuntimeContract';
import type {CanvasAssetReference} from './studioCanvasViewClient';
import type {StudioGraphCatalog,StudioGraphDefinition,StudioGraphNode} from './studioGraphTypes';

export type CanvasImageSource={cardId:string;reference:CanvasAssetReference;weight:number;purpose:ImageReferencePurpose};
export type CanvasImageGraphRequest={prompt:string;sources:CanvasImageSource[]};
export type CanvasImageGraphPlan=ReturnType<typeof buildCanvasImageGraphStarter>;
export type CanvasImageGraphHandoff={scope:object;available:boolean;isCurrent:()=>boolean;
 preview:(request:CanvasImageGraphRequest,scope:object)=>CanvasImageGraphPlan;
 apply:(plan:CanvasImageGraphPlan,scope:object,sourceCurrent:()=>boolean)=>boolean;
 graph:{id?:string;version?:number;title:string;prompts:{nodeId:string;text:string}[];references:{nodeId:string;reference:CanvasAssetReference}[]};
 focusPrompt:(nodeId:string,scope:object)=>void};

/** A bounded extension of the original image starter; never an execution owner. */
export function buildCanvasImageGraphStarter(draft:StudioGraphDefinition,catalog:StudioGraphCatalog,request:CanvasImageGraphRequest,makeId=graphId){
 if(draft.schema_version!==4||!graphStarterAvailable('image-draft',draft,catalog)||!catalog.definitions.some(row=>row.id==='image_reference'))throw new Error('请先在原图明确进入空白图片图 v4；这里不会升级或覆盖已有图。');
 if(draft.nodes.length||draft.edges.length)throw new Error('双参考图起步只用于空图，不覆盖已有节点或连接。');
 if(!Array.isArray(request.sources)||request.sources.length!==2||new Set(request.sources.map(row=>row.cardId)).size!==2||new Set(request.sources.map(row=>row.reference.asset_id)).size!==2)throw new Error('请明确选择两张不同素材的已保存图片卡片。');
 if(request.sources.some(row=>!row.cardId||row.reference.kind!=='image'||!Number.isFinite(row.weight)||row.weight<=0||row.weight>1||!IMAGE_REFERENCE_PURPOSES.includes(row.purpose)))throw new Error('图片引用、用途或权重无效。');
 const occupied=new Set([...(draft.presentation?.groups||[]),...(draft.presentation?.notes||[]),...request.sources.map(row=>({id:row.cardId}))].map(row=>row.id));
 const fresh=(prefix='node')=>{const id=makeId(prefix);if(!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id)||occupied.has(id))throw new Error('新节点或连线标识冲突，请重新预览。');occupied.add(id);return id;};
 const next=buildGraphStarter(draft,catalog,'image-draft',request.prompt,fresh);
 const prompt=next.nodes.find(node=>node.definition_id==='image_prompt')!,generator=next.nodes.find(node=>node.definition_id==='image_generate')!;
 prompt.parameters={prompt:''};generator.parameters={...generator.parameters,operation_id:'m5.image.reference',provider_id:'',model_id:'',allow_cloud:false};
 const inputs:StudioGraphNode[]=request.sources.map((source,index)=>({id:fresh('asset'),definition_id:'asset_reference',definition_version:1,enabled:true,position:{x:40,y:360+index*260},parameters:{...source.reference}}));
 const references:StudioGraphNode={id:fresh('references'),definition_id:'image_reference',definition_version:1,enabled:true,position:{x:460,y:360},parameters:{bindings:request.sources.map((source,index)=>({port:index===0?'source_1' as const:'source_2' as const,weight:source.weight,purpose:source.purpose}))}};
 next.nodes.push(...inputs,references);
 const links=[...inputs.map((node,index)=>({source:node.id,output:'asset',target:references.id,input:`source_${index+1}`})),{source:references.id,output:'references',target:prompt.id,input:'references'}];
 for(const link of links){const edge={id:fresh('edge'),source_node_id:link.source,source_port:link.output,target_node_id:link.target,target_port:link.input};const issue=connectionIssue(next,catalog.definitions,edge);if(issue)throw new Error(issue);next.edges.push(edge);}
 if(next.nodes.length>(catalog.media_limits?.nodes||24)||next.edges.length>catalog.limits.edges||(catalog.media_limits?.generators||4)<1||graphNoteDefinitionBytes(next)>catalog.limits.definition_bytes)throw new Error('完整起步图超过原图容量，未加入任何节点。');
 checkedLocalGraphDefinition(next);
 return {definition:next,generatorNodeId:generator.id,promptNodeId:next.nodes.find(node=>node.definition_id==='text_input')!.id,
  sources:request.sources.map((source,index)=>({...structuredClone(source),nodeId:inputs[index].id})),prompt:request.prompt,nodeCount:7,edgeCount:6};
}
