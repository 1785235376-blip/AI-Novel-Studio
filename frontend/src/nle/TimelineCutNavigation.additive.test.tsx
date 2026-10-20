// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TimelineWorkspacePanel } from './TimelineWorkspacePanel';
import { checkedTimeline, cloneTimeline } from '../creative/studioTimelineTypes';

const source={kind:'ASSET',id:'sound',asset_kind:'audio',version:1,digest:'a'.repeat(64)};
const clip=(id:string,start_ms:number,in_ms:number,out_ms:number,speed_num=1,speed_den=1)=>({id,source_snapshot:source,start_ms,in_ms,out_ms,speed_num,speed_den});
export const timeline=checkedTimeline({schema_version:3,media_kind:'AUDIO',duration_ms:5000,tracks:[
 {id:'first',kind:'AUDIO',order:0,muted:false,gain_db:0,clips:[clip('a',100,100,700,3,2),clip('b',1000,0,1000)]},
 {id:'locked',kind:'AUDIO',order:1,muted:true,locked:true,gain_db:0,clips:[clip('c',500,0,500),clip('d',4000,0,1000)]},
]});
const previous=()=>screen.getByRole('button',{name:'上一个剪切点'});
const next=()=>screen.getByRole('button',{name:'下一个剪切点'});
const ruler=()=>screen.getByRole('region',{name:'时间线标尺'});
const head=()=>Number(ruler().getAttribute('data-playhead-ms'));
const edit=vi.fn(),navigate=vi.fn();
function Workspace({editable=true,isCurrent=()=>true}:{editable?:boolean;isCurrent?:()=>boolean}){
 const [playhead,setPlayhead]=useState(0);
 return <TimelineWorkspacePanel projectId="fixture" identity="local" documentId="saved-one" timeline={timeline}
  selectedClipIds={[]} playheadMs={playhead} viewStartMs={0} viewScale={0.1} editable={editable}
  onPlayhead={ms=>{navigate(ms);setPlayhead(ms);}} onView={vi.fn()} onEdit={edit} onSelectClips={vi.fn()} isSplitReviewCurrent={isCurrent}/>;
}
afterEach(()=>{cleanup();vi.restoreAllMocks();edit.mockReset();navigate.mockReset();});

it('jumps only to deduplicated real clip starts/retimed ends, including locked/muted track facts, without editing or wrapping',()=>{
 const fetch=vi.spyOn(globalThis,'fetch');render(<Workspace/>);
 expect((previous() as HTMLButtonElement).disabled).toBe(true);
 for(const ms of [100,500,1000,2000,4000,5000]){fireEvent.click(next());expect(head()).toBe(ms);}
 expect((next() as HTMLButtonElement).disabled).toBe(true);fireEvent.click(next());expect(head()).toBe(5000);
 for(const ms of [4000,2000,1000,500,100]){fireEvent.click(previous());expect(head()).toBe(ms);}
 expect((previous() as HTMLButtonElement).disabled).toBe(true);
 expect(navigate.mock.calls.map(([ms])=>ms)).toEqual([100,500,1000,2000,4000,5000,4000,2000,1000,500,100]);
 expect(edit).not.toHaveBeenCalled();expect(fetch).not.toHaveBeenCalled();
});

it('uses local ArrowUp/ArrowDown keys and updates the original numeric playhead view',()=>{
 render(<Workspace/>);ruler().focus();fireEvent.keyDown(ruler(),{key:'ArrowDown'});expect(head()).toBe(100);
 expect((within(ruler()).getByLabelText('播放头（毫秒）') as HTMLInputElement).value).toBe('100');
 fireEvent.keyDown(next(),{key:'ArrowDown'});expect(head()).toBe(500);
 fireEvent.keyDown(ruler(),{key:'ArrowUp'});expect(head()).toBe(100);
 fireEvent.keyDown(ruler(),{key:'ArrowUp'});expect(head()).toBe(100);
 expect(edit).not.toHaveBeenCalled();
});

it('does not intercept text inputs, contenteditable, IME, modified/repeated keys or keys outside this ruler',()=>{
 render(<Workspace/>);const input=within(ruler()).getByLabelText('播放头（毫秒）');
 fireEvent.keyDown(input,{key:'ArrowDown'});fireEvent.keyDown(document.body,{key:'ArrowDown'});
 const content=document.createElement('div');content.setAttribute('contenteditable','true');const child=document.createElement('span');content.append(child);ruler().append(content);
 fireEvent.keyDown(child,{key:'ArrowDown'});content.remove();
 fireEvent.keyDown(ruler(),{key:'ArrowDown',ctrlKey:true});fireEvent.keyDown(ruler(),{key:'ArrowDown',metaKey:true});
 fireEvent.keyDown(ruler(),{key:'ArrowDown',altKey:true});fireEvent.keyDown(ruler(),{key:'ArrowDown',shiftKey:true});
 fireEvent.keyDown(ruler(),{key:'ArrowDown',repeat:true});fireEvent.keyDown(ruler(),{key:'ArrowDown',isComposing:true});fireEvent.keyDown(ruler(),{key:'ArrowDown',keyCode:229});
 fireEvent.compositionStart(ruler());fireEvent.keyDown(ruler(),{key:'ArrowDown'});fireEvent.click(next());expect(navigate).not.toHaveBeenCalled();
 fireEvent.compositionEnd(ruler());fireEvent.keyDown(ruler(),{key:'ArrowDown'});expect(head()).toBe(100);
});

it.each(['disabled','owner-refusal'] as const)('preserves original navigation refusal: %s',reason=>{
 render(<Workspace editable={reason!=='disabled'} isCurrent={()=>reason!=='owner-refusal'}/>);
 fireEvent.click(next());fireEvent.keyDown(ruler(),{key:'ArrowDown'});expect(navigate).not.toHaveBeenCalled();expect(edit).not.toHaveBeenCalled();
});

it('recomputes points after current timeline content changes instead of retaining old boundaries',()=>{
 const props={projectId:'fixture',identity:'local',documentId:'one',timeline,selectedClipIds:[],playheadMs:0,viewStartMs:0,viewScale:0.1,editable:true,onPlayhead:navigate,onView:vi.fn(),onEdit:edit,onSelectClips:vi.fn()};
 const view=render(<TimelineWorkspacePanel {...props}/>);fireEvent.click(next());expect(navigate).toHaveBeenLastCalledWith(100);
 const changed=cloneTimeline(timeline);changed.tracks[0].clips[0].start_ms=200;
 view.rerender(<TimelineWorkspacePanel {...props} timeline={changed}/>);fireEvent.click(next());expect(navigate).toHaveBeenLastCalledWith(200);
 view.rerender(<TimelineWorkspacePanel {...props} documentId="two" timeline={changed}/>);fireEvent.click(next());expect(navigate).toHaveBeenLastCalledWith(200);
});
