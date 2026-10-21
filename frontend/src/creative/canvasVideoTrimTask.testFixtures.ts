// Software protocol fixtures generated from source, never captured Jobs or media output.
// Candidate bytes are deliberately only an MP4 marker, not a playable video. jsdom tests
// model decoded metadata explicitly. Real codec/frame checks live in the Python CPU test.
import {createHash} from 'node:crypto';
import {compileCanvasVideoTimeline,type CanvasVideoTaskCommand,type CanvasVideoTaskPreview} from './canvasVideoTrimTask';
import type {ProductionJob,ProductionRecipe} from './studioProductionClient';
import type {CanvasDefinition,CanvasViewRecord,CanvasViewHistory} from './studioCanvasViewClient';
import type {StudioAsset} from './studioClient';
const hash=(value:string|Uint8Array)=>createHash('sha256').update(value).digest('hex');
const canonical=(value:unknown):string=>Array.isArray(value)?'['+value.map(canonical).join(',')+']':
 value!==null&&typeof value==='object'?'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical((value as Record<string,unknown>)[key])).join(',')+'}':JSON.stringify(value);
const time='2026-01-01T00:00:00Z',project='synthetic-video-project';
const bytes=new Uint8Array([0,0,0,12,102,116,121,112,109,112,52,50]);
const sourceBytes=new TextEncoder().encode('software-only-video-source');
const source_asset:StudioAsset={id:'synthetic-video-source',novel_id:project,branch_id:null,kind:'video',version:1,
 media_type:'video/mp4',filename:'synthetic-video-source.mp4',size:sourceBytes.length,sha256:hash(sourceBytes),created_at:time,updated_at:time};
const scope={mode:'local' as const,novel_id:project},incarnation='file:00000000-0000-0000-0000-000000000003';
const reference=(asset:StudioAsset)=>({asset_id:asset.id,kind:'video' as const,version:asset.version,digest:asset.sha256});
const definition:CanvasDefinition={schema_version:1,title:'Synthetic video cards',viewport:{x:0,y:0,zoom:1},cards:[
 {id:'origin-video',position:{x:44,y:66},asset:reference(source_asset)},
 {id:'another-video',position:{x:760,y:120},asset:reference(source_asset)}]};
function record(version:number,definition:CanvasDefinition):CanvasViewRecord{return {id:'synthetic-video-canvas',project_id:project,scope,version,definition,
 definition_digest:hash(canonical(definition)),created_at:time,updated_at:time,reference_states:definition.cards.map(card=>({card_id:card.id,state:'CURRENT_METADATA',filename:'synthetic-video.mp4'})),
 execution_authority:false,binary_content_verified:false,capacity:{history_used:version-1,record_bytes:version*1000}};}
const canvas=record(1,definition),pin={id:source_asset.id,kind:'ASSET' as const,asset_kind:'video' as const,version:source_asset.version,digest:source_asset.sha256};
const parameters={in_ms:1000,out_ms:1600},compiled=compileCanvasVideoTimeline(pin,parameters);
const timeline={id:'synthetic-video-timeline',novel_id:project,branch_id:null,title:'Synthetic saved video task',version:1,timeline:compiled,
 timeline_digest:hash(canonical(compiled)),created_at:time,updated_at:time};
const command:CanvasVideoTaskCommand={contract:'studio-canvas-video-trim/1',operation_id:'m9.timeline.multitrack',request_id:'synthetic-video-trim',
 provider_id:null,model_id:null,prompt:'',allow_cloud:false,license_note:'',parameters,source_snapshots:[pin],
 timeline_snapshot:{id:timeline.id,version:1,digest:timeline.timeline_digest},canvas_return:{contract:'studio-canvas-return/1',project_id:project,scope,incarnation,
 canvas_id:canvas.id,canvas_version:1,canvas_digest:canvas.definition_digest,card_id:'origin-video',source:pin}};
const export_profile={preset:'DELIVERY_H264_MP4' as const,video_bitrate_kbps:400,audio_bitrate_kbps:96,crf:23};
const recipeBody={contract:'studio-execution-recipe/1' as const,operation_id:command.operation_id,adapter:'LOCAL_FFMPEG',output_profile:'DELIVERY_H264_MP4',
 timeline:compiled,export_profile,automatic_fallback:false as const};
