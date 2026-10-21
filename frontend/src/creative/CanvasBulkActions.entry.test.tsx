// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {MediaCanvasViewPanel} from './MediaCanvasViewPanel';
import type {CanvasDefinition,CanvasViewRecord} from './studioCanvasViewClient';
const clone=<T,>(v:T):T=>structuredClone(v);
const scope={mode:'local' as const,novel_id:'project'};
const initial:CanvasDefinition={schema_version:1,title:'Original',viewport:{x:0,y:0,zoom:1},cards:[{id:'a',position:{x:10,y:20},asset:{asset_id:'asset',version:1,digest:'a'.repeat(64),kind:'audio'}},{id:'b',position:{x:150,y:70},asset:{asset_id:'asset',version:1,digest:'a'.repeat(64),kind:'audio'}}],groups:[{id:'group',name:'Group',card_ids:['a','b'],collapsed:false}]};
function row(definition:CanvasDefinition,version=1):CanvasViewRecord{return {id:'view',project_id:'project',scope,version,definition:clone(definition),definition_digest:'b'.repeat(64),reference_states:definition.cards.map(c=>({card_id:c.id,state:'CURRENT_METADATA' as const,filename:'source.wav'})),created_at:'2026-10-21',updated_at:'2026-10-21',execution_authority:false,binary_content_verified:false,capacity:{history_used:0,record_bytes:1200}} as CanvasViewRecord;}
function rig(){let saved=row(initial);const views={list:vi.fn(async()=>({items:[{id:'view',title:'Saved',version:saved.version,card_count:saved.definition.cards.length}]})),get:vi.fn(async()=>clone(saved)),save:vi.fn(async(_id:string,version:number,definition:CanvasDefinition)=>{expect(version).toBe(saved.version);saved=row(definition,version+1);return clone(saved);}),create:vi.fn()};
 const props:any={active:true,denied:false,identity:'owner',client:{graphs:{canvasViews:views},assets:vi.fn()},draftOwner:{projectId:'project',incarnation:'file:00000000-0000-0000-0000-000000000001',actorId:'actor',actorWorkspaceId:'',mode:'local',workspaceId:'',storylineId:'',branchId:''},canMutate:true,busy:false,externalDirty:false,isCurrent:()=>true,read:<T,>(f:()=>Promise<T>)=>f(),mutate:<T,>(f:()=>Promise<T>)=>f(),onDirtyChange:vi.fn()};return{props,views};}
async function open(){fireEvent.click(screen.getByText('读取已存画布'));fireEvent.click(await screen.findByText('Saved · v1 · 2 张'));await screen.findByText(/共 2\/1000/);fireEvent.click(screen.getByText('选择全部卡片（含视口外）'));}
beforeEach(()=>{vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);});afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('requires every affected card, performs one original draft edit, and preserves undo/redo plus original Save/reopen',async()=>{
 const {props,views}=rig();const view=render(<MediaCanvasViewPanel {...props}/>);await open();fireEvent.change(screen.getByLabelText('多选操作影响预览'),{target:{value:'REMOVE_CARDS'}});
 const apply=screen.getByRole('button',{name:'应用到当前画布草稿（仍需 Save）'});expect((apply as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByLabelText('确认卡片 a 的本次影响'));expect((apply as HTMLButtonElement).disabled).toBe(true);fireEvent.click(screen.getByLabelText('确认卡片 b 的本次影响'));fireEvent.click(apply);
 expect(screen.getByText(/共 0\/1000/)).toBeTruthy();expect(views.save).not.toHaveBeenCalled();expect(views.create).not.toHaveBeenCalled();
 fireEvent.click(screen.getByText('撤销媒体画布编辑'));expect(screen.getByText(/共 2\/1000/)).toBeTruthy();fireEvent.click(screen.getByText('重做媒体画布编辑'));expect(screen.getByText(/共 0\/1000/)).toBeTruthy();
 fireEvent.click(screen.getByText('保存媒体画布'));await waitFor(()=>expect(views.save).toHaveBeenCalledTimes(1));expect(views.save.mock.calls[0][2].cards).toEqual([]);expect(views.save.mock.calls[0][2].groups).toEqual([{...initial.groups![0],card_ids:[]}]);
 view.unmount();render(<MediaCanvasViewPanel {...props}/>);fireEvent.click(screen.getByText('读取已存画布'));fireEvent.click(await screen.findByText('Saved · v2 · 0 张'));await screen.findByText(/共 0\/1000/);expect(views.save).toHaveBeenCalledTimes(1);
});
it('left alignment now previews first and owner change retires per-card confirmation before any draft mutation',async()=>{
 const {props,views}=rig();const view=render(<MediaCanvasViewPanel {...props}/>);await open();fireEvent.click(screen.getByText('左对齐所选卡片'));
 expect(screen.getByText(/共 2\/1000/)).toBeTruthy();expect(views.save).not.toHaveBeenCalled();fireEvent.click(screen.getByLabelText('确认卡片 a 的本次影响'));fireEvent.click(screen.getByLabelText('确认卡片 b 的本次影响'));
 view.rerender(<MediaCanvasViewPanel {...props} canMutate={false}/>);view.rerender(<MediaCanvasViewPanel {...props}/>);expect((screen.getByRole('button',{name:'应用到当前画布草稿（仍需 Save）'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByLabelText('确认卡片 a 的本次影响'));fireEvent.click(screen.getByLabelText('确认卡片 b 的本次影响'));fireEvent.click(screen.getByRole('button',{name:'应用到当前画布草稿（仍需 Save）'}));
 fireEvent.click(screen.getByText('保存媒体画布'));await waitFor(()=>expect(views.save).toHaveBeenCalledTimes(1));expect(views.save.mock.calls[0][2].cards.map(c=>c.position)).toEqual([{x:10,y:20},{x:10,y:70}]);expect(views.save.mock.calls[0][2].groups).toEqual(initial.groups);
});
it('failed CAS Save keeps the edited draft uncertain and never automatically repeats the save',async()=>{
 const {props,views}=rig();views.save.mockRejectedValueOnce(new Error('CAS changed'));render(<MediaCanvasViewPanel {...props}/>);await open();fireEvent.change(screen.getByLabelText('多选操作影响预览'),{target:{value:'REMOVE_CARDS'}});fireEvent.click(screen.getByLabelText('确认卡片 a 的本次影响'));fireEvent.click(screen.getByLabelText('确认卡片 b 的本次影响'));fireEvent.click(screen.getByRole('button',{name:'应用到当前画布草稿（仍需 Save）'}));fireEvent.click(screen.getByText('保存媒体画布'));await screen.findByText(/保存结果尚未确认/);expect(screen.getByText(/共 0\/1000/)).toBeTruthy();expect(views.save).toHaveBeenCalledTimes(1);expect((screen.getByText('保存媒体画布') as HTMLButtonElement).disabled).toBe(true);
});
