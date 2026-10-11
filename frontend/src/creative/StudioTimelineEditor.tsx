import { useEffect, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { TIMELINE_LIMITS, timelineSourceState, type StudioTimelineClip, type StudioTimelineDraft, type StudioTimelineTrack } from './studioTimelineTypes';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
export type { StudioTimelineEditorProps } from './useStudioTimelineEditor';

const numeric = (value: string) => value === '' ? Number.NaN : Number(value);
const displayNumber = (value: number) => Number.isFinite(value) ? value : '';
const seconds = (value: number) => Number.isFinite(value) ? `${(value / 1000).toFixed(3)} 秒` : '时间无效';
const sourceLabel = { CURRENT: '当前素材版本', STALE: '素材已变化，请重新选择', UNAVAILABLE: '素材不可用或无权访问' };

function NumberField({ label, value, onChange, min = 0, max, step = 1 }: { label: string; value: number; onChange: (value: number) => void; min?: number; max?: number; step?: number }) {
  return <label>{label}<input type="number" min={min} max={max} step={step} value={displayNumber(value)} onChange={event => onChange(numeric(event.currentTarget.value))} /></label>;
}

/** Shared-shell form only. Opus can replace this view while retaining the headless controller. */
export function StudioTimelineEditor(props: StudioTimelineEditorProps) {
  const c = useStudioTimelineEditor(props), [picked, setPicked] = useState<Record<string, string>>({});
  useEffect(() => setPicked({}), [props.client]);
  const draft = c.draft;
  if (!draft) return <Panel title="时间线"><EmptyState title="当前时间线入口不可用" detail="请重新核对项目、身份与原可信会话。旧输入和回执不会跨身份显示。" /></Panel>;
  const changeTrack = (id: string, work: (track: StudioTimelineTrack, draft: StudioTimelineDraft) => void) => c.change(input => {
    const track = input.timeline.tracks.find(row => row.id === id); if (track) work(track, input);
  });
  const changeClip = (trackId: string, clipId: string, work: (clip: StudioTimelineClip) => void) => changeTrack(trackId, track => {
    const clip = track.clips.find(row => row.id === clipId); if (clip) work(clip);
  });
  const addTrack = (kind: 'VIDEO' | 'AUDIO') => c.change(input => {
    if (input.timeline.tracks.length >= 8 || input.timeline.tracks.filter(track => track.kind === kind).length >= 4) return;
    input.timeline.tracks.push({ id: crypto.randomUUID(), kind, order: input.timeline.tracks.length, muted: false, gain_db: 0, clips: [] });
  });
  const moveTrack = (id: string, direction: -1 | 1) => c.change(input => {
    const tracks = input.timeline.tracks, index = tracks.findIndex(track => track.id === id), target = index + direction;
    if (index < 0 || target < 0 || target >= tracks.length) return;
    [tracks[index], tracks[target]] = [tracks[target], tracks[index]]; tracks.forEach((track, order) => { track.order = order; });
  });
  const addClip = (trackId: string) => changeTrack(trackId, (track, input) => {
    const kind = track.kind === 'VIDEO' ? 'video' : 'audio', asset = props.assets.find(row => row.id === picked[trackId] && row.kind === kind && !row.deleted_at);
    if (!asset || input.timeline.tracks.reduce((total, row) => total + row.clips.length, 0) >= TIMELINE_LIMITS.clips) return;
    const placement = track.clips.reduce((latest, clip) => Math.max(latest, clip.start_ms + clip.out_ms - clip.in_ms), 0);
    if (!Number.isFinite(placement) || placement >= input.timeline.duration_ms) return;
    track.clips.push({ id: crypto.randomUUID(), source_snapshot: { id: asset.id, kind: 'ASSET', asset_kind: kind, version: asset.version, digest: asset.sha256 },
      start_ms: placement, in_ms: 0, out_ms: Math.min(1000, input.timeline.duration_ms - placement),
      ...(kind === 'video' ? { x: 0, y: 0, width: input.timeline.width, height: input.timeline.height } : {}) });
  });
  const locked = !c.canEdit || props.busy;
  const readLocked = c.denied || props.busy || !!c.pending;
  const clipsCount = draft.timeline.tracks.reduce((sum, track) => sum + track.clips.length, 0);
  return <Panel title="多轨时间线" aria-label="Studio 多轨时间线编辑器" actions={<Button loading={c.pending === 'LIST'} disabled={readLocked} onClick={() => void c.reload()}>刷新时间线列表</Button>}>
    <p>选择已有视频和音频素材，设定裁剪与摆放。视频按轨道顺序叠放，音频轨道混音；视频自身声音不自动加入。总长最多十分钟，产物仍须在制作任务中预览和人工审核。</p>
    <label>读取已保存时间线<select disabled={readLocked} value={c.candidate?.id ?? c.base?.id ?? ''} onChange={event => { if (event.currentTarget.value) void c.checkServer(event.currentTarget.value); }}>
      <option value="">选择时间线后核对</option>{c.rows.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}
    </select></label>
    <Button disabled={readLocked} onClick={() => void c.checkServer()}>核对当前服务端版本</Button>
    <Button disabled={locked || !!c.attempt && c.attempt.state === 'UNKNOWN' || c.inputDirty && !c.discardConfirmed} onClick={c.createNew}>新建时间线</Button>
    {!c.rows.length && !c.pending && <p>尚无已读取的时间线。可以先添加轨道与素材，再明确保存。</p>}
    {c.pending && <StatusMessage>{({ LIST: '正在读取时间线列表…', GET: '正在读取服务端版本…', SAVE: '正在保存时间线…', RENDER: '正在执行原本地渲染任务…', JOB: '正在读取原渲染任务回执…' })[c.pending]}</StatusMessage>}
    {c.failure && <StatusMessage tone="warning">{c.failure === 'CONFLICT' ? '服务端版本已变化。输入保留，请读取并核对版本后人工采用或保留草稿。' : '保存结果不确定，不能直接重复保存。请读取服务端版本；新建请求没有已知标识时，刷新列表并选择候选。'}</StatusMessage>}
    {c.error && <StatusMessage tone="error">{c.error}</StatusMessage>}{c.notice && <StatusMessage>{c.notice}</StatusMessage>}
    {c.candidate && <section aria-label="核对服务端时间线">
      <h3>{c.candidate.title} · v{c.candidate.version}</h3><p>{seconds(c.candidate.timeline.duration_ms)} · {c.candidate.timeline.width} × {c.candidate.timeline.height} · {c.candidate.timeline.fps} fps · {c.candidate.timeline.tracks.length} 条轨道</p>
      <ul>{c.candidate.timeline.tracks.map(track => <li key={track.id}>{track.kind === 'VIDEO' ? '视频' : '音频'}轨道 {track.order + 1} · {track.clips.length} 个片段 · {track.muted ? '隐藏或静音' : '参与渲染'}{track.kind === 'AUDIO' ? ` · ${track.gain_db} dB` : ''}
        <ul>{track.clips.map(clip => <li key={clip.id}>{props.assets.find(asset => asset.id === clip.source_snapshot.id)?.filename ?? '素材不可用'} · v{clip.source_snapshot.version} · 放入 {seconds(clip.start_ms)} · 裁剪 {seconds(clip.in_ms)} 至 {seconds(clip.out_ms)}</li>)}</ul>
      </li>)}</ul>
      <p>字幕：{c.candidate.timeline.captions.map(cue => `${seconds(cue.start_ms)}—${seconds(cue.end_ms)} ${cue.text}`).join('；') || '无'}</p>
      <details><summary>版本绑定摘要</summary><code>{c.candidate.timeline_digest}</code></details>
      <p>读取的候选不证明原保存或渲染请求已完成；采用服务端值会替换当前编辑内容。</p>
      <label><input type="checkbox" checked={c.adoptConfirmed} disabled={readLocked} onChange={event => c.setAdoptConfirmed(event.currentTarget.checked)} />已核对服务端内容与本地输入，确认以下选择</label>
      <Button disabled={readLocked || !c.adoptConfirmed} onClick={() => c.adoptCandidate(false)}>采用服务端时间线</Button>
      <Button disabled={readLocked || !c.adoptConfirmed || !props.canMutate} onClick={() => c.adoptCandidate(true)}>保留草稿并基于此版本编辑</Button>
    </section>}
    <fieldset disabled={locked}><legend>时间线参数</legend>
      <label>名称<input maxLength={240} value={draft.title} onChange={event => { const title = event.currentTarget.value; c.change(input => { input.title = title; }); }} /></label>
      <NumberField label="总长（毫秒）" value={draft.timeline.duration_ms} min={1} max={600000} onChange={value => c.change(input => { input.timeline.duration_ms = value; })} />
      <NumberField label="画面宽度" value={draft.timeline.width} min={16} max={1920} step={2} onChange={value => c.change(input => { input.timeline.width = value; })} />
      <NumberField label="画面高度" value={draft.timeline.height} min={16} max={1080} step={2} onChange={value => c.change(input => { input.timeline.height = value; })} />
      <NumberField label="帧率" value={draft.timeline.fps} min={1} max={60} onChange={value => c.change(input => { input.timeline.fps = value; })} />
      <p>1000 毫秒为一秒。更改画面大小后请核对各视频片段的位置与尺寸，素材实际时长由原服务校验。</p>
      <Button disabled={draft.timeline.tracks.length >= 8 || draft.timeline.tracks.filter(track => track.kind === 'VIDEO').length >= 4} onClick={() => addTrack('VIDEO')}>添加视频轨道</Button>
      <Button disabled={draft.timeline.tracks.length >= 8 || draft.timeline.tracks.filter(track => track.kind === 'AUDIO').length >= 4} onClick={() => addTrack('AUDIO')}>添加音频轨道</Button>
    </fieldset>
    {draft.timeline.tracks.map((track, index) => <fieldset key={track.id} disabled={locked}><legend>{track.kind === 'VIDEO' ? '视频' : '音频'}轨道 {index + 1}</legend>
      <p>{track.kind === 'VIDEO' ? '靠后的轨道覆盖前面的画面，同轨道片段不能重叠。' : '参与轨道按摆放时间混音，未放入声音的区间保留静音。'}</p>
      <label><input type="checkbox" checked={track.muted} onChange={event => { const muted = event.currentTarget.checked; changeTrack(track.id, row => { row.muted = muted; }); }} />{track.kind === 'VIDEO' ? '隐藏整条轨道' : '整条轨道静音'}</label>
      {track.kind === 'AUDIO' && <NumberField label="轨道音量（dB）" value={track.gain_db} min={-60} max={12} step={0.1} onChange={value => changeTrack(track.id, row => { row.gain_db = value; })} />}
      <Button disabled={index === 0} onClick={() => moveTrack(track.id, -1)}>轨道前移</Button><Button disabled={index === draft.timeline.tracks.length - 1} onClick={() => moveTrack(track.id, 1)}>轨道后移</Button>
      <Button variant="danger" onClick={() => c.change(input => { input.timeline.tracks = input.timeline.tracks.filter(row => row.id !== track.id); input.timeline.tracks.forEach((row, order) => { row.order = order; }); })}>移除轨道及片段</Button>
      <label>选择已有{track.kind === 'VIDEO' ? '视频' : '音频'}素材<select value={picked[track.id] ?? ''} onChange={event => { const value = event.currentTarget.value; setPicked(values => ({ ...values, [track.id]: value })); }}>
        <option value="">请选择素材</option>{props.assets.filter(asset => asset.kind === (track.kind === 'VIDEO' ? 'video' : 'audio') && !asset.deleted_at).map(asset => <option key={asset.id} value={asset.id}>{asset.filename} · v{asset.version}</option>)}
      </select></label>
      <Button disabled={!picked[track.id] || clipsCount >= 30} onClick={() => addClip(track.id)}>将所选素材加入轨道</Button>
      {!track.clips.length && <p>此轨道尚无片段，保存前请加入素材或移除此轨道。</p>}
      {track.clips.map((clip, clipIndex) => <section key={clip.id} aria-label={`轨道 ${index + 1} 片段 ${clipIndex + 1}`}>
        <h4>{props.assets.find(asset => asset.id === clip.source_snapshot.id)?.filename ?? '素材不可用'} · 片段 {clipIndex + 1}</h4>
        <Badge tone={timelineSourceState(clip.source_snapshot, props.assets) === 'CURRENT' ? 'neutral' : 'warning'}>{sourceLabel[timelineSourceState(clip.source_snapshot, props.assets)]} · v{clip.source_snapshot.version}</Badge>
        <label>重新绑定当前素材版本<select value={props.assets.some(asset => asset.id === clip.source_snapshot.id && !asset.deleted_at) ? clip.source_snapshot.id : ''} onChange={event => {
          const asset = props.assets.find(row => row.id === event.currentTarget.value && row.kind === (track.kind === 'VIDEO' ? 'video' : 'audio') && !row.deleted_at);
          if (asset) changeClip(track.id, clip.id, value => { value.source_snapshot = { id: asset.id, kind: 'ASSET', asset_kind: track.kind === 'VIDEO' ? 'video' : 'audio', version: asset.version, digest: asset.sha256 }; });
        }}><option value="">素材不可用，请选择</option>{props.assets.filter(asset => asset.kind === (track.kind === 'VIDEO' ? 'video' : 'audio') && !asset.deleted_at).map(asset => <option key={asset.id} value={asset.id}>{asset.filename} · v{asset.version}</option>)}</select></label>
        {timelineSourceState(clip.source_snapshot, props.assets) === 'STALE' && <Button onClick={() => {
          const asset = props.assets.find(row => row.id === clip.source_snapshot.id && row.kind === clip.source_snapshot.asset_kind && !row.deleted_at);
          if (asset) changeClip(track.id, clip.id, row => { row.source_snapshot = { id: asset.id, kind: 'ASSET', asset_kind: clip.source_snapshot.asset_kind, version: asset.version, digest: asset.sha256 }; });
        }}>明确采用此素材的当前版本</Button>}
        <NumberField label="放入时间线（毫秒）" value={clip.start_ms} max={draft.timeline.duration_ms - 1} onChange={value => changeClip(track.id, clip.id, row => { row.start_ms = value; })} />
        <NumberField label="素材入点（毫秒）" value={clip.in_ms} max={36000000} onChange={value => changeClip(track.id, clip.id, row => { row.in_ms = value; })} />
        <NumberField label="素材出点（毫秒）" value={clip.out_ms} min={1} max={36000000} onChange={value => changeClip(track.id, clip.id, row => { row.out_ms = value; })} />
        {track.kind === 'VIDEO' && <details><summary>画面位置与尺寸</summary>
          <NumberField label="画面左侧位置" value={clip.x ?? 0} max={draft.timeline.width - 16} onChange={value => changeClip(track.id, clip.id, row => { row.x = value; })} />
          <NumberField label="画面顶部位置" value={clip.y ?? 0} max={draft.timeline.height - 16} onChange={value => changeClip(track.id, clip.id, row => { row.y = value; })} />
          <NumberField label="片段宽度" value={clip.width ?? draft.timeline.width} min={16} max={draft.timeline.width} step={2} onChange={value => changeClip(track.id, clip.id, row => { row.width = value; })} />
          <NumberField label="片段高度" value={clip.height ?? draft.timeline.height} min={16} max={draft.timeline.height} step={2} onChange={value => changeClip(track.id, clip.id, row => { row.height = value; })} />
        </details>}
        <Button variant="danger" onClick={() => changeTrack(track.id, row => { row.clips = row.clips.filter(value => value.id !== clip.id); })}>移除此片段</Button>
      </section>)}
    </fieldset>)}
    <fieldset disabled={locked}><legend>字幕（可选，作者输入的纯文字）</legend>
      <p>字幕不代表模型转录。每条一至八行，不接受空行、样式标记或文件路径。</p>
      <Button disabled={draft.timeline.captions.length >= 500} onClick={() => c.change(input => { input.timeline.captions.push({ start_ms: 0, end_ms: Math.min(1000, input.timeline.duration_ms), text: '' }); })}>添加字幕</Button>
      {draft.timeline.captions.map((cue, index) => <section key={index} aria-label={`字幕 ${index + 1}`}>
        <NumberField label={`字幕 ${index + 1} 开始（毫秒）`} value={cue.start_ms} max={draft.timeline.duration_ms - 1} onChange={value => c.change(input => { input.timeline.captions[index].start_ms = value; })} />
        <NumberField label={`字幕 ${index + 1} 结束（毫秒）`} value={cue.end_ms} min={1} max={draft.timeline.duration_ms} onChange={value => c.change(input => { input.timeline.captions[index].end_ms = value; })} />
        <label>字幕文字<textarea maxLength={1000} value={cue.text} onChange={event => { const text = event.currentTarget.value; c.change(input => { input.timeline.captions[index].text = text; }); }} /></label>
        <Button variant="danger" onClick={() => c.change(input => { input.timeline.captions.splice(index, 1); })}>移除此字幕</Button>
      </section>)}
    </fieldset>
    <details><summary>时间布局（参数预览）</summary><p>这是裁剪、摆放和叠放参数，不是已经渲染的媒体预览。实际画面与声音请从原制作任务的私有候选中核对。</p>
      <table><thead><tr><th scope="col">轨道</th><th scope="col">素材版本</th><th scope="col">裁剪范围</th><th scope="col">时间线范围</th><th scope="col">状态</th></tr></thead>
        <tbody>{draft.timeline.tracks.flatMap(track => track.clips.map(clip => <tr key={clip.id}><th scope="row">{track.kind === 'VIDEO' ? '视频' : '音频'} {track.order + 1}</th>
          <td>{props.assets.find(asset => asset.id === clip.source_snapshot.id)?.filename ?? '不可用'} · v{clip.source_snapshot.version}</td>
          <td>{seconds(clip.in_ms)} — {seconds(clip.out_ms)}</td><td>{seconds(clip.start_ms)} — {seconds(clip.start_ms + clip.out_ms - clip.in_ms)}</td><td>{track.muted ? '隐藏或静音' : '参与渲染'}</td></tr>))}</tbody></table>
    </details>
    <p role="status">{c.inputDirty ? '未保存' : c.base ? `已读取或保存 v${c.base.version}` : '新时间线尚未保存'} · {draft.timeline.tracks.length} 条轨道 · {clipsCount} 个片段</p>
    <Button variant="primary" loading={c.pending === 'SAVE'} disabled={locked || !c.inputDirty && !!c.base} onClick={() => void c.save()}>保存时间线</Button>
    {c.inputDirty && !c.failure && <><label><input type="checkbox" disabled={readLocked} checked={c.discardConfirmed} onChange={event => c.setDiscardConfirmed(event.currentTarget.checked)} />确认放弃本地未保存内容</label><Button disabled={readLocked || !c.discardConfirmed} onClick={c.discardDraft}>放弃本地编辑</Button></>}
    {c.base && <section aria-label="确认本地时间线渲染"><h3>本地渲染</h3>
      <p>绑定已保存 v{c.base.version}。不调用模型；输出 MP4，画面与音频按原渲染服务处理，素材保留原样。</p>
      <details><summary>当前保存摘要</summary><code>{c.base.timeline_digest}</code></details>
      {!c.sourcesCurrent && <StatusMessage tone="warning">素材有变化或不可用，请重新选择对应素材并保存新版本。</StatusMessage>}
      <label><input type="checkbox" checked={c.confirmed} disabled={locked || c.inputDirty || !c.sourcesCurrent || !!c.attempt && c.attempt.state === 'UNKNOWN'} onChange={event => c.setConfirmed(event.currentTarget.checked)} />已核对当前版本、摘要、裁剪、叠放、音量和字幕，确认生成私有渲染候选</label>
      <Button loading={c.pending === 'RENDER'} disabled={!c.canRender} onClick={() => void c.render()}>明确渲染此保存版本</Button>
    </section>}
    {c.attempt && <StatusMessage tone={c.attempt.state === 'UNKNOWN' ? 'warning' : 'info'}>{c.attempt.state === 'UNKNOWN' ? '渲染结果仍需核对，请从制作任务读取原回执；不会再次发送此请求。' : '此快照的渲染请求已有回执，不会从这里重复发起。'} 原请求：<code>{c.attempt.requestId}</code></StatusMessage>}
    {c.attempt && <Button disabled={readLocked} loading={c.pending === 'JOB'} onClick={() => void c.checkRenderJob()}>读取此请求的原渲染回执</Button>}
    <p>这些入口已接入原 owner，当前代码的 Windows、媒体和完整产品验证仍待执行。</p>
  </Panel>;
}
