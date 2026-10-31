// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TrackHeaderPanel } from './TrackHeaderPanel';
import { StudioTimelineEditor } from '../creative/StudioTimelineEditor';
import { checkedTimelineRow, cloneTimeline, type StudioTimelineDraft, type StudioTimelineRow } from '../creative/studioTimelineTypes';
import type { StudioTimelineEditorProps } from '../creative/useStudioTimelineEditor';
import type { StudioProductionClient } from '../creative/studioProductionClient';
import type { StudioAsset } from '../creative/studioClient';

const source = (kind: 'image' | 'audio') => ({ id:`asset-${kind}`,kind:'ASSET' as const,asset_kind:kind,version:1,digest:'a'.repeat(64) });
function row(): StudioTimelineRow {
  const sound=(id:string,start:number)=>({id,source_snapshot:source('audio'),start_ms:start,in_ms:0,out_ms:500,speed_num:1,speed_den:1});
  return checkedTimelineRow({id:'arbitrary-selection',version:1,timeline_digest:'b'.repeat(64),title:'Arbitrary selection fixture',created_at:'2026-10-19',updated_at:'2026-10-19',
    timeline:{schema_version:2,duration_ms:8000,width:64,height:64,fps:25,captions:[{start_ms:200,end_ms:800,text:'Unselected caption'}],tracks:[
      {id:'visual',kind:'VIDEO',order:0,muted:false,gain_db:0,clips:[{id:'still',source_snapshot:source('image'),start_ms:0,in_ms:0,out_ms:7000,x:0,y:0,width:64,height:64}]},
      {id:'sound',kind:'AUDIO',order:1,muted:false,gain_db:0,clips:[sound('a1',1000),sound('a2',3000)]},
      {id:'other-sound',kind:'AUDIO',order:2,muted:false,gain_db:0,clips:[sound('b1',2000),sound('b2',4500)]},
    ]}});
}
const button=(name:string)=>screen.getByRole('button',{name});
const selected=()=>screen.getAllByRole('button').filter(node=>node.getAttribute('aria-pressed')==='true').map(node=>node.textContent);
function Controlled(){const [ids,setIds]=useState<string[]>([]);return <TrackHeaderPanel timeline={row().timeline} selectedClipIds={ids} editable onSelectClips={setIds}/>;}
afterEach(()=>{cleanup();vi.restoreAllMocks();});

