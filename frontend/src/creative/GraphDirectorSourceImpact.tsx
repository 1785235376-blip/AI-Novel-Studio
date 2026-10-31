import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import type { CreativeDocument } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';
import type { StudioGraphDefinition } from './studioGraphTypes';
import { directorContentChanges, directorDownstream, exactHistoricalDirector, validDirectorSnapshot } from './directorSourceImpact';

type Props = { client: GraphDirectorSource; pin: PlanningSnapshot; graph?: StudioGraphDefinition; selectedNodeId?: string;
  active: boolean; busy: boolean; isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T> };
type Preview = { generation: number; current: PlanningSnapshot; previous?: CreativeDocument; document: CreativeDocument; boards: CreativeDocument[]; historyNotice: string };
const text = (value: string) => value.length > 2000 ? `${value.slice(0, 2000)}…（字段预览已截断）` : value;
/** Read-only projection. Does not change author drafts, pins, approval or unknown outcomes. */
export function GraphDirectorSourceImpact(props: Props) {
  const { client, pin, graph, selectedNodeId, active, busy, read } = props;
  const [preview, setPreview] = useState<Preview>(), [working, setWorking] = useState(false), [error, setError] = useState('');
  const latest = useRef(props); latest.current = props;
  const alive = useRef(true), lock = useRef(false);
  const key = JSON.stringify([pin, selectedNodeId, graph, active]);
  const identity = useRef({ key, client, generation: 0 });
  if (identity.current.key !== key || identity.current.client !== client) identity.current = { key, client, generation: identity.current.generation + 1 };
  const valid = (generation: number) => alive.current && latest.current.active && latest.current.isCurrent() && generation === identity.current.generation;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { setPreview(undefined); setError(''); }, [key, client]);
  async function inspect() {
    if (!active || busy || lock.current || !latest.current.isCurrent()) return;
    const generation = identity.current.generation;
    lock.current = true; setWorking(true); setPreview(undefined); setError('');
    try {
      const value = await read(() => client.export(pin.id));
      if (!valid(generation)) return;
      const document = value.document;
      if (!validDirectorSnapshot(document, pin.id) || !/^[a-f0-9]{64}$/.test(value.document_digest)) throw new Error('导演来源回执不完整。');
      let previous: CreativeDocument | undefined, historyNotice = '仅元数据比较：历史快照或确切摘要不可用，不能推断具体内容变化。';
      try {
        const history = await read(() => client.history(pin.id));
        if (!valid(generation)) return;
        previous = exactHistoricalDirector(history, pin, { id: document.id, version: document.version, digest: value.document_digest });
        if (previous) historyNotice = '历史快照版本与原 Owner 摘要匹配；下方是已保存内容的字段差异，不含本地未保存草稿。';
      } catch (reason) {
        if (!(reason instanceof ApiError) || ![404, 409].includes(reason.status)) throw reason;
      }
      if (!valid(generation)) return;
      const related = await read(() => client.list());
      if (!valid(generation)) return;
      setPreview({ generation, current: { id: document.id, version: document.version, digest: value.document_digest }, previous, document,
        boards: related.items.filter(row => { const ref = row.source_documents?.[pin.id]; return row.mode === 'STORYBOARD' && ref && Number.isSafeInteger(ref.version) && ref.version > 0 && /^[a-f0-9]{64}$/.test(ref.digest); }), historyNotice });
    } catch (reason) { if (valid(generation)) { setPreview(undefined); setError(apiErrorView(reason, '影响预览读取失败，请重新核对原文档。').message); } }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  if (!active) return null;
  const visible = preview?.generation === identity.current.generation ? preview : undefined;
  const changes = visible?.previous ? directorContentChanges(visible.previous, visible.document) : undefined;
  const downstream = directorDownstream(graph, selectedNodeId);
  return <section aria-label="导演来源变更影响预览">
    <h3>导演来源变更影响 · 只读</h3>
    <Button disabled={busy || working} onClick={() => void inspect()}>读取／刷新导演来源影响</Button>
    {working && <StatusMessage>正在核对原文档、历史摘要与可读关联分镜…</StatusMessage>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {visible && <>
      <p>选中 director_plan 节点：{selectedNodeId || '独立来源核对'}。绑定 v{pin.version} · {pin.digest}；当前 v{visible.current.version} · {visible.current.digest}</p>
      <StatusMessage tone={pin.version === visible.current.version && pin.digest === visible.current.digest ? 'info' : 'warning'}>{pin.version === visible.current.version && pin.digest === visible.current.digest ? '绑定仍匹配本次读取的当前原文档。' : '原导演来源已变化；此节点仍引用旧快照，执行前须由原图预检重新核对。'}</StatusMessage>
      <p>{visible.historyNotice}</p>
      {changes && <><p>已保存字段差异：{changes.length} 项；最多展示前 40 项，每侧最多 2000 字符。无字段差异也可能有更新时间等元数据变化。</p>
        <ol>{changes.slice(0, 40).map(row => <li key={row.field}><strong>{row.field}</strong><p>绑定版本：{text(row.before)}</p><p>当前版本：{text(row.after)}</p></li>)}</ol></>}
      <h4>当前图的潜在下游影响</h4>
      <p>仅按已加载图的连线追踪，包含禁用节点；结构连接不证明派生来源或执行结果。</p>
      <ul>{downstream.map(node => <li key={node.id}>{node.id} · {node.definition_id}{!node.enabled ? ' · 已禁用' : ''}{node.parameters.document_snapshot && <span> · 文档 {node.parameters.document_snapshot.id} · v{node.parameters.document_snapshot.version} · {node.parameters.document_snapshot.digest}</span>}</li>)}</ul>
      {!downstream.length && <p>当前图未找到该节点的下游连接；不能据此排除图外引用。</p>}
      <h4>本次目录中可读的关联分镜引用</h4>
      <ul>{visible.boards.map(row => { const ref = row.source_documents![pin.id]; return <li key={row.id}>{row.title} · {row.id} · v{row.version} · {row.status}；导演来源 v{ref.version} · {ref.digest} · {ref.version === visible.current.version && ref.digest === visible.current.digest ? '匹配本次当前来源' : '引用另一来源快照，需要原 Owner 核对'}</li>; })}</ul>
      <p>可读关联分镜 {visible.boards.length} 个。原目录会排除来源过期、归档或不可用记录；这不是完整影响清单，零条不代表没有受影响分镜。旧分镜可能因来源变化暂不可读取，其原引用不会自动更新。</p>
      <p>本次预览不改草稿、不解决 UNKNOWN、不重绑或覆盖任何内容。已保存规划节点没有重绑操作；如需使用新版本，请在原制作节点目录明确建立新的节点／图并保存，保留旧版本供人工复审。</p>
    </>}
  </section>;
}
