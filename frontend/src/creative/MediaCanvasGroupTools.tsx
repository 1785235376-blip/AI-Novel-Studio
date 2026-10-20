import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { CanvasDefinition } from './studioCanvasViewClient';
import { assignCanvasCard, dissolveCanvasGroup, replaceCanvasGroups } from './mediaCanvasGroups';
type Props = { definition: CanvasDefinition; selectedCard: string; owner: object; disabled: boolean; isCurrent: () => boolean; onChange: (value: CanvasDefinition) => void };
export function MediaCanvasGroupTools(props: Props) {
  const [groupId, setGroupId] = useState(''), [name, setName] = useState(''), [error, setError] = useState('');
  const alive = useRef(true), live = useRef(props); live.current = props;
  const values = [props.definition, props.owner, props.disabled, props.selectedCard, groupId, name]; const fence = useRef({ values, token: {} });
  if (values.some((v, i) => !Object.is(v, fence.current.values[i]))) fence.current = { values, token: {} };
  const token = fence.current.token, groups = props.definition.groups ?? [], selected = groups.find(g => g.id === groupId), hasCard = props.definition.cards.some(c => c.id === props.selectedCard);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  function apply(work: () => CanvasDefinition) { if (!alive.current || fence.current.token !== token || live.current.disabled || !live.current.isCurrent()) return;
    try { const next = work(); setError(''); live.current.onChange(next); } catch { setError('分组操作无效。请检查重复成员、循环引用或超过八层的嵌套。'); } }
  return <section aria-label="媒体画布显示分组"><p>显示分组最多 64 个、嵌套最多八层。折叠只隐藏显示，不删除素材或执行任务；仍需保存。</p><div className="creative-actions">
    <label>分组名称<input value={name} maxLength={80} disabled={props.disabled} onChange={e => setName(e.target.value)} /></label>
    <Button disabled={props.disabled || !name.trim() || groups.length >= 64} onClick={() => apply(() => replaceCanvasGroups(props.definition, [...groups, { id: `Group_${crypto.randomUUID().replaceAll('-', '')}`, name, card_ids: [], collapsed: false }]))}>新建空显示组</Button>
    <label>当前显示组<select value={groupId} disabled={props.disabled} onChange={e => setGroupId(e.target.value)}><option value="">选择分组</option>{groups.map(g => <option key={g.id} value={g.id}>{g.name} · {g.card_ids.length} 张直接成员</option>)}</select></label>
    <Button disabled={props.disabled || !selected || !name.trim()} onClick={() => apply(() => replaceCanvasGroups(props.definition, groups.map(g => g.id === groupId ? { ...g, name } : g)))}>重命名所选组</Button>
    <Button disabled={props.disabled || !selected || !hasCard} onClick={() => apply(() => assignCanvasCard(props.definition, props.selectedCard, groupId))}>将当前卡片移入所选组</Button>
    <Button disabled={props.disabled || !hasCard} onClick={() => apply(() => assignCanvasCard(props.definition, props.selectedCard))}>将当前卡片移出分组</Button>
    {selected && <><label>父显示组<select value={selected.parent_id ?? ''} disabled={props.disabled} onChange={e => { const parent = e.target.value; apply(() => replaceCanvasGroups(props.definition, groups.map(g => { if (g.id !== groupId) return g; const { parent_id: _old, ...rest } = g; return { ...rest, ...(parent ? { parent_id: parent } : {}) }; }))); }}><option value="">顶层</option>{groups.filter(g => g.id !== groupId).map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
      <Button disabled={props.disabled} onClick={() => apply(() => replaceCanvasGroups(props.definition, groups.map(g => g.id === groupId ? { ...g, collapsed: !g.collapsed } : g)))}>{selected.collapsed ? '展开所选组' : '折叠所选组'}</Button>
      <Button disabled={props.disabled} onClick={() => apply(() => dissolveCanvasGroup(props.definition, groupId))}>解散所选组，保留卡片</Button></>}
  </div>{error && <StatusMessage tone="warning">{error}</StatusMessage>}</section>;
}