describe('actual arbitrary clip selection entry',()=>{
  it('keeps plain click single-select and Ctrl toggles only the requested cross-track subset',()=>{
    render(<Controlled/>);fireEvent.click(button('a1'));fireEvent.click(button('b2'),{ctrlKey:true});expect(selected()).toEqual(['a1','b2']);
    fireEvent.click(button('a2'),{ctrlKey:true});expect(selected()).toEqual(['a1','a2','b2']);
    fireEvent.click(button('a2'),{ctrlKey:true});expect(selected()).toEqual(['a1','b2']);
    fireEvent.click(button('b1'));expect(selected()).toEqual(['b1']);
  });
  it('supports Cmd toggle and normalizes stable visual order regardless of click order',()=>{
    render(<Controlled/>);fireEvent.click(button('b2'));fireEvent.click(button('a1'),{metaKey:true});expect(selected()).toEqual(['a1','b2']);
    fireEvent.click(button('b2'),{metaKey:true});expect(selected()).toEqual(['a1']);fireEvent.click(button('a1'),{metaKey:true});expect(selected()).toEqual([]);
  });
  it('supports focused Ctrl/Cmd keyboard toggles once and refuses IME or key repeat',()=>{
    render(<Controlled/>);fireEvent.click(button('a1'));
    fireEvent.keyDown(button('b2'),{key:'Enter',ctrlKey:true});expect(selected()).toEqual(['a1','b2']);
    fireEvent.keyDown(button('b2'),{key:'Enter',ctrlKey:true,repeat:true});expect(selected()).toEqual(['a1','b2']);
    fireEvent.keyDown(button('a2'),{key:' ',metaKey:true});expect(selected()).toEqual(['a1','a2','b2']);
    fireEvent.keyDown(button('a2'),{key:' ',metaKey:true});expect(selected()).toEqual(['a1','b2']);
    fireEvent.compositionStart(button('a2'));fireEvent.keyDown(button('a2'),{key:'Enter',ctrlKey:true});expect(selected()).toEqual(['a1','b2']);
    fireEvent.compositionEnd(button('a2'));fireEvent.keyDown(button('a2'),{key:'Enter',ctrlKey:true,isComposing:true,keyCode:229});expect(selected()).toEqual(['a1','b2']);
  });
  it('cleans unknown/duplicate selections and removed clips through the original callback',()=>{
    const change=vi.fn();const timeline=row().timeline;const view=render(<TrackHeaderPanel timeline={timeline} selectedClipIds={['gone','b2','a1','a1']} editable onSelectClips={change}/>);
    expect(change).toHaveBeenLastCalledWith(['a1','b2']);change.mockClear();
    const next=cloneTimeline(timeline);next.tracks[1].clips=next.tracks[1].clips.filter(clip=>clip.id!=='a1');
    view.rerender(<TrackHeaderPanel timeline={next} selectedClipIds={['a1','b2']} editable onSelectClips={change}/>);
    expect(change).toHaveBeenLastCalledWith(['b2']);
  });
  it('does not select while unavailable or during IME composition, then resumes ordinary selection',()=>{
    const change=vi.fn();const view=render(<TrackHeaderPanel timeline={row().timeline} selectedClipIds={[]} editable={false} onSelectClips={change}/>);
    fireEvent.click(button('a1'),{ctrlKey:true});expect(change).not.toHaveBeenCalled();
    view.rerender(<TrackHeaderPanel timeline={row().timeline} selectedClipIds={[]} editable onSelectClips={change}/>);
    fireEvent.compositionStart(button('a1'));fireEvent.click(button('a1'),{ctrlKey:true});expect(change).not.toHaveBeenCalled();
    fireEvent.compositionEnd(button('a1'));fireEvent.click(button('a1'));expect(change).toHaveBeenCalledWith(['a1']);
  });
});

