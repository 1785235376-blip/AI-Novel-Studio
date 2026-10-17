import type { CaptionCue, CaptionTrack } from './voiceSubtitleClient';

export type CaptionTimingOffset = { cues: CaptionCue[]; changes: { id: string; index: number; before: [number, number]; after: [number, number] }[]; offset: number };
const integer = (value: number, minimum = 0) => Number.isSafeInteger(value) && value >= minimum;
const text = (value: unknown, minimum: number, maximum: number): value is string => typeof value === 'string' && value.length <= maximum * 2 && Array.from(value).length >= minimum && Array.from(value).length <= maximum;
const fail = (message: string): never => { throw new Error(message); };

/** Local draft operation only. The original save owner revalidates live sources and CAS.
 * Validate the entire result, including unselected neighbors; never sort or clamp cues.
 */
export function previewCaptionTimingOffset(track: CaptionTrack, cues: CaptionCue[], selected: readonly string[] | 'all', input: string): CaptionTimingOffset {
 if (input.trim() !== input || !/^[+-]?\d{1,16}$/.test(input) || !Number.isSafeInteger(Number(input))) fail('偏移量必须是安全整数 tick，可使用正负号。');
 const offset = Number(input), base = track.timebase, duration = track.media?.duration_seconds;
 if (!base || !integer(base.numerator, 1) || base.numerator > 192000 || !integer(base.denominator, 1) || base.denominator > 1001 || !duration || !integer(duration.numerator, 1) || !integer(duration.denominator, 1)) fail('时间基准或实测时长无效，请刷新字幕来源。');
 if (!cues.length || cues.length > 2000) fail('偏移须包含 1 至 2000 条字幕。');
 const ids = new Set(cues.map(cue => cue.id));
 if (ids.size !== cues.length) fail('字幕标识重复，不能预览偏移。');
 const targets = selected === 'all' ? ids : new Set(selected);
 if (!targets.size || selected !== 'all' && (targets.size !== selected.length || selected.some(id => !ids.has(id)))) fail('请选择当前字幕行。');
 const changes: CaptionTimingOffset['changes'] = [];
 let previousStart = -1, previousEnd = -1;
 const result = cues.map((cue, index) => {
  if (!text(cue.id, 1, 240) || !text(cue.text, 1, 10000) || !cue.text.trim() || /[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(cue.text) || /\n\s*\n/.test(cue.text) || !(cue.segment_id === null || text(cue.segment_id, 0, 240)) || !text(cue.overlap_reason, 0, 500)) fail(`字幕 ${index + 1} 字段无效，请先修正本地输入。`);
  if (!integer(cue.start_tick) || !integer(cue.end_tick, 1) || cue.end_tick <= cue.start_tick) fail(`字幕 ${index + 1} 时间必须为递增的安全整数 tick。`);
  const delta = targets.has(cue.id) ? BigInt(offset) : 0n;
  const start = BigInt(cue.start_tick) + delta, end = BigInt(cue.end_tick) + delta;
  if (start < 0n || end > BigInt(Number.MAX_SAFE_INTEGER)) fail(`字幕 ${index + 1} 偏移后超出安全整数范围。`);
  if (end * BigInt(base.denominator) * BigInt(duration.denominator) > BigInt(duration.numerator) * BigInt(base.numerator)) fail(`字幕 ${index + 1} 偏移后超过实测媒体时长。`);
  const start_tick = Number(start), end_tick = Number(end);
  if (start_tick < previousStart) fail(`字幕 ${index + 1} 偏移后顺序无效。`);
  if (start_tick < previousEnd && !cue.overlap_reason.trim()) fail(`字幕 ${index + 1} 偏移后重叠，须先人工填写有意重叠说明。`);
  previousStart = start_tick; previousEnd = Math.max(previousEnd, end_tick);
  if (targets.has(cue.id)) changes.push({ id: cue.id, index, before: [cue.start_tick, cue.end_tick], after: [start_tick, end_tick] });
  return { ...cue, start_tick, end_tick };
 });
 return { cues: result, changes, offset };
}
