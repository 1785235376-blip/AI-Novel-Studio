// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {SavedCanvasVideoDraftPanel as Panel,type SavedCanvasVideoDraftPanelProps as Props} from './SavedCanvasVideoDraftPanel';
import {savedDraftFixture} from './savedDraft.testFixtures';
import type {StudioTimelineRow} from '../studioTimelineTypes';
const list=()=>screen.getByRole('button',{name:'读取已保存视频输入草稿'});
const selection=()=>screen.getByLabelText('已保存的视频输入草稿');
const consent=()=>screen.getByLabelText('我已核对所选版本与来源，仅恢复输入草稿') as HTMLInputElement;
const resume=()=>screen.getByRole('button',{name:'明确仅恢复输入草稿'});
function retained(element:HTMLElement){const key=Object.keys(element).find(k=>k.startsWith('__reactProps'));return (element as any)[key!].onClick as ()=>unknown;}
function setup(extra:Partial<Props>={},rows=[savedDraftFixture()]){
 const props:Props={owner:{client:'original'},current:true,canMutate:true,busy:false,isCurrent:()=>true,onList:vi.fn(async()=>rows),onResume:vi.fn(),...extra};
 const view=render(<Panel {...props}/>);return {props,view,rows};
}
async function choose(id='saved-video-draft'){fireEvent.click(list());await waitFor(()=>expect(selection()).toBeTruthy());fireEvent.change(selection(),{target:{value:id}});}
afterEach(cleanup);
it('requires list, explicit selection and input-only consent before exactly one recovery',async()=>{
 const {props,rows}=setup();expect(props.onList).not.toHaveBeenCalled();expect(props.onResume).not.toHaveBeenCalled();
 await choose();expect(consent().checked).toBe(false);expect((resume() as HTMLButtonElement).disabled).toBe(true);expect(screen.getByText(/范围 1000–1600 毫秒/)).toBeTruthy();
 consent().focus();expect(document.activeElement).toBe(consent());fireEvent.click(consent());resume().focus();expect(document.activeElement).toBe(resume());
 const click=retained(resume());await act(async()=>{click();click();});expect(props.onResume).toHaveBeenCalledTimes(1);expect(props.onResume).toHaveBeenCalledWith(rows[0]);expect((resume() as HTMLButtonElement).disabled).toBe(true);
 expect(screen.getByText(/没有派发或采用/)).toBeTruthy();
});
it('shows honest empty state and filters historical, unrelated or corrupt rows',async()=>{
 const stale=savedDraftFixture('old');stale.version++;
 const plain={...savedDraftFixture('plain'),canvas_video_draft:undefined};
 const corrupt={...savedDraftFixture('bad'),canvas_video_draft_digest:'unavailable'};
 setup({},[stale,plain,corrupt]);fireEvent.click(list());await waitFor(()=>expect(screen.getByText('没有当前版本可恢复的未入队视频派生输入。')).toBeTruthy());expect(screen.queryByRole('checkbox')).toBeNull();
});
it('offers read-only list without mutation permission and does not permanently lock after busy',async()=>{
 const {props,view}=setup({canMutate:false});await choose();expect(consent().disabled).toBe(true);expect((resume() as HTMLButtonElement).disabled).toBe(true);
 view.rerender(<Panel {...props} busy/>);expect((list() as HTMLButtonElement).disabled).toBe(true);
 view.rerender(<Panel {...props}/>);expect((list() as HTMLButtonElement).disabled).toBe(false);expect(props.onResume).not.toHaveBeenCalled();
});
it('keeps a readonly list response across a transient owner busy state while retiring consent',async()=>{
 let resolve!:(v:StudioTimelineRow[])=>void;const pending=new Promise<StudioTimelineRow[]>(r=>{resolve=r;});
 const {props,view,rows}=setup({onList:vi.fn(()=>pending)});fireEvent.click(list());view.rerender(<Panel {...props} busy/>);view.rerender(<Panel {...props}/>);
 await act(async()=>resolve(rows));expect(selection()).toBeTruthy();expect(props.onResume).not.toHaveBeenCalled();
});
it('suppresses a late list after owner replacement, without retaining a pending lock',async()=>{
 let resolve!:(v:StudioTimelineRow[])=>void;const pending=new Promise<StudioTimelineRow[]>(r=>{resolve=r;});
 const {props,view,rows}=setup({onList:vi.fn(()=>pending)});fireEvent.click(list());const next={...props,owner:{client:'next'},onList:vi.fn(async()=>[savedDraftFixture('next')])};view.rerender(<Panel {...next}/>);
 await act(async()=>resolve(rows));expect(screen.queryByRole('combobox')).toBeNull();fireEvent.click(list());await waitFor(()=>expect(selection()).toBeTruthy());expect(screen.queryByRole('option',{name:/original/})).toBeNull();
});
it.each(['owner','owner-mutation','method','getter','current','permission','busy'])('retires an observed %s ABA from a captured recovery click',async kind=>{
 const {props,view}=setup();await choose();fireEvent.click(consent());const click=retained(resume());let current=true;const next={...props};
 if(kind==='owner')next.owner={client:'other'};
 if(kind==='owner-mutation')Object.assign(props.owner,{generation:2});
 if(kind==='method')next.onResume=vi.fn();
 if(kind==='getter')next.isCurrent=()=>false;
 if(kind==='current')next.current=false;
 if(kind==='permission')next.canMutate=false;
 if(kind==='busy')next.busy=true;
 view.rerender(<Panel {...next}/>);act(()=>{click();});
 if(kind==='owner-mutation')delete (props.owner as any).generation;
 view.rerender(<Panel {...props}/>);act(()=>{click();});expect(props.onResume).not.toHaveBeenCalled();
});
it.each(['array','row','source','pin','command','digest','owner-method','owner-getter'])('latches observed %s mutation without rerender before ABA restoration',async kind=>{
 // React scalar props change through rerender (covered above); these mutate shared owner/row references.
 let allowed=true;const owner={read:()=>true};const {props,rows}=setup({owner,isCurrent:()=>allowed});await choose();fireEvent.click(consent());const click=retained(resume());const original=structuredClone(rows[0]),method=owner.read;
 if(kind==='array')rows[0]=savedDraftFixture('replacement');
 if(kind==='row')rows[0].version++;
 if(kind==='source')rows[0].canvas_video_draft!.source_snapshots[0].version++;
 if(kind==='pin')rows[0].canvas_video_draft!.canvas_return.card_id='replaced';
 if(kind==='command')rows[0].canvas_video_draft!.parameters.out_ms+=40;
 if(kind==='digest')rows[0].canvas_video_draft_digest='b'.repeat(64);
 if(kind==='owner-method')owner.read=()=>false;
 if(kind==='owner-getter')allowed=false;
 act(()=>{click();});Object.assign(rows[0],original);owner.read=method;allowed=true;props.canMutate=true;props.busy=false;act(()=>{click();});expect(props.onResume).not.toHaveBeenCalled();
});
it('requires a fresh selection and consent after another list, even with the same row object',async()=>{
 const {props}=setup();await choose();fireEvent.click(consent());const click=retained(resume());fireEvent.click(list());await waitFor(()=>expect(selection()).toBeTruthy());act(()=>{click();});expect(props.onResume).not.toHaveBeenCalled();
 fireEvent.change(selection(),{target:{value:'saved-video-draft'}});expect(consent().checked).toBe(false);fireEvent.click(consent());await act(async()=>{fireEvent.click(resume());});expect(props.onResume).toHaveBeenCalledTimes(1);
});
it('switching selections retires the old callback and requires fresh consent',async()=>{
 const {props}=setup({},[savedDraftFixture('one'),savedDraftFixture('two')]);await choose('one');fireEvent.click(consent());const click=retained(resume());fireEvent.change(selection(),{target:{value:'two'}});act(()=>{click();});expect(props.onResume).not.toHaveBeenCalled();expect(consent().checked).toBe(false);
});
it('shows fixed errors without leaking arbitrary server messages or provider credentials',async()=>{
 const {props,view}=setup({onList:vi.fn(async()=>{throw new Error('API_KEY_NEVER_DISPLAY');})});fireEvent.click(list());await waitFor(()=>expect(screen.getByRole('alert')).toBeTruthy());expect(document.body.textContent).not.toContain('API_KEY_NEVER_DISPLAY');
 const next={...props,onList:vi.fn(async()=>[savedDraftFixture()]),onResume:vi.fn(async()=>{throw new Error('BEARER_NEVER_DISPLAY');})};view.rerender(<Panel {...next}/>);await choose();fireEvent.click(consent());await act(async()=>{fireEvent.click(resume());});expect(screen.getByRole('alert')).toBeTruthy();expect(document.body.textContent).not.toContain('BEARER_NEVER_DISPLAY');expect((resume() as HTMLButtonElement).disabled).toBe(true);
});
it('rejects duplicate list identities without guessing a row',async()=>{
 setup({},[savedDraftFixture(),savedDraftFixture()]);fireEvent.click(list());await waitFor(()=>expect(screen.getByRole('alert')).toBeTruthy());expect(screen.queryByRole('combobox')).toBeNull();
});
it('suppresses late errors after unmount and retained operations after current=false without reading old getter',async()=>{
 let reject!:(v:unknown)=>void;const {props,view}=setup({onResume:vi.fn(()=>new Promise<void>((_r,j)=>{reject=j;}))});await choose();fireEvent.click(consent());const click=retained(resume());act(()=>{click();});view.unmount();await act(async()=>reject(new Error('DO_NOT_RENDER')));expect(document.body.textContent).not.toContain('DO_NOT_RENDER');
 const getter=vi.fn(()=>{throw new Error('old getter');});const next=render(<Panel {...props} current={false} isCurrent={getter}/>);act(()=>{click();});expect(getter).not.toHaveBeenCalled();next.unmount();
});
