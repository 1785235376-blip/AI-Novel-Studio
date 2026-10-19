import { expect, it, vi } from 'vitest';
import fixture from './storyboardVideoTimeline.testFixture.json';
import { checkedVideoTimelinePreview, createStoryboardVideoTimelineClient, type VideoTimelineCreate, type VideoTimelineInput } from './storyboardVideoTimelineClient';
import type { StoryboardReceipt } from './studioStoryboardContract';
const receipt=fixture.receipt as StoryboardReceipt,body=fixture.body as VideoTimelineInput,intent=fixture.request as VideoTimelineCreate;
const shown=checkedVideoTimelinePreview(fixture.shown,receipt,body);

it('checks actual CPU decoded receipt and uses explicit preview/create/read routes with one request identity',async()=>{
  const request=vi.fn().mockResolvedValueOnce(fixture.shown).mockResolvedValueOnce(fixture.created).mockResolvedValueOnce({...fixture.created,replayed:true});
  const api=createStoryboardVideoTimelineClient(fixture.created.timeline.novel_id,'/creative',null,request);
  expect(await api.storyboardVideoTimelinePreview(receipt,body)).toEqual(fixture.shown);
  const created=await api.storyboardVideoTimelineCreate(receipt,intent,shown),reopened=await api.storyboardVideoTimelineCreation(receipt,intent,shown);
  expect(created.timeline).toEqual(reopened.timeline);expect(reopened.replayed).toBe(true);
  expect(request.mock.calls.map(call=>[call[0],call[1]])).toEqual([['/creative/documents/'+receipt.document_snapshot.id+'/storyboard/video-timeline/preview','POST'],
    ['/creative/documents/'+receipt.document_snapshot.id+'/storyboard/video-timeline/create','POST'],['/creative/documents/'+receipt.document_snapshot.id+'/storyboard/video-timeline/creations/'+intent.request_id,undefined]]);
});

it.each(['order','trim','source','duration','dimensions','format','timeline','flag','extra'])('rejects corrupted %s preview',fault=>{
  const value=structuredClone(fixture.shown);if(fault==='order')value.clips.reverse();if(fault==='trim')value.clips[0].out_ms++;if(fault==='source')value.clips[0].video_result.asset.version++;
  if(fault==='duration')value.clips[0].measured.duration_ms=1;if(fault==='dimensions')value.clips[0].measured.width=5000;if(fault==='format')value.clips[0].measured.extension='';
  if(fault==='timeline')value.timeline.tracks[0].clips[0].source_snapshot.id='forged';if(fault==='flag')(value as unknown as {model_called:boolean}).model_called=true;
  if(fault==='extra')Object.assign(value,{execute:true});expect(()=>checkedVideoTimelinePreview(value,receipt,body)).toThrow();
});

it.each(['request','preview','origin','snapshot','scope','timeline','digest'])('rejects changed %s create/recovery proof',async fault=>{
  const value=structuredClone(fixture.created);if(fault==='request')value.creation_receipt.request.title='changed';if(fault==='preview')value.creation_receipt.preview.clips[0].in_ms++;
  if(fault==='origin')value.storyboard_origin.shots.reverse();if(fault==='snapshot')value.creation_receipt.creation_snapshot.version++;if(fault==='scope')value.timeline.novel_id='other';
  if(fault==='timeline')value.timeline.timeline.tracks[0].clips[0].out_ms--;if(fault==='digest')value.creation_receipt.request_digest='0'.repeat(64);
  const request=vi.fn().mockResolvedValue(value),api=createStoryboardVideoTimelineClient(fixture.created.timeline.novel_id,'/creative',null,request);
  await expect(api.storyboardVideoTimelineCreation(receipt,intent,shown)).rejects.toThrow();expect(request).toHaveBeenCalledTimes(1);
});

it('rejects stale/unapproved or injected choice before dispatch',()=>{
  const request=vi.fn(),api=createStoryboardVideoTimelineClient(fixture.created.timeline.novel_id,'/creative',null,request);
  for(const clips of [[],[...body.clips,...body.clips,...body.clips],[body.clips[0],body.clips[0]],[{...body.clips[0],shot_version:999}]])
    expect(()=>api.storyboardVideoTimelinePreview(receipt,{...body,clips})).toThrow();
  expect(()=>api.storyboardVideoTimelinePreview({...receipt,approved:false},body)).toThrow();expect(request).not.toHaveBeenCalled();
});


it('keeps the exact creation proof while reopening a later original Timeline edit',async()=>{
  const value=structuredClone(fixture.created);value.timeline.version=2;value.timeline.timeline.tracks[0].muted=true;value.timeline.timeline_digest='1'.repeat(64);value.replayed=true;
  const request=vi.fn().mockResolvedValue(value),api=createStoryboardVideoTimelineClient(fixture.created.timeline.novel_id,'/creative',null,request);
  const reopened=await api.storyboardVideoTimelineCreation(receipt,intent,shown);expect(reopened.timeline.version).toBe(2);expect(reopened.timeline.timeline.tracks[0].muted).toBe(true);
});
