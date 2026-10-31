import { Button, StatusMessage } from '../ui/primitives';
import type { StudioGraphNode } from './studioGraphTypes';
import type { StudioGraphTimelineEditorController } from './useStudioGraphTimelineEditor';
import { graphTimelinePorts } from './studioGraphTimelineContract';
import { timelineExportPresets, type TimelineExportPreset } from './studioTimelineExportTypes';

const presetLabels: Record<Exclude<TimelineExportPreset, 'AUDIO_WAV_PCM16'>, string> = { REVIEW_MP4: '审核 MP4', DELIVERY_H264_MP4: 'H.264 MP4', DELIVERY_VP9_WEBM: 'VP9 WebM' };
/** Basic replaceable controls; the controller owns the exact source and closed operation list. */
export function StudioGraphTimelineNodeEditor({ node, state, editable, connectedPorts }: { node: StudioGraphNode;
  state: StudioGraphTimelineEditorController; editable: boolean; connectedPorts: string[] }) {
  const snapshot = node.parameters.timeline_snapshot, profile = node.parameters.export_profile, form = state.form;
  const disabled = !editable || !state.formOwnerMatches || state.loading;
  const numeric = (key: 'in_ms' | 'out_ms' | 'start_ms' | 'at_ms' | 'offset_ms' | 'speed_num' | 'speed_den' | 'opacity' | 'gain_db' | 'fade_in_ms' | 'fade_out_ms', label: string) =>
    <label key={key}>{label}<input type="number" step={key === 'opacity' || key === 'gain_db' ? 'any' : 1} disabled={disabled} value={form[key]} onChange={event => state.changeForm(key, event.target.value)} /></label>;
  const extraClips = state.operations.flatMap(operation => operation.op === 'clip.duplicate' || operation.op === 'clip.split' ? [operation.new_clip_id] : operation.op === 'clip.insert' ? [operation.clip.id] : []);
  const clipIds = [...new Set([...state.clips.map(row => row.clip.id), ...extraClips])];
  return <section aria-label="时间线节点配置">
    <p>绑定原时间线和确切版本，编辑操作按保存的顺序执行。预览不保存、不渲染；确认派发后才原子保存剪辑与素材替换，并仅入队。渲染和候选审核分别明确操作。</p>
    {state.error && <StatusMessage tone="error">{state.error}</StatusMessage>}
    <Button disabled={!state.canLoad} loading={state.loading} onClick={() => void state.loadRows()}>明确读取原时间线目录</Button>
    <label>原时间线<select disabled={!editable || state.loading} value={state.choice} onChange={event => state.choose(event.target.value)}><option value="">选择已有时间线</option>{state.rows.map(row => <option key={row.id} value={row.id}>{row.title} · {row.id} · v{row.version}</option>)}</select></label>
    <Button disabled={!editable || !state.chosen || state.formDirty || state.loading} onClick={state.bindChosen}>替换时间线绑定并清空本节点的剪辑与素材绑定</Button>
    {snapshot && <p>原绑定：{snapshot.id} · v{snapshot.version}<br /><code>{snapshot.digest}</code></p>}
    {!state.bound && <StatusMessage tone="warning">尚未读取到与此绑定完全一致的原时间线。请明确读取目录；当前版本变更不会自动更新绑定。</StatusMessage>}
    {state.bound && <p>{state.bound.timeline.tracks.length} 轨道 · {state.bound.timeline.duration_ms} 毫秒 · {state.bound.timeline.width}×{state.bound.timeline.height} · {state.bound.timeline.fps} fps</p>}
    <fieldset disabled={!editable || state.loading}><legend>导出编码配置</legend>
      <label>输出预设<select value={profile?.preset || 'REVIEW_MP4'} onChange={event => state.setPreset(event.target.value as TimelineExportPreset)}>{timelineExportPresets.filter((preset): preset is Exclude<TimelineExportPreset, 'AUDIO_WAV_PCM16'> => preset !== 'AUDIO_WAV_PCM16').map(preset => <option key={preset} value={preset}>{presetLabels[preset]}</option>)}</select></label>
      {profile && profile.preset !== 'REVIEW_MP4' && <>{(['video_bitrate_kbps', 'audio_bitrate_kbps', 'crf'] as const).map(key => <label key={key}>{key === 'video_bitrate_kbps' ? '视频码率 kbps' : key === 'audio_bitrate_kbps' ? '音频码率 kbps' : 'CRF'}<input type="number" step={1} min={key === 'crf' ? 0 : key === 'video_bitrate_kbps' ? 100 : 32} max={key === 'crf' ? profile.preset === 'DELIVERY_VP9_WEBM' ? 63 : 51 : key === 'video_bitrate_kbps' ? 20000 : 320} value={profile[key] ?? ''} onChange={event => state.setProfileField(key, event.target.value)} /></label>)}</>}
    </fieldset>
    <fieldset disabled={!editable || !state.bound || state.loading}><legend>Graph 素材端口到片段的绑定</legend>
      {graphTimelinePorts.map(port => <label key={port}>{port} · {connectedPorts.includes(port) ? '已连接，须绑定片段' : '未连接'}<select value={state.bindings.find(binding => binding.port === port)?.clip_id || ''} onChange={event => state.bindSource(port, event.target.value)}><option value="">无替换绑定</option>{clipIds.map(id => <option key={id} value={id}>{id}</option>)}</select></label>)}
      <p>每个已连接端口须绑定一个不同片段；无连接端口不设绑定。素材只接受原资产引用或已审核媒体输出，按最终轨道类型核对。绑定会计入剪辑操作上限。</p>
    </fieldset>
    <fieldset disabled={disabled || !state.bound}><legend>添加常用剪辑操作</legend>
      {form.operation !== 'track.update' && <label>片段<select value={form.clip_id} onChange={event => state.selectClip(event.target.value)}><option value="">选择原时间线片段</option>{state.clips.map(({ clip, track }) => <option key={clip.id} value={clip.id}>{track.id} · {clip.id} · {clip.source_snapshot.asset_kind}</option>)}</select></label>}
      {state.clips.find(row => row.clip.id === form.clip_id) && <details><summary>核对所选片段来源版本和摘要</summary><pre>{JSON.stringify(state.clips.find(row => row.clip.id === form.clip_id)!.clip.source_snapshot, null, 2)}</pre></details>}
      <label>剪辑操作<select value={form.operation} onChange={event => state.changeForm('operation', event.target.value as typeof form.operation)}><option value="track.update">轨道静音、音量与用途</option><option value="clip.trim">截取（可波纹）</option><option value="clip.move">移动片段</option><option value="clip.split">分割片段</option><option value="clip.duplicate">复制片段</option><option value="clip.slip">滑移来源区间</option><option value="clip.update" disabled={state.bound?.timeline.schema_version !== 2}>速度、音量与淡入淡出（schema2）</option><option value="clip.remove">移除片段（可波纹）</option></select></label>
      {form.operation === 'track.update' && <><label>待编辑原轨道<select value={form.track_id} onChange={event => state.selectTrack(event.target.value)}><option value="">选择原时间线轨道</option>{state.bound?.timeline.tracks.map(track => <option key={track.id} value={track.id} disabled={track.locked}>{track.id} · {track.kind}{track.locked ? ' · 已锁定' : ''}</option>)}</select></label>{state.bound?.timeline.tracks.find(track => track.id === form.track_id)?.kind === 'AUDIO' && numeric('gain_db', '轨道音量 dB')}<label><input type="checkbox" checked={form.muted} onChange={event => state.changeForm('muted', event.target.checked)} />停用轨道（视频隐藏／音频静音）</label>{state.bound?.timeline.schema_version === 2 && <label>轨道用途<select value={form.role} onChange={event => state.changeForm('role', event.target.value)}><option value="">选择用途</option>{(state.bound.timeline.tracks.find(track => track.id === form.track_id)?.kind === 'VIDEO' ? ['PRIMARY','OVERLAY'] : ['DIALOGUE','MUSIC','EFFECTS']).map(role => <option key={role} value={role}>{role}</option>)}</select></label>}<p>只加入原 track.update 操作；不会自动解锁、保存、混音或渲染。schema1 不写用途字段。</p></>}
      {form.operation === 'clip.trim' && <>{numeric('in_ms', '来源起点 ms')}{numeric('out_ms', '来源终点 ms')}</>}
      {(form.operation === 'clip.move' || form.operation === 'clip.duplicate') && <><label>目标轨道<select value={form.track_id} onChange={event => state.changeForm('track_id', event.target.value)}>{state.bound?.timeline.tracks.map(track => <option key={track.id} value={track.id}>{track.id} · {track.kind}</option>)}</select></label>{numeric('start_ms', '时间线起点 ms')}</>}
      {form.operation === 'clip.split' && numeric('at_ms', '时间线分割点 ms')}
      {form.operation === 'clip.slip' && numeric('offset_ms', '来源滑移量 ms')}
      {form.operation === 'clip.update' && <>{numeric('speed_num', '速度分子 1–4')}{numeric('speed_den', '速度分母 1–4')}{numeric('gain_db', '音量 dB')}{numeric('fade_in_ms', '淡入 ms')}{numeric('fade_out_ms', '淡出 ms')}<label><input type="checkbox" checked={form.muted} onChange={event => state.changeForm('muted', event.target.checked)} />片段静音</label>{state.clips.find(row => row.clip.id === form.clip_id)?.track.kind === 'VIDEO' && <>{numeric('opacity', '不透明度 0–1')}<label><input type="checkbox" checked={form.include_audio} onChange={event => state.changeForm('include_audio', event.target.checked)} />包含来源视频的音轨（静态图不支持）</label></>}</>}
      {(form.operation === 'clip.trim' || form.operation === 'clip.remove') && <label><input type="checkbox" checked={form.ripple} onChange={event => state.changeForm('ripple', event.target.checked)} />同轨后续片段按时长变化波纹移动</label>}
      <Button disabled={disabled || !state.bound || (form.operation === 'track.update' ? !form.track_id : !form.clip_id) || !form.owner || state.operations.length + state.bindings.length >= 40} onClick={state.append}>明确加入剪辑操作</Button>
      <p>同轨视频不重叠；速度和分割保持整数毫秒；完整结果由原时间线服务原子校验。schema1 不使用新速度、淡入淡出字段，可先在原时间线编辑器明确升级。</p>
    </fieldset>
    {state.formDirty && !state.formOwnerMatches && <StatusMessage tone="warning">节点或原时间线版本已变化，未加入的输入已暂停。请先放弃该输入，再选择当前来源。</StatusMessage>}
    {state.formDirty && <Button disabled={state.loading} onClick={state.clearForm}>放弃尚未加入的剪辑输入</Button>}
    <p>已保存到图草稿的编辑：{state.operations.length} · 素材替换：{state.bindings.length} · 合计最多 40。</p>
    <p>剪辑按列表顺序应用。上移或下移只修改图草稿；复制、分割产生的新片段必须先创建再使用。请重新预览，由原时间线服务校验完整结果后再确认派发。</p>
    <ol>{state.operations.map((operation, index) => <li key={index}><details><summary>{index + 1}. {operation.op}</summary><pre>{JSON.stringify(operation, null, 2)}</pre></details><Button aria-label={`上移第 ${index + 1} 项剪辑操作`} disabled={!editable || state.loading || index === 0} onClick={() => state.moveOperation(index, index - 1)}>上移</Button><Button aria-label={`下移第 ${index + 1} 项剪辑操作`} disabled={!editable || state.loading || index === state.operations.length - 1} onClick={() => state.moveOperation(index, index + 1)}>下移</Button><Button disabled={!editable || state.loading} onClick={() => state.removeOperation(index)}>移除此剪辑操作</Button></li>)}</ol>
    <p>本机渲染与完整流程验收仍为 LOCAL_REQUIRED。图保存、连接及预览不会执行剪辑或导出。</p>
  </section>;
}
