import { connectionIssue, graphId } from './graphDraft';
import { graphSelectionCopy, type GraphSelectionCopy } from './graphSelectionCopy';
import { visualGroupMembers } from './graphVisualHierarchy';
import type { StudioGraphCatalog, StudioGraphDefinition } from './studioGraphTypes';

type Group = NonNullable<NonNullable<StudioGraphDefinition['presentation']>['groups']>[number];
export type GraphVisualGroupCopy = GraphSelectionCopy & { groupCopy: { groups: Group[]; nested: number; promoted: number } };
/** Materialize visual hierarchy with a bounded selection; never create an executable subworkflow. */
export function graphVisualGroupCopy(definition: StudioGraphDefinition, selected: readonly string[], catalog: StudioGraphCatalog): GraphVisualGroupCopy {
  const groups = definition.presentation?.groups || [], ids = new Set(selected);
  const nodes = new Set(definition.nodes.map(node => node.id)), groupIds = new Set(groups.map(group => group.id));
  const members = groups.flatMap(group => group.node_ids);
  const id = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
  if (!selected.length || selected.length > 24 || ids.size !== selected.length || selected.some(value => !nodes.has(value))
    || nodes.size !== definition.nodes.length || new Set(definition.edges.map(edge => edge.id)).size !== definition.edges.length
    || groups.length > 24 || groupIds.size !== groups.length || new Set(members).size !== members.length
    || groups.some(group => !id.test(group.id) || !group.name.trim() || Array.from(group.name).length > 80
      || !group.node_ids.length || group.node_ids.length > 24 || group.node_ids.some(value => !nodes.has(value))
      || group.parent_id !== undefined && (!groups.some(parent => parent.id === group.parent_id && parent.id !== group.id && parent.parent_id === undefined)))) {
    throw new Error('当前选择或视觉分组结构无效；未复制任何内容。');
  }
  const touched = groups.filter(group => group.node_ids.some(value => ids.has(value)));
  if (!touched.length) throw new Error('请先选择至少一个完整视觉分组。');
  if (touched.some(group => visualGroupMembers(groups, group.id).some(value => !ids.has(value)))) {
    throw new Error('选择包含不完整分组；请用“选择分组成员”包含父组及子组，再重新预览。');
  }
  if (groups.length + touched.length > 24) throw new Error('复制将超过原有 24 个视觉分组限制；未复制任何内容。');
  const result = graphSelectionCopy(definition, selected, catalog);
  const mapping = new Map(definition.nodes.filter(node => ids.has(node.id)).map((node, index) => [node.id, result.selected[index]]));
  const occupied = new Set([...definition.nodes, ...definition.edges, ...groups, ...(definition.presentation?.notes || []),
    ...result.definition.nodes, ...result.definition.edges].map(row => row.id));
  const groupMapping = new Map(touched.map(group => {
    const fresh = graphId('group');
    if (!id.test(fresh) || occupied.has(fresh)) throw new Error('新分组标识冲突，请重新预览。');
    occupied.add(fresh); return [group.id, fresh];
  }));
  let promoted = 0;
  const copied: Group[] = touched.map(group => {
    const { parent_id, ...value } = group;
    if (parent_id && !groupMapping.has(parent_id)) promoted++;
    return { ...structuredClone(value), id: groupMapping.get(group.id)!, node_ids: group.node_ids.map(value => mapping.get(value)!),
      ...(parent_id && groupMapping.has(parent_id) ? { parent_id: groupMapping.get(parent_id)! } : {}) };
  });
  const next = { ...result.definition, presentation: { ...result.definition.presentation, groups: [...structuredClone(groups), ...copied] } };
  for (const edge of next.edges.slice(definition.edges.length)) {
    const issue = connectionIssue({ ...next, edges: next.edges.filter(row => row.id !== edge.id) }, catalog.definitions, edge);
    if (issue) throw new Error(`所选内部连接无效：${issue}`);
  }
  if (new TextEncoder().encode(JSON.stringify(next)).length > catalog.limits.definition_bytes) throw new Error('复制完整分组将超过原图大小限制；未复制任何内容。');
  return { ...result, definition: next, groupCopy: { groups: copied, nested: copied.filter(group => group.parent_id).length, promoted } };
}
