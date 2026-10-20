import { checkedLocalGraphDefinition } from './studioGraphLocalDraft';
import { graphSelectionCopy } from './graphSelectionCopy';
import { graphId } from './graphDraft';
import { GRAPH_POSITION_LIMIT } from './graphCanvasGeometry';
import { graphNoteDefinitionBytes } from './graphCanvasNotesHelpers';
import type { StudioGraphCatalog, StudioGraphDefinition } from './studioGraphTypes';
export const TEXT_GRAPH_TEMPLATE_CONTRACT = 'poemseed-text-graph-template/1';
export const TEXT_GRAPH_TEMPLATE_PRESENTATION_CONTRACT = 'poemseed-text-graph-template/2';
export const TEXT_GRAPH_TEMPLATE_BYTES = 110_000;
function portable(value: unknown, presentation = false): StudioGraphDefinition {
  const definition = checkedLocalGraphDefinition(value);
  if (![1, 2].includes(definition.schema_version)) throw new Error('便携文字模板仅支持文字图 v1/v2。');
  if (!definition.nodes.length) throw new Error('文字图模板至少需要一个节点。');
  // Only original visual authoring fields are portable. Owner, graph comment,
  // target view preferences, source bindings and execution authority stay out.
  const groups = presentation ? definition.presentation?.groups : undefined, notes = presentation ? definition.presentation?.notes : undefined;
  return { schema_version: definition.schema_version, title: definition.title, nodes: definition.nodes, edges: definition.edges, viewport: definition.viewport,
    ...(groups?.length || notes?.length ? { presentation: { ...(groups?.length ? { groups } : {}), ...(notes?.length ? { notes } : {}) } } : {}) };
}
export function exportTextGraphTemplate(definition: StudioGraphDefinition): string {
  const content = portable(definition, true);
  const raw = JSON.stringify({ contract: content.presentation ? TEXT_GRAPH_TEMPLATE_PRESENTATION_CONTRACT : TEXT_GRAPH_TEMPLATE_CONTRACT, definition: content });
  if (new TextEncoder().encode(raw).length > TEXT_GRAPH_TEMPLATE_BYTES) throw new Error('模板超过大小上限。');
  return raw;
}
function noExtraFields(raw: unknown, normalized: unknown): void {
  if (Array.isArray(raw)) { if (!Array.isArray(normalized) || raw.length !== normalized.length) throw new Error('模板结构不正确。'); raw.forEach((value, index) => noExtraFields(value, normalized[index])); }
  else if (raw && typeof raw === 'object') {
    if (!normalized || typeof normalized !== 'object' || Array.isArray(normalized)) throw new Error('模板结构不正确。');
    for (const key of Object.keys(raw)) { if (!Object.hasOwn(normalized, key)) throw new Error('模板包含不允许的额外字段。'); noExtraFields((raw as Record<string, unknown>)[key], (normalized as Record<string, unknown>)[key]); }
  }
}
export function readTextGraphTemplate(raw: string): StudioGraphDefinition {
  if (typeof raw !== 'string' || new TextEncoder().encode(raw).length > TEXT_GRAPH_TEMPLATE_BYTES) throw new Error('模板超过大小上限。');
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('模板格式不正确。');
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !['contract', 'definition'].includes(key)) || ![TEXT_GRAPH_TEMPLATE_CONTRACT, TEXT_GRAPH_TEMPLATE_PRESENTATION_CONTRACT].includes(row.contract as string)) throw new Error('只接受受限文字图模板，不接收权限或运行回执。');
  const definition = portable(row.definition, row.contract === TEXT_GRAPH_TEMPLATE_PRESENTATION_CONTRACT);
  noExtraFields(row.definition, definition);
  return definition;
}
export function planTextGraphTemplate(raw: string, target: StudioGraphDefinition, catalog: StudioGraphCatalog) {
  const source = readTextGraphTemplate(raw);
  const result = graphSelectionCopy(source, source.nodes.map(node => node.id), catalog, target);
  const groups = source.presentation?.groups || [], notes = source.presentation?.notes || [];
  if ((target.presentation?.groups?.length || 0) + groups.length > 24 || (target.presentation?.notes?.length || 0) + notes.length > 1024) throw new Error('模板追加将超过原分组或便笺数量限制。');
  const oldVisualIds = new Set([...(source.presentation?.groups || []), ...(source.presentation?.notes || []), ...(target.presentation?.groups || []), ...(target.presentation?.notes || [])].map(row => row.id));
  const added = [...result.definition.nodes.slice(target.nodes.length), ...result.definition.edges.slice(target.edges.length)];
  if (added.some(row => oldVisualIds.has(row.id))) throw new Error('新节点或连接与视觉标识冲突，请重新预览。');
  const occupied = new Set([...target.nodes, ...target.edges, ...source.nodes, ...source.edges, ...added].map(row => row.id));
  for (const id of oldVisualIds) occupied.add(id);
  const fresh = (prefix: string) => { const id = graphId(prefix); if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id) || occupied.has(id)) throw new Error('新视觉标识冲突，请重新预览。'); occupied.add(id); return id; };
  const nodeIds = new Map(source.nodes.map((node, index) => [node.id, result.selected[index]]));
  const groupIds = new Map(groups.map(group => [group.id, fresh('group')]));
  const copiedGroups = groups.map(group => ({ ...structuredClone(group), id: groupIds.get(group.id)!, node_ids: group.node_ids.map(id => nodeIds.get(id)!), ...(group.parent_id ? { parent_id: groupIds.get(group.parent_id)! } : {}) }));
  const copiedNotes = notes.map(note => {
    const position = { x: note.position.x + result.delta.x, y: note.position.y + result.delta.y };
    if (Math.abs(position.x) > GRAPH_POSITION_LIMIT || Math.abs(position.y) > GRAPH_POSITION_LIMIT) throw new Error('便笺追加后超出原画布边界，未追加任何内容。');
    return { ...structuredClone(note), id: fresh('note'), position };
  });
  const definition = { ...result.definition, ...(copiedGroups.length || copiedNotes.length ? { presentation: { ...result.definition.presentation,
    ...(copiedGroups.length ? { groups: [...structuredClone(target.presentation?.groups || []), ...copiedGroups] } : {}),
    ...(copiedNotes.length ? { notes: [...structuredClone(target.presentation?.notes || []), ...copiedNotes] } : {}) } } : {}) };
  if (graphNoteDefinitionBytes(definition) > catalog.limits.definition_bytes) throw new Error('模板追加将超过原图定义大小限制。');
  checkedLocalGraphDefinition(definition);
  return { sourceTitle: source.title, groupCount: groups.length, noteCount: notes.length, result: { ...result, definition } };
}
