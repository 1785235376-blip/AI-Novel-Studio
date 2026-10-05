// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { VoiceDirectionPanel } from './VoiceDirectionPanel';
import { SubtitleTimelinePanel } from './SubtitleTimelinePanel';
import { experimentalClient } from './api';
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
const client=(nid='novel')=>experimentalClient(nid,{sessionToken:'trusted',scope:{branchId:'branch'} as any});
const plan={id:'plan',version:1,title:'Synthetic voice',status:'PENDING_REVIEW',needs_review_count:1,segments:[{id:'seg',version:1,kind:'DIALOGUE',text:'她说：你好',character_id:null,profile_id:'voice',attribution_status:'NEEDS_REVIEW'}]};
const track={id:'track',version:1,title:'Synthetic captions',status:'DRAFT',stale:false,asset_id:'audio',timebase:{numerator:1000,denominator:1},media:{duration_seconds:{numerator:2,denominator:1},waveform:{status:'UNAVAILABLE'}},cues:[{id:'cue',start_tick:0,end_tick:1000,text:'你好🌙',segment_id:null,overlap_reason:''}],speakers:{},warnings:[]};
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
it('captures actor/branch and reviewed text with literal pronunciation without unsolicited generation',async()=>{
 const fetch=vi.fn(async(url:string,init:RequestInit)=>{if(init.method==='PUT')return response({...plan,version:2});if(url.endsWith('/catalog'))return response({plans:[plan],profiles:[{id:'voice',display_name:'Synthetic'}],characters:[{id:'alice',name:'Alice'}],tts:{runtime:'NOT_RUN'}});return response({items:[]});});
 vi.stubGlobal('fetch',fetch);render(<VoiceDirectionPanel client={client()}/>);
 await screen.findByText('Synthetic voice · v1 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});
 expect((screen.getByLabelText('说话人') as HTMLSelectElement).value).toBe('');
 fireEvent.change(screen.getByLabelText('说话人'),{target:{value:'alice'}});fireEvent.change(screen.getByLabelText('此片段审核朗读文本'),{target:{value:'你好，重庆'}});
 fireEvent.change(screen.getByLabelText('片段发音规则（每行 原词=读音）'),{target:{value:'重庆=chongqing'}});
 fireEvent.click(screen.getByLabelText('已核对说话人归属'));fireEvent.click(screen.getByLabelText('已审核此片段朗读文本'));fireEvent.click(screen.getByLabelText('已确认此声音的使用授权'));
 fireEvent.click(screen.getByRole('button',{name:'保存声音方向'}));await waitFor(()=>expect(fetch.mock.calls.some(([,r])=>r.method==='PUT')).toBe(true));
 const [url,req]=fetch.mock.calls.find(([,r])=>r.method==='PUT')!;expect(url).toContain('/voice-direction/plans/plan/segments/seg');
 expect(req.headers).toMatchObject({'X-Session-Token':'trusted','X-Branch-Id':'branch'});
 expect(JSON.parse(String(req.body))).toMatchObject({expected_version:1,character_id:'alice',reviewed_text:'你好，重庆',text_reviewed:true,voice_authorized:true,pronunciation_rules:[{term:'重庆',pronunciation:'chongqing'}]});
 expect(fetch.mock.calls.some(([url])=>/execute|queue/.test(url))).toBe(false);
});
it('voice conflict preserves local draft and scope replacement clears it',async()=>{
 const fetch=vi.fn(async(url:string,init:RequestInit)=>init.method==='PUT'?response({detail:{code:'EXPERIMENTAL_VERSION_CONFLICT'}},409):response(url.endsWith('/catalog')?{plans:[plan],profiles:[],characters:[],tts:{}}:{items:[]}));vi.stubGlobal('fetch',fetch);
 const view=render(<VoiceDirectionPanel client={client()}/>);await screen.findByText('Synthetic voice · v1 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});
 fireEvent.change(screen.getByLabelText('此片段审核朗读文本'),{target:{value:'Retain local voice draft'}});fireEvent.click(screen.getByRole('button',{name:'保存声音方向'}));await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
 expect((screen.getByLabelText('此片段审核朗读文本') as HTMLTextAreaElement).value).toBe('Retain local voice draft');
 vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(()=>{})));view.rerender(<VoiceDirectionPanel client={client('other')}/>);expect(screen.queryByDisplayValue('Retain local voice draft')).toBeNull();
});
it('caption request preserves exact integer ticks, edits, and no fake waveform',async()=>{
 const fetch=vi.fn(async(url:string,init:RequestInit)=>init.method==='PUT'?response({...track,version:2,cues:JSON.parse(String(init.body)).cues}):response(url.endsWith('/catalog')?{assets:[],plans:[]}:{items:[track]}));vi.stubGlobal('fetch',fetch);
 render(<SubtitleTimelinePanel client={client()}/>);await screen.findByLabelText('字幕 1 文本');
 expect(screen.queryByRole('img',{name:'实际音频采样峰值波形'})).toBeNull();
 fireEvent.change(screen.getByLabelText('字幕 1 结束 tick'),{target:{value:'1500'}});fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'双语字幕\nHello 🌙'}});
 fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await waitFor(()=>expect(fetch.mock.calls.some(([,r])=>r.method==='PUT')).toBe(true));
 const [,req]=fetch.mock.calls.find(([,r])=>r.method==='PUT')!;expect(JSON.parse(String(req.body))).toEqual({expected_version:1,cues:[{...track.cues[0],end_tick:1500,text:'双语字幕\nHello 🌙'}]});
 expect(req.headers).toMatchObject({'X-Session-Token':'trusted','X-Branch-Id':'branch'});
});
it('subtitle permission errors retain inputs and changed version cannot silently rebase',async()=>{
 let version=1;const fetch=vi.fn(async(url:string,init:RequestInit)=>init.method==='PUT'?response({detail:{code:'FORBIDDEN'}},403):response(url.endsWith('/catalog')?{assets:[],plans:[]}:{items:[{...track,version}]}));vi.stubGlobal('fetch',fetch);
 render(<SubtitleTimelinePanel client={client()}/>);await screen.findByLabelText('字幕 1 文本');fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'Keep this caption'}});fireEvent.click(screen.getByRole('button',{name:'保存字幕版本'}));await screen.findByText(/FORBIDDEN/);
 expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe('Keep this caption');version=2;fireEvent.click(screen.getByRole('button',{name:'刷新字幕来源与记录'}));await screen.findByText(/字幕版本已变化/);
 expect((screen.getByLabelText('字幕 1 文本') as HTMLTextAreaElement).value).toBe('Keep this caption');expect((screen.getByRole('button',{name:'保存字幕版本'}) as HTMLButtonElement).disabled).toBe(true);
});
it('empty and failed catalog never auto-create captions or model tasks',async()=>{
 const fetch=vi.fn(async()=>response({detail:{code:'FORBIDDEN'}},403));vi.stubGlobal('fetch',fetch);render(<SubtitleTimelinePanel client={client()}/>);
 await screen.findAllByText(/FORBIDDEN/);expect((screen.getByRole('button',{name:'创建字幕草稿'}) as HTMLButtonElement).disabled).toBe(true);expect(fetch.mock.calls.length).toBe(2);
});
