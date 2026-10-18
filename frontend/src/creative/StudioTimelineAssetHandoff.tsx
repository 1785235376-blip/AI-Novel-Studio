import { parseTimelineAssetRange, timelineDurationHint, timelineMeasuredDuration, validTimelineAssetRange, type TimelineAssetRange, type TimelineReceiptReader } from './studioTimelineAssetRange';
import { useEffect, useRef, useState } from 'react';
import { apiErrorView } from '../api';
import type { AssetBrowserReference } from '../assetbrowser/assetBrowserTypes';
import { Button, StatusMessage } from '../ui/primitives';
import type { StudioAsset } from './studioClient';
import { TIMELINE_LIMITS, timelineClipDuration, timelineInputKey, type StudioTimelineDraft } from './studioTimelineTypes';

/** A session-only intent. Reading it grants no permission and never edits a draft. */
export type TimelineAssetHandoff = { id: string; reference: AssetBrowserReference; readAsset: () => Promise<StudioAsset> };
export function exactHandoffAsset(asset: StudioAsset, reference: AssetBrowserReference): boolean {
  return asset.id === reference.asset_id && asset.version === reference.version && asset.sha256 === reference.digest
    && Number.isSafeInteger(reference.version) && reference.version > 0 && /^[a-f0-9]{64}$/.test(reference.digest)
    && !asset.deleted_at && ['image', 'video', 'audio'].includes(asset.kind);
}
export function timelineAssetPlacement(draft: StudioTimelineDraft, trackId: string, asset: StudioAsset): number | null {
  const track = draft.timeline.tracks.find(row => row.id === trackId);
  if (!track || track.locked || asset.deleted_at || !(track.kind === 'AUDIO' ? asset.kind === 'audio'
    : asset.kind === 'video' || draft.timeline.schema_version === 2 && asset.kind === 'image')
    || draft.timeline.tracks.reduce((count, row) => count + row.clips.length, 0) >= TIMELINE_LIMITS.clips) return null;
  const placement = track.clips.reduce((end, clip) => Math.max(end, clip.start_ms + timelineClipDuration(clip)), 0);
  return Number.isFinite(placement) && placement >= 0 && placement < draft.timeline.duration_ms ? placement : null;
}
/** Same insertion used by the ordinary picker and the explicit reference handoff. */
export function appendTimelineAsset(draft: StudioTimelineDraft, trackId: string, asset: StudioAsset, range?: TimelineAssetRange): void {
  const placement = timelineAssetPlacement(draft, trackId, asset);
  if (placement === null || asset.kind !== 'image' && (!validTimelineAssetRange(range) || range.out_ms - range.in_ms > draft.timeline.duration_ms - placement)) return;
  const track = draft.timeline.tracks.find(row => row.id === trackId)!;
  track.clips.push({ id: crypto.randomUUID(), source_snapshot: { id: asset.id, kind: 'ASSET', asset_kind: asset.kind as 'image' | 'video' | 'audio', version: asset.version, digest: asset.sha256 },
    start_ms: placement, in_ms: asset.kind === 'image' ? 0 : range!.in_ms,
    out_ms: asset.kind === 'image' ? Math.min(1000, draft.timeline.duration_ms - placement) : range!.out_ms,
    ...(track.kind === 'VIDEO' ? { x: 0, y: 0, width: draft.timeline.width, height: draft.timeline.height } : {}),
    ...([2, 3].includes(draft.timeline.schema_version ?? 1) ? { speed_num: 1, speed_den: 1, muted: false, gain_db: 0, fade_in_ms: 0, fade_out_ms: 0,
      ...(track.kind === 'VIDEO' ? { opacity: 1, include_audio: false } : {}) } : {}) });
}

