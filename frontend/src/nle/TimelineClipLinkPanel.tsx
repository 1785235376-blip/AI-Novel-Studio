import { Button } from '../ui/primitives';
import type { StudioTimeline } from '../creative/studioTimelineTypes';
import { changeClipLinks } from '../creative/studioTimelineClipLinks';

/** Explicit intents only; draft/history/CAS stay in the original editor owner. */
export function TimelineClipLinkPanel(props: { timeline: StudioTimeline; selectedClipIds: readonly string[];
  editable: boolean; onLink: () => void; onUnlink: () => void }) {
  if (props.timeline.schema_version !== 2) return null;
  let canLink = false, canUnlink = false;
  try { changeClipLinks(props.timeline, props.selectedClipIds, false); canLink = true; } catch { /* unavailable selection */ }
  try { changeClipLinks(props.timeline, props.selectedClipIds, true); canUnlink = true; } catch { /* unavailable selection */ }
  return <section aria-label="视频音频片段链接">
    <h4>视频／音频片段链接</h4>
    <p>明确选择同一时间线的一对视频轨与音频轨片段建立链接。移动任一成员会联动另一成员，保持起点偏移；同时选中两者只移动一次。</p>
    <ul>{props.timeline.clip_links?.map(pair => <li key={pair.video_clip_id}>{pair.video_clip_id} ↔ {pair.audio_clip_id} · 音频起点偏移 {pair.offset_ms} 毫秒</li>)}</ul>
    <Button disabled={!props.editable || !canLink} onClick={props.onLink}>链接所选视频与音频</Button>
    <Button disabled={!props.editable || !canUnlink} onClick={props.onUnlink}>解除所选片段链接</Button>
    <p>仅更新原时间线草稿，可撤销，明确保存后保留关系。锁轨、来源失效或越界整批拒绝。链接中的独立裁剪、拆分、滑移与来源替换暂不支持，请先解除链接；联动移动保留原轨道。</p>
  </section>;
}
