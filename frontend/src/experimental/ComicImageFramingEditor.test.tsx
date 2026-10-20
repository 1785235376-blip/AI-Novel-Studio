// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { Blob as NodeBlob } from 'node:buffer';
import { ComicImageFramingEditor } from './ComicImageFramingEditor';
import type { ComicAsset, ComicCatalog, ComicPanel } from './comicLayoutsClient';
const asset:ComicAsset={id:'art',version:2,filename:'art.png',approved:true,manual_review_available:false};
const panel:ComicPanel={id:'panel',shot_id:null,order:1,x:8,y:8,width:100,height:100,asset_id:'art',expected_asset_version:2,fit:'COVER',character_ids:[],bubbles:[]};
function png():Blob { const bytes=Buffer.alloc(33); Buffer.from([137,80,78,71,13,10,26,10]).copy(bytes); bytes.writeUInt32BE(13,8);bytes.write('IHDR',12);bytes.writeUInt32BE(800,16);bytes.writeUInt32BE(100,20);return new NodeBlob([bytes],{type:'image/png'}) as unknown as Blob; }
const api=()=>({catalog:vi.fn(async()=>({assets:[asset]}) as ComicCatalog),image:vi.fn(async()=>png())});
const readButton=()=>screen.getByRole('button',{name:'读取并核对取景图片'});
const surface=()=>screen.getByRole('button',{name:'拖动格内图片取景'});
const image=()=>screen.getByRole('img',{name:'当前格框图片取景示意'});
function decode(){const element=image();Object.defineProperties(element,{naturalWidth:{configurable:true,value:800},naturalHeight:{configurable:true,value:100}});fireEvent.load(element);}
function handlers(element:HTMLElement){return (element as unknown as Record<string,Record<string,(event:any)=>void>>)[Object.keys(element).find(key=>key.startsWith('__reactProps'))!];}
beforeEach(()=>{
  let count=0;Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=>`blob:framing-${++count}`)});Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()});
  vi.stubGlobal('PointerEvent',class extends MouseEvent{pointerId:number;constructor(type:string,init:PointerEventInit){super(type,init);this.pointerId=init.pointerId||1;}});
  vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockReturnValue({width:100,height:100} as DOMRect);
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
function mount(){const props={panel,asset,api:api(),disabled:false,getRevision:()=>1,isCurrent:()=>true,onApply:vi.fn()};return {props,view:render(<ComicImageFramingEditor {...props}/>)};}
async function ready(){fireEvent.click(readButton());await screen.findByRole('img',{name:'当前格框图片取景示意'});decode();}
it('loads only on request and projects drag until one release, preserving omitted inactive fields',async()=>{
  const f=mount();expect(f.props.api.image).not.toHaveBeenCalled();await ready();
  fireEvent.pointerDown(surface(),{button:0,pointerId:1,clientX:0,clientY:0});fireEvent.pointerMove(surface(),{pointerId:1,clientX:70,clientY:0});
  expect(f.props.onApply).not.toHaveBeenCalled();expect(screen.getByText('取景位置：水平 40% · 垂直 50%')).toBeTruthy();
  fireEvent.pointerUp(surface(),{pointerId:1,clientX:70,clientY:0});fireEvent.pointerUp(surface(),{pointerId:1,clientX:70,clientY:0});
  expect(f.props.onApply).toHaveBeenCalledTimes(1);expect(f.props.onApply).toHaveBeenCalledWith({cover_x_percent:40});expect(f.props.api.catalog).toHaveBeenCalledTimes(2);
});
it('keeps the source thumbnail for current keyboard edits without rereading and ignores IME/inactive axes',async()=>{
  const f=mount();await ready();fireEvent.keyDown(surface(),{key:'ArrowDown'});fireEvent.keyDown(surface(),{key:'ArrowRight',isComposing:true});expect(f.props.onApply).not.toHaveBeenCalled();
  fireEvent.keyDown(surface(),{key:'ArrowRight',shiftKey:true});expect(f.props.onApply).toHaveBeenCalledWith({cover_x_percent:40});
  f.view.rerender(<ComicImageFramingEditor {...f.props} panel={{...panel,cover_x_percent:40}}/>);
  fireEvent.keyDown(surface(),{key:'ArrowLeft'});expect(f.props.onApply).toHaveBeenLastCalledWith({cover_x_percent:41});expect(f.props.api.image).toHaveBeenCalledTimes(1);
});
it.each(['revision','panel','owner','disabled','unmount'])('retires an active drag on %s, including retained callbacks',async reason=>{
  let revision=1,current=true;const props={panel,asset,api:api(),disabled:false,getRevision:()=>revision,isCurrent:()=>current,onApply:vi.fn()};const view=render(<ComicImageFramingEditor {...props}/>);await ready();
  fireEvent.pointerDown(surface(),{button:0,pointerId:1,clientX:0,clientY:0});const retained=handlers(surface()).onPointerUp;
  if(reason==='revision')revision++;if(reason==='owner')current=false;
  if(reason==='panel')view.rerender(<ComicImageFramingEditor {...props} panel={{...panel,cover_x_percent:25}}/>);
  if(reason==='disabled')view.rerender(<ComicImageFramingEditor {...props} disabled/>);if(reason==='unmount')view.unmount();
  act(()=>retained({pointerId:1,clientX:70,clientY:0}));expect(props.onApply).not.toHaveBeenCalled();
});
it('does not adopt a late thumbnail after source authority changes',async()=>{
  const f=mount();let resolve!:(blob:Blob)=>void;f.props.api.image.mockReturnValueOnce(new Promise(done=>{resolve=done;}));fireEvent.click(readButton());await waitFor(()=>expect(f.props.api.image).toHaveBeenCalledTimes(1));
  f.view.rerender(<ComicImageFramingEditor {...f.props} disabled/>);await act(async()=>resolve(png()));expect(URL.createObjectURL).not.toHaveBeenCalled();expect(f.props.onApply).not.toHaveBeenCalled();
});
it('retires old image events and controls during a reread while admitting the fresh decoded image',async()=>{
  const f=mount();await ready();const oldImage=image(),oldLoad=handlers(oldImage).onLoad,oldKey=handlers(surface()).onKeyDown;
  let resolve!:(blob:Blob)=>void;f.props.api.image.mockReturnValueOnce(new Promise(done=>{resolve=done;}));fireEvent.click(readButton());await waitFor(()=>expect(f.props.api.image).toHaveBeenCalledTimes(2));
  act(()=>{oldLoad({currentTarget:oldImage});oldKey({key:'ArrowRight',nativeEvent:{},preventDefault:()=>{}});});expect(f.props.onApply).not.toHaveBeenCalled();
  await act(async()=>resolve(png()));await screen.findByRole('img',{name:'当前格框图片取景示意'});expect((surface() as HTMLButtonElement).disabled).toBe(true);
  decode();fireEvent.keyDown(surface(),{key:'ArrowRight'});expect(f.props.onApply).toHaveBeenCalledWith({cover_x_percent:49});expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:framing-1');
});
it('cancel closes the projected drag without editing and unmount revokes the thumbnail',async()=>{
  const f=mount();await ready();fireEvent.pointerDown(surface(),{button:0,pointerId:1,clientX:0,clientY:0});fireEvent.pointerMove(surface(),{pointerId:1,clientX:70,clientY:0});fireEvent.keyDown(surface(),{key:'Escape'});
  fireEvent.pointerUp(surface(),{pointerId:1,clientX:70,clientY:0});expect(f.props.onApply).not.toHaveBeenCalled();f.view.unmount();expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:framing-1');
});
