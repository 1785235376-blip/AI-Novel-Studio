// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { StoryboardVideoTimeline } from './StoryboardVideoTimeline';
import { StudioProductionLeaveContext, type StudioProductionLeaveRisk } from './studioProductionLeaveRisk';
import type { StoryboardProductionProps } from './useStoryboardProductionController';
import type { StoryboardReceipt } from './studioStoryboardContract';
import type { CreativeClient } from './client';
import type { VideoTimelinePreview, VideoTimelineCreation, VideoTimelineCreate } from './storyboardVideoTimelineClient';
import fixture from './storyboardVideoTimeline.testFixture.json';

afterEach(cleanup);
const deferred = <T,>() => { let resolve!: (value:T)=>void; const promise=new Promise<T>(yes=>{resolve=yes;});return {promise,resolve}; };
const shown=fixture.shown as VideoTimelinePreview;
const created={ timeline:fixture.created.timeline,storyboard_origin:fixture.created.storyboard_origin,request_id:fixture.request.request_id,replayed:false } as VideoTimelineCreation;
function setup() {
  const client={storyboardVideoTimelinePreview:vi.fn().mockResolvedValue(shown),storyboardVideoTimelineCreate:vi.fn().mockResolvedValue(created),storyboardVideoTimelineCreation:vi.fn().mockResolvedValue({...created,replayed:true})};
  const receipt=structuredClone(fixture.receipt) as StoryboardReceipt;
  const owner={document:{id:receipt.document_snapshot.id,version:receipt.document_snapshot.version,title:fixture.body.title},client:client as unknown as CreativeClient,active:true,editable:true,busy:false,
    isBusy:()=>false,isCurrent:()=>true,perform:async <T,>(fn:()=>Promise<T>)=>fn(),onDenied:vi.fn()} as unknown as StoryboardProductionProps;
  const props={owner,receipt,blocked:false,onDirty:vi.fn()};return {client,props};
}
const button=(name:string)=>screen.getByRole('button',{name});
function handler(element:HTMLElement,event='onClick') { const key=Object.keys(element).find(key=>key.startsWith('__reactProps$'))!;return (element as unknown as Record<string,Record<string,(event?:unknown)=>void>>)[key][event]; }
function choose() {fireEvent.click(screen.getByLabelText('选择正式视频 SHOT 2 · shot-2'));fireEvent.click(screen.getByLabelText('选择正式视频 SHOT 1 · shot-1'));}
async function preview(){fireEvent.click(button('解码并预览视频底稿'));await act(async()=>{});}
const grant=()=>fireEvent.click(screen.getByLabelText('已核对顺序、裁切及来源，确认只创建原 Timeline'));

it('selects/order/trims explicitly, previews without save, confirms once, and reopens original receipt',async()=>{
  const {client,props}=setup();render(<StoryboardVideoTimeline {...props}/>);expect(client.storyboardVideoTimelinePreview).not.toHaveBeenCalled();
  choose();fireEvent.change(screen.getByLabelText('入点毫秒 shot-2'),{target:{value:'100'}});fireEvent.change(screen.getByLabelText('出点毫秒 shot-2'),{target:{value:'400'}});await preview();
  expect(client.storyboardVideoTimelinePreview.mock.calls[0][1].clips).toEqual(fixture.body.clips);expect(client.storyboardVideoTimelineCreate).not.toHaveBeenCalled();
  expect(screen.getByLabelText('视频底稿顺序裁切与来源预览').textContent).toContain('64×64');
  expect(button('确认保存视频剪辑底稿').hasAttribute('disabled')).toBe(true);grant();const save=handler(button('确认保存视频剪辑底稿'));
  await act(async()=>{save();save();});expect(client.storyboardVideoTimelineCreate).toHaveBeenCalledTimes(1);
  expect(props.onDirty).toHaveBeenLastCalledWith(false);fireEvent.click(button('重新读取这份原 Timeline'));await act(async()=>{});
  expect(client.storyboardVideoTimelineCreation).toHaveBeenCalledTimes(1);expect(client.storyboardVideoTimelineCreate).toHaveBeenCalledTimes(1);
});

