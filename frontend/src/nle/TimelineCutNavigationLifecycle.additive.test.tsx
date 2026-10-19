// @vitest-environment jsdom
import { cleanup, render, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { TimelineRulerPanel } from './TimelineRulerPanel';
import { StudioTimelineEditor } from '../creative/StudioTimelineEditor';
import { checkedTimelineRow } from '../creative/studioTimelineTypes';
import type { StudioTimelineEditorProps } from '../creative/useStudioTimelineEditor';
import type { StudioProductionClient } from '../creative/studioProductionClient';
const retained=vi.hoisted(()=>({clicks:[] as Array<()=>unknown>}));
vi.mock('../ui/primitives',async importOriginal=>{
 const actual=await importOriginal<typeof import('../ui/primitives')>();
 return {...actual,Button:(props:ComponentProps<typeof actual.Button>)=>{
  if(props.children==='下一个剪切点')retained.clicks.push(props.onClick as ()=>unknown);
  return <actual.Button {...props}/>;
 }};
});
const timeline={schema_version:3,media_kind:'AUDIO',duration_ms:5000,tracks:[{id:'one',kind:'AUDIO',order:0,muted:false,gain_db:0,
 clips:[{id:'a',source_snapshot:{kind:'ASSET',id:'audio',asset_kind:'audio',version:1,digest:'a'.repeat(64)},start_ms:100,in_ms:0,out_ms:500}]}]};
const base={timebase:{durationMs:5000,mediaKind:'AUDIO' as const},view:{startMs:0,scale:0.1},playheadMs:0,marks:{inMs:null,outMs:null},editable:true,onView:vi.fn()};
afterEach(()=>{cleanup();retained.clicks=[];});
it.each(['timeline','document','playhead','editable','version','unmount'] as const)('retires retained navigation on %s ABA/lifecycle',fault=>{
 const onPlayhead=vi.fn(),isCurrent=()=>true,navigation={timeline,contextKey:'doc-one',isCurrent};
 const props={...base,onPlayhead,navigation};const view=render(<TimelineRulerPanel {...props}/>);const old=retained.clicks.at(-1)!;
 if(fault==='timeline'){view.rerender(<TimelineRulerPanel {...props} navigation={{...navigation,timeline:{...timeline,duration_ms:4500}}}/>);view.rerender(<TimelineRulerPanel {...props}/>);}
 if(fault==='document'){view.rerender(<TimelineRulerPanel {...props} navigation={{...navigation,contextKey:'doc-two'}}/>);view.rerender(<TimelineRulerPanel {...props}/>);}
 if(fault==='playhead'){view.rerender(<TimelineRulerPanel {...props} playheadMs={100}/>);view.rerender(<TimelineRulerPanel {...props}/>);}
 if(fault==='editable'){view.rerender(<TimelineRulerPanel {...props} editable={false}/>);view.rerender(<TimelineRulerPanel {...props}/>);}
 if(fault==='version'){view.rerender(<TimelineRulerPanel {...props} navigation={{...navigation,isCurrent:()=>true}}/>);view.rerender(<TimelineRulerPanel {...props}/>);}
 if(fault==='unmount')view.unmount();
 old();expect(onPlayhead).not.toHaveBeenCalled();
 if(fault!=='unmount'){fireEvent.click(screen.getByRole('button',{name:'下一个剪切点'}));expect(onPlayhead).toHaveBeenCalledWith(100);}
});
it('rechecks the original owner fence immediately before navigation even without a rerender',()=>{
 let ready=true;const onPlayhead=vi.fn();render(<TimelineRulerPanel {...base} onPlayhead={onPlayhead} navigation={{timeline,contextKey:'one',isCurrent:()=>ready}}/>);
 ready=false;fireEvent.click(screen.getByRole('button',{name:'下一个剪切点'}));expect(onPlayhead).not.toHaveBeenCalled();
});
it('refuses a mismatched timebase instead of navigating using another document length',()=>{
 const onPlayhead=vi.fn();render(<TimelineRulerPanel {...base} timebase={{durationMs:4000,mediaKind:'AUDIO'}} onPlayhead={onPlayhead} navigation={{timeline,contextKey:'one'}}/>);
 expect((screen.getByRole('button',{name:'下一个剪切点'}) as HTMLButtonElement).disabled).toBe(true);expect(screen.getByRole('alert').textContent).toContain('总长不一致');expect(onPlayhead).not.toHaveBeenCalled();
});

it('uses the mounted original busy/revision owner and retires a prior saved version with identical timeline contents',async()=>{
 let version=1,busy=false;
 const row=()=>checkedTimelineRow({id:'same-saved-document',title:'Navigation fixture',version,timeline_digest:'b'.repeat(64),created_at:'2026-10-19',updated_at:'2026-10-19',timeline});
 const client={timelineList:vi.fn(async()=>({items:[row()]})),timelineGet:vi.fn(async()=>row()),timelineSave:vi.fn(),timelineEdit:vi.fn(),timelineRender:vi.fn()};
 const props:StudioTimelineEditorProps={projectId:'fixture',mediaKind:'AUDIO',client:client as unknown as StudioProductionClient,
  assets:[{id:'audio',kind:'audio',version:1,sha256:'a'.repeat(64),filename:'SYNTHETIC.wav',deleted_at:null}] as StudioTimelineEditorProps['assets'],
  canMutate:true,busy:false,isBusy:()=>busy,isCurrent:()=>true,read:async work=>work(),mutate:async work=>work(),onDirtyChange:vi.fn(),onJob:vi.fn(),onUnavailable:vi.fn()};
 render(<StudioTimelineEditor {...props}/>);
 const adopt=async()=>{
  await screen.findByRole('option',{name:`Navigation fixture · v${version}`});
  fireEvent.change(screen.getByLabelText('读取已保存时间线'),{target:{value:'same-saved-document'}});
  await screen.findByRole('heading',{name:`Navigation fixture · v${version}`});
  fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择'));fireEvent.click(screen.getByRole('button',{name:'采用服务端时间线'}));
 };
 await adopt();const ruler=()=>screen.getByRole('region',{name:'时间线标尺'});
 busy=true;fireEvent.click(screen.getByRole('button',{name:'下一个剪切点'}));expect(ruler().getAttribute('data-playhead-ms')).toBe('0');
 busy=false;fireEvent.click(screen.getByRole('button',{name:'下一个剪切点'}));expect(ruler().getAttribute('data-playhead-ms')).toBe('100');
 const old=retained.clicks.at(-1)!;version=2;fireEvent.click(screen.getByRole('button',{name:'刷新时间线列表'}));await adopt();
 old();expect(ruler().getAttribute('data-playhead-ms')).toBe('100');
 fireEvent.click(screen.getByRole('button',{name:'下一个剪切点'}));await waitFor(()=>expect(ruler().getAttribute('data-playhead-ms')).toBe('600'));
 expect(client.timelineSave).not.toHaveBeenCalled();expect(client.timelineEdit).not.toHaveBeenCalled();expect(client.timelineRender).not.toHaveBeenCalled();
});

it.each(['timeline','capability','version','playhead'] as const)('retains its actual composition until matching end across %s rerenders',change=>{
 const onPlayhead=vi.fn(),navigation={timeline,contextKey:'one',isCurrent:()=>true};const props={...base,navigation,onPlayhead};
 const view=render(<TimelineRulerPanel {...props}/>);const original=screen.getByRole('region',{name:'时间线标尺'});original.focus();fireEvent.compositionStart(original);
 if(change==='timeline'){const next=structuredClone(timeline);next.tracks[0].clips[0].out_ms=600;view.rerender(<TimelineRulerPanel {...props} navigation={{...navigation,timeline:next}}/>);}
 if(change==='capability'){view.rerender(<TimelineRulerPanel {...props} editable={false}/>);view.rerender(<TimelineRulerPanel {...props}/>);}
 if(change==='version')view.rerender(<TimelineRulerPanel {...props} navigation={{...navigation,isCurrent:()=>true}}/>);
 if(change==='playhead')view.rerender(<TimelineRulerPanel {...props} playheadMs={150}/>);
 const current=screen.getByRole('region',{name:'时间线标尺'});expect(current).toBe(original);expect(document.activeElement).toBe(original);
 fireEvent.keyDown(current,{key:'ArrowDown',keyCode:40,isComposing:false});expect(onPlayhead).not.toHaveBeenCalled();
 fireEvent.compositionEnd(current);fireEvent.keyDown(current,{key:'ArrowDown',keyCode:40,isComposing:false});expect(onPlayhead).toHaveBeenCalledTimes(1);expect(onPlayhead).toHaveBeenLastCalledWith(change==='playhead'?600:100);
});

it('only matching compositionend/blur finishes a connected input session, including focus moving inside the ruler',()=>{
 const onPlayhead=vi.fn();render(<TimelineRulerPanel {...base} onPlayhead={onPlayhead} navigation={{timeline,contextKey:'one'}}/>);
 const root=screen.getByRole('region',{name:'时间线标尺'}),button=screen.getByRole('button',{name:'下一个剪切点'});root.focus();fireEvent.compositionStart(root);
 fireEvent.compositionEnd(button);fireEvent.blur(button,{relatedTarget:root});fireEvent.keyDown(root,{key:'ArrowDown',isComposing:false});expect(onPlayhead).not.toHaveBeenCalled();
 fireEvent.blur(root,{relatedTarget:button});button.focus();fireEvent.keyDown(button,{key:'ArrowDown',isComposing:false});expect(onPlayhead).toHaveBeenCalledTimes(1);expect(onPlayhead).toHaveBeenLastCalledWith(100);
});

it('starts a fresh input region for another document and ignores delayed events from the retired DOM',()=>{
 const onPlayhead=vi.fn(),navigation={timeline,contextKey:'one'};const props={...base,onPlayhead,navigation};const view=render(<TimelineRulerPanel {...props}/>);
 const old=screen.getByRole('region',{name:'时间线标尺'});old.focus();fireEvent.compositionStart(old);
 view.rerender(<TimelineRulerPanel {...props} navigation={{...navigation,contextKey:'two'}}/>);const current=screen.getByRole('region',{name:'时间线标尺'});
 expect(current).not.toBe(old);expect(old.isConnected).toBe(false);current.focus();fireEvent.keyDown(current,{key:'ArrowDown'});expect(onPlayhead).toHaveBeenCalledTimes(1);
 onPlayhead.mockClear();fireEvent.compositionStart(current);fireEvent.compositionEnd(old);fireEvent.keyDown(current,{key:'ArrowDown',isComposing:false});expect(onPlayhead).not.toHaveBeenCalled();
 fireEvent.compositionEnd(current);fireEvent.keyDown(current,{key:'ArrowDown'});expect(onPlayhead).toHaveBeenCalledTimes(1);expect(onPlayhead).toHaveBeenLastCalledWith(100);
});
