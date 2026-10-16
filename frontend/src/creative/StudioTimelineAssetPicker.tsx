import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { StudioAsset } from './studioClient';
import { parseTimelineAssetRange, timelineDurationHint, timelineMeasuredDuration, validTimelineAssetRange, type TimelineAssetRange, type TimelineReceiptReader } from './studioTimelineAssetRange';

/** Ordinary picker uses the same original receipt proof and explicit unknown range. */
export function StudioTimelineAssetPicker(props: { asset?: StudioAsset; canEdit: boolean; isCurrent: () => boolean;
  getRevision: () => string; readJob?: TimelineReceiptReader; onApply: (range?: TimelineAssetRange) => boolean }) {
  const [start, setStart] = useState('0'), [end, setEnd] = useState(''), [notice, setNotice] = useState(''), [pending, setPending] = useState(false);
  const alive = useRef(true), busy = useRef(false), edited = useRef(0), latest = useRef(props); latest.current = props;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const range = parseTimelineAssetRange(start, end), hint = props.asset && timelineDurationHint(props.asset);
  function change(starting: boolean, value: string) { if (busy.current || !latest.current.canEdit || !latest.current.isCurrent()) return; edited.current++; if (starting) setStart(value); else setEnd(value); }
  async function add() {
    const origin = latest.current, asset = origin.asset, revision = origin.getRevision(), edit = edited.current;
    if (!asset || busy.current || !origin.canEdit || !origin.isCurrent()) return;
    if (asset.kind === 'image') { origin.onApply(); return; }
    if (!range && !(edited.current === 0 && hint && origin.readJob)) return;
    busy.current = true; setPending(true); setNotice('');
    try {
      let duration: number | undefined;
      if (hint && origin.readJob) { try { duration = timelineMeasuredDuration(asset, await origin.readJob(hint.owner, hint.id)); } catch { /* Unknown never becomes an invented duration. */ } }
      if (!alive.current || !latest.current.isCurrent() || !latest.current.canEdit || latest.current.asset !== asset
        || origin.getRevision() !== revision || edited.current !== edit) return;
      const selected = range || (edited.current !== 0 || duration === undefined ? undefined : { in_ms: 0, out_ms: Math.min(1000, duration) });
      if (!validTimelineAssetRange(selected, duration)) { setNotice('没有可用的精确原输出时长，或范围超过实测时长。请明确填写来源起止范围；没有加入片段。'); return; }
      if (latest.current.onApply(selected)) setNotice('已把精确素材和来源范围加入本地草稿；仍须明确保存。');
      else setNotice('范围或轨道状态不适合当前草稿；请明确调整来源范围或时间线长度，没有截断输入。');
    } finally { busy.current = false; if (alive.current) setPending(false); }
  }
  return <>
    {props.asset && props.asset.kind !== 'image' && <>
      <p>{hint ? '加入时读取原已批准输出回执；只有精确版本的实测时长可用于默认范围。也可明确填写来源范围。' : '来源时长未知，请明确填写来源范围。不会假定素材有一秒；保存和渲染仍由原服务核对。'}</p>
      <label>所选素材来源起点（毫秒）<input inputMode="numeric" disabled={!props.canEdit || pending} value={start} onChange={event => change(true, event.target.value)} /></label>
      <label>所选素材来源终点（毫秒）<input inputMode="numeric" disabled={!props.canEdit || pending} value={end} onChange={event => change(false, event.target.value)} /></label>
    </>}
    <Button disabled={!props.canEdit || !props.asset || pending || props.asset.kind !== 'image' && !range && !(edited.current === 0 && hint && props.readJob)} onClick={() => void add()}>将所选素材加入轨道</Button>
    {notice && <StatusMessage>{notice}</StatusMessage>}
  </>;
}
