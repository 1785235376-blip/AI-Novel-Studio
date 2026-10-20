import { describe, expect, it } from 'vitest';
import { reviewCaptionTransfer } from './captionTransferReview';
import type { CaptionCue, CaptionTrack } from './voiceSubtitleClient';
const cue: CaptionCue = { id:'one',start_tick:0,end_tick:1000,text:'你好 🌙\nHello',segment_id:null,overlap_reason:'' };
const track = { id:'track',version:1,asset_id:'media',timebase:{numerator:1000,denominator:1},media:{duration_seconds:{numerator:10,denominator:1},waveform:{status:'UNAVAILABLE'}},cues:[cue],speakers:{},warnings:[] } satisfies CaptionTrack;
const messages = (cues: CaptionCue[]) => reviewCaptionTransfer(track,cues).issues.map(i=>i.message).join(' ');
describe('caption file-handoff advisory review',()=>{
 it('preserves UTF text and labels without mutation',()=>{
  const source={...track,speakers:{seg:{name:'月亮🌙'}}};const cues=[{...cue,segment_id:'seg'}];const before=JSON.stringify(cues);
  const result=reviewCaptionTransfer(source,cues);expect(result.issues).toEqual([]);expect(result.cues[0]).toEqual({startMs:'0',endMs:'1000',text:'[月亮🌙] 你好 🌙\nHello',quantized:false});expect(JSON.stringify(cues)).toBe(before);expect(result.speakerCount).toBe(1);
 });
 it('uses exact rational tick conversion beyond floating point products',()=>{
  const source={...track,timebase:{numerator:192000,denominator:1001},media:{...track.media,duration_seconds:{numerator:Number.MAX_SAFE_INTEGER,denominator:1}}};
  const start=9007199254740000;const result=reviewCaptionTransfer(source,[{...cue,start_tick:start,end_tick:start+100}]);
  expect(result.cues[0].startMs).toBe(String(BigInt(start)*1001n*1000n/192000n));
 });
 it('reports millisecond collapse, range, ordering and nested overlap',()=>{
  expect(reviewCaptionTransfer({...track,timebase:{numerator:192000,denominator:1}},[{...cue,end_tick:1}]).issues[0].message).toContain('时长为零');
  expect(messages([{...cue,end_tick:10001}])).toContain('实测时长');
  expect(messages([{...cue,end_tick:9000},{...cue,id:'two',start_tick:1000,end_tick:2000,overlap_reason:'合唱'},{...cue,id:'three',start_tick:3000,end_tick:4000}])).toContain('重叠说明');
  expect(messages([{...cue,start_tick:500,end_tick:1000},{...cue,id:'two',start_tick:0}])).toContain('未按顺序');
 });
 it.each([NaN,Infinity,1.5,Number.MAX_SAFE_INTEGER+1,-1])('rejects unsafe tick %s',value=>{expect(messages([{...cue,start_tick:value}])).toContain('安全整数');});
 it.each(['\ud800','<b>hi</b>','a\\b','{tag}','a\tB','a\n\nB','a --> b',Array(9).fill('a').join('\n')])('reports literal format restrictions %j',text=>{expect(messages([{...cue,text}])).toContain('纯文字');});
 it('counts astral Unicode by codepoint and includes flattened speaker labels',()=>{
  expect(messages([{...cue,text:'🌙'.repeat(1000)}])).toBe('');
  expect(messages([{...cue,text:'🌙'.repeat(1001)}])).toContain('1000');
  expect(reviewCaptionTransfer({...track,speakers:{seg:{name:'speaker'}}},[{...cue,text:'a'.repeat(999),segment_id:'seg'}]).issues[0].message).toContain('1000');
 });
 it.each(['a\r\nb','a\u0085b','a\u2028b','a\u2029b','a '])('reports original export readback loss %j',text=>{
  expect(messages([{...cue,text}])).toContain('导出读回');
 });
 it('bounds oversized collections before scanning or rendering and rejects huge draft text',()=>{
  const result=reviewCaptionTransfer(track,Array(501).fill(cue));expect(result.cues).toEqual([]);expect(result.issues).toHaveLength(1);
  expect(messages([{...cue,text:'a'.repeat(20001)}])).toContain('有界检查范围');
 });
 it('reports aggregate limits, missing speakers and invalid metadata',()=>{
  expect(messages(Array.from({length:501},(_,i)=>({...cue,id:String(i),start_tick:i,end_tick:i+1})))).toContain('500');
  expect(messages(Array.from({length:33},(_,i)=>({...cue,id:String(i),start_tick:i,end_tick:i+1,text:'🌙'.repeat(1000)})))).toContain('32000');
  expect(messages([{...cue,segment_id:'missing'}])).toContain('尚未绑定');
  expect(reviewCaptionTransfer({...track,timebase:{numerator:0,denominator:1}},[cue]).issues[0].message).toContain('时间基准');
 });
});
