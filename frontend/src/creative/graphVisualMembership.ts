import type { StudioGraphDefinition } from './studioGraphTypes';
import { promoteOrphanGroups, type VisualGroups } from './graphVisualHierarchy';
/** Presentation-only membership. Node identities, pins, edges and execution stay untouched. */
export function changeVisualMembership(definition: StudioGraphDefinition, selected: readonly string[],
  groupId: string, action: 'move' | 'remove'): VisualGroups | null {
  const groups = definition.presentation?.groups || [];
  const target = groups.find(group => group.id === groupId);
  if (!target || !selected.length || selected.length > 24 || new Set(selected).size !== selected.length
      || !selected.every(id => definition.nodes.some(node => node.id === id))) return null;
  const ids = new Set(selected);
  if (action === 'move') {
    const members = [...target.node_ids, ...selected.filter(id => !target.node_ids.includes(id))];
    if (members.length > 24 || members.length === target.node_ids.length) return null;
    return promoteOrphanGroups(groups.map(group => ({ ...group, node_ids: group.id === groupId
      ? members : group.node_ids.filter(id => !ids.has(id)) })).filter(group => group.node_ids.length > 0));
  }
  if (!target.node_ids.some(id => ids.has(id))) return null;
  return promoteOrphanGroups(groups.map(group => group.id === groupId
    ? { ...group, node_ids: group.node_ids.filter(id => !ids.has(id)) } : group)
    .filter(group => group.node_ids.length > 0));
}
