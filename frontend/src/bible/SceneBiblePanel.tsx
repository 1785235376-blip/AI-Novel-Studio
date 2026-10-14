import { Badge, StatusMessage } from '../ui/primitives';
import { BibleDimensionRow } from './BibleDimensionRow';
import { draftFields, unknownFields } from './bibleContract';
import type { SceneBibleEntry } from './bibleTypes';

/**
 * 场景圣经面板：一个地点一张只读卡片。
 *
 * 地点身份来自既有 `locations` 记录（另有 `WorldService` GEOGRAPHY 关系），建筑/材质/
 * 灯光/天气/时间/氛围来自 Round 2 新增的 `SCENE_VISUAL` 记录。参考素材是**声明**的资产 id。
 *
 * 与角色面板一样：没有编辑、保存或修改入口。
 */
export function SceneBiblePanel({ entry }: { entry: SceneBibleEntry }) {
  const missing = unknownFields(entry);
  const drafts = draftFields(entry);
  return <article className="bible-entry" data-location-id={entry.location_id}
                  aria-label={`场景 ${entry.name || entry.location_id}`}>
    <header className="bible-entry__head">
      <h4>{entry.name || entry.location_id}</h4>
      <code className="bible-entry__id">{entry.location_id}</code>
      {entry.visual_record_status === 'APPROVED' && <Badge tone="success">视觉记录已批准</Badge>}
      {entry.visual_record_status !== null && entry.visual_record_status !== 'APPROVED' &&
        <Badge tone="warning">视觉记录 {entry.visual_record_status}（非 canon）</Badge>}
      {entry.visual_record_status === null && <Badge tone="neutral">尚无视觉记录</Badge>}
    </header>

    <dl className="bible-entry__dimensions">
      {entry.dimensions.map(dimension => <BibleDimensionRow key={dimension.field} dimension={dimension} />)}
    </dl>

    {entry.reference_asset_ids.length > 0 && <section className="bible-entry__refs" aria-label="参考素材（声明）">
      <h5>参考素材（声明，未在本面板内校验）</h5>
      <ul>{entry.reference_asset_ids.map(id => <li key={id}><code>{id}</code></li>)}</ul>
    </section>}

    {missing.length > 0 && <StatusMessage tone="info">
      尚未 authoring：{missing.join('、')}（这些维度显示 UNKNOWN，不会被推测填充）
    </StatusMessage>}
    {drafts.length > 0 && <StatusMessage tone="warning">
      处于 DRAFT（非 canon）：{drafts.join('、')}。草稿内容会显示，但不会被当成已确定的设定。
    </StatusMessage>}

    <section className="bible-entry__usage" aria-label="出现位置">
      <h5>出现位置（只来自原文档的真实引用）</h5>
      {entry.used_in.length === 0
        ? <p className="bible-entry__note">原文档里没有任何地方引用这个地点。</p>
        : <ul>{entry.used_in.map(row => <li key={`${row.document_id}-${row.role}-${row.scene_id ?? row.shot_id ?? ''}`}>
            <code>{row.document_id}</code>
            <Badge tone="neutral">{row.mode}</Badge>
            <span>{row.role === 'SCENE_LOCATION' ? '场景地点' : row.role}</span>
            {(row.scene_id ?? row.shot_id) && <code>{row.scene_id ?? row.shot_id}</code>}
          </li>)}</ul>}
    </section>
  </article>;
}
