// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { SubtitleTimelinePanel } from './SubtitleTimelinePanel';
import { experimentalClient } from './api';

const cue={id:'current',start_tick:0,end_tick:1000,text:'当前字幕',segment_id:null,overlap_reason:''};
const old={...cue,id:'historical',text:'旧字幕'};
const track={id:'track',version:3,title:'History captions',asset_id:'audio',asset_snapshot:{version:1,digest:'media-sha'},plan_id:null,timebase:{numerator:1000,denominator:1},media:{duration_seconds:{numerator:5,denominator:1},waveform:{status:'UNAVAILABLE'}},cues:[cue],speakers:{},warnings:[],stale:false};
const history={record_id:'track',expected_version:3,items:[{version:2,updated_at:'2026-10-17T00:00:00Z',status:'DRAFT',timing_origin:'MANUAL',cue_count:1},{version:1,updated_at:'2026-10-16T00:00:00Z',status:'APPROVED',timing_origin:'MANUAL',cue_count:1}],has_more:false,next_before_version:null};
const previewValue=(version=2)=>({record_id:'track',expected_version:3,history_version:version,asset_id:track.asset_id,asset_snapshot:track.asset_snapshot,timebase:track.timebase,plan_id:null,source_binding_digest:'a'.repeat(64),cues:[old],warnings:[]});
const response=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
const client=(id='novel',branch='main',sessionToken='trusted')=>experimentalClient(id,{sessionToken,scope:{branchId:branch} as any});
const deferred=<T,>()=>{let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r;});return {promise,resolve};};
let current=structuredClone(track),fetchMock:ReturnType<typeof vi.fn>;
let historyHandler:(url:string)=>Promise<Response>,previewHandler:(body:any)=>Promise<Response>,saveHandler:(body:any)=>Promise<Response>;
beforeEach(()=>{
 current=structuredClone(track);vi.stubGlobal('crypto',webcrypto);
 historyHandler=async()=>response(history);previewHandler=async body=>response(previewValue(body.history_version));saveHandler=async body=>{current={...current,version:4,cues:body.cues};return response(current);};
 fetchMock=vi.fn(async(url:string,init?:RequestInit)=>{
  if(url.includes('/history?'))return historyHandler(url);
  if(url.endsWith('/history-preview'))return previewHandler(JSON.parse(String(init?.body)));
  if(init?.method==='PUT')return saveHandler(JSON.parse(String(init.body)));
  return response(url.endsWith('/catalog')?{assets:[],plans:[]}:{items:[current]});
 });vi.stubGlobal('fetch',fetchMock);
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
const mount=async()=>{const owner=client();const view=render(<SubtitleTimelinePanel client={owner}/>);await screen.findByLabelText('字幕 1 文本');return {view,owner};};
const load=async()=>{fireEvent.click(screen.getByRole('button',{name:'读取字幕历史'}));await screen.findByLabelText('字幕历史版本');};
const select=(version='2')=>fireEvent.change(screen.getByLabelText('字幕历史版本'),{target:{value:version}});
const read=()=>fireEvent.click(screen.getByRole('button',{name:'预览所选历史字幕'}));
const preview=async()=>{await load();select();read();await screen.findByRole('region',{name:'字幕历史只读预览'});};
const replace=()=>screen.getByRole('button',{name:'确认用历史替换本地字幕（尚未保存）'});
const input=()=>screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement;
const writes=()=>fetchMock.mock.calls.filter(([,init])=>init?.method==='PUT');
const handler=(button:HTMLElement)=>(button as any)[Object.keys(button).find(k=>k.startsWith('__reactProps$'))!].onClick as ()=>void;

it('reads bounded history, previews without mutation, explicitly replaces dirty cues and split fields, then saves edited restoration with original CAS and source pin',async()=>{
 await mount();fireEvent.change(input(),{target:{value:'local draft'}});fireEvent.change(screen.getByLabelText('字幕 1 拆分左文'),{target:{value:'split draft'}});await preview();
 expect(input().value).toBe('local draft');expect(writes()).toHaveLength(0);expect(screen.getByText(/包括尚未保存的修改及拆分输入/)).toBeTruthy();
 expect(fetchMock.mock.calls.find(([url])=>url.includes('/history?'))![0]).toContain('expected_version=3&limit=20');
 fireEvent.click(replace());expect(input().value).toBe(old.text);expect((screen.getByLabelText('字幕 1 拆分左文') as HTMLTextAreaElement).value).toBe('');expect(writes()).toHaveLength(0);
 fireEvent.change(input(),{target:{value:'historical with manual edit'}});expect(screen.getByText(/本地字幕来自历史 v2/)).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await waitFor(()=>expect(writes()).toHaveLength(1));
 expect(JSON.parse(String(writes()[0][1]?.body))).toEqual({expected_version:3,cues:[{...old,text:'historical with manual edit'}],restore_history_version:2});
 await waitFor(()=>expect(screen.queryByText(/本地字幕来自历史 v2/)).toBeNull());expect(screen.getByText(/字幕已保存/)).toBeTruthy();
});
it.each([403,409,422,503,'UNKNOWN'] as const)('preserves edited restoration and source pin on failed save %s without retry or false success',async(status)=>{
 saveHandler=async()=>{if(status==='UNKNOWN')throw new Error('UNKNOWN');return response({code:'HISTORY_SAVE_FAILED'},status);};
 await mount();await preview();fireEvent.click(replace());fireEvent.change(input(),{target:{value:'keep edited'}});fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));
 await screen.findByText(status==='UNKNOWN'?'读取或操作失败，请重试。':/HISTORY_SAVE_FAILED/);expect(input().value).toBe('keep edited');expect(screen.getByText(/本地字幕来自历史 v2/)).toBeTruthy();expect(writes()).toHaveLength(1);expect(screen.queryByText(/字幕已保存/)).toBeNull();
 expect((screen.getByRole('button',{name:'保存字幕版本'}) as HTMLButtonElement).disabled).toBe(false);
});
it.each([403,409,422,503])('handles history/preview HTTP %s without replacing drafts',async(status)=>{
 await mount();fireEvent.change(input(),{target:{value:'keep'}});historyHandler=async()=>response({code:'HISTORY_READ_FAILED'},status);fireEvent.click(screen.getByRole('button',{name:'读取字幕历史'}));await screen.findByText(/HISTORY_READ_FAILED/);expect(input().value).toBe('keep');
 historyHandler=async()=>response(history);await load();select();previewHandler=async()=>response({code:'HISTORY_PREVIEW_FAILED'},status);read();await screen.findByText(/HISTORY_PREVIEW_FAILED/);expect(input().value).toBe('keep');expect(writes()).toHaveLength(0);
});
it('supports genuine empty history and historical cue lists',async()=>{
 historyHandler=async()=>response({...history,items:[]});await mount();fireEvent.click(screen.getByRole('button',{name:'读取字幕历史'}));await screen.findByText('暂无旧字幕版本');
 historyHandler=async()=>response(history);previewHandler=async()=>response({...previewValue(),cues:[]});await preview();expect(screen.getByText(/此历史版本没有字幕行/)).toBeTruthy();fireEvent.click(replace());expect(screen.queryByLabelText('字幕 1 文本')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await waitFor(()=>expect(writes()).toHaveLength(1));expect(JSON.parse(String(writes()[0][1]?.body))).toEqual({expected_version:3,cues:[],restore_history_version:2});
});
it('treats equal historical cues as no-op without clearing split fields or an existing provenance pin',async()=>{
 await mount();await preview();fireEvent.click(replace());fireEvent.change(screen.getByLabelText('字幕 1 拆分左文'),{target:{value:'keep split'}});await preview();
 expect(screen.getByText(/历史字幕与本地字幕一致/)).toBeTruthy();expect(screen.queryByRole('button',{name:'确认用历史替换本地字幕（尚未保存）'})).toBeNull();expect((screen.getByLabelText('字幕 1 拆分左文') as HTMLTextAreaElement).value).toBe('keep split');expect(screen.getByText(/本地字幕来自历史 v2/)).toBeTruthy();expect(writes()).toHaveLength(0);
});
it('clears provenance only on explicit current replacement, then normal save omits the pin',async()=>{
 await mount();await preview();fireEvent.click(replace());fireEvent.click(screen.getByRole('button',{name:'载入当前字幕并替换本地输入'}));expect(screen.queryByText(/本地字幕来自历史/)).toBeNull();fireEvent.change(input(),{target:{value:'normal edit'}});fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await waitFor(()=>expect(writes()).toHaveLength(1));expect(JSON.parse(String(writes()[0][1]?.body))).not.toHaveProperty('restore_history_version');
});
it('strips historical approval and processing authority from copied cues and save',async()=>{
 previewHandler=async()=>response({...previewValue(),status:'APPROVED',processing_task_id:'privileged',cues:[{...old,approved:true,processing_task_id:'privileged'}]});await mount();await preview();fireEvent.click(replace());fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await waitFor(()=>expect(writes()).toHaveLength(1));expect(JSON.parse(String(writes()[0][1]?.body))).toEqual({expected_version:3,cues:[old],restore_history_version:2});
});
it.each(['selection','draft ABA','split'] as const)('invalidates retained history confirmation after %s',async(kind)=>{
 await mount();await preview();const retained=handler(replace());if(kind==='selection')select('1');else if(kind==='split')fireEvent.change(screen.getByLabelText('字幕 1 拆分右文'),{target:{value:'split'}});else{fireEvent.change(input(),{target:{value:'edit'}});fireEvent.change(input(),{target:{value:cue.text}});}act(()=>retained());expect(input().value).toBe(cue.text);expect(writes()).toHaveLength(0);expect(screen.queryByRole('region',{name:'字幕历史只读预览'})).toBeNull();
});
it.each(['refresh','save','split','merge'] as const)('synchronously retires confirmation at %s admission before repaint',async(kind)=>{
 if(kind==='merge')current={...current,cues:[cue,{...cue,id:'second',start_tick:1000,end_tick:2000}]};await mount();if(kind==='save')fireEvent.change(input(),{target:{value:'dirty'}});if(kind==='split'){fireEvent.change(screen.getByLabelText('字幕 1 拆分左文'),{target:{value:'left'}});fireEvent.change(screen.getByLabelText('字幕 1 拆分右文'),{target:{value:'right'}});fireEvent.change(screen.getByLabelText('字幕 1 拆分 tick'),{target:{value:'500'}});}await preview();const retained=handler(replace());const start=handler(screen.getByRole('button',{name:'预览所选历史字幕'}));const name=kind==='refresh'?'刷新字幕来源与记录':kind==='save'?'保存字幕版本':kind==='split'?'拆分字幕 1':'合并下一条字幕';const operation=handler(screen.getAllByRole('button',{name})[0]);const gate=deferred<Response>();fetchMock.mockImplementation(()=>gate.promise);act(()=>{operation();retained();start();});expect(input().value).toBe(kind==='save'?'dirty':cue.text);expect(fetchMock.mock.calls.filter(([url])=>url.endsWith('/history-preview'))).toHaveLength(1);
});
it.each(['head','source','stale','error'] as const)('invalidates history after %s refresh, retaining drafts',async(kind)=>{
 await mount();fireEvent.change(input(),{target:{value:'keep'}});await preview();const retained=handler(replace());if(kind==='head')current={...current,version:4};if(kind==='source')current={...current,asset_snapshot:{version:2,digest:'drift'}};if(kind==='stale')current={...current,stale:true};if(kind==='error')fetchMock.mockImplementation(async()=>response({code:'UNAVAILABLE'},503));fireEvent.click(screen.getByRole('button',{name:'刷新字幕来源与记录'}));act(()=>retained());await waitFor(()=>expect(screen.queryByRole('region',{name:'字幕历史只读预览'})).toBeNull());if(kind!=='stale')expect(input().value).toBe('keep');expect(writes()).toHaveLength(0);
});
it.each(['scope','actor','client','ABA','unmount'] as const)('fences retained callbacks and delayed preview after %s change',async(kind)=>{
 const {view,owner}=await mount();await preview();const accept=handler(replace()),start=handler(screen.getByRole('button',{name:'预览所选历史字幕'}));const gate=deferred<Response>();previewHandler=()=>gate.promise;read();
 if(kind==='unmount')view.unmount();else{view.rerender(<SubtitleTimelinePanel client={kind==='scope'?client('novel','other'):kind==='actor'?client('novel','main','other'):client('other')}/>);await screen.findByLabelText('字幕 1 文本');if(kind==='ABA'){view.rerender(<SubtitleTimelinePanel client={owner}/>);await screen.findByLabelText('字幕 1 文本');}}
 act(()=>{accept();start();});await act(async()=>gate.resolve(response(previewValue())));expect(screen.queryByRole('region',{name:'字幕历史只读预览'})).toBeNull();if(kind!=='unmount')expect(input().value).toBe(cue.text);expect(writes()).toHaveLength(0);
});
it('discards stale delayed list and preview; allows a fresh request before an old hung response settles',async()=>{
 const listGate=deferred<Response>();historyHandler=()=>listGate.promise;await mount();fireEvent.click(screen.getByRole('button',{name:'读取字幕历史'}));fireEvent.change(input(),{target:{value:'edited'}});historyHandler=async()=>response(history);await load();await act(async()=>listGate.resolve(response({...history,items:[]})));expect(screen.getByLabelText('字幕历史版本')).toBeTruthy();
 const gate=deferred<Response>();previewHandler=()=>gate.promise;select();read();select('1');previewHandler=async()=>response(previewValue(1));read();await screen.findByRole('region',{name:'字幕历史只读预览'});await act(async()=>gate.resolve(response(previewValue(2))));expect(screen.getByText(/历史 v1 ·/)).toBeTruthy();expect(input().value).toBe('edited');
});
it('paginates using a bounded exclusive cursor anchored to the same current head',async()=>{
 historyHandler=async url=>response(url.includes('before_version=2')?{...history,items:[history.items[1]]}:{...history,items:[history.items[0]],has_more:true,next_before_version:2});await mount();await load();fireEvent.click(screen.getByRole('button',{name:'读取更早字幕历史'}));await waitFor(()=>expect((screen.getByLabelText('字幕历史版本') as HTMLSelectElement).options.length).toBe(2));expect(fetchMock.mock.calls.some(([url])=>url.includes('expected_version=3&limit=20&before_version=2'))).toBe(true);
});
it.each([{record_id:'wrong'},{expected_version:9},{items:[{...history.items[0],version:3}]},{items:[history.items[0],history.items[0]]},{items:[history.items[1],history.items[0]]},{items:Array(21).fill(history.items[0])},{items:[{...history.items[0],cue_count:2001}]},{has_more:true,next_before_version:null},{next_before_version:2},{items:[null]}])('rejects malformed history metadata %#',async patch=>{
 historyHandler=async()=>response({...history,...patch});await mount();fireEvent.click(screen.getByRole('button',{name:'读取字幕历史'}));await screen.findByText(/历史响应与当前字幕或来源不匹配/);expect(screen.queryByLabelText('字幕历史版本')).toBeNull();expect(input().value).toBe(cue.text);
});
it.each([{record_id:'wrong'},{expected_version:9},{history_version:1},{asset_id:'other'},{asset_snapshot:{version:2,digest:'changed'}},{timebase:{numerator:24,denominator:1}},{plan_id:'other'},{source_binding_digest:'bad'},{cues:[null]},{cues:[old,old]},{cues:[{...old,text:''}]},{cues:[{...old,overlap_reason:'x'.repeat(501)}]},{cues:Array(2001).fill(old)},{warnings:[{cue_id:'missing',code:'LONG_LINE_HEURISTIC'}]},{warnings:[null]}])('rejects malformed or source-drifted preview %#',async patch=>{
 previewHandler=async()=>response({...previewValue(),...patch});await mount();await load();select();read();await screen.findByText(/历史响应与当前字幕或来源不匹配/);expect(screen.queryByRole('region',{name:'字幕历史只读预览'})).toBeNull();expect(input().value).toBe(cue.text);
});
it('keeps source pin when manual edit returns to current cues and offers explicit save or current replacement',async()=>{
 previewHandler=async()=>response({...previewValue(),cues:[{...cue,text:'historical text'}]});await mount();await preview();fireEvent.click(replace());fireEvent.change(input(),{target:{value:cue.text}});
 expect(screen.getByText(/本地字幕来自历史 v2/)).toBeTruthy();expect((screen.getByRole('button',{name:'保存字幕版本'}) as HTMLButtonElement).disabled).toBe(false);expect((screen.getByRole('button',{name:'合并下一条字幕'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('字幕 1 拆分左文'),{target:{value:'left'}});fireEvent.change(screen.getByLabelText('字幕 1 拆分右文'),{target:{value:'right'}});expect((screen.getByRole('button',{name:'拆分字幕 1'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await waitFor(()=>expect(writes()).toHaveLength(1));expect(JSON.parse(String(writes()[0][1]?.body))).toEqual({expected_version:3,cues:[cue],restore_history_version:2});
});
it('treats a historical snapshot identical to current cues as no-op without staging or writes',async()=>{
 previewHandler=async()=>response({...previewValue(),cues:[cue]});await mount();await preview();expect(screen.getByText(/历史字幕与本地字幕一致/)).toBeTruthy();expect(screen.queryByRole('button',{name:'确认用历史替换本地字幕（尚未保存）'})).toBeNull();expect(screen.queryByText(/本地字幕来自历史/)).toBeNull();expect(writes()).toHaveLength(0);
});
it('explicit imported replacement clears historical provenance while ordinary manual edits do not',async()=>{
 await mount();await preview();fireEvent.click(replace());const original=fetchMock.getMockImplementation()!;
 const bytes=new TextEncoder().encode('1\n00:00:00,000 --> 00:00:01,000\nImported\n');const file=new File([bytes],'captions.srt');Object.defineProperty(file,'arrayBuffer',{value:async()=>bytes.buffer});
 fetchMock.mockImplementation(async(url,init)=>{if(!url.endsWith('/import-preview'))return original(url,init);const body=JSON.parse(String(init?.body));const hash=Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');return response({record_id:'track',expected_version:3,asset_id:track.asset_id,asset_snapshot:track.asset_snapshot,timebase:track.timebase,format:body.format,byte_length:bytes.length,content_sha256:hash,cues:[{...cue,text:'Imported'}],warnings:[]});});
 fireEvent.change(screen.getByLabelText('字幕导入文件'),{target:{files:[file]}});fireEvent.click(screen.getByRole('button',{name:'读取字幕导入预览'}));await screen.findByRole('region',{name:'字幕导入转换预览'});fireEvent.click(screen.getByRole('button',{name:'确认替换全部本地字幕（尚未保存）'}));expect(screen.queryByText(/本地字幕来自历史/)).toBeNull();fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await waitFor(()=>expect(writes()).toHaveLength(1));expect(JSON.parse(String(writes()[0][1]?.body))).not.toHaveProperty('restore_history_version');
});
it.each(['list','preview','page'] as const)('retires retained confirmation and old read callbacks synchronously when starting a new %s request',async(kind)=>{
 if(kind==='page')historyHandler=async()=>response({...history,items:[history.items[0]],has_more:true,next_before_version:2});await mount();await preview();const accept=handler(replace()),oldRead=handler(screen.getByRole('button',{name:'预览所选历史字幕'}));const gate=deferred<Response>();historyHandler=()=>gate.promise;previewHandler=()=>gate.promise;const name=kind==='list'?'读取字幕历史':kind==='page'?'读取更早字幕历史':'预览所选历史字幕';const operation=handler(screen.getByRole('button',{name}));act(()=>{operation();accept();oldRead();});expect(input().value).toBe(cue.text);expect(writes()).toHaveLength(0);
});
it.each(['save','split','merge'] as const)('fences retained pre-restoration %s mutation callbacks so they cannot omit the source pin',async(kind)=>{
 if(kind==='merge')current={...current,cues:[cue,{...cue,id:'second',start_tick:1000,end_tick:2000}]};await mount();
 if(kind==='save')fireEvent.change(input(),{target:{value:'old draft'}});
 if(kind==='split'){fireEvent.change(screen.getByLabelText('字幕 1 拆分左文'),{target:{value:'left'}});fireEvent.change(screen.getByLabelText('字幕 1 拆分右文'),{target:{value:'right'}});fireEvent.change(screen.getByLabelText('字幕 1 拆分 tick'),{target:{value:'500'}});}
 const name=kind==='save'?'保存字幕版本':kind==='split'?'拆分字幕 1':'合并下一条字幕';const retained=handler(screen.getAllByRole('button',{name})[0]);await preview();const confirm=handler(replace());act(()=>{confirm();retained();});expect(input().value).toBe(old.text);expect(writes()).toHaveLength(0);expect(fetchMock.mock.calls.some(([url])=>url.includes('/split')||url.includes('/merge'))).toBe(false);
});
it('keeps current normal Save live through unrelated review rerenders and still writes original CAS',async()=>{
 await mount();fireEvent.change(input(),{target:{value:'normal edit'}});const save=handler(screen.getByRole('button',{name:'保存字幕版本'}));fireEvent.click(screen.getByRole('button',{name:'检查字幕交付兼容性'}));act(()=>save());await waitFor(()=>expect(writes()).toHaveLength(1));expect(JSON.parse(String(writes()[0][1]?.body))).toEqual({expected_version:3,cues:[{...cue,text:'normal edit'}]});await screen.findByText(/字幕已保存/);
});
