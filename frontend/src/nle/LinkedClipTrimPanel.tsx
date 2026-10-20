import { useEffect, useRef, useState } from 'react';
import { Button } from '../ui/primitives';
import type { StudioTimeline } from '../creative/studioTimelineTypes';
import { linkedPairFacts } from '../creative/studioTimelineLinkedSplit';
import { linkedTrimFacts } from '../creative/studioTimelineLinkedTrim';

export function LinkedClipTrimPanel(props: { timeline: StudioTimeline; selectedClipIds: readonly string[];
  ready: boolean; onTrim: (keepFromMs: number, keepToMs: number) => void }) {
  const [from, setFrom] = useState(''), [to, setTo] = useState('');
  const inputGeneration = useRef(0), alive = useRef(true), reviewedGeneration = inputGeneration.current;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  if (props.timeline.schema_version !== 2 || !props.timeline.clip_links?.length) return null;
  let pair: ReturnType<typeof linkedPairFacts> | undefined, preview: ReturnType<typeof linkedTrimFacts> | undefined, error = '';
  try {
    pair = linkedPairFacts(props.timeline, props.selectedClipIds);
    if (from !== '' && to !== '') preview = linkedTrimFacts(props.timeline, props.selectedClipIds, Number(from), Number(to));
  } catch (reason) { error = reason instanceof Error ? reason.message : '请重新核对来源和共同区间。'; }
  return <section aria-label="已保存链接联动裁剪">
    <h4>已保存链接联动裁剪</h4>
    <p>共同来源区间按各自原入点起算。保留双方时间线起点、原偏移和链接，仅缩小来源范围；不波纹，不移动后续片段。</p>
    {pair && <p>可保留相对区间：0 — {pair.commonLength} 毫秒。目标：{pair.pair.video_clip_id} ↔ {pair.pair.audio_clip_id}；偏移 {pair.pair.offset_ms} 毫秒。</p>}
    <label>共同保留入点（相对毫秒）<input aria-label="共同保留入点（相对毫秒）" type="number" min={0} step={1} value={from} disabled={!props.ready} onChange={event => { inputGeneration.current++; setFrom(event.currentTarget.value); }} /></label>
    <label>共同保留出点（相对毫秒）<input aria-label="共同保留出点（相对毫秒）" type="number" min={0} step={1} max={pair?.commonLength} value={to} disabled={!props.ready} onChange={event => { inputGeneration.current++; setTo(event.currentTarget.value); }} /></label>
    {preview && <><p>将同时裁剪双方，保留 [{preview.keepFromMs}, {preview.keepToMs}) 毫秒，共 {preview.durationMs} 毫秒。</p>
      {[preview.video, preview.audio].map(({ clip }) => <p key={clip.id}>{clip.id}：来源 [{clip.in_ms}, {clip.out_ms}) → [{clip.in_ms + preview.keepFromMs}, {clip.in_ms + preview.keepToMs})；时间线起点保持 {clip.start_ms} 毫秒。</p>)}</>}
    {props.ready && error && <p>{error}</p>}
    {!props.ready && <p>需先保存草稿，并核对当前来源与权限；裁剪后先保存，再编辑其他内容。</p>}
    <Button disabled={!props.ready || !preview} onClick={() => {
      if (alive.current && props.ready && preview && inputGeneration.current === reviewedGeneration) props.onTrim(preview.keepFromMs, preview.keepToMs);
    }}>按已预览区间联动裁剪链接</Button>
    <p>仅支持一对 schema 2、1× 视频／音频，无转场和淡入淡出；越界、扩展及其他模式整批拒绝。</p>
  </section>;
}
