// @vitest-environment jsdom
import { act,cleanup,fireEvent,render,screen,waitFor,within } from '@testing-library/react';
import { afterEach,beforeEach,expect,it,vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import native from './canvasAudioTrimTask.testFixtures';
// Generated software receipts; actual CPU processing is covered by the separate Python owner test.
const historyAt=(version:number)=>({...native.history,current_version:version,current_definition_digest:[native.canvas,native.returned,native.restored][version-1].definition_digest,items:[native.canvas,native.returned,native.restored].slice(0,version).map(row=>({version:row.version,definition:row.definition,definition_digest:row.definition_digest,reference_states:row.reference_states,created_at:row.created_at,updated_at:row.updated_at,can_restore:row.version!==version&&row.reference_states.every(s=>s.state==='CURRENT_METADATA')}))});
const fixture={...native,project:native.canvas.project_id,incarnation:native.command.canvas_return.incarnation,asset:native.output,
 command:{...native.command,parameters:{in_ms:550,out_ms:850},source_snapshots:native.command.source_snapshots.map(s=>({...s}))},
 providers:{items:[],automatic_runtime_start:false,health_probed:false,credentials_read:false},initial_history:historyAt(1),history:historyAt(2),final_history:historyAt(3)};

import { useStudioGraphEditor } from './useStudioGraphEditor';
import { studioClient } from './studioClient';
import { studioProductionClient } from './studioProductionClient';
import { studioGraphDraftOwner } from './studioGraphLocalDraft';
import { imageGraphCatalog } from './studioImageGraph.testFixtures';

const base=`/api/projects/${fixture.project}/studio`,canvasPath=`${base}/canvas-views/${fixture.canvas.id}`,productionPath=base+'/production';
const json=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json'}});
const retained=(element:HTMLElement)=>(element as any)[Object.keys(element).find(key=>key.startsWith('__reactProps$'))!].onClick as ()=>void;
let canvas:any,phase:'none'|'queued'|'executed'|'approved',fetcher:ReturnType<typeof vi.fn>;
beforeEach(()=>{
 localStorage.clear();canvas=structuredClone(fixture.canvas);phase='none';
 vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);
 vi.stubGlobal('crypto',{subtle:webcrypto.subtle,randomUUID:()=>fixture.command.request_id,getRandomValues:webcrypto.getRandomValues.bind(webcrypto)});
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> 'blob:dual-fixture')});Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()});
 fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const method=init.method||'GET',body=init.body?JSON.parse(String(init.body)):undefined;
  if(url===`${base}/assets/${fixture.source.id}`)return json(fixture.source);
  if(url===`${base}/assets/${fixture.asset.id}`){expect(phase).toBe('approved');return json(fixture.asset);}
  if(url===base+'/canvas-views'){const {id,version,definition_digest,created_at,updated_at}=canvas;return json({items:[{id,version,definition_digest,created_at,updated_at,title:canvas.definition.title,card_count:canvas.definition.cards.length}],execution_authority:false});}
  if(url===canvasPath+'/history')return json(canvas.version===1?fixture.initial_history:canvas.version===2?fixture.history:fixture.final_history);
  if(url===canvasPath+'/restore'){
   expect(body).toEqual({expected_version:2,expected_definition_digest:fixture.returned.definition_digest,expected_incarnation:fixture.incarnation,restore_version:1,restore_definition_digest:fixture.canvas.definition_digest});
   canvas=structuredClone(fixture.restored);return json(canvas);
  }
  if(url===canvasPath&&method==='PUT'){expect(body.expected_version).toBe(1);expect(body.expected_incarnation).toBe(fixture.incarnation);expect(body.expected_definition_digest).toBe(fixture.canvas.definition_digest);expect(body.expected_card).toEqual({card_id:'origin-audio',source:fixture.canvas.definition.cards[0].asset});expect(body.definition).toEqual(fixture.returned.definition);canvas=structuredClone(fixture.returned);return json(canvas);}
  if(url===canvasPath)return json(canvas);
  if(url===productionPath+'/providers')return json(fixture.providers);
  if(url===productionPath+'/jobs'&&method==='GET')return json({items:phase==='approved'?[fixture.approved]:phase==='executed'?[fixture.executed]:[],product_acceptance:'LOCAL_REQUIRED'});
  if(url===productionPath+'/preview'){expect({...body,image_references:body.image_references??[]}).toMatchObject(fixture.command);return json(fixture.preview);}
  if(url===productionPath+'/jobs'&&method==='POST'){expect({...body.command,image_references:body.command.image_references??[]}).toMatchObject(fixture.command);expect(body.reviewed_preview_digest).toBe(fixture.preview.preview_digest);phase='queued';return json(fixture.queued);}
  if(url.endsWith('/execute')){expect(phase).toBe('queued');phase='executed';return json(fixture.executed);}
  if(url.endsWith('/review')){expect(body.reviewed_output_digest).toBe(fixture.executed.output_candidate.digest);phase='approved';return json(fixture.approved);}
  if(url.endsWith('/candidate'))return new Response(Uint8Array.from(atob(fixture.candidate_wav_base64),c=>c.charCodeAt(0)),{headers:{'Content-Type':'audio/wav'}});
  if(url===`${productionPath}/jobs/audio/${fixture.approved.id}`)return json(phase==='executed'?fixture.executed:fixture.approved);
  throw new Error('Unexpected software fixture request '+method+' '+url);
 });vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
