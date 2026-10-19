// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {TrackHeaderPanel} from './TrackHeaderPanel';
import {checkedTimeline} from '../creative/studioTimelineTypes';
const timeline=checkedTimeline({schema_version:3,media_kind:'AUDIO',duration_ms:8000,tracks:[{id:'sound',kind:'AUDIO',order:0,muted:false,gain_db:0,clips:['a1','a2'].map((id,i)=>({id,start_ms:i*2000,in_ms:0,out_ms:500,source_snapshot:{kind:'ASSET',id:'audio',asset_kind:'audio',version:1,digest:'a'.repeat(64)}}))}]});
afterEach(cleanup);
it.each(['selection','timeline','capability'] as const)('review: composition remains active until compositionend across %s context changes', change=>{
 const onSelectClips=vi.fn();const props={documentId:'same-doc',timeline,editable:true,selectedClipIds:[],onSelectClips};
 const view=render(<TrackHeaderPanel {...props}/>);const button=()=>screen.getByRole('button',{name:'a1'});
 const originalButton=button();originalButton.focus();fireEvent.compositionStart(originalButton);
 if(change==='selection')view.rerender(<TrackHeaderPanel {...props} selectedClipIds={['a2']}/>);
 if(change==='timeline')view.rerender(<TrackHeaderPanel {...props} timeline={{...timeline,duration_ms:9000}}/>);
 if(change==='capability'){view.rerender(<TrackHeaderPanel {...props} editable={false}/>);view.rerender(<TrackHeaderPanel {...props}/>);}
 expect(button()).toBe(originalButton);if(change!=='capability')expect(document.activeElement).toBe(originalButton);
 onSelectClips.mockClear();
 // The composition session still targets the same DOM button and no end/blur occurred.
 // Some commit keys lack native isComposing; the explicit composition lifecycle is the fallback.
 fireEvent.keyDown(button(),{key:'Enter',ctrlKey:true,keyCode:13,isComposing:false});
 expect(onSelectClips).not.toHaveBeenCalled();
 fireEvent.compositionEnd(button());fireEvent.keyDown(button(),{key:'Enter',ctrlKey:true,keyCode:13});expect(onSelectClips).toHaveBeenCalledTimes(1);
});

const props=()=>({documentId:'same-doc',timeline,editable:true,selectedClipIds:['a2'],onSelectClips:vi.fn()});
const clipButton=(id='a1')=>screen.getByRole('button',{name:id});

it.each(['plain-click','ctrl-click','cmd-click','ctrl-enter'] as const)('keeps %s blocked through ordinary rerender and allows its exact original behavior after compositionend',action=>{
 const input=props();const view=render(<TrackHeaderPanel {...input}/>);const original=clipButton();original.focus();fireEvent.compositionStart(original);
 view.rerender(<TrackHeaderPanel {...input} timeline={{...timeline,duration_ms:9000}}/>);expect(clipButton()).toBe(original);expect(document.activeElement).toBe(original);
 const invoke=()=>action==='ctrl-enter'?fireEvent.keyDown(clipButton(),{key:'Enter',ctrlKey:true,isComposing:false,keyCode:13}):fireEvent.click(clipButton(),{ctrlKey:action==='ctrl-click',metaKey:action==='cmd-click'});
 input.onSelectClips.mockClear();invoke();expect(input.onSelectClips).not.toHaveBeenCalled();
 fireEvent.compositionEnd(clipButton());invoke();expect(input.onSelectClips).toHaveBeenCalledTimes(1);expect(input.onSelectClips).toHaveBeenLastCalledWith(action==='plain-click'?['a1']:['a1','a2']);
});

it('ends the active session when that actual input blurs to another clip within the same region',()=>{
 const input={...props(),selectedClipIds:[]};render(<TrackHeaderPanel {...input}/>);const first=clipButton(),second=clipButton('a2');first.focus();fireEvent.compositionStart(first);
 fireEvent.blur(first,{relatedTarget:second});second.focus();fireEvent.keyDown(second,{key:'Enter',ctrlKey:true,keyCode:13});expect(input.onSelectClips).toHaveBeenCalledTimes(1);expect(input.onSelectClips).toHaveBeenLastCalledWith(['a2']);
});

