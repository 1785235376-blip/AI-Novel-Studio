// @vitest-environment jsdom
import { createRef } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StudioTimelinePlaybackOptions } from './StudioTimelinePlaybackOptions';
const fixture = () => { const media=createRef<HTMLVideoElement>(); const video=document.createElement('video');
  video.setAttribute('src','blob:review-a'); Object.defineProperty(media,'current',{value:video,writable:true});
  const view=render(<StudioTimelinePlaybackOptions media={media} url="blob:review-a" identity="a-v1" />);
  return {media,video,...view}; };
afterEach(cleanup);
it('changes only local review speed and loop, without autoplay', () => {
  const {video}=fixture(), play=vi.spyOn(video,'play');
  expect(video.loop).toBe(false); expect(video.playbackRate).toBe(1);
  fireEvent.change(screen.getByLabelText('预览播放速度'),{target:{value:'1.5'}});
  fireEvent.click(screen.getByRole('checkbox'));
  expect(video.playbackRate).toBe(1.5); expect(video.loop).toBe(true); expect(play).not.toHaveBeenCalled();
});
it('resets options on a new verified cache identity', () => {
  const {video,media,rerender}=fixture();
  fireEvent.change(screen.getByLabelText('预览播放速度'),{target:{value:'2'}}); fireEvent.click(screen.getByRole('checkbox'));
  video.setAttribute('src','blob:review-b');
  rerender(<StudioTimelinePlaybackOptions media={media} url="blob:review-b" identity="b-v2" />);
  expect(video.playbackRate).toBe(1); expect(video.loop).toBe(false);
  fireEvent.change(screen.getByLabelText('预览播放速度'),{target:{value:'0.75'}});
  expect(video.playbackRate).toBe(0.75);
});
it('ignores controls when the displayed element no longer matches verified cache URL', () => {
  const {video}=fixture(); video.setAttribute('src','blob:other');
  fireEvent.change(screen.getByLabelText('预览播放速度'),{target:{value:'2'}}); fireEvent.click(screen.getByRole('checkbox'));
  expect(video.playbackRate).toBe(1); expect(video.loop).toBe(false);
});
it('observes native control rate changes and ignores retired callbacks after unmount', () => {
  const {video,unmount}=fixture(); video.playbackRate=1.75; fireEvent(video,new Event('ratechange'));
  expect((screen.getByLabelText('预览播放速度') as HTMLSelectElement).value).toBe('1.75');
  const checkbox=screen.getByRole('checkbox'); const key=Object.keys(checkbox).find(k=>k.startsWith('__reactProps$'))!;
  const handler=(checkbox as unknown as Record<string,{onChange:(event:unknown)=>void}>)[key].onChange;
  unmount(); handler({currentTarget:{checked:true}}); expect(video.loop).toBe(false);
});
it('is mounted only for original visible verified media and never invokes generation or review commands', async () => {
  const { StudioTimelinePlaybackPanel } = await import('./StudioTimelinePlaybackPanel');
  const { waveformRow } = await import('./studioTimelineWaveform.testFixtures');
  const command = vi.fn(async () => {}), report = vi.fn();
  const controller: import('./useStudioTimelinePlayback').StudioTimelinePlaybackController = {
    available:true, preview:undefined, visible:{ key:'cache-a',url:'blob:review-a',bytes:12,digest:'a'.repeat(64),jobVersion:2,source:waveformRow(),durationMs:5000 },
    positionMs:0,pending:undefined,unknown:undefined,error:'',notice:'',locked:false,dirty:false,canOperate:true,confirmed:false,
    previewPlayback:command,buildPlayback:command,readOriginal:command,loadPlayback:command,cancelOriginal:command,
    auxiliary:undefined,canReadDuringBuild:false,canCancel:false,setConfirmed:vi.fn(),reportPosition:report,reportMediaError:vi.fn(),clear:vi.fn(),
  };
  const pause=vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{});
  try {
    const view=render(<StudioTimelinePlaybackPanel controller={controller} />);
    const video=screen.getByLabelText('已核验的时间线缓存视频') as HTMLVideoElement;
    fireEvent.change(screen.getByLabelText('预览播放速度'),{target:{value:'0.5'}}); fireEvent.click(screen.getByRole('checkbox'));
    expect(video.playbackRate).toBe(0.5); expect(video.loop).toBe(true); expect(command).not.toHaveBeenCalled();
    expect(controller.visible?.source.timeline.tracks[1].clips[0].speed_num).toBe(3);
    view.rerender(<StudioTimelinePlaybackPanel controller={{...controller,visible:undefined}} />);
    expect(screen.queryByLabelText('预览播放速度')).toBeNull(); expect(pause).toHaveBeenCalled();
    expect(command).not.toHaveBeenCalled();
  } finally { cleanup(); pause.mockRestore(); }
});
