import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button } from '../ui/primitives';
import { GRAPH_NODE_LABELS } from './studioGraphLabels';
import type { StudioGraphDefinition } from './studioGraphTypes';
import { inspectGraphDependencies, type GraphDependencyDirection } from './graphDependencies';

type Props = { definition: StudioGraphDefinition; selected: readonly string[]; owner?: string | number;
  busy: boolean; onSelect: (ids: string[]) => void };
/** Selection-only diagnostic. Original graph edges, save and execution owners are untouched. */
export function GraphDependencyInspector(props: Props) {
  const [open, setOpen] = useState(false), [direction, setDirection] = useState<GraphDependencyDirection>('upstream');
  const [depth, setDepth] = useState<'direct' | 'all'>('all'), [page, setPage] = useState(0);
  const alive = useRef(true), live = useRef(props); live.current = props;
  const values = [props.definition, props.owner, props.busy, JSON.stringify(props.selected)];
  const fence = useRef({ values, token: {} });
  if (values.some((value, index) => value !== fence.current.values[index])) fence.current = { values, token: {} };
  const token = fence.current.token;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useLayoutEffect(() => { setOpen(false); setPage(0); }, [props.owner]);
  useLayoutEffect(() => { setPage(0); }, [props.definition, JSON.stringify(props.selected), direction, depth]);
  const rows = useMemo(() => inspectGraphDependencies(props.definition, props.selected, direction)
    .filter(row => depth === 'all' || row.distance === 1), [props.definition, props.selected, direction, depth]);
  const current = () => alive.current && !live.current.busy && fence.current.token === token;
  return <section className="graph-canvas__groups" aria-label="图节点依赖检查" onKeyDown={event => event.stopPropagation()}>
    <Button type="button" variant="ghost" aria-expanded={open} disabled={props.busy} onClick={() => { if (current()) setOpen(value => !value); }}>检查所选节点依赖</Button>
    {open && <><p>依据当前草稿已有连接追踪；包含停用节点，不代表可执行、已获授权或已验证运行顺序。仅改变选中项，不修改连线。</p>
      <div role="group" aria-label="依赖方向">{(['upstream', 'downstream'] as const).map(value => <Button key={value} type="button" variant="ghost" aria-pressed={direction === value} disabled={props.busy}
        onClick={() => { if (current()) setDirection(value); }}>{value === 'upstream' ? '查看上游来源' : '查看下游影响'}</Button>)}</div>
      <label><input type="checkbox" checked={depth === 'direct'} disabled={props.busy} onChange={event => { if (current()) setDepth(event.target.checked ? 'direct' : 'all'); }} />仅显示直接连接</label>
      <p role="status">已选 {props.selected.length} 个起点，找到 {rows.length} 个{direction === 'upstream' ? '上游' : '下游'}节点。</p>
      {!props.selected.length && <p>先在画布中选择节点。</p>}
      <ol>{rows.slice(page * 20, (page + 1) * 20).map(({ node, distance, links }) => <li key={node.id}>
        <Button type="button" variant="ghost" disabled={props.busy} onClick={() => { if (current()) props.onSelect([node.id]); }}>选择依赖节点 {node.id}</Button>
        <span>{GRAPH_NODE_LABELS[node.definition_id]} · {distance} 跳 · {node.enabled ? '启用' : '停用'}</span>
        <ul>{links.map(edge => <li key={edge.id}>{edge.source_node_id}.{edge.source_port} → {edge.target_node_id}.{edge.target_port}</li>)}</ul>
      </li>)}</ol>
      <Button type="button" variant="ghost" disabled={props.busy || page === 0} onClick={() => { if (current()) setPage(value => Math.max(0, value - 1)); }}>上一页依赖</Button>
      <Button type="button" variant="ghost" disabled={props.busy || (page + 1) * 20 >= rows.length} onClick={() => { if (current()) setPage(value => value + 1); }}>下一页依赖</Button>
    </>}
  </section>;
}