it('retires saved consent, old preview and reorder callbacks when the form changes and changes back',async()=>{
  const {client,props}=setup();render(<StoryboardVideoTimeline {...props}/>);choose();await preview();grant();
  const save=handler(button('确认保存视频剪辑底稿')),inspect=handler(button('解码并预览视频底稿')),move=handler(button('上移 shot-1'));
  fireEvent.click(screen.getByLabelText('选择正式视频 SHOT 2 · shot-2'));fireEvent.click(screen.getByLabelText('选择正式视频 SHOT 2 · shot-2'));
  await act(async()=>{save();inspect();move();});expect(client.storyboardVideoTimelineCreate).not.toHaveBeenCalled();expect(client.storyboardVideoTimelinePreview).toHaveBeenCalledTimes(1);
  expect(screen.getByText('顺序 1 · shot-1')).toBeTruthy();await preview();expect(button('确认保存视频剪辑底稿').hasAttribute('disabled')).toBe(true);
});

it('retires an unchecked then rechecked consent callback even on the same preview',async()=>{
  const {client,props}=setup();render(<StoryboardVideoTimeline {...props}/>);choose();await preview();grant();const save=handler(button('确认保存视频剪辑底稿'));grant();grant();
  await act(async()=>{save();});expect(client.storyboardVideoTimelineCreate).not.toHaveBeenCalled();
});

it.each(['permission','client','source','active','current','busy'])('rejects retained Save across %s ABA',async kind=>{
  const {client,props}=setup(),view=render(<StoryboardVideoTimeline {...props}/>);choose();await preview();grant();const save=handler(button('确认保存视频剪辑底稿'));
  const owner={...props.owner};let receipt=props.receipt,blocked=false;
  if(kind==='permission')owner.editable=false;if(kind==='client')owner.client={...owner.client};if(kind==='source')receipt={...receipt,content_digest:'0'.repeat(64)};
  if(kind==='active')owner.active=false;if(kind==='current')owner.isCurrent=()=>false;if(kind==='busy')blocked=true;
  view.rerender(<StoryboardVideoTimeline {...props} owner={owner} receipt={receipt} blocked={blocked}/>);view.rerender(<StoryboardVideoTimeline {...props}/>);
  await act(async()=>{save();});expect(client.storyboardVideoTimelineCreate).not.toHaveBeenCalled();expect(screen.queryByLabelText('视频底稿顺序裁切与来源预览')).toBeNull();
});

it('discards late previews after source ABA and does not mutate a dirty owner',async()=>{
  const {client,props}=setup(),pending=deferred<VideoTimelinePreview>();client.storyboardVideoTimelinePreview.mockReturnValueOnce(pending.promise);const view=render(<StoryboardVideoTimeline {...props}/>);choose();
  fireEvent.click(button('解码并预览视频底稿'));view.rerender(<StoryboardVideoTimeline {...props} owner={{...props.owner,document:{...props.owner.document,version:999}}}/>);view.rerender(<StoryboardVideoTimeline {...props}/>);
  await act(async()=>pending.resolve(shown));expect(screen.queryByLabelText('视频底稿顺序裁切与来源预览')).toBeNull();expect(client.storyboardVideoTimelineCreate).not.toHaveBeenCalled();
  view.rerender(<StoryboardVideoTimeline {...props} blocked/>);fireEvent.click(screen.getByLabelText('选择正式视频 SHOT 1 · shot-1'));expect((screen.getByLabelText('选择正式视频 SHOT 1 · shot-1') as HTMLInputElement).checked).toBe(false);
});

it('preserves UNKNOWN request for explicit read or same-key retry and leave capture',async()=>{
  const {client,props}=setup();client.storyboardVideoTimelineCreate.mockRejectedValueOnce(new Error('lost response'));client.storyboardVideoTimelineCreation.mockRejectedValueOnce(new ApiError({status:404,message:'not yet',code:'NOT_FOUND'}));
  let read=()=>({unknown:false,requests:[]} as StudioProductionLeaveRisk);const capture=vi.fn();
  render(<StudioProductionLeaveContext.Provider value={{register:fn=>{read=fn;return()=>{};},capture}}><StoryboardVideoTimeline {...props}/></StudioProductionLeaveContext.Provider>);
  choose();await preview();grant();fireEvent.click(button('确认保存视频剪辑底稿'));await act(async()=>{});
  const body=client.storyboardVideoTimelineCreate.mock.calls[0][1] as VideoTimelineCreate;expect(read()).toEqual({unknown:true,requests:[{requestId:body.request_id,owner:'timeline',operationId:'storyboard.video.timeline.create'}]});
  fireEvent.click(button('读取原请求创建回执'));await act(async()=>{});expect(client.storyboardVideoTimelineCreate).toHaveBeenCalledTimes(1);
  fireEvent.click(button('用原请求键明确重试创建'));await act(async()=>{});expect(client.storyboardVideoTimelineCreate).toHaveBeenCalledTimes(2);
  expect(client.storyboardVideoTimelineCreate.mock.calls[1][1]).toEqual(body);expect(read().unknown).toBe(false);
});