function mount(){
 const context={sessionToken:''},original=studioClient(fixture.project,context),production=studioProductionClient(fixture.project,context);
 const client={...original,graphs:{...original.graphs,catalog:vi.fn(async()=>imageGraphCatalog()),list:vi.fn(async()=>({items:[]})),runs:vi.fn(async()=>({items:[]}))}};
 const props={active:true,denied:false,identity:'dual-owner',client,canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:async<T,>(f:()=>Promise<T>)=>f(),mutate:async<T,>(f:()=>Promise<T>)=>f(),productionTaskSource:production,
  draftOwner:studioGraphDraftOwner(fixture.project,fixture.incarnation,context,{token:'synthetic-host-token',actorId:'local-studio-author'})};
 function Harness(){const view=useStudioGraphEditor(props);return <>{view.content}{view.inspector}</>;}
 return {...render(<Harness/>),props,Harness};
}
async function selectCard(id:string){
 await waitFor(()=>expect(document.querySelector(`[data-media-card="${id}"]`)).not.toBeNull());
 const card=document.querySelector(`[data-media-card="${id}"]`)!;fireEvent.click(within(card as HTMLElement).getByRole('button'));
}
async function startTask(){
 const mounted=mount();await screen.findByRole('region',{name:'Studio 双画布'});
 expect(screen.getByRole('button',{name:'创作画布'}).getAttribute('aria-pressed')).toBe('true');
 fireEvent.click(screen.getByRole('button',{name:'读取已存画布'}));fireEvent.click(await screen.findByRole('button',{name:new RegExp(fixture.canvas.definition.title+' · v1')}));
 await selectCard('origin-audio');fireEvent.click(screen.getByRole('button',{name:'从此卡片创建音频截取任务'}));
 const task=await screen.findByRole('region',{name:'所选卡片的执行画布'});
 expect(screen.queryByRole('region',{name:'独立媒体素材画布'})).toBeNull();expect(fetcher.mock.calls.filter(([u])=>u.endsWith('/jobs'))).toHaveLength(0);
 fireEvent.click(screen.getByRole('button',{name:'对照分屏'}));expect(screen.getByRole('region',{name:'独立媒体素材画布'})).toBeTruthy();expect(screen.getByRole('region',{name:'所选卡片的执行画布'})).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'执行画布'}));
 for(const [label,value] of [['来源起点（毫秒）','550'],['来源终点（毫秒）','850']])fireEvent.change(within(task).getByLabelText(label),{target:{value}});
 return {mounted,task};
}
async function confirmTaskImpact(task:HTMLElement){
 const check=within(task).getByLabelText('已核对本次输入变化与影响范围');await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));
 fireEvent.click(check);fireEvent.click(within(task).getByRole('button',{name:'确认本次输入核对'}));
}
async function approveTask(task:HTMLElement){
 fireEvent.click(within(task).getByRole('button',{name:'读取制作预览'}));await within(task).findByRole('region',{name:'制作预览确认'});
 fireEvent.click(within(task).getByLabelText('已核对本次输入、来源和处理边界'));await confirmTaskImpact(task);
  const create=within(task).getByRole('button',{name:'仅创建任务并入队'});await waitFor(()=>expect((create as HTMLButtonElement).disabled).toBe(false));fireEvent.click(create);
 const execute=await within(task).findByRole('button',{name:'明确执行当前入队任务'});await waitFor(()=>expect(within(task).getByText(/执行前再次核对/)).toBeTruthy());await confirmTaskImpact(task);await waitFor(()=>expect((execute as HTMLButtonElement).disabled).toBe(false));fireEvent.click(execute);
 const candidate=await within(task).findByRole('button',{name:'读取并核对候选媒体'});await waitFor(()=>expect((candidate as HTMLButtonElement).disabled).toBe(false));fireEvent.click(candidate);
 const check=within(task).getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要');await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));fireEvent.click(check);
 fireEvent.click(within(task).getByRole('button',{name:'明确审核并入素材库'}));await screen.findByRole('region',{name:'审核结果回到原作品位置'});
}
it('uses one original task, confirms actual execution/review, returns only to the captured card and restores history as a new version',async()=>{
 const {task}=await startTask();await approveTask(task);
 await selectCard('other-audio');fireEvent.click(screen.getByRole('button',{name:'核验原位置与正式审核结果'}));
 await waitFor(()=>expect(screen.queryByLabelText('确认只采用到上述原卡片'),[...document.querySelectorAll('[role=alert],[role=status]')].map(e=>e.textContent).join(' ')).not.toBeNull());fireEvent.click(screen.getByLabelText('确认只采用到上述原卡片'));
 const apply=screen.getByRole('button',{name:'确认采用并回填原卡片'}),oldApply=retained(apply);fireEvent.click(apply);
 await screen.findByText('已采用正式结果并回填原卡片；原素材文件、坐标和分组保留。');expect(canvas.version).toBe(2);
 fireEvent.click(screen.getByText('画布版本历史与恢复'));fireEvent.click(screen.getByRole('button',{name:'读取画布版本历史'}));
 const choice=await screen.findByLabelText('待恢复画布版本');fireEvent.change(choice,{target:{value:'1'}});
 fireEvent.click(screen.getByLabelText('确认创建新的当前版本并退役旧预览'));fireEvent.click(screen.getByRole('button',{name:'恢复此画布版本为新版本'}));
 await screen.findByText('已恢复为新的当前画布版本；原历史保留，旧选择和预览已退役。');expect(canvas.version).toBe(3);expect(canvas.definition).toEqual(fixture.canvas.definition);
 await act(async()=>oldApply());expect(fetcher.mock.calls.filter(([u,i])=>u===canvasPath&&i.method==='PUT')).toHaveLength(1);
 for(const suffix of ['/execute','/review','/restore'])expect(fetcher.mock.calls.filter(([u])=>u.endsWith(suffix))).toHaveLength(1);
});
it('refuses a changed return target while retaining the formal asset and never guesses the new selected card',async()=>{
 const {task}=await startTask();await approveTask(task);canvas=structuredClone(fixture.restored);
 fireEvent.click(screen.getByRole('button',{name:'核验原位置与正式审核结果'}));await waitFor(()=>{const messages=[...document.querySelectorAll('[role=alert],[role=status]')].map(e=>e.textContent).join(' ');expect(messages,messages).toMatch(/原画布、卡片或音频版本已改变|原项目代次、范围或画布版本已改变/);});
 expect(screen.queryByRole('button',{name:'确认采用并回填原卡片'})).toBeNull();expect(fetcher.mock.calls.filter(([u,i])=>u===canvasPath&&i.method==='PUT')).toHaveLength(0);expect(phase).toBe('approved');
});
async function recoverResult(){
 fireEvent.click(screen.getByText('重开后恢复尚未采用的卡片结果'));fireEvent.click(screen.getByRole('button',{name:'读取有原位置绑定的卡片结果'}));
 fireEvent.click(await screen.findByRole('button',{name:/核验并恢复原卡片任务/}));
}
it('reopens from the original approved Job after complete unmount and requires a new explicit adoption',async()=>{
 const {mounted,task}=await startTask();await approveTask(task);mounted.unmount();mount();
 expect(screen.queryByRole('region',{name:'审核结果回到原作品位置'})).toBeNull();const before=fetcher.mock.calls.length;
 await recoverResult();await screen.findByRole('region',{name:'审核结果回到原作品位置'});
 expect(fetcher.mock.calls.slice(before).every(([,i])=>!i.method||i.method==='GET')).toBe(true);expect(canvas.version).toBe(1);
 fireEvent.click(screen.getByRole('button',{name:'核验原位置与正式审核结果'}));fireEvent.click(await screen.findByLabelText('确认只采用到上述原卡片'));fireEvent.click(screen.getByRole('button',{name:'确认采用并回填原卡片'}));
 await screen.findByText('已采用正式结果并回填原卡片；原素材文件、坐标和分组保留。');expect(canvas.version).toBe(2);
 expect(fetcher.mock.calls.filter(([u])=>u.endsWith('/execute'))).toHaveLength(1);
});
it('reopens a private candidate for the original explicit review without creating or executing another Job',async()=>{
 phase='executed';mount();await recoverResult();const task=await screen.findByRole('region',{name:'所选卡片的执行画布'});
 const candidate=await within(task).findByRole('button',{name:'读取并核对候选媒体'});await waitFor(()=>expect((candidate as HTMLButtonElement).disabled).toBe(false));fireEvent.click(candidate);
 const consent=within(task).getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要');await waitFor(()=>expect((consent as HTMLInputElement).disabled).toBe(false));fireEvent.click(consent);fireEvent.click(within(task).getByRole('button',{name:'明确审核并入素材库'}));
 await screen.findByRole('region',{name:'审核结果回到原作品位置'});expect(fetcher.mock.calls.filter(([u,i])=>u.endsWith('/execute')||u===productionPath+'/jobs'&&i.method==='POST')).toHaveLength(0);expect(canvas.version).toBe(1);
});
it.each(['card deleted','version changed'])('blocks recovery after %s and retains the approved asset',async mode=>{
 phase='approved';canvas=structuredClone(fixture.restored);
 if(mode==='card deleted'){canvas.definition.cards=canvas.definition.cards.filter((c:any)=>c.id!=='origin-audio');delete canvas.definition.groups;canvas.reference_states=canvas.reference_states.filter((c:any)=>c.card_id!=='origin-audio');}
 mount();await recoverResult();await waitFor(()=>expect(screen.getByRole('region',{name:'持久卡片回流任务'}).querySelector('[role="status"],[role="alert"]')).not.toBeNull());
 expect(screen.queryByRole('region',{name:'审核结果回到原作品位置'})).toBeNull();expect(fetcher.mock.calls.filter(([,i])=>i.method==='PUT')).toHaveLength(0);expect(phase).toBe('approved');
});
it('does not offer a recorded result from another project',async()=>{
 phase='approved';const original=fetcher.getMockImplementation()!;fetcher.mockImplementation((url,init)=>url===productionPath+'/jobs'?Promise.resolve(json({items:[{...fixture.approved,novel_id:'other-project'}],product_acceptance:'LOCAL_REQUIRED'})):original(url,init));
 mount();fireEvent.click(screen.getByText('重开后恢复尚未采用的卡片结果'));fireEvent.click(screen.getByRole('button',{name:'读取有原位置绑定的卡片结果'}));
 await screen.findByText('服务回执不完整。请重新读取核对，勿重复发送。');expect(screen.queryByRole('button',{name:/核验并恢复原卡片任务/})).toBeNull();expect(fetcher.mock.calls.filter(([,i])=>i.method==='PUT')).toHaveLength(0);
});
it.each(['owner','client'])('retires a late original Job read across %s A/B/A before further source reads or adoption',async mode=>{
 phase='approved';let finish!:(v:Response)=>void;const original=fetcher.getMockImplementation()!,jobPath=`${productionPath}/jobs/audio/${fixture.approved.id}`;
 fetcher.mockImplementation((url,init)=>url===jobPath?new Promise(resolve=>{finish=resolve;}):original(url,init));const mounted=mount();await recoverResult();await waitFor(()=>expect(finish).toBeTypeOf('function'));
 const originalClient=mounted.props.client;
 if(mode==='owner')mounted.props.identity='other-owner';else mounted.props.client={...originalClient};mounted.rerender(<mounted.Harness/>);
 mounted.props.identity='dual-owner';mounted.props.client=originalClient;mounted.rerender(<mounted.Harness/>);const before=fetcher.mock.calls.length;
 await act(async()=>finish(json(fixture.approved)));expect(fetcher.mock.calls.slice(before).filter(([u])=>u.includes('/assets/')||u===canvasPath)).toHaveLength(0);
 expect(screen.queryByRole('region',{name:'审核结果回到原作品位置'})).toBeNull();expect(fetcher.mock.calls.filter(([,i])=>i.method==='PUT')).toHaveLength(0);
});

