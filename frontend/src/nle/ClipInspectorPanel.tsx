import { selectionDuplicateOperations, selectionDuplicateTargets } from './timelineSelectionDuplicate';
import { selectionMoveOperations } from './timelineSelectionMove';
import { useEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { editCommand, safeTimeline, selectedClipFacts, snapCandidates, snapClipStart } from './timelineOps';
import type { NleEditRequest, NleMarks, NleRefusal } from './timelineOpsTypes';
import './timelineWorkspace.css';

type Outcome = { kind: 'IDLE' } | { kind: 'OK'; op: string; bytes: number } | { kind: 'REFUSED'; refusal: NleRefusal };

const ACTIONS = [
  ['split', '拆分（clip.split）'],
  ['trim', '裁剪（clip.trim）'],
  ['move', '移动（clip.move）'],
  ['copy', '复制（clip.duplicate）'],
  ['slip', '滑移（clip.slip）'],
  ['ripple', '波纹删除（clip.remove, ripple）'],
  ['source-replace', '替换素材（clip.update → source_snapshot）'],
  ['speed', '速度调整（原服务无此动作，将明确拒绝）'],
  ['grade', '调色（本工作包不支持，将明确拒绝）'],
] as const;

const numeric = (value: string): number => value.trim() === '' ? Number.NaN : Number(value);

/**
 * 片段属性面板：属性只显示已校验时间线中的事实。
 * 每个动作先生成原编辑服务的操作描述符；被拒绝时**只显示原因，不调用 onEdit**。
 */
export type ClipInspectorPanelProps = {
  timeline: unknown;
  selectedClipIds: string[];
  playheadMs: number;
  marks: NleMarks;
  editable: boolean;
  newId?: () => string;
  onEdit: (command: NleEditRequest) => void;
};

export function ClipInspectorPanel(props: ClipInspectorPanelProps) {
  const inputGeneration = useRef(0);
  const reviewedInputGeneration = inputGeneration.current;
  const authored = (work: () => void) => { inputGeneration.current++; work(); };
  const [duplicateOffset, setDuplicateOffset] = useState('');
  const [duplicateOutcome, setDuplicateOutcome] = useState('');
  const duplicateConsumed = useRef('');
  const [selectionOffset, setSelectionOffset] = useState('');
  const [selectionOutcome, setSelectionOutcome] = useState('');
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; inputGeneration.current++; }; }, []);
  const [kind, setKind] = useState<string>('split');
  const [atMs, setAtMs] = useState(''), [inMs, setInMs] = useState(''), [outMs, setOutMs] = useState('');
  const [startMs, setStartMs] = useState(''), [offsetMs, setOffsetMs] = useState('');
  const [targetTrackId, setTargetTrackId] = useState('');
  const [ripple, setRipple] = useState(false);
  const [assetId, setAssetId] = useState(''), [assetVersion, setAssetVersion] = useState(''), [assetDigest, setAssetDigest] = useState('');
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'IDLE' });

  const parsed = safeTimeline(props.timeline);
  const facts = parsed.ok ? selectedClipFacts(parsed.timeline, props.selectedClipIds) : [];
  const first = facts[0];
  const selectionKey = JSON.stringify([props.selectedClipIds, first?.trackId, first?.clip]);
  const contextKey = JSON.stringify([selectionKey, props.timeline]);
  const contextGeneration = useRef({ key: contextKey, editable: props.editable, generation: 0 });
  if (contextGeneration.current.key !== contextKey || contextGeneration.current.editable !== props.editable) {
    contextGeneration.current = { key: contextKey, editable: props.editable, generation: contextGeneration.current.generation + 1 };
  }
  const reviewedContextGeneration = contextGeneration.current.generation;
  const latestContext = useRef({ contextKey, editable: props.editable });
  latestContext.current = { contextKey, editable: props.editable };
  useEffect(() => {
    // Do not carry authored trim/slip points or ripple consent to a different target.
    // Ordinary rerenders keep the semantic key and preserve in-progress input.
    inputGeneration.current++;
    setSelectionOffset(''); setSelectionOutcome(''); setInMs(''); setOutMs(''); setOffsetMs(''); setRipple(false); setOutcome({ kind: 'IDLE' });
  }, [selectionKey]);
  useEffect(() => { setSelectionOffset(''); setSelectionOutcome(''); setDuplicateOffset(''); setDuplicateOutcome(''); }, [contextKey]);
  if (!parsed.ok) {
    return <section className="nle-clip" aria-label="片段属性"><StatusMessage tone="error">{parsed.message}</StatusMessage>
      <EmptyState title="片段属性不可用" detail="需要一份通过原时间线契约校验的时间线。" /></section>;
  }
  const timeline = parsed.timeline;
  const snaps = snapCandidates({ timeline, playheadMs: props.playheadMs, marks: props.marks, selectedClipIds: props.selectedClipIds });
  const sameKindTracks = first ? timeline.tracks.filter(track => track.kind === first.trackKind) : [];
  const reset = () => {
    if (!first) return;
    inputGeneration.current++;
    setAtMs(String(Math.min(timeline.duration_ms - 1, first.startMs + Math.floor(first.durationMs / 2))));
    setInMs(String(first.clip.in_ms)); setOutMs(String(first.clip.out_ms));
    setStartMs(String(Math.min(timeline.duration_ms - 1, first.endMs)));
    setOffsetMs('0'); setTargetTrackId(first.trackId);
    setAssetId(first.clip.source_snapshot.id); setAssetVersion(String(first.clip.source_snapshot.version));
    setAssetDigest(first.clip.source_snapshot.digest); setRipple(false);
  };
  const generateSelectionDuplicate = () => {
    const consent = `${reviewedInputGeneration}:${reviewedContextGeneration}`;
    if (!alive.current || !latestContext.current.editable || inputGeneration.current !== reviewedInputGeneration
      || contextGeneration.current.generation !== reviewedContextGeneration || duplicateConsumed.current === consent) return;
    duplicateConsumed.current = consent;
    try {
      const offset = numeric(duplicateOffset);
      selectionDuplicateTargets(timeline, props.selectedClipIds, offset);
      const newIds = Object.freeze(Object.fromEntries(props.selectedClipIds.map(id =>
        [id, (props.newId ?? (() => globalThis.crypto.randomUUID()))()])));
      const operations = selectionDuplicateOperations(timeline, props.selectedClipIds, offset, newIds);
      props.onEdit({ kind: 'clip.duplicate', payload: operations });
      setDuplicateOutcome(`已生成 ${props.selectedClipIds.length} 个复制片段、${operations.length} 项原编辑指令；应用结果见时间线提示，仍需明确保存。`);
    } catch (reason) {
      setDuplicateOutcome(`${reason instanceof Error ? reason.message : '整体复制输入无效。'} 请修改输入后再明确尝试。`);
    }
  };
  const generateSelectionMove = () => {
    if (!alive.current || !latestContext.current.editable || inputGeneration.current !== reviewedInputGeneration
      || contextGeneration.current.generation !== reviewedContextGeneration) return;
    try {
      const operations = selectionMoveOperations(timeline, props.selectedClipIds, numeric(selectionOffset));
      props.onEdit({ kind: 'clip.move', payload: operations });
      setSelectionOutcome(`已生成 ${operations.length} 项原 clip.move 指令；应用结果见时间线提示，仍需明确保存。`);
    } catch (reason) { setSelectionOutcome(reason instanceof Error ? reason.message : '整体移动输入无效。'); }
  };
  const generate = () => {
    if (inputGeneration.current !== reviewedInputGeneration || !first || !latestContext.current.editable || latestContext.current.contextKey !== contextKey) return;
    const context: Record<string, unknown> = {
      timeline, clipId: first.clip.id, atMs: numeric(atMs), inMs: numeric(inMs), outMs: numeric(outMs),
      startMs: numeric(startMs), offsetMs: numeric(offsetMs), ripple,
      ...(targetTrackId ? { targetTrackId } : {}),
    };
    if (kind === 'split' || kind === 'copy') {
      context.newClipId = (props.newId ?? (() => globalThis.crypto.randomUUID()))();
    }
    if (kind === 'source-replace') {
      context.sourceSnapshot = { id: assetId, kind: 'ASSET', asset_kind: first.sourceKind, version: numeric(assetVersion), digest: assetDigest };
    }
    // Ruler marks describe timeline time, never verified source-media bounds.
    const plan = editCommand(kind, context);
    if (!plan.ok) { setOutcome({ kind: 'REFUSED', refusal: plan }); return; }
    props.onEdit({ kind: plan.op, payload: plan.payload });
    setOutcome({ kind: 'OK', op: plan.op, bytes: plan.batchBytes });
  };

  return <section className="nle-clip" aria-label="片段属性">
    <h3>片段属性</h3>
    {!facts.length && <EmptyState title="尚未选择片段" detail="请在上方轨道头或时间线上选择一个片段。" />}
    {first && <>
      <dl className="nle-clip__facts">
        <div><dt>片段</dt><dd><code>{first.clip.id}</code></dd></div>
        <div><dt>轨道</dt><dd>{first.trackKind === 'VIDEO' ? '视频' : '音频'} <code>{first.trackId}</code></dd></div>
        <div><dt>时间线范围</dt><dd>{first.startMs} — {first.endMs} 毫秒（{first.durationMs} 毫秒）</dd></div>
        <div><dt>素材裁剪</dt><dd>{first.clip.in_ms} — {first.clip.out_ms} 毫秒</dd></div>
        <div><dt>速度</dt><dd>{first.speedNum} / {first.speedDen}</dd></div>
        <div><dt>素材</dt><dd>{first.sourceKind} · v{first.clip.source_snapshot.version} · <code>{first.clip.source_snapshot.digest}</code></dd></div>
      </dl>
      {facts.length > 1 && <Badge tone="info">已选择 {facts.length} 个片段；下方整体移动与整体复制作用于全部选择，其他动作仍针对第一个片段</Badge>}
      <div className="nle-clip__form">
        <label>整体移动增量（毫秒，可为负）<input type="number" step={1} value={selectionOffset} aria-label="整体移动增量（毫秒，可为负）"
          onChange={event => authored(() => setSelectionOffset(event.currentTarget.value))} /></label>
      </div>
      <Button disabled={!props.editable} onClick={generateSelectionMove}>整体移动所选片段</Button>
      <p>整体移动保持各自原轨道与相对间距，不移动未选片段或字幕，不改变时间线总长；一次撤销可恢复。</p>
      {selectionOutcome && <StatusMessage tone="info">{selectionOutcome}</StatusMessage>}
      <div className="nle-clip__form">
        <label>整体复制增量（毫秒，可为负或零）<input type="number" step={1} value={duplicateOffset} aria-label="整体复制增量（毫秒，可为负或零）"
          onChange={event => authored(() => setDuplicateOffset(event.currentTarget.value))} /></label>
      </div>
      <Button disabled={!props.editable} onClick={generateSelectionDuplicate}>整体复制所选片段</Button>
      <p>复制 {facts.length} 个所选片段到各自原轨道，保持相对间距；仅复制两端均已选择的内部转场，不复制通向未选片段的转场。原片段、字幕与时间线总长不变；一次撤销可恢复。</p>
      {duplicateOutcome && <StatusMessage tone="info">{duplicateOutcome}</StatusMessage>}
      <p className="nle-clip__snap">吸附候选只来自真实边界：片段开始、片段结束、播放头与已设置的入/出点。播放头 {props.playheadMs} 毫秒。</p>
      <p className="nle-clip__snap" data-snap-count={snaps.candidates.length}>
        当前候选 {snaps.candidates.length} 个 · 容差 {snaps.toleranceMs} 毫秒
        {snapClipStart(timeline, first.clip, first.startMs + 1, snaps).snapped ? ' · 片段起点会被吸附到真实边界' : ' · 片段起点无需吸附'}
      </p>
      <div className="nle-clip__form">
        <label>请求的动作<select aria-label="请求的动作" value={kind} onChange={event => authored(() => setKind(event.currentTarget.value))}>
          {ACTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label>拆分位置（毫秒）<input type="number" step={1} value={atMs} aria-label="拆分位置（毫秒）" onChange={event => authored(() => setAtMs(event.currentTarget.value))} /></label>
        <label>裁剪入点（毫秒）<input type="number" step={1} value={inMs} aria-label="裁剪入点（毫秒）" onChange={event => authored(() => setInMs(event.currentTarget.value))} /></label>
        <label>裁剪出点（毫秒）<input type="number" step={1} value={outMs} aria-label="裁剪出点（毫秒）" onChange={event => authored(() => setOutMs(event.currentTarget.value))} /></label>
        <label>摆放或复制位置（毫秒）<input type="number" step={1} value={startMs} aria-label="摆放或复制位置（毫秒）" onChange={event => authored(() => setStartMs(event.currentTarget.value))} /></label>
        <label>滑移增量（毫秒，可为负）<input type="number" step={1} value={offsetMs} aria-label="滑移增量（毫秒）" onChange={event => authored(() => setOffsetMs(event.currentTarget.value))} /></label>
        <label>目标轨道<select aria-label="目标轨道" value={targetTrackId} onChange={event => authored(() => setTargetTrackId(event.currentTarget.value))}>
          <option value={first.trackId}>原轨道</option>
          {sameKindTracks.filter(track => track.id !== first.trackId).map(track => <option key={track.id} value={track.id}>{track.kind === 'VIDEO' ? '视频' : '音频'} {track.order + 1}</option>)}
        </select></label>
        <label className="nle-clip__check"><input type="checkbox" checked={ripple} aria-label="波纹闭合间隙" onChange={event => authored(() => setRipple(event.currentTarget.checked))} />波纹动作时明确闭合间隙</label>
        <p>裁剪时勾选波纹，只按时长变化移动本轨道中从原片段终点开始的后续片段；其他轨道与字幕保持原位。</p>
        <p>滑移只改变素材入出点；波纹删除只移动本轨道从原片段终点起的后续片段，其他轨道与字幕保持原位。</p>
        <p>此面板中尚未生成编辑指令的输入不会成为时间线草稿，离开页面不会保护这些未应用输入。</p>
        <p>保存不会证明素材实际时长；实际素材入出点范围仍由原渲染服务读取媒体后校验。</p>
        <label>替换素材标识<input type="text" value={assetId} aria-label="替换素材标识" onChange={event => authored(() => setAssetId(event.currentTarget.value))} /></label>
        <label>替换素材版本<input type="number" step={1} value={assetVersion} aria-label="替换素材版本" onChange={event => authored(() => setAssetVersion(event.currentTarget.value))} /></label>
        <label>替换素材摘要<input type="text" value={assetDigest} aria-label="替换素材摘要" onChange={event => authored(() => setAssetDigest(event.currentTarget.value))} /></label>
      </div>
      <div className="nle-clip__actions">
        <Button disabled={!props.editable} onClick={reset}>以所选片段填入默认值</Button>
        <Button variant="primary" disabled={!props.editable} onClick={generate}>生成编辑指令</Button>
      </div>
      {outcome.kind === 'REFUSED' && <div data-refusal-code={outcome.refusal.code}>
        <StatusMessage tone="error">
          已拒绝（{outcome.refusal.code}）：{outcome.refusal.message} 没有向原服务发送任何指令。
        </StatusMessage>
      </div>}
      {outcome.kind === 'OK' && <div data-operation={outcome.op}>
        <StatusMessage tone="success">
          已生成原编辑服务操作 {outcome.op}（约 {outcome.bytes} 字节）。仅生成描述符；保存与版本递增仍由原服务决定。
        </StatusMessage>
      </div>}
    </>}
  </section>;
}