export function StudioTimelineAssetHandoff({ request, draft, canEdit, isCurrent, getRevision, onApply, readJob }: {
  request: TimelineAssetHandoff; draft: StudioTimelineDraft; canEdit: boolean; isCurrent: () => boolean;
  getRevision: () => string;
  onApply: (trackId: string, asset: StudioAsset, range?: TimelineAssetRange) => boolean;
  readJob?: TimelineReceiptReader;
}) {
  const [asset, setAsset] = useState<StudioAsset>(), [trackId, setTrackId] = useState('');
  const [start, setStart] = useState('0'), [end, setEnd] = useState('');
  const [duration, setDuration] = useState<number>(), [automatic, setAutomatic] = useState(false);
  const rangeRevision = useRef(0);
  const [pending, setPending] = useState(false), [notice, setNotice] = useState(''), [done, setDone] = useState(false);
  const alive = useRef(true), inFlight = useRef(false), consumed = useRef(false);
  const latest = useRef({ request, draft, canEdit, isCurrent, getRevision, onApply, trackId, readJob, start, end, duration, automatic });
  latest.current = { request, draft, canEdit, isCurrent, getRevision, onApply, trackId, readJob, start, end, duration, automatic };
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  async function read(apply: boolean) {
    const origin = latest.current;
    if (inFlight.current || consumed.current || !origin.isCurrent() || !origin.canEdit) return;
    const inputKey = timelineInputKey(origin.draft), revision = origin.getRevision(), rangeEpoch = rangeRevision.current;
    const range = parseTimelineAssetRange(origin.start, origin.end);
    if (apply && asset?.kind !== 'image' && !validTimelineAssetRange(range, origin.duration)) return;
    inFlight.current = true; setPending(true); setNotice('');
    try {
      const fresh = await origin.request.readAsset();
      if (!alive.current || consumed.current || origin.request !== latest.current.request || !latest.current.isCurrent()) return;
      if (!exactHandoffAsset(fresh, origin.request.reference)) { setAsset(undefined); setNotice('来源已变化或不可用；不会改用最新版本。请返回素材工作区重新选择。'); return; }
      const hint = timelineDurationHint(fresh); let measured: number | undefined;
      if (hint && origin.readJob) {
        try { measured = timelineMeasuredDuration(fresh, await origin.readJob(hint.owner, hint.id)); }
        catch { /* Missing or inaccessible original proof stays unknown; no guessed value. */ }
      }
      if (!alive.current || consumed.current || origin.request !== latest.current.request || !latest.current.isCurrent()) return;
      setAsset(fresh);
      if (!apply && rangeEpoch === rangeRevision.current) {
        setDuration(measured);
        if (rangeEpoch === 0 || origin.automatic) { setStart('0'); setEnd(measured === undefined ? '' : String(Math.min(1000, measured))); setAutomatic(measured !== undefined); }
      }
      if (apply) {
        if (rangeEpoch !== rangeRevision.current || origin.getRevision() !== revision || !latest.current.canEdit || latest.current.trackId !== origin.trackId || timelineInputKey(latest.current.draft) !== inputKey
          || timelineAssetPlacement(latest.current.draft, origin.trackId, fresh) === null) {
          setNotice('草稿、轨道或编辑状态已变化；请重新核对后明确加入。'); return;
        }
        if (fresh.kind !== 'image' && (!validTimelineAssetRange(range, measured) || origin.automatic && measured !== origin.duration)) {
          setDuration(measured); setNotice('原输出时长回执缺失或已变化；请重新核对，或明确填写来源范围后再加入。'); return;
        }
        const placement = timelineAssetPlacement(latest.current.draft, origin.trackId, fresh);
        if (fresh.kind !== 'image' && range && placement !== null && range.out_ms - range.in_ms > latest.current.draft.timeline.duration_ms - placement) { setNotice('来源范围超出轨道剩余时间；请明确调整范围或时间线长度，没有截断输入。'); return; }
        if (latest.current.onApply(origin.trackId, fresh, fresh.kind === 'image' ? undefined : range)) {
          consumed.current = true; setDone(true); setNotice('已把核对的原素材版本加入本地草稿。可撤销；仍需明确保存，尚未渲染或导出。');
        }
      }
    } catch (reason) {
      if (alive.current && !consumed.current && origin.request === latest.current.request && latest.current.isCurrent()) {
        setAsset(undefined); setNotice(apiErrorView(reason, '素材读取失败；没有加入草稿。').message);
      }
    } finally { inFlight.current = false; if (alive.current) setPending(false); }
  }
  function editRange(field: 'start' | 'end', value: string) {
    if (inFlight.current || !latest.current.canEdit || !latest.current.isCurrent()) return;
    rangeRevision.current++; setAutomatic(false); if (field === 'start') setStart(value); else setEnd(value);
  }
  const range = parseTimelineAssetRange(start, end);
  const compatible = asset ? draft.timeline.tracks.filter(track => timelineAssetPlacement(draft, track.id, asset) !== null) : [];
  return <section aria-label="素材引用交接到时间线">
    <h3>素材引用交接到时间线</h3>
    <p>{request.reference.asset_id} · v{request.reference.version} · {request.reference.digest}</p>
    <p>只交接原素材引用。先读取当前元数据，再选择兼容且未锁定的轨道明确加入；加入前会再次核对同一版本。图片需要原时间线的扩展编辑版本 2。</p>
    <Button disabled={!canEdit || pending || done} onClick={() => void read(false)}>核对交接素材版本</Button>
    {asset && !done && <><p>{asset.filename} · {asset.kind} · {asset.size} 字节</p>
      {asset.kind !== 'image' && <><p>{duration === undefined ? '来源时长尚未由原输出回执验证。请明确填写来源范围；保存与渲染仍由原服务核对实际字节。' : `原已批准输出实测时长 ${duration} 毫秒；只采用此素材的精确版本回执。`}</p>
        <label>交接来源起点（毫秒）<input inputMode="numeric" value={start} disabled={!canEdit || pending} onChange={event => editRange('start', event.target.value)} /></label>
        <label>交接来源终点（毫秒）<input inputMode="numeric" value={end} disabled={!canEdit || pending} onChange={event => editRange('end', event.target.value)} /></label>
        {!validTimelineAssetRange(range, duration) && <p>请填写有效来源范围；不能超过已核对的实测时长。</p>}</>}
      <label>交接目标轨道<select value={trackId} disabled={!canEdit || pending} onChange={event => setTrackId(event.target.value)}>
        <option value="">选择轨道</option>{compatible.map(track => <option key={track.id} value={track.id}>{track.kind === 'AUDIO' ? '音频' : '视频'}轨道 {track.order + 1}</option>)}
      </select></label>
      {!compatible.length && <p>没有兼容的可用轨道。可通过下方原编辑器明确添加轨道或调整草稿。</p>}
      <Button disabled={!canEdit || pending || !compatible.some(track => track.id === trackId) || asset.kind !== 'image' && !validTimelineAssetRange(range, duration)} onClick={() => void read(true)}>明确加入原时间线草稿</Button>
    </>}
    {!done && <Button onClick={() => { consumed.current = true; setDone(true); setAsset(undefined); setNotice('已取消交接，没有修改时间线草稿。'); }}>取消素材交接</Button>}
    {pending && <StatusMessage>正在读取原素材元数据…</StatusMessage>}
    {notice && <StatusMessage>{notice}</StatusMessage>}
  </section>;
}
