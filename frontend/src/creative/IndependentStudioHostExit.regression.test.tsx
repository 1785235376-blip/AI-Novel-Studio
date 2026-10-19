// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { StudioOverview } from './studioClient';
import emptyPrompts from '../prompt/__fixtures__/empty-library.json';
import type { ComponentProps } from 'react';

const comic = vi.hoisted(() => ({ current: undefined as undefined | {
  onDirtyChange: (value: boolean) => void; onBusyChange: (value: boolean) => void } }));
vi.mock('./StudioComicPanel', async () => {
  const React = await import('react');
  return { StudioComicPanel: (props: { onDirtyChange: (value: boolean) => void; onBusyChange: (value: boolean) => void }) => {
    comic.current = props;
    React.useEffect(() => () => { props.onDirtyChange(false); props.onBusyChange(false); }, []);
    return <button onClick={() => props.onDirtyChange(true)}>输入本地漫画草稿</button>;
  } };
});

const id = 'host-exit-project', base = `/api/projects/${id}/studio`;
const overview: StudioOverview = { project: { id, title: 'Host exit project', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' },
  capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false,
    chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image','video','audio'] } };
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
let fetcher: ReturnType<typeof vi.fn>;
function server(override?: (url: string, init: RequestInit) => Promise<Response> | Response | undefined) {
  fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    const changed = override?.(url, init); if (changed !== undefined) return changed;
    if (url === base) return reply(overview);
    if (url === base + '/prompts') return reply({ ...emptyPrompts, project_id: id, scope: { mode:'local',novel_id:id } });
    if (url === base + '/comic-workspace') return reply({ contract:'studio-comic-workspace/1', project:{id,title:overview.project.title}, source_free:false, capabilities:{can_mutate:true,can_review:true} });
    return reply({ items: [] });
  });
  vi.stubGlobal('fetch', fetcher);
}
function mount(patch: Partial<ComponentProps<typeof IndependentStudioWorkspace>> = {}) {
  const props = { projectId:id, context:{sessionToken:''}, scope:{workspace:'Local',project:'Host exit project',storyline:'Default',branch:'Main'},
    actor:'Author', module:'IMAGE' as const, onModuleChange:vi.fn(), onProjectChoice:vi.fn(), ...patch };
  const query = new QueryClient({ defaultOptions:{queries:{retry:false},mutations:{retry:false}} });
  const view = render(<QueryClientProvider client={query}><IndependentStudioWorkspace {...props}/></QueryClientProvider>);
  return { ...view, props };
}
async function ready() { await screen.findByRole('button',{name:'上传资产'}); }
function loseHost() { act(() => useLocalHostSession.setState(state => ({token:'',actorId:'',epoch:state.epoch+1}))); }
const novel = () => fireEvent.click(screen.getByRole('tab',{name:'小说'}));
const confirm = () => screen.getByRole('button',{name:'确认离开'});
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); comic.current=undefined;
  useStudio.setState({novelId:id,chapterId:'',sessionToken:'',actor:undefined,scope:undefined});
  useLocalHostSession.setState({token:'task-host-secret',actorId:'host',epoch:1});
  server();
});
afterEach(() => { cleanup();vi.restoreAllMocks();vi.unstubAllGlobals(); });

