// @vitest-environment jsdom
import {act,cleanup,renderHook} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {ApiError} from '../api';
import {checkedTimelineRow} from './studioTimelineTypes';
import {TIMELINE_HALF_PREVIEW_SCALE,checkedTimelineExportProfile,timelineExportDimensions} from './studioTimelineExportTypes';
import {checkedTimelinePlayback,type TimelinePlayback} from './studioTimelinePlaybackTypes';
import {useStudioTimelinePlayback} from './useStudioTimelinePlayback';
import {studioProductionClient,type StudioProductionClient} from './studioProductionClient';
import {useLocalHostSession} from '../localHostSession';
import type {StudioTimelineEditorProps} from './useStudioTimelineEditor';
import captured from './fixtures/timelinePreviewProxy.actual.json';
const row=checkedTimelineRow(captured.row),asset=captured.source;
function playback(half=false):TimelinePlayback{
 const key=(half?'b':'a').repeat(64);
 return {contract:'studio-timeline-playback/1',novel_id:captured.row.novel_id,branch_id:captured.half_playback_preview.branch_id,
  cache_key:key,request_id:'playback_'+key,job_id:(half?'d':'c').repeat(64),playback_digest:(half?'f':'e').repeat(64),
  export_preview:structuredClone(half?captured.half_preview:captured.normal_preview),job:null,cache_state:'MISSING',model_called:false,automatic_replay:false,product_acceptance:'LOCAL_REQUIRED'} as TimelinePlayback;
}
function setup(alwaysFull=false){
 const client={timelinePlaybackPreview:vi.fn(async(_source:unknown,_signal?:AbortSignal,resolution?:'HALF')=>playback(!alwaysFull&&resolution==='HALF')),
  timelinePlaybackBuild:vi.fn(async()=>{throw new ApiError({status:0,code:'NETWORK_ERROR',message:'lost reply'});}),timelinePlaybackAttestation:vi.fn(),get:vi.fn(),timelineSave:vi.fn(),timelineRender:vi.fn()};
 const props:StudioTimelineEditorProps={client:client as unknown as StudioProductionClient,assets:[asset],canMutate:true,busy:false,isCurrent:()=>true,
  read:work=>work(),mutate:work=>work(),onDirtyChange:vi.fn(),onUnavailable:vi.fn(),onJob:vi.fn()};
 const options={props,source:row,isReady:()=>true,onGateChange:vi.fn(),onAuthorityLost:vi.fn()};
 const hook=renderHook(value=>useStudioTimelinePlayback(value),{initialProps:options});return {client,options,hook};
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
it('keeps original export identities and accepts only the fixed H264 output scaling policy',()=>{
 const full=checkedTimelineExportProfile(captured.normal_preview.export_profile),half=checkedTimelineExportProfile(captured.half_preview.export_profile);
 expect(full).toEqual(captured.normal_preview.export_profile);expect(Object.hasOwn(full,'preview_scale')).toBe(false);
 expect(half.preview_scale).toBe(TIMELINE_HALF_PREVIEW_SCALE);expect(timelineExportDimensions({width:98,height:66},half)).toEqual([48,32]);
 expect(timelineExportDimensions({width:98,height:66},full)).toEqual([98,66]);
 for(const value of [null,true,false,.5,'HALF','scale=iw/2',{}])expect(()=>checkedTimelineExportProfile({...full,preview_scale:value})).toThrow();
 for(const preset of ['REVIEW_MP4','DELIVERY_VP9_WEBM','AUDIO_WAV_PCM16'])expect(()=>checkedTimelineExportProfile({preset,preview_scale:TIMELINE_HALF_PREVIEW_SCALE})).toThrow();
});
it('validates the requested selection against genuine File export receipts without accepting a downgraded profile',()=>{
 const scope={novelId:captured.row.novel_id,branchId:captured.half_playback_preview.branch_id},decode=()=>{throw Error('no job expected')};
 expect(checkedTimelinePlayback(playback(),row,decode,scope).export_preview).toEqual(captured.normal_preview);
 expect(checkedTimelinePlayback(playback(true),row,decode,scope,'HALF').export_preview).toEqual(captured.half_preview);
 expect(()=>checkedTimelinePlayback(playback(),row,decode,scope,'HALF')).toThrow();
 expect(()=>checkedTimelinePlayback(playback(true),row,decode,scope)).toThrow();
});
it('changes only preview state on explicit selection, retires old mode callbacks, and preserves UNKNOWN identity',async()=>{
 const {hook,client}=setup(),oldPreview=hook.result.current.previewPlayback;
 expect(hook.result.current.resolution).toBe('ORIGINAL');expect(client.timelinePlaybackPreview).not.toHaveBeenCalled();
 act(()=>hook.result.current.changeResolution('HALF'));await act(async()=>oldPreview());expect(client.timelinePlaybackPreview).not.toHaveBeenCalled();
 await act(async()=>hook.result.current.previewPlayback());expect(client.timelinePlaybackPreview.mock.calls[0][2]).toBe('HALF');
 expect(hook.result.current.previewDimensions).toEqual([48,32]);act(()=>hook.result.current.setConfirmed(true));const oldBuild=hook.result.current.buildPlayback;
 act(()=>hook.result.current.changeResolution('ORIGINAL'));act(()=>hook.result.current.changeResolution('HALF'));
 expect(hook.result.current.preview).toBeUndefined();expect(hook.result.current.confirmed).toBe(false);
 await act(async()=>hook.result.current.previewPlayback());act(()=>hook.result.current.setConfirmed(true));await act(async()=>oldBuild());expect(client.timelinePlaybackBuild).not.toHaveBeenCalled();
 await act(async()=>hook.result.current.buildPlayback());expect(client.timelinePlaybackBuild).toHaveBeenCalledTimes(1);
 const id=hook.result.current.unknown?.preview.request_id;expect(id).toBe(playback(true).request_id);
 act(()=>hook.result.current.changeResolution('ORIGINAL'));expect(hook.result.current.resolution).toBe('HALF');expect(hook.result.current.unknown?.preview.request_id).toBe(id);
 expect(client.timelineSave).not.toHaveBeenCalled();expect(client.timelineRender).not.toHaveBeenCalled();expect(row).toEqual(checkedTimelineRow(captured.row));
});
it('rejects an older client that returns original resolution after a HALF request while preserving its original default',async()=>{
 const {hook,client}=setup(true);await act(async()=>hook.result.current.previewPlayback());expect(hook.result.current.preview).toBeDefined();
 act(()=>hook.result.current.changeResolution('HALF'));await act(async()=>hook.result.current.previewPlayback());
 expect(hook.result.current.preview).toBeUndefined();expect(hook.result.current.error).toContain('所选预览分辨率');expect(client.timelinePlaybackBuild).not.toHaveBeenCalled();
});
it('retires retained preview callbacks after permission ABA without starting a read or render',async()=>{
 const {hook,client,options}=setup();act(()=>hook.result.current.changeResolution('HALF'));const oldPreview=hook.result.current.previewPlayback,oldChange=hook.result.current.changeResolution;
 hook.rerender({...options,props:{...options.props,canMutate:false}});hook.rerender(options);
 await act(async()=>oldPreview());act(()=>oldChange('ORIGINAL'));
 expect(client.timelinePlaybackPreview).not.toHaveBeenCalled();expect(hook.result.current.resolution).toBe('HALF');
 await act(async()=>hook.result.current.previewPlayback());expect(client.timelinePlaybackPreview).toHaveBeenCalledTimes(1);expect(client.timelinePlaybackBuild).not.toHaveBeenCalled();
});
it('carries explicit HALF across original transport preview/build/attestation and decodes the real 48x32 File job',async()=>{
 useLocalHostSession.setState({token:'local-proxy-test-fixture',actorId:''});
 const sent:{url:string;body:Record<string,unknown>;headers:Headers}[]=[];
 let wrongDimensions=false;
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
  const body=JSON.parse(String(init?.body)) as Record<string,unknown>;
  sent.push({url,body,headers:new Headers(init?.headers)});
  if(url.endsWith('/playback-preview'))return new Response(JSON.stringify(body.preview_resolution==='HALF'?captured.half_playback_preview:captured.normal_playback_preview));
  if(url.endsWith('/playback-build')){
   const result=structuredClone(captured.half_playback_built);
   if(wrongDimensions)result.job.media_measurement.width=98;
   return new Response(JSON.stringify(result));
  }
  if(url.endsWith('/playback-attestation'))return new Response(JSON.stringify(captured.half_attestation));
  throw Error('Unexpected proxy transport request '+url);
 });
 vi.stubGlobal('fetch',fetcher);
 const client=studioProductionClient(captured.row.novel_id,{sessionToken:''});
 const full=await client.timelinePlaybackPreview(row);expect(full.cache_key).toBe(captured.normal_playback_preview.cache_key);
 expect(sent[0].body).toEqual({expected_version:row.version,reviewed_timeline_digest:row.timeline_digest});
 const half=await client.timelinePlaybackPreview(row,undefined,'HALF');
 const built=await client.timelinePlaybackBuild(row,half);expect(built.job?.media_measurement?.width).toBe(48);expect(built.job?.media_measurement?.height).toBe(32);
 const proof=await client.timelinePlaybackAttestation(row,built);expect(proof.sha256).toBe(captured.half_attestation.sha256);
 for(const request of sent.slice(1))expect(request.body.preview_resolution).toBe('HALF');
 expect(sent[2].body.reviewed_playback_digest).toBe(half.playback_digest);
 expect(sent[3].body.expected_request_digest).toBe(built.job!.request_digest);
 expect(sent[3].body.expected_job_version).toBe(built.job!.version);
 wrongDimensions=true;await expect(client.timelinePlaybackBuild(row,half)).rejects.toBeInstanceOf(ApiError);
 expect(sent.every(request=>request.url.includes(`/timelines/${row.id}/playback-`))).toBe(true);
});
