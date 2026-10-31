import { expect, it } from 'vitest';
import { transformComicGeometry, translateComicPanels } from './comicGeometry';
import type { ComicDocument } from './comicLayoutsClient';
import fixture from '../../../tests/fixtures/comic_panel_duplicate.json';
const doc = () => structuredClone(fixture.document) as ComicDocument;
it('moves panels and their bubbles together while preserving all other fields and references', () => {
  const d = doc(), p = d.panels[0];
  const next = transformComicGeometry(d, { panelId: p.id }, 'move', 1, 2);
  expect(next.panels[0]).toEqual({ ...p, x: p.x + 1, y: p.y + 2, bubbles: p.bubbles.map(b => ({ ...b, x: b.x + 1, y: b.y + 2 })) });
  expect(d).toEqual(fixture.document);
});
it('clamps move and resize to safe bounds and retains child containment', () => {
  const d = doc(), p = d.panels[0];
  const moved = transformComicGeometry(d, { panelId: p.id }, 'move', -99999, -99999).panels[0];
  expect(moved.x).toBe(d.safe_area); expect(moved.y).toBe(d.safe_area);
  const resized = transformComicGeometry(d, { panelId: p.id }, 'resize', -9999, -9999).panels[0];
  expect(resized.width).toBe(Math.max(16, ...p.bubbles.map(b => b.x + b.width + 8 - p.x)));
  expect(resized.bubbles).toEqual(p.bubbles);
  const max = transformComicGeometry(d, { panelId: p.id }, 'resize', 9999, 9999).panels[0];
  expect(max.x + max.width).toBe(d.width - d.safe_area); expect(max.y + max.height).toBe(d.height - d.safe_area);
});
it('bubble edits are bounded by panel and never scale text or font', () => {
  const d = doc(), p = d.panels[0], b = p.bubbles[0], target = { panelId: p.id, bubbleId: b.id };
  const next = transformComicGeometry(d, target, 'move', 9999, 9999).panels[0].bubbles[0];
  expect(next.x + next.width).toBe(p.x + p.width - 8); expect(next.y + next.height).toBe(p.y + p.height - 8);
  const min = transformComicGeometry(d, target, 'move', -9999, -9999).panels[0].bubbles[0];
  expect(min.x).toBe(p.x + 8); expect(min.y).toBe(p.y + 8);
  const max = transformComicGeometry(d, target, 'resize', 9999, 9999).panels[0].bubbles[0];
  expect(max.x + max.width).toBe(p.x + p.width - 8); expect(max.y + max.height).toBe(p.y + p.height - 8);
  const resized = transformComicGeometry(d, target, 'resize', -9999, -9999).panels[0].bubbles[0];
  expect(resized).toEqual({ ...b, width: 16, height: 16 });
});
it('invalid drafts, unknown targets, nonfinite deltas and unchanged moves are identity no-ops', () => {
  const d = doc(), target = { panelId: d.panels[0].id };
  expect(transformComicGeometry(d, target, 'move', 0, 0)).toBe(d);
  expect(transformComicGeometry(d, target, 'move', NaN, 0)).toBe(d);
  expect(transformComicGeometry(d, { panelId: 'missing' }, 'move', 1, 1)).toBe(d);
  d.panels[0].x = -1;
  expect(transformComicGeometry(d, target, 'move', 10, 10)).toBe(d);
});

it.each([{ safe_area: -1 }, { safe_area: 129 }, { width: 800.5 }, { width: 1601 }, { height: 12001 }, { height: 319 }])('invalid page dimensions fail closed: %j', patch => {
  const d = { ...doc(), ...patch };
  expect(transformComicGeometry(d, { panelId: d.panels[0].id }, 'move', -9999, -9999)).toBe(d);
});

const groupDoc = () => ({ ...doc(), panels: [doc().panels[0], structuredClone(fixture.expectedPanel)] }) as ComicDocument;
it('translates selected panels and bubbles in one immutable change, preserving all pins and other panels', () => {
  const d = groupDoc(), untouched = { ...doc().panels[0], id: 'untouched' }; d.panels.push(untouched);
  const before = structuredClone(d), ids = d.panels.slice(0, 2).map(panel => panel.id);
  const next = translateComicPanels(d, ids, 10, 20);
  expect(d).toEqual(before); expect(next.panels[2]).toBe(untouched);
  for (let i = 0; i < 2; i++) expect(next.panels[i]).toEqual({ ...d.panels[i], x: d.panels[i].x + 10, y: d.panels[i].y + 20,
    bubbles: d.panels[i].bubbles.map(bubble => ({ ...bubble, x: bubble.x + 10, y: bubble.y + 20 })) });
});
it('clamps the whole group at the first safe boundary without compressing spacing', () => {
  const d = groupDoc(), next = translateComicPanels(d, d.panels.map(panel => panel.id), 99999, -99999);
  expect(next.panels.map(panel => [panel.x, panel.y])).toEqual([[40, 8], [184, 328]]);
  expect(next.panels[1].x - next.panels[0].x).toBe(d.panels[1].x - d.panels[0].x);
  expect(next.panels[1].y - next.panels[0].y).toBe(d.panels[1].y - d.panels[0].y);
});
it('rejects missing/duplicate targets, invalid selected geometry and nonfinite or no-op group movements', () => {
  const d = groupDoc(), ids = d.panels.map(panel => panel.id);
  for (const selection of [[], ['missing'], [ids[0], ids[0]]]) expect(translateComicPanels(d, selection, 10, 10)).toBe(d);
  expect(translateComicPanels(d, ids, NaN, 10)).toBe(d); expect(translateComicPanels(d, ids, 0, 0)).toBe(d);
  const bad = groupDoc(); bad.panels[1].bubbles[0].x = -1;
  expect(translateComicPanels(bad, ids, 10, 10)).toBe(bad);
  const page = { ...d, safe_area: 129 }; expect(translateComicPanels(page, ids, 10, 10)).toBe(page);
});
