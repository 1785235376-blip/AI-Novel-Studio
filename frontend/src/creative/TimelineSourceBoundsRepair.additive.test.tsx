// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import wire from './timelineSourceBounds.testFixture.json';
import {previewSourceBoundsRepair} from './timelineSourceBoundsRepair';
import {StudioTimelineSourceBoundsRepair} from './StudioTimelineSourceBoundsRepair';
import type {TimelineSourceBounds} from './studioTimelineSourceBounds';
import type {StudioTimelineRow,StudioTimelineDraft} from './studioTimelineTypes';
const source=wire.source as StudioTimelineRow,observation=wire.result as TimelineSourceBounds,draft:StudioTimelineDraft={title:source.title,timeline:source.timeline};
afterEach(cleanup);
it('shortens only the exact source out point without mutation or ripple',()=>{
 const before=structuredClone(draft),result=previewSourceBoundsRepair(draft,source,observation);expect(result.before).toBe(9000);expect(result.after).toBe(6000);expect(draft).toEqual(before);
 const expected=structuredClone(draft);expected.timeline.tracks[0].clips[0].out_ms=6000;expect(result.draft).toEqual(expected);
});
it('refuses changed draft, source pin, locked track and empty remaining source',()=>{
 const dirty=structuredClone(draft);dirty.timeline.tracks[0].clips[0].start_ms++;expect(()=>previewSourceBoundsRepair(dirty,source,observation)).toThrow();
 expect(()=>previewSourceBoundsRepair(draft,source,{...observation,timeline_version:99})).toThrow();
 const locked=structuredClone(source);locked.timeline.tracks[0].locked=true;expect(()=>previewSourceBoundsRepair({title:locked.title,timeline:locked.timeline},locked,observation)).toThrow();
 const empty=structuredClone(source);empty.timeline.tracks[0].clips[0].in_ms=7000;const proof={...observation,clip:{...observation.clip,in_ms:7000},requested_start_frame:56000};expect(()=>previewSourceBoundsRepair({title:empty.title,timeline:empty.timeline},empty,proof)).toThrow();
});
it('requires explicit confirmation and invalidates retained actions after a scope change',()=>{
 const onApply=vi.fn(()=>true),props={scope:{},source,draft,observation,disabled:false,isCurrent:()=>true,getRevision:()=> 'one',onApply};const view=render(<StudioTimelineSourceBoundsRepair {...props}/>);
 fireEvent.click(screen.getByText('将实测出点应用到本地草稿'));expect(onApply).not.toHaveBeenCalled();fireEvent.click(screen.getByLabelText('确认仅收短出点，保留其他位置'));
 const button=screen.getByText('将实测出点应用到本地草稿'),old=(button as any)[Object.keys(button).find(k=>k.startsWith('__reactProps$'))!].onClick;
 view.rerender(<StudioTimelineSourceBoundsRepair {...props} scope={{}}/>);act(()=>old());expect(onApply).not.toHaveBeenCalled();fireEvent.click(screen.getByLabelText('确认仅收短出点，保留其他位置'));fireEvent.click(screen.getByText('将实测出点应用到本地草稿'));expect(onApply).toHaveBeenCalledTimes(1);expect(onApply.mock.calls[0]).toEqual([previewSourceBoundsRepair(draft,source,observation).draft]);
});
it('consumes consent synchronously and rejects an unmounted retained action',()=>{
 const onApply=vi.fn(()=>true),props={scope:{},source,draft,observation,disabled:false,isCurrent:()=>true,getRevision:()=> 'one',onApply};let view=render(<StudioTimelineSourceBoundsRepair {...props}/>);
 fireEvent.click(screen.getByLabelText('确认仅收短出点，保留其他位置'));let button=screen.getByText('将实测出点应用到本地草稿');let callback=(button as any)[Object.keys(button).find(k=>k.startsWith('__reactProps$'))!].onClick;
 act(()=>{callback();callback();});expect(onApply).toHaveBeenCalledTimes(1);view.unmount();onApply.mockClear();view=render(<StudioTimelineSourceBoundsRepair {...props}/>);fireEvent.click(screen.getByLabelText('确认仅收短出点，保留其他位置'));button=screen.getByText('将实测出点应用到本地草稿');callback=(button as any)[Object.keys(button).find(k=>k.startsWith('__reactProps$'))!].onClick;view.unmount();act(()=>callback());expect(onApply).not.toHaveBeenCalled();
});
