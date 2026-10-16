import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Button } from '../ui/primitives';
import type { StudioGraphDefinition } from './studioGraphTypes';
import type { GraphCanvasNodeDefinition } from './graphCanvasGeometry';
import { GRAPH_NODE_LABELS } from './studioGraphLabels';

export const GRAPH_NAVIGATION_PAGE_SIZE = 20;

/** Existing graph instances only. Filtering never invokes selection, graph writes or execution. */
export function GraphNodeNavigator({ nodes, definitions, owner, busy, readonly, onNavigate }: {
  nodes: StudioGraphDefinition['nodes']; definitions: readonly GraphCanvasNodeDefinition[];
  owner?: string | number; busy: boolean; readonly: boolean; onNavigate: (id: string) => void;
}) {
  const [open, setOpen] = useState(false), [query, setQuery] = useState(''), [active, setActive] = useState(0);
  const trigger = useRef<HTMLButtonElement>(null), input = useRef<HTMLInputElement>(null);
  const id = useId();
  const entries = useMemo(() => {
    const labels = new Map(definitions.map(row => [row.id, row.label]));
    return nodes.map(node => ({ id: node.id, type: node.definition_id,
      label: labels.get(node.definition_id) || GRAPH_NODE_LABELS[node.definition_id] || node.definition_id }));
  }, [nodes, definitions]);
  const matches = useMemo(() => {
    const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    return entries.filter(row => words.every(word => `${row.label} ${row.type} ${row.id}`.toLocaleLowerCase().includes(word)));
  }, [entries, query]);
  const index = Math.min(active, Math.max(0, matches.length - 1));
  const start = Math.floor(index / GRAPH_NAVIGATION_PAGE_SIZE) * GRAPH_NAVIGATION_PAGE_SIZE;
  const page = matches.slice(start, start + GRAPH_NAVIGATION_PAGE_SIZE);
  useEffect(() => { setOpen(false); setQuery(''); setActive(0); }, [owner]);
  useEffect(() => { if (open && !busy) input.current?.focus(); }, [open, busy]);
  useEffect(() => {
    if (open) document.getElementById(`${id}-option-${index}`)?.scrollIntoView?.({ block: 'nearest' });
  }, [open, id, index, query]);
  function close() { setOpen(false); setQuery(''); setActive(0); trigger.current?.focus(); }
  function choose(nodeId: string) { if (busy) return; onNavigate(nodeId); close(); }
  return <div className="graph-canvas__node-navigation" onKeyDown={event => {
    event.stopPropagation();
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    if (event.key === 'Escape' && open) { event.preventDefault(); close(); }
  }}>
    <Button ref={trigger} type="button" variant="ghost" disabled={busy && !open} aria-expanded={open} aria-controls={`${id}-panel`}
      onClick={() => open ? close() : setOpen(true)}>查找图中节点</Button>
    {open && <section id={`${id}-panel`} aria-label="图中节点目录" className="graph-canvas__groups">
      <label htmlFor={`${id}-input`}>按名称、类型或 ID 查找</label>
      <input ref={input} id={`${id}-input`} role="combobox" aria-label="查找图中节点" autoComplete="off"
        aria-expanded="true" aria-controls={`${id}-list`} aria-autocomplete="list"
        aria-activedescendant={matches.length ? `${id}-option-${index}` : undefined}
        value={query} maxLength={200} disabled={busy} onChange={event => { setQuery(event.target.value); setActive(0); }}
        onKeyDown={event => {
          if (busy || event.nativeEvent.isComposing || event.keyCode === 229 || event.altKey || event.ctrlKey || event.metaKey) return;
          if (event.key === 'Enter') { event.preventDefault(); if (matches[index]) choose(matches[index].id); }
          const delta = event.key === 'ArrowDown' ? 1 : event.key === 'ArrowUp' ? -1
            : event.key === 'PageDown' ? GRAPH_NAVIGATION_PAGE_SIZE : event.key === 'PageUp' ? -GRAPH_NAVIGATION_PAGE_SIZE : 0;
          if (delta) { event.preventDefault(); setActive(Math.max(0, Math.min(matches.length - 1, index + delta))); }
        }} />
      <p role="status" className="graph-canvas__help">共 {entries.length} 个节点，匹配 {matches.length} 个；显示 {matches.length ? start + 1 : 0}–{start + page.length}。{readonly ? '只读：确认后仅选择，不移动视图。' : '确认后选择并居中；视图修改仍需保存。'}方向键选择，翻页键换页，Enter 确认，Esc 关闭。</p>
      <div id={`${id}-list`} role="listbox" aria-label="匹配的图节点" className="graph-canvas__navigation-results">
        {page.map((row, offset) => <Button type="button" variant="ghost" role="option" key={row.id}
          id={`${id}-option-${start + offset}`} aria-selected={index === start + offset} aria-posinset={start + offset + 1} aria-setsize={matches.length} disabled={busy}
          onClick={() => choose(row.id)}>{row.label} · {row.type} · {row.id}</Button>)}
      </div>
      {!matches.length && <p className="graph-canvas__help">没有匹配的图中节点。</p>}
      <Button type="button" variant="ghost" disabled={busy || !start} onClick={() => { setActive(Math.max(0, start - GRAPH_NAVIGATION_PAGE_SIZE)); input.current?.focus(); }}>上一页节点</Button>
      <Button type="button" variant="ghost" disabled={busy || start + page.length >= matches.length} onClick={() => { setActive(start + GRAPH_NAVIGATION_PAGE_SIZE); input.current?.focus(); }}>下一页节点</Button>
      <Button type="button" variant="ghost" onClick={close}>关闭节点查找</Button>
    </section>}
  </div>;
}
