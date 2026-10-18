import { expect, it } from 'vitest';
import type { ComicDocument, ComicRasterLayer } from './comicLayoutsClient';
import { comicLayersError, enableComicLayers, reconcileComicLayers, duplicateComicLayers } from './comicLayers';
const raster: ComicRasterLayer = { id: 'layer_raster', kind: 'RASTER', target_id: 'asset', name: '外部 👩🏽‍🚀', visible: false, opacity_percent: 42, x: -20, y: 10, width: 100, height: 100, pin: { version: 2, sha256: 'a'.repeat(64), review_digest: 'b'.repeat(64) } };
const fixture = (): ComicDocument => ({ title: 'Raster', source_mode: 'INDEPENDENT', screenplay_id: null, expected_screenplay_version: null, preset: 'PAGE', font_family: 'NOTO_SANS_SC_OFL', width: 320, height: 640, safe_area: 8, segment_height: 320, panels: [], layer_stack: { schema_version: 1, items: [structuredClone(raster)] } });
it('reopen and native structural reconciliation retain exact raster identity, pin and placement', () => {
  const before = fixture(), reopened = JSON.parse(JSON.stringify(before));
  expect(comicLayersError(reopened)).toBeUndefined(); expect(enableComicLayers(reopened)).toBe(reopened);
  const next = reconcileComicLayers(before, { ...reopened, title: 'Renamed' });
  expect(next.layer_stack!.items).toEqual([raster]);
  expect(duplicateComicLayers(before, next, 'native', 'native-copy', new Map()).layer_stack!.items).toEqual([raster]);
});
it('allows bounded position, opacity, visibility, name changes without changing pins', () => {
  const before = fixture(), next = fixture(); next.layer_stack!.items[0] = { ...raster, x: 12000, y: -12000, name: 'Edited', visible: true, opacity_percent: 0 };
  expect(reconcileComicLayers(before, next)).toEqual(next); expect(comicLayersError(next)).toBeUndefined();
});
it.each(['missing', 'dimensions', 'asset', 'pin', 'coupled'])('refuses destructive raster %s edits', change => {
  const before = fixture(), next = fixture(), layer = next.layer_stack!.items[0] as ComicRasterLayer;
  if (change === 'missing') next.layer_stack!.items = [];
  if (change === 'dimensions') layer.width++;
  if (change === 'asset') layer.target_id = 'other';
  if (change === 'pin') layer.pin.sha256 = 'c'.repeat(64);
  if (change === 'coupled') next.source_mode = 'SCREENPLAY';
  expect(() => reconcileComicLayers(before, next)).toThrow();
});
it.each(['fraction', 'outside', 'version', 'digest', 'pixels', 'coupled', 'duplicate'])('fails closed on invalid raster %s', change => {
  const doc = fixture(), layer = doc.layer_stack!.items[0] as ComicRasterLayer;
  if (change === 'fraction') layer.x = 0.1;
  if (change === 'outside') layer.y = -12001;
  if (change === 'version') layer.pin.version = 1;
  if (change === 'digest') layer.pin.review_digest = 'invalid';
  if (change === 'pixels') { layer.width = 16000; layer.height = 16000; }
  if (change === 'coupled') doc.source_mode = 'SCREENPLAY';
  if (change === 'duplicate') doc.layer_stack!.items.push({ ...layer });
  expect(comicLayersError(doc)).toBeTruthy();
});
it('native panel copies get unique IDs while raster pins appear once, unchanged', () => {
  const before = fixture(); before.panels = [{ id: 'p', shot_id: null, artwork_mode: 'BLANK', order: 1, character_ids: [], asset_id: null, expected_asset_version: null, fit: 'CONTAIN', x: 8, y: 8, width: 100, height: 100, bubbles: [] }];
  before.layer_stack!.items.push({ id: 'layer_art', kind: 'PANEL_ART', target_id: 'p', name: 'Art', visible: true, opacity_percent: 100 }, { id: 'layer_frame', kind: 'PANEL_FRAME', target_id: 'p', name: 'Frame', visible: true, opacity_percent: 100 });
  const next = duplicateComicLayers(before, { ...before, panels: [...before.panels, { ...before.panels[0], id: 'copy', order: 2, y: 120 }] }, 'p', 'copy', new Map());
  expect(next.layer_stack!.items.filter(layer => layer.kind === 'RASTER')).toEqual([raster]);
  expect(new Set(next.layer_stack!.items.map(layer => layer.id)).size).toBe(5);
  expect(next.layer_stack!.items.slice(-2).map(layer => layer.target_id)).toEqual(['copy', 'copy']);
  expect(comicLayersError(next)).toBeUndefined();
});
