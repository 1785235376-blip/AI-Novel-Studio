import { useEffect, useRef } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { StudioTimelinePlaybackOptions } from './StudioTimelinePlaybackOptions';
import type { StudioTimelinePlaybackController } from './useStudioTimelinePlayback';

/** Replaceable playback view; authority, cache and receipts stay in controller. */
export function StudioTimelinePlaybackPanel({ controller: c }: { controller: StudioTimelinePlaybackController }) {
  const media = useRef<HTMLMediaElement | null>(null);
  useEffect(() => { const previous = media.current; return () => { previous?.pause(); }; }, [c.visible?.url]);
  if (!c.available) return <StatusMessage tone="info">当前客户端尚未提供原时间线播放缓存入口。</StatusMessage>;
  const seek = (milliseconds: number) => { const element = media.current, entry = c.visible;
    if (!element || !entry || element.currentSrc !== entry.url || !Number.isFinite(milliseconds)) return;
    element.currentTime = Math.max(0, Math.min(milliseconds, entry.durationMs)) / 1000; c.reportPosition(entry.key, element.currentTime); };
  return <section aria-label="时间线播放缓存"><h3>播放缓存</h3>
    <p>先保存时间线，再读取缓存方案。首次明确生成经原本地渲染任务；同一版本、来源与编码器复用原私有结果。</p>
    {c.error && <StatusMessage tone="error">{c.error}</StatusMessage>}{c.notice && <StatusMessage tone="info">{c.notice}</StatusMessage>}
    {c.pending && <StatusMessage>正在处理播放缓存：{c.pending}。</StatusMessage>}
    <Button disabled={!c.canOperate} loading={c.pending === 'PREVIEW'} onClick={() => void c.previewPlayback()}>读取此保存版本的播放方案</Button>
    {c.preview && <><p>{c.preview.export_preview.export_profile.preset === 'AUDIO_WAV_PCM16' ? 'PCM16 WAV · 48 kHz · 立体声' : 'H.264 / AAC · 原画布尺寸'} · 原 v{c.preview.export_preview.timeline_snapshot.version} · {c.preview.job?.status ?? '尚未生成'}</p>
      <details><summary>原缓存任务与方案摘要</summary><p><code>{c.preview.job_id}</code></p><p><code>{c.preview.playback_digest}</code></p></details>
      <label><input type="checkbox" disabled={!c.canOperate} checked={c.confirmed} onChange={event => c.setConfirmed(event.currentTarget.checked)} />已核对保存版本、来源和本次播放方案</label>
      {!c.preview.job && <Button disabled={!c.canOperate || !c.confirmed} loading={c.pending === 'BUILD'} onClick={() => void c.buildPlayback()}>明确生成此版本的播放缓存</Button>}
      {c.preview.job?.output_candidate && <Button disabled={!c.canOperate || !c.confirmed || !['SUCCEEDED', 'AWAITING_REVIEW', 'APPROVED'].includes(c.preview.job.status)}
        loading={c.pending === 'BLOB'} onClick={() => void c.loadPlayback()}>核对候选并载入播放</Button>}
      <Button disabled={!!c.pending && !c.canReadDuringBuild || !!c.auxiliary} loading={c.auxiliary === 'READ'} onClick={() => void c.readOriginal()}>读取原缓存任务回执</Button>
      {c.preview.job && <p>恢复或审核继续使用上方原媒体任务入口；播放缓存不自动批准或重复执行。</p>}
    </>}
    {c.unknown && <StatusMessage tone="warning">原请求 {c.unknown.preview.request_id} 结果不明，保留 UNKNOWN；只读回执，不重新编码。</StatusMessage>}
    {c.unknown && <Button disabled={!c.canReadDuringBuild} loading={c.auxiliary === 'READ'} onClick={() => void c.readOriginal()}>核对本次请求的原缓存任务</Button>}
    <Button disabled={!c.canCancel} loading={c.auxiliary === 'CANCEL'} onClick={() => void c.cancelOriginal()}>明确取消此原缓存任务</Button>
    {c.visible && <>{c.visible.mediaType === 'audio/wav' ? <audio ref={element => { media.current = element; }} key={c.visible.url} src={c.visible.url} controls preload="metadata" aria-label="已核验的时间线缓存音频"
      onTimeUpdate={event => { if (event.currentTarget.currentSrc === c.visible?.url) c.reportPosition(c.visible.key, event.currentTarget.currentTime); }}
      onError={() => c.visible && c.reportMediaError(c.visible.key)} /> : <video ref={element => { media.current = element; }} key={c.visible.url} src={c.visible.url} controls preload="metadata" playsInline width="640" style={{ maxWidth: '100%' }} aria-label="已核验的时间线缓存视频"
      onTimeUpdate={event => { if (event.currentTarget.currentSrc === c.visible?.url) c.reportPosition(c.visible.key, event.currentTarget.currentTime); }}
      onError={() => c.visible && c.reportMediaError(c.visible.key)} />}
      <StudioTimelinePlaybackOptions key={JSON.stringify([c.visible.key, c.visible.url, c.visible.jobVersion])}
        media={media} url={c.visible.url} identity={JSON.stringify([c.visible.key, c.visible.digest, c.visible.jobVersion])} />
      <label>时间定位<input type="range" min={0} max={c.visible.durationMs} step={1} value={c.positionMs} onChange={event => seek(Number(event.currentTarget.value))} /></label>
      <p>{(c.positionMs / 1000).toFixed(3)} / {(c.visible.durationMs / 1000).toFixed(3)} 秒 · {c.visible.bytes} 字节</p>
      <Button onClick={() => seek(Math.max(0, c.positionMs - 5000))}>后退 5 秒</Button><Button onClick={() => seek(c.positionMs + 5000)}>前进 5 秒</Button>
    </>}
    <Button disabled={!!c.pending || !!c.unknown || !!c.auxiliary} onClick={c.clear}>清除本会话播放缓存</Button>
    <p>浏览器缓存最多 2 项／50 MiB。清除仅撤销本地 Blob，原任务、私有候选和证据保留。关闭网络请求不代表取消渲染。</p>
  </section>;
}
