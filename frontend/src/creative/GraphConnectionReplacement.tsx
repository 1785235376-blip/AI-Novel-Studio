import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { graphConnectionReplacement, type GraphConnectionCatalog } from './graphConnectionReplacementHelpers';
import { graphCatalogForSchema } from './graphDraft';
import { GRAPH_NODE_LABELS } from './studioGraphLabels';
import type { StudioGraphDefinition } from './studioGraphTypes';

type Props = { definition: StudioGraphDefinition; catalog: GraphConnectionCatalog; owner: object;
  disabled: boolean; isCurrent: () => boolean;
  onApply: (edgeId: string, sourceNodeId: string, sourcePort: string) => boolean };
/** The transient review cannot survive an observed owner/draft/lock ABA. */
export function GraphConnectionReplacement(props: Props) {
  const live = useRef(props); live.current = props;
  const values = [props.definition, JSON.stringify(props.definition), props.owner, props.disabled,
    props.isCurrent(), JSON.stringify(props.catalog)];
  const fence = useRef({ values, generation: 0 });
  if (values.some((value, index) => !Object.is(value, fence.current.values[index]))) fence.current = { values, generation: fence.current.generation + 1 };
  const generation = fence.current.generation;
  if (!props.isCurrent()) return null;
  return <ReplacementReview key={generation} {...props}
    current={() => generation === fence.current.generation && !live.current.disabled && live.current.isCurrent()} />;
}
function ReplacementReview(props: Props & { current: () => boolean }) {
  const [edgeId, setEdgeId] = useState(''), [outputKey, setOutputKey] = useState('');
  const [preview, setPreview] = useState<ReturnType<typeof graphConnectionReplacement>>();
  const [confirmed, setConfirmed] = useState(false), [error, setError] = useState('');
  const alive = useRef(true), revision = useRef(0), candidate = useRef(preview), consent = useRef(false);
  const live = useRef(props); live.current = props;
  const renderedRevision = revision.current;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; candidate.current = undefined; consent.current = false; }; }, []);
  const authorized = () => alive.current && props.current();
  const current = () => authorized() && renderedRevision === revision.current;
  const outputs = props.definition.nodes.flatMap(node => (graphCatalogForSchema(props.catalog.definitions, props.definition.schema_version)
    .find(row => row.id === node.definition_id)?.outputs || []).map(port => ({ node, port, key: JSON.stringify([node.id, port.id]) })));
  function retire() { revision.current++; candidate.current = undefined; consent.current = false; setPreview(undefined); setConfirmed(false); setError(''); }
  function inspect() {
    if (!current()) return;
    retire();
    try {
      const output = outputs.find(row => row.key === outputKey);
      if (!output) throw new Error('请明确选择当前图的新输出端口。');
      const result = graphConnectionReplacement(props.definition, props.catalog, edgeId, { nodeId: output.node.id, portId: output.port.id });
      candidate.current = result; setPreview(result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : '重接预览不可用。'); }
  }
  function apply() {
    if (!current() || !preview || candidate.current !== preview || !confirmed || !consent.current) return;
    candidate.current = undefined; consent.current = false; revision.current++; setPreview(undefined); setConfirmed(false);
    if (!live.current.onApply(preview.previous.id, preview.next.source_node_id, preview.next.source_port)) setError('重接未应用，请重新核对当前图与编辑状态。');
  }
  return <section className="graph-canvas__groups" aria-label="输入连接原子重接">
    <h3>替换已有输入连接</h3>
    <p>选择一条已有连接及新输出，预览后一次替换到原输入；保留连接 ID，不产生先断开再连接的中间草稿。</p>
    <label>要重接的输入<select aria-label="要重接的输入" value={edgeId} disabled={props.disabled} onChange={event => {
      if (authorized()) { retire(); setEdgeId(event.target.value); setOutputKey(''); }
    }}><option value="">明确选择原连接</option>{props.definition.edges.map(edge => <option key={edge.id} value={edge.id}>{edge.id} · {edge.source_node_id}.{edge.source_port} → {edge.target_node_id}.{edge.target_port}</option>)}</select></label>
    <label>重接的新输出<select aria-label="重接的新输出" value={outputKey} disabled={props.disabled} onChange={event => {
      if (authorized()) { retire(); setOutputKey(event.target.value); }
    }}><option value="">明确选择新输出</option>{outputs.map(({ node, port, key }) => <option key={key} value={key}>{GRAPH_NODE_LABELS[node.definition_id]} · {node.id}.{port.id} ({port.type})</option>)}</select></label>
    <Button disabled={props.disabled || !edgeId || !outputKey} onClick={inspect}>预览输入重接</Button>
    {preview && <section aria-label="输入重接影响预览">
      <p>旧来源：{preview.previous.source_node_id}.{preview.previous.source_port} → {preview.previous.target_node_id}.{preview.previous.target_port}</p>
      <p>新来源：{preview.next.source_node_id}.{preview.next.source_port} → {preview.next.target_node_id}.{preview.next.target_port} · 类型 {preview.type}</p>
      <p>目标及原下游：{preview.affected.join('、') || '无'}。新增缺少的必需输入：{preview.newMissing.join('、') || '无'}。</p>
      <p>仅替换这一条连接的来源端口；节点参数、来源绑定、分组和其他连接保持原样。一次撤销可恢复。保存、预检、审核与执行仍需原流程；此预览不证明可执行或已获批准。</p>
      <label><input type="checkbox" checked={confirmed} disabled={props.disabled} onChange={event => {
        if (current() && candidate.current === preview) { consent.current = event.target.checked; setConfirmed(event.target.checked); }
      }} />已核对旧新来源与下游范围，确认只替换此连接</label>
      <Button disabled={props.disabled || !confirmed} onClick={apply}>确认重接到本地草稿</Button>
      <Button variant="ghost" onClick={() => { if (current()) retire(); }}>保留原输入连接</Button>
    </section>}
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
  </section>;
}
