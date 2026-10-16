import type { CaptionCue, CaptionTrack } from './voiceSubtitleClient';

export type CaptionTransferIssue = { cue: number | null; message: string };
export type CaptionTransferReview = {
  issues: CaptionTransferIssue[];
  cues: { startMs: string; endMs: string; text: string; quantized: boolean }[];
  speakerCount: number;
  overlapCount: number;
};
const integer = (n: number, minimum = 0) => Number.isSafeInteger(n) && n >= minimum;
const characters = (text: string) => Array.from(text).length;
const invalidUnicode = (text: string) => Array.from(text).some(c => {
  const n = c.codePointAt(0)!; return n >= 0xd800 && n <= 0xdfff;
});

/** Advisory preflight only. Original caption export and Timeline import remain authoritative.
 * BigInt preserves rational tick arithmetic even when safe ticks times 1000 exceed 2^53.
 * Never repairs, sorts, truncates or writes the author's cues.
 */
export function reviewCaptionTransfer(track: CaptionTrack, cues: CaptionCue[]): CaptionTransferReview {
  const result: CaptionTransferReview = { issues: [], cues: [], speakerCount: 0, overlapCount: 0 };
  const issue = (cue: number | null, message: string) => result.issues.push({ cue, message });
  const base = track.timebase, duration = track.media?.duration_seconds;
  if (!base || !integer(base.numerator, 1) || !integer(base.denominator, 1) || base.numerator > 192000 || base.denominator > 1001
    || !duration || !integer(duration.numerator, 1) || !integer(duration.denominator, 1)) {
    issue(null, '时间基准或实测时长无效，请刷新原字幕记录。'); return result;
  }
  if (!cues.length) issue(null, '请先填写字幕；空轨道不能导出。');
  if (cues.length > 500) { issue(null, 'Timeline 最多接收 500 条字幕；请人工拆分交付后重新检查。'); return result; }
  let previousStart = -1, previousEnd = -1, total = 0;
  const ids = new Set<string>();
  for (const [index, cue] of cues.entries()) {
    const position = index + 1;
    if (ids.has(cue.id)) issue(position, '字幕标识重复。');
    ids.add(cue.id);
    const speaker = cue.segment_id ? track.speakers?.[cue.segment_id]?.name : undefined;
    if (cue.segment_id) {
      result.speakerCount++;
      if (!speaker) issue(position, '说话人标签尚未绑定；请保存并刷新后重新检查。');
    }
    // The authoritative source permits at most 10000 codepoints. Bound this
    // advisory scan even when the unsaved textarea contains much larger input.
    if (cue.text.length > 20000 || (speaker?.length ?? 0) > 20000) {
      issue(position, '文字超出有界检查范围；请先缩短至 Timeline 每条最多 1000 个 Unicode 字符。'); continue;
    }
    const text = speaker ? `[${speaker}] ${cue.text}` : cue.text;
    if (/[\r\u0085\u2028\u2029]/.test(text) || index === cues.length - 1 && /[\s\u0085\u001c-\u001f]$/.test(text))
      issue(position, '原字幕导出读回不保留这些换行符或末条尾随空白；请人工改为 LF 换行并核对末尾文字。');
    total += characters(text.replace(/\r\n/g, '\n'));
    if (!text.trim() || characters(text) > 1000) issue(position, 'Timeline 每条字幕须非空且最多 1000 个 Unicode 字符（含说话人标签）。');
    if (invalidUnicode(text) || /[{}<>\\\x00-\x09\x0b-\x1f\x7f]/.test(text.replace(/\r\n/g, '\n'))
      || text.includes('-->') || text.split('\n').length > 8 || text.split('\n').some(line => !line.trim())) {
      issue(position, 'Timeline 仅接收一至八行纯文字；请检查空行、控制字符、无效 Unicode 或样式/路径符号。');
    }
    if (!integer(cue.start_tick) || !integer(cue.end_tick, 1) || cue.end_tick <= cue.start_tick) {
      issue(position, '开始和结束须为安全整数 tick，且结束大于开始。'); continue;
    }
    if (cue.start_tick < previousStart) issue(position, '字幕开始时间未按顺序排列，请人工核对。');
    if (cue.start_tick < previousEnd) {
      result.overlapCount++;
      if (!cue.overlap_reason.trim()) issue(position, '字幕与此前字幕重叠，请填写有意重叠说明。');
    }
    previousStart = cue.start_tick; previousEnd = Math.max(previousEnd, cue.end_tick);
    const n = BigInt(base.numerator), d = BigInt(base.denominator);
    if (BigInt(cue.end_tick) * d * BigInt(duration.denominator) > BigInt(duration.numerator) * n)
      issue(position, '字幕结束时间超过绑定媒体的实测时长。');
    const start = BigInt(cue.start_tick) * d * 1000n, end = BigInt(cue.end_tick) * d * 1000n;
    if (end / n <= start / n) issue(position, '向下量化到毫秒后时长为零；请调整时间后再导出。');
    result.cues.push({ startMs: String(start / n), endMs: String(end / n), text, quantized: start % n !== 0n || end % n !== 0n });
  }
  if (total > 32000) issue(null, 'Timeline 字幕总计最多 32000 个 Unicode 字符（含说话人标签）。');
  return result;
}
