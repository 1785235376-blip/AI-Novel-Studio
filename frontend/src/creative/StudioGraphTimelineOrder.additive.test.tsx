// @vitest-environment jsdom
import {useState} from 'react';
import {act,cleanup,fireEvent,render,renderHook,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {useStudioGraphTimelineEditor} from './useStudioGraphTimelineEditor';
import {StudioGraphTimelineNodeEditor} from './StudioGraphTimelineNodeEditor';
import type {StudioGraphClient} from './studioGraphClient';
import type {StudioGraphNode,StudioGraphParameters} from './studioGraphTypes';
const node=():StudioGraphNode=>({id:'timeline-node',definition_id:'timeline_export',definition_version:1,enabled:true,position:{x:0,y:0},parameters:{timeline_snapshot:{id:'timeline',version:1,digest:'a'.repeat(64)},export_profile:{preset:'REVIEW_MP4'},source_bindings:[{port:'source_1',clip_id:'clip'}],edit_operations:[{op:'clip.trim',clip_id:'clip',in_ms:0,out_ms:1000,ripple:false},{op:'clip.slip',clip_id:'clip',offset_ms:10},{op:'clip.move',clip_id:'clip',track_id:'video',start_ms:0}]}});
const client={} as StudioGraphClient;
const props=(value=node())=>({client,node:value,editable:true,identity:'project',isCurrent:()=>true,isBusy:()=>false,read:async<T,>(work:()=>Promise<T>)=>work(),update:vi.fn()});
afterEach(cleanup);
it('reorders exact operations preserving bindings/source/profile and does not mutate input',()=>{
 const value=props(),before=structuredClone(value.node),{result}=renderHook(()=>useStudioGraphTimelineEditor(value));act(()=>result.current.moveOperation(0,2));
 const next=value.update.mock.calls[0][0] as StudioGraphParameters;expect(next.edit_operations).toEqual([before.parameters.edit_operations![1],before.parameters.edit_operations![2],before.parameters.edit_operations![0]]);expect(next.timeline_snapshot).toEqual(before.parameters.timeline_snapshot);expect(next.source_bindings).toEqual(before.parameters.source_bindings);expect(next.export_profile).toEqual(before.parameters.export_profile);expect(value.node).toEqual(before);
});
it('rejects invalid indices, permission loss and retained list controls across node ABA',()=>{
 const value=props(),view=renderHook(p=>useStudioGraphTimelineEditor(p),{initialProps:value});const oldMove=view.result.current.moveOperation,oldRemove=view.result.current.removeOperation;
 for(const [a,b] of [[-1,0],[0,3],[0,0],[.5,1],[0,Infinity]])act(()=>oldMove(a,b));expect(value.update).not.toHaveBeenCalled();
 view.rerender({...value,editable:false});act(()=>oldMove(0,1));expect(value.update).not.toHaveBeenCalled();
 view.rerender({...value,node:{...node(),id:'other'}});view.rerender(value);act(()=>{oldMove(0,1);oldRemove(0);});expect(value.update).not.toHaveBeenCalled();act(()=>view.result.current.moveOperation(1,0));expect(value.update).toHaveBeenCalledTimes(1);
});
it('mounts explicit adjacent controls and preserves normal removal without any transport calls',()=>{
 const writes=vi.fn();function Harness(){const [current,setCurrent]=useState(node);const state=useStudioGraphTimelineEditor({...props(current),update:next=>{writes(next);setCurrent({...current,parameters:next});}});return <StudioGraphTimelineNodeEditor node={current} state={state} editable connectedPorts={['source_1']}/>;}
 render(<Harness/>);expect((screen.getByLabelText('上移第 1 项剪辑操作') as HTMLButtonElement).disabled).toBe(true);expect((screen.getByLabelText('下移第 3 项剪辑操作') as HTMLButtonElement).disabled).toBe(true);fireEvent.click(screen.getByLabelText('下移第 1 项剪辑操作'));expect(writes.mock.calls[0][0].edit_operations.map((v:{op:string})=>v.op)).toEqual(['clip.slip','clip.trim','clip.move']);fireEvent.click(screen.getByLabelText('上移第 2 项剪辑操作'));expect(writes.mock.calls[1][0].edit_operations).toEqual(node().parameters.edit_operations);fireEvent.click(screen.getAllByText('移除此剪辑操作')[1]);expect(writes.mock.calls[2][0].edit_operations).toHaveLength(2);
});