it('reads real Job provenance explicitly from the card task and checks its formal asset without adopting or replaying',async()=>{
 const {task}=await startTask();await approveTask(task);fireEvent.click(screen.getByRole('button',{name:'执行画布'}));
 const panel=within(task).getByRole('region',{name:'执行来源与失败恢复'}),jobPath=`${productionPath}/jobs/audio/${fixture.approved.id}`;
 const before=fetcher.mock.calls.length;expect(within(panel).getByText('尚未读取执行来源')).toBeTruthy();
 fireEvent.click(within(panel).getByRole('button',{name:'读取执行来源'}));
 await within(panel).findByText(/原 Job 已持久记录位置绑定/);
 expect(within(panel).getByText('origin-audio')).toBeTruthy();expect(panel.textContent).toContain(fixture.incarnation);
 await within(panel).findByText(/已核验正式资产/);
 expect(panel.textContent).toContain('持久绑定不代表已回填');expect(panel.textContent).not.toContain('原 Job 没有持久 canvas/card origin');
 expect(fetcher.mock.calls.slice(before).map(([url,init])=>[url,init.method||'GET'])).toEqual([[jobPath,'GET'],[`${base}/assets/${fixture.asset.id}`,'GET']]);
 expect(canvas.version).toBe(1);for(const suffix of ['/execute','/review'])expect(fetcher.mock.calls.filter(([url])=>url.endsWith(suffix))).toHaveLength(1);
});
