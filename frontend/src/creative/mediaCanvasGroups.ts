import { checkedCanvasDefinition, type CanvasDefinition, type CanvasDisplayGroup } from './studioCanvasViewClient';
export function canvasGroupMembers(groups: CanvasDisplayGroup[], id: string): Set<string> {
  const descendants = new Set([id]); for (let i = 0; i < 8; i++) for (const group of groups) if (group.parent_id && descendants.has(group.parent_id)) descendants.add(group.id);
  return new Set(groups.filter(group => descendants.has(group.id)).flatMap(group => group.card_ids));
}
export function canvasHiddenCards(definition: CanvasDefinition): Set<string> {
  const groups = definition.groups ?? [], hidden = new Set<string>();
  for (const group of groups) if (group.collapsed) for (const id of canvasGroupMembers(groups, group.id)) hidden.add(id);
  return hidden;
}
export function replaceCanvasGroups(definition: CanvasDefinition, groups: CanvasDisplayGroup[]): CanvasDefinition {
  const { groups: _old, ...base } = definition; return checkedCanvasDefinition({ ...base, ...(groups.length ? { groups } : {}) });
}
export function assignCanvasCard(definition: CanvasDefinition, card: string, groupId?: string) {
  if (!definition.cards.some(c => c.id === card) || groupId !== undefined && !definition.groups?.some(g => g.id === groupId)) throw new Error('卡片或分组已改变。');
  return replaceCanvasGroups(definition, (definition.groups ?? []).map(g => ({ ...g, card_ids: [...g.card_ids.filter(id => id !== card), ...(g.id === groupId ? [card] : [])] })));
}
export function dissolveCanvasGroup(definition: CanvasDefinition, id: string) {
  const group = definition.groups?.find(g => g.id === id); if (!group) throw new Error('分组已改变。');
  return replaceCanvasGroups(definition, definition.groups!.filter(g => g.id !== id).map(g => { if (g.parent_id !== id) return g;
    const { parent_id: _old, ...rest } = g; return { ...rest, ...(group.parent_id ? { parent_id: group.parent_id } : {}) }; }));
}
export function removeCanvasCard(definition: CanvasDefinition, id: string) {
  return replaceCanvasGroups({ ...definition, cards: definition.cards.filter(c => c.id !== id) }, (definition.groups ?? []).map(g => ({ ...g, card_ids: g.card_ids.filter(c => c !== id) })));
}
export function canvasGroupFrames(definition: CanvasDefinition) {
  const groups = definition.groups ?? [], byId = new Map(groups.map(g => [g.id, g]));
  return groups.flatMap(group => {
    let parent = group.parent_id; for (let depth = 0; parent && depth < 8; depth++) { const row = byId.get(parent); if (row?.collapsed) return []; parent = row?.parent_id; }
    const members = canvasGroupMembers(groups, group.id), cards = definition.cards.filter(c => members.has(c.id)); if (!cards.length) return [];
    const x = Math.min(...cards.map(c => c.position.x)) - 16, y = Math.min(...cards.map(c => c.position.y)) - 40;
    const right = Math.max(...cards.map(c => c.position.x + 240)) + 16, bottom = Math.max(...cards.map(c => c.position.y + 120)) + 16;
    return [{ group, x, y, width: group.collapsed ? 240 : right - x, height: group.collapsed ? 64 : bottom - y, members: members.size }];
  });
}
