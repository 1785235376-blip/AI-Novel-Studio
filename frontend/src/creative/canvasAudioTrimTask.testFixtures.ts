// Synthetic software receipts only. Native FFmpeg is covered separately by the Python owner test.
// Generate the tiny WAV in memory; no recorded Job, user data, or fixture output is published.
import {createHash} from 'node:crypto';
import {audioAssets,audioBytes,audioCommand,audioJob,audioPreview} from './studioAudioWav.testFixtures';
import type {CanvasReturnBinding} from './studioCanvasReturnBinding';
import type {CanvasDefinition,CanvasViewRecord,CanvasViewHistory} from './studioCanvasViewClient';
import type {MediaCommand} from './studioProductionClient';

const hash=(data:string|Uint8Array)=>createHash('sha256').update(data).digest('hex');
const canonical=(value:unknown):string=>Array.isArray(value)?'['+value.map(canonical).join(',')+']':
  value!==null&&typeof value==='object'?'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical((value as Record<string,unknown>)[k])).join(',')+'}':JSON.stringify(value);
const time='2026-01-01T00:00:00Z';
const sourceBytes=audioBytes(audioCommand('synthetic-source',{in_ms:0,out_ms:1000}));
const source={...audioAssets()[0],filename:'synthetic-card-source.wav',sha256:hash(sourceBytes),size:sourceBytes.length,created_at:time,updated_at:time};
const project=source.novel_id,scope={mode:'local' as const,novel_id:project};
const incarnation='file:00000000-0000-0000-0000-000000000002';
const reference=(asset:typeof source)=>({asset_id:asset.id,version:asset.version,digest:asset.sha256,kind:'audio' as const});
const definition:CanvasDefinition={schema_version:1,title:'Synthetic audio card',viewport:{x:0,y:0,zoom:1},cards:[
  {id:'origin-audio',position:{x:44,y:66},asset:reference(source)},
  {id:'other-audio',position:{x:360,y:120},asset:reference(source)}]};
function record(version:number,definition:CanvasDefinition):CanvasViewRecord{
  return {id:'synthetic-audio-canvas',project_id:project,scope,version,definition,definition_digest:hash(canonical(definition)),created_at:time,updated_at:time,
    reference_states:definition.cards.map(card=>({card_id:card.id,state:'CURRENT_METADATA',filename:card.id==='origin-audio'&&version===2?'reviewed.wav':source.filename})),
    execution_authority:false,binary_content_verified:false,capacity:{history_used:version-1,record_bytes:1000*version}};
}
const canvas=record(1,definition);
const pin={id:source.id,kind:'ASSET' as const,asset_kind:'audio' as const,version:source.version,digest:source.sha256};
const binding:CanvasReturnBinding={contract:'studio-canvas-return/1',project_id:project,scope,incarnation,canvas_id:canvas.id,canvas_version:1,
  canvas_digest:canvas.definition_digest,card_id:'origin-audio',source:pin};
const command:MediaCommand&{canvas_return:CanvasReturnBinding}={...audioCommand('audio-request',{in_ms:550,out_ms:850}),source_snapshots:[pin],canvas_return:binding};
const preview=audioPreview(command);
const projected={...command,source_snapshots:[{...pin,reference_only:true as const}]};
const queued={...audioJob('QUEUED',1,projected),command:projected};
const executedBase=audioJob('AWAITING_REVIEW',3,projected),approvedBase=audioJob('APPROVED',4,projected);
const executed={...executedBase,command:projected,output_candidate:executedBase.output_candidate!};
const approved={...approvedBase,command:projected,output_candidate:approvedBase.output_candidate!};
const bytes=audioBytes(command);
const output={...source,id:approved.output_candidate!.id,version:2,filename:'reviewed.wav',sha256:hash(bytes),size:bytes.length,source_job_id:approved.id};
const returnedDefinition=structuredClone(definition);returnedDefinition.cards[0].asset=reference(output);
const returned=record(2,returnedDefinition),restored=record(3,structuredClone(definition));
const history:CanvasViewHistory={project_id:project,scope,id:canvas.id,incarnation,current_version:2,current_definition_digest:returned.definition_digest,
  items:[canvas,returned].map(row=>({version:row.version,definition:row.definition,definition_digest:row.definition_digest,reference_states:row.reference_states,
    created_at:row.created_at,updated_at:row.updated_at,can_restore:row.version===1})),restore_policy:'CURRENT_METADATA_ONLY',execution_authority:false,binary_content_verified:false};
export default {contract:'synthetic-audio-canvas-software/1',model_inference:false,real_cpu_ffmpeg:false,
  source,output,canvas,command,preview,queued,executed,approved,returned,restored,history,candidate_wav_base64:Buffer.from(bytes).toString('base64')};
