// @vitest-environment jsdom
import {act} from 'react';
import {createRoot,Root} from 'react-dom/client';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {ApiError,api} from '../api';
import {ModelCenter} from './ModelCenter';

(globalThis as typeof globalThis & {IS_REACT_ACT_ENVIRONMENT:boolean}).IS_REACT_ACT_ENVIRONMENT=true;

describe('ModelCenter',()=>{
 let host:HTMLDivElement,root:Root,mounted=false;
 afterEach(()=>{if(mounted)act(()=>root.unmount());host?.remove();vi.restoreAllMocks();mounted=false});
 it('shows verified models, runtime state, and the registered video pipeline',async()=>{
  vi.spyOn(api,'modelCenterModels').mockResolvedValue({items:[{id:'qwen',display_name:'Qwen3.6 27B',capabilities:['TEXT'],runtime_type:'LLAMA_CPP',status:'READY',verified:true,historically_validated:true,hardware_profile_details:[{id:'gpu',gpu_name:'RTX 5080',profile_kind:'DEFAULT',benchmark:{}}]}]});
  vi.spyOn(api,'modelCenterRuntimes').mockResolvedValue({items:[{id:'llama',runtime_type:'LLAMA_CPP',base_url:'http://127.0.0.1:8081',status:'CONFIGURED',instance:null,discovery:{path_exists:true,executable_exists:true}}]});
  vi.spyOn(api,'modelCenterPipelines').mockResolvedValue({items:[{id:'LOCAL_VIDEO_PIPELINE_V1',nodes:[{id:'generate',capability:'VIDEO',model_id:'wan22'}],edges:[]}]});
  vi.spyOn(api,'modelCenterHealth').mockResolvedValue({status:'READY',mutation_authorization:{can_mutate:true,mutation_auth_mode:'TRUSTED_SESSION'}});
  host=document.createElement('div');document.body.append(host);root=createRoot(host);mounted=true;await act(async()=>{root.render(<ModelCenter/>);await Promise.resolve();await Promise.resolve()});
  expect(host.textContent).toContain('Qwen3.6 27B');expect(host.textContent).toContain('Current Verified');expect(host.textContent).toContain('LOCAL_VIDEO_PIPELINE_V1');expect(host.textContent).toContain('127.0.0.1');
 });
 it('renders non-ready states and prevents duplicate start while starting',async()=>{
  vi.spyOn(api,'modelCenterModels').mockResolvedValue({items:[{id:'rife',display_name:'RIFE 4.26',capabilities:['INTERPOLATION'],runtime_type:'COMFYUI',status:'INCOMPATIBLE',verified:false,historically_validated:true,hardware_profile_details:[]},{id:'ltx',display_name:'LTX 2.5',capabilities:['VIDEO'],runtime_type:'COMFYUI',status:'LICENSE_REQUIRED',verified:false,historically_validated:false,hardware_profile_details:[]}]});
  vi.spyOn(api,'modelCenterRuntimes').mockResolvedValue({items:[{id:'llama',runtime_type:'LLAMA_CPP',base_url:'http://127.0.0.1:8081',status:'CONFIGURED',instance:{state:'STARTING',process_id:123},discovery:{path_exists:true,executable_exists:true}}]});
  vi.spyOn(api,'modelCenterPipelines').mockResolvedValue({items:[]});
  vi.spyOn(api,'modelCenterHealth').mockResolvedValue({status:'READY',mutation_authorization:{can_mutate:true,mutation_auth_mode:'TRUSTED_SESSION'}});
  host=document.createElement('div');document.body.append(host);root=createRoot(host);mounted=true;await act(async()=>{root.render(<ModelCenter/>);await Promise.resolve();await Promise.resolve()});
  expect(host.textContent).toContain('INCOMPATIBLE');expect(host.textContent).toContain('LICENSE_REQUIRED');expect(host.textContent).toContain('Historical Validation');expect(host.textContent).toContain('未完成推理验证');
  const buttons=Array.from(host.querySelectorAll('button'));
  expect(buttons.find(button=>button.textContent?.includes('Start'))?.disabled).toBe(true);
  expect(buttons.find(button=>button.textContent?.includes('Stop'))?.disabled).toBe(false);
  expect(buttons.find(button=>button.textContent?.includes('Validate'))?.disabled).toBe(true);
 });
 it('ignores responses that finish after unmount',async()=>{
  let resolveModels!:(value:Awaited<ReturnType<typeof api.modelCenterModels>>)=>void;
  let resolveRuntimes!:(value:Awaited<ReturnType<typeof api.modelCenterRuntimes>>)=>void;
  let resolvePipelines!:(value:Awaited<ReturnType<typeof api.modelCenterPipelines>>)=>void;
  let resolveHealth!:(value:Awaited<ReturnType<typeof api.modelCenterHealth>>)=>void;
  vi.spyOn(api,'modelCenterModels').mockReturnValue(new Promise(resolve=>{resolveModels=resolve}));
  vi.spyOn(api,'modelCenterRuntimes').mockReturnValue(new Promise(resolve=>{resolveRuntimes=resolve}));
  vi.spyOn(api,'modelCenterPipelines').mockReturnValue(new Promise(resolve=>{resolvePipelines=resolve}));
  vi.spyOn(api,'modelCenterHealth').mockReturnValue(new Promise(resolve=>{resolveHealth=resolve}));
  host=document.createElement('div');document.body.append(host);root=createRoot(host);mounted=true;
  await act(async()=>{root.render(<ModelCenter/>);await Promise.resolve()});
  act(()=>root.unmount());mounted=false;
  await act(async()=>{resolveModels({items:[]});resolveRuntimes({items:[]});resolvePipelines({items:[]});resolveHealth({status:'READY',mutation_authorization:{can_mutate:false,mutation_auth_mode:'DEVELOPMENT_SESSION_REQUIRED'}});await Promise.resolve()});
  expect(host.textContent).toBe('');
 });
 it('keeps default local runtime controls read-only without sending mutations',async()=>{
  vi.spyOn(api,'modelCenterModels').mockResolvedValue({items:[]});
  vi.spyOn(api,'modelCenterRuntimes').mockResolvedValue({items:[{id:'llama',runtime_type:'LLAMA_CPP',base_url:'http://127.0.0.1:8081',status:'CONFIGURED',instance:{state:'RUNNING',process_id:123},discovery:{path_exists:true,executable_exists:true}}]});
  vi.spyOn(api,'modelCenterPipelines').mockResolvedValue({items:[]});
  vi.spyOn(api,'modelCenterHealth').mockResolvedValue({status:'READY',mutation_authorization:{can_mutate:false,mutation_auth_mode:'DEVELOPMENT_SESSION_REQUIRED'}});
  const validate=vi.spyOn(api,'modelCenterValidateRuntime'),start=vi.spyOn(api,'modelCenterStartRuntime'),stop=vi.spyOn(api,'modelCenterStopRuntime');
  host=document.createElement('div');document.body.append(host);root=createRoot(host);mounted=true;await act(async()=>{root.render(<ModelCenter/>);await Promise.resolve();await Promise.resolve()});
  expect(host.textContent).toContain('运行时控制需要受信任的桌面会话');
  const controls=Array.from(host.querySelectorAll('button')).filter(button=>/Validate|Start|Stop/.test(button.textContent||''));
  expect(controls).toHaveLength(3);expect(controls.every(button=>button.disabled)).toBe(true);
  controls.forEach(button=>button.click());
  expect(validate).not.toHaveBeenCalled();expect(start).not.toHaveBeenCalled();expect(stop).not.toHaveBeenCalled();
 });
 it('falls back to read-only controls when the trusted session expires',async()=>{
  vi.spyOn(api,'modelCenterModels').mockResolvedValue({items:[]});
  vi.spyOn(api,'modelCenterRuntimes').mockResolvedValue({items:[{id:'llama',runtime_type:'LLAMA_CPP',base_url:'http://127.0.0.1:8081',status:'CONFIGURED',instance:null,discovery:{path_exists:true,executable_exists:true}}]});
  vi.spyOn(api,'modelCenterPipelines').mockResolvedValue({items:[]});
  vi.spyOn(api,'modelCenterHealth').mockResolvedValue({status:'READY',mutation_authorization:{can_mutate:true,mutation_auth_mode:'PACKAGED_BOOTSTRAP'}});
  vi.spyOn(api,'modelCenterStartRuntime').mockRejectedValue(new ApiError({status:401,code:'INVALID_SESSION',message:'INVALID_SESSION'}));
  host=document.createElement('div');document.body.append(host);root=createRoot(host);mounted=true;await act(async()=>{root.render(<ModelCenter/>);await Promise.resolve();await Promise.resolve()});
  const start=Array.from(host.querySelectorAll('button')).find(button=>button.textContent?.includes('Start'))!;
  expect(start.disabled).toBe(false);
  await act(async()=>{start.click();await Promise.resolve();await Promise.resolve()});
  expect(start.disabled).toBe(true);expect(host.textContent).toContain('受信任的桌面会话已失效');
 });
});
