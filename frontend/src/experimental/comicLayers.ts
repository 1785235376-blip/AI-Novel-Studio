import type { ComicDocument, ComicLayer, ComicLayerKind } from './comicLayoutsClient';

const MAX_LAYERS = 256;
const layerKey = (layer: Pick<ComicLayer, 'kind' | 'target_id'>) => `${layer.kind}:${layer.target_id}`;
const validId = (id: unknown): id is string => typeof id === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(id);
export const comicLayerKindLabel: Record<ComicLayerKind, string> = {
  PANEL_ART: '格框图片', PANEL_FRAME: '格框边框', BUBBLE_SHAPE: '气泡形状', BUBBLE_TEXT: '气泡文字',
};

/** Legacy painter order: each panel's art/frame followed by its bubbles' shape/text. */
function coverage(document: ComicDocument): Omit<ComicLayer, 'id'>[] {
  const items: Omit<ComicLayer, 'id'>[] = [];
  const panelIds = new Set<string>(), bubbleIds = new Set<string>();
  for (const panel of [...document.panels].sort((a, b) => a.order - b.order)) {
    if (!validId(panel.id) || panelIds.has(panel.id)) throw new Error('格框标识无效或重复，不能修改图层。');
    panelIds.add(panel.id);
    const add = (kind: ComicLayerKind, target_id: string, name: string) => items.push({ kind, target_id, name, visible: true, opacity_percent: 100 });
    add('PANEL_ART', panel.id, `格框 ${panel.order} · 图片`);
    add('PANEL_FRAME', panel.id, `格框 ${panel.order} · 边框`);
    panel.bubbles.forEach((bubble, index) => {
      if (!validId(bubble.id) || bubbleIds.has(bubble.id)) throw new Error('气泡标识无效或重复，不能修改图层。');
      bubbleIds.add(bubble.id);
      add('BUBBLE_SHAPE', bubble.id, `格框 ${panel.order} · 气泡 ${index + 1} · 形状`);
      add('BUBBLE_TEXT', bubble.id, `格框 ${panel.order} · 气泡 ${index + 1} · 文字`);
    });
  }
  if (items.length > MAX_LAYERS) throw new Error('图层最多 256 个；请减少格框或气泡。');
  return items;
}

function validateItems(items: ComicLayer[]) {
  if (!Array.isArray(items) || items.length > MAX_LAYERS) throw new Error('图层结构无效或超过 256 个。');
  const ids = new Set<string>(), targets = new Set<string>();
  for (const layer of items) {
    if (!layer || !validId(layer.id) || !/^layer_[A-Za-z0-9_-]{1,74}$/.test(layer.id) || ids.has(layer.id)
      || !Object.hasOwn(comicLayerKindLabel, layer.kind) || !validId(layer.target_id)
      || typeof layer.name !== 'string' || Array.from(layer.name).length < 1 || Array.from(layer.name).length > 120
      || Array.from(layer.name).some(character => { const point = character.codePointAt(0)!; return point < 32 || (point >= 0xd800 && point <= 0xdfff) || point === 0xfffe || point === 0xffff; })
      || typeof layer.visible !== 'boolean' || !Number.isInteger(layer.opacity_percent) || layer.opacity_percent < 0 || layer.opacity_percent > 100
      || targets.has(layerKey(layer))) throw new Error('图层字段或标识无效。请重新打开有效版本；不会重置图层修改。');
    ids.add(layer.id); targets.add(layerKey(layer));
  }
}

export function comicLayersError(document: ComicDocument): string | undefined {
  if (document.layer_stack === undefined) return undefined;
  try {
    if (!document.layer_stack || document.layer_stack.schema_version !== 1) throw new Error('不支持此图层版本。');
    validateItems(document.layer_stack.items);
    const expected = new Set(coverage(document).map(layerKey));
    if (document.layer_stack.items.length !== expected.size || document.layer_stack.items.some(layer => !expected.has(layerKey(layer)))) throw new Error('图层与格框或气泡不匹配。请重新打开有效版本；不会丢弃图层修改。');
  } catch (error) { return error instanceof Error ? error.message : '图层结构无效。'; }
}

function allocator(document: ComicDocument, layers: ComicLayer[]) {
  const used = new Set([...layers.map(layer => layer.id), ...document.panels.flatMap(panel => [panel.id, ...panel.bubbles.map(bubble => bubble.id)])]);
  let index = 1;
  return () => { while (used.has(`layer_${index}`)) index++; const id = `layer_${index++}`; used.add(id); return id; };
}

/** Only called by explicit enable intent. Legacy drafts remain byte-compatible. */
export function enableComicLayers(document: ComicDocument): ComicDocument {
  if (document.layer_stack !== undefined) {
    const error = comicLayersError(document); if (error) throw new Error(error);
    return document;
  }
  const nextId = allocator(document, []);
  return { ...document, layer_stack: { schema_version: 1, items: coverage(document).map(layer => ({ ...layer, id: nextId() })) } };
}

/** Structural edits remove only deleted targets and append new targets at the top.
 * Surviving layers retain their exact IDs, stacking order and authored properties.
 * A previously enabled stack may never be silently dropped or regenerated. */
export function reconcileComicLayers(before: ComicDocument, next: ComicDocument): ComicDocument {
  const priorError = comicLayersError(before); if (priorError) throw new Error(priorError);
  if (before.layer_stack === undefined) {
    const error = comicLayersError(next); if (error) throw new Error(error);
    return next;
  }
  if (!next.layer_stack || next.layer_stack.schema_version !== 1) throw new Error('此操作会丢弃图层，请保留当前图层并手工调整布局。');
  validateItems(next.layer_stack.items);
  const expected = coverage(next), keys = new Set(expected.map(layerKey));
  const items = next.layer_stack.items.filter(layer => keys.has(layerKey(layer)));
  const existing = new Set(items.map(layerKey)), nextId = allocator(next, next.layer_stack.items);
  const additions = expected.filter(layer => !existing.has(layerKey(layer))).map(layer => ({ ...layer, id: nextId() }));
  if (items.length === next.layer_stack.items.length && !additions.length) return next;
  return { ...next, layer_stack: { schema_version: 1, items: [...items, ...additions] } };
}

/** Copy source appearance/order to fresh canonical targets, never alias the source. */
export function duplicateComicLayers(before: ComicDocument, next: ComicDocument, panelId: string, copyPanelId: string, bubbleIds: Map<string, string>): ComicDocument {
  if (before.layer_stack === undefined) return next;
  const error = comicLayersError(before); if (error) throw new Error(error);
  const sourceLayers = before.layer_stack.items.filter(layer => layer.kind.startsWith('PANEL_') ? layer.target_id === panelId : bubbleIds.has(layer.target_id));
  const nextId = allocator(next, before.layer_stack.items);
  const copies = sourceLayers.map(layer => ({ ...layer, id: nextId(), target_id: layer.kind.startsWith('PANEL_') ? copyPanelId : bubbleIds.get(layer.target_id)! }));
  const result: ComicDocument = { ...next, layer_stack: { schema_version: 1, items: [...before.layer_stack.items, ...copies] } };
  const resultError = comicLayersError(result); if (resultError) throw new Error(resultError);
  return result;
}
