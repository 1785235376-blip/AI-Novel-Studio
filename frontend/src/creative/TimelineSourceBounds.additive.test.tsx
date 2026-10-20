// @vitest-environment jsdom
import {act,cleanup,renderHook} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import wire from './timelineSourceBounds.testFixture.json';
import {checkedTimelineSourceBounds,type TimelineSourceBounds} from './studioTimelineSourceBounds';
import {studioProductionClient} from './studioProductionClient';
import {useStudioTimelineSourceBounds,type TimelineSourceBoundsOptions} from './useStudioTimelineSourceBounds';
import type {StudioTimelineRow} from './studioTimelineTypes';
import type {StudioTimelineEditorProps} from './useStudioTimelineEditor';
const source=wire.source as StudioTimelineRow,result=wire.result as TimelineSourceBounds;
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('decodes the actual overlong File clip observation without pretending it fits or changing it',()=>{
 const before=structuredClone(source);expect(checkedTimelineSourceBounds(result,source,'measured',{novelId:result.novel_id})).toEqual(result);expect(result.within_source).toBe(false);expect(result.maximum_out_ms).toBe(6000);expect(source).toEqual(before);
 for(const field of ['within_source','maximum_out_ms','requested_end_frame','frame_count','timeline_digest','source_snapshot'])expect(()=>checkedTimelineSourceBounds({...result,[field]:true},source,'measured')).toThrow();
});
it('uses the original captured Studio transport with exact read-only selected source body',async()=>{
 const fetch=vi.fn(async(_url:unknown,_init?:RequestInit)=>new Response(JSON.stringify(result),{status:200}));vi.stubGlobal('fetch',fetch);const client=studioProductionClient(result.novel_id,{sessionToken:'synthetic-host'});
 expect(await client.timelineSourceBounds(source,'measured')).toEqual(result);expect(fetch.mock.calls[0][0]).toContain('/source-bounds');expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({expected_version:source.version,reviewed_timeline_digest:source.timeline_digest,clip_id:'measured',source_snapshot:result.source_snapshot});
});
function setup(){
 let revision=0,generation=0;const client={timelineSourceBounds:vi.fn(async()=>result)},mutate=vi.fn(),onUnavailable=vi.fn();
 const assets=source.timeline.tracks.flatMap(t=>t.clips.map(c=>({id:c.source_snapshot.id,kind:c.source_snapshot.asset_kind,version:c.source_snapshot.version,sha256:c.source_snapshot.digest})));
 const props={client,assets,projectId:result.novel_id,canMutate:true,busy:false,isCurrent:()=>true,read:async<T,>(work:()=>Promise<T>)=>work(),mutate,onUnavailable} as unknown as StudioTimelineEditorProps;
 const options:TimelineSourceBoundsOptions={props,source,selectedClipIds:['measured'],getRevision:()=>String(revision),getSelectionGeneration:()=>generation,isReady:()=>true};
 const hook=renderHook((value:TimelineSourceBoundsOptions)=>useStudioTimelineSourceBounds(value),{initialProps:options});return {client,mutate,onUnavailable,hook,options,change:()=>{revision++;generation++;hook.rerender(options);}};
}
it('reads only on request, retains a truthful invalid-range result and never mutates',async()=>{
 const s=setup();expect(s.client.timelineSourceBounds).not.toHaveBeenCalled();await act(async()=>s.hook.result.current.request());expect(s.hook.result.current.preview?.within_source).toBe(false);expect(s.mutate).not.toHaveBeenCalled();expect(s.hook.result.current.error).toBe('');
});
it('retires late reads after a draft/selection change and refuses a retained request callback',async()=>{
 const s=setup();let finish!:(v:TimelineSourceBounds)=>void;s.client.timelineSourceBounds.mockImplementationOnce(()=>new Promise(r=>{finish=r;}));const old=s.hook.result.current.request;let work!:Promise<void>;act(()=>{work=old();});s.change();await act(async()=>{finish(result);await work;});expect(s.hook.result.current.preview).toBeUndefined();await act(async()=>old());expect(s.client.timelineSourceBounds).toHaveBeenCalledTimes(1);expect(s.mutate).not.toHaveBeenCalled();
});
