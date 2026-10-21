// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {CanvasImageTaskRecovery} from './CanvasImageTaskRecovery';
import native from './fixtures/canvasAudioTrim.native.json';
const clone=<T,>(v:T):T=>structuredClone(v);
function rig(status:'QUEUED'|'FAILED'|'UNKNOWN'='FAILED'){
 const job={...clone(native.queued),status,output_candidate:null,approved_asset_version:null};
 const canvas=clone(native.canvas),binding=native.command.canvas_return;
 const history={...clone(native.history),current_version:canvas.version,current_definition_digest:canvas.definition_digest};
 const production={list:vi.fn(async()=>[clone(job)]),get:vi.fn(async()=>clone(job)),create:vi.fn(),execute:vi.fn()};
 const views={history:vi.fn(async()=>history),get:vi.fn(async()=>canvas)};
 const props:any={client:{graphs:{canvasViews:views},asset:vi.fn(async()=>clone(native.source))},production,owner:{projectId:canvas.project_id,incarnation:binding.incarnation,actorId:'actor',actorWorkspaceId:'',mode:'local',workspaceId:'',storylineId:'',branchId:''},ownerToken:{},disabled:false,canMutate:true,isCurrent:()=>true,read:<T,>(f:()=>Promise<T>)=>f(),onResume:vi.fn()};return{props,production,views,job,canvas,history};
}
afterEach(cleanup);
async function load(){fireEvent.click(screen.getByText('读取有原位置绑定的卡片结果'));return screen.findByRole('button',{name:/核验并恢复原卡片任务/});}
it.each(['QUEUED','FAILED','UNKNOWN'] as const)('reopens the exact saved audio %s only after original Job/canvas/source reads, never creating/executing',async status=>{
 const e=rig(status);const first=render(<CanvasImageTaskRecovery {...e.props}/>);first.unmount();render(<CanvasImageTaskRecovery {...e.props}/>);
 expect(e.production.list).not.toHaveBeenCalled();fireEvent.click(await load());await waitFor(()=>expect(e.props.onResume).toHaveBeenCalledTimes(1));
 const [canvas,asset,job,origin]=e.props.onResume.mock.calls[0];expect(canvas.id).toBe(native.canvas.id);expect(asset.id).toBe(native.source.id);expect(job.status).toBe(status);expect(origin.binding).toEqual(native.command.canvas_return);
 expect(e.production.get).toHaveBeenCalledWith('audio',e.job.id);expect(e.views.history).toHaveBeenCalledWith(native.canvas.id);expect(e.production.create).not.toHaveBeenCalled();expect(e.production.execute).not.toHaveBeenCalled();
});
it.each(['version','deleted-card','source-pin','incarnation'] as const)('blocks reopened FAILED audio at changed %s without guessing a target',async mode=>{
 const e=rig();render(<CanvasImageTaskRecovery {...e.props}/>);const open=await load();
 if(mode==='version'){e.canvas.version++;e.history.current_version=e.canvas.version;}
 if(mode==='deleted-card')e.canvas.definition.cards=e.canvas.definition.cards.filter(c=>c.id!==native.command.canvas_return.card_id);
 if(mode==='source-pin')e.props.client.asset.mockResolvedValue({...clone(native.source),version:native.source.version+1});
 if(mode==='incarnation')e.history.incarnation='file:00000000-0000-0000-0000-000000000001';
 fireEvent.click(open);await screen.findByRole('status');expect(e.props.onResume).not.toHaveBeenCalled();expect(e.production.create).not.toHaveBeenCalled();expect(e.production.execute).not.toHaveBeenCalled();
});
it('retires a late original Job read after owner replacement without opening a task',async()=>{
 const e=rig();let resolve!:(v:unknown)=>void;e.production.get.mockImplementation(()=>new Promise(r=>{resolve=r;}) as any);
 const view=render(<CanvasImageTaskRecovery {...e.props}/>);fireEvent.click(await load());view.rerender(<CanvasImageTaskRecovery {...e.props} ownerToken={{}}/>);await act(async()=>resolve(clone(e.job)));expect(e.props.onResume).not.toHaveBeenCalled();expect(e.views.history).not.toHaveBeenCalled();
});
it('does not expose a failed generation provider as the local CPU recovery route',async()=>{
 const e=rig();e.production.list.mockResolvedValue([{...e.job,provider:{provider_id:'remote',model_id:'model',local:false,route_digest:'a'.repeat(64)}}] as any);render(<CanvasImageTaskRecovery {...e.props}/>);fireEvent.click(screen.getByText('读取有原位置绑定的卡片结果'));await screen.findByText(/没有可恢复/);expect(screen.queryByRole('button',{name:/核验并恢复原卡片任务/})).toBeNull();expect(e.production.create).not.toHaveBeenCalled();
});
