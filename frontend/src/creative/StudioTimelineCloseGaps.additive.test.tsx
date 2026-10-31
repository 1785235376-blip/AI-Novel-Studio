// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { previewTimelineCloseGaps } from './timelineCloseGaps';
import { StudioTimelineCloseGaps } from './StudioTimelineCloseGaps';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimelineDraft, checkedTimelineRow, cloneTimeline, type StudioTimelineDraft } from './studioTimelineTypes';
import type { StudioProductionClient } from './studioProductionClient';
const source=(kind:'video'|'audio')=>({id:`asset-${kind}`,kind:'ASSET' as const,asset_kind:kind,version:1,digest:'a'.repeat(64)});
const audio=(id:string,start:number,duration=1000)=>({id,source_snapshot:source('audio'),start_ms:start,in_ms:0,out_ms:duration});
function fixture():StudioTimelineDraft{return checkedTimelineDraft({title:'Original',timeline:{schema_version:2,duration_ms:10000,width:64,height:64,fps:25,captions:[{start_ms:5000,end_ms:6000,text:'Keep caption'}],tracks:[
 {id:'video',kind:'VIDEO',order:0,muted:false,gain_db:0,clips:[{id:'picture',source_snapshot:source('video'),start_ms:0,in_ms:0,out_ms:9000,x:0,y:0,width:64,height:64}]},
 {id:'sound',kind:'AUDIO',order:1,muted:false,gain_db:0,clips:[audio('late',6000),audio('first',1000),audio('overlap',1500),{...audio('speed',4000,2000),speed_num:2,speed_den:1}]},
]}});}
afterEach(cleanup);
it('closes union gaps using actual speed while preserving authored order, overlap, sources and other tracks',()=>{
 const draft=fixture();draft.timeline.tracks[1].clips.reverse();const before=cloneTimeline(draft),result=previewTimelineCloseGaps(draft,'sound',false);
 expect(result.gaps).toEqual([{start:2500,end:4000},{start:5000,end:6000}]);expect(result.removedMs).toBe(2500);
 expect(result.draft.timeline.tracks[1].clips.map(row=>[row.id,row.start_ms])).toEqual([['late',3500],['speed',2500],['overlap',1500],['first',1000]]);
 expect(result.draft.timeline.tracks[0]).toEqual(before.timeline.tracks[0]);expect(result.draft.timeline.captions).toEqual(before.timeline.captions);expect(result.draft.timeline.duration_ms).toBe(10000);expect(draft).toEqual(before);
 for(const clip of result.draft.timeline.tracks[1].clips){const original=before.timeline.tracks[1].clips.find(row=>row.id===clip.id)!;expect({...clip,start_ms:original.start_ms}).toEqual(original);}
});
it('requires explicit leading-gap choice and is idempotent',()=>{
 const result=previewTimelineCloseGaps(fixture(),'sound',true);expect(result.removedMs).toBe(3500);expect(result.draft.timeline.tracks[1].clips.find(row=>row.id==='first')!.start_ms).toBe(0);
 expect(previewTimelineCloseGaps(result.draft,'sound',true).shifts).toHaveLength(0);
});
it('rejects locked, missing and invalid original drafts without mutation',()=>{
 const draft=fixture();draft.timeline.tracks[1].locked=true;expect(()=>previewTimelineCloseGaps(draft,'sound',false)).toThrow();expect(()=>previewTimelineCloseGaps(draft,'absent',false)).toThrow();
 draft.timeline.duration_ms=1;expect(()=>previewTimelineCloseGaps(draft,'video',false)).toThrow();
});
const button=(name:string)=>screen.getByRole('button',{name,hidden:true});
const handler=(element:HTMLElement)=>(element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!].onClick;
function prepare(){fireEvent.change(screen.getByLabelText('整理空隙的轨道'),{target:{value:'sound'}});fireEvent.click(button('预览本轨空隙整理'));fireEvent.click(screen.getByLabelText('确认仅移动本轨片段，其他轨道与字幕不跟随'));}
it('needs separate preview/consent and consumes the local apply once',()=>{
 const props={draft:fixture(),scope:{},disabled:false,isCurrent:()=>true,getRevision:()=> '1',onApply:vi.fn(()=>true)};render(<StudioTimelineCloseGaps {...props}/>);prepare();expect(props.onApply).not.toHaveBeenCalled();
 const apply=handler(button('应用空隙整理到本地草稿'));act(()=>{apply();apply();});expect(props.onApply).toHaveBeenCalledTimes(1);
});
it('rejects retained apply after consent revocation or original revision change',()=>{
 let revision='1';const props={draft:fixture(),scope:{},disabled:false,isCurrent:()=>true,getRevision:()=>revision,onApply:vi.fn(()=>true)};render(<StudioTimelineCloseGaps {...props}/>);prepare();const old=handler(button('应用空隙整理到本地草稿'));
 fireEvent.click(screen.getByLabelText('确认仅移动本轨片段，其他轨道与字幕不跟随'));act(()=>old());expect(props.onApply).not.toHaveBeenCalled();
 fireEvent.click(screen.getByLabelText('确认仅移动本轨片段，其他轨道与字幕不跟随'));const second=handler(button('应用空隙整理到本地草稿'));revision='2';act(()=>second());expect(props.onApply).not.toHaveBeenCalled();
});
it('uses original controller change and undo without automatic save or render',async()=>{
 const row=checkedTimelineRow({...fixture(),id:'timeline',version:1,timeline_digest:'b'.repeat(64),created_at:'2026-10-17',updated_at:'2026-10-17'});
 const save=vi.fn(async(_id:string|undefined,body:StudioTimelineDraft)=>checkedTimelineRow({...row,...body,version:2,timeline_digest:'c'.repeat(64)}));
 const client={timelineList:vi.fn(async()=>({items:[row]})),timelineGet:vi.fn(async()=>row),timelineSave:save,timelineRender:vi.fn()};
 const props:StudioTimelineEditorProps={client:client as unknown as StudioProductionClient,assets:[],canMutate:true,busy:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work(),onDirtyChange:vi.fn(),onJob:vi.fn(),onUnavailable:vi.fn()};
 const hook=renderHook(()=>useStudioTimelineEditor(props));await waitFor(()=>expect(hook.result.current.rows).toHaveLength(1));await act(async()=>hook.result.current.checkServer('timeline'));act(()=>hook.result.current.setAdoptConfirmed(true));act(()=>hook.result.current.adoptCandidate(false));
 const before=cloneTimeline(hook.result.current.draft!);act(()=>{const next=previewTimelineCloseGaps(before,'sound',false);expect(hook.result.current.change(input=>{input.timeline=next.draft.timeline;})).toBe(true);});
 expect(save).not.toHaveBeenCalled();act(()=>hook.result.current.undo());expect(hook.result.current.draft).toEqual(before);act(()=>hook.result.current.redo());expect(hook.result.current.draft!.timeline.tracks[1].clips.find(row=>row.id==='late')!.start_ms).toBe(3500);expect(client.timelineRender).not.toHaveBeenCalled();
});

it('preserves exact cross-dissolve overlap while closing only a later uncovered gap',()=>{
 const draft=fixture(),clip=draft.timeline.tracks[0].clips[0];draft.timeline.tracks[0].clips=[
 {...clip,id:'a',start_ms:1000,out_ms:2000,transition_out:{kind:'CROSS_DISSOLVE',to_clip_id:'b',duration_ms:500}},
 {...clip,id:'b',start_ms:2500,out_ms:2000},
 {...clip,id:'c',start_ms:6000,out_ms:1000},
 ];
 const result=previewTimelineCloseGaps(draft,'video',false);expect(result.removedMs).toBe(1500);
 expect(result.draft.timeline.tracks[0].clips.map(row=>row.start_ms)).toEqual([1000,2500,4500]);expect(result.draft.timeline.tracks[0].clips[0].transition_out).toEqual(draft.timeline.tracks[0].clips[0].transition_out);
});
