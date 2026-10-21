import { ApiError } from '../api';
export type FailedCanvasAudioOrigin = { owner:'audio'; job_id:string; job_version:number; request_id:string; request_digest:string; receipt_digest:string|null };
export type CanvasAudioWorkflowTemplateRef = { contract:'studio-canvas-audio-template/1'; graph_id:string; graph_version:number; definition_digest:string; execution_digest:string; node_id:string; parameters:{in_ms:number;out_ms:number} };
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const id=(v:unknown)=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(v);
const graphName=(v:unknown)=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,239}$/.test(v);
const request=(v:unknown)=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(v);
const hex=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const version=(v:unknown)=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=1;
const exact=(v:Record<string,unknown>,keys:string[])=>Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
function invalid():never{throw new ApiError({status:422,code:'STUDIO_CANVAS_AUDIO_PROVENANCE_INVALID',message:'任务派生来源或模板版本不完整，请重新核对原记录。'});}
export function checkedCanvasAudioProvenance(command:unknown){
 if(!object(command))invalid();
 if(!Object.hasOwn(command,'derived_from')&&!Object.hasOwn(command,'template_ref'))return;
 if(command.operation_id!=='m8.audio.trim'||!object(command.canvas_return)||!object(command.canvas_return.source)||command.canvas_return.source.asset_kind!=='audio')invalid();
 if(Object.hasOwn(command,'derived_from')){
  const p=command.derived_from;
  if(!object(p)||!exact(p,['owner','job_id','job_version','request_id','request_digest','receipt_digest'])||p.owner!=='audio'||!id(p.job_id)||!version(p.job_version)||!request(p.request_id)||p.request_id===command.request_id||!hex(p.request_digest)||p.receipt_digest!==null&&!hex(p.receipt_digest))invalid();
 }
 if(Object.hasOwn(command,'template_ref')){
  const p=command.template_ref;
  if(!object(p)||!exact(p,['contract','graph_id','graph_version','definition_digest','execution_digest','node_id','parameters'])||p.contract!=='studio-canvas-audio-template/1'||!graphName(p.graph_id)||!version(p.graph_version)||!hex(p.definition_digest)||!hex(p.execution_digest)||!graphName(p.node_id)||!object(p.parameters))invalid();
  const r=p.parameters;
  if(!exact(r,['in_ms','out_ms'])||![r.in_ms,r.out_ms].every(v=>typeof v==='number'&&Number.isSafeInteger(v))||(r.in_ms as number)<0||(r.out_ms as number)>600000||(r.out_ms as number)-(r.in_ms as number)<=0||(r.out_ms as number)-(r.in_ms as number)>120000)invalid();
 }
}
const canonical=(v:unknown):string=>JSON.stringify(v,(_k,x)=>object(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
export const sameCanvasAudioProvenance=(a:unknown,b:unknown)=>{
 checkedCanvasAudioProvenance(a);checkedCanvasAudioProvenance(b);
 const left=a as Record<string,unknown>,right=b as Record<string,unknown>;
 return ['derived_from','template_ref'].every(k=>Object.hasOwn(left,k)===Object.hasOwn(right,k)&&canonical(left[k])===canonical(right[k]));
};
