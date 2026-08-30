// @vitest-environment jsdom
import {act} from 'react';
import {createRoot,Root} from 'react-dom/client';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {api} from '../api';
import {ModelCenter} from './ModelCenter';

(globalThis as typeof globalThis & {IS_REACT_ACT_ENVIRONMENT:boolean}).IS_REACT_ACT_ENVIRONMENT=true;

describe('ModelCenter',()=>{
 let host:HTMLDivElement,root:Root;
 afterEach(()=>{if(root)act(()=>root.unmount());host?.remove();vi.restoreAllMocks()});
 it('shows verified models, runtime state, and the registered video pipeline',async()=>{
  vi.spyOn(api,'modelCenterModels').mockResolvedValue({items:[{id:'qwen',display_name:'Qwen3.6 27B',capabilities:['TEXT'],runtime_type:'LLAMA_CPP',status:'READY',verified:true,hardware_profile_details:[{id:'gpu',gpu_name:'RTX 5080',profile_kind:'DEFAULT',benchmark:{}}]}]});
  vi.spyOn(api,'modelCenterRuntimes').mockResolvedValue({items:[{id:'llama',runtime_type:'LLAMA_CPP',base_url:'http://127.0.0.1:8081',status:'CONFIGURED',instance:null,discovery:{path_exists:true,executable_exists:true}}]});
  vi.spyOn(api,'modelCenterPipelines').mockResolvedValue({items:[{id:'LOCAL_VIDEO_PIPELINE_V1',nodes:[{id:'generate',capability:'VIDEO',model_id:'wan22'}],edges:[]}]});
  host=document.createElement('div');document.body.append(host);root=createRoot(host);await act(async()=>{root.render(<ModelCenter/>);await Promise.resolve();await Promise.resolve()});
  expect(host.textContent).toContain('Qwen3.6 27B');expect(host.textContent).toContain('Inference Verified');expect(host.textContent).toContain('LOCAL_VIDEO_PIPELINE_V1');expect(host.textContent).toContain('127.0.0.1');
 });
 it('renders non-ready states and prevents duplicate start while starting',async()=>{
  vi.spyOn(api,'modelCenterModels').mockResolvedValue({items:[{id:'rife',display_name:'RIFE 4.26',capabilities:['INTERPOLATION'],runtime_type:'COMFYUI',status:'INCOMPATIBLE',verified:false,hardware_profile_details:[]},{id:'ltx',display_name:'LTX 2.5',capabilities:['VIDEO'],runtime_type:'COMFYUI',status:'LICENSE_REQUIRED',verified:false,hardware_profile_details:[]}]});
  vi.spyOn(api,'modelCenterRuntimes').mockResolvedValue({items:[{id:'llama',runtime_type:'LLAMA_CPP',base_url:'http://127.0.0.1:8081',status:'CONFIGURED',instance:{state:'STARTING',process_id:123},discovery:{path_exists:true,executable_exists:true}}]});
  vi.spyOn(api,'modelCenterPipelines').mockResolvedValue({items:[]});
  host=document.createElement('div');document.body.append(host);root=createRoot(host);await act(async()=>{root.render(<ModelCenter/>);await Promise.resolve();await Promise.resolve()});
  expect(host.textContent).toContain('INCOMPATIBLE');expect(host.textContent).toContain('LICENSE_REQUIRED');expect(host.textContent).toContain('未完成推理验证');
  const buttons=Array.from(host.querySelectorAll('button'));
  expect(buttons.find(button=>button.textContent?.includes('Start'))?.disabled).toBe(true);
  expect(buttons.find(button=>button.textContent?.includes('Stop'))?.disabled).toBe(false);
  expect(buttons.find(button=>button.textContent?.includes('Validate'))?.disabled).toBe(true);
 });
});
