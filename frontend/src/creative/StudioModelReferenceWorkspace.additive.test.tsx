// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { modelAsset, modelGlbBytes, modelInspection } from './studioModelReference.testFixtures';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
it.each([false,true])('imports through original workspace, with lost-response retry %s and no FFmpeg',async(lost)=>{
 vi.stubGlobal('crypto',webcrypto);localStorage.clear();useStudio.setState({novelId:'project',chapterId:'',sessionToken:'',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'',actorId:''});
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> 'blob:fixture')});Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()});
 let didLose=false;let saved:ReturnType<typeof modelAsset>[]=[];const base='/api/projects/project/studio';
 const overview={project:{id:'project',title:'Independent',entry_kind:'NEUTRAL_STUDIO'},preferences:{version:1,intents:[],preset:'BLANK',custom_intent:''},capabilities:{can_mutate:true,manual_import:true,manual_export:true,model_required:false,chapter_required:false,intent_is_permission:false,media_validator_configured:false,asset_kinds:['image','video','audio']}};
 const reply=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
 const fetch=vi.fn(async(url:string,init:RequestInit={})=>{
  if(url===base)return reply(overview);
  if(url===base+'/prompts')return reply({...emptyPromptLibrary,project_id:'project',scope:{mode:'local',novel_id:'project'}});
  if((url===base+'/assets'||url.startsWith(base+'/assets?'))&&init.method==='GET')return reply({items:saved});
  if(url===base+'/assets/model-reference'&&init.method==='POST'){if(!saved.length)saved=[modelAsset(true)];if(lost&&!didLose){didLose=true;throw new Error('Fixture lost response after commit');}return reply(saved[0],201);}
  if(url.endsWith('/lineage')){saved=[{...saved[0],version:2}];return reply(saved[0]);}
  if(url===base+'/assets/model-reference/model-reference')return reply(modelInspection(saved[0],true));
  if(url===base+'/assets/model-reference/model-reference/materials'&&init.method==='GET')return reply({detail:{code:'MODEL_REFERENCE_GLB_MATERIAL_INVALID',message:'Unsupported material'}},422);
  if(url===base+'/assets/model-reference/model-reference/clay-export'&&init.method==='POST')return reply({detail:{code:'MODEL_REFERENCE_GLB_CLAY_LIMIT',message:'Budget exceeded'}},422);
  if(url===base+'/assets/model-reference/model-reference/depth-export'&&init.method==='POST')return reply({detail:{code:'MODEL_REFERENCE_GLB_DEPTH_LIMIT',message:'Budget exceeded'}},422);
  if(url===base+'/assets/model-reference/model-reference/scene-preview')return reply({...modelInspection(saved[0],true),scene_preview:{contract:'studio-static-glb-scene-preview/1',space:'SCENE_WORLD_STATIC',scene_index:0,selection:'DECLARED_DEFAULT',traversed_nodes:1,mesh_instances:1,position_count:3,triangle_count:1,primitives:[{node_index:0,mesh_index:0,primitive_index:0,positions:[[99,0,0],[101,0,0],[100,2,0]],triangles:[[0,1,2]]}],bounds:{min:[99,0,0],max:[101,2,0]},scene_transforms_applied:true,materials_rendered:false,animation_applied:false,decimated:false,model_called:false}});
  if(url===base+'/assets/model-reference/model-reference/mesh-preview')return reply({...modelInspection(saved[0],true),mesh_preview:{contract:'studio-static-glb-mesh-preview/1',space:'MESH_LOCAL_UNTRANSFORMED',primitives:[{positions:[[-1,0,0],[1,0,0],[0,2,0]],triangles:[[0,1,2]]}],scene_transforms_applied:false,materials_rendered:false,decimated:false,model_called:false}});
  if(url===base+'/assets/model-reference')return reply(saved[0]);
  throw new Error(`Unexpected request: ${init.method} ${url}`);
 });vi.stubGlobal('fetch',fetch);
 const query=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId='project' context={{sessionToken:''}} scope={{workspace:'Local',project:'Independent',storyline:'Default',branch:'Main'}} actor='Author' module='ASSETS' onModuleChange={vi.fn()} onProjectChoice={vi.fn()}/></QueryClientProvider>);
 const picker=await screen.findByLabelText('选择静态 GLB 文件');const bytes=modelGlbBytes(true),file=new File([bytes],'triangle.glb');Object.defineProperty(file,'arrayBuffer',{value:async()=>bytes.buffer});fireEvent.change(picker,{target:{files:[file]}});fireEvent.click(await screen.findByRole('button',{name:'明确导入并保存 GLB 参考素材'}));
 if(lost)fireEvent.click(await screen.findByRole('button',{name:'使用同一请求重试 GLB 导入'}));
 await waitFor(()=>expect(saved[0]?.version).toBe(2));await waitFor(()=>expect((screen.getByRole('button',{name:'读取当前 GLB 几何检查'}) as HTMLButtonElement).disabled).toBe(false));fireEvent.click(screen.getByRole('button',{name:'读取当前 GLB 几何检查'}));await screen.findByLabelText('GLB 原素材几何回执');fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 网格诊断'}));await screen.findByRole('img',{name:'实际 GLB 网格局部几何示意'});
 const writes=fetch.mock.calls.filter(([,init])=>(init?.method??'GET')!=='GET');expect(writes.map(([url])=>url)).toEqual([base+'/assets/model-reference',...(lost?[base+'/assets/model-reference']:[]),base+'/assets/model-reference/lineage']);
 const sent=JSON.parse(String(writes[0][1]!.body));expect(sent.contract).toBe('studio-static-glb-import/1');expect(writes[0][1]!.headers).toMatchObject({'Idempotency-Key':sent.idempotency_key});if(lost)expect(JSON.parse(String(writes[1][1]!.body)).idempotency_key).toBe(sent.idempotency_key);expect(fetch.mock.calls.some(([url])=>/generate|execute|render/.test(url))).toBe(false);
 fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'scene'}});fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 静态场景'}));await screen.findByRole('img',{name:'实际 GLB 静态场景几何示意'});
 fireEvent.click(screen.getByRole('button',{name:'导出当前视角深度参考 PNG'}));await waitFor(()=>expect(fetch.mock.calls.some(([url])=>url.endsWith('/model-reference/depth-export'))).toBe(true));
 const depth=fetch.mock.calls.find(([url])=>url.endsWith('/model-reference/depth-export'))!;expect(depth[1]?.method).toBe('POST');expect(JSON.parse(String(depth[1]?.body))).toEqual({contract:'studio-static-glb-depth-export/1',source_version:2,source_sha256:saved[0].sha256,yaw:35,pitch:25});
 await screen.findByText('深度参考计算超出预算，未生成部分图片。');expect(URL.createObjectURL).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'导出当前视角灰模参考 PNG'}));await screen.findByText('灰模参考计算超出预算，未生成部分图片。');const clay=fetch.mock.calls.find(([url])=>url.endsWith('/model-reference/clay-export'))!;expect(JSON.parse(String(clay[1]?.body))).toEqual({contract:'studio-static-glb-clay-export/1',source_version:2,source_sha256:saved[0].sha256,yaw:35,pitch:25});expect(URL.createObjectURL).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 材质数值'}));await screen.findByText('材质数值或绑定超出支持范围，未返回部分材质。');expect(fetch.mock.calls.filter(([url])=>url.endsWith('/model-reference/materials'))).toHaveLength(1);
});
