import { selectionSplitOperations, sameSelectionSplitDescriptors } from '../nle/timelineSelectionSplit';
import { applyClipColorOperation } from '../nle/timelineClipColor';
import {StudioTimelineSourceBoundsRepair} from './StudioTimelineSourceBoundsRepair';
import {useStudioTimelineSourceBounds} from './useStudioTimelineSourceBounds';
import { StudioTimelineCloseGaps } from './StudioTimelineCloseGaps';
import { StudioTimelineCaptionStyle } from './StudioTimelineCaptionStyle';
import { applyNleCaptionCommand } from './nleCaptionEditing';
import { nleSourceReplacementIntent } from './nleSourceReplacement';
import { selectionDuplicateOperations, sameSelectionDuplicateDescriptors } from '../nle/timelineSelectionDuplicate';
import { selectionMoveOperations } from '../nle/timelineSelectionMove';
import { selectionRemovePreview, sameSelectionRemoveDescriptors } from '../nle/timelineSelectionRemove';
import { StudioTimelineAssetPicker } from './StudioTimelineAssetPicker';
import { appendTimelineAsset, StudioTimelineAssetHandoff } from './StudioTimelineAssetHandoff';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { TIMELINE_LIMITS, timelineClipDuration, timelineSourceState, type StudioTimelineClip, type StudioTimelineDraft, type StudioTimelineTrack } from './studioTimelineTypes';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { StudioTimelineExportPanel } from './StudioTimelineExportPanel';
import { StudioTimelineMeasurement } from './StudioTimelineMeasurement';
import { transferClipTarget } from './timelineTransferReviewHelpers';
import { StudioTimelineTransferPanel } from './StudioTimelineTransferPanel';
import { StudioTimelinePlaybackPanel } from './StudioTimelinePlaybackPanel';
import { StudioTimelineSourceEditPanel } from './StudioTimelineSourceEditPanel';
import { useStudioTimelineWaveform } from './useStudioTimelineWaveform';
// UX-PRODUCT batch 3 (UX-06): multitrack editing rail. Additive presentation over the
// SAME controller and draft; it never introduces a second timeline engine.
import { TimelineWorkspacePanel } from '../nle/TimelineWorkspacePanel';
import { TimelineClipLinkPanel } from '../nle/TimelineClipLinkPanel';
import { LinkedClipSplitPanel } from '../nle/LinkedClipSplitPanel';
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
  const [clipEdits, setClipEdits] = useState<Record<string, { split?: number; position?: number; target?: string }>>({});
  // UX-06 rail state: local view/selection only; it never writes the timeline.
  const [nleClips, setNleClips] = useState<string[]>([]);
  const selection = useRef({ ids: [] as string[], generation: 0 });
  const selectClips = (ids: string[]) => {
    if (JSON.stringify(ids) !== JSON.stringify(selection.current.ids)) selection.current.generation++;
    selection.current.ids = [...ids]; setNleClips([...ids]);
  };
  const selectionGeneration = selection.current.generation;
  const [nlePlayhead, setNlePlayhead] = useState(0);
  const playhead = useRef({ value: 0, generation: 0 });
  const selectPlayhead = (value: number) => {
    if (playhead.current.value !== value) playhead.current.generation++;
    playhead.current.value = value; setNlePlayhead(value);
  };
  const playheadGeneration = playhead.current.generation;
  const [nleView, setNleView] = useState({ startMs: 0, scale: 1 });
  const [nleNotice, setNleNotice] = useState('');
  const [sourceEditReveal, setSourceEditReveal] = useState(0);
  useEffect(() => { setPicked({}); setClipEdits({}); setSourceEditReveal(0); }, [props.client]);
  const clipElements = useRef(new Map<string, HTMLElement>()), composing = useRef(false);
  const pickerOwner = useRef({ client: props.client, generation: 0 });
  if (pickerOwner.current.client !== props.client) pickerOwner.current = { client: props.client, generation: pickerOwner.current.generation + 1 };
  useEffect(() => { composing.current = false; }, [props.client]);
  const latestReview = useRef({ c, props, nleClips }); latestReview.current = { c, props, nleClips };
  const reviewGeneration = c.getHandoffRevision();
  const observationOptions = { props, source: c.base, selectedClipIds: nleClips,
    getSelectionGeneration: () => selection.current.generation, getRevision: c.getHandoffRevision,
    isReady: () => {
      const live = latestReview.current;
      return live.c.canEdit && !!live.c.base && !live.c.inputDirty && !live.c.dirty && !live.c.failure && !live.c.pending
        && !live.c.denied && live.c.attempt?.state !== 'UNKNOWN' && live.c.sourcesCurrent
        && !live.c.transfer.locked && !live.c.playback.locked && !live.c.sourceEdit.locked;
    } };
  const waveform = useStudioTimelineWaveform(observationOptions);
  const sourceBounds = useStudioTimelineSourceBounds(observationOptions);
  useLayoutEffect(() => {
    if (waveform.preview && c.base) c.observeWaveformMeasurement(waveform.preview,c.base,props.client);
  }, [waveform.preview,c.base,props.client]);
  const draft = c.draft;
  if (!draft) return <Panel title="时间线"><EmptyState title="当前时间线入口不可用" detail="请重新核对项目、身份与原可信会话。旧输入和回执不会跨身份显示。" /></Panel>;
  const audioOnly = draft.timeline.schema_version === 3, videoTimeline = draft.timeline.schema_version === 3 ? undefined : draft.timeline;
  const extended = draft.timeline.schema_version === 2 || audioOnly;
  const sourceFits = (track: StudioTimelineTrack, kind: string) => track.kind === 'AUDIO' ? kind === 'audio' : kind === 'video' || extended && kind === 'image';
  const editControl = (clipId: string, values: { split?: number; position?: number; target?: string }) => setClipEdits(rows => ({ ...rows, [clipId]: { ...rows[clipId], ...values } }));
  const changeTrack = (id: string, work: (track: StudioTimelineTrack, draft: StudioTimelineDraft) => void) => c.change(input => {
    const track = input.timeline.tracks.find(row => row.id === id); if (track) work(track, input);
  });
  const changeClip = (trackId: string, clipId: string, work: (clip: StudioTimelineClip) => void) => changeTrack(trackId, track => {
    const clip = track.clips.find(row => row.id === clipId); if (clip) work(clip);
  });
  const addTrack = (kind: 'VIDEO' | 'AUDIO') => c.change(input => {
    if (input.timeline.schema_version === 3 && kind !== 'AUDIO') return;
    if (input.timeline.tracks.length >= 8 || input.timeline.tracks.filter(track => track.kind === kind).length >= 4) return;
    input.timeline.tracks.push({ id: crypto.randomUUID(), kind, order: input.timeline.tracks.length, muted: false, gain_db: 0, clips: [],
      ...([2, 3].includes(input.timeline.schema_version ?? 1) ? { role: kind === 'VIDEO' ? 'PRIMARY' as const : 'DIALOGUE' as const } : {}) });
  });
  const moveTrack = (id: string, direction: -1 | 1) => c.change(input => {
    const tracks = input.timeline.tracks, index = tracks.findIndex(track => track.id === id), target = index + direction;
    if (index < 0 || target < 0 || target >= tracks.length) return;
    [tracks[index], tracks[target]] = [tracks[target], tracks[index]]; tracks.forEach((track, order) => { track.order = order; });
  });
  const locked = !c.canEdit || props.busy;
  const readLocked = c.denied || props.busy || !!c.pending || c.transfer.locked || c.playback.locked || c.sourceEdit.locked;
  const clipsCount = draft.timeline.tracks.reduce((sum, track) => sum + track.clips.length, 0);
  return <Panel title={audioOnly ? "音频多轨时间线" : "多轨时间线"} aria-label="Studio 多轨时间线编辑器" onCompositionStart={() => { composing.current = true; }} onCompositionEnd={() => { composing.current = false; }} actions={<Button loading={c.pending === 'LIST'} disabled={readLocked} onClick={() => void c.reload()}>刷新时间线列表</Button>}>
    <p>{audioOnly ? '选择已有音频素材，设定裁剪、摆放、增益和淡入淡出。最多四条音频轨道、三十个片段、十分钟；明确试听与 WAV 导出后，产物仍须在制作任务中人工审核。' : '选择已有视频和音频素材，设定裁剪与摆放。视频按轨道顺序叠放，音频轨道混音；视频自身声音只在扩展编辑中明确加入。总长最多十分钟，产物仍须在制作任务中预览和人工审核。'}</p>
    <label>读取已保存时间线<select disabled={readLocked} value={c.candidate?.id ?? c.base?.id ?? ''} onChange={event => { if (event.currentTarget.value) void c.checkServer(event.currentTarget.value); }}>
      <option value="">选择时间线后核对</option>{c.rows.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}
    </select></label>
    <Button disabled={readLocked} onClick={() => void c.checkServer()}>核对当前服务端版本</Button>
    <Button disabled={locked || !!c.attempt && c.attempt.state === 'UNKNOWN' || c.inputDirty && !c.discardConfirmed} onClick={c.createNew}>新建时间线</Button>
    {!c.rows.length && !c.pending && <p>尚无已读取的时间线。可以先添加轨道与素材，再明确保存。</p>}
    {c.pending && <StatusMessage>{({ LIST: '正在读取时间线列表…', GET: '正在读取服务端版本…', SAVE: '正在保存时间线…', RENDER: '正在执行原本地渲染任务…', JOB: '正在读取原渲染或导出任务回执…', EXPORT_PREVIEW: '正在核对导出方案，尚未执行…', EXPORT: '正在执行本次明确确认的导出渲染…', TRACK_LOCK: '正在保存轨道锁定状态…' })[c.pending]}</StatusMessage>}
    {c.failure && <StatusMessage tone="warning">{c.failure === 'CONFLICT' ? '服务端版本已变化。输入保留，请读取并核对版本后人工采用或保留草稿。' : '保存结果不确定，不能直接重复保存。请读取服务端版本；新建请求没有已知标识时，刷新列表并选择候选。'}</StatusMessage>}
    {c.error && <StatusMessage tone="error">{c.error}</StatusMessage>}{c.notice && <StatusMessage>{c.notice}</StatusMessage>}
    {c.candidate && <section aria-label="核对服务端时间线">
      <h3>{c.candidate.title} · v{c.candidate.version}</h3><p>{seconds(c.candidate.timeline.duration_ms)}{c.candidate.timeline.schema_version === 3 ? ' · 纯音频' : ` · ${c.candidate.timeline.width} × ${c.candidate.timeline.height} · ${c.candidate.timeline.fps} fps`} · {c.candidate.timeline.tracks.length} 条轨道</p>
      <ul>{c.candidate.timeline.tracks.map(track => <li key={track.id}>{track.kind === 'VIDEO' ? '视频' : '音频'}轨道 {track.order + 1} · {track.clips.length} 个片段 · {track.muted ? '隐藏或静音' : '参与渲染'}{track.kind === 'AUDIO' ? ` · ${track.gain_db} dB` : ''}
        <ul>{track.clips.map(clip => <li key={clip.id}>{props.assets.find(asset => asset.id === clip.source_snapshot.id)?.filename ?? '素材不可用'} · v{clip.source_snapshot.version} · 放入 {seconds(clip.start_ms)} · 裁剪 {seconds(clip.in_ms)} 至 {seconds(clip.out_ms)}</li>)}</ul>
      </li>)}</ul>
      {c.candidate.timeline.schema_version !== 3 && <p>字幕：{c.candidate.timeline.captions.map(cue => `${seconds(cue.start_ms)}—${seconds(cue.end_ms)} ${cue.text}`).join('；') || '无'}</p>}
      <details><summary>版本绑定摘要</summary><code>{c.candidate.timeline_digest}</code></details>
      <p>读取的候选不证明原保存或渲染请求已完成；采用服务端值会替换当前编辑内容。</p>
      <label><input type="checkbox" checked={c.adoptConfirmed} disabled={readLocked} onChange={event => c.setAdoptConfirmed(event.currentTarget.checked)} />已核对服务端内容与本地输入，确认以下选择</label>
      <Button disabled={readLocked || !c.adoptConfirmed || c.attempt?.state === 'UNKNOWN'} onClick={() => c.adoptCandidate(false)}>采用服务端时间线</Button>
      <Button disabled={readLocked || !c.adoptConfirmed || !props.canMutate || c.attempt?.state === 'UNKNOWN'} onClick={() => c.adoptCandidate(true)}>保留草稿并基于此版本编辑</Button>
    </section>}
    {props.assetHandoff && <StudioTimelineAssetHandoff key={props.assetHandoff.id}
      request={props.assetHandoff} draft={draft} canEdit={c.canEdit} isCurrent={props.isCurrent} getRevision={c.getHandoffRevision}
      readJob={(owner, id) => props.read(() => props.client.get(owner, id))}
      onApply={(trackId, asset, range) => c.change(input => appendTimelineAsset(input, trackId, asset, range))} />}
    <StudioTimelineSourceEditPanel controller={c.sourceEdit} source={c.base} assets={audioOnly ? props.assets.filter(asset => asset.kind === 'audio') : props.assets} revealRequest={sourceEditReveal} />
    <fieldset disabled={locked}><legend>时间线参数</legend>
      <p>{audioOnly ? '音频编辑版本 3：独立音频轨道，支持裁剪、速度、淡入淡出和片段音量。' : extended ? '扩展编辑版本 2：可使用静态画面、速度、淡入淡出和片段音量。' : '原时间线版本：保存与渲染保持原有字段和行为。'}</p>
      {!extended && <Button onClick={c.upgradeTimeline}>明确采用扩展编辑（版本 2，需重新保存）</Button>}
      <label>名称<input maxLength={240} value={draft.title} onChange={event => { const title = event.currentTarget.value; c.change(input => { input.title = title; }); }} /></label>
      <NumberField label="总长（毫秒）" value={draft.timeline.duration_ms} min={1} max={600000} onChange={value => c.change(input => { input.timeline.duration_ms = value; })} />
      {videoTimeline && <><NumberField label="画面宽度" value={videoTimeline.width} min={16} max={1920} step={2} onChange={value => c.change(input => { if (input.timeline.schema_version !== 3) input.timeline.width = value; })} />
      <NumberField label="画面高度" value={videoTimeline.height} min={16} max={1080} step={2} onChange={value => c.change(input => { if (input.timeline.schema_version !== 3) input.timeline.height = value; })} />
      <NumberField label="帧率" value={videoTimeline.fps} min={1} max={60} onChange={value => c.change(input => { if (input.timeline.schema_version !== 3) input.timeline.fps = value; })} />
      <p>1000 毫秒为一秒。更改画面大小后请核对各视频片段的位置与尺寸，素材实际时长由原服务校验。</p></>}
      {!audioOnly && <Button disabled={draft.timeline.tracks.length >= 8 || draft.timeline.tracks.filter(track => track.kind === 'VIDEO').length >= 4} onClick={() => addTrack('VIDEO')}>添加视频轨道</Button>}
      <Button disabled={draft.timeline.tracks.length >= 8 || draft.timeline.tracks.filter(track => track.kind === 'AUDIO').length >= 4} onClick={() => addTrack('AUDIO')}>添加音频轨道</Button>
    </fieldset>
    <StudioTimelineCloseGaps draft={draft} scope={props.client} disabled={locked} isCurrent={props.isCurrent} getRevision={c.getHandoffRevision} onApply={next => c.change(input => { input.timeline = next.timeline; })} />
    {draft.timeline.tracks.map((track, index) => <fieldset key={track.id} disabled={locked}><legend>{track.kind === 'VIDEO' ? '视频' : '音频'}轨道 {index + 1}</legend>
      {extended && <><Badge tone={track.locked ? 'warning' : 'neutral'}>{track.locked ? '已保存的轨道锁' : '轨道可编辑'}</Badge>
        <Button disabled={!c.trackLockAvailable || c.inputDirty || !c.base || !c.sourcesCurrent} loading={c.pending === 'TRACK_LOCK'} onClick={() => void c.setTrackLocked(track.id, !track.locked)}>{track.locked ? '通过原服务明确解锁' : '通过原服务锁定此轨道'}</Button>
        <p>锁定与解锁直接保存新版本，需要先保存草稿；锁定轨道不接受片段、排序或画布改动。解锁使用独立原编辑动作。</p></>}
      <fieldset disabled={!!track.locked}><legend>轨道编辑</legend>
      <p>{track.kind === 'VIDEO' ? '靠后的轨道覆盖前面的画面；同轨道只有明确交叉溶解的相邻片段可按准确窗口重叠。' : '参与轨道按摆放时间混音，未放入声音的区间保留静音。'}</p>
      <label><input type="checkbox" checked={track.muted} onChange={event => { const muted = event.currentTarget.checked; changeTrack(track.id, row => { row.muted = muted; }); }} />{track.kind === 'VIDEO' ? '隐藏整条轨道' : '整条轨道静音'}</label>
      {extended && <label>轨道用途<select value={track.role ?? (track.kind === 'VIDEO' ? 'PRIMARY' : 'DIALOGUE')} onChange={event => {
        const role = event.currentTarget.value as StudioTimelineTrack['role']; changeTrack(track.id, row => { row.role = role; });
      }}>{(track.kind === 'VIDEO' ? [['PRIMARY', '主要画面'], ['OVERLAY', '叠加画面']] : [['DIALOGUE', '对白'], ['MUSIC', '音乐'], ['EFFECTS', '音效']]).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
      {track.kind === 'AUDIO' && <NumberField label="轨道音量（dB）" value={track.gain_db} min={-60} max={12} step={0.1} onChange={value => changeTrack(track.id, row => { row.gain_db = value; })} />}
      <Button disabled={index === 0} onClick={() => moveTrack(track.id, -1)}>轨道前移</Button><Button disabled={index === draft.timeline.tracks.length - 1} onClick={() => moveTrack(track.id, 1)}>轨道后移</Button>
      <Button variant="danger" onClick={() => c.change(input => { input.timeline.tracks = input.timeline.tracks.filter(row => row.id !== track.id); input.timeline.tracks.forEach((row, order) => { row.order = order; }); })}>移除轨道及片段</Button>
      <label>选择已有{track.kind === 'VIDEO' ? extended ? '视频或静态画面' : '视频' : '音频'}素材<select value={picked[track.id] ?? ''} onChange={event => { const value = event.currentTarget.value; setPicked(values => ({ ...values, [track.id]: value })); }}>
        <option value="">请选择素材</option>{props.assets.filter(asset => sourceFits(track, asset.kind) && !asset.deleted_at).map(asset => <option key={asset.id} value={asset.id}>{asset.filename} · {asset.kind} · v{asset.version}</option>)}
      </select></label>
      <StudioTimelineAssetPicker key={JSON.stringify([pickerOwner.current.generation, track.id, picked[track.id], props.assets.find(row => row.id === picked[track.id])?.version, props.assets.find(row => row.id === picked[track.id])?.sha256])}
        asset={props.assets.find(row => row.id === picked[track.id])} canEdit={!locked && !track.locked && clipsCount < 30} isCurrent={props.isCurrent} getRevision={c.getHandoffRevision}
        readJob={(owner, id) => props.read(() => props.client.get(owner, id))}
        onApply={range => c.change(input => { const asset = props.assets.find(row => row.id === picked[track.id]); if (asset) appendTimelineAsset(input, track.id, asset, range); })} />
      {!track.clips.length && <p>此轨道尚无片段，保存前请加入素材或移除此轨道。</p>}
      {track.clips.map((clip, clipIndex) => <section key={clip.id} tabIndex={-1} ref={element => { if (element) clipElements.current.set(clip.id, element); else clipElements.current.delete(clip.id); }} aria-label={`轨道 ${index + 1} 片段 ${clipIndex + 1}`}>
        <h4>{props.assets.find(asset => asset.id === clip.source_snapshot.id)?.filename ?? '素材不可用'} · 片段 {clipIndex + 1}</h4>
        <Badge tone={timelineSourceState(clip.source_snapshot, props.assets) === 'CURRENT' ? 'neutral' : 'warning'}>{sourceLabel[timelineSourceState(clip.source_snapshot, props.assets)]} · v{clip.source_snapshot.version}</Badge>
        <details><summary>片段与素材绑定</summary><p>片段 <code>{clip.id}</code> · 素材 <code>{clip.source_snapshot.id}</code> · {clip.source_snapshot.asset_kind} · v{clip.source_snapshot.version}</p><code>{clip.source_snapshot.digest}</code></details>
        <label>重新绑定当前素材版本<select value={props.assets.some(asset => asset.id === clip.source_snapshot.id && !asset.deleted_at) ? clip.source_snapshot.id : ''} onChange={event => {
          const asset = props.assets.find(row => row.id === event.currentTarget.value && sourceFits(track, row.kind) && !row.deleted_at);
          if (asset) changeClip(track.id, clip.id, value => { value.source_snapshot = { id: asset.id, kind: 'ASSET', asset_kind: asset.kind as 'image' | 'video' | 'audio', version: asset.version, digest: asset.sha256 }; });
        }}><option value="">素材不可用，请选择</option>{props.assets.filter(asset => sourceFits(track, asset.kind) && !asset.deleted_at).map(asset => <option key={asset.id} value={asset.id}>{asset.filename} · {asset.kind} · v{asset.version}</option>)}</select></label>
        {timelineSourceState(clip.source_snapshot, props.assets) === 'STALE' && <Button onClick={() => {
          const asset = props.assets.find(row => row.id === clip.source_snapshot.id && row.kind === clip.source_snapshot.asset_kind && !row.deleted_at);
          if (asset) changeClip(track.id, clip.id, row => { row.source_snapshot = { id: asset.id, kind: 'ASSET', asset_kind: clip.source_snapshot.asset_kind, version: asset.version, digest: asset.sha256 }; });
        }}>明确采用此素材的当前版本</Button>}
        <NumberField label="放入时间线（毫秒）" value={clip.start_ms} max={draft.timeline.duration_ms - 1} onChange={value => changeClip(track.id, clip.id, row => { row.start_ms = value; })} />
        <NumberField label="素材入点（毫秒）" value={clip.in_ms} max={36000000} onChange={value => changeClip(track.id, clip.id, row => { row.in_ms = value; })} />
        <NumberField label="素材出点（毫秒）" value={clip.out_ms} min={1} max={36000000} onChange={value => changeClip(track.id, clip.id, row => { row.out_ms = value; })} />
        {extended && <details><summary>速度、淡入淡出与片段状态</summary>
          <p>速度为分子 / 分母，保存时约分；渲染长度必须落在整数毫秒。静态画面使用零入点与 1/1 速度，出点表示展示时长。</p>
          <NumberField label="速度分子" value={clip.speed_num ?? 1} min={1} max={4} onChange={value => changeClip(track.id, clip.id, row => { row.speed_num = value; })} />
          <NumberField label="速度分母" value={clip.speed_den ?? 1} min={1} max={4} onChange={value => changeClip(track.id, clip.id, row => { row.speed_den = value; })} />
          <NumberField label="淡入（毫秒）" value={clip.fade_in_ms ?? 0} max={timelineClipDuration(clip)} onChange={value => changeClip(track.id, clip.id, row => { row.fade_in_ms = value; })} />
          <NumberField label="淡出（毫秒）" value={clip.fade_out_ms ?? 0} max={timelineClipDuration(clip)} onChange={value => changeClip(track.id, clip.id, row => { row.fade_out_ms = value; })} />
          <label><input type="checkbox" checked={clip.muted ?? false} onChange={event => { const muted = event.currentTarget.checked; changeClip(track.id, clip.id, row => { row.muted = muted; }); }} />{track.kind === 'VIDEO' ? '隐藏此片段及其声音' : '此片段静音'}</label>
          {track.kind === 'VIDEO' && videoTimeline && <><NumberField label="不透明度" value={clip.opacity ?? 1} max={1} step={0.05} onChange={value => changeClip(track.id, clip.id, row => { row.opacity = value; })} />
            <label><input type="checkbox" checked={clip.include_audio ?? false} disabled={clip.source_snapshot.asset_kind === 'image' && !clip.include_audio} onChange={event => { const include = event.currentTarget.checked; changeClip(track.id, clip.id, row => { row.include_audio = include; }); }} />明确加入此视频原声（静态画面保持关闭）</label>
            <label>交叉溶解到下一片段<select value={clip.transition_out?.to_clip_id ?? ''} onChange={event => {
              const targetId = event.currentTarget.value; changeClip(track.id, clip.id, row => {
                if (!targetId) delete row.transition_out;
                else { const target = track.clips.find(item => item.id === targetId);
                  row.transition_out = { kind: 'CROSS_DISSOLVE', to_clip_id: targetId,
                    duration_ms: target ? Math.max(1, clip.start_ms + timelineClipDuration(clip) - target.start_ms) : 500 }; }
              });
            }}><option value="">无交叉溶解</option>{track.clips.filter(item => item.start_ms > clip.start_ms).sort((left, right) => left.start_ms - right.start_ms).slice(0, 1)
              .map(item => <option key={item.id} value={item.id}>{item.id}</option>)}</select></label>
            {clip.transition_out && <NumberField label="两源交叉溶解窗口（毫秒）" value={clip.transition_out.duration_ms} min={Math.ceil(2000 / videoTimeline.fps)} max={10000}
              onChange={value => changeClip(track.id, clip.id, row => { if (row.transition_out) row.transition_out.duration_ms = value; })} />}
            <p>转场需两个相邻片段准确重叠，同位置、尺寸与不透明度；窗口至少两帧且小于两片段时长。转场片段不能另外淡入淡出或静音；修改摆放后须重新核对窗口。</p></>}
          <NumberField label={track.kind === 'VIDEO' ? '原声音量（dB；未加入原声时保持 0）' : '片段音量（dB）'} value={clip.gain_db ?? 0} min={-60} max={12} step={0.1} onChange={value => changeClip(track.id, clip.id, row => { row.gain_db = value; })} />
          <p>渲染时长 {seconds(timelineClipDuration(clip))}；淡入与淡出总长不能超过此长度。</p>
        </details>}
        {track.kind === 'VIDEO' && videoTimeline && <details><summary>画面位置与尺寸</summary>
          <NumberField label="画面左侧位置" value={clip.x ?? 0} max={videoTimeline.width - 16} onChange={value => changeClip(track.id, clip.id, row => { row.x = value; })} />
          <NumberField label="画面顶部位置" value={clip.y ?? 0} max={videoTimeline.height - 16} onChange={value => changeClip(track.id, clip.id, row => { row.y = value; })} />
          <NumberField label="片段宽度" value={clip.width ?? videoTimeline.width} min={16} max={videoTimeline.width} step={2} onChange={value => changeClip(track.id, clip.id, row => { row.width = value; })} />
          <NumberField label="片段高度" value={clip.height ?? videoTimeline.height} min={16} max={videoTimeline.height} step={2} onChange={value => changeClip(track.id, clip.id, row => { row.height = value; })} />
          {extended && <><label><input type="checkbox" checked={!!clip.crop} onChange={event => {
            const enabled = event.currentTarget.checked; changeClip(track.id, clip.id, row => {
              if (enabled) row.crop = { x: 0, y: 0, width: row.width ?? videoTimeline.width, height: row.height ?? videoTimeline.height };
              else delete row.crop;
            });
          }} />明确裁剪素材原始像素区域</label><p>裁剪发生在缩放之前。实际素材尺寸由原渲染服务核对，参数越界会拒绝执行。</p>
            {clip.crop && <><NumberField label="源像素左侧" value={clip.crop.x} max={32767} onChange={value => changeClip(track.id, clip.id, row => { if (row.crop) row.crop.x = value; })} />
              <NumberField label="源像素顶部" value={clip.crop.y} max={32767} onChange={value => changeClip(track.id, clip.id, row => { if (row.crop) row.crop.y = value; })} />
              <NumberField label="源裁剪宽度" value={clip.crop.width} min={1} max={32768} onChange={value => changeClip(track.id, clip.id, row => { if (row.crop) row.crop.width = value; })} />
              <NumberField label="源裁剪高度" value={clip.crop.height} min={1} max={32768} onChange={value => changeClip(track.id, clip.id, row => { if (row.crop) row.crop.height = value; })} /></>}</>}
        </details>}
        <details><summary>拆分、复制与移动</summary>
          <NumberField label="拆分位置（时间线毫秒）" value={clipEdits[clip.id]?.split ?? clip.start_ms + Math.floor(timelineClipDuration(clip) / 2)} min={clip.start_ms + 1} max={clip.start_ms + timelineClipDuration(clip) - 1} onChange={value => editControl(clip.id, { split: value })} />
          <Button disabled={clipsCount >= TIMELINE_LIMITS.clips} onClick={() => c.splitClip(track.id, clip.id, clipEdits[clip.id]?.split ?? clip.start_ms + Math.floor(timelineClipDuration(clip) / 2))}>在此位置拆分为两段</Button>
          <label>移动目标轨道<select value={clipEdits[clip.id]?.target ?? track.id} onChange={event => editControl(clip.id, { target: event.currentTarget.value })}>
            {draft.timeline.tracks.filter(row => row.kind === track.kind).map(row => <option key={row.id} value={row.id}>{row.kind === 'VIDEO' ? '视频' : '音频'} {row.order + 1}</option>)}
          </select></label>
          <NumberField label="复制或移动至（时间线毫秒）" value={clipEdits[clip.id]?.position ?? clip.start_ms + timelineClipDuration(clip)} max={draft.timeline.duration_ms - 1} onChange={value => editControl(clip.id, { position: value })} />
          <Button disabled={clipsCount >= TIMELINE_LIMITS.clips} onClick={() => c.duplicateClip(track.id, clip.id, clipEdits[clip.id]?.position ?? clip.start_ms + timelineClipDuration(clip))}>在原轨道复制片段</Button>
          <Button onClick={() => c.moveClip(track.id, clip.id, clipEdits[clip.id]?.target ?? track.id, clipEdits[clip.id]?.position ?? clip.start_ms + timelineClipDuration(clip))}>移动原片段至所选轨道</Button>
          <p>这些操作只改本地草稿，保留素材快照；同视频轨道仅允许已明确指定的相邻交叉溶解重叠，不能超出总长。拆分不调用模型，不生成新媒体。</p>
        </details>
        <Button variant="danger" onClick={() => changeTrack(track.id, row => { row.clips = row.clips.filter(value => value.id !== clip.id); })}>移除此片段</Button>
      </section>)}
      </fieldset>
    </fieldset>)}
    {videoTimeline && <fieldset disabled={locked}><legend>字幕（可选，作者输入的纯文字）</legend>
      <p>字幕不代表模型转录。每条一至八行，不接受空行、样式标记或文件路径。</p>
      <StudioTimelineCaptionStyle draft={draft} scope={props.client} disabled={locked} isCurrent={props.isCurrent} getRevision={c.getHandoffRevision}
        onApply={style => c.change(input => {
          if (input.timeline.schema_version !== 2) return;
          if (style === null) delete input.timeline.caption_style;
          else input.timeline.caption_style = style;
        })} />
      <Button disabled={videoTimeline.captions.length >= 500} onClick={() => c.change(input => { if (input.timeline.schema_version !== 3) input.timeline.captions.push({ start_ms: 0, end_ms: Math.min(1000, input.timeline.duration_ms), text: '' }); })}>添加字幕</Button>
      {videoTimeline.captions.map((cue, index) => <section key={index} aria-label={`字幕 ${index + 1}`}>
        <NumberField label={`字幕 ${index + 1} 开始（毫秒）`} value={cue.start_ms} max={draft.timeline.duration_ms - 1} onChange={value => c.change(input => { if (input.timeline.schema_version !== 3) input.timeline.captions[index].start_ms = value; })} />
        <NumberField label={`字幕 ${index + 1} 结束（毫秒）`} value={cue.end_ms} min={1} max={draft.timeline.duration_ms} onChange={value => c.change(input => { if (input.timeline.schema_version !== 3) input.timeline.captions[index].end_ms = value; })} />
        <label>字幕文字<textarea maxLength={1000} value={cue.text} onChange={event => { const text = event.currentTarget.value; c.change(input => { if (input.timeline.schema_version !== 3) input.timeline.captions[index].text = text; }); }} /></label>
        <Button variant="danger" onClick={() => c.change(input => { if (input.timeline.schema_version !== 3) input.timeline.captions.splice(index, 1); })}>移除此字幕</Button>
      </section>)}
    </fieldset>}
    <details><summary>时间布局（参数预览）</summary><p>这是裁剪、摆放和叠放参数，不是已经渲染的媒体预览。实际画面与声音请从原制作任务的私有候选中核对。</p>
      <table><thead><tr><th scope="col">轨道</th><th scope="col">素材版本</th><th scope="col">裁剪范围</th><th scope="col">时间线范围</th><th scope="col">状态</th></tr></thead>
        <tbody>{draft.timeline.tracks.flatMap(track => track.clips.map(clip => <tr key={clip.id}><th scope="row">{track.kind === 'VIDEO' ? '视频' : '音频'} {track.order + 1}</th>
          <td>{props.assets.find(asset => asset.id === clip.source_snapshot.id)?.filename ?? '不可用'} · v{clip.source_snapshot.version}</td>
          <td>{seconds(clip.in_ms)} — {seconds(clip.out_ms)}</td><td>{seconds(clip.start_ms)} — {seconds(clip.start_ms + timelineClipDuration(clip))}</td><td>{track.muted || clip.muted ? '隐藏或静音' : '参与渲染'}</td></tr>))}</tbody></table>
    </details>
    <p role="status">{c.inputDirty ? '未保存' : c.base ? `已读取或保存 v${c.base.version}` : '新时间线尚未保存'} · {draft.timeline.tracks.length} 条轨道 · {clipsCount} 个片段</p>
    <Button disabled={!c.canUndo} onClick={c.undo}>撤销本地编辑</Button><Button disabled={!c.canRedo} onClick={c.redo}>重做本地编辑</Button>
    <p>撤销与重做只在当前本地草稿中保留最多五十步，不回退已保存版本或原渲染、导出任务。</p>
    <Button variant="primary" loading={c.pending === 'SAVE'} disabled={locked || !c.inputDirty && !!c.base} onClick={() => void c.save()}>保存时间线</Button>
    {c.inputDirty && !c.failure && <><label><input type="checkbox" disabled={readLocked || c.attempt?.state === 'UNKNOWN'} checked={c.discardConfirmed} onChange={event => c.setDiscardConfirmed(event.currentTarget.checked)} />确认放弃本地未保存内容</label><Button disabled={readLocked || !c.discardConfirmed || c.attempt?.state === 'UNKNOWN'} onClick={c.discardDraft}>放弃本地编辑</Button></>}
    {c.base && !audioOnly && <section aria-label="确认本地时间线渲染"><h3>本地渲染</h3>
      <p>绑定已保存 v{c.base.version}。不调用模型；输出 MP4，画面与音频按原渲染服务处理，素材保留原样。</p>
      <details><summary>当前保存摘要</summary><code>{c.base.timeline_digest}</code></details>
      {!c.sourcesCurrent && <StatusMessage tone="warning">素材有变化或不可用，请重新选择对应素材并保存新版本。</StatusMessage>}
      <label><input type="checkbox" checked={c.confirmed} disabled={locked || c.inputDirty || !c.sourcesCurrent || !!c.attempt && c.attempt.state === 'UNKNOWN'} onChange={event => c.setConfirmed(event.currentTarget.checked)} />已核对当前版本、摘要、裁剪、叠放、音量和字幕，确认生成私有渲染候选</label>
      <Button loading={c.pending === 'RENDER'} disabled={!c.canRender} onClick={() => void c.render()}>明确渲染此保存版本</Button>
    </section>}
    <StudioTimelineExportPanel controller={c} />
    {!audioOnly && <StudioTimelineTransferPanel controller={c.transfer} assets={props.assets} onLocate={(preview, path) => {
      const now = latestReview.current;
      if (now.c !== c || now.props.client !== props.client || !props.isCurrent() || composing.current || readLocked
        || props.isBusy?.() || c.getHandoffRevision() !== reviewGeneration
        || !c.transfer.isCurrentPreview(preview) || c.transfer.preview !== preview || c.inputDirty || !c.base
        || preview.timeline_snapshot.id !== c.base.id || preview.timeline_snapshot.version !== c.base.version
        || preview.timeline_snapshot.digest !== c.base.timeline_digest || c.attempt?.state === 'UNKNOWN') return;
      const target = transferClipTarget(preview, path);
      if (!target) return;
      const currentTrack = draft.timeline.tracks.find(track => track.id === target.track.id);
      const currentClip = currentTrack?.clips.find(clip => clip.id === target.clip.id);
      if (!currentClip || JSON.stringify(currentClip) !== JSON.stringify(target.clip)) return;
      const element = clipElements.current.get(target.clip.id);
      if (!element?.isConnected) return;
      element.focus(); element.scrollIntoView?.({ block: 'nearest' });
      selectClips([target.clip.id]); selectPlayhead(target.clip.start_ms);
    }} />}
    <StudioTimelinePlaybackPanel controller={c.playback} />
    {c.attempt && <StatusMessage tone={c.attempt.state === 'UNKNOWN' ? 'warning' : 'info'}>{c.attempt.state === 'UNKNOWN' ? '渲染或导出结果仍需核对，请从制作任务读取原回执；不会再次发送此请求。' : '此快照与配置的请求已有回执，不会从这里重复发起。'} 原请求：<code>{c.attempt.requestId}</code>{c.attempt.exportProfile && <> · 导出 {c.attempt.exportProfile.preset}</>}</StatusMessage>}
    {c.attempt && <StudioTimelineMeasurement measurement={c.attempt.measurement} />}
    {c.attempt && <Button disabled={readLocked} loading={c.pending === 'JOB'} onClick={() => void c.checkRenderJob()}>读取此请求的原渲染或导出回执</Button>}
    <p>这些入口已接入原 owner，当前代码的 Windows、媒体和完整产品验证仍待执行。</p>
    {c.measuredSourceCount > 0 && <StatusMessage>已保留 {c.measuredSourceCount} 个当前来源的实测长度；新改的素材入出范围超界时，本地编辑会拒绝。未测来源仍是未知，最终保存与渲染由原服务核对。</StatusMessage>}
    {nleNotice && <StatusMessage tone="warning">{nleNotice}</StatusMessage>}
    <section aria-label="音频源时长核对"><Button disabled={!sourceBounds.canRequest} onClick={()=>void sourceBounds.request()}>核对所选音频源时长</Button><p>仅支持当前保存片段的 PCM16 WAV（8 MiB、十分钟内）。核对实际源采样长度；不修改裁剪、不保存、不执行渲染。</p>
      {sourceBounds.unavailable&&<p>{sourceBounds.unavailable}</p>}{sourceBounds.pending&&<StatusMessage>正在核对源文件长度…</StatusMessage>}{sourceBounds.error&&<StatusMessage tone="warning">{sourceBounds.error}</StatusMessage>}
      {sourceBounds.preview&&<StatusMessage tone={sourceBounds.preview.within_source?'info':'warning'}>源文件 {sourceBounds.preview.frame_count} 帧 / {sourceBounds.preview.sample_rate} Hz；整数毫秒出点最多 {sourceBounds.preview.maximum_out_ms} ms。{sourceBounds.preview.within_source?'当前源入出范围在实测长度内。':'当前保存的源入出范围越界，请手动调整后重新保存。'} 此结果只说明源时长，不代表全时间线验收。</StatusMessage>}
      {sourceBounds.preview&&c.base&&<StudioTimelineSourceBoundsRepair scope={props.client} source={c.base} draft={draft} observation={sourceBounds.preview} disabled={!sourceBounds.canRequest} isCurrent={props.isCurrent} getRevision={c.getHandoffRevision} onApply={next=>{const applied=c.change(input=>{input.timeline=next.timeline;});if(applied)setNleNotice('已按实测长度收短本地草稿出点，可撤销；尚未保存或渲染。');return applied;}}/>}
    </section>
    <TimelineClipLinkPanel timeline={draft.timeline} selectedClipIds={nleClips} editable={c.canEdit && c.sourcesCurrent}
      onLink={() => {
        const live = latestReview.current;
        if (live.props.client === props.client && live.c.getHandoffRevision() === reviewGeneration
          && selection.current.generation === selectionGeneration && live.props.isCurrent()
          && JSON.stringify(selection.current.ids) === JSON.stringify(nleClips)) live.c.linkClips(nleClips);
      }} onUnlink={() => {
        const live = latestReview.current;
        if (live.props.client === props.client && live.c.getHandoffRevision() === reviewGeneration
          && selection.current.generation === selectionGeneration && live.props.isCurrent()
          && JSON.stringify(selection.current.ids) === JSON.stringify(nleClips)) live.c.unlinkClips(nleClips);
      }} />
    <LinkedClipSplitPanel timeline={draft.timeline} selectedClipIds={nleClips} videoAtMs={nlePlayhead}
      ready={c.canEdit && c.sourcesCurrent && !!c.base && !c.inputDirty} onSplit={() => {
        const live = latestReview.current;
        if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
          || selection.current.generation !== selectionGeneration || playhead.current.generation !== playheadGeneration
          || !live.props.isCurrent() || !live.c.canEdit || live.c.inputDirty || !live.c.base
          || JSON.stringify(selection.current.ids) !== JSON.stringify(nleClips)) return;
        live.c.splitLinkedClips(nleClips, nlePlayhead, { video: crypto.randomUUID(), audio: crypto.randomUUID() });
      }} />
    <TimelineWorkspacePanel documentId={c.base?.id} projectId={props.projectId || ''} identity={props.projectId || ''} timeline={draft.timeline}
      selectedClipIds={nleClips} playheadMs={nlePlayhead} viewStartMs={nleView.startMs} viewScale={nleView.scale}
      editable={c.canEdit} onSelectClips={selectClips} onPlayhead={selectPlayhead}
      isSplitReviewCurrent={() => {
        const live = latestReview.current;
        return live.props.client === props.client && live.c.getHandoffRevision() === reviewGeneration
          && selection.current.generation === selectionGeneration && playhead.current.generation === playheadGeneration
          && playhead.current.value === nlePlayhead && live.props.isCurrent() && live.c.canEdit && !live.props.busy
          && !live.props.isBusy?.() && JSON.stringify(selection.current.ids) === JSON.stringify(nleClips);
      }}
      onView={next => setNleView({ startMs: next.startMs, scale: next.scale })}
      exportReceipt={c.exportPreview} limits={{ duration_ms: TIMELINE_LIMITS.duration, tracks: audioOnly ? TIMELINE_LIMITS.kindTracks : TIMELINE_LIMITS.tracks,
        tracks_per_kind: TIMELINE_LIMITS.kindTracks, clips: TIMELINE_LIMITS.clips, ...(audioOnly ? {} : { captions: TIMELINE_LIMITS.captions, caption_characters: TIMELINE_LIMITS.captionCharacters }) }}
      waveform={{ ...waveform, source: c.base, onRequest: () => void waveform.request() }}
      onEdit={command => {
        if (command.kind === 'clip.remove' && Array.isArray(command.payload)) {
          const live = latestReview.current;
          if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
            || selection.current.generation !== selectionGeneration || !live.props.isCurrent()
            || !live.c.canEdit || live.props.busy || live.props.isBusy?.()
            || JSON.stringify(selection.current.ids) !== JSON.stringify(nleClips)) return;
          try {
            const preview = selectionRemovePreview(draft.timeline, nleClips);
            if (!sameSelectionRemoveDescriptors(command.payload, preview.operations)) {
              throw new Error('删除必须完整对应当前选择，且每项均为保留间隙的原 clip.remove 指令。');
            }
            const applied = live.c.change(input => { input.timeline = preview.timeline; });
            if (applied) selectClips([]);
            setNleNotice(applied ? '所选片段已删除并保留间隙；一次撤销可恢复，明确保存前不会写入服务端。'
              : '所选删除未应用，请重新核对当前编辑状态。');
          } catch (reason) { setNleNotice(reason instanceof Error ? reason.message : '所选删除未应用。'); }
          return;
        }
        if (['caption.insert', 'caption.update', 'caption.remove'].includes(command.kind)) {
          if (audioOnly) return;
          const live = latestReview.current;
          if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
            || !live.props.isCurrent() || !live.c.canEdit || live.props.busy) return;
          try {
            const next = applyNleCaptionCommand(draft, command.kind, command.payload);
            const applied = live.c.change(value => { if (value.timeline.schema_version !== 3) value.timeline.captions = next.timeline.captions; });
            setNleNotice(applied ? '字幕编辑已应用到本地时间线；可撤销，明确保存前不会写入服务端。' : '字幕编辑未应用，请核对当前编辑状态。');
          } catch (reason) { setNleNotice(reason instanceof Error ? reason.message : '字幕编辑未应用。'); }
          return;
        }
        if (command.kind === 'clip.update' && command.payload && typeof command.payload === 'object'
          && 'changes' in command.payload && command.payload.changes && typeof command.payload.changes === 'object'
          && Object.hasOwn(command.payload.changes, 'color_adjustment')) {
          const live = latestReview.current;
          if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
            || selection.current.generation !== selectionGeneration || !live.props.isCurrent()
            || !live.c.canEdit || live.props.busy || JSON.stringify(selection.current.ids) !== JSON.stringify(nleClips)) return;
          try {
            const next = applyClipColorOperation(draft.timeline, nleClips, command.payload);
            const applied = live.c.change(input => { input.timeline = next; });
            setNleNotice(applied ? '基础调色已应用到本地草稿，可撤销；尚未保存或渲染。' : '调色参数未改变，或当前编辑状态不允许应用。');
          } catch (reason) { setNleNotice(reason instanceof Error ? reason.message : '基础调色未应用。'); }
          return;
        }
        if (command.kind === 'clip.update') {
          const live = latestReview.current;
          if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
            || selection.current.generation !== selectionGeneration || !live.props.isCurrent()
            || JSON.stringify(selection.current.ids) !== JSON.stringify(nleClips)) return;
          if (!live.c.sourceEdit.canPrepare || live.c.inputDirty || !live.c.base || live.c.sourceEdit.dirty) {
            setNleNotice('先保存时间线草稿，并完成或清空现有正式素材操作，再准备替换。'); return;
          }
          try {
            const intent = nleSourceReplacementIntent(draft.timeline, nleClips, live.props.assets, command.payload);
            live.c.sourceEdit.change(intent); setSourceEditReveal(value => value + 1);
            setNleNotice('已填入原“正式素材加入与替换”面板。请核对范围、预览，再明确保存；尚未替换素材或发送请求。');
          } catch (reason) { setNleNotice(reason instanceof Error ? reason.message : '素材替换未准备，请核对原片段与素材版本。'); }
          return;
        }
        if (command.kind === 'clip.split') {
          const live = latestReview.current;
          if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
            || selection.current.generation !== selectionGeneration || playhead.current.generation !== playheadGeneration
            || playhead.current.value !== nlePlayhead || !live.props.isCurrent() || !live.c.canEdit || live.props.busy
            || JSON.stringify(selection.current.ids) !== JSON.stringify(nleClips)) return;
          try {
            if (!Array.isArray(command.payload)) throw new Error('拆分必须完整对应当前选择与播放头预览。');
            const operations = command.payload;
            const ids = Object.freeze(Object.fromEntries(operations.map(operation => [operation?.clip_id, operation?.new_clip_id])));
            const expected = selectionSplitOperations(draft.timeline, nleClips, nlePlayhead, ids);
            if (!sameSelectionSplitDescriptors(operations, expected)) throw new Error('已拒绝额外、遗漏或不匹配的拆分指令。');
            const applied = live.c.splitSelection(nleClips, nlePlayhead, ids);
            setNleNotice(applied ? '所选片段已在精确播放头拆分；一次撤销可恢复，保存前不会写入服务端。' : '拆分未应用，请重新核对当前编辑状态。');
          } catch (reason) { setNleNotice(reason instanceof Error ? reason.message : '拆分未应用。'); }
          return;
        }
        if (command.kind === 'clip.duplicate' && Array.isArray(command.payload)) {
          const live = latestReview.current;
          if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
            || selection.current.generation !== selectionGeneration || !live.props.isCurrent()
            || JSON.stringify(selection.current.ids) !== JSON.stringify(nleClips)) return;
          try {
            const operations = command.payload;
            const first = operations[0];
            const original = draft.timeline.tracks.flatMap(row => row.clips).find(clip => clip.id === first?.clip_id);
            if (!original || typeof first.start_ms !== 'number') throw new Error('缺少原片段或整体复制位置。');
            const offset = first.start_ms - original.start_ms;
            const copies = operations.slice(0, nleClips.length);
            if (copies.some(operation => !operation || typeof operation !== 'object' || operation.op !== 'clip.duplicate')) {
              throw new Error('整体复制必须包含当前选择的全部复制指令。');
            }
            const newIds = Object.freeze(Object.fromEntries(copies.map(operation => [operation.clip_id, operation.new_clip_id])));
            const expected = selectionDuplicateOperations(draft.timeline, nleClips, offset, newIds);
            if (!sameSelectionDuplicateDescriptors(operations, expected)) throw new Error('整体复制必须完整对应当前选择、原轨道、同一增量与内部转场。');
            const applied = c.duplicateSelection(nleClips, offset, newIds);
            setNleNotice(applied ? '整体复制已应用到本地草稿；一次撤销可恢复，保存前不会写入服务端。'
              : '整体复制未应用；请核对增量、原轨道约束与当前编辑状态。');
          } catch (reason) { setNleNotice(reason instanceof Error ? reason.message : '已拒绝无效的整体复制批次。'); }
          return;
        }
        // An array is an explicit batch of existing clip.move descriptors, never a new backend operation.
        if (command.kind === 'clip.move' && Array.isArray(command.payload)) {
          const live = latestReview.current;
          if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
            || selection.current.generation !== selectionGeneration || !live.props.isCurrent()
            || JSON.stringify(selection.current.ids) !== JSON.stringify(nleClips)) return;
          try {
            const operations = command.payload;
            const first = operations[0];
            const original = draft.timeline.tracks.flatMap(row => row.clips).find(clip => clip.id === first?.clip_id);
            if (!original || typeof first.start_ms !== 'number') throw new Error('缺少原片段或整体移动位置。');
            const offset = first.start_ms - original.start_ms;
            const expected = selectionMoveOperations(draft.timeline, nleClips, offset);
            if (operations.length !== expected.length || operations.some((operation, index) =>
              !operation || typeof operation !== 'object' || Array.isArray(operation)
              || Object.keys(operation).length !== 4 || Object.keys(operation).some(key => !['op', 'clip_id', 'track_id', 'start_ms'].includes(key))
              || Object.entries(expected[index]).some(([key, value]) => operation[key] !== value))) {
              throw new Error('整体移动必须完整对应当前选择、原轨道与同一增量。');
            }
            const applied = c.moveSelection(nleClips, offset);
            setNleNotice(applied ? '整体移动已应用到本地草稿；一次撤销可恢复，保存前不会写入服务端。'
              : '整体移动未应用；请核对增量、原轨道约束与当前编辑状态。');
          } catch (reason) { setNleNotice(reason instanceof Error ? reason.message : '已拒绝无效的整体移动批次。'); }
          return;
        }
        // Field names come from the mapper's REAL payloads (nle/timelineOps.ts):
        // clip.split {at_ms}, clip.duplicate/clip.move {start_ms, track_id}.
        const payload = command.payload as { op?: string; clip_id?: string; at_ms?: number; start_ms?: number; track_id?: string; in_ms?: number; out_ms?: number; offset_ms?: number; ripple?: boolean } | undefined;
        const clipId = payload?.clip_id;
        const position = payload?.start_ms;
        const track = clipId ? draft.timeline.tracks.find(row => row.clips.some(clip => clip.id === clipId)) : undefined;
        // Trim has source in/out points, not a timeline position. Route it before
        // the position-only operations and bind it to the reviewed live context.
        if (command.kind === 'clip.trim') {
          const live = latestReview.current;
          if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
            || JSON.stringify(live.nleClips) !== JSON.stringify(nleClips) || !props.isCurrent()) return;
          const firstSelected = draft.timeline.tracks.flatMap(row => row.clips).find(clip => nleClips.includes(clip.id));
          if (!clipId || !track || firstSelected?.id !== clipId || payload?.op !== 'clip.trim'
            || typeof payload.in_ms !== 'number' || typeof payload.out_ms !== 'number' || typeof payload.ripple !== 'boolean') {
            setNleNotice('已拒绝裁剪：请重新选择原片段并填写整数毫秒入出点。'); return;
          }
          const applied = c.trimClip(track.id, clipId, payload.in_ms, payload.out_ms, payload.ripple);
          setNleNotice(applied ? '裁剪已应用到本地草稿；波纹仅影响本轨道，保存前不会写入服务端。' : '裁剪未应用；请核对输入、轨道约束与当前编辑状态。');
          return;
        }
        if (command.kind === 'clip.slip' || command.kind === 'clip.remove') {
          const live = latestReview.current;
          if (live.props.client !== props.client || live.c.getHandoffRevision() !== reviewGeneration
            || JSON.stringify(live.nleClips) !== JSON.stringify(nleClips) || !props.isCurrent()) return;
          const firstSelected = draft.timeline.tracks.flatMap(row => row.clips).find(clip => nleClips.includes(clip.id));
          const keys = command.kind === 'clip.slip' ? ['op', 'clip_id', 'offset_ms'] : ['op', 'clip_id', 'ripple'];
          if (!clipId || !track || firstSelected?.id !== clipId || payload?.op !== command.kind
            || Object.keys(payload).length !== keys.length || Object.keys(payload).some(key => !keys.includes(key))
            || (command.kind === 'clip.slip' ? !Number.isSafeInteger(payload.offset_ms) : payload.ripple !== true)) {
            setNleNotice('已拒绝该编辑：请核对所选片段、整数滑移增量或明确的波纹删除确认。'); return;
          }
          const applied = command.kind === 'clip.slip' ? c.slipClip(track.id, clipId, payload.offset_ms!)
            : c.rippleRemoveClip(track.id, clipId, payload.ripple!);
          setNleNotice(applied ? '片段编辑已应用到本地草稿；保存前不会写入服务端。' : '片段编辑未应用；请核对输入、轨道约束与当前编辑状态。');
          return;
        }
        if (!clipId || !track || typeof position !== 'number') {
          setNleNotice('已拒绝该编辑：缺少原 owner 需要的片段或位置；未执行任何更改。');
          return;
        }
        if (command.kind === 'clip.duplicate') { c.duplicateClip(track.id, clipId, position); setNleNotice('已按原 owner 的 duplicate 语义应用到本地草稿。'); return; }
        if (command.kind === 'clip.move' && payload?.track_id) { c.moveClip(track.id, clipId, payload.track_id, position); setNleNotice('已按原 owner 的 move 语义应用到本地草稿。'); return; }
        setNleNotice(`该编辑（${command.kind}）由原 owner 支持，但当前工作台尚未接线到控制器；未执行任何更改。`);
      }} />
  </Panel>;
}
