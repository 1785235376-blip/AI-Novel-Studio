import { Badge, StatusMessage } from '../ui/primitives';
import { SHOT_ACTION_LABELS } from './storyboardWorkspaceTypes';
import type { ShotStalenessNote, StoryboardShotRow } from './storyboardWorkspaceTypes';

/**
 * 一张镜头卡。身份（`shot_id`）与显示序号（`number`）分开显示：拖动只改序号。
 * 所有事实都来自 `ShotSummary`，缺席的字段就显示"原文档未提供"。
 *
 * 外层 `<li>` 由 `ShotList` 提供，这里只渲染卡片本身。
 */
export function ShotCard({ row, selected, onSelect, staleness }: {
  row: StoryboardShotRow;
  selected: boolean;
  onSelect: (shotId: string) => void;
  staleness?: ShotStalenessNote[];
}) {
  const { shot, summary } = row;
  const missing = (value: string | number | null) => value === null ? '原文档未提供' : String(value);
  return <>
    <button
      type="button"
      className="storyboard-shot-card"
      data-selected={selected ? 'true' : 'false'}
      aria-pressed={selected}
      aria-label={`镜头 ${summary.number}（身份 ${summary.shot_id}）`}
      onClick={() => onSelect(summary.shot_id)}
    >
      <span className="storyboard-shot-card__number">SHOT {summary.number}</span>
      <span className="storyboard-shot-card__identity">{summary.shot_id}</span>
      <span className="storyboard-shot-card__subject">{summary.subject ?? '原文档未提供主体描述'}</span>
      <span className="storyboard-shot-card__facts">
        <span>时长 {summary.duration ? `${summary.duration.seconds} 秒` : '原文档未提供'}</span>
        <span>景别 {missing(summary.framing.shot_size)}</span>
        <span>机位 {missing(summary.framing.camera_angle)}</span>
        <span>运动 {missing(summary.framing.camera_motion)}</span>
      </span>
      <span className="storyboard-shot-card__badges">
        <Badge tone="neutral">v{shot.shot_version}</Badge>
        {summary.candidate
          ? <Badge tone={summary.candidate.kind === 'VIDEO' ? 'success' : 'info'}>
            {summary.candidate.kind === 'VIDEO' ? '已有正式视频' : '已有正式图片'}
          </Badge>
          : <Badge tone="warning">尚无正式绑定</Badge>}
        {summary.audio && <Badge tone="neutral">有音频线索</Badge>}
        {summary.staleness.length > 0 && <Badge tone="warning">来源有变化（{summary.staleness.length} 条证据）</Badge>}
        {summary.references.director_note_ids.length > 0 && <Badge tone="info">有导演目标</Badge>}
      </span>
      <span className="storyboard-shot-card__next">
        下一步：{SHOT_ACTION_LABELS[summary.next_actions[0]] ?? '没有由原文档声明的下一步'}
      </span>
    </button>
    {/** 陈旧性只在有证据时出现；它绝不会被悄悄丢掉。 */}
    {staleness && staleness.length > 0 && <StatusMessage tone="warning">
      {staleness[0].kind}：{staleness[0].detail}
      {staleness.length > 1 && `（还有 ${staleness.length - 1} 条证据）`}
    </StatusMessage>}
  </>;
}
