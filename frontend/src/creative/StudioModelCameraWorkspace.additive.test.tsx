// @vitest-environment jsdom
import {webcrypto} from 'node:crypto';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,expect,it,vi} from 'vitest';
import {IndependentStudioWorkspace} from './IndependentStudioWorkspace';
import {useStudio} from '../store';
import {useLocalHostSession} from '../localHostSession';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
import {cameraAsset,cameraReview,cameraExport,cameraChoice} from './studioModelCamera.testFixtures';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';

vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();vi.clearAllMocks();});
function mount(canExport=true,denial=false) {
  vi.stubGlobal('crypto',webcrypto);localStorage.clear();useStudio.setState({novelId:'project',chapterId:'',sessionToken:'',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'',actorId:''});
  const base='/api/projects/project/studio';
  const overview={project:{id:'project',title:'Independent',entry_kind:'NEUTRAL_STUDIO'},preferences:{version:1,intents:[],preset:'BLANK',custom_intent:''},capabilities:{can_mutate:false,manual_import:false,manual_export:canExport,model_required:false,chapter_required:false,intent_is_permission:false,media_validator_configured:false,asset_kinds:['image','video','audio']}};
  const reply=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
  const fetch=vi.fn(async(url:string,init:RequestInit={})=>{
    if(url===base)return reply(overview);
    if(url===base+'/prompts')return reply({...emptyPromptLibrary,project_id:'project',scope:{mode:'local',novel_id:'project'}});
    if((url===base+'/assets'||url.startsWith(base+'/assets?'))&&init.method==='GET')return reply({items:[cameraAsset]});
    if(url===base+`/assets/${cameraAsset.id}`)return reply(cameraAsset);
    if(url===base+`/assets/${cameraAsset.id}/model-reference/cameras`)return denial?reply({detail:{code:'FORBIDDEN',message:'Camera access denied'}},403):reply(cameraReview());
    if(url===base+`/assets/${cameraAsset.id}/model-reference/camera-export`)return reply(cameraExport(cameraChoice(1)));
    throw new Error(`Unexpected request: ${init.method} ${url}`);
  });vi.stubGlobal('fetch',fetch);
  const query=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId="project" context={{sessionToken:''}} scope={{workspace:'Local',project:'Independent',storyline:'Default',branch:'Main'}} actor="Author" module="ASSETS" onModuleChange={vi.fn()} onProjectChoice={vi.fn()}/></QueryClientProvider>);
  return {fetch,base};
}
it('reads and exports explicit source camera through the original asset workspace without asset/job/model writes',async()=>{
  const {fetch,base}=mount();const assetSelector=await screen.findByLabelText('已保存 GLB 参考');
  await waitFor(()=>expect(screen.getByRole('option',{name:'triangle.glb · v1'})).toBeTruthy());fireEvent.change(assetSelector,{target:{value:cameraAsset.id}});
  expect(fetch.mock.calls.some(([url])=>url.endsWith('/cameras'))).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 源相机'}));await screen.findByLabelText('选择源相机实例');expect((screen.getByLabelText('选择源相机实例') as HTMLSelectElement).value).toBe('');
  fireEvent.change(screen.getByLabelText('选择源相机实例'),{target:{value:'1'}});fireEvent.click(screen.getByRole('button',{name:'导出所选源相机 glTF'}));
  await screen.findByText('源相机 glTF 校验通过，已发起下载；目标软件导入尚未验收。');
  const writes=fetch.mock.calls.filter(([,init])=>(init?.method??'GET')!=='GET');
  expect(writes).toHaveLength(1);expect(writes[0][0]).toBe(base+`/assets/${cameraAsset.id}/model-reference/camera-export`);
  expect(JSON.parse(String(writes[0][1]?.body))).toEqual({contract:'studio-static-glb-camera-export/1',source_version:1,source_sha256:cameraAsset.sha256,scene_index:0,node_index:1,camera_index:1,profile:'GLTF_2_CAMERA_ONLY'});
  expect(downloadPortableBlob).toHaveBeenCalledTimes(1);expect(fetch.mock.calls.some(([url])=>/generate|execute|model-benchmark|clay-save/.test(url))).toBe(false);
});
it('keeps workspace export capability authoritative while permitting inspection',async()=>{
  const {fetch}=mount(false);const assetSelector=await screen.findByLabelText('已保存 GLB 参考');await screen.findByRole('option',{name:'triangle.glb · v1'});fireEvent.change(assetSelector,{target:{value:cameraAsset.id}});
  fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 源相机'}));await screen.findByLabelText('选择源相机实例');fireEvent.change(screen.getByLabelText('选择源相机实例'),{target:{value:'1'}});
  const button=screen.getByRole('button',{name:'导出所选源相机 glTF'}) as HTMLButtonElement;expect(button.disabled).toBe(true);fireEvent.click(button);expect(fetch.mock.calls.some(([url])=>url.endsWith('/camera-export'))).toBe(false);expect(downloadPortableBlob).not.toHaveBeenCalled();
});
it('retires the original workspace after authoritative camera access denial',async()=>{
  const {fetch}=mount(true,true);const assetSelector=await screen.findByLabelText('已保存 GLB 参考');await screen.findByRole('option',{name:'triangle.glb · v1'});fireEvent.change(assetSelector,{target:{value:cameraAsset.id}});
  fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 源相机'}));await waitFor(()=>expect(screen.queryByLabelText('GLB 源相机检查与交换')).toBeNull());
  expect(fetch.mock.calls.filter(([url])=>url.endsWith('/cameras'))).toHaveLength(1);expect(fetch.mock.calls.some(([url])=>url.endsWith('/camera-export'))).toBe(false);expect(downloadPortableBlob).not.toHaveBeenCalled();
});
