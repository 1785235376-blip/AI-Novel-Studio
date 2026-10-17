import { previewCaptionTimingOffset } from './captionTimingOffset';
import type { CaptionCue, CaptionTrack } from './voiceSubtitleClient';

export type CaptionTextReplacement = { cues: CaptionCue[]; occurrences: number; changes: { id: string; index: number; before: string; after: string; occurrences: number }[] };
/** Literal, case-sensitive local replacement; timing validation reuses the existing owner helper. */
export function previewCaptionTextReplacement(track: CaptionTrack, cues: CaptionCue[], find: string, replacement: string): CaptionTextReplacement {
  if (!find || find.length > 2000 || Array.from(find).length > 1000) throw new Error('查找内容须为 1 至 1000 个字符。');
  if (replacement.length > 20000 || Array.from(replacement).length > 10000) throw new Error('替换内容超过字幕文本上限。');
  if (!cues.length || cues.length > 2000) throw new Error('请选择包含 1 至 2000 条字幕的当前轨道。');
  const changes: CaptionTextReplacement['changes'] = [];
  const findLength = Array.from(find).length, replacementLength = Array.from(replacement).length;
  let occurrences = 0;
  const result = cues.map((cue, index) => {
    if (typeof cue.text !== 'string' || cue.text.length > 20000) throw new Error(`字幕 ${index + 1} 文本过长，请先修正。`);
    const parts = cue.text.split(find), count = parts.length - 1;
    const length = Array.from(cue.text).length + count * (replacementLength - findLength);
    if (length > 10000) throw new Error(`字幕 ${index + 1} 替换后超过 10000 字符，未应用任何替换。`);
    const text = count ? parts.join(replacement) : cue.text;
    if (text !== cue.text) { changes.push({ id: cue.id, index, before: cue.text, after: text, occurrences: count }); occurrences += count; }
    return { ...cue, text };
  });
  // Offset zero validates the complete result without moving/sorting/clamping cues.
  const validated = previewCaptionTimingOffset(track, result, 'all', '0').cues;
  return { cues: validated, changes, occurrences };
}