function setup(input=row()){
  let saved=cloneTimeline(input);
  const client={timelineList:vi.fn(async()=>({items:[cloneTimeline(saved)]})),timelineGet:vi.fn(async()=>cloneTimeline(saved)),
    timelineSave:vi.fn(async(_id:string|undefined,body:StudioTimelineDraft&{expected_version:number})=>{saved=checkedTimelineRow({...saved,title:body.title,timeline:body.timeline,version:body.expected_version+1,timeline_digest:'c'.repeat(64)});return cloneTimeline(saved);}),
    timelineRender:vi.fn(),timelineEdit:vi.fn(),list:vi.fn()};
  const assets=['image','audio'].map(kind=>({id:`asset-${kind}`,kind,version:1,sha256:'a'.repeat(64),filename:`${kind}.fixture`,deleted_at:null})) as unknown as StudioAsset[];
  const props:StudioTimelineEditorProps={projectId:'nle-selection-fixture',client:client as unknown as StudioProductionClient,assets,canMutate:true,busy:false,isCurrent:()=>true,read:async work=>work(),mutate:async work=>work(),onDirtyChange:vi.fn(),onJob:vi.fn(),onUnavailable:vi.fn()};
  return {client,props,view:render(<StudioTimelineEditor {...props}/>)};
}
async function adopt(version=1){await screen.findByRole('option',{name:`Arbitrary selection fixture · v${version}`});fireEvent.change(screen.getByLabelText('读取已保存时间线'),{target:{value:'arbitrary-selection'}});await screen.findByRole('heading',{name:`Arbitrary selection fixture · v${version}`});fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择'));fireEvent.click(button('采用服务端时间线'));}
const find=(draft:StudioTimelineDraft,id:string)=>draft.timeline.tracks.flatMap(track=>track.clips).find(clip=>clip.id===id)!;

describe('original mounted multitrack edit owner',()=>{
  it('moves only the selected cross-track subset, preserves offsets/other content, undoes/redoes once and saves/reopens with original CAS',async()=>{
    const state=setup();await adopt();fireEvent.click(button('b2'));fireEvent.click(button('a1'),{ctrlKey:true});
    expect(selected()).toEqual(['a1','b2']);const preview=screen.getByRole('region',{name:'播放头拆分预览'});expect(preview.textContent).toContain('a1');expect(preview.textContent).toContain('b2');expect(preview.textContent).not.toContain('a2');
    fireEvent.change(screen.getByLabelText('整体移动增量（毫秒，可为负）'),{target:{value:'500'}});expect(state.client.timelineSave).not.toHaveBeenCalled();fireEvent.click(button('整体移动所选片段'));
    expect(screen.getByText(/整体移动已应用到本地草稿/)).toBeTruthy();fireEvent.click(button('撤销本地编辑'));expect((button('撤销本地编辑') as HTMLButtonElement).disabled).toBe(true);fireEvent.click(button('重做本地编辑'));
    fireEvent.click(button('保存时间线'));await waitFor(()=>expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
    const body=state.client.timelineSave.mock.calls[0][1];const expected=cloneTimeline(row());find(expected,'a1').start_ms+=500;find(expected,'b2').start_ms+=500;
    expect(body.expected_version).toBe(1);expect(body.timeline).toEqual(expected.timeline);expect(find(body,'b2').start_ms-find(body,'a1').start_ms).toBe(3500);
    for(const id of ['still','a2','b1'])expect(find(body,id)).toEqual(find(row(),id));expect(state.client.timelineEdit).not.toHaveBeenCalled();expect(state.client.timelineRender).not.toHaveBeenCalled();
    state.view.unmount();render(<StudioTimelineEditor {...state.props}/>);await adopt(2);expect(selected()).toEqual([]);
    expect((within(screen.getByRole('region',{name:'轨道 2 片段 1'})).getByLabelText('放入时间线（毫秒）') as HTMLInputElement).value).toBe('1500');
    expect((within(screen.getByRole('region',{name:'轨道 3 片段 2'})).getByLabelText('放入时间线（毫秒）') as HTMLInputElement).value).toBe('5000');
  });
  it('keeps locked-track batch refusal in the original owner instead of moving an unselected substitute',async()=>{
    const input=row();input.timeline.tracks[2].locked=true;const state=setup(input);await adopt();fireEvent.click(button('a1'));fireEvent.click(button('b2'),{ctrlKey:true});expect(selected()).toEqual(['a1','b2']);
    fireEvent.change(screen.getByLabelText('整体移动增量（毫秒，可为负）'),{target:{value:'500'}});fireEvent.click(button('整体移动所选片段'));
    expect(screen.getByText(/所选片段包含锁定轨道/)).toBeTruthy();expect((button('撤销本地编辑') as HTMLButtonElement).disabled).toBe(true);expect(state.client.timelineSave).not.toHaveBeenCalled();
  });
});

it('clears a selection when the original owner adopts another saved document reusing the same clip IDs',async()=>{
  const state=setup();await adopt();fireEvent.click(button('a1'));fireEvent.click(button('b2'),{ctrlKey:true});expect(selected()).toEqual(['a1','b2']);
  const second=checkedTimelineRow({...cloneTimeline(row()),id:'another-saved-timeline',title:'Second saved timeline'});
  state.client.timelineList.mockResolvedValue({items:[row(),second]});
  state.client.timelineGet.mockImplementation(async(...args:unknown[])=>cloneTimeline(args[0]===second.id?second:row()));
  fireEvent.click(button('刷新时间线列表'));await screen.findByRole('option',{name:'Second saved timeline · v1'});
  fireEvent.change(screen.getByLabelText('读取已保存时间线'),{target:{value:second.id}});await screen.findByRole('heading',{name:'Second saved timeline · v1'});
  fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择'));fireEvent.click(button('采用服务端时间线'));
  expect(selected()).toEqual([]);expect(state.client.timelineSave).not.toHaveBeenCalled();
});

it('clears the controlled view when a supplied document ID changes even with byte-identical timeline content',()=>{
  function Document({id}:{id:string}){const [ids,setIds]=useState(['a1','b2']);return <TrackHeaderPanel documentId={id} timeline={row().timeline} selectedClipIds={ids} editable onSelectClips={setIds}/>;}
  const view=render(<Document id="first"/>);expect(selected()).toEqual(['a1','b2']);view.rerender(<Document id="second"/>);expect(selected()).toEqual([]);
});
