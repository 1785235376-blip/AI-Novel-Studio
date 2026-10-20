import { expect, it } from 'vitest';
import { arrangeComicVertically } from './comicArrangement';
import { comicPreset, type ComicDocument } from './comicLayoutsClient';
const source = { id: 's', title: 'Test', edit_version: 1, shot_status: 'DRAFT', checks: [], shots: [{ id: 'shot', number: 1, scene_id: 'scene', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5 }] };
function draft(): ComicDocument {
  const doc = comicPreset(source, 'WEBTOON', { width: 800, height: 2400, safe_area: 24, segment_height: 1200 });
  const panel = { ...doc.panels[0], x: 60, y: 400, width: 500, height: 300, asset_id: 'asset', expected_asset_version: 7, image_brief: '保留简报', character_ids: ['person'], appearance_references: [{ character_id: 'person', asset_id: 'ref', expected_asset_version: 3, note: '原版本' }], bubbles: [{ id: 'b', x: 80, y: 420, width: 200, height: 80, font_size: 32, kind: 'DIALOGUE' as const, text: '你好 👩🏽‍🚀\né', character_id: 'person' }] };
  return { ...doc, panels: [{ ...panel, id: 'second', order: 2 }, { ...panel, id: 'first', order: 1, bubbles: [] }] };
}
it('preserves exact source/content/dimensions and array identities while translating bubbles in reading order', () => {
  const doc = draft(), before = JSON.stringify(doc), result = arrangeComicVertically(doc);
  expect(result.error).toBeUndefined(); expect(result.changed).toBe(true); expect(JSON.stringify(doc)).toBe(before);
  const next = result.document!; expect(next.panels.map(p => p.id)).toEqual(['second', 'first']);
  expect(next.panels[0]).toEqual({ ...doc.panels[0], x: 24, y: 340, bubbles: [{ ...doc.panels[0].bubbles[0], x: 44, y: 360 }] });
  expect(next.panels[1]).toEqual({ ...doc.panels[1], x: 24, y: 24 });
  expect(arrangeComicVertically(next).changed).toBe(false);
});
it.each(['page', 'order', 'id', 'bubble', 'overflow', 'width', 'fraction', 'nan'] as const)('rejects %s without partial edits', kind => {
  const doc = draft();
  if (kind === 'page') doc.height = 12001;
  if (kind === 'order') doc.panels[1].order = 2;
  if (kind === 'id') doc.panels[1].id = doc.panels[0].id;
  if (kind === 'bubble') doc.panels[0].bubbles[0].x = 61;
  if (kind === 'overflow') doc.height = 640;
  if (kind === 'width') doc.width = 320;
  if (kind === 'fraction') doc.panels[0].height = 300.5;
  if (kind === 'nan') doc.panels[0].x = NaN;
  const before = JSON.stringify(doc); expect(arrangeComicVertically(doc)).toMatchObject({ changed: false, error: expect.any(String) }); expect(arrangeComicVertically(doc).document).toBeUndefined(); expect(JSON.stringify(doc)).toBe(before);
});
it('accepts exact page safe boundary and preserves blank text and overflow for original raster preflight', () => {
  const doc = draft(); doc.height = 664; doc.panels[0].bubbles[0].text = '长'.repeat(1000);
  expect(arrangeComicVertically(doc).document?.panels[0].y).toBe(340);
});

it.each([null, {}, { panels: null }, { panels: [null] }, { panels: [{ id: 'p', bubbles: null }] }, { panels: [{ id: 'p', bubbles: [null] }] }, { panels: [{ id: 'p', bubbles: [{ id: '' }] }] }])('rejects malformed runtime structures without throwing', value => {
  expect(arrangeComicVertically(value as ComicDocument).error).toBeTruthy();
});
it('rejects duplicate bubble identity across panels', () => {
  const doc = draft(); doc.panels[1].bubbles = structuredClone(doc.panels[0].bubbles);
  expect(arrangeComicVertically(doc).document).toBeUndefined();
});
