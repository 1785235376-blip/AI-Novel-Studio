import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { graphNodeRemovalImpact } from './graphNodeRemovalImpact';
import type { StudioGraphCatalogDefinition, StudioGraphDefinition } from './studioGraphTypes';

type Props = {
  definition: StudioGraphDefinition;
  nodeIds: readonly string[];
  /** The whole selection also fences a single-node inspector preview. */
  selectionIds?: readonly string[];
  protectedNodeIds: readonly string[];
  definitions: readonly StudioGraphCatalogDefinition[];
  owner?: object | string | number;
  sourceOwner?: object;
  disabled: boolean;
  isCurrent: () => boolean;
  onApply: (definition: StudioGraphDefinition, removedIds: readonly string[]) => void;
};
type Candidate = ReturnType<typeof graphNodeRemovalImpact> & { token: object };

/** Shared by the canvas shortcuts/toolbar and the inspector; never saves or executes a graph. */
export function useGraphNodeRemoval(props: Props) {
  const [candidate, setCandidate] = useState<Candidate>();
  const [confirmed, setConfirmed] = useState(false), [error, setError] = useState('');
  const alive = useRef(true), live = useRef(props), pending = useRef<Candidate>(), consent = useRef(false);
  const trigger = useRef<HTMLElement>();
  live.current = props;
  const values = [props.definition, JSON.stringify(props.nodeIds), JSON.stringify(props.selectionIds),
    JSON.stringify(props.protectedNodeIds), JSON.stringify(props.definitions), props.owner, props.sourceOwner, props.disabled, props.isCurrent()];
  const fence = useRef({ values, token: {} });
  if (values.some((value, index) => !Object.is(value, fence.current.values[index]))) fence.current = { values, token: {} };
  const token = fence.current.token;
  const current = () => alive.current && fence.current.token === token && !live.current.disabled && live.current.isCurrent();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; pending.current = undefined; consent.current = false; }; }, []);
  useLayoutEffect(() => {
    pending.current = undefined; consent.current = false;
    setCandidate(undefined); setConfirmed(false); setError('');
  }, [token]);
  const visible = candidate?.token === token ? candidate : undefined;
  function clear() {
    pending.current = undefined; consent.current = false;
    setCandidate(undefined); setConfirmed(false); setError('');
  }
  function inspect() {
    if (!current()) return;
    clear();
    trigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
    try {
      const next = { ...graphNodeRemovalImpact(props.definition, props.nodeIds, props.protectedNodeIds, props.definitions), token };
      pending.current = next; setCandidate(next);
    } catch {
      setError('节点、保护范围或目录已变化，无法核对移除影响。请重新读取原图。');
    }
  }
  function cancel() {
    if (!current() || !visible || pending.current !== visible) return;
    clear();
    if (trigger.current?.isConnected) trigger.current.focus();
  }
  function confirm(value: boolean) {
    if (!current() || !visible || pending.current !== visible) return;
    consent.current = value; setConfirmed(value);
  }
  function apply() {
    if (!current() || !visible || pending.current !== visible || !confirmed || !consent.current) return;
    // Consume before invoking the original controller, including retained/repeated callbacks.
    clear();
    live.current.onApply(visible.definition, visible.removed);
  }
  return { candidate: visible, confirmed, error, disabled: props.disabled, inspect, cancel, confirm, apply };
}

export function GraphNodeRemovalPreview({ removal }: { removal: ReturnType<typeof useGraphNodeRemoval> }) {
  const preview = useRef<HTMLElement>(null), { candidate, confirmed, disabled } = removal;
  useLayoutEffect(() => { if (candidate) preview.current?.focus(); }, [candidate]);
  return <>
    {candidate && <section ref={preview} tabIndex={-1} aria-label="移除节点影响预览" onKeyDown={event => {
      event.stopPropagation();
      if (event.key === 'Escape') { event.preventDefault(); removal.cancel(); }
    }}>
      <h4>移除 {candidate.removed.join('、')} 的结构影响</h4>
      <p>将移除的节点：{candidate.removed.join('、')}。</p>
      <p>保留的受保护来源引用：{candidate.protectedIds.join('、') || '无'}。</p>
      <p>同时移除的连接（{candidate.removedEdges.length} 条）：{candidate.removedEdges.map(edge => `${edge.id} (${edge.source_node_id}.${edge.source_port} → ${edge.target_node_id}.${edge.target_port})`).join('、') || '无'}。</p>
      <p>保留但可能受影响的可达下游：{candidate.affected.join('、') || '无'}。</p>
      <p>新增缺少的必需输入：{candidate.newMissing.join('、') || '无'}。</p>
      <p>变更后仍缺少的必需输入：{candidate.remainingMissing.join('、') || '无'}。</p>
      <p>不在该下游路径中的保留节点：{candidate.unaffected.join('、') || '无'}。</p>
      <p>清理的空分组：{candidate.removedGroups.join('、') || '无'}；更新成员或层级的分组：{candidate.changedGroups.join('、') || '无'}。</p>
      <p>仅移除本地草稿中的这些节点及相连连接，下游节点保留。沿用原分组清理，可一次撤销；不删除原资产、章节、文档或运行历史。不会自动保存、运行或停止已有任务。保存与再次运行仍走原流程；这里只报告结构关系，不判断模型语义或费用。</p>
      <label><input type="checkbox" checked={confirmed} disabled={disabled} onChange={event => removal.confirm(event.target.checked)} />已核对结构影响，确认移除这些节点</label>
      <Button type="button" variant="danger" disabled={disabled || !confirmed} onClick={removal.apply}>确认移除节点到本地草稿</Button>
      <Button type="button" onClick={removal.cancel}>保留原节点</Button>
    </section>}
    {removal.error && <StatusMessage tone="warning">{removal.error}</StatusMessage>}
  </>;
}

export function GraphNodeRemovalControl(props: Props) {
  const removal = useGraphNodeRemoval(props);
  return <section aria-label="节点移除影响检查">
    <Button type="button" variant="danger" disabled={props.disabled || !props.nodeIds.some(id => !props.protectedNodeIds.includes(id))} onClick={removal.inspect}>移除当前节点</Button>
    <GraphNodeRemovalPreview removal={removal} />
  </section>;
}
