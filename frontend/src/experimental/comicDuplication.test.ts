import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import { applyComicDuplicate, previewComicDuplicate } from './comicDuplication';
import type { ComicCatalog, ComicDocument } from './comicLayoutsClient';
const fixture = JSON.parse(readFileSync(new URL('../../../tests/fixtures/comic_panel_duplicate.json', import.meta.url), 'utf8'));
function setup() {
  const document = structuredClone(fixture.document) as ComicDocument;
  const catalog = { screenplays: [{ id: 'screenplay', edit_version: 1, shots: [{ id: 'shot' }] }], characters: [{ id: 'alice' }], assets: [{ id: 'asset', version: 2, approved: true }] } as ComicCatalog;
  return { document, catalog, target: { ...fixture.target } };
}
it('matches the shared File-owner regression fixture and never changes the source', () => {
  const { document, catalog, target } = setup(), before = JSON.stringify(document);
  const preview = previewComicDuplicate(document, catalog, target);
  expect(preview.panel?.id).toBe('authored'); expect(preview.panel?.bubbles[0].id).toBe('speech');
  const next = applyComicDuplicate(document, catalog, target, fixture.ids).document!;
  expect(next.panels[1]).toEqual(fixture.expectedPanel); expect(next.panels[0]).toBe(document.panels[0]);
  expect(JSON.stringify(document)).toBe(before);
  expect(next.panels[1].character_ids).not.toBe(document.panels[0].character_ids);
  expect(next.panels[1].appearance_references![0]).not.toBe(document.panels[0].appearance_references![0]);
});
it('keeps exact Unicode, optional legacy crop omission, dimensions and bubble styles', () => {
  const { document, catalog, target } = setup();
  delete document.panels[0].cover_x_percent; delete document.panels[0].cover_y_percent;
  document.panels[0].bubbles[0].text = '你好 👩🏽‍🚀\né';
  const copy = applyComicDuplicate(document, catalog, target, fixture.ids).document!.panels[1];
  expect(copy).not.toHaveProperty('cover_x_percent'); expect(copy).not.toHaveProperty('cover_y_percent');
  expect(copy.bubbles[0]).toEqual({ ...document.panels[0].bubbles[0], id: 'duplicate-speech', x: 168, y: 344 });
});
it.each(['bounds', 'overlap', 'order', 'fraction', 'nan', 'bubble', 'stale', 'shot', 'asset', 'approval', 'appearance', 'character', 'font', 'surrogate', 'crop', 'pixel', 'segment'] as const)('rejects %s atomically', kind => {
  const { document, catalog, target } = setup();
  if (kind === 'bounds') target.x = 300;
  if (kind === 'overlap') { target.x = 16; target.y = 16; }
  if (kind === 'order') { document.panels[0].y = 400; document.panels[0].bubbles[0].y = 408; target.y = 16; }
  if (kind === 'fraction') target.y = 336.5;
  if (kind === 'nan') target.x = NaN;
  if (kind === 'bubble') document.panels[0].bubbles[0].x = 17;
  if (kind === 'stale') catalog.screenplays[0].edit_version++;
  if (kind === 'shot') catalog.screenplays[0].shots = [];
  if (kind === 'asset') catalog.assets[0].version++;
  if (kind === 'approval') catalog.assets[0].approved = false;
  if (kind === 'appearance') document.panels[0].appearance_references![0].expected_asset_version++;
  if (kind === 'character') catalog.characters = [];
  if (kind === 'font') document.panels[0].bubbles[0].font_size = 13;
  if (kind === 'surrogate') document.panels[0].bubbles[0].text = '\ud800';
  if (kind === 'crop') document.panels[0].cover_x_percent = 101;
  if (kind === 'pixel') { document.width = 1600; document.height = 12000; }
  if (kind === 'segment') document.segment_height = 319;
  const before = JSON.stringify(document);
  expect(previewComicDuplicate(document, catalog, target).error).toBeTruthy();
  expect(applyComicDuplicate(document, catalog, target, fixture.ids).document).toBeUndefined();
  expect(JSON.stringify(document)).toBe(before);
});
it.each([{ panel: 'authored', bubbles: ['fresh'] }, { panel: 'speech', bubbles: ['fresh'] }, { panel: 'new', bubbles: ['speech'] }, { panel: 'new', bubbles: ['new'] }, { panel: 'new', bubbles: [] }, { panel: 'invalid space', bubbles: ['fresh'] }])('rejects colliding or invalid generated IDs', ids => {
  const { document, catalog, target } = setup();
  expect(applyComicDuplicate(document, catalog, target, ids).error).toBeTruthy();
  expect(document.panels).toHaveLength(1);
});
it('accepts exact safe-area and same-row trailing placement', () => {
  const { document, catalog } = setup();
  expect(previewComicDuplicate(document, catalog, { sourceId: 'authored', x: 184, y: 16 }).panel).toBeTruthy();
});
it('enforces original 24 panels, 12 bubbles per panel, 80 total bubbles and 10000 code points', () => {
  const { document, catalog, target } = setup();
  const panel = document.panels[0], bubble = panel.bubbles[0];
  document.panels = Array.from({ length: 24 }, (_, i) => ({ ...panel, id: `p${i}`, order: i + 1, bubbles: [] }));
  expect(previewComicDuplicate(document, catalog, target).error).toMatch(/24/);
  document.panels = [{ ...panel, bubbles: Array.from({ length: 13 }, (_, i) => ({ ...bubble, id: `b${i}` })) }];
  expect(previewComicDuplicate(document, catalog, target).error).toMatch(/结构/);
  document.panels = Array.from({ length: 7 }, (_, i) => ({ ...panel, id: i ? `p${i}` : 'authored', order: i + 1, x: 16, y: i * 150 + 16, bubbles: Array.from({ length: i === 6 ? 8 : 12 }, (_, j) => ({ ...bubble, id: `b${i}-${j}` })) }));
  document.height = 1200;
  expect(previewComicDuplicate(document, catalog, target).error).toMatch(/80/);
  // Python len counts code points, not UTF-16 units: emoji must count once.
  document.panels = [{ ...panel, bubbles: Array.from({ length: 6 }, (_, i) => ({ ...bubble, id: `b${i}`, text: '😀'.repeat(1000) })) }];
  expect(previewComicDuplicate(document, catalog, target).error).toMatch(/10000/);
  document.panels[0].bubbles = [{ ...bubble, text: '😀'.repeat(1000) }];
  expect(previewComicDuplicate(document, catalog, target).panel).toBeTruthy();
});
it.each([null, {}, { panels: [null] }, { panels: [{ id: 'p', bubbles: null }] }])('fails closed on malformed draft structure', value => {
  const { catalog, target } = setup();
  expect(previewComicDuplicate(value as unknown as ComicDocument, catalog, target).error).toBeTruthy();
});
it.each([null, {}, 'bad', [null]])('rejects malformed appearance reference containers without throwing', value => {
  const { document, catalog, target } = setup();
  (document.panels[0] as unknown as { appearance_references: unknown }).appearance_references = value;
  expect(previewComicDuplicate(document, catalog, target).error).toMatch(/外观引用结构/);
  expect(applyComicDuplicate(document, catalog, target, fixture.ids).document).toBeUndefined();
});
it('copies independent blank panels without inventing screenplay, shot or image bindings', () => {
  const { document, catalog, target } = setup();
  document.source_mode = 'INDEPENDENT'; document.screenplay_id = null; document.expected_screenplay_version = null;
  document.panels.forEach(panel => { panel.shot_id = null; panel.artwork_mode = 'BLANK'; panel.asset_id = null; panel.expected_asset_version = null; });
  catalog.screenplays = [];
  const next = applyComicDuplicate(document, catalog, target, fixture.ids).document!;
  expect(next.panels[1]).toMatchObject({ shot_id: null, artwork_mode: 'BLANK', asset_id: null, expected_asset_version: null, bubbles: [{ text: document.panels[0].bubbles[0].text }] });
  document.panels[0].shot_id = 'invented';
  expect(previewComicDuplicate(document, catalog, target).error).toBeTruthy();
});
