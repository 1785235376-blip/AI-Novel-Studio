import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import type { ComicCatalog, ComicDocument } from './comicLayoutsClient';
import { comicLayersError, duplicateComicLayers, enableComicLayers, reconcileComicLayers } from './comicLayers';
import { applyComicDuplicate, previewComicDuplicate } from './comicDuplication';
import { arrangeComicVertically } from './comicArrangement';
import { previewComicReadingOrder } from './comicReadingOrder';

const fixture = JSON.parse(readFileSync(new URL('../../../tests/fixtures/comic_panel_duplicate.json', import.meta.url), 'utf8'));
const legacy = () => structuredClone(fixture.document) as ComicDocument;
const catalog = { screenplays: [{ id: 'screenplay', edit_version: 1, shots: [{ id: 'shot' }] }], characters: [{ id: 'alice' }], assets: [{ id: 'asset', version: 2, approved: true }] } as ComicCatalog;
function authored() {
  const document = enableComicLayers(legacy());
  document.layer_stack!.items.reverse();
  document.layer_stack!.items.forEach((layer, index) => { layer.name = `自定 ${index} 👩🏽‍🚀`; layer.visible = index % 2 === 0; layer.opacity_percent = index * 19; });
  return document;
}
it('explicit enable preserves legacy pixels order including blank artwork and canonical text', () => {
  const document = legacy(), before = structuredClone(document);
  document.panels[0].artwork_mode = 'BLANK';
  const enabled = enableComicLayers(document), stack = enabled.layer_stack!;
  expect(stack.schema_version).toBe(1);
  expect(stack.items.map(layer => layer.kind)).toEqual(['PANEL_ART', 'PANEL_FRAME', 'BUBBLE_SHAPE', 'BUBBLE_TEXT']);
  expect(stack.items.map(layer => layer.target_id)).toEqual(['authored', 'authored', 'speech', 'speech']);
  expect(stack.items.every(layer => layer.id.startsWith('layer_') && layer.visible && layer.opacity_percent === 100)).toBe(true);
  expect(enabled.panels).toBe(document.panels);
  expect(enabled.panels[0].bubbles[0].text).toBe(before.panels[0].bubbles[0].text);
  expect(document).not.toHaveProperty('layer_stack'); expect(enableComicLayers(enabled)).toBe(enabled);
});
it('omission stays absent through edits, arrangement, reading-number changes and duplication', () => {
  const document = legacy();
  expect(reconcileComicLayers(document, { ...document, title: 'New' })).not.toHaveProperty('layer_stack');
  expect(arrangeComicVertically(document).document).not.toHaveProperty('layer_stack');
  expect(previewComicReadingOrder(document).document).not.toHaveProperty('layer_stack');
  expect(applyComicDuplicate(document, catalog, fixture.target, fixture.ids).document).not.toHaveProperty('layer_stack');
});
it('add/remove covers only canonical additions/removals without resetting unrelated edits', () => {
  const document = authored(), before = structuredClone(document);
  const newBubble = { ...document.panels[0].bubbles[0], id: 'new-bubble' };
  const added = reconcileComicLayers(document, { ...document, panels: [{ ...document.panels[0], bubbles: [...document.panels[0].bubbles, newBubble] }] });
  expect(added.layer_stack!.items.slice(0, 4)).toEqual(document.layer_stack!.items);
  expect(added.layer_stack!.items.slice(4).map(layer => [layer.kind, layer.target_id])).toEqual([['BUBBLE_SHAPE', 'new-bubble'], ['BUBBLE_TEXT', 'new-bubble']]);
  expect(comicLayersError(added)).toBeUndefined();
  const removed = reconcileComicLayers(added, { ...added, panels: [{ ...added.panels[0], bubbles: [newBubble] }] });
  expect(removed.layer_stack!.items.filter(layer => layer.target_id === 'authored')).toEqual(document.layer_stack!.items.filter(layer => layer.target_id === 'authored'));
  expect(removed.layer_stack!.items.some(layer => layer.target_id === 'speech')).toBe(false);
  expect(reconcileComicLayers(removed, { ...removed, panels: [] }).layer_stack!.items).toEqual([]);
  expect(document).toEqual(before);
});
it('copy remaps every target with fresh layer IDs and preserves source-layer order and properties', () => {
  const document = authored(), before = structuredClone(document);
  const next = applyComicDuplicate(document, catalog, fixture.target, fixture.ids).document!;
  const originals = document.layer_stack!.items, copies = next.layer_stack!.items.slice(originals.length);
  expect(next.panels[1]).toEqual(fixture.expectedPanel);
  expect(next.layer_stack!.items.slice(0, originals.length)).toEqual(originals);
  expect(copies).toHaveLength(originals.length);
  copies.forEach((layer, index) => {
    expect(layer.id).not.toBe(originals[index].id);
    expect(layer).toEqual({ ...originals[index], id: layer.id, target_id: originals[index].kind.startsWith('PANEL_') ? 'duplicate' : 'duplicate-speech' });
  });
  expect(new Set(next.layer_stack!.items.map(layer => layer.id)).size).toBe(8);
  expect(comicLayersError(next)).toBeUndefined(); expect(document).toEqual(before);
});
it('coordinate and reading-order changes preserve the entire authored stack and canonical bubble offsets', () => {
  const document = authored();
  const next = arrangeComicVertically(document).document!;
  expect(next.layer_stack).toBe(document.layer_stack);
  expect(next.panels[0].bubbles[0].x - next.panels[0].x).toBe(document.panels[0].bubbles[0].x - document.panels[0].x);
  expect(previewComicReadingOrder(document).document.layer_stack).toBe(document.layer_stack);
});
it('rejects destructive preset resets and malformed stacks rather than repairing authored data', () => {
  const document = authored();
  const { layer_stack: _removed, ...withoutLayers } = document;
  expect(() => reconcileComicLayers(document, withoutLayers)).toThrow(/丢弃图层/);
  document.layer_stack!.items.pop();
  expect(comicLayersError(document)).toMatch(/不匹配/);
  expect(previewComicDuplicate(document, catalog, fixture.target).panel).toBeUndefined();
  expect(arrangeComicVertically(document).document).toBeUndefined();
  expect(() => reconcileComicLayers(document, { ...document, panels: [] })).toThrow();
});
it.each(['id', 'target', 'kind', 'duplicate', 'visible', 'opacity', 'fraction', 'name', 'empty-name', 'control-name', 'schema'] as const)('fails closed on malformed %s', kind => {
  const document = authored(), layer = document.layer_stack!.items[0];
  if (kind === 'id') layer.id = 'unprefixed';
  if (kind === 'target') layer.target_id = 'missing';
  if (kind === 'kind') (layer as unknown as { kind: string }).kind = 'ARBITRARY';
  if (kind === 'duplicate') document.layer_stack!.items.push({ ...layer });
  if (kind === 'visible') (layer as unknown as { visible: unknown }).visible = 'false';
  if (kind === 'opacity') layer.opacity_percent = 101;
  if (kind === 'fraction') layer.opacity_percent = 5.5;
  if (kind === 'name') layer.name = '字'.repeat(121);
  if (kind === 'empty-name') layer.name = '';
  if (kind === 'control-name') layer.name = 'New\nline';
  if (kind === 'schema') (document.layer_stack as unknown as { schema_version: number }).schema_version = 2;
  expect(comicLayersError(document)).toBeTruthy(); expect(() => enableComicLayers(document)).toThrow();
});
it('bounded IDs avoid collisions with canonical and existing layer identifiers', () => {
  const document = legacy(); document.panels[0].id = 'layer_1'; document.panels[0].bubbles[0].id = 'layer_2';
  const enabled = enableComicLayers(document);
  expect(enabled.layer_stack!.items.map(layer => layer.id)).toEqual(['layer_3', 'layer_4', 'layer_5', 'layer_6']);
});
it('enforces the layer capacity before enabling or adding data', () => {
  const document = legacy();
  document.panels[0].bubbles = Array.from({ length: 128 }, (_, index) => ({ ...document.panels[0].bubbles[0], id: `b${index}` }));
  expect(() => enableComicLayers(document)).toThrow(/256/);
});
it('new copy helper retains absence without inventing a stack', () => {
  const document = legacy(); expect(duplicateComicLayers(document, document, 'authored', 'copy', new Map())).toBe(document);
});
