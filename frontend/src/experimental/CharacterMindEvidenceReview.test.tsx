// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StoryGraphPanel } from './StoryGraphPanel';
import { CharacterMindEvidenceReview } from './CharacterMindEvidenceReview';
import { matchesCharacterMindEvidence, type CharacterMindEvidence } from './characterMindEvidence';
import { experimentalClient } from './api';
import type { Chapter } from '../api';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const evidence = {record_id:'event-1',record_version:3,chapter_id:'ch1',source_versions:{ch1:{version:2,digest:'chapter-pin'},'relation:r1':{version:4,digest:'relation-pin'}}};
const pin: CharacterMindEvidence = {characterId:'alice',category:'FALSE_BELIEF',text:'钥匙已经遗失',evidenceStatus:'HYPOTHESIS',evidence};
const row = {id:'event-1',version:3,kind:'KNOWLEDGE_EVENT',status:'APPROVED',stale:false,title:'阿澄误解',chapter_id:'ch1',event_order:2,sources:evidence.source_versions,data:{character_id:'alice',operation:'MISUNDERSTAND',category:'FALSE_BELIEF',relation_id:'r1',psychology_id:null,value:pin.text,state_key:'current',evidence_status:'HYPOTHESIS',scene_id:null,calendar:'story',world_time:12,valid_from:null,valid_to:null,until_chapter_id:null,evidence:[{chapter_id:'ch1',start:0,quote:'作者原文证据'}]}};
const reply = (value: unknown,status=200) => new Response(JSON.stringify(value),{status});
function setup(original: unknown=row,status=200) {
 const fetch=vi.fn(async(url:string,init:RequestInit)=>{
  if(url.endsWith('/records/event-1'))return reply(original,status);
  if(url.endsWith('/character-context'))return reply({false_beliefs:[{text:pin.text,epistemic_status:pin.category,evidence_status:pin.evidenceStatus,evidence}]});
  if(url.includes('/query?'))return reply({nodes:[],edges:[],visible_count:0});
  if(url.endsWith('/catalog'))return reply({items:[{kind:'CHAPTER',id:'ch1'},{kind:'CHARACTER',id:'alice'}]});
  if(init.method==='POST')return reply(row,201);
  return reply({items:[]});
 });
 vi.stubGlobal('fetch',fetch); const client=experimentalClient('novel',{sessionToken:'session'});
 const view=render(<StoryGraphPanel client={client} chapter={{id:'ch1'} as Chapter} mindEnabled/>); return {fetch,client,view};
}
async function query(){fireEvent.click(screen.getByRole('button',{name:'人物可知视图'}));fireEvent.change(screen.getByLabelText('视角人物 ID'),{target:{value:'alice'}});fireEvent.click(screen.getByRole('button',{name:'查询当前视图'}));await screen.findByText(pin.text);}
async function inspect(){await query();fireEvent.click(screen.getByRole('button',{name:'退出人物视图并核对原事件'}));}
it('exits character mode before author read and manually saves a candidate through the original owner',async()=>{
 const {fetch}=setup();await query();expect(fetch.mock.calls.some(([url])=>url.endsWith('/records/event-1'))).toBe(false);expect(screen.queryByText('作者原文证据')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'退出人物视图并核对原事件'}));fireEvent.click(await screen.findByRole('button',{name:'将原人物事件复制到待审表单'}));
 expect(screen.queryByLabelText('人物上下文预览')).toBeNull();expect((screen.getByLabelText('记录类型') as HTMLSelectElement).value).toBe('KNOWLEDGE_EVENT');expect((screen.getByLabelText('人物信念或心智状态') as HTMLTextAreaElement).value).toBe(pin.text);expect(screen.getAllByText('作者原文证据')).toHaveLength(2);
 expect(fetch.mock.calls.filter(([,init])=>init.method!=='GET')).toHaveLength(1);
 fireEvent.change(screen.getByLabelText('人物信念或心智状态'),{target:{value:'人工修正的信念'}});fireEvent.click(screen.getByRole('button',{name:'保存待审记录'}));
 await waitFor(()=>expect(fetch.mock.calls.some(([url,init])=>url.endsWith('/records')&&init.method==='POST')).toBe(true));
 const call=fetch.mock.calls.find(([url,init])=>url.endsWith('/records')&&init.method==='POST')!;
 expect(JSON.parse(call[1].body as string)).toMatchObject({kind:'KNOWLEDGE_EVENT',event_order:2,data:{character_id:'alice',category:'FALSE_BELIEF',value:'人工修正的信念',evidence_status:'HYPOTHESIS'}});
 expect(fetch.mock.calls.some(([url,init])=>url.endsWith('/approve')||init.method==='PUT')).toBe(false);
});
it.each([[{...row,version:4},200],[{...row,stale:true},200],[{...row,status:'ARCHIVED'},200],[{...row,data:{...row.data,character_id:'bob'}},200],[{...row,sources:{...row.sources,ch1:{version:2,digest:'changed'}}},200],[{},403],[{},404]])('blocks stale, changed, denied or missing original events',async(original,status)=>{
 setup(original,status);await inspect();await waitFor(()=>expect(screen.queryByText('正在读取…')).toBeNull());expect(screen.queryByRole('button',{name:'将原人物事件复制到待审表单'})).toBeNull();expect(screen.queryByText('作者原文证据')).toBeNull();
});
it('keeps dirty author input until cancelled and consumes copy once',async()=>{
 setup();await inspect();const button=await screen.findByRole('button',{name:'将原人物事件复制到待审表单'});
 fireEvent.change(screen.getByLabelText('记录标题'),{target:{value:'未保存输入'}});expect((button as HTMLButtonElement).disabled).toBe(true);expect((screen.getByRole('button',{name:'人物可知视图'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'取消编辑'}));await waitFor(()=>expect((button as HTMLButtonElement).disabled).toBe(false));fireEvent.click(button);expect((button as HTMLButtonElement).disabled).toBe(true);
});
it('clears author evidence on return and client identity replacement',async()=>{
 const {view,fetch}=setup();await inspect();await screen.findByText('作者原文证据');fireEvent.click(screen.getByRole('button',{name:'人物可知视图'}));expect(screen.queryByText('作者原文证据')).toBeNull();
 fetch.mockClear();fireEvent.click(screen.getByRole('button',{name:'作者全知视图'}));await screen.findByLabelText('记录标题');expect(fetch.mock.calls.some(([url])=>url.endsWith('/records/event-1'))).toBe(false);
 await inspect();await screen.findByText('作者原文证据');view.rerender(<StoryGraphPanel client={experimentalClient('other',{sessionToken:'other'})} chapter={{id:'ch1'} as Chapter} mindEnabled/>);expect(screen.queryByLabelText('人物事件原始证据核对')).toBeNull();
});
it('rejects wrong category, text, evidence status, malformed data and incomplete or extra pins',()=>{
 expect(matchesCharacterMindEvidence(row,pin)).toBe(true);
 for(const patch of [{category:'SECRET'},{value:'different'},{evidence_status:'EXPLICIT'},{operation:'FORGET'},{evidence:[{chapter_id:'ch1',quote:'q',start:-1}]},{valid_from:10,valid_to:5}])expect(matchesCharacterMindEvidence({...row,data:{...row.data,...patch}},pin)).toBe(false);
 for(const sources of [{},{...row.sources,extra:{version:1,digest:'x'}},{ch1:{version:2,digest:'chapter-pin'}}])expect(matchesCharacterMindEvidence({...row,sources},pin)).toBe(false);
 expect(matchesCharacterMindEvidence({...row,event_order:-1},pin)).toBe(false);
});
it('does not revive late evidence across client A to B to A replacement',async()=>{
 let finish:(value:Response)=>void=()=>{};vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(resolve=>{finish=resolve;})));
 const a=experimentalClient('a',{sessionToken:'a'}),b=experimentalClient('b',{sessionToken:'b'}),onCopy=vi.fn();const view=render(<CharacterMindEvidenceReview client={a} pin={pin} blocked={false} onCopy={onCopy}/>);const oldFinish=finish;
 view.rerender(<CharacterMindEvidenceReview client={b} pin={pin} blocked={false} onCopy={onCopy}/>);view.rerender(<CharacterMindEvidenceReview client={a} pin={pin} blocked={false} onCopy={onCopy}/>);oldFinish(reply(row));await Promise.resolve();expect(screen.queryByText('作者原文证据')).toBeNull();expect(onCopy).not.toHaveBeenCalled();
});

it('accepts original-owner Unicode code-point limits for title, state and quoted evidence',()=>{
 const value='😀'.repeat(8000), quote='😀'.repeat(4000);
 const unicodeRow={...row,title:'😀'.repeat(240),data:{...row.data,value,state_key:'😀'.repeat(160),evidence:[{chapter_id:'ch1',start:0,quote}]}};
 expect(matchesCharacterMindEvidence(unicodeRow,{...pin,text:value})).toBe(true);
 expect(matchesCharacterMindEvidence({...unicodeRow,title:unicodeRow.title+'😀'},{...pin,text:value})).toBe(false);
});

it('rechecks the original event after author refresh instead of reusing a previous reconciliation',async()=>{
 const current=structuredClone(row);setup(current);await inspect();await screen.findByRole('button',{name:'将原人物事件复制到待审表单'});
 current.version=4;fireEvent.click(screen.getByRole('button',{name:'刷新实验记录'}));
 await screen.findByText(/原事件版本、人物、类别、来源摘要或审核状态已变化/);
 expect(screen.queryByRole('button',{name:'将原人物事件复制到待审表单'})).toBeNull();
});
