import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { StudioAsset } from './studioClient';
import { checkedVideoReferencePreview, checkedVideoReferenceWindow, videoReferenceFrameBlob,
  type VideoReferenceFrame, type VideoReferencePreview, type VideoReferenceWindow } from './studioVideoReferenceContract';

type Props = {
  scope: object; assets: StudioAsset[]; blocked: boolean; canSave: boolean; isCurrent: () => boolean;
  onPreview: (source: StudioAsset, window: VideoReferenceWindow, signal: AbortSignal) => Promise<VideoReferencePreview>;
  onSave: (source: StudioAsset, review: VideoReferencePreview, selectedIndex: number, signal: AbortSignal) => Promise<void>;
};
type ReviewState = { token: object; pending?: 'preview' | 'save'; review?: VideoReferencePreview; selected?: number;
  loaded?: number[]; confirmed?: boolean; error?: string; saved?: boolean };
function failure(reason: unknown, saving: boolean): string {
  if (reason instanceof ApiError && reason.status === 409) return '来源版本或已预览图片已变化，请重新读取素材并明确预览。';
  if (reason instanceof ApiError && [401, 403].includes(reason.status)) return '当前会话无权继续，请重新核对项目与权限。';
  if (reason instanceof ApiError && reason.problem.code === 'STUDIO_RESPONSE_INVALID') return reason.message;
  return saving ? '保存结果未确认。请先核对原素材库；同一预览重试将沿用原请求，不会自动发送。'
    : '视频参考未能预览。请核对媒体工具、视频版本与区间；不支持旋转、非方形像素或非零起始时间的视频。';
}
export function StudioVideoReferencePanel(props: Props) {
  const [selected, setSelected] = useState(''), [inText, setInText] = useState('0'), [outText, setOutText] = useState('1000'), [countText, setCountText] = useState('4');
  const [state, setState] = useState<ReviewState>();
  const alive = useRef(true), live = useRef(props); live.current = props;
  const active = useRef<AbortController>();
  const asset = props.assets.find(row => row.id === selected && row.kind === 'video' && !row.deleted_at);
  const key = JSON.stringify([selected, asset?.version, asset?.sha256, asset?.novel_id, asset?.branch_id ?? null, asset?.size, inText, outText, countText, props.canSave, props.blocked && !(active.current && state?.pending === 'save'), props.isCurrent()]);
  const owner = useRef({ scope: props.scope, key, token: {} });
  if (owner.current.scope !== props.scope || owner.current.key !== key) {
    active.current?.abort(); active.current = undefined;
    owner.current = { scope: props.scope, key, token: {} };
  }
  const token = owner.current.token, visible = state?.token === token ? state : undefined;
  const current = (saving = false) => alive.current && owner.current.token === token && live.current.scope === props.scope
    && live.current.isCurrent() && (saving || !live.current.blocked);
  useEffect(() => { alive.current = true; return () => { alive.current = false; active.current?.abort(); }; }, []);
  useLayoutEffect(() => { setSelected(''); setInText('0'); setOutText('1000'); setCountText('4'); setState(undefined); }, [props.scope]);
  // Event-time retirement catches A -> B -> A even if React batches both changes.
  function retire() { active.current?.abort(); active.current = undefined; owner.current = { ...owner.current, token: {} }; setState(undefined); }
  function change(setter: (value: string) => void, value: string) { if (!live.current.isCurrent() || visible?.pending === 'save') return; retire(); setter(value); }
  function windowInput(): VideoReferenceWindow | undefined {
    if (![inText, outText, countText].every(text => /^\d+$/.test(text))) return undefined;
    try { return checkedVideoReferenceWindow({ in_ms: Number(inText), out_ms: Number(outText), sample_count: Number(countText) }); } catch { return undefined; }
  }
  const window = windowInput();
  async function preview() {
    if (!current() || active.current || !asset || !window) return;
    const source = structuredClone(asset), input = { ...window }, abort = new AbortController(); active.current = abort;
    setState({ token, pending: 'preview' });
    try {
      const response = await props.onPreview(source, input, abort.signal);
      if (!current() || abort.signal.aborted) return;
      const review = await checkedVideoReferencePreview(response, source, input);
      if (current() && !abort.signal.aborted) setState({ token, review, loaded: [] });
    } catch (reason) { if (current() && !abort.signal.aborted) setState({ token, error: failure(reason, false) }); }
    finally { if (active.current === abort) { active.current = undefined; if (current()) setState(previous => previous?.token === token ? { ...previous, pending: undefined } : previous); } }
  }
  async function save() {
    if (!current() || active.current || !live.current.canSave || !asset || !visible?.review || visible.selected === undefined
      || !visible.confirmed || !visible.loaded?.includes(visible.selected)) return;
    const review = structuredClone(visible.review), source = structuredClone(asset), selectedIndex = visible.selected;
    const abort = new AbortController(); active.current = abort; setState({ ...visible, pending: 'save', error: undefined });
    try {
      await props.onSave(source, review, selectedIndex, abort.signal);
      if (current(true) && !abort.signal.aborted) setState({ token, saved: true });
    } catch (reason) { if (current(true) && !abort.signal.aborted) setState({ ...visible, confirmed: false, error: failure(reason, true) }); }
    finally { if (active.current === abort) { active.current = undefined; if (current(true)) setState(previous => previous?.token === token ? { ...previous, pending: undefined } : previous); } }
  }
  if (!props.isCurrent()) return null;
  const videos = props.assets.filter(row => row.kind === 'video' && !row.deleted_at);
  return <Panel title="视频参考 · 时间采样帧">
    <p>从已保存视频明确预览实际采样帧：原视频最多 60 秒、25 MiB；整数区间 [起点, 终点) 最多 10 秒，采样 1 至 8 帧。显示原视频时间戳，不判断语义关键帧或动作。</p>
    {!videos.length && <EmptyState title="还没有可选视频" detail="先通过下方原素材库导入视频，再明确选择其版本。" />}
    <label>视频参考原素材<select value={selected} disabled={props.blocked || visible?.pending === 'save'} onChange={event => change(setSelected, event.target.value)}>
      <option value="">明确选择已保存视频版本</option>{videos.map(row => <option key={row.id} value={row.id}>{row.filename} · v{row.version}</option>)}
    </select></label>
    <label>采样起点（毫秒，包含）<input type="number" min={0} max={59999} step={1} value={inText} disabled={props.blocked || visible?.pending === 'save'} onChange={event => change(setInText, event.target.value)} /></label>
    <label>采样终点（毫秒，不包含）<input type="number" min={1} max={60000} step={1} value={outText} disabled={props.blocked || visible?.pending === 'save'} onChange={event => change(setOutText, event.target.value)} /></label>
    <label>采样帧数<input type="number" min={1} max={8} step={1} value={countText} disabled={props.blocked || visible?.pending === 'save'} onChange={event => change(setCountText, event.target.value)} /></label>
    {!window && <StatusMessage tone="warning">请填写整数毫秒区间，终点大于起点且区间不超过 10000 毫秒，帧数为 1 至 8。</StatusMessage>}
    <Button disabled={props.blocked || !!visible?.pending || !asset || !window} onClick={() => void preview()}>明确预览视频采样帧</Button>
    {(visible?.review || visible?.pending === 'preview') && <Button disabled={visible.pending === 'save'} onClick={retire}>关闭采样预览</Button>}
    {visible?.pending && <StatusMessage>{visible.pending === 'save' ? '正在保存已确认的采样帧…' : '正在读取原视频并校验实际采样帧…'}</StatusMessage>}
    {visible?.review && <section aria-label="已校验的视频采样帧">
      <p>原素材 {visible.review.source.id} · v{visible.review.source.version} · 时长 {visible.review.media.duration_ms} 毫秒。取各目标时刻起的第一帧；短区间可能重复同一帧。每帧最长边不超过 320 像素。保存的就是这张已预览的低分辨率图片，不提取全分辨率图片，也不放大原图。</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)' }}>{visible.review.frames.map(frame => <figure key={`${visible.review!.preview_digest}:${frame.index}`} style={{ margin: 0 }}>
        <FramePreview frame={frame} loaded={ok => {
          if (!current(true)) return;
          setState(previous => previous?.token !== token ? previous : { ...previous,
            loaded: ok ? [...new Set([...(previous.loaded ?? []), frame.index])] : previous.loaded?.filter(index => index !== frame.index),
            confirmed: ok ? previous.confirmed : false, error: ok ? previous.error : '采样图片显示失败，请关闭后重新预览。' });
        }} />
        <figcaption>第 {frame.index + 1} 帧 · 目标 {frame.requested_ms} 毫秒<br />实际 {frame.time_ms.num}/{frame.time_ms.den} 毫秒（约 {(frame.time_ms.num / frame.time_ms.den).toFixed(3)}）<br />原帧 #{frame.source_frame_index} · PTS {frame.pts} · {frame.width} × {frame.height} 像素</figcaption>
        <Button aria-pressed={visible.selected === frame.index} disabled={props.blocked || !!visible.pending || !visible.loaded?.includes(frame.index)} onClick={() => {
          if (current() && !active.current) setState({ ...visible, selected: frame.index, confirmed: false, error: undefined });
        }}>选择第 {frame.index + 1} 帧</Button>
      </figure>)}</div>
      <label><input type="checkbox" checked={!!visible.confirmed} disabled={props.blocked || !props.canSave || !!visible.pending || visible.selected === undefined || !visible.loaded?.includes(visible.selected)}
        onChange={event => { if (current() && !active.current && live.current.canSave) setState({ ...visible, confirmed: event.target.checked }); }} />已查看所选采样帧，确认保存为派生图片素材</label>
      <Button disabled={props.blocked || !props.canSave || !!visible.pending || !visible.confirmed || visible.selected === undefined || !visible.loaded?.includes(visible.selected)} onClick={() => void save()}>保存所选参考帧到素材库</Button>
      {!props.canSave && <p>当前为只读权限，可预览，不能保存派生素材。</p>}
      <p>保存保留原视频版本和精确帧时间；不会调用模型。保存后可在原素材库另行选择图片，通过已有图片到视频入口使用。</p>
    </section>}
    {visible?.error && <StatusMessage tone="warning">{visible.error}</StatusMessage>}
    {visible?.saved && <StatusMessage>所选帧已保存到原素材库。图片到视频需在现有入口另行明确操作。</StatusMessage>}
  </Panel>;
}
function FramePreview({ frame, loaded }: { frame: VideoReferenceFrame; loaded: (ok: boolean) => void }) {
  const [url, setUrl] = useState<string>();
  useEffect(() => { const next = URL.createObjectURL(videoReferenceFrameBlob(frame)); setUrl(next); return () => URL.revokeObjectURL(next); }, [frame]);
  return url ? <img src={url} alt={`已校验采样帧 ${frame.index + 1}`} width={frame.width} height={frame.height} onLoad={() => loaded(true)} onError={() => loaded(false)} /> : null;
}
