// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { VoiceDirectionPanel } from './VoiceDirectionPanel';
import { VoicePlanReview, voiceAssignmentIssues } from './VoicePlanReview';
import type { AudioPlan, AudioSegment, VoiceCatalog } from './voiceSubtitleClient';
import type { ExperimentalClient } from './api';
const line:AudioSegment={id:'line',version:1,kind:'DIALOGUE',text:'你好 🌙',character_id:'alice',profile_id:'voice',profile_version:2,attribution_status:'REVIEWED',source_start:3,source_end:7,source_text_digest:'a'.repeat(64),direction:{reviewed_text:'你好 🌙',emotion:'neutral',speech_rate:1,pause_ms:280,text_reviewed:true,voice_authorized:true,pronunciation_rules:[]}};
const plan:AudioPlan={id:'plan',version:4,title:'Saved',status:'PENDING_REVIEW',needs_review_count:0,segments:[line],sources:{chapter:{version:9,digest:'source-digest'}},character_snapshots:{alice:'character-digest'}};
const catalog:VoiceCatalog={plans:[plan],profiles:[{id:'voice',version:2,display_name:'Voice',supports_emotion:false}],characters:[{id:'alice',name:'Alice'}],tts:{quality:'NOT_RUN'}};
function client(){return {get:vi.fn(async(path:string)=>path.endsWith('/catalog')?catalog:{items:[]}),put:vi.fn(async()=>({...plan,version:5})),post:vi.fn()} as unknown as ExperimentalClient;}
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('distinguishes exact configured assignments from missing refs, version changes and unsupported emotion',()=>{
 expect(voiceAssignmentIssues(plan,line,catalog)).toEqual([]);
 expect(voiceAssignmentIssues(plan,{...line,profile_version:1,direction:{...line.direction!,emotion:'sad'}},catalog)).toEqual(expect.arrayContaining([expect.stringMatching(/版本不一致/),expect.stringMatching(/支持声明/)]));
 expect(voiceAssignmentIssues(plan,{...line,character_id:'missing',profile_id:'missing'},catalog)).toEqual(expect.arrayContaining([expect.stringMatching(/说话人未分配/),expect.stringMatching(/Profile 未分配/)]));
 expect(voiceAssignmentIssues(plan,line,{...catalog,characters:[...catalog.characters,...catalog.characters],profiles:[...catalog.profiles,...catalog.profiles]})).toEqual(expect.arrayContaining([expect.stringMatching(/有歧义/)]));
});
it('flags same speaker divergent versions without interpreting intended emotion variation as a conflict',()=>{
 const other={...line,id:'second',profile_version:3,direction:{...line.direction!,emotion:'happy'}};
 expect(voiceAssignmentIssues({...plan,segments:[line,other]},line,catalog)).toContain('同一说话人在本计划使用不同声音或版本；请确认是否有意安排');
 expect(voiceAssignmentIssues({...plan,segments:[line,{...other,profile_version:2}]},line,catalog)).toEqual([]);
});
it('bounds saved review pages and disables ambiguous exact targets',()=>{
 const segments=Array.from({length:23},(_,i)=>({...line,id:`s${i}`}));segments[1].id='s0';const locate=vi.fn();
 render(<VoicePlanReview plan={{...plan,segments}} catalog={catalog} available onLocate={locate}/>);
 expect(screen.getAllByRole('button',{name:/定位声音片段/})).toHaveLength(20);
 expect(screen.getByRole('button',{name:'定位声音片段 1'}).hasAttribute('disabled')).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'下一页声音核对'}));expect(screen.getAllByRole('button',{name:/定位声音片段/})).toHaveLength(3);
 fireEvent.click(screen.getByRole('button',{name:'定位声音片段 23'}));expect(locate).toHaveBeenCalledWith(segments[22]);
});
it('opens saved evidence and focuses original editor without discarding dirty inputs or writing',async()=>{
 const api=client();render(<VoiceDirectionPanel client={api}/>);await screen.findByText('Saved · v4 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});
 fireEvent.change(screen.getByLabelText('此片段审核朗读文本'),{target:{value:'Unsaved 中文'}});fireEvent.click(screen.getByRole('button',{name:'核对已保存声音分配'}));
 expect(screen.getByText(/不包含下方未保存输入/)).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'定位声音片段 1'}));
 expect(document.activeElement).toBe(screen.getByRole('article',{name:'声音片段 1 原编辑器'}));expect((screen.getByLabelText('此片段审核朗读文本') as HTMLTextAreaElement).value).toBe('Unsaved 中文');
 expect(api.put).not.toHaveBeenCalled();expect(api.post).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'保存声音方向'}));await waitFor(()=>expect(api.put).toHaveBeenCalled());expect(vi.mocked(api.put).mock.calls[0]).toEqual(['/voice-direction/plans/plan/segments/line',expect.objectContaining({expected_version:4,reviewed_text:'Unsaved 中文',text_reviewed:false})]);
});
it('does not steal composition focus and hides saved review during failed refresh',async()=>{
 const api=client();render(<VoiceDirectionPanel client={api}/>);await screen.findByText('Saved · v4 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});fireEvent.click(screen.getByRole('button',{name:'核对已保存声音分配'}));
 const input=screen.getByLabelText('此片段审核朗读文本');input.focus();fireEvent.compositionStart(input);fireEvent.click(screen.getByRole('button',{name:'定位声音片段 1'}));expect(document.activeElement).toBe(input);fireEvent.compositionEnd(input);
 vi.mocked(api.get).mockRejectedValue(new Error('UNAVAILABLE'));fireEvent.click(screen.getByRole('button',{name:'刷新声音来源与任务'}));await screen.findAllByText(/读取或操作失败/);expect(screen.queryByRole('button',{name:'定位声音片段 1'})).toBeNull();expect((input as HTMLTextAreaElement).value).toBe(line.text);
});
it('keeps missing saved references visible in original selects instead of pretending an empty assignment',async()=>{
 const api=client();vi.mocked(api.get).mockImplementation(async(path:string)=>(path.endsWith('/catalog')?{...catalog,profiles:[],characters:[]}:{items:[]}) as never);
 render(<VoiceDirectionPanel client={api}/>);await screen.findByText('Saved · v4 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});
 expect(screen.getByRole('option',{name:'缺失 Profile：voice'})).toBeTruthy();expect(screen.getByRole('option',{name:'缺失说话人：alice'})).toBeTruthy();expect((screen.getByLabelText('使用的声音 Profile') as HTMLSelectElement).value).toBe('voice');
});

it('keeps saved-version evidence separate after refresh while dirty original inputs cannot silently rebase',async()=>{
 const api=client();render(<VoiceDirectionPanel client={api}/>);await screen.findByText('Saved · v4 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});
 fireEvent.change(screen.getByLabelText('此片段审核朗读文本'),{target:{value:'Keep draft'}});fireEvent.click(screen.getByRole('button',{name:'核对已保存声音分配'}));
 vi.mocked(api.get).mockImplementation(async(path:string)=>(path.endsWith('/catalog')?{...catalog,plans:[{...plan,version:5,segments:[{...line,profile_version:1}]}]}:{items:[]}) as never);
 fireEvent.click(screen.getByRole('button',{name:'刷新声音来源与任务'}));await screen.findByText(/计划版本已变化/);await screen.findByText(/声音 Profile 版本不一致/);
 fireEvent.click(screen.getByRole('button',{name:'定位声音片段 1'}));expect((screen.getByLabelText('此片段审核朗读文本') as HTMLTextAreaElement).value).toBe('Keep draft');expect(screen.getByRole('button',{name:'保存声音方向'}).hasAttribute('disabled')).toBe(true);expect(api.put).not.toHaveBeenCalled();
});
it('does not reuse another plan editor when a different plan has the same segment ID',async()=>{
 const api=client();vi.mocked(api.get).mockImplementation(async(path:string)=>(path.endsWith('/catalog')?{...catalog,plans:[plan,{...plan,id:'other',title:'Other',segments:[{...line,text:'Different source',direction:undefined}]}]}:{items:[]}) as never);
 render(<VoiceDirectionPanel client={api}/>);await screen.findByText('Saved · v4 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});fireEvent.click(screen.getByRole('button',{name:'核对已保存声音分配'}));fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'other'}});
 expect(screen.queryByRole('button',{name:'定位声音片段 1'})).toBeNull();expect((screen.getByLabelText('此片段审核朗读文本') as HTMLTextAreaElement).value).toBe('Different source');expect(api.put).not.toHaveBeenCalled();
});
it('clears inspection on owner replacement and never mounts stale source segments',async()=>{
 const api=client();const view=render(<VoiceDirectionPanel client={api}/>);await screen.findByText('Saved · v4 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});fireEvent.click(screen.getByRole('button',{name:'核对已保存声音分配'}));
 const next=client();vi.mocked(next.get).mockImplementation(async(path:string)=>(path.endsWith('/catalog')?{...catalog,plans:[{...plan,stale:true}]}:{items:[]}) as never);view.rerender(<VoiceDirectionPanel client={next}/>);await screen.findByText('Saved · v4 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});expect(screen.queryByRole('button',{name:'核对已保存声音分配'})).toBeNull();expect(screen.queryByLabelText('此片段审核朗读文本')).toBeNull();
});

it('preserves the original legacy segment emotion when loading the direction editor',async()=>{
 const api=client();vi.mocked(api.get).mockImplementation(async(path:string)=>(path.endsWith('/catalog')?{...catalog,plans:[{...plan,segments:[{...line,direction:undefined,emotion:'sad'}]}]}:{items:[]}) as never);
 render(<VoiceDirectionPanel client={api}/>);await screen.findByText('Saved · v4 · PENDING_REVIEW');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});expect((screen.getByLabelText('情绪参数') as HTMLInputElement).value).toBe('sad');
 fireEvent.click(screen.getByRole('button',{name:'保存声音方向'}));await waitFor(()=>expect(api.put).toHaveBeenCalledWith('/voice-direction/plans/plan/segments/line',expect.objectContaining({emotion:'sad',expected_version:4})));
});

it('never reports unknown enums, nonboolean review flags or malformed source/parameters as clean',()=>{
 const invalid={...line,kind:'ALIEN',attribution_status:'UNKNOWN',profile_version:0,source_start:undefined,source_text_digest:'missing',direction:{...line.direction!,text_reviewed:'false',voice_authorized:'false',speech_rate:0,pause_ms:0.5}} as unknown as AudioSegment;
 const issues=voiceAssignmentIssues(plan,invalid,{...catalog,profiles:[{...catalog.profiles[0],version:0}]});
 for(const text of ['类型缺失','状态缺失','原文范围','朗读速度','版本不一致','朗读文本','声音使用授权'])expect(issues.some(issue=>issue.includes(text))).toBe(true);
 expect(voiceAssignmentIssues(plan,{...line,kind:undefined,attribution_status:undefined} as unknown as AudioSegment,catalog)).toEqual(expect.arrayContaining([expect.stringMatching(/类型缺失/),expect.stringMatching(/状态缺失/)]));
});
function retainedClick(node:HTMLElement):()=>void {const key=Object.keys(node).find(k=>k.startsWith('__reactProps$'))!;return (node as any)[key].onClick;}
it('invalidates retained review navigation across page ABA and unmount',()=>{
 const locate=vi.fn(),segments=Array.from({length:21},(_,i)=>({...line,id:`s${i}`}));const view=render(<VoicePlanReview plan={{...plan,segments}} catalog={catalog} available onLocate={locate}/>);
 const old=retainedClick(screen.getByRole('button',{name:'定位声音片段 1'}));fireEvent.click(screen.getByRole('button',{name:'下一页声音核对'}));fireEvent.click(screen.getByRole('button',{name:'上一页声音核对'}));old();expect(locate).not.toHaveBeenCalled();
 const latest=retainedClick(screen.getByRole('button',{name:'定位声音片段 1'}));view.unmount();latest();expect(locate).not.toHaveBeenCalled();
});
it('invalidates retained location after profile-only refresh and plan ABA',async()=>{
 const api=client();vi.mocked(api.get).mockImplementation(async(path:string)=>(path.endsWith('/catalog')?{...catalog,plans:[plan,{...plan,id:'other'}]}:{items:[]}) as never);
 render(<VoiceDirectionPanel client={api}/>);await waitFor(()=>expect(screen.getAllByRole('option',{name:'Saved · v4 · PENDING_REVIEW'})).toHaveLength(2));fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});fireEvent.click(screen.getByRole('button',{name:'核对已保存声音分配'}));
 const old=retainedClick(screen.getByRole('button',{name:'定位声音片段 1'}));const focus=vi.spyOn(HTMLElement.prototype,'focus');fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'other'}});fireEvent.change(screen.getByLabelText('声音导演有声计划'),{target:{value:'plan'}});old();expect(focus).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'核对已保存声音分配'}));
 const beforeRefresh=retainedClick(screen.getByRole('button',{name:'定位声音片段 1'}));vi.mocked(api.get).mockImplementation(async(path:string)=>(path.endsWith('/catalog')?{...catalog,profiles:[{...catalog.profiles[0],version:3}]}:{items:[]}) as never);fireEvent.click(screen.getByRole('button',{name:'刷新声音来源与任务'}));await screen.findByText(/声音 Profile 版本不一致/);beforeRefresh();expect(focus).not.toHaveBeenCalled();
});

it('recognizes original rule-confirmed attribution and renders malformed emotion as unknown',()=>{
 expect(voiceAssignmentIssues(plan,{...line,attribution_status:'RULE_CONFIRMED'},catalog)).toEqual([]);
 render(<VoicePlanReview plan={{...plan,segments:[{...line,direction:{...line.direction!,emotion:{} as string}}]}} catalog={catalog} available onLocate={()=>{}}/>);expect(screen.getByText('情绪参数缺失或无效')).toBeTruthy();
});
