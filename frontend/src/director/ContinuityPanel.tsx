import { Badge, StatusMessage } from '../ui/primitives';
import type { ContinuityPanel as ContinuityPanelValue } from './directorWorkspaceTypes';

/**
 * 连续性面板：五个维度只做提示。
 *
 * 这个面板**没有写入口**，也没有"一键修正"。它做的事只有两件：
 *  1. 列出两个相邻镜头之间、双方都 authoring 且不一致的维度；
 *  2. 如实报告覆盖度——某一对被判为"未知"还是"已比较"。
 *
 * 第 2 点是刻意的：如果只显示"没有警告"，读者会把"没比较"误当成"一致"。
 */

const REASON_LABELS: Record<string, string> = {
  CAMERA_MOVE_IS_DIRECTION: '镜头之间移动摄影机是导演手法，不是连续性错误',
};

export function ContinuityPanel({ panel }: { panel: ContinuityPanelValue }) {
  const unknownTotal = panel.dimensions.reduce((sum, dimension) => sum + dimension.unknown_pairs, 0);
  return <section className="director-continuity" aria-label="连续性检查">
    <p className="director-continuity__scope">
      只提示，不自动修改：这里不会改写任何镜头、不会自动对齐服装或灯光。
      是否修改由你决定，并且要在原文档界面完成。
    </p>

    <div className="director-continuity__summary">
      <Badge tone="info">比较了 {panel.compared_pairs} 对相邻镜头</Badge>
      <Badge tone={panel.warnings.length > 0 ? 'warning' : 'success'}>
        {panel.warnings.length > 0 ? `${panel.warnings.length} 条提示` : '没有提示'}
      </Badge>
      {unknownTotal > 0 && <Badge tone="neutral">未知维度 {unknownTotal} 项（两侧未同时填写）</Badge>}
    </div>

    <table className="director-continuity__dimensions">
      <caption>五个维度 · 覆盖度（"未知"表示两侧没有同时 authoring，不是"一致"）</caption>
      <thead><tr>
        <th scope="col">维度</th><th scope="col">已比较</th><th scope="col">未知</th><th scope="col">authoring 来源</th>
      </tr></thead>
      <tbody>{panel.dimensions.map(dimension => <tr key={dimension.field} data-field={dimension.field}>
        <th scope="row">{dimension.label}</th>
        <td>{dimension.compared_pairs}</td>
        <td>{dimension.unknown_pairs}</td>
        <td>{dimension.sources.map(source => <code key={source}>{source}</code>)}</td>
      </tr>)}</tbody>
    </table>

    {panel.warnings.length === 0
      ? <StatusMessage tone="success">在当前已比较的维度里没有发现不一致。</StatusMessage>
      : <ul className="director-continuity__warnings">
        {panel.warnings.map(warning => <li key={`${warning.code}-${warning.previous_shot_id}-${warning.next_shot_id}`}
            data-code={warning.code}>
          <span className="director-continuity__warning-head">
            <Badge tone="warning">提示</Badge>
            <strong>{warning.label}</strong>
            <code>{warning.code}</code>
          </span>
          <span className="director-continuity__warning-detail">
            镜头 {warning.previous_shot_id}：{warning.previous}
            {' → '}
            镜头 {warning.next_shot_id}：{warning.next}
          </span>
        </li>)}
      </ul>}

    <section className="director-continuity__excluded" aria-label="不比较的维度">
      <h4>刻意不比较的维度</h4>
      <ul>{panel.excluded.map(item => <li key={item.field}>
        <code>{item.field}</code>：{REASON_LABELS[item.reason] ?? item.reason}
      </li>)}</ul>
    </section>
  </section>;
}
