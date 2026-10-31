import { Badge, StatusMessage } from '../ui/primitives';
import type { DirectorCameraEvidence } from './directorCameraEvidence';

const labels: Record<string, string> = { INSUFFICIENT_EVIDENCE: '信息不足', INTENTIONAL_OVERRIDE: '已记录有意选择', AXIS_CROSSING: '几何越轴提示', SAME_SIDE: '几何同侧', CONSISTENT: '声明方向相符', DIRECTION_MISMATCH: '声明方向不符', REVIEW_SUGGESTION: '核对建议' };
export function DirectorCameraEvidencePanel({ evidence }: { evidence?: DirectorCameraEvidence }) {
  return <section aria-label="手填机位辅助证据">
    <h3>手填机位与轴线 · 辅助证据</h3>
    <p>模型语义分析与创作判断是主要决策依据。以下仅复算作者明确填写的几何与元数据，不是模型或画面分析，也不代表审美与连续性正确。</p>
    {!evidence ? <StatusMessage>信息不足：原文档尚未提供手填机位几何。可在原导演调度或镜头参数中填写，保存后重新读取。</StatusMessage> : <>
      <p>原文档 {evidence.document_snapshot.id} · v{evidence.document_snapshot.version} · <code>{evidence.document_snapshot.digest}</code></p>
      <p>来源：{evidence.source_field === 'director_notes' ? '导演调度' : '分镜镜头'}；{evidence.rows.filter(r => r.geometry_authored).length} / {evidence.rows.length} 项已手填。只提示，不自动修改或执行。</p>
      <ul>{evidence.findings.map(f => <li key={[f.kind, f.shot_id, f.from_shot_id, f.to_shot_id].join(':')}>
        <Badge tone={['AXIS_CROSSING', 'DIRECTION_MISMATCH', 'REVIEW_SUGGESTION'].includes(f.state) ? 'warning' : 'neutral'}>{labels[f.state]}</Badge>
        <span> {f.shot_id || `${f.from_shot_id} → ${f.to_shot_id}`} · {f.kind}：{f.message}</span>
        {f.cross_products && <p>精确叉积：{f.cross_products.join(' / ')}</p>}
        {f.computed && <p>计算方向：{f.computed}；精确投影：{f.projection}</p>}
        {f.state === 'INTENTIONAL_OVERRIDE' && <p>作者理由：{evidence.rows.find(r => r.id === f.to_shot_id)?.camera_grammar?.override_reason}</p>}
      </li>)}</ul>
      <details><summary>查看手填来源坐标与意图</summary>{evidence.rows.map(row => <section key={row.id} aria-label={`几何来源 ${row.id}`}><h4>{row.id} · 场景 {row.scene_id}</h4>
        {row.camera_grammar ? <><p>坐标系：{row.camera_grammar.coordinate_system || '未填'}；轴线：{row.camera_grammar.axis.join(' → ') || '未填'}；机位：{row.camera_grammar.camera_position ? `${row.camera_grammar.camera_position.x}, ${row.camera_grammar.camera_position.y}` : '未填'}</p>
          <ul>{Object.entries(row.camera_grammar.character_positions).map(([id, p]) => <li key={id}>{id}：{p.x}, {p.y}</li>)}</ul></> : <p>信息不足：未填写几何。</p>}
      </section>)}</details>
    </>}
  </section>;
}
