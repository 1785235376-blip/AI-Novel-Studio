// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {api,ApiError} from '../api';
import {AdaptationPanel} from './AdaptationPanel';

const row=(revision=1,focus='Prefilled focus')=>({id:'proposal',title:'Lifecycle proposal',revision,blueprint_revision:revision,blueprint:{focus,pacing:'Prefilled pace',format:'Screen',constraints:['Preserve source'],chapter_map:[{source_chapter_id:'source',source_title:'Original',unit:'Episode one',action:'Prefilled action'}]},status:'DRAFT',target:'SCREEN',source_chapter_count:1,source_versions:[{chapter_id:'source',version:1}],source_digest:'bound-source'});
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done;});return {promise,resolve};}
function mount(){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});render(<QueryClientProvider client={client}><AdaptationPanel novelId="source-novel"/></QueryClientProvider>);return client;}
beforeEach(()=>{vi.spyOn(api,'adaptationCatalog').mockResolvedValue({enabled:true,can_write:true,can_review:true,model_runtime:'NOT_CONFIGURED'});vi.spyOn(api,'adaptationProposals').mockResolvedValue([row()]);});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('keeps exact control labels independent of prefilled textarea text',async()=>{
  mount();await screen.findByText('Lifecycle proposal');fireEvent.click(screen.getByText('编辑改编蓝图'));
  for(const name of ['改编重点','节奏策略','输出格式','约束（每行一条）','目标单元','改编动作']){
    const control=screen.getByLabelText(name,{exact:true});expect(control.getAttribute('aria-label')).toBe(name);
    fireEvent.change(control,{target:{value:'Changed text cannot become the label'}});expect(screen.getByLabelText(name,{exact:true})).toBe(control);
  }
});
it('disables blueprint edits until both save and authoritative refresh complete, then saves the next real edit',async()=>{
  const saving=deferred<any>(),refreshing=deferred<any[]>();vi.spyOn(api,'updateAdaptationBlueprint').mockReturnValueOnce(saving.promise).mockResolvedValueOnce(row(3,'Next edit'));
  mount();await screen.findByText('Lifecycle proposal');fireEvent.click(screen.getByText('编辑改编蓝图'));
  const focus=screen.getByLabelText('改编重点') as HTMLTextAreaElement;fireEvent.change(focus,{target:{value:'Saved edit'}});
  const save=screen.getByRole('button',{name:'保存蓝图修订'});act(()=>{fireEvent.click(save);fireEvent.click(save);});
  await waitFor(()=>{expect(api.updateAdaptationBlueprint).toHaveBeenCalledTimes(1);expect(focus.disabled).toBe(true);});
  vi.mocked(api.adaptationProposals).mockReturnValueOnce(refreshing.promise);
  await act(async()=>saving.resolve(row(2,'Saved edit')));await waitFor(()=>expect(api.adaptationProposals).toHaveBeenCalledTimes(2));expect(focus.disabled).toBe(true);
  await act(async()=>refreshing.resolve([row(2,'Saved edit')]));await waitFor(()=>expect(focus.disabled).toBe(false));
  vi.mocked(api.adaptationProposals).mockResolvedValue([row(3,'Next edit')]);fireEvent.change(focus,{target:{value:'Next edit'}});fireEvent.click(screen.getByRole('button',{name:'保存蓝图修订'}));
  await waitFor(()=>expect(api.updateAdaptationBlueprint).toHaveBeenCalledTimes(2));expect(api.updateAdaptationBlueprint).toHaveBeenLastCalledWith('source-novel','proposal',expect.objectContaining({expected_revision:2,focus:'Next edit'}),undefined);
});
it('releases pending state after a failed save without losing or silently rebasing the local edit',async()=>{
  vi.spyOn(api,'updateAdaptationBlueprint').mockRejectedValue(new ApiError({status:409,code:'CONFLICT',message:'Synthetic conflict'}));mount();await screen.findByText('Lifecycle proposal');fireEvent.click(screen.getByText('编辑改编蓝图'));
  const focus=screen.getByLabelText('改编重点') as HTMLTextAreaElement;fireEvent.change(focus,{target:{value:'Preserve this draft'}});fireEvent.click(screen.getByRole('button',{name:'保存蓝图修订'}));
  await screen.findByRole('alert');expect(focus.value).toBe('Preserve this draft');expect(focus.disabled).toBe(false);expect(api.updateAdaptationBlueprint).toHaveBeenCalledTimes(1);
});
it('keeps proposal commands locked through delayed query invalidation',async()=>{
  const approving=deferred<any>(),refreshing=deferred<any[]>();vi.spyOn(api,'approveAdaptationProposal').mockReturnValue(approving.promise);mount();await screen.findByText('Lifecycle proposal');
  fireEvent.click(screen.getByRole('button',{name:'批准方案'}));await waitFor(()=>expect(api.approveAdaptationProposal).toHaveBeenCalledTimes(1));vi.mocked(api.adaptationProposals).mockReturnValueOnce(refreshing.promise);
  await act(async()=>approving.resolve({...row(2),status:'APPROVED'}));await waitFor(()=>expect(api.adaptationProposals).toHaveBeenCalledTimes(2));
  const button=screen.getByRole('button',{name:'批准方案'}) as HTMLButtonElement;expect(button.disabled).toBe(true);fireEvent.click(button);expect(api.approveAdaptationProposal).toHaveBeenCalledTimes(1);
  await act(async()=>refreshing.resolve([{...row(2),status:'APPROVED'}]));await waitFor(()=>expect((screen.getByRole('button',{name:'生成改编版本'}) as HTMLButtonElement).disabled).toBe(false));
});
