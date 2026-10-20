// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { changedRangeBeyondMeasurement, measuredBoundFromWaveform } from './timelineMeasuredBounds';
import { waveformDto, waveformRow, waveformAssets } from './studioTimelineWaveform.testFixtures';
import { cloneTimeline } from './studioTimelineTypes';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import type { StudioProductionClient } from './studioProductionClient';
afterEach(cleanup);
it('uses exact source sample duration, accepts boundary and never infers bounds for another pin',()=>{
 const row=waveformRow(),bound=measuredBoundFromWaveform(waveformDto(),row),next=cloneTimeline(row);next.timeline.tracks[1].clips[0].out_ms=1001;
 expect(changedRangeBeyondMeasurement(row,next,[bound])).toBe('audio-clip');next.timeline.tracks[1].clips[0].out_ms=1000;expect(changedRangeBeyondMeasurement(row,next,[bound])).toBeUndefined();
 next.timeline.tracks[1].clips[0].out_ms=2000;next.timeline.tracks[1].clips[0].source_snapshot.version++;expect(changedRangeBeyondMeasurement(row,next,[bound])).toBeUndefined();
});
it('does not clamp pre-existing author input or invent duration when none was measured',()=>{
 const row=waveformRow(),next=cloneTimeline(row);next.timeline.tracks[1].clips[0].out_ms=1600;
 expect(changedRangeBeyondMeasurement(row,next,[])).toBeUndefined();const same=cloneTimeline(next);same.title='Title only';expect(changedRangeBeyondMeasurement(next,same,[measuredBoundFromWaveform(waveformDto(),row)])).toBeUndefined();
});
it('rejects a waveform receipt from a different original timeline or source version',()=>{
 const row=waveformRow();expect(()=>measuredBoundFromWaveform({...waveformDto(),timeline_version:2},row)).toThrow();const dto=waveformDto();dto.source_snapshot.version++;expect(()=>measuredBoundFromWaveform(dto,row)).toThrow();
});
async function setup(){
 const row=waveformRow(),client={timelineList:vi.fn(async()=>({items:[row]})),timelineGet:vi.fn(async()=>row),timelineSave:vi.fn(),timelineRender:vi.fn()};
 const props:StudioTimelineEditorProps={client:client as unknown as StudioProductionClient,assets:waveformAssets(),projectId:'project-waveform',canMutate:true,busy:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work(),onDirtyChange:vi.fn(),onJob:vi.fn(),onUnavailable:vi.fn()};
 const hook=renderHook((next:StudioTimelineEditorProps)=>useStudioTimelineEditor(next),{initialProps:props});await waitFor(()=>expect(hook.result.current.rows).toHaveLength(1));await act(async()=>hook.result.current.checkServer(row.id));act(()=>hook.result.current.setAdoptConfirmed(true));act(()=>hook.result.current.adoptCandidate(false));return {row,client,props,hook};
}
it('registers only current original measurement and rejects trim/slip and direct form overrun before history changes',async()=>{
 const {hook,props,client}=await setup();const base=hook.result.current.base!;act(()=>expect(hook.result.current.observeWaveformMeasurement(waveformDto(),base,props.client)).toBe(true));expect(hook.result.current.measuredSourceCount).toBe(1);
 const before=cloneTimeline(hook.result.current.draft!);
 act(()=>expect(hook.result.current.trimClip('audio-track','audio-clip',1,1600,false)).toBe(false));
 act(()=>expect(hook.result.current.slipClip('audio-track','audio-clip',300)).toBe(false));
 act(()=>expect(hook.result.current.change(input=>{input.timeline.tracks[1].clips[0].out_ms=1600;})).toBe(false));
 expect(hook.result.current.draft).toEqual(before);expect(hook.result.current.canUndo).toBe(false);expect(hook.result.current.error).toContain('实测长度');expect(client.timelineSave).not.toHaveBeenCalled();expect(client.timelineRender).not.toHaveBeenCalled();
 act(()=>expect(hook.result.current.change(input=>{input.title='Still editable';})).toBe(true));expect(hook.result.current.measuredSourceCount).toBe(1);
});
it('drops measurement on authority transition and does not reuse a changed asset pin',async()=>{
 const {hook,props}=await setup();act(()=>expect(hook.result.current.observeWaveformMeasurement(waveformDto(),hook.result.current.base!,props.client)).toBe(true));
 hook.rerender({...props,assets:props.assets.map(asset=>asset.kind==='audio'?{...asset,version:3}:asset)});expect(hook.result.current.measuredSourceCount).toBe(0);
 hook.rerender({...props,canMutate:false});hook.rerender(props);expect(hook.result.current.measuredSourceCount).toBe(0);
});
it('allows an in-bound trim through original undo without converting unknown sources to zero',async()=>{
 const {hook,props}=await setup();act(()=>expect(hook.result.current.observeWaveformMeasurement(waveformDto(),hook.result.current.base!,props.client)).toBe(true));const before=cloneTimeline(hook.result.current.draft!);
 act(()=>expect(hook.result.current.trimClip('audio-track','audio-clip',1,997,false)).toBe(true));expect(hook.result.current.draft!.timeline.tracks[1].clips[0].out_ms).toBe(997);act(()=>hook.result.current.undo());expect(hook.result.current.draft).toEqual(before);
});
