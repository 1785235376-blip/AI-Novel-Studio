// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { useStudio } from '../store';
import { bindLocalHostSession, useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { checkedMaskInput, maskSha256, type StudioMaskInput } from './studioManualMaskContract';
import type { StudioAsset, StudioOverview } from './studioClient';
import type { CollaborationContext } from '../api';
const id='mask-shell-project',base=`/api/projects/${id}/studio`;
const deferred=<T,>()=>{let resolve!:(value:T)=>void;const promise=new Promise<T>(yes=>{resolve=yes;});return{promise,resolve};};
const reply=(value:unknown,status=200)=>({ok:status<400,status,json:async()=>value,blob:async()=>blob});
let blob:Blob,source:StudioAsset,rows:StudioAsset[],fetcher:ReturnType<typeof vi.fn>,post:ReturnType<typeof deferred<ReturnType<typeof reply>>>|undefined,context:CollaborationContext;
const overview=():StudioOverview=>({project:{id,title:'遮罩项目',entry_kind:'NEUTRAL_STUDIO'},preferences:{version:1,intents:[],preset:'IMAGE',custom_intent:''},capabilities:{can_mutate:true,manual_import:true,manual_export:true,chapter_required:false,model_required:false,media_validator_configured:true,asset_kinds:['image','video','audio'],intent_is_permission:false}});
async function result(body:StudioMaskInput){const pixel=checkedMaskInput(body),sha='d'.repeat(64);const asset={...source,id:'saved-mask',filename:'mask.png',sha256:sha,version:1,provenance:{id:'saved-mask',kind:'image',deleted:false,origin:'MANUAL_EDIT',version:1,digest:sha,integrity:'VERIFIED',stale:false,sources:[],generation:null,parents:[{id:source.id,version:body.source_version,digest:body.source_sha256,state:'CURRENT'}],license:{label:'UNSPECIFIED',source:'',note:''},license_verification:'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION'}};return{asset,receipt:{contract:body.contract,source_asset_id:source.id,source_version:body.source_version,source_sha256:body.source_sha256,width:body.width,height:body.height,bitplane_sha256:await maskSha256(pixel.bytes),keep_pixels:pixel.keep,remove_pixels:body.width*body.height-pixel.keep,mask_sha256:sha}};}
beforeEach(async()=>{
  localStorage.clear();vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('createImageBitmap',vi.fn(async()=>({width:64,height:64,close:vi.fn()})));
  Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=>'blob:original')});Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()});
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockImplementation(()=>({createImageData:(w:number,h:number)=>({data:new Uint8ClampedArray(w*h*4)}),putImageData:vi.fn()}) as unknown as CanvasRenderingContext2D);
  const bytes=new Uint8Array(57),data=new DataView(bytes.buffer);bytes.set([137,80,78,71,13,10,26,10]);data.setUint32(8,13);bytes.set([73,72,68,82],12);data.setUint32(16,64);data.setUint32(20,64);bytes[24]=8;bytes[25]=6;bytes.set([73,68,65,84],37);bytes.set([73,69,78,68],49);
  blob=new NodeBlob([bytes]) as unknown as Blob;source={id:'source',novel_id:id,branch_id:null,version:2,kind:'image',filename:'source.png',media_type:'image/png',size:57,sha256:await maskSha256(bytes),created_at:'',updated_at:''};rows=[source];post=undefined;context={sessionToken:''};
  useStudio.setState({novelId:id,sessionToken:'',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'mask-host',actorId:''});
  fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
    if(url===base)return reply(overview());
    if(url.includes('/assets?'))return reply({items:rows});
    if(url===`${base}/assets/source/mask`){if(post)return post.promise;const response=await result(JSON.parse(init!.body as string));rows=[source,response.asset];return reply(response);}
    if(url.endsWith('/download'))return reply({});
    if(url===`${base}/assets/source`)return reply(source);
    if(url===`${base}/assets/other`)return reply({...source,id:'other',filename:'other.png'});
    if(url===`${base}/assets/saved-mask`)return reply(rows.find(row=>row.id==='saved-mask'));
    if(url.includes('/references?'))return reply({items:[],read_only:true,content_copied:false});
    throw new Error(`Unexpected ${url}`);
  });vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
