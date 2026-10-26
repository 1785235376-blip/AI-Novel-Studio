// @vitest-environment jsdom
/** Actual Workspace/selector/original panel and HTTP clients, using File-derived
 * QUEUED metadata. Execute below is an explicit SOFTWARE HTTP projection only;
 * this does not run a provider, File execution, media inspection or review. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_resume.json';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace, type IndependentStudioProps } from './IndependentStudioWorkspace';

const base = `/api/projects/${native.project}/studio`;
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers:{'Content-Type':'application/json'}});
let fetcher: ReturnType<typeof vi.fn>, row: typeof native.job, canvas: typeof native.canvas;
type Override = (url: string, init: RequestInit) => Response | Promise<Response> | undefined;
const provider = {...native.job.provider, operation_id:'m5.image.t2i', capability:'TEXT_TO_IMAGE',
  supported_parameters:['width','height','steps','seed'], readiness:'CONFIGURED_NOT_VERIFIED'};
function server(override?: Override) {
  fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    const value = override?.(url, init); if (value !== undefined) return await value;
    if (url === base) return json(native.overview);
    if (url === `${base}/prompts`) return json({...emptyPromptLibrary,project_id:native.project,scope:native.scope});
    if (url.startsWith(`${base}/assets`)) return json({items:[]});
    if (url === `${base}/production/jobs` && init.method === 'GET') return json({...native.jobs,items:[row]});
    if (url.endsWith('/jobs/image/resolve-create')) return json(row);
    if (url.endsWith(`/canvas-views/${native.canvas.id}/history`)) return json(native.history);
    if (url.endsWith(`/canvas-views/${native.canvas.id}`)) return json(canvas);
    if (url.endsWith(`/jobs/image/${native.job.id}`)) return json(row);
    if (url.endsWith('/providers')) return json({items:[provider], health_probed:false, credentials_read:false});
    if (url.endsWith('/preview')) return json(native.preview);
    if (url.endsWith(`/jobs/image/${native.job.id}/execute`)) {
      // Deliberately a software-only ambiguous receipt, never a generated output.
      return json({...native.job,version:2,status:'UNKNOWN'});
    }
    if (url.endsWith('/timelines')) return json({items:[]});
    if (url.includes('/experimental/workspace/tasks?')) return json({items:[],unavailable:[],truncated:false,executor:false,refresh:'MANUAL',automatic_retries:false});
    if ((init.method || 'GET') === 'GET') return json({code:'FIXTURE_UNRELATED_READ_NOT_AVAILABLE',message:'Not part of this bounded metadata fixture'},404);
    throw new Error(`Unexpected mutation in resume-only fixture: ${init.method} ${url}`);
  }); vi.stubGlobal('fetch',fetcher);
}
const workspaceProps = (): IndependentStudioProps => ({projectId:native.project,context:{sessionToken:''},
  scope:{workspace:'本机作品',project:'Synthetic query fixture',storyline:'默认故事线',branch:'主线'},actor:'作者',module:'IMAGE',
  onModuleChange:vi.fn(),onProjectChoice:vi.fn()});
function mount(patch:Partial<IndependentStudioProps>={}) {
  const client = new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  const props={...workspaceProps(),...patch};
  const tree=(next:IndependentStudioProps)=><QueryClientProvider client={client}><IndependentStudioWorkspace {...next}/></QueryClientProvider>;
  const view=render(tree(props));
  return {...view,rerenderWorkspace:(next:IndependentStudioProps)=>view.rerender(tree(next))};
}
async function tasks() {
  mount(); fireEvent.click(await screen.findByRole('button',{name:'任务中心'}));
  return screen.findByRole('button',{name:`打开原制作任务 ${native.job.id} v1`});
}
async function resume() { fireEvent.click(await tasks()); await screen.findByRole('heading',{name:'仅续接原节点任务'}); }
const count = (suffix: string) => fetcher.mock.calls.filter(([url, init]) => url.endsWith(suffix) && init.method === 'POST').length;
function noDispatch() { expect(count('/jobs')).toBe(0); expect(count('/execute')).toBe(0); expect(count('/review')).toBe(0); }
function retained(button: HTMLElement) {
  const key = Object.keys(button).find(name => name.startsWith('__reactProps$'))!;
  return (button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;
}
function noCreationPersistence(writes:{mock:{calls:[key:string,value:string][]}}) {
  for (const [key,value] of writes.mock.calls) {
    expect(key).not.toMatch(/rebuild|canvas.*(?:draft|hint|queue|create)|image.*node.*(?:draft|hint|queue|create)/i);
    expect(value).not.toContain(native.node.prompt);
    expect(value).not.toContain(native.command.canvas_image_node.prompt_digest);
    expect(value).not.toContain(native.job.request_id);
  }
}
beforeEach(() => {
  vi.stubGlobal('crypto',webcrypto); localStorage.clear(); row=structuredClone(native.job); canvas=structuredClone(native.canvas);
  // Canvas painting/geometry is outside this jsdom HTTP-contract test.
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);
  useStudio.setState({novelId:native.project,chapterId:'',sessionToken:'',actor:undefined,scope:undefined});
  useLocalHostSession.setState({token:'',actorId:''}); server();
});
afterEach(() => {cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('opens one exact hintless original QUEUED Job via actual TaskCenter and Workspace without rebuilding a draft or dispatching', async () => {
  const writes=vi.spyOn(Storage.prototype,'setItem'); await resume();
  const prompt=screen.getByLabelText('原任务已确认的提示词') as HTMLTextAreaElement;
  expect(prompt.value).toBe(native.node.prompt); expect(prompt.readOnly).toBe(true);
  expect(screen.queryByLabelText('本次提示词')).toBeNull(); expect(screen.queryByLabelText('服务商与模型')).toBeNull();
  expect(screen.queryByRole('button',{name:'仅创建任务并入队'})).toBeNull();
  expect(screen.queryByRole('button',{name:'读取任务列表'})).toBeNull();
  expect(screen.queryByRole('button',{name:'读取制作预览'})).toBeNull();
  expect(screen.queryByRole('button',{name:'新建时间线'})).toBeNull();
  expect(screen.queryByRole('button',{name:'添加视频轨道'})).toBeNull();
  expect(screen.queryByRole('button',{name:'添加音频轨道'})).toBeNull();
  expect(fetcher.mock.calls.some(([url])=>url.includes('/production/timelines'))).toBe(false);
  expect(fetcher.mock.calls.some(([url])=>url.endsWith(`/canvas-views/${native.canvas.id}/history`))).toBe(true);
  const execute=screen.getByRole('button',{name:'明确执行当前入队任务'});
  expect((execute as HTMLButtonElement).disabled).toBe(true); await act(async()=>retained(execute)());
  noDispatch(); noCreationPersistence(writes);
});

it('requires fresh original command preview and EXECUTE impact consent before one software-only original Job action', async () => {
  await resume(); const execute=screen.getByRole('button',{name:'明确执行当前入队任务'});
  await act(async()=>retained(execute)()); noDispatch();
  await waitFor(()=>expect((screen.getByRole('button',{name:'重新读取原任务服务配置'}) as HTMLButtonElement).disabled).toBe(false));
  const configReads=fetcher.mock.calls.filter(([url])=>url.endsWith('/providers')).length;
  fireEvent.click(screen.getByRole('button',{name:'重新读取原任务服务配置'}));
  await waitFor(()=>expect(fetcher.mock.calls.filter(([url])=>url.endsWith('/providers')).length).toBe(configReads+1));
  await waitFor(()=>expect((screen.getByRole('button',{name:'重新读取原任务服务配置'}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button',{name:'读取原入队任务预览'}));
  const check=await screen.findByLabelText('已核对本次输入变化与影响范围');
  await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));
  expect((execute as HTMLButtonElement).disabled).toBe(true); await act(async()=>retained(execute)()); noDispatch();
  const request=JSON.parse(String(fetcher.mock.calls.find(([url])=>url.endsWith('/preview'))![1].body));
  expect(request).toEqual(native.command);
  fireEvent.click(check); fireEvent.click(screen.getByRole('button',{name:'确认本次输入核对'}));
  await waitFor(()=>expect((screen.getByRole('button',{name:'明确执行当前入队任务'}) as HTMLButtonElement).disabled).toBe(false));
  const send=retained(screen.getByRole('button',{name:'明确执行当前入队任务'}));
  await act(async()=>{send();send();}); await waitFor(()=>expect(count('/execute')).toBe(1));
  const sent=fetcher.mock.calls.find(([url])=>url.endsWith('/execute'))!;
  expect(sent[0]).toBe(`${base}/production/jobs/image/${native.job.id}/execute`);
  expect(JSON.parse(String(sent[1].body))).toEqual({expected_version:1,expected_request_digest:native.job.request_digest});
  expect(count('/jobs')).toBe(0);expect(count('/review')).toBe(0);
  await act(async()=>send()); expect(count('/execute')).toBe(1);
});

it.each(['job-version','canvas-version','permission'] as const)('fails closed on fresh %s instead of silently opening the newest source',async kind=>{
  const open=await tasks();
  if(kind==='job-version')row={...row,version:2};
  if(kind==='canvas-version')canvas={...canvas,version:2};
  if(kind==='permission')server((url)=>url===base?json({...native.overview,capabilities:{...native.overview.capabilities,can_mutate:false}}):undefined);
  fireEvent.click(open);
  await screen.findByText(kind==='job-version'?/所选制作回执已变化/:kind==='permission'?/原项目代次或当前写入能力未确认/:/原节点画布、范围、代次或版本已改变/);
  expect(screen.queryByRole('heading',{name:'仅续接原节点任务'})).toBeNull();
  noDispatch();
});

it('does not adopt a late handoff after the mounted Workspace is removed',async()=>{
  let release!:(value:Response)=>void;
  server(url=>url.endsWith('/jobs/image/resolve-create')?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  mount();fireEvent.click(await screen.findByRole('button',{name:'任务中心'}));
  fireEvent.click(await screen.findByRole('button',{name:`打开原制作任务 ${native.job.id} v1`}));
  await waitFor(()=>expect(release).toBeTypeOf('function')); cleanup();
  await act(async()=>release(json(native.resolved_job))); noDispatch();
  expect(fetcher.mock.calls.some(([url])=>url.endsWith(`/canvas-views/${native.canvas.id}`))).toBe(false);
});

it('preserves dirty input when source changed while the existing navigation confirmation was deferred',async()=>{
  const open=await tasks();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'keep this independent draft'}});
  fireEvent.click(open);await screen.findByRole('button',{name:'确认离开'});
  canvas={...canvas,version:2};fireEvent.click(screen.getByLabelText('确认放弃未保存输入'));fireEvent.click(screen.getByRole('button',{name:'确认离开'}));
  await screen.findByText(/原节点画布、范围、代次或版本已改变/);
  await waitFor(()=>expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep this independent draft'));
  expect(screen.queryByRole('heading',{name:'仅续接原节点任务'})).toBeNull();noDispatch();
});

it('does not let an old checked navigation callback authorize a newly selected original Job session',async()=>{
  const open=await tasks();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'retain until current confirmation'}});
  fireEvent.click(open);await screen.findByRole('button',{name:'确认离开'});
  fireEvent.click(screen.getByLabelText('确认放弃未保存输入'));
  const oldConfirm=retained(screen.getByRole('button',{name:'确认离开'}));
  fireEvent.click(screen.getByRole('button',{name:'继续编辑'}));
  fireEvent.click(screen.getByRole('button',{name:`打开原制作任务 ${native.job.id} v1`}));
  await screen.findByRole('button',{name:'确认离开'});
  expect((screen.getByLabelText('确认放弃未保存输入') as HTMLInputElement).checked).toBe(false);
  const reads=fetcher.mock.calls.length;
  await act(async()=>oldConfirm());
  expect(fetcher.mock.calls).toHaveLength(reads);
  expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('retain until current confirmation');
  expect(screen.queryByRole('heading',{name:'仅续接原节点任务'})).toBeNull();
  fireEvent.click(screen.getByLabelText('确认放弃未保存输入'));fireEvent.click(screen.getByRole('button',{name:'确认离开'}));
  await screen.findByRole('heading',{name:'仅续接原节点任务'});noDispatch();
});

it('retires a pending exact handoff across explicit transport client token A/B/A without adopting its late source',async()=>{
  let release!:(value:Response)=>void;
  server(url=>url.endsWith('/jobs/image/resolve-create')?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  const initial={...workspaceProps(),context:{sessionToken:'',localHostToken:'synthetic-prop-A'}};
  const view=mount(initial);fireEvent.click(await screen.findByRole('button',{name:'任务中心'}));
  fireEvent.click(await screen.findByRole('button',{name:`打开原制作任务 ${native.job.id} v1`}));
  await waitFor(()=>expect(release).toBeTypeOf('function'));
  view.rerenderWorkspace({...initial,context:{...initial.context,localHostToken:'synthetic-prop-B'}});
  await screen.findByRole('button',{name:'任务中心'});
  view.rerenderWorkspace(initial);await screen.findByRole('button',{name:'任务中心'});
  await act(async()=>release(json(native.resolved_job)));
  expect(screen.queryByRole('heading',{name:'仅续接原节点任务'})).toBeNull();
  expect(fetcher.mock.calls.some(([url])=>url.endsWith(`/canvas-views/${native.canvas.id}`))).toBe(false);noDispatch();
});