it('does not publish late create results after permission retirement and captures only the original request identity',async()=>{
  const {client,props}=setup(),pending=deferred<VideoTimelineCreation>();client.storyboardVideoTimelineCreate.mockReturnValueOnce(pending.promise);let read=()=>({unknown:false,requests:[]} as StudioProductionLeaveRisk),captured:StudioProductionLeaveRisk|undefined;
  const wrap=(editable:boolean)=><StudioProductionLeaveContext.Provider value={boundary}><StoryboardVideoTimeline {...props} owner={{...props.owner,editable}}/></StudioProductionLeaveContext.Provider>;
  const boundary={register:(fn:typeof read)=>{read=fn;return()=>{};},capture:()=>{captured=read();}};const view=render(wrap(true));choose();await preview();grant();fireEvent.click(button('确认保存视频剪辑底稿'));
  view.rerender(wrap(false));view.rerender(wrap(true));await act(async()=>pending.resolve(created));expect(screen.queryByLabelText('已保存的视频分镜底稿')).toBeNull();
  expect(captured?.requests[0].requestId).toBe(client.storyboardVideoTimelineCreate.mock.calls[0][1].request_id);expect(Object.keys(captured!.requests[0]).sort()).toEqual(['operationId','owner','requestId']);
});

it('keeps preview and Save across the original perform-owned busy envelope',async()=>{
  const {client,props}=setup();function Harness(){const [busy,setBusy]=useState(false);return <StoryboardVideoTimeline {...props} blocked={busy} owner={{...props.owner,busy,isBusy:()=>busy,perform:async <T,>(fn:()=>Promise<T>)=>{setBusy(true);try{return await fn();}finally{setBusy(false);}}}}/>;}
  render(<Harness/>);choose();await preview();grant();fireEvent.click(button('确认保存视频剪辑底稿'));await act(async()=>{});expect(client.storyboardVideoTimelineCreate).toHaveBeenCalledTimes(1);expect(screen.getByLabelText('已保存的视频分镜底稿')).toBeTruthy();
});


it('limits explicit selection to four and permits changing order before a fresh preview',async()=>{
  const {client,props}=setup();props.receipt.shots=Array.from({length:5},(_,index)=>({...props.receipt.shots[0],shot_id:`shot-${index+1}`,shot:{...props.receipt.shots[0].shot,number:index+1}}));render(<StoryboardVideoTimeline {...props}/>);
  for(let i=1;i<=4;i++)fireEvent.click(screen.getByLabelText(`选择正式视频 SHOT ${i} · shot-${i}`));
  expect(screen.getByLabelText('选择正式视频 SHOT 5 · shot-5').hasAttribute('disabled')).toBe(true);fireEvent.click(button('上移 shot-4'));await preview();
  expect(client.storyboardVideoTimelinePreview.mock.calls[0][1].clips.map((clip:{shot_id:string})=>clip.shot_id)).toEqual(['shot-1','shot-2','shot-4','shot-3']);expect(client.storyboardVideoTimelineCreate).not.toHaveBeenCalled();
});

it('requires a fresh preview and consent after a known conflict; permission denial calls the original owner',async()=>{
  const {client,props}=setup();client.storyboardVideoTimelineCreate.mockRejectedValueOnce(new ApiError({status:409,code:'STALE',message:'changed'}));render(<StoryboardVideoTimeline {...props}/>);choose();await preview();grant();fireEvent.click(button('确认保存视频剪辑底稿'));await act(async()=>{});
  expect(screen.queryByLabelText('视频底稿原请求恢复')).toBeNull();expect(screen.queryByLabelText('视频底稿顺序裁切与来源预览')).toBeNull();
  client.storyboardVideoTimelinePreview.mockRejectedValueOnce(new ApiError({status:403,code:'DENIED',message:'denied'}));await preview();expect(props.owner.onDenied).toHaveBeenCalledTimes(1);expect(client.storyboardVideoTimelineCreate).toHaveBeenCalledTimes(1);
});