function mount(){
  Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });const leave=vi.fn(),query=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});const node=(requested='source')=> <QueryClientProvider client={query}><IndependentStudioWorkspace projectId={id} context={context} scope={{workspace:'本机',project:'遮罩项目',storyline:'默认',branch:'主线'}} actor="作者" module="IMAGE" requestedAssetId={requested} onModuleChange={leave} onProjectChoice={leave}/></QueryClientProvider>;return{...render(node()),leave,node};}
async function start(){await waitFor(()=>expect(screen.queryByRole('button',{name:'素材工作区'})).toBeTruthy());fireEvent.click(screen.getByRole('button',{name:'素材工作区'}));await screen.findByRole('button',{name:'核对来源并打开遮罩编辑'});fireEvent.click(screen.getByRole('button',{name:'核对来源并打开遮罩编辑'}));await screen.findByRole('application',{name:'二值蒙版绘图区'});fireEvent.click(screen.getByRole('button',{name:'应用精确矩形'}));fireEvent.click(screen.getByLabelText('确认将当前黑白像素保存为新遮罩资产'));}
function maskCalls(){return fetcher.mock.calls.filter(([url])=>url.endsWith('/mask'));}
describe('manual mask in the original Image workspace',()=>{
  it('loads only explicitly and creates original MANUAL_EDIT Asset without jobs or automatic selection',async()=>{
    mount();await screen.findByRole('button',{name:'核对来源并打开遮罩编辑'});expect(createImageBitmap).not.toHaveBeenCalled();expect(maskCalls()).toHaveLength(0);await start();fireEvent.click(screen.getByRole('button',{name:'保存二值遮罩'}));await screen.findByText('二值遮罩已保存到原资产库。未创建任务或执行抠图。');expect(maskCalls()).toHaveLength(1);
    const inspector=screen.getByRole('region',{name:'资产检查面板'});expect(within(inspector).getByText('资产 ID').nextElementSibling?.textContent).toBe('source');
    expect(fetcher.mock.calls.filter(([,init])=>init?.method&&init.method!=='GET').map(([url])=>url)).toEqual([`${base}/assets/source/mask`]);
    fireEvent.click(screen.getByRole('button',{name:'查看已保存遮罩资产'}));await waitFor(()=>expect(within(screen.getByRole('region',{name:'资产检查面板'})).getByText('资产 ID').nextElementSibling?.textContent).toBe('saved-mask'));
  });
  it('uses the original shared semaphore to block imports and navigation until POST settles',async()=>{
    const view=mount();await start();post=deferred();fireEvent.click(screen.getByRole('button',{name:'保存二值遮罩'}));await waitFor(()=>expect(maskCalls()).toHaveLength(1));expect((screen.getByRole('button',{name:'上传资产'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(screen.getByRole('tablist',{name:'创作模块'})).getByRole('tab',{name:'视频'}));expect(view.leave).not.toHaveBeenCalled();
    const response=await result(JSON.parse(maskCalls()[0][1]!.body as string));await act(async()=>post!.resolve(reply(response)));await screen.findByRole('button',{name:'查看已保存遮罩资产'});expect(view.leave).not.toHaveBeenCalled();
  });
  it('uses original discard confirmation for local dirty pixels',async()=>{
    const view=mount();await start();fireEvent.click(within(screen.getByRole('tablist',{name:'创作模块'})).getByRole('tab',{name:'视频'}));expect(view.leave).not.toHaveBeenCalled();expect(screen.getByLabelText('确认放弃未保存输入')).toBeTruthy();fireEvent.click(screen.getByLabelText('确认放弃未保存输入'));fireEvent.click(screen.getByRole('button',{name:'确认离开'}));expect(view.leave).toHaveBeenCalledWith('VIDEO');expect(maskCalls()).toHaveLength(0);expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:original');
  });
  it.each(['host','host-rebind','project','actor','branch','session'])('latches %s ABA before a late save response, with no Asset merge or selection',async kind=>{
    if(['actor','branch','session'].includes(kind)){context={sessionToken:'synthetic-original',actor:{id:'author',displayName:'作者',workspaceId:'w'},scope:{workspaceId:'w',projectId:id,storylineId:'s',branchId:'b'}};source.branch_id='b';useStudio.setState({sessionToken:context.sessionToken,actor:context.actor,scope:context.scope});}
    mount();await start();post=deferred();fireEvent.click(screen.getByRole('button',{name:'保存二值遮罩'}));await waitFor(()=>expect(maskCalls()).toHaveLength(1));const response=await result(JSON.parse(maskCalls()[0][1]!.body as string));
    act(()=>{if(kind==='host-rebind'){bindLocalHostSession('mask-host',{session_mode:'LOCAL_HOST',actor_id:'same-author'});}else if(kind==='host'){useLocalHostSession.setState({token:'different'});useLocalHostSession.setState({token:'mask-host'});}else if(kind==='project'){useStudio.setState({novelId:'other'});useStudio.setState({novelId:id});}else if(kind==='actor'){useStudio.setState({actor:{...context.actor!,id:'other'}});useStudio.setState({actor:context.actor});}else if(kind==='branch'){useStudio.setState({scope:{...context.scope!,branchId:'other'}});useStudio.setState({scope:context.scope});}else{useStudio.setState({sessionToken:'other'});useStudio.setState({sessionToken:context.sessionToken});}});
    expect(maskCalls()[0][1]?.signal?.aborted).toBe(true);await act(async()=>post!.resolve(reply(response)));expect(screen.queryByRole('application',{name:'二值蒙版绘图区'})).toBeNull();expect(screen.queryByRole('button',{name:'查看已保存遮罩资产'})).toBeNull();expect(screen.queryByText('mask.png')).toBeNull();expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:original');
  });
  it('does not reopen a late source decode after source A→B→A navigation',async()=>{
    const decode=deferred<ImageBitmap>();vi.mocked(createImageBitmap).mockReturnValueOnce(decode.promise);const view=mount();
    fireEvent.click(await screen.findByRole('button',{name:'核对来源并打开遮罩编辑'}));await waitFor(()=>expect(createImageBitmap).toHaveBeenCalledTimes(1));
    view.rerender(view.node('other'));await waitFor(()=>expect(within(screen.getByRole('region',{name:'资产检查面板'})).getByText('资产 ID').nextElementSibling?.textContent).toBe('other'));
    view.rerender(view.node('source'));await waitFor(()=>expect(within(screen.getByRole('region',{name:'资产检查面板'})).getByText('资产 ID').nextElementSibling?.textContent).toBe('source'));
    const close=vi.fn();await act(async()=>decode.resolve({width:64,height:64,close} as unknown as ImageBitmap));expect(close).toHaveBeenCalled();expect(screen.queryByRole('application',{name:'二值蒙版绘图区'})).toBeNull();expect(maskCalls()).toHaveLength(0);
  });
  it('keeps lost-save uncertainty after stale retry and provides an original list read',async()=>{
    mount();await start();post=deferred();fireEvent.click(screen.getByRole('button',{name:'保存二值遮罩'}));await waitFor(()=>expect(maskCalls()).toHaveLength(1));await act(async()=>post!.resolve(reply({code:'UNKNOWN'},503)));await screen.findByRole('button',{name:'明确重试同一遮罩保存'});
    source={...source,version:3};fireEvent.click(screen.getByRole('button',{name:'明确重试同一遮罩保存'}));await screen.findByText('来源已变化或不可用；不能重试此保存。结果可能已在原资产库，请刷新列表核对。');expect(maskCalls()).toHaveLength(1);expect((screen.getByRole('button',{name:'明确重试同一遮罩保存'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'刷新原资产列表核对结果'}));await waitFor(()=>expect(fetcher.mock.calls.filter(([url])=>url.includes('/assets?')).length).toBeGreaterThan(1));expect(maskCalls()).toHaveLength(1);
  });
});
