import { checkedLocalGraphDefinition } from './studioGraphLocalDraft';
import { graphSelectionCopy } from './graphSelectionCopy';
import type { StudioGraphCatalog, StudioGraphDefinition } from './studioGraphTypes';
export const TEXT_GRAPH_TEMPLATE_CONTRACT = 'poemseed-text-graph-template/1';
export const TEXT_GRAPH_TEMPLATE_BYTES = 110_000;
function portable(value: unknown): StudioGraphDefinition {
  const definition = checkedLocalGraphDefinition(value);
  if (!definition.nodes.length) throw new Error('文字图模板至少需要一个节点。');
  // No owner, saved id, source binding, approval, run/cache receipt or presentation notes.
  return { schema_version: definition.schema_version, title: definition.title, nodes: definition.nodes, edges: definition.edges, viewport: definition.viewport };
}
export function exportTextGraphTemplate(definition: StudioGraphDefinition): string {
  const raw = JSON.stringify({ contract: TEXT_GRAPH_TEMPLATE_CONTRACT, definition: portable(definition) });
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
  if (Object.keys(row).some(key => !['contract', 'definition'].includes(key)) || row.contract !== TEXT_GRAPH_TEMPLATE_CONTRACT) throw new Error('只接受受限文字图模板，不接收权限或运行回执。');
  const definition = portable(row.definition);
  noExtraFields(row.definition, definition);
  return definition;
}
export function planTextGraphTemplate(raw: string, target: StudioGraphDefinition, catalog: StudioGraphCatalog) {
  const source = readTextGraphTemplate(raw);
  return { sourceTitle: source.title, result: graphSelectionCopy(source, source.nodes.map(node => node.id), catalog, target) };
}
