// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ComponentProps, MouseEvent } from 'react';
import { TrackHeaderPanel } from './TrackHeaderPanel';
import { checkedTimeline, cloneTimeline } from '../creative/studioTimelineTypes';
const retained=vi.hoisted(()=>({clicks:[] as Array<(event:MouseEvent<HTMLButtonElement>)=>void>}));
vi.mock('../ui/primitives',async importOriginal=>{
 const actual=await importOriginal<typeof import('../ui/primitives')>();
 return {...actual,Button:(props:ComponentProps<typeof actual.Button>)=>{
  if(props.children==='a1')retained.clicks.push(props.onClick!);
  return <actual.Button {...props}/>;
 }};
});
const timeline=checkedTimeline({schema_version:3,media_kind:'AUDIO',duration_ms:8000,tracks:[{id:'sound',kind:'AUDIO',order:0,muted:false,gain_db:0,clips:['a1','a2'].map((id,index)=>({id,start_ms:index*2000,in_ms:0,out_ms:500,source_snapshot:{kind:'ASSET',id:'audio',asset_kind:'audio',version:1,digest:'a'.repeat(64)}}))}]});
const event={button:0,ctrlKey:true,metaKey:false} as MouseEvent<HTMLButtonElement>;
afterEach(()=>{cleanup();retained.clicks=[];});
it.each(['timeline','editable','selection','unmount'] as const)('rejects the retained selection callback after %s ABA/lifecycle',fault=>{
 const onSelectClips=vi.fn();const props={timeline,editable:true,selectedClipIds:['a1'],onSelectClips};const view=render(<TrackHeaderPanel {...props}/>);const old=retained.clicks.at(-1)!;
 if(fault==='timeline'){view.rerender(<TrackHeaderPanel {...props} timeline={{...timeline,duration_ms:9000}}/>);view.rerender(<TrackHeaderPanel {...props}/>);}
 if(fault==='editable'){view.rerender(<TrackHeaderPanel {...props} editable={false}/>);view.rerender(<TrackHeaderPanel {...props}/>);}
 if(fault==='selection'){view.rerender(<TrackHeaderPanel {...props} selectedClipIds={['a2']}/>);view.rerender(<TrackHeaderPanel {...props}/>);}
 if(fault==='unmount')view.unmount();
 onSelectClips.mockClear();old(event);expect(onSelectClips).not.toHaveBeenCalled();
});
it('keeps structurally unchanged rerenders usable and routes only to the current view callback',()=>{
 const oldSelect=vi.fn(),currentSelect=vi.fn();const props={timeline,editable:true,selectedClipIds:['a1'],onSelectClips:oldSelect};const view=render(<TrackHeaderPanel {...props}/>);const click=retained.clicks.at(-1)!;
 view.rerender(<TrackHeaderPanel {...props} timeline={cloneTimeline(timeline)} onSelectClips={currentSelect}/>);click(event);
 expect(oldSelect).not.toHaveBeenCalled();expect(currentSelect).toHaveBeenCalledWith([]);
});
it('clears invalid selections when the document becomes unavailable',()=>{
 const select=vi.fn();const view=render(<TrackHeaderPanel timeline={timeline} editable selectedClipIds={['a1']} onSelectClips={select}/>);
 view.rerender(<TrackHeaderPanel timeline={{schema_version:99}} editable={false} selectedClipIds={['a1']} onSelectClips={select}/>);
 expect(select).toHaveBeenCalledWith([]);
});
