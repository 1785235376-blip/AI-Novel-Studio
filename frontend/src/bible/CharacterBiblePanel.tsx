import { Badge, StatusMessage } from '../ui/primitives';
import { BibleDimensionRow } from './BibleDimensionRow';
import { draftFields, unknownFields } from './bibleContract';
import type { CharacterBibleEntry } from './bibleTypes';

/**
 * 角色圣经面板：一个角色一张只读卡片。
 *
 * 身份来自既有 `characters` 记录，行为与关系来自既有 `WorldService`
 * PSYCHOLOGY/RELATIONSHIP 记录，外形与服装来自 Round 2 新增的
 * `CHARACTER_VISUAL` 记录，参考素材是**声明**的资产 id。
 *
 * 本面板没有编辑、保存或修改入口：authoring 仍然走既有 owner 路径。
 */

const ROLE_LABELS: Record<string, string> = {
  SCENE_CAST: '场景角色表', SHOT_CAST: '镜头角色表',
  SHOT_CONTINUITY: '镜头连续性', SCENE_LOCATION: '场景地点',
};

export function CharacterBiblePanel({ entry }: { entry: CharacterBibleEntry }) {
  const missing = unknownFields(entry);
  const drafts = draftFields(entry);
  return <article className="bible-entry" data-character-id={entry.character_id}
                  aria-label={`角色 ${entry.name || entry.character_id}`}>
    <header className="bible-entry__head">
      <h4>{entry.name || entry.character_id}</h4>
      <code className="bible-entry__id">{entry.character_id}</code>
      {entry.visual_record_status === 'APPROVED' && <Badge tone="success">外形记录已批准</Badge>}
      {entry.visual_record_status !== null && entry.visual_record_status !== 'APPROVED' &&
        <Badge tone="warning">外形记录 {entry.visual_record_status}（非 canon）</Badge>}
      {entry.visual_record_status === null && <Badge tone="neutral">尚无外形记录</Badge>}
    </header>

    <dl className="bible-entry__dimensions">
      {entry.dimensions.map(dimension => <BibleDimensionRow key={dimension.field} dimension={dimension} />)}
    </dl>

    {missing.length > 0 && <StatusMessage tone="info">
      尚未 authoring：{missing.join('、')}（这些维度显示 UNKNOWN，不会被推测填充）
    </StatusMessage>}
    {drafts.length > 0 && <StatusMessage tone="warning">
      处于 DRAFT（非 canon）：{drafts.join('、')}。草稿内容会显示，但不会被当成已确定的设定。
    </StatusMessage>}

    <section className="bible-entry__usage" aria-label="出现位置">
      <h5>出现位置（只来自原文档的真实引用）</h5>
      {entry.used_in.length === 0
        ? <p className="bible-entry__note">原文档里没有任何地方引用这个角色。</p>
        : <ul>{entry.used_in.map(row => <li key={`${row.document_id}-${row.role}-${row.scene_id ?? row.shot_id ?? ''}`}>
            <code>{row.document_id}</code>
            <Badge tone="neutral">{row.mode}</Badge>
            <span>{ROLE_LABELS[row.role] ?? row.role}</span>
            {(row.scene_id ?? row.shot_id) && <code>{row.scene_id ?? row.shot_id}</code>}
          </li>)}</ul>}
    </section>
  </article>;
}
