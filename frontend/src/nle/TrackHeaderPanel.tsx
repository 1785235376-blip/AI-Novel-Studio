import { useId, useLayoutEffect, useRef } from 'react';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { safeTimeline, trackHeaderState } from './timelineOps';
import type { NleTrackHeaderState } from './timelineOpsTypes';
import { normalizeClipSelection, sameClipSelection, toggleClipSelection } from './clipSelection';
import './timelineWorkspace.css';

const KIND_LABEL = { VIDEO: '视频', AUDIO: '音频' } as const;
const ROLE_LABEL: Record<string, string> = {
  PRIMARY: '主要画面', OVERLAY: '叠加画面', DIALOGUE: '对白', MUSIC: '音乐', EFFECTS: '音效',
};

/** 轨道头面板：锁、静音、增益与片段计数全部来自给定时间线，不推断任何状态。 */
export type TrackHeaderPanelProps = {
  timeline: unknown;
  documentId?: string;
  selectedClipIds: string[];
  editable: boolean;
  onSelectClips: (ids: string[]) => void;
};

export function TrackHeaderPanel(props: TrackHeaderPanelProps) {
  const parsed = safeTimeline(props.timeline);
  const clipOrder = parsed.ok ? parsed.timeline.tracks.flatMap(track => track.clips.map(clip => clip.id)) : [];
  const previousDocument = useRef(props.documentId);
  const documentChanged = previousDocument.current !== props.documentId;
  const selectedIds = documentChanged ? [] : normalizeClipSelection(props.selectedClipIds, clipOrder);
  const hintId = useId(), alive = useRef(true), composing = useRef<HTMLElement | null>(null);
  const selectionKey = Array.isArray(props.selectedClipIds) ? props.selectedClipIds.filter(id => typeof id === 'string') : [];
  const contextKey = JSON.stringify([props.documentId, parsed.ok ? parsed.timeline : null, props.editable, selectionKey]);
  const context = useRef({ key: contextKey, generation: 0 });
  if (context.current.key !== contextKey) {
    context.current = { key: contextKey, generation: context.current.generation + 1 };
  }
  const generation = context.current.generation;
  const latest = useRef(props); latest.current = props;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; composing.current = null; }; }, []);
  useLayoutEffect(() => {
    // Generation changes retire callbacks, not a still-active DOM composition session.
    // A removed input node (including a different document's keyed region) ends that session.
    if (composing.current && !composing.current.isConnected) composing.current = null;
    previousDocument.current = props.documentId;
    // Clear a changed document and remove disappeared IDs before the Inspector can use the old selection.
    // Reordering/deduplication changes view state only; it never edits a timeline.
    if (!sameClipSelection(props.selectedClipIds, selectedIds)) props.onSelectClips(selectedIds);
  }, [contextKey, props.onSelectClips]);
  const select = (ids: string[], toggle = false) => {
    if (!alive.current || !latest.current.editable || context.current.generation !== generation || composing.current) return;
    const next = toggle ? toggleClipSelection(latest.current.selectedClipIds, ids[0], clipOrder)
      : normalizeClipSelection(ids, clipOrder);
    latest.current.onSelectClips(next);
  };
  if (!parsed.ok) {
    return <section key={props.documentId} className="nle-tracks" aria-label="轨道头"><StatusMessage tone="error">{parsed.message}</StatusMessage>
      <EmptyState title="轨道头不可用" detail="需要一份通过原时间线契约校验的时间线。" /></section>;
  }
  const rows: Array<{ header: NleTrackHeaderState } | { failure: string }> = parsed.timeline.tracks.map(track => {
    const checked = trackHeaderState(track);
    return checked.ok ? { header: checked.header } : { failure: checked.message };
  });
  const selected = new Set(selectedIds);
  return <section key={props.documentId} className="nle-tracks" aria-label="轨道头" data-track-count={rows.length}
    onCompositionStartCapture={event => {
      if (event.target instanceof HTMLElement && event.target.isConnected) composing.current = event.target;
    }}
    onCompositionEndCapture={event => { if (event.target === composing.current) composing.current = null; }}
    onBlurCapture={event => { if (event.target === composing.current) composing.current = null; }}
    onKeyDownCapture={event => {
      if (event.nativeEvent.isComposing || event.keyCode === 229 || composing.current) {
        if (event.key === 'Enter' || event.key === ' ' || event.keyCode === 229) event.preventDefault();
      }
    }}>
    <h3>轨道头</h3>
    <p className="nle-tracks__note">锁定与解锁、静音与增益都由原编辑服务保存；这里只显示已保存的事实。音量范围 −60 至 12 dB，视频轨道固定 0 dB。</p>
    <p id={hintId} className="nle-tracks__note">点击单选；按住 Ctrl（Mac 为 ⌘）点击可切换多选，支持跨轨道。键盘可按 Ctrl/⌘ + Enter 或 Ctrl/⌘ + 空格切换。
      <span role="status" aria-live="polite">已选 {selectedIds.length} 个片段。</span>
    </p>
    <Button disabled={!props.editable || !selectedIds.length} onClick={() => select([])}>清除片段选择</Button>
    <ul className="nle-tracks__list">
      {rows.map((row, index) => 'failure' in row
        ? <li key={`failure-${index}`}><StatusMessage tone="error">{row.failure}</StatusMessage></li>
        : <li key={row.header.trackId} className="nle-track" data-track-id={row.header.trackId}
          data-kind={row.header.kind} data-locked={row.header.locked} data-muted={row.header.muted}
          data-gain-db={row.header.gainDb}>
          <header className="nle-track__head">
            <strong>{KIND_LABEL[row.header.kind]}轨道 {row.header.order + 1}</strong>
            <Badge tone={row.header.locked ? 'warning' : 'neutral'}>{row.header.locked ? '已锁定' : '可编辑'}</Badge>
            <Badge tone={row.header.muted ? 'warning' : 'neutral'}>{row.header.muted ? '已静音或隐藏' : '参与渲染'}</Badge>
          </header>
          <dl className="nle-track__facts">
            <div><dt>用途</dt><dd>{ROLE_LABEL[row.header.role] ?? row.header.role}</dd></div>
            <div><dt>音量</dt><dd>{row.header.gainAdjustable ? `${row.header.gainDb} dB` : `固定 ${row.header.gainDb} dB`}</dd></div>
            <div><dt>片段</dt><dd>{row.header.clipCount} 个</dd></div>
          </dl>
          <Button disabled={!props.editable || !row.header.clipIds.length}
            onClick={() => select([...row.header.clipIds])}>选择整条轨道的片段</Button>
          <ul className="nle-track__clips">
            {row.header.clipIds.map(clipId => <li key={clipId}>
              <Button aria-pressed={selected.has(clipId)} aria-describedby={hintId} disabled={!props.editable}
                onKeyDown={event => {
                  if (!(event.ctrlKey || event.metaKey) || event.altKey || !['Enter', ' '].includes(event.key)) return;
                  event.preventDefault(); event.stopPropagation();
                  if (event.repeat || event.nativeEvent.isComposing || event.keyCode === 229 || composing.current) return;
                  select([clipId], true);
                }}
                onClick={event => { if (event.button === 0) select([clipId], event.ctrlKey || event.metaKey); }}>{clipId}</Button>
            </li>)}
          </ul>
        </li>)}
    </ul>
  </section>;
}
