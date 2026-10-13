import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { StudioAsset } from './studioClient';
import type { StudioTimelineRow } from './studioTimelineTypes';
import type { useStudioTimelineSourceEdit } from './useStudioTimelineSourceEdit';
type Controller = ReturnType<typeof useStudioTimelineSourceEdit>;
/** Replaceable source Inspector over the original Timeline edit controller. */
export function StudioTimelineSourceEditPanel({ controller: c, source, assets }: { controller: Controller; source?: StudioTimelineRow; assets: StudioAsset[] }) {
  if (!c.available || !source) return null; const intent = c.intent, asset = assets.find(row => row.id === intent.asset_id), track = source.timeline.tracks.find(row => row.id === intent.track_id);
  const tracks = source.timeline.tracks.filter(row => asset?.kind === 'audio' ? row.kind === 'AUDIO' : row.kind === 'VIDEO');
  return <section aria-label="正式素材时间线操作"><details><summary>正式素材加入与替换</summary><p>基于已保存 v{source.version}。新轨道和首片段在同一批次保存；替换保留原片段摆放与其他作者参数。</p>
    {c.error && <StatusMessage tone="error">{c.error}</StatusMessage>}{c.notice && <StatusMessage>{c.notice}</StatusMessage>}
    <fieldset disabled={!c.canPrepare}><legend>正式素材来源</legend><label>加入或替换方式<select value={intent.mode} onChange={event => c.change({ mode: event.target.value as typeof intent.mode, track_id: '', clip_id: '' })}><option value="NEW_TRACK">新轨道与首个片段</option><option value="INSERT">加入已有轨道</option><option value="REPLACE">替换原片段来源</option></select></label>
      <label>当前正式素材<select value={intent.asset_id} onChange={event => c.change({ asset_id: event.target.value, track_id: '', clip_id: '', include_audio: false })}><option value="">明确选择当前版本</option>{assets.filter(row => !row.deleted_at && ['video', 'audio', 'image'].includes(row.kind)).map(row => <option key={row.id} value={row.id}>{row.filename} · v{row.version} · {row.kind}</option>)}</select></label>
      {intent.mode !== 'NEW_TRACK' && <label>原目标轨道<select value={intent.track_id} onChange={event => c.change({ track_id: event.target.value, clip_id: '' })}><option value="">选择素材类型兼容的轨道</option>{tracks.map(row => <option key={row.id} value={row.id} disabled={row.locked}>{row.kind === 'AUDIO' ? '音频' : '画面'} {row.order + 1}{row.locked ? ' · 已锁定' : ''}</option>)}</select></label>}
      {intent.mode === 'REPLACE' && <label>原目标片段<select value={intent.clip_id} onChange={event => c.change({ clip_id: event.target.value })}><option value="">明确选择原片段</option>{track?.clips.map(clip => <option key={clip.id} value={clip.id}>{clip.id} · {clip.start_ms} 毫秒</option>)}</select></label>}
      {intent.mode !== 'REPLACE' && <label>放入时间线（毫秒）<input type="number" min={0} max={source.timeline.duration_ms - 1} value={Number.isFinite(intent.start_ms) ? intent.start_ms : ''} onChange={event => c.change({ start_ms: event.target.value === '' ? Number.NaN : Number(event.target.value) })} /></label>}
      <label>正式素材起点（毫秒）<input type="number" min={0} max={35999999} value={Number.isFinite(intent.in_ms) ? intent.in_ms : ''} onChange={event => c.change({ in_ms: event.target.value === '' ? Number.NaN : Number(event.target.value) })} /></label>
      <label>正式素材终点（毫秒）<input type="number" min={1} max={36000000} value={Number.isFinite(intent.out_ms) ? intent.out_ms : ''} onChange={event => c.change({ out_ms: event.target.value === '' ? Number.NaN : Number(event.target.value) })} /></label>
      {asset?.kind === 'video' && source.timeline.schema_version === 2 && <label><input type="checkbox" checked={intent.include_audio} onChange={event => c.change({ include_audio: event.target.checked })} />明确采用视频原音轨（来源须确有音轨）</label>}
      <Button disabled={!intent.asset_id} onClick={c.prepare}>核对正式素材操作</Button></fieldset>
    {c.preview && <section aria-label="正式素材操作预览"><Badge>待明确保存</Badge><p>{c.preview.tracks.length} 条轨道 · {c.preview.tracks.reduce((sum, row) => sum + row.clips.length, 0)} 个片段；绑定当前正式素材版本。</p><details><summary>原编辑批次与来源摘要</summary><pre>{JSON.stringify(c.prepared?.operations, null, 2)}</pre></details>
      <label><input type="checkbox" checked={c.confirmed} disabled={!c.canPrepare} onChange={event => c.confirm(event.target.checked)} />已核对当前时间线、正式素材版本与本次片段范围</label><Button disabled={!c.canExecute} loading={c.pending === 'EDIT'} onClick={() => void c.execute()}>明确保存正式素材操作</Button></section>}
    {c.unknown && <section aria-label="原编辑回执待核对"><StatusMessage tone="warning">编辑结果尚未确认。仅原当前编辑回执、请求身份与完整片段效果一致时解锁；不会重新发送。</StatusMessage><details><summary>待核对原请求</summary><code>{c.unknown.body.request_id}</code></details><Button disabled={!!c.pending} loading={c.pending === 'CHECK'} onClick={() => void c.check()}>只读核对原编辑回执</Button></section>}
    <Button disabled={c.locked} onClick={c.clear}>清空本次素材选择</Button></details></section>;
}
