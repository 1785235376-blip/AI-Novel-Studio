import { expect, it } from 'vitest';
import { checkedCanvasDefinition, type CanvasDefinition } from './studioCanvasViewClient';
import { dragCanvasCards } from './mediaCanvasSelection';
const definition = (): CanvasDefinition => ({ schema_version: 1, title: 'Grid', cards: [{ id: 'A', position: { x: 10, y: 20 } }, { id: 'B', position: { x: 35, y: 45 } }], viewport: { x: 0, y: 0, zoom: 2 }, view_options: { grid: true, snap_step: 16 } });
it('snaps the grabbed world anchor and keeps relative offsets', () => {
 const d = definition(), next = dragCanvasCards(d, ['A', 'B'], 'A', 12, 12);
 expect(next.cards.map(c => c.position)).toEqual([{ x: 16, y: 32 }, { x: 41, y: 57 }]);
 expect(d.cards[0].position).toEqual({ x: 10, y: 20 }); expect(next.viewport).toBe(d.viewport);
});
it('keeps original clamping for the whole cohort and preserves unsnapped behavior', () => {
 const d = definition(); d.cards[1].position.x = 99999;
 const next = dragCanvasCards(d, ['A', 'B'], 'A', 100, 0); expect(next.cards[1].position.x).toBe(100000); expect(next.cards[0].position.x).toBe(11);
 delete d.view_options; expect(dragCanvasCards(d, ['A'], 'A', 3, 7).cards[0].position).toEqual({ x: 13, y: 27 });
});
it.each([NaN, Infinity, -Infinity])('refuses invalid movement %s', x => { const d = definition(); expect(dragCanvasCards(d, ['A'], 'A', x, 0)).toBe(d); });
it('roundtrips presentation options without adding defaults to old definitions', () => { const d = definition(); expect(checkedCanvasDefinition(d)).toEqual(d); delete d.view_options; expect(checkedCanvasDefinition(d)).not.toHaveProperty('view_options'); });
it.each([null, {}, { grid: 1, snap_step: 16 }, { grid: true, snap_step: '16' }, { grid: true, snap_step: 17 }, { grid: true, snap_step: null, execute: true }])('rejects invalid options %j', view_options => { expect(() => checkedCanvasDefinition({ ...definition(), view_options })).toThrow(); });
