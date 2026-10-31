// @vitest-environment jsdom
import { act,cleanup,fireEvent,render,screen } from '@testing-library/react';
import { afterEach,expect,it,vi } from 'vitest';
import fixture from '../../../tests/fixtures/studio_dual_canvas_loop.json';
import { MediaCanvasHistoryPanel } from './MediaCanvasHistoryPanel';
import type { CanvasViewClient,CanvasViewHistory,CanvasViewRecord } from './studioCanvasViewClient';
afterEach(cleanup);
const retained=(el:HTMLElement)=>(el as any)[Object.keys(el).find(k=>k.startsWith('__reactProps$'))!].onClick as ()=>void;
function setup(incarnation:string|undefined=fixture.incarnation){
 const restore=vi.fn(async(..._args:Parameters<CanvasViewClient['restore']>)=>structuredClone(fixture.restored) as unknown as CanvasViewRecord);
 const props={base:structuredClone(fixture.returned) as unknown as CanvasViewRecord,client:{history:vi.fn(async()=>structuredClone(fixture.history) as unknown as CanvasViewHistory),restore} as unknown as CanvasViewClient,owner:{},incarnation,
  canMutate:true,externalDirty:false,busy:false,isCurrent:()=>true,read:async<T,>(f:()=>Promise<T>)=>f(),mutate:async<T,>(f:()=>Promise<T>)=>f(),onAdopt:vi.fn(),onUncertain:vi.fn()};
 const view=render(<MediaCanvasHistoryPanel {...props}/>);return {...view,props,restore};
}
async function choose(){fireEvent.click(screen.getByText('画布版本历史与恢复'));fireEvent.click(screen.getByRole('button',{name:'读取画布版本历史'}));fireEvent.change(await screen.findByLabelText('待恢复画布版本'),{target:{value:'1'}});}
it('keeps history read-only when the current context has not supplied incarnation',async()=>{
 const f=setup();f.rerender(<MediaCanvasHistoryPanel {...f.props} incarnation={undefined}/>);await choose();expect((screen.getByLabelText('确认创建新的当前版本并退役旧预览') as HTMLInputElement).disabled).toBe(true);expect(f.restore).not.toHaveBeenCalled();
});
it('does not revive retained restore consent after incarnation A/B/A',async()=>{
 const f=setup();await choose();fireEvent.click(screen.getByLabelText('确认创建新的当前版本并退役旧预览'));const old=retained(screen.getByRole('button',{name:'恢复此画布版本为新版本'}));
 f.rerender(<MediaCanvasHistoryPanel {...f.props} incarnation="other-incarnation"/>);f.rerender(<MediaCanvasHistoryPanel {...f.props}/>);await act(async()=>old());
 expect(f.restore).not.toHaveBeenCalled();expect(f.props.onAdopt).not.toHaveBeenCalled();
});
it('retains the history incarnation and refuses a late restore record after current incarnation changes',async()=>{
 const f=setup();let finish!:(value:CanvasViewRecord)=>void;f.restore.mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 await choose();fireEvent.click(screen.getByLabelText('确认创建新的当前版本并退役旧预览'));fireEvent.click(screen.getByRole('button',{name:'恢复此画布版本为新版本'}));
 expect(f.restore.mock.calls[0][0].incarnation).toBe(fixture.incarnation);
 f.rerender(<MediaCanvasHistoryPanel {...f.props} incarnation="new-incarnation"/>);await act(async()=>finish(structuredClone(fixture.restored) as unknown as CanvasViewRecord));
 expect(f.props.onAdopt).not.toHaveBeenCalled();expect(f.props.onUncertain).toHaveBeenCalledTimes(1);expect(f.restore).toHaveBeenCalledTimes(1);
});


it('shows the original per-card metadata comparison before a successful explicit restore',async()=>{
 const f=setup();await choose();expect(screen.getByRole('region',{name:'画布历史版本影响对比'})).toBeTruthy();
 fireEvent.click(screen.getByLabelText('确认创建新的当前版本并退役旧预览'));
 fireEvent.click(screen.getByRole('button',{name:'恢复此画布版本为新版本'}));
 await act(async()=>{});expect(f.restore).toHaveBeenCalledTimes(1);expect(f.props.onAdopt).toHaveBeenCalledTimes(1);
});
it.each(['layout','pin','permission','client'])('rechecks %s at the actual scheduled restore callback before sending',async mode=>{
 const f=setup();let release!:()=>Promise<void>;
 f.props.mutate=<T,>(work:()=>Promise<T>)=>new Promise<T>((resolve,reject)=>{release=async()=>{try{resolve(await work());}catch(error){reject(error);}};});
 f.rerender(<MediaCanvasHistoryPanel {...f.props}/>);await choose();fireEvent.click(screen.getByLabelText('确认创建新的当前版本并退役旧预览'));
 fireEvent.click(screen.getByRole('button',{name:'恢复此画布版本为新版本'}));
 if(mode==='layout')f.props.base.definition.cards[0].position.x++;
 if(mode==='pin')f.props.base.definition.cards[0].asset!.version++;
 if(mode==='permission')f.props.canMutate=false;
 if(mode==='client')f.props.client={...f.props.client};
 f.rerender(<MediaCanvasHistoryPanel {...f.props}/>);await act(async()=>release());
 expect(f.restore).not.toHaveBeenCalled();expect(f.props.onAdopt).not.toHaveBeenCalled();expect(f.props.onUncertain).not.toHaveBeenCalled();
});
it('retires observed metadata A/B/A even when an old restore callback is retained',async()=>{
 const f=setup();await choose();fireEvent.click(screen.getByLabelText('确认创建新的当前版本并退役旧预览'));
 const old=retained(screen.getByRole('button',{name:'恢复此画布版本为新版本'}));
 const x=f.props.base.definition.cards[0].position.x;f.props.base.definition.cards[0].position.x=x+1;
 await act(async()=>old());f.props.base.definition.cards[0].position.x=x;await act(async()=>old());
 expect(f.restore).not.toHaveBeenCalled();expect(f.props.onAdopt).not.toHaveBeenCalled();
});
