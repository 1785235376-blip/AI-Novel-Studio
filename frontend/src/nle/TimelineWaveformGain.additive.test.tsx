// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { waveformDto, waveformRow } from '../creative/studioTimelineWaveform.testFixtures';
import { projectWaveformGain } from '../creative/timelineWaveformGain';
import { TimelineWaveformPanel } from './TimelineWaveformPanel';
afterEach(cleanup);
function source(){const row=waveformRow(),track=row.timeline.tracks[1],clip=track.clips[0];track.muted=false;track.gain_db=0;clip.muted=false;clip.gain_db=0;clip.fade_in_ms=0;clip.fade_out_ms=0;return row;}
it('preserves original peaks at unity gain and leaves receipt/source untouched',()=>{
 const row=source(),dto=waveformDto(),before=structuredClone({row,dto});expect(projectWaveformGain(dto,row).peaks).toEqual(dto.peaks);expect({row,dto}).toEqual(before);
});
it.each(['track','clip'] as const)('shows silence for %s mute without rewriting source peaks',kind=>{
 const row=source();if(kind==='track')row.timeline.tracks[1].muted=true;else row.timeline.tracks[1].clips[0].muted=true;
 const dto=waveformDto(),result=projectWaveformGain(dto,row);expect(result.muted).toBe(true);expect(result.peaks.every(value=>value===0)).toBe(true);expect(dto.peaks.some(value=>value>0)).toBe(true);
});
it('combines track/clip dB and exposes above-unity estimates without normalization',()=>{
 const row=source();row.timeline.tracks[1].gain_db=6;row.timeline.tracks[1].clips[0].gain_db=6;
 const result=projectWaveformGain(waveformDto(),row);expect(result.gainDb).toBe(12);expect(result.peaks[1]).toBeCloseTo(10**(12/20));expect(result.aboveUnity).toBeGreaterThan(0);
});
it('projects linear fades in speed-adjusted timeline time using bucket maximum, not guessed peak position',()=>{
 const row=source(),dto=waveformDto();dto.peaks=dto.peaks.map(()=>1);row.timeline.tracks[1].clips[0].fade_in_ms=100;row.timeline.tracks[1].clips[0].fade_out_ms=100;
 const result=projectWaveformGain(dto,row);const expectedFirst=((dto.start_frame+dto.samples_per_bucket)*1000/dto.sample_rate-dto.clip.in_ms)*dto.clip.speed_den/dto.clip.speed_num/100;
 expect(result.peaks[0]).toBeCloseTo(expectedFirst,10);expect(result.peaks[250]).toBe(1);expect(result.peaks.at(-1)).toBeLessThan(.1);
});
it('refuses mismatched original versions, pins and invalid fade settings',()=>{
 const row=source();row.version++;expect(()=>projectWaveformGain(waveformDto(),row)).toThrow();row.version--;row.timeline.tracks[1].clips[0].fade_in_ms=99999;expect(()=>projectWaveformGain(waveformDto(),row)).toThrow();
});
it('keeps source waveform, requires explicit display toggle, clips only SVG and resets on owner change',()=>{
 const row=source();row.timeline.tracks[1].gain_db=12;const dto=waveformDto(),onRequest=vi.fn();const props={available:true,canRequest:true,pending:false,error:'',unavailable:'',preview:dto,source:row,onRequest};
 const view=render(<TimelineWaveformPanel {...props}/>);expect(screen.queryByRole('img',{name:'增益与淡化的显示估算包络'})).toBeNull();
 fireEvent.click(screen.getByLabelText('显示已保存片段的增益与淡化估算'));expect(screen.getAllByRole('img')).toHaveLength(2);
 const bars=screen.getByRole('img',{name:'增益与淡化的显示估算包络'}).querySelectorAll('rect');expect(Number(bars[1].getAttribute('height'))).toBe(96);expect(Number(bars[1].getAttribute('data-estimated-peak'))).toBeGreaterThan(1);expect(onRequest).not.toHaveBeenCalled();
 view.rerender(<TimelineWaveformPanel {...props} source={structuredClone(row)}/>);expect(screen.queryByRole('img',{name:'增益与淡化的显示估算包络'})).toBeNull();expect(screen.getByRole('img',{name:'已测量的所选片段源采样包络'})).toBeTruthy();
});
