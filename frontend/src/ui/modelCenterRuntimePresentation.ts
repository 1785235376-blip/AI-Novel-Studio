import type {ModelCenterRuntime,ModelCenterWhisperRuntimeConfiguration} from '../api';

/** Server observations only. Neither HTTP reachability nor a READY model
 * registration can manufacture the host's original private-pipe load witness.
 * Opus can replace the view while keeping this boundary and original actions. */
export function runtimePresentation(runtime:ModelCenterRuntime){
 const state=runtime.instance?.state??'STOPPED';
 const whisper=runtime.runtime_type==='WHISPER_CPP';
 const managed=whisper?runtime.management==='MANAGED':runtime.runtime_type==='LLAMA_CPP'&&runtime.management!=='EXTERNAL';
 const ownedAlive=runtime.instance?.process_alive===true;
 const active=['STARTING','RUNNING'].includes(state)||ownedAlive;
 const loaded=whisper&&state==='RUNNING'&&ownedAlive&&runtime.instance?.http_reachable===true
  &&runtime.instance?.health?.model_loaded===true&&runtime.instance.health.admission==='OWNED_PRIVATE_PIPE'
  &&Array.isArray(runtime.instance.loaded_models)&&runtime.instance.loaded_models.length===1
  &&/^whisper-fixed-[a-f0-9]{32}$/.test(runtime.instance.loaded_models[0]);
 return {state,whisper,managed,active,loaded,loadedModelId:loaded?runtime.instance!.loaded_models![0]:null,
  canStart:managed&&!active&&['STOPPED','FAILED','DEGRADED'].includes(state),
  canStop:managed&&active,
  canConfigure:runtime.runtime_type==='LLAMA_CPP'||runtime.runtime_type==='COMFYUI',
  tone:(state==='FAILED'?'error':state==='STARTING'||state==='DEGRADED'||whisper&&!loaded&&state==='RUNNING'
   ?'warning':state==='RUNNING'||state==='EXTERNAL'?'success':'neutral') as 'success'|'warning'|'error'|'neutral'};
}

/** Project only a closed, server-owned readonly response. Unexpected legacy
 * paths, model hashes or launch parameters are never copied into UI state. */
export function fixedWhisperConfiguration(value:unknown,runtimeId:string):ModelCenterWhisperRuntimeConfiguration{
 if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('MODEL_CENTER_FIXED_CONFIGURATION_INVALID');
 const record=value as Record<string,unknown>;
 const keys=['id','runtime_type','management','base_url','port','configuration_source','read_only','pin_values_exposed'];
 if(Object.keys(record).length!==keys.length||Object.keys(record).some(key=>!keys.includes(key))
  ||record.id!==runtimeId||record.runtime_type!=='WHISPER_CPP'||record.management!=='MANAGED'
  ||record.configuration_source!=='V2_HOST_CONFIGURATION'||record.read_only!==true||record.pin_values_exposed!==false
  ||typeof record.base_url!=='string'||!Number.isInteger(record.port)||Number(record.port)<1024||Number(record.port)>65535)
  throw new Error('MODEL_CENTER_FIXED_CONFIGURATION_INVALID');
 let endpoint:URL;
 try{endpoint=new URL(record.base_url)}catch{throw new Error('MODEL_CENTER_FIXED_CONFIGURATION_INVALID')}
 if(endpoint.protocol!=='http:'||endpoint.hostname!=='127.0.0.1'||endpoint.port!==String(record.port)
  ||endpoint.pathname!=='/'||endpoint.username||endpoint.password||endpoint.search||endpoint.hash)
  throw new Error('MODEL_CENTER_FIXED_CONFIGURATION_INVALID');
 return {id:runtimeId,runtime_type:'WHISPER_CPP',management:'MANAGED',base_url:record.base_url,
  port:Number(record.port),configuration_source:'V2_HOST_CONFIGURATION',read_only:true,pin_values_exposed:false};
}
