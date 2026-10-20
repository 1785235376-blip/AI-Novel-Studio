import { Button } from '../ui/primitives';
import type { StudioTimeline } from '../creative/studioTimelineTypes';
import { linkedSplitFacts } from '../creative/studioTimelineLinkedSplit';

export function LinkedClipSplitPanel(props: { timeline: StudioTimeline; selectedClipIds: readonly string[];
  videoAtMs: number; ready: boolean; onSplit: () => void }) {
  if (props.timeline.schema_version !== 2 || !props.timeline.clip_links?.length) return null;
  let facts: ReturnType<typeof linkedSplitFacts> | undefined, error = '';
  try { facts = linkedSplitFacts(props.timeline, props.selectedClipIds, props.videoAtMs); }
  catch (reason) { error = reason instanceof Error ? reason.message : '请选择同一链接并核对切点。'; }
  return <section aria-label="已保存链接联动拆分">
    <h4>已保存链接联动拆分</h4>
    <p>以视频播放头为基准，音频切点加上原起点偏移；左右各保留一对链接，两段来源范围连续衔接。</p>
    {facts && <p>视频切点 {facts.videoAtMs} 毫秒；音频切点 {facts.audioAtMs} 毫秒；左右偏移均为 {facts.pair.offset_ms} 毫秒。视频基准共同区间：{facts.commonStart} — {facts.commonEnd} 毫秒（不含边界）。</p>}
    {error && props.ready && <p>{error}</p>}
    {!props.ready && <p>需先保存草稿，并核对当前来源与权限；拆分后请明确保存。</p>}
    <Button disabled={!props.ready || !facts} onClick={props.onSplit}>按已核对切点联动拆分链接</Button>
    <p>首片仅支持一对 1× 视频／音频、无转场和淡入淡出；静态图片、单边拆分及其他模式明确拒绝，不静默解链。</p>
  </section>;
}
