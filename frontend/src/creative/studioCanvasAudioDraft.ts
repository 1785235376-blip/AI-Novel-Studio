import {ApiError} from '../api';
import {checkedCanvasAudioTaskEnvelope,type CanvasAudioTaskEnvelope} from './canvasAudioTaskEnvelope';
import {checkedCanvasAudioProvenance,type CanvasAudioWorkflowTemplateRef,type FailedCanvasAudioOrigin} from './studioCanvasAudioProvenance';
import {canvasReturnInCommand,type CanvasReturnBinding} from './studioCanvasReturnBinding';
import type {MediaCommand,ProductionSource} from './studioProductionClient';
import type {StudioTimeline} from './studioTimelineTypes';

export type CanvasAudioDraftInput={contract:'studio-canvas-audio-draft/1';request_id:string;parameters:CanvasAudioTaskEnvelope;
 source_snapshots:ProductionSource[];canvas_return:CanvasReturnBinding;license_note:string;template_ref?:CanvasAudioWorkflowTemplateRef;derived_from?:FailedCanvasAudioOrigin};
export type SavedCanvasAudioDraft=CanvasAudioDraftInput&{timeline_snapshot:{id:string;version:number;digest:string}};
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const request=/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/,identity=/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/,hex=/^[a-f0-9]{64}$/;
export const audioDraftIdentity=(v:unknown)=>JSON.stringify(v,(_k,x)=>object(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
function invalid():never{throw new ApiError({status:422,code:'STUDIO_CANVAS_AUDIO_DRAFT_INVALID',message:'音频草稿输入或原版本已变化，请重新读取核对。'});}
export function checkedCanvasAudioDraftInput(value:unknown):CanvasAudioDraftInput{
 if(!object(value)||Object.keys(value).some(k=>!['contract','request_id','parameters','source_snapshots','canvas_return','license_note','template_ref','derived_from'].includes(k))
  ||value.contract!=='studio-canvas-audio-draft/1'||typeof value.request_id!=='string'||!request.test(value.request_id)
  ||!Array.isArray(value.source_snapshots)||value.source_snapshots.length!==1||!object(value.source_snapshots[0])
  ||Object.keys(value.source_snapshots[0]).some(k=>!['id','kind','version','digest','asset_kind'].includes(k)))invalid();
 const parameters=checkedCanvasAudioTaskEnvelope(value.parameters);if(!parameters)invalid();
 const license=value.license_note===undefined?'':value.license_note;if(typeof license!=='string'||license.length>2000)invalid();
 const command={operation_id:'m8.audio.trim',request_id:value.request_id,provider_id:null,model_id:null,prompt:'',allow_cloud:false,license_note:license,
  parameters,source_snapshots:value.source_snapshots,canvas_return:value.canvas_return,
  ...(Object.hasOwn(value,'template_ref')?{template_ref:value.template_ref}:{}),...(Object.hasOwn(value,'derived_from')?{derived_from:value.derived_from}:{})};
 const binding=canvasReturnInCommand(command);if(!binding||binding.source.asset_kind!=='audio')invalid();checkedCanvasAudioProvenance(command);
 return structuredClone({...value,parameters,source_snapshots:[binding.source],canvas_return:binding,license_note:license}) as CanvasAudioDraftInput;
}
export function canvasAudioDraftCommand(input:CanvasAudioDraftInput):MediaCommand{
 const v=Object.hasOwn(input,'timeline_snapshot')?checkedSavedCanvasAudioDraft(input):checkedCanvasAudioDraftInput(input);
 return {operation_id:'m8.audio.trim',request_id:v.request_id,provider_id:null,model_id:null,prompt:'',allow_cloud:false,license_note:v.license_note,
  parameters:{...v.parameters},source_snapshots:structuredClone(v.source_snapshots),canvas_return:structuredClone(v.canvas_return),
  ...(v.template_ref?{template_ref:structuredClone(v.template_ref)}:{}),...(v.derived_from?{derived_from:structuredClone(v.derived_from)}:{})};
}
export function canvasAudioDraftFromCommand(c:MediaCommand):CanvasAudioDraftInput{
 if(c.operation_id!=='m8.audio.trim'||c.provider_id!=null||c.model_id!=null||c.prompt!==''||c.allow_cloud!==false)invalid();
 canvasReturnInCommand(c);checkedCanvasAudioProvenance(c);
 return checkedCanvasAudioDraftInput({contract:'studio-canvas-audio-draft/1',request_id:c.request_id,parameters:c.parameters,
  source_snapshots:c.source_snapshots.map(s=>Object.fromEntries(Object.entries(s).filter(([k])=>k!=='reference_only'))),
  canvas_return:c.canvas_return,license_note:c.license_note,...(c.template_ref?{template_ref:c.template_ref}:{}),...(c.derived_from?{derived_from:c.derived_from}:{})});
}
export function checkedSavedCanvasAudioDraft(value:unknown):SavedCanvasAudioDraft{
 if(!object(value))invalid();const {timeline_snapshot,...rest}=value;const input=checkedCanvasAudioDraftInput(rest);
 if(!object(timeline_snapshot)||Object.keys(timeline_snapshot).length!==3||!['id','version','digest'].every(k=>Object.hasOwn(timeline_snapshot,k))
  ||typeof timeline_snapshot.id!=='string'||!identity.test(timeline_snapshot.id)||!Number.isSafeInteger(timeline_snapshot.version)||Number(timeline_snapshot.version)<1||typeof timeline_snapshot.digest!=='string'||!hex.test(timeline_snapshot.digest))invalid();
 return {...input,timeline_snapshot:structuredClone(timeline_snapshot)} as SavedCanvasAudioDraft;
}
export function compileCanvasAudioDraftTimeline(input:CanvasAudioDraftInput):StudioTimeline{
 const v=Object.hasOwn(input,'timeline_snapshot')?checkedSavedCanvasAudioDraft(input):checkedCanvasAudioDraftInput(input),p=v.parameters;
 return {schema_version:3,media_kind:'AUDIO',duration_ms:p.out_ms-p.in_ms,tracks:[{id:'canvas-audio-track',kind:'AUDIO',order:0,role:'DIALOGUE',muted:false,gain_db:0,
  clips:[{id:'canvas-audio-clip',source_snapshot:{...v.source_snapshots[0],asset_kind:'audio'},start_ms:0,in_ms:p.in_ms,out_ms:p.out_ms,
   speed_num:1,speed_den:1,muted:false,gain_db:p.gain_db??0,fade_in_ms:p.fade_in_ms??0,fade_out_ms:p.fade_out_ms??0}]}]};
}
