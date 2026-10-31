import type { StudioGraphDefinition } from './studioGraphTypes';
export type VisualGroups = NonNullable<NonNullable<StudioGraphDefinition['presentation']>['groups']>;
/** Two levels only; members remain disjoint in storage. No execution projection. */
export function visualGroupMembers(groups: VisualGroups, id: string): string[] {
  return groups.filter(group => group.id === id || group.parent_id === id).flatMap(group => group.node_ids);
}
export function promoteOrphanGroups(groups: VisualGroups): VisualGroups {
  const ids = new Set(groups.map(group => group.id));
  return groups.map(group => {
    if (group.parent_id !== undefined && !ids.has(group.parent_id)) {
      const { parent_id: _parent, ...root } = group;
      return root;
    }
    return group;
  });
}