it('lets a clean401 exit to the original Novel Host entry without reviving auth or issuing requests', async () => {
  server(url => url.endsWith('/production/timelines') ? reply({detail:{code:'SESSION_REQUIRED'}},401) : undefined);
  const {props}=mount();await ready();fireEvent.click(screen.getByRole('button',{name:'制作操作'}));
  await screen.findByText('当前会话无权访问此项目',{exact:true});const count=fetcher.mock.calls.length;
  novel();expect(props.onModuleChange, document.body.textContent || '').toHaveBeenCalledWith('NOVEL');
  expect(fetcher.mock.calls).toHaveLength(count);expect(fetcher.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
  expect(useLocalHostSession.getState().token).toBe('task-host-secret');
  expect(JSON.stringify([Object.values(localStorage),Object.values(sessionStorage)])).not.toContain('task-host-secret');
});
it('preserves pre-denial dirty consent across cancel and does not run retired draft controllers', async () => {
  const {props}=mount();await ready();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'unsaved intent'}});
  loseHost();await screen.findByText('当前会话无权访问此项目',{exact:true});novel();
  expect(props.onModuleChange).not.toHaveBeenCalled();
  const alert=screen.getByRole('alert');expect(alert.textContent).toContain('授权失效前');
  fireEvent.click(within(alert).getByRole('button',{name:'留在当前页'}));
  novel();expect((screen.getByLabelText('确认放弃未保存输入') as HTMLInputElement).checked).toBe(false);
  fireEvent.click(screen.getByLabelText('确认放弃未保存输入'));fireEvent.click(confirm());
  expect(props.onModuleChange).toHaveBeenCalledWith('NOVEL');
  expect(fetcher.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
  expect(useLocalHostSession.getState().token).toBe('');
});
it('keeps a real import in flight blocked after Host loss, then requires unknown-outcome consent with its original ID', async () => {
  let resolve!: (value:Response)=>void;const request=new Promise<Response>(done=>{resolve=done;});
  server((url,init)=>url===base+'/assets'&&init.method==='POST'?request:undefined);
  const {props}=mount();await ready();
  const file=new File(['png'],'synthetic.png',{type:'image/png'});Object.defineProperty(file,'arrayBuffer',{value:async()=>new Uint8Array([1,2,3]).buffer});
  fireEvent.change(screen.getByLabelText('选择要上传的资产文件'),{target:{files:[file]}});
  await waitFor(()=>expect(fetcher.mock.calls.filter(([url,init])=>url===base+'/assets'&&init.method==='POST')).toHaveLength(1));
  const body=JSON.parse(String(fetcher.mock.calls.find(([url,init])=>url===base+'/assets'&&init.method==='POST')![1].body));
  loseHost();novel();expect(props.onModuleChange).not.toHaveBeenCalled();expect(screen.queryByRole('button',{name:'确认离开'})).toBeNull();
  await act(async()=>resolve(reply({id:'imported',novel_id:id,filename:'synthetic.png',kind:'image',media_type:'image/png',size:3,sha256:'a'.repeat(64),version:1,created_at:'now',updated_at:'now'},201)));
  novel();await screen.findByLabelText('确认保留原请求待核对后离开');
  expect(screen.getByRole('alert').textContent).toContain(body.idempotency_key);
  expect((confirm() as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('确认保留原请求待核对后离开'));fireEvent.click(confirm());
  expect(props.onModuleChange).toHaveBeenCalledWith('NOVEL');
  expect(fetcher.mock.calls.filter(([,init])=>init.method!=='GET')).toHaveLength(1);
});
it('keeps dirty protection after child cleanup and rechecks other-owner busy at confirmation', async () => {
  const {props}=mount();await ready();fireEvent.click(screen.getByRole('button',{name:'打开漫画制作'}));
  fireEvent.click(await screen.findByRole('button',{name:'输入本地漫画草稿'}));
  const retained=comic.current!;loseHost();novel();
  fireEvent.click(await screen.findByLabelText('确认放弃未保存输入'));
  act(()=>retained.onBusyChange(true));fireEvent.click(confirm());expect(props.onModuleChange).not.toHaveBeenCalled();
  act(()=>retained.onBusyChange(false));fireEvent.click(confirm());expect(props.onModuleChange).toHaveBeenCalledWith('NOVEL');
  expect(fetcher.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
});
it('allows only the original Novel exit after denial while private destinations and project actions stay fenced', async () => {
  const {props}=mount();await ready();loseHost();
  fireEvent.click(screen.getByRole('tab',{name:'视频'}));fireEvent.click(screen.getByRole('tab',{name:'主控'}));
  fireEvent.click(screen.getByRole('button',{name:'返回项目列表'}));
  expect(props.onModuleChange).not.toHaveBeenCalled();expect(props.onProjectChoice).not.toHaveBeenCalled();
  novel();expect(props.onModuleChange).toHaveBeenCalledTimes(1);expect(props.onModuleChange).toHaveBeenCalledWith('NOVEL');
});
it('rejects old-owner exit after the selected project identity changes', async () => {
  const {props}=mount();await ready();act(()=>useStudio.setState({novelId:'another-project'}));novel();
  expect(props.onModuleChange).not.toHaveBeenCalled();expect(props.onProjectChoice).not.toHaveBeenCalled();
});

it('does not treat an unrelated storage401 as settlement of a concurrent actual import', async () => {
  let resolve!: (value:Response)=>void;const request=new Promise<Response>(done=>{resolve=done;});
  server((url,init)=>url===base+'/assets'&&init.method==='POST'?request:url===base+'/storage'?reply({detail:{code:'SESSION_REQUIRED'}},401):undefined);
  const {props}=mount();await ready();
  const file=new File(['png'],'parallel.png',{type:'image/png'});Object.defineProperty(file,'arrayBuffer',{value:async()=>new Uint8Array([1,2,3]).buffer});
  fireEvent.change(screen.getByLabelText('选择要上传的资产文件'),{target:{files:[file]}});
  await waitFor(()=>expect(fetcher.mock.calls.filter(([,init])=>init.method==='POST')).toHaveLength(1));
  fireEvent.click(screen.getByRole('button',{name:'刷新存储统计'}));
  await screen.findByText('当前会话无权访问此项目',{exact:true});novel();
  expect(props.onModuleChange).not.toHaveBeenCalled();expect(screen.queryByRole('button',{name:'确认离开'})).toBeNull();
  await act(async()=>resolve(reply({id:'parallel',novel_id:id,filename:'parallel.png',kind:'image',media_type:'image/png',size:3,sha256:'b'.repeat(64),version:1,created_at:'now',updated_at:'now'},201)));
  novel();fireEvent.click(await screen.findByLabelText('确认保留原请求待核对后离开'));fireEvent.click(confirm());
  expect(props.onModuleChange).toHaveBeenCalledWith('NOVEL');expect(fetcher.mock.calls.filter(([,init])=>init.method!=='GET')).toHaveLength(1);
});
it('keeps the pre-retirement Comic busy fence when child unmount reports false without a settlement receipt', async () => {
  const {props}=mount();await ready();fireEvent.click(screen.getByRole('button',{name:'打开漫画制作'}));
  await screen.findByRole('button',{name:'输入本地漫画草稿'});
  act(()=>comic.current!.onBusyChange(true));loseHost();novel();
  expect(screen.queryByRole('button',{name:'确认离开'})).toBeNull();expect(props.onModuleChange).not.toHaveBeenCalled();
  expect(screen.getByText('当前操作尚未结束，请等待结果确认后再离开。')).toBeTruthy();
});
it('keeps a retired Host controller invalid through A-B-A and commits the safe exit only once', async () => {
  const {props}=mount();await ready();
  act(()=>{useLocalHostSession.setState({token:'other',actorId:'other',epoch:2});useLocalHostSession.setState({token:'task-host-secret',actorId:'host',epoch:1});});
  fireEvent.click(screen.getByRole('tab',{name:'视频'}));expect(props.onModuleChange).not.toHaveBeenCalled();
  novel();novel();expect(props.onModuleChange).toHaveBeenCalledTimes(1);expect(props.onModuleChange).toHaveBeenCalledWith('NOVEL');
});
it('rejects old project callbacks even after a synchronous project A-B-A transition', async () => {
  const {props}=mount();await ready();
  act(()=>{useStudio.setState({novelId:'another-project'});useStudio.setState({novelId:id});});
  novel();expect(props.onModuleChange).not.toHaveBeenCalled();
});
it('retires an already open private navigation confirmation before creating a fixed Novel exit', async () => {
  const {props}=mount();await ready();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'unsaved intent'}});
  fireEvent.click(screen.getByRole('tab',{name:'视频'}));fireEvent.click(screen.getByLabelText('确认放弃未保存输入'));
  loseHost();expect(screen.queryByRole('button',{name:'确认离开'})).toBeNull();
  novel();fireEvent.click(screen.getByLabelText('确认放弃未保存输入'));fireEvent.click(confirm());
  expect(props.onModuleChange).toHaveBeenCalledTimes(1);expect(props.onModuleChange).toHaveBeenCalledWith('NOVEL');
});
it('preserves Timeline dirty protection even though its retirement cleanup reports clean', async () => {
  const {props}=mount();await ready();fireEvent.click(screen.getByRole('button',{name:'制作操作'}));
  const editor=await screen.findByLabelText('Studio 多轨时间线编辑器');
  await waitFor(()=>expect((within(editor).getByLabelText('名称',{exact:true}) as HTMLInputElement).disabled).toBe(false));
  fireEvent.change(within(editor).getByLabelText('名称',{exact:true}),{target:{value:'unsaved timeline title'}});
  loseHost();novel();fireEvent.click(await screen.findByLabelText('确认放弃未保存输入'));fireEvent.click(confirm());
  expect(props.onModuleChange).toHaveBeenCalledWith('NOVEL');expect(fetcher.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
});

it('retains the original beforeunload protection for dirty input after denial cleanup', async () => {
  mount();await ready();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'unsaved intent'}});loseHost();
  const event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);expect(event.defaultPrevented).toBe(true);
});
it('retains an already unknown import ID when a later Host loss opens the safe exit', async () => {
  server((url,init)=>url===base+'/assets'&&init.method==='POST'?Promise.reject(new TypeError('synthetic connection lost')):undefined);
  const {props}=mount();await ready();
  const file=new File(['png'],'unknown.png',{type:'image/png'});Object.defineProperty(file,'arrayBuffer',{value:async()=>new Uint8Array([1,2,3]).buffer});
  fireEvent.change(screen.getByLabelText('选择要上传的资产文件'),{target:{files:[file]}});
  await waitFor(()=>expect((screen.getByRole('button',{name:'上传资产'}) as HTMLButtonElement).disabled).toBe(false));
  await waitFor(()=>expect(fetcher.mock.calls.filter(([,init])=>init.method==='POST')).toHaveLength(1));
  const body=JSON.parse(String(fetcher.mock.calls.find(([,init])=>init.method==='POST')![1].body));
  loseHost();novel();const checkbox=await screen.findByLabelText('确认保留原请求待核对后离开');
  expect(screen.getByRole('alert').textContent).toContain(body.idempotency_key);fireEvent.click(checkbox);fireEvent.click(confirm());
  expect(props.onModuleChange).toHaveBeenCalledWith('NOVEL');expect(fetcher.mock.calls.filter(([,init])=>init.method!=='GET')).toHaveLength(1);
});
