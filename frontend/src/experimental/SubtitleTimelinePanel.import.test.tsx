// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { SubtitleTimelinePanel } from './SubtitleTimelinePanel';
import { experimentalClient } from './api';
import { readCaptionImport } from './voiceSubtitleClient';

const cue={id:'old',start_tick:0,end_tick:1000,text:'原字幕',segment_id:null,overlap_reason:''};
const track={id:'track',version:1,title:'Test captions',asset_id:'audio',asset_snapshot:{version:1,digest:'media-sha'},timebase:{numerator:1000,denominator:1},media:{duration_seconds:{numerator:5,denominator:1},waveform:{status:'UNAVAILABLE'}},cues:[cue],speakers:{},warnings:[],stale:false};
const imported={...cue,id:'import-sha-1',text:'你好🌙',start_tick:1000,end_tick:2000};
const response=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
const client=(id='novel',branch='main')=>experimentalClient(id,{sessionToken:'trusted',scope:{branchId:branch} as any});
const deferred=<T,>()=>{let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r;});return {promise,resolve};};
const file=(name='captions.srt',content='\ufeff1\r\n00:00:01,000 --> 00:00:02,000\r\n你好🌙\r\n')=>{
 const bytes=new TextEncoder().encode(content);const value=new File([bytes],name);Object.defineProperty(value,'arrayBuffer',{value:vi.fn(async()=>bytes.buffer),configurable:true});return value;
};
const selected=()=>fireEvent.change(screen.getByLabelText('字幕导入文件'),{target:{files:[file()]}});
const previewButton=()=>screen.getByRole('button',{name:'读取字幕导入预览'});
const acceptButton=()=>screen.getByRole('button',{name:'确认替换全部本地字幕（尚未保存）'});
let current=structuredClone(track);
let previewHandler:(body:any)=>Promise<Response>;
let fetchMock:ReturnType<typeof vi.fn>;
const previewResponse=async(body:any)=>{
 const bytes=Uint8Array.from(atob(body.content_base64),(c)=>c.charCodeAt(0));const hash=Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');
 return response({record_id:track.id,expected_version:body.expected_version,asset_id:track.asset_id,asset_snapshot:track.asset_snapshot,timebase:track.timebase,format:body.format,byte_length:bytes.length,content_sha256:hash,cues:[imported],warnings:[]});
};
beforeEach(()=>{
 current=structuredClone(track);vi.stubGlobal('crypto',webcrypto);previewHandler=previewResponse;
 fetchMock=vi.fn(async(url:string,init?:RequestInit)=>{
  if(url.endsWith('/import-preview'))return previewHandler(JSON.parse(String(init?.body)));
  if(init?.method==='PUT'){const body=JSON.parse(String(init.body));current={...current,version:current.version+1,cues:body.cues};return response(current);}
  return response(url.endsWith('/catalog')?{assets:[],plans:[]}:{items:[current]});
 });vi.stubGlobal('fetch',fetchMock);
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
const mount=async()=>{const owner=client();const view=render(<SubtitleTimelinePanel client={owner}/>);await screen.findByLabelText('字幕 1 文本');return {view,owner};};
const preview=async()=>{selected();fireEvent.click(previewButton());await screen.findByRole('region',{name:'字幕导入转换预览'});};

it('preserves exact UTF-8 CJK/BOM/CRLF bytes, previews without mutation, then explicitly replaces dirty local cues and saves through original API',async()=>{
 await mount();fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'Keep local draft'}});await preview();
 expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe('Keep local draft');
 expect(screen.getByText(/包括尚未保存的修改/)).toBeTruthy();
 const request=fetchMock.mock.calls.find(([url])=>url.endsWith('/import-preview'))!;
 const body=JSON.parse(String(request[1]?.body));expect(body.expected_version).toBe(1);expect(body.format).toBe('srt');
 expect(new TextDecoder('utf-8',{ignoreBOM:true}).decode(Uint8Array.from(atob(body.content_base64),(c)=>c.charCodeAt(0)))).toBe('\ufeff1\r\n00:00:01,000 --> 00:00:02,000\r\n你好🌙\r\n');
 expect(fetchMock.mock.calls.filter(([,init])=>init?.method==='PUT')).toHaveLength(0);
 fireEvent.click(acceptButton());expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe(imported.text);
 expect(screen.getByText('未保存：本地字幕已修改。')).toBeTruthy();expect(fetchMock.mock.calls.filter(([,init])=>init?.method==='PUT')).toHaveLength(0);
 fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await waitFor(()=>expect(fetchMock.mock.calls.filter(([,init])=>init?.method==='PUT')).toHaveLength(1));
 const saved=JSON.parse(String(fetchMock.mock.calls.find(([,init])=>init?.method==='PUT')![1]?.body));expect(saved).toEqual({expected_version:1,cues:[imported]});
});
it('invalidates accepted-preview handlers after a changed draft and after returning to identical text',async()=>{
 await mount();await preview();const old=acceptButton();
 fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'new'}});fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:cue.text}});
 expect(screen.queryByRole('region',{name:'字幕导入转换预览'})).toBeNull();fireEvent.click(old);
 expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe(cue.text);expect(screen.getByText(/旧导入预览已失效/)).toBeTruthy();
});
it('fences duplicate preview submits and discards an async response after local editing',async()=>{
 const gate=deferred<Response>();previewHandler=()=>gate.promise;await mount();selected();const button=previewButton();fireEvent.click(button);fireEvent.click(button);
 await waitFor(()=>expect(fetchMock.mock.calls.filter(([url])=>url.endsWith('/import-preview'))).toHaveLength(1));
 fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'keep edited'}});
 const body=JSON.parse(String(fetchMock.mock.calls.find(([url])=>url.endsWith('/import-preview'))![1]?.body));await act(async()=>gate.resolve(await previewResponse(body)));
 expect(screen.queryByRole('region',{name:'字幕导入转换预览'})).toBeNull();expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe('keep edited');
});
it('discards a delayed file read after selection changes without posting the old bytes',async()=>{
 await mount();const gate=deferred<ArrayBuffer>();const first=file();Object.defineProperty(first,'arrayBuffer',{value:()=>gate.promise,configurable:true});
 fireEvent.change(screen.getByLabelText('字幕导入文件'),{target:{files:[first]}});fireEvent.click(previewButton());selected();
 await act(async()=>gate.resolve(new TextEncoder().encode('old').buffer));expect(fetchMock.mock.calls.some(([url])=>url.endsWith('/import-preview'))).toBe(false);
});
it.each(['version','media','stale','refresh error'] as const)('invalidates preview on %s refresh while preserving dirty content',async(kind)=>{
 await mount();fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'keep'}});await preview();
 if(kind==='version')current={...current,version:2};if(kind==='media')current={...current,asset_snapshot:{version:2,digest:'changed'}};if(kind==='stale')current={...current,stale:true};
 if(kind==='refresh error')fetchMock.mockImplementation(async()=>response({code:'UNAVAILABLE'},503));
 fireEvent.click(screen.getByRole('button',{name:'刷新字幕来源与记录'}));await waitFor(()=>expect(screen.queryByRole('region',{name:'字幕导入转换预览'})).toBeNull());
 if(kind!=='stale')expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe('keep');
});
it('fences pending previews and retained handlers on client/scope replacement and unmount',async()=>{
 const gate=deferred<Response>();previewHandler=()=>gate.promise;const {view}=await mount();selected();const old=previewButton();fireEvent.click(old);
 await waitFor(()=>expect(fetchMock.mock.calls.some(([url])=>url.endsWith('/import-preview'))).toBe(true));
 const body=JSON.parse(String(fetchMock.mock.calls.find(([url])=>url.endsWith('/import-preview'))![1]?.body));view.rerender(<SubtitleTimelinePanel client={client('other','other')}/>);await screen.findByLabelText('字幕 1 文本');view.unmount();fireEvent.click(old);
 await act(async()=>gate.resolve(await previewResponse(body)));expect(fetchMock.mock.calls.filter(([url])=>url.endsWith('/import-preview'))).toHaveLength(1);
});
it.each([403,409,422,503])('preserves draft and never retries preview HTTP %s',async(status)=>{
 previewHandler=async()=>response({code:'CAPTION_IMPORT_FAILED'},status);await mount();fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'keep'}});selected();fireEvent.click(previewButton());await screen.findByText(/CAPTION_IMPORT_FAILED/);
 expect(screen.queryByRole('region',{name:'字幕导入转换预览'})).toBeNull();expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe('keep');expect(fetchMock.mock.calls.filter(([url])=>url.endsWith('/import-preview'))).toHaveLength(1);
});
it('rejects mismatched preview hashes without changing local cues',async()=>{
 previewHandler=async body=>{const value=await (await previewResponse(body)).json();return response({...value,content_sha256:'other'});};await mount();selected();fireEvent.click(previewButton());await screen.findByText(/导入预览与当前文件或媒体绑定不匹配/);expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe(cue.text);
});
it('handles VTT and rejects oversized, empty, unsupported and malformed UTF-8 before requesting preview',async()=>{
 expect((await readCaptionImport(file('captions.VTT','WEBVTT\r\n\r\n00:00:01.000 --> 00:00:02.000\r\n你好'))).format).toBe('vtt');
 await expect(readCaptionImport(file('large.srt','x'.repeat(192001)))).rejects.toThrow('192000');
 await expect(readCaptionImport(file('empty.srt',''))).rejects.toThrow('192000');await expect(readCaptionImport(file('bad.txt'))).rejects.toThrow('.srt');
 const bad=new File([new Uint8Array([255])],'bad.srt');Object.defineProperty(bad,'arrayBuffer',{value:async()=>new Uint8Array([255]).buffer});await expect(readCaptionImport(bad)).rejects.toThrow('UTF-8');
 expect(fetchMock).not.toHaveBeenCalled();
});
it('does not quantize exact rational backend ticks in the local replacement',async()=>{
 current={...current,timebase:{numerator:24000,denominator:1001}};
 previewHandler=async body=>{const value=await (await previewResponse(body)).json();return response({...value,timebase:current.timebase,cues:[{...imported,start_tick:24,end_tick:48}]});};
 await mount();await preview();fireEvent.click(acceptButton());expect((screen.getByLabelText('字幕 1 开始 tick') as HTMLInputElement).value).toBe('24');expect((screen.getByLabelText('字幕 1 结束 tick') as HTMLInputElement).value).toBe('48');
});
it('retained acceptance callbacks cannot replace cues after selection or draft changes',async()=>{
 await mount();await preview();const button=acceptButton();const key=Object.keys(button).find(k=>k.startsWith('__reactProps$'))!;
 const retained=(button as any)[key].onClick;selected();act(()=>retained());expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe(cue.text);
 fireEvent.click(previewButton());await screen.findByRole('region',{name:'字幕导入转换预览'});const next=acceptButton();const retainedNext=(next as any)[Object.keys(next).find(k=>k.startsWith('__reactProps$'))!].onClick;
 fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'new draft'}});act(()=>retainedNext());expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe('new draft');
});
it('keeps an UNKNOWN save outcome unresolved and does not retry or auto-save imported cues',async()=>{
 await mount();await preview();fireEvent.click(acceptButton());const original=fetchMock.getMockImplementation()!;
 fetchMock.mockImplementation(async(url,init)=>init?.method==='PUT'?Promise.reject(new Error('UNKNOWN save outcome')):original(url,init));
 fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await screen.findByText('读取或操作失败，请重试。');
 expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe(imported.text);expect(fetchMock.mock.calls.filter(([,init])=>init?.method==='PUT')).toHaveLength(1);expect(screen.getByText('未保存：本地字幕已修改。')).toBeTruthy();
});
const clickHandler=(button:HTMLElement)=>(button as any)[Object.keys(button).find(k=>k.startsWith('__reactProps$'))!].onClick as ()=>void;
it('invalidates preview on split inputs and warns before explicitly replacing unsaved split input',async()=>{
 await mount();await preview();const retained=clickHandler(acceptButton());fireEvent.change(screen.getByLabelText('字幕 1 拆分左文'),{target:{value:'unsaved split'}});act(()=>retained());expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe(cue.text);
 fireEvent.click(previewButton());await screen.findByRole('region',{name:'字幕导入转换预览'});expect(screen.getByText(/包括尚未保存的修改及拆分输入/)).toBeTruthy();fireEvent.click(acceptButton());expect((screen.getByLabelText('字幕 1 拆分左文') as HTMLTextAreaElement).value).toBe('');
});
it('admits a fresh preview after draft retirement before an obsolete hung response settles',async()=>{
 const gate=deferred<Response>();let count=0;previewHandler=body=>++count===1?gate.promise:previewResponse(body);await mount();selected();fireEvent.click(previewButton());await waitFor(()=>expect(count).toBe(1));
 fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'changed'}});fireEvent.click(previewButton());await screen.findByRole('region',{name:'字幕导入转换预览'});expect(count).toBe(2);
 const body=JSON.parse(String(fetchMock.mock.calls.find(([url])=>url.endsWith('/import-preview'))![1]?.body));await act(async()=>gate.resolve(await previewResponse(body)));expect(screen.getByRole('region',{name:'字幕导入转换预览'})).toBeTruthy();
});
it.each(['refresh','save','split','merge'] as const)('synchronously fences retained acceptance and preview callbacks at %s admission before repaint',async(kind)=>{
 if(kind==='merge')current={...current,cues:[cue,{...cue,id:'second',start_tick:1000,end_tick:2000}]};
 await mount();if(kind==='save')fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'dirty'}});
 if(kind==='split'){fireEvent.change(screen.getByLabelText('字幕 1 拆分左文'),{target:{value:'left'}});fireEvent.change(screen.getByLabelText('字幕 1 拆分右文'),{target:{value:'right'}});fireEvent.change(screen.getByLabelText('字幕 1 拆分 tick'),{target:{value:'500'}});}
 await preview();const accept=clickHandler(acceptButton()),start=clickHandler(previewButton());const target=kind==='refresh'?'刷新字幕来源与记录':kind==='save'?'保存字幕版本':kind==='split'?'拆分字幕 1':'合并下一条字幕';const operation=clickHandler(screen.getAllByRole('button',{name:target})[0]);
 const gate=deferred<Response>();fetchMock.mockImplementation(()=>gate.promise);act(()=>{operation();accept();start();});
 expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe(kind==='save'?'dirty':cue.text);expect(fetchMock.mock.calls.filter(([url])=>url.endsWith('/import-preview'))).toHaveLength(1);
});
it.each([
 {record_id:'wrong'},{expected_version:99},{asset_id:'wrong'},{asset_snapshot:{version:99,digest:'media-sha'}},{asset_snapshot:{version:1,digest:'wrong'}},{timebase:{numerator:24,denominator:1}},{format:'vtt'},{byte_length:0},
 {cues:[{...imported,id:''}]},{cues:[{...imported,text:''}]},{cues:[imported,imported]},{cues:[{...imported,text:'x'.repeat(10001)}]},
])('rejects mismatched or invalid preview DTO %#',async(patch)=>{
 previewHandler=async body=>response({...await (await previewResponse(body)).json(),...patch});await mount();selected();fireEvent.click(previewButton());await screen.findByText(/导入预览与当前文件或媒体绑定不匹配/);expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe(cue.text);
});
it('drops extra response cue fields before invoking the original save owner',async()=>{
 previewHandler=async body=>response({...await (await previewResponse(body)).json(),cues:[{...imported,unexpected:'not a Cue field'}]});await mount();await preview();fireEvent.click(acceptButton());fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));
 await waitFor(()=>expect(fetchMock.mock.calls.some(([,init])=>init?.method==='PUT')).toBe(true));expect(JSON.parse(String(fetchMock.mock.calls.find(([,init])=>init?.method==='PUT')![1]?.body)).cues).toEqual([imported]);
});
it('retained acceptance and start handlers stay inert through owner ABA and unmount',async()=>{
 const {view,owner}=await mount();await preview();const accept=clickHandler(acceptButton()),start=clickHandler(previewButton());view.rerender(<SubtitleTimelinePanel client={client('other')}/>);await screen.findByLabelText('字幕 1 文本');view.rerender(<SubtitleTimelinePanel client={owner}/>);await screen.findByLabelText('字幕 1 文本');act(()=>{accept();start();});expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe(cue.text);view.unmount();act(()=>{accept();start();});expect(fetchMock.mock.calls.filter(([url])=>url.endsWith('/import-preview'))).toHaveLength(1);
});