const execution_recipe:ProductionRecipe={...recipeBody,recipe_digest:hash(canonical(recipeBody))},request_digest=hash(canonical(command));
const previewBody={contract:'studio-canvas-video-preview/1' as const,novel_id:project,branch_id:null,command,request_digest,execution_recipe,
 execution_available:true,automatic_dispatch:false as const,product_acceptance:'LOCAL_REQUIRED' as const};
const preview:CanvasVideoTaskPreview={...previewBody,preview_digest:hash(canonical(previewBody))};
const output={width:640,height:360,fps:'25/1',codec:'h264',duration_ms:600,decoded_frames:15,byte_count:bytes.length,sha256:hash(bytes)};
const measurement:NonNullable<ProductionJob['media_measurement']>={duration_ms:600,width:640,height:360,fps:25,byte_count:bytes.length,video_codec:'h264',audio_codec:'aac',sample_rate:48000,channels:2,
 container:'mp4',profile_validation:'NATIVE_FFPROBE_EXACT',render_profile:'STUDIO_MULTITRACK_LOCAL_FFMPEG_DELIVERY_H264_MP4',export_profile};
function job(status:'QUEUED'|'SUCCEEDED'|'APPROVED',version:number):ProductionJob&{attempt:number;review_state:null;needs_reconciliation:boolean|null;execution_state:string|null}{const rendered=status!=='QUEUED';return {
 contract:'studio-production-job/1',owner:'timeline',id:'synthetic-video-job',novel_id:project,branch_id:null,version,status,request_digest,
 receipt_digest:hash('software-receipt:'+status),attempt:rendered?1:0,created_at:time,updated_at:time,error_code:null,review_state:null,
 cancellation_mode:null,needs_reconciliation:null,execution_state:null,operation_id:command.operation_id,
 output_candidate:rendered?{id:'synthetic-video-result',version:1,digest:output.sha256,kind:'video'}:null,
 timeline_snapshot:command.timeline_snapshot,sources:command.source_snapshots,command:null,provider:null,canvas_video:command,execution_recipe,
 media_measurement:rendered?measurement:null,approved_asset_version:status==='APPROVED'?2:null,request_id:command.request_id,
 product_acceptance:'LOCAL_REQUIRED',automatic_replay:false,remote_compute_may_continue:false};}
const queued=job('QUEUED',1),executedBase=job('SUCCEEDED',3),approvedBase=job('APPROVED',4);
const executed={...executedBase,output_candidate:executedBase.output_candidate!},approved={...approvedBase,output_candidate:approvedBase.output_candidate!};
const formal_asset:StudioAsset&{source_job_id:string}={...source_asset,id:'synthetic-video-result',version:2,filename:'synthetic-reviewed.mp4',size:bytes.length,sha256:output.sha256,source_job_id:approved.id};
const returnedDefinition=structuredClone(definition);returnedDefinition.cards[0].asset=reference(formal_asset);
const returned=record(2,returnedDefinition),restored=record(3,structuredClone(definition));
const history:CanvasViewHistory={project_id:project,scope,id:canvas.id,incarnation,current_version:2,current_definition_digest:returned.definition_digest,
 items:[canvas,returned].map(row=>({version:row.version,definition:row.definition,definition_digest:row.definition_digest,reference_states:row.reference_states,
 created_at:row.created_at,updated_at:row.updated_at,can_restore:row.version===1})),restore_policy:'CURRENT_METADATA_ONLY',execution_authority:false,binary_content_verified:false};
const fixture={contract:'synthetic-video-canvas-software/1',real_cpu_ffmpeg:false,model_called:false,source_asset,timeline,command,canvas,preview,queued,executed,approved,
 get_queued:{...queued,execution_state:'QUEUED',needs_reconciliation:false},list_queued:{items:[{...queued,execution_state:'QUEUED',needs_reconciliation:false}],product_acceptance:'LOCAL_REQUIRED'},
 get:{...approved,execution_state:'APPROVED',needs_reconciliation:false},returned,restored,history,formal_asset,output,candidate_base64:Buffer.from(bytes).toString('base64')};

// JSON wire snapshots have equal values but independent object identities.
export default JSON.parse(JSON.stringify(fixture)) as typeof fixture;
