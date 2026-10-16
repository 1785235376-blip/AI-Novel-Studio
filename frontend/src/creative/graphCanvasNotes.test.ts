import { describe, expect, it } from 'vitest';
import { graphNoteDefinitionBytes, graphNoteDisplayIndex, visibleGraphNotes, withGraphNotes } from './graphCanvasNotes';
import type { StudioGraphDefinition } from './studioGraphTypes';
const graph = (): StudioGraphDefinition => ({ schema_version: 1, title: 'Notes', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } });
const notes = (count: number, text = 'Scene 🎬') => Array.from({ length: count }, (_, i) => ({ id: `n${i}`, text, position: { x: i * 500, y: i * 100 } }));
describe('bounded independent display notes', () => {
  it('keeps old omission and other metadata, never populates execution nodes', () => {
    const old = { ...graph(), presentation: { comment: 'Keep' } }, copy = structuredClone(old);
    const next = withGraphNotes(old, notes(128))!;
    expect(next.nodes).toEqual([]); expect(next.presentation!.notes).toHaveLength(128);
    expect(withGraphNotes(next, [])).toEqual(old); expect(old).toEqual(copy);
    expect(withGraphNotes(graph(), [])).not.toHaveProperty('presentation');
  });
  it('enforces count, aggregate codepoints, coordinates, IDs and conservative UTF-8 owner budget', () => {
    expect(withGraphNotes(graph(), notes(1025))).toBeNull();
    expect(withGraphNotes(graph(), notes(47, '🎬'.repeat(256)))).toBeNull();
    expect(withGraphNotes(graph(), notes(46, '🎬'.repeat(256)))).not.toBeNull();
    const exact = notes(46, '🎬'.repeat(256)); exact.push({ id: 'last', text: '🎬'.repeat(224), position: { x: 0, y: 0 } });
    expect(withGraphNotes(graph(), exact)).not.toBeNull();
    exact[46].text += 'a'; expect(withGraphNotes(graph(), exact)).toBeNull();
    expect(withGraphNotes(graph(), notes(1, '🎬'.repeat(257)))).toBeNull();
    for (const id of ['n\n', 'n\r']) expect(withGraphNotes(graph(), [{ id, text: '', position: { x: 0, y: 0 } }])).toBeNull();
    const bad = notes(2); bad[1].id = bad[0].id; expect(withGraphNotes(graph(), bad)).toBeNull();
    bad[1].id = 'n1'; bad[0].position.x = NaN; expect(withGraphNotes(graph(), bad)).toBeNull();
    const definition = graph(); definition.title = 'x'.repeat(96000); expect(withGraphNotes(definition, notes(1))).toBeNull();
    expect(graphNoteDefinitionBytes(graph())).toBeGreaterThan(new TextEncoder().encode(JSON.stringify(graph())).length);
  });
  it('uses fixed geometric bounds, zoomed viewport clipping, retention and hidden-layout fallback', () => {
    const all = notes(128), index = graphNoteDisplayIndex(all);
    expect(index.cards[0].bounds).toEqual({ x: 0, y: 0, width: 240, height: 160 });
    expect(index.connections).toEqual([]);
    const size = { width: 800, height: 600 };
    expect(visibleGraphNotes(all, graph().viewport, size, null).map(n => n.id)).toEqual(['n0', 'n1']);
    expect(visibleGraphNotes(all, { x: -50000, y: -10000, zoom: 1 }, size, 'n0').some(n => n.id === 'n100')).toBe(true);
    expect(visibleGraphNotes(all, graph().viewport, null, null)).toHaveLength(128);
    expect(visibleGraphNotes(all, { x: 0, y: 0, zoom: 2.5 }, size, null)).toHaveLength(1);
  });
});
