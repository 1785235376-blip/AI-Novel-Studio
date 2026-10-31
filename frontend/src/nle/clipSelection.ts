/** Selection is local view state over the current validated clip order. */
export function normalizeClipSelection(selected: unknown, clipOrder: readonly string[]): string[] {
  const requested = new Set(Array.isArray(selected) ? selected.filter((id): id is string => typeof id === 'string') : []);
  return [...new Set(clipOrder)].filter(id => requested.has(id));
}

export function sameClipSelection(left: unknown, right: readonly string[]): boolean {
  return Array.isArray(left) && left.length === right.length && left.every((id, index) => id === right[index]);
}

export function toggleClipSelection(selected: unknown, clipId: string, clipOrder: readonly string[]): string[] {
  const next = new Set(normalizeClipSelection(selected, clipOrder));
  if (!clipOrder.includes(clipId)) return [...next];
  if (next.has(clipId)) next.delete(clipId); else next.add(clipId);
  return normalizeClipSelection([...next], clipOrder);
}
