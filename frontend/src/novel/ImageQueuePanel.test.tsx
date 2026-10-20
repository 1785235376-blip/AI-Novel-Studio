// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {api,setCollaborationContext} from '../api';
import {ImageQueuePanel} from './ImageQueuePanel';
afterEach(()=>{cleanup();vi.restoreAllMocks();setCollaborationContext({sessionToken:''})});
const draft={provider_id:'local',model_id:'fixture',prompt:'Synthetic test'};
it('persists configured image parameters and accepts reviewed output explicitly',async()=>{
 vi.spyOn(api,'imageJobs').mockResolvedValue({items:[]});
 const create=vi.spyOn(api,'createImageJob').mockResolvedValue({id:'job-a',status:'QUEUED'});
 const view=render(<ImageQueuePanel novelId="project-a" draft={draft} local/>);
 fireEvent.change(screen.getByLabelText('队列图片宽度'),{target:{value:'768'}});
 fireEvent.click(screen.getByRole('button',{name:'保存到生成队列'}));
 await waitFor(()=>expect(create).toHaveBeenCalledWith('project-a',expect.objectContaining({parameters:{width:768,height:1024,steps:28,seed:1}})));
 vi.mocked(api.imageJobs).mockResolvedValue({items:[{id:'job-a',prompt:'Review me',status:'SUCCEEDED',approval_status:'PENDING',attempt:1,asset_uri:'https://example.test/image.png'}]});
 const accept=vi.spyOn(api,'acceptImageJob').mockResolvedValue({id:'asset-a'} as any);
 fireEvent.click(screen.getByRole('button',{name:'刷新任务'}));
 fireEvent.click(await screen.findByRole('button',{name:'对比结果'}));
 expect(screen.getByAltText('对比结果 job-a')).toBeTruthy();expect(accept).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'接受并入库'}));
 await waitFor(()=>expect(accept).toHaveBeenCalledWith('project-a','job-a'));view.unmount();
});
it('drops old scope responses and suppresses duplicate submission',async()=>{
 let resolve!:(value:any)=>void;
 vi.spyOn(api,'imageJobs').mockImplementation(nid=>nid==='project-a'?new Promise(done=>{resolve=done}):Promise.resolve({items:[]}));
 let finish!:(value:any)=>void;
 const create=vi.spyOn(api,'createImageJob').mockImplementation(()=>new Promise(done=>{finish=done}));
 const view=render(<ImageQueuePanel novelId="project-a" draft={draft}/>);
 const submit=screen.getByRole('button',{name:'保存到生成队列'});fireEvent.click(submit);fireEvent.click(submit);expect(create).toHaveBeenCalledTimes(1);
 view.rerender(<ImageQueuePanel novelId="project-b" draft={draft}/>);
 resolve({items:[{id:'private-old',prompt:'Must not appear',status:'FAILED'}]});finish({id:'old-job'});
 await waitFor(()=>expect(screen.getByText('暂无持久任务。')).toBeTruthy());expect(screen.queryByText('Must not appear')).toBeNull();
});
