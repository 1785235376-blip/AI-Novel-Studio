// @vitest-environment jsdom
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {api,ApiError,setCollaborationContext} from '../api';
import {ScreenplayPanel} from './ScreenplayPanel';
vi.mock('./ScreenplayPipelinePanel',()=>({ScreenplayPipelinePanel:()=>null}));
vi.mock('./MotionTaskWorkspace',()=>({MotionTaskWorkspace:()=>null}));
const clients:QueryClient[]=[];
const scene={id:'scene',sequence:1,source_chapter_id:'chapter',source_version:3,heading:'Original scene',time:'DAY',location:'ROOM',characters:['Alice'],emotion:'calm',action:'Original action',dialogue:[]};
const base={id:'script',novel_id:'project',title:'Synthetic screenplay',revision:4,status:'DRAFT',scenes:[scene]};
function mount(){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);return render(<QueryClientProvider client={client}><ScreenplayPanel novelId="project"/></QueryClientProvider>)}
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals();setCollaborationContext({sessionToken:''});});

it('edits the real structured scene fields and preserves source provenance',async()=>{
  vi.spyOn(api,'screenplays').mockResolvedValue([base]);
  const save=vi.spyOn(api,'updateScreenplayScene').mockResolvedValue(base);
  mount();await screen.findByText('1. Original scene');
  fireEvent.change(screen.getByLabelText('场景标题'),{target:{value:'Updated scene'}});
  fireEvent.change(screen.getByLabelText('地点'),{target:{value:'STATION'}});
  fireEvent.click(screen.getByRole('button',{name:'添加对白',hidden:true}));
  fireEvent.change(screen.getByLabelText('角色'),{target:{value:'小明Alex'}});
  fireEvent.change(screen.getByLabelText('对白内容'),{target:{value:'First\n\nSecond'}});
  fireEvent.click(screen.getByRole('button',{name:'保存场景',hidden:true}));
  await waitFor(()=>expect(save).toHaveBeenCalledWith('project','script','scene',expect.objectContaining({heading:'Updated scene',location:'STATION',source_version:3,dialogue:[{character:'小明Alex',text:'First\n\nSecond'}]})));
});

it('keeps approved scene and shot controls frozen and offers an explicit new revision',async()=>{
  const approved={...base,status:'APPROVED',shot_status:'APPROVED',shots:[{id:'shot',number:1,shot_size:'WIDE',camera_angle:'EYE_LEVEL',camera_motion:'STATIC',subject_position:'center',sound_effect:'quiet',duration_seconds:5,action:'Frozen'}],storyboard:[],transitions:[]};
  vi.spyOn(api,'screenplays').mockResolvedValue([approved]);
  const revise=vi.spyOn(api,'reviseScreenplay').mockResolvedValue({...base,id:'new-script'});
  mount();await screen.findByText('镜头计划已批准并冻结。');
  expect((screen.getByLabelText('场景标题') as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByLabelText('摄影机运动') as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByLabelText('时长（秒）') as HTMLInputElement).disabled).toBe(true);
  expect(screen.queryByRole('button',{name:'保存镜头',hidden:true})).toBeNull();
  expect(screen.queryByRole('button',{name:'保存场景',hidden:true})).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'创建修订草稿'}));
  await waitFor(()=>expect(revise).toHaveBeenCalledWith('project','script',0,undefined));
});

it('hides prior-session cached scenes while the new authorized list is pending',async()=>{
  const scope={workspaceId:'w',projectId:'project',storylineId:'s',branchId:'a'};
  setCollaborationContext({sessionToken:'owner-a',scope});
  let release!:(rows:any[])=>void;
  const pending=new Promise<any[]>(resolve=>{release=resolve});
  vi.spyOn(api,'screenplays').mockResolvedValueOnce([base]).mockReturnValueOnce(pending);
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client);
  const view=render(<QueryClientProvider client={client}><ScreenplayPanel novelId="project" scope={scope} sessionToken="owner-a"/></QueryClientProvider>);
  await screen.findByText('Synthetic screenplay');
  view.rerender(<QueryClientProvider client={client}><ScreenplayPanel novelId="project" scope={scope} sessionToken="owner-b"/></QueryClientProvider>);
  expect(screen.queryByText('Synthetic screenplay')).toBeNull();
  await act(async()=>release([]));await screen.findByText('暂无剧本');
  expect(api.screenplays).toHaveBeenLastCalledWith('project',expect.objectContaining({sessionToken:'owner-b'}));
});

it('shows actionable list and revision failures without claiming a new draft',async()=>{
  const list=vi.spyOn(api,'screenplays').mockRejectedValueOnce(new ApiError({status:403,code:'FORBIDDEN',message:'无法访问此分支'})).mockResolvedValue([{...base,status:'APPROVED'}]);
  vi.spyOn(api,'reviseScreenplay').mockRejectedValue(new Error('无法创建修订，请重试'));
  mount();await screen.findByText('无法访问此分支');
  fireEvent.click(screen.getByRole('button',{name:'重新读取剧本'}));
  fireEvent.click(await screen.findByRole('button',{name:'创建修订草稿'}));
  await screen.findByText('无法创建修订，请重试');
  expect(list).toHaveBeenCalledTimes(2);
});

it('preserves a stale local scene on 409 and requires explicit review before a new-version save',async()=>{
  vi.spyOn(api,'screenplays').mockResolvedValueOnce([{...base,edit_version:1}]).mockResolvedValue([{...base,edit_version:2,scenes:[{...scene,action:'New server action'}]}]);
  const save=vi.spyOn(api,'updateScreenplayScene').mockRejectedValueOnce(new ApiError({status:409,code:'VERSION_CONFLICT',message:'Conflict'})).mockResolvedValue({...base,edit_version:3});
  mount();await screen.findByText('1. Original scene');
  fireEvent.change(screen.getByLabelText('场景动作'),{target:{value:'My unsaved local action'}});
  fireEvent.click(screen.getByRole('button',{name:'保存场景',hidden:true}));
  await screen.findByText('剧本已有新版本。本地编辑已保留，请对照最新内容后再保存。');
  await screen.findByText(/服务器已有编辑版本 2/);
  expect((screen.getByLabelText('场景动作') as HTMLTextAreaElement).value).toBe('My unsaved local action');
  expect(save).toHaveBeenCalledTimes(1);
  expect(save).toHaveBeenLastCalledWith('project','script','scene',expect.objectContaining({expected_version:1,action:'My unsaved local action'}));
  fireEvent.click(screen.getByRole('button',{name:'保留本地内容，按最新版本继续编辑',hidden:true}));
  fireEvent.click(screen.getByRole('button',{name:'保存场景',hidden:true}));
  await waitFor(()=>expect(save).toHaveBeenCalledTimes(2));
  expect(save).toHaveBeenLastCalledWith('project','script','scene',expect.objectContaining({expected_version:2,action:'My unsaved local action'}));
});
