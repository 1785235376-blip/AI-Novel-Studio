import {buildGraphStarter,graphStarterAvailable} from './graphStarter';
import {graphId} from './graphDraft';
import {checkedLocalGraphDefinition} from './studioGraphLocalDraft';
import {graphNoteDefinitionBytes} from './graphCanvasNotesHelpers';
import type {StudioGraphCatalog,StudioGraphDefinition} from './studioGraphTypes';

export const IMAGE_OUTPUT_COUNTS=[2,3,4] as const;
export type ImageOutputCount=typeof IMAGE_OUTPUT_COUNTS[number];
export type ImageOutputRequest={prompt:string;supplements:string[];count:ImageOutputCount};
export type ImageOutputPlan=ReturnType<typeof buildImageOutputStarter>;
export type ImageOutputHandoff={scope:object;available:boolean;isCurrent:()=>boolean;existingGenerators:number;
 preview:(request:ImageOutputRequest,scope:object)=>ImageOutputPlan;
 apply:(plan:ImageOutputPlan,scope:object,sourceCurrent:()=>boolean)=>boolean;
 cancel:(plan:ImageOutputPlan,scope:object)=>void};

/** Only original image starter branches. This is authoring, never a batch executor. */
export function buildImageOutputStarter(draft:StudioGraphDefinition,catalog:StudioGraphCatalog,request:ImageOutputRequest,makeId=graphId){
 if(draft.schema_version!==4||!graphStarterAvailable('image-draft',draft,catalog)||draft.nodes.length||draft.edges.length)throw new Error('请在原图明确采用空白图片图 v4；不会升级或覆盖已有图。');
 if(!IMAGE_OUTPUT_COUNTS.includes(request.count)||!Array.isArray(request.supplements)||request.supplements.length!==request.count)throw new Error('请明确选择2–4份产物，并核对每份补充说明。');
 if(typeof request.prompt!=='string'||!request.prompt.trim()||Array.from(request.prompt).length>8000||Array.from(request.supplements).some(text=>typeof text!=='string'||Array.from(text).length>2000))throw new Error('作者输入须为1–8000字符，每份补充说明最多2000字符。');
 const limits=catalog.media_limits;
 if(!limits||request.count>limits.generators||request.count*4>limits.nodes||request.count*3>catalog.limits.edges)throw new Error('产物数量超过原图生成节点或连接预算，未建立任何分支。');
 const occupied=new Set([...(draft.presentation?.groups||[]),...(draft.presentation?.notes||[])].map(row=>row.id));
 const fresh=(prefix='node')=>{const id=makeId(prefix);if(!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id)||occupied.has(id))throw new Error('节点或连接标识冲突，请重新预览。');occupied.add(id);return id;};
 const next:StudioGraphDefinition={...structuredClone(draft),nodes:[],edges:[]};
 const outputs=request.supplements.map((supplement,index)=>{
  const prompt=supplement.trim()?request.prompt+'\n\n'+supplement:request.prompt;
  const branch=buildGraphStarter({...structuredClone(draft),nodes:[],edges:[]},catalog,'image-draft',prompt,fresh);
  const promptNode=branch.nodes.find(row=>row.definition_id==='image_prompt')!,generator=branch.nodes.find(row=>row.definition_id==='image_generate')!,input=branch.nodes.find(row=>row.definition_id==='text_input')!,review=branch.nodes.find(row=>row.definition_id==='media_review')!;
  promptNode.parameters={prompt:''};
  for(const node of branch.nodes)node.position={...node.position,y:node.position.y+index*320};
  next.nodes.push(...branch.nodes);next.edges.push(...branch.edges);
  return {number:index+1,prompt,supplement,inputNodeId:input.id,generatorNodeId:generator.id,reviewNodeId:review.id};
 });
 const definition=checkedLocalGraphDefinition(next);
 if(graphNoteDefinitionBytes(definition)>catalog.limits.definition_bytes)throw new Error('完整产物草稿超过原图字节容量，未建立任何分支。');
 return {definition,outputs,count:request.count,nodeCount:definition.nodes.length,edgeCount:definition.edges.length};
}
