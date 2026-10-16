import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { safeTimeline, trackHeaderState } from './timelineOps';
import type { NleTrackHeaderState } from './timelineOpsTypes';
import './timelineWorkspace.css';

const KIND_LABEL = { VIDEO: '视频', AUDIO: '音频' } as const;
const ROLE_LABEL: Record<string, string> = {
  PRIMARY: '主要画面', OVERLAY: '叠加画面', DIALOGUE: '对白', MUSIC: '音乐', EFFECTS: '音效',
};

/** 轨道头面板：锁、静音、增益与片段计数全部来自给定时间线，不推断任何状态。 */
export type TrackHeaderPanelProps = {
  timeline: unknown;
  selectedClipIds: string[];
  editable: boolean;
  onSelectClips: (ids: string[]) => void;
};

export function TrackHeaderPanel(props: TrackHeaderPanelProps) {
  const parsed = safeTimeline(props.timeline);
  if (!parsed.ok) {
    return <section className="nle-tracks" aria-label="轨道头"><StatusMessage tone="error">{parsed.message}</StatusMessage>
      <EmptyState title="轨道头不可用" detail="需要一份通过原时间线契约校验的时间线。" /></section>;
  }
  const rows: Array<{ header: NleTrackHeaderState } | { failure: string }> = parsed.timeline.tracks.map(track => {
    const checked = trackHeaderState(track);
    return checked.ok ? { header: checked.header } : { failure: checked.message };
  });
  const selected = new Set(props.selectedClipIds);
  return <section className="nle-tracks" aria-label="轨道头" data-track-count={rows.length}>
    <h3>轨道头</h3>
    <p className="nle-tracks__note">锁定与解锁、静音与增益都由原编辑服务保存；这里只显示已保存的事实。音量范围 −60 至 12 dB，视频轨道固定 0 dB。</p>
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
            onClick={() => props.onSelectClips([...row.header.clipIds])}>选择整条轨道的片段</Button>
          <ul className="nle-track__clips">
            {row.header.clipIds.map(clipId => <li key={clipId}>
              <Button aria-pressed={selected.has(clipId)} disabled={!props.editable}
                onClick={() => props.onSelectClips([clipId])}>{clipId}</Button>
            </li>)}
          </ul>
        </li>)}
    </ul>
  </section>;
}
