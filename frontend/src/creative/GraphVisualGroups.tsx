import { promoteOrphanGroups, visualGroupMembers } from './graphVisualHierarchy';
import { useEffect, useId, useState } from 'react';
import { Button } from '../ui/primitives';
import type { StudioGraphDefinition } from './studioGraphTypes';

type Props = {
  definition: StudioGraphDefinition;
  selected: readonly string[];
  blocked: boolean;
  interactionKey?: string | number;
  onChange: (value: StudioGraphDefinition, record?: boolean) => void;
  onSelect: (ids: string[]) => void;
};
/** All persisted content stays in the original graph. Only the pending name is local. */
export function GraphVisualGroups({ definition, selected, blocked, interactionKey, onChange, onSelect }: Props) {
  const labelId = useId();
  const [name, setName] = useState('');
  const [choice, setChoice] = useState('');
  const [parentChoice, setParentChoice] = useState('');
  const groups = definition.presentation?.groups || [];
  const chosen = groups.find(group => group.id === choice);
  useEffect(() => { setChoice(''); setName(''); setParentChoice(''); }, [definition, interactionKey, blocked]);
  const validName = !!name.trim() && Array.from(name).length <= 80;
  const members = new Set(groups.flatMap(group => group.node_ids));
  const validSelection = selected.length > 0 && selected.length <= 24 && new Set(selected).size === selected.length
    && selected.every(id => definition.nodes.some(node => node.id === id) && !members.has(id));
  function write(nextGroups: typeof groups) {
    if (blocked) return;
    const next: StudioGraphDefinition = { ...definition, presentation: { ...definition.presentation } };
    if (nextGroups.length) next.presentation!.groups = nextGroups;
    else delete next.presentation!.groups;
    if (!Object.keys(next.presentation!).length) delete next.presentation;
    onChange(next, true);
  }
  return <section className="graph-canvas__groups" aria-label="已保存视觉分组" onKeyDown={event => event.stopPropagation()}>
    <div className="graph-canvas__toolbar">
      <label htmlFor={`${labelId}-choice`}>视觉分组</label>
      <select id={`${labelId}-choice`} disabled={blocked} value={choice} onChange={event => {
        setChoice(event.target.value); setName(groups.find(group => group.id === event.target.value)?.name || '');
        setParentChoice(groups.find(group => group.id === event.target.value)?.parent_id || '');
      }}>
        <option value="">新建分组</option>
        {groups.map(group => <option key={group.id} value={group.id}>{group.parent_id ? `${groups.find(parent => parent.id === group.parent_id)?.name} / ` : ''}{group.name} · {group.node_ids.length} 个节点</option>)}
      </select>
      <label htmlFor={`${labelId}-name`}>分组名称</label>
      <input id={`${labelId}-name`} value={name} maxLength={160} disabled={blocked} onChange={event => setName(event.target.value)} />
      <Button disabled={blocked || !!chosen || !validName || !validSelection || groups.length >= 24} onClick={() => {
        if (blocked || chosen || !validName || !validSelection || groups.length >= 24) return;
        let index = 1; while (groups.some(group => group.id === `group_${index}`)) index++;
        write([...groups, { id: `group_${index}`, name, node_ids: [...selected] }]);
      }}>用所选节点创建分组</Button>
      <Button disabled={blocked || !chosen || !validName || chosen.name === name} onClick={() => {
        if (chosen && validName) write(groups.map(group => group.id === chosen.id ? { ...group, name } : group));
      }}>重命名分组</Button>
      <Button disabled={blocked || !chosen} onClick={() => { if (!blocked && chosen) onSelect(visualGroupMembers(groups, chosen.id)); }}>选择分组成员</Button>
      <Button variant="ghost" disabled={blocked || !chosen} onClick={() => { if (chosen) write(promoteOrphanGroups(groups.filter(group => group.id !== chosen.id))); }}>移除分组（保留节点）</Button>
    </div>
    {chosen && <div className="graph-canvas__toolbar">
      <label htmlFor={`${labelId}-parent`}>父视觉分组</label>
      <select id={`${labelId}-parent`} value={parentChoice} disabled={blocked} onChange={event => setParentChoice(event.target.value)}>
        <option value="">无父组（顶层）</option>
        {groups.filter(group => group.id !== chosen.id && !group.parent_id && !groups.some(child => child.parent_id === chosen.id))
          .map(group => <option key={group.id} value={group.id}>{group.name}</option>)}
      </select>
      <Button disabled={blocked || parentChoice === (chosen.parent_id || '')} onClick={() => {
        if (blocked || parentChoice === (chosen.parent_id || '')) return;
        if (parentChoice && (!groups.some(group => group.id === parentChoice && group.id !== chosen.id && !group.parent_id)
          || groups.some(group => group.parent_id === chosen.id))) return;
        write(groups.map(group => {
          if (group.id !== chosen.id) return group;
          const { parent_id: _parent, ...root } = group;
          return parentChoice ? { ...root, parent_id: parentChoice } : root;
        }));
      }}>应用父组</Button>
    </div>}
    {chosen && <p className="graph-canvas__help">直属成员：{chosen.node_ids.join('、')}</p>}
    <p className="graph-canvas__help">最多 24 组，名称 1–80 个 Unicode 字符。每个节点只能属于一组；先移除原组才能重新分组。选择成员后拖动任一所选节点可整体移动；删节点同步清理成员，空组自动移除。通过保存创作图持久化，可撤销。折叠是下方独立的临时视图操作；视觉嵌套最多两层（顶层＋子组），非运行子工作流。父组选择、边框与折叠包含子组成员；移除父组或其直属节点清空时，子组提升至顶层且保留节点。小地图仍显示原节点，无子画布隔离。</p>
    {name && !validName && <p role="alert" className="graph-canvas__help">请输入非空且不超过 80 个字符的名称。</p>}
  </section>;
}