it('ignores compositionend and blur from a different node instead of dropping the still-active fallback guard',()=>{
 const input=props();render(<TrackHeaderPanel {...input}/>);const first=clipButton(),second=clipButton('a2');first.focus();fireEvent.compositionStart(first);
 fireEvent.compositionEnd(second);fireEvent.blur(second,{relatedTarget:first});fireEvent.keyDown(first,{key:'Enter',ctrlKey:true,keyCode:13,isComposing:false});expect(input.onSelectClips).not.toHaveBeenCalled();
 fireEvent.compositionEnd(first);fireEvent.keyDown(first,{key:'Enter',ctrlKey:true,keyCode:13});expect(input.onSelectClips).toHaveBeenCalledTimes(1);expect(input.onSelectClips).toHaveBeenLastCalledWith(['a1','a2']);
});

it('retires the previous document DOM session, permits fresh selection, and does not let its delayed end clear a new session',()=>{
 const input={...props(),selectedClipIds:[]};const view=render(<TrackHeaderPanel {...input}/>);const old=clipButton();old.focus();fireEvent.compositionStart(old);
 view.rerender(<TrackHeaderPanel {...input} documentId="other-doc"/>);const current=clipButton();expect(current).not.toBe(old);expect(old.isConnected).toBe(false);expect(document.activeElement).not.toBe(old);
 input.onSelectClips.mockClear();fireEvent.keyDown(old,{key:'Enter',ctrlKey:true,keyCode:13});expect(input.onSelectClips).not.toHaveBeenCalled();
 current.focus();fireEvent.keyDown(current,{key:'Enter',ctrlKey:true,keyCode:13});expect(input.onSelectClips).toHaveBeenCalledTimes(1);expect(input.onSelectClips).toHaveBeenLastCalledWith(['a1']);
 input.onSelectClips.mockClear();fireEvent.compositionStart(current);fireEvent.compositionEnd(old);fireEvent.keyDown(current,{key:'Enter',ctrlKey:true,keyCode:13});expect(input.onSelectClips).not.toHaveBeenCalled();
 fireEvent.compositionEnd(current);fireEvent.keyDown(current,{key:'Enter',ctrlKey:true,keyCode:13});expect(input.onSelectClips).toHaveBeenCalledTimes(1);expect(input.onSelectClips).toHaveBeenLastCalledWith(['a1']);
});

it('clears a session whose actual clip node was removed without leaking it to the remaining clip',()=>{
 const input={...props(),selectedClipIds:[]};const view=render(<TrackHeaderPanel {...input}/>);const old=clipButton();old.focus();fireEvent.compositionStart(old);
 const remaining={...timeline,tracks:[{...timeline.tracks[0],clips:[timeline.tracks[0].clips[1]]}]};view.rerender(<TrackHeaderPanel {...input} timeline={remaining}/>);
 expect(old.isConnected).toBe(false);fireEvent.keyDown(clipButton('a2'),{key:'Enter',ctrlKey:true,keyCode:13});expect(input.onSelectClips).toHaveBeenCalledTimes(1);expect(input.onSelectClips).toHaveBeenLastCalledWith(['a2']);
});

it('does not carry a composition session across unmount/remount',()=>{
 const input={...props(),selectedClipIds:[]};const view=render(<TrackHeaderPanel {...input}/>);const old=clipButton();old.focus();fireEvent.compositionStart(old);view.unmount();
 render(<TrackHeaderPanel {...input}/>);fireEvent.keyDown(clipButton(),{key:'Enter',ctrlKey:true,keyCode:13});expect(input.onSelectClips).toHaveBeenCalledTimes(1);expect(input.onSelectClips).toHaveBeenLastCalledWith(['a1']);
});
