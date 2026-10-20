import { Badge } from '../ui/primitives';
import { canonState, type BibleDimension } from './bibleTypes';

/**
 * 一个圣经维度的只读呈现。
 *
 * 这个组件最重要的职责是：**未知必须是可见的状态**。
 * 未 authoring 的维度渲染成字面量 `UNKNOWN` 并标注"未作者化"，绝不渲染成一个空白，
 * 因为空白会被读成"这里没什么可说的"，而事实是"还没 authoring"。
 *
 * 同样地，来自世界记录的维度会带上 canon 判定：已批准的显示 CANON / APPROVED，
 * 未批准的显示 DRAFT（非 canon）。资产引用逐个显示 RESOLVED / UNRESOLVED。
 */
export function BibleDimensionRow({ dimension }: { dimension: BibleDimension }) {
  const canon = canonState(dimension);
  const unknown = dimension.state === 'UNKNOWN';
  return <div className="bible-dimension" data-field={dimension.field} data-state={dimension.state}
              data-canon={canon}>
    <dt className="bible-dimension__label">{dimension.label}</dt>
    <dd className="bible-dimension__body">
      {unknown
        ? <span className="bible-dimension__unknown">
            <code>{dimension.value}</code>
            <span className="bible-dimension__note">未作者化</span>
          </span>
        : <span className="bible-dimension__value">{dimension.value}</span>}

      <span className="bible-dimension__badges">
        {canon === 'CANON' && <Badge tone="success">CANON · APPROVED</Badge>}
        {canon === 'DRAFT' && <Badge tone="warning">DRAFT（非 canon）</Badge>}
        {dimension.authoritative === true && dimension.record_status === 'APPROVED'
          && <Badge tone="success">记录已批准</Badge>}
      </span>

      {/* 来源恒可见：每个值都能被追回到真正存储它的 owner 字段。 */}
      <span className="bible-dimension__source">来源 <code>{dimension.source}</code></span>

      {dimension.references && <ul className="bible-dimension__references">
        {dimension.references.length === 0
          ? <li className="bible-dimension__note">没有声明任何参考素材</li>
          : dimension.references.map(reference => <li key={reference.asset_id}>
              <code>{reference.asset_id}</code>
              <Badge tone={reference.resolution === 'RESOLVED' ? 'success' : 'warning'}>
                {reference.resolution === 'RESOLVED' ? 'RESOLVED（索引中已找到）' : 'UNRESOLVED（索引中没有）'}
              </Badge>
            </li>)}
      </ul>}
      {dimension.verification === 'NO_INDEX_SUPPLIED' &&
        <span className="bible-dimension__note">未提供资产索引，因此没有任何引用可以判定为已找到。</span>}

      {dimension.relationships && <ul className="bible-dimension__relationships">
        {dimension.relationships.length === 0
          ? <li className="bible-dimension__note">原文档没有记录关系</li>
          : dimension.relationships.map(row => <li key={`${row.target_character_id}-${row.state}`}>
              <span>→ <code>{row.target_character_id}</code>：{row.state}</span>
              {row.authoritative
                ? <Badge tone="success">CANON · APPROVED</Badge>
                : <Badge tone="warning">DRAFT（非 canon）</Badge>}
            </li>)}
      </ul>}

      {typeof dimension.geography_records === 'number' && dimension.geography_records > 0 &&
        <span className="bible-dimension__note">地理关系记录 {dimension.geography_records} 条（原 GEOGRAPHY 记录）</span>}
    </dd>
  </div>;
}
