// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {api,ApiError} from '../api';
import {ScreenplayPipelinePanel} from './ScreenplayPipelinePanel';
afterEach(()=>{cleanup();vi.restoreAllMocks();});
const status={next_stage:'screenplay',stages:[{id:'screenplay',complete:false}],motion:{completed:0,total:0}};
it('shows empty, loading and denied states instead of silently disappearing',async()=>{
  const view=render(<ScreenplayPipelinePanel/>);expect(screen.getByText('尚未选择剧本')).toBeTruthy();
  vi.spyOn(api,'pipelineStatus').mockRejectedValue(new ApiError({status:403,code:'FORBIDDEN',message:'Denied'}));
  view.rerender(<ScreenplayPipelinePanel novelId="n" screenplayId="s"/>);await screen.findByText(/无权读取或推进/);expect(screen.queryByRole('button',{name:'推进下一阶段'})).toBeNull();
});
it('retains human review gate and prevents repeated advance commands',async()=>{
  vi.spyOn(api,'pipelineStatus').mockResolvedValue(status);let finish:(value:any)=>void=()=>{};
  vi.spyOn(api,'advancePipeline').mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));render(<ScreenplayPipelinePanel novelId="n" screenplayId="s"/>);
  const advance=await screen.findByRole('button',{name:'推进下一阶段'});act(()=>{fireEvent.click(advance);fireEvent.click(advance);});expect(api.advancePipeline).toHaveBeenCalledTimes(1);
  await act(async()=>finish({action:'MANUAL_APPROVAL_REQUIRED'}));await screen.findByText('需要先人工批准当前阶段。');
});
it('fences a late response from the previously selected screenplay',async()=>{
  let release:(value:any)=>void=()=>{};vi.spyOn(api,'pipelineStatus').mockImplementation((_n,id)=>id==='old'?new Promise(resolve=>{release=resolve;}):Promise.resolve({...status,next_stage:'complete'}));
  const view=render(<ScreenplayPipelinePanel novelId="n" screenplayId="old"/>);await waitFor(()=>expect(api.pipelineStatus).toHaveBeenCalled());view.rerender(<ScreenplayPipelinePanel novelId="n" screenplayId="new"/>);
  await screen.findByText('下一阶段：已完成');await act(async()=>release(status));expect(screen.queryByText('下一阶段：剧本审批')).toBeNull();
});
