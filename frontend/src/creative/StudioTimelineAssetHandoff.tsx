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
export function appendTimelineAsset(draft: StudioTimelineDraft, trackId: string, asset: StudioAsset): void {
  const placement = timelineAssetPlacement(draft, trackId, asset);
  if (placement === null) return;
  const track = draft.timeline.tracks.find(row => row.id === trackId)!;
  track.clips.push({ id: crypto.randomUUID(), source_snapshot: { id: asset.id, kind: 'ASSET', asset_kind: asset.kind as 'image' | 'video' | 'audio', version: asset.version, digest: asset.sha256 },
    start_ms: placement, in_ms: 0, out_ms: Math.min(1000, draft.timeline.duration_ms - placement),
    ...(track.kind === 'VIDEO' ? { x: 0, y: 0, width: draft.timeline.width, height: draft.timeline.height } : {}),
    ...(draft.timeline.schema_version === 2 ? { speed_num: 1, speed_den: 1, muted: false, gain_db: 0, fade_in_ms: 0, fade_out_ms: 0,
      ...(track.kind === 'VIDEO' ? { opacity: 1, include_audio: false } : {}) } : {}) });
}

export function StudioTimelineAssetHandoff({ request, draft, canEdit, isCurrent, getRevision, onApply }: {
  request: TimelineAssetHandoff; draft: StudioTimelineDraft; canEdit: boolean; isCurrent: () => boolean;
  getRevision: () => string;
  onApply: (trackId: string, asset: StudioAsset) => boolean;
}) {
  const [asset, setAsset] = useState<StudioAsset>(), [trackId, setTrackId] = useState('');
  const [pending, setPending] = useState(false), [notice, setNotice] = useState(''), [done, setDone] = useState(false);
  const alive = useRef(true), inFlight = useRef(false), consumed = useRef(false);
  const latest = useRef({ request, draft, canEdit, isCurrent, getRevision, onApply, trackId });
  latest.current = { request, draft, canEdit, isCurrent, getRevision, onApply, trackId };
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  async function read(apply: boolean) {
    const origin = latest.current;
    if (inFlight.current || consumed.current || !origin.isCurrent() || !origin.canEdit) return;
    const inputKey = timelineInputKey(origin.draft), revision = origin.getRevision();
    inFlight.current = true; setPending(true); setNotice('');
    try {
      const fresh = await origin.request.readAsset();
      if (!alive.current || consumed.current || origin.request !== latest.current.request || !latest.current.isCurrent()) return;
      if (!exactHandoffAsset(fresh, origin.request.reference)) { setAsset(undefined); setNotice('来源已变化或不可用；不会改用最新版本。请返回素材工作区重新选择。'); return; }
      setAsset(fresh);
      if (apply) {
        if (origin.getRevision() !== revision || !latest.current.canEdit || latest.current.trackId !== origin.trackId || timelineInputKey(latest.current.draft) !== inputKey
          || timelineAssetPlacement(latest.current.draft, origin.trackId, fresh) === null) {
          setNotice('草稿、轨道或编辑状态已变化；请重新核对后明确加入。'); return;
        }
        if (latest.current.onApply(origin.trackId, fresh)) {
          consumed.current = true; setDone(true); setNotice('已把核对的原素材版本加入本地草稿。可撤销；仍需明确保存，尚未渲染或导出。');
        }
      }
    } catch (reason) {
      if (alive.current && !consumed.current && origin.request === latest.current.request && latest.current.isCurrent()) {
        setAsset(undefined); setNotice(apiErrorView(reason, '素材读取失败；没有加入草稿。').message);
      }
    } finally { inFlight.current = false; if (alive.current) setPending(false); }
  }
  const compatible = asset ? draft.timeline.tracks.filter(track => timelineAssetPlacement(draft, track.id, asset) !== null) : [];
  return <section aria-label="素材引用交接到时间线">
    <h3>素材引用交接到时间线</h3>
    <p>{request.reference.asset_id} · v{request.reference.version} · {request.reference.digest}</p>
    <p>只交接原素材引用。先读取当前元数据，再选择兼容且未锁定的轨道明确加入；加入前会再次核对同一版本。图片需要原时间线的扩展编辑版本 2。</p>
    <Button disabled={!canEdit || pending || done} onClick={() => void read(false)}>核对交接素材版本</Button>
    {asset && !done && <><p>{asset.filename} · {asset.kind} · {asset.size} 字节</p>
      <label>交接目标轨道<select value={trackId} disabled={!canEdit || pending} onChange={event => setTrackId(event.target.value)}>
        <option value="">选择轨道</option>{compatible.map(track => <option key={track.id} value={track.id}>{track.kind === 'AUDIO' ? '音频' : '视频'}轨道 {track.order + 1}</option>)}
      </select></label>
      {!compatible.length && <p>没有兼容的可用轨道。可通过下方原编辑器明确添加轨道或调整草稿。</p>}
      <Button disabled={!canEdit || pending || !compatible.some(track => track.id === trackId)} onClick={() => void read(true)}>明确加入原时间线草稿</Button>
    </>}
    {!done && <Button onClick={() => { consumed.current = true; setDone(true); setAsset(undefined); setNotice('已取消交接，没有修改时间线草稿。'); }}>取消素材交接</Button>}
    {pending && <StatusMessage>正在读取原素材元数据…</StatusMessage>}
    {notice && <StatusMessage>{notice}</StatusMessage>}
  </section>;
}
