import { expect, it } from 'vitest';
import { checkedStudioGraphDraft } from './studioGraphClient';
import { graphNoteDefinitionBytes, graphNumberSpellingReserve, graphNoteDisplayWindow, withGraphNotes } from './graphCanvasNotes';
import type { StudioGraphDefinition } from './studioGraphTypes';
const graph = (): StudioGraphDefinition => ({ schema_version: 1, title: '大空间便笺', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } });
const notes = (count = 1024) => Array.from({ length: count }, (_, i) => ({ id: `note_${i + 1}`, text: `雨夜·镜头${String(i + 1).padStart(4, '0')}`, position: { x: (i % 40) * 320, y: Math.floor(i / 40) * 220 } }));
it('admits 1024 meaningful display items within the unchanged text/byte budgets and rejects 1025', () => {
  const source = graph(), result = withGraphNotes(source, notes())!;
  expect(result.presentation!.notes).toHaveLength(1024); expect(result.nodes).toEqual([]);
  expect(graphNoteDefinitionBytes(result)).toBeLessThan(96000);
  expect(checkedStudioGraphDraft(result)).toEqual(result); expect(source.presentation).toBeUndefined();
  expect(withGraphNotes(source, notes(1025))).toBeNull();
  expect(() => checkedStudioGraphDraft({ ...source, presentation: { notes: notes(1025) } })).toThrow();
});
it.each([0, -0, 1, -1, 100000, -100000, 99999])('reserves Python float .0 for bounded exact integer %s', value => {
  expect(graphNumberSpellingReserve(value)).toBe(2);
  const source = graph(); source.viewport.x = value;
  // JSON.stringify normalizes -0 before it reaches Python/Pydantic.
  if (Object.is(value, -0)) expect(JSON.parse(JSON.stringify(source)).viewport.x).toBe(0);
});
it.each([0.1, -0.1, 1e-6, 1e-7, -1e-7, Number.MIN_VALUE, -Number.MIN_VALUE, 99999.99999999999, 100001, Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER + 1])('retains the full spelling reserve for %s', value => {
  expect(graphNumberSpellingReserve(value)).toBe(32);
});
it('retains UTF-8, emoji, escape and near-byte-boundary rejection without trimming author text', () => {
  const source = graph(); source.nodes = Array.from({ length: 8 }, (_, i) => ({ id: `text${i}`, definition_id: 'text_input', definition_version: 1, enabled: true, parameters: { text: '中文🎬"\\\n'.repeat(500) }, position: { x: 0, y: 0 } }));
  const large = notes(1000), copy = structuredClone(large);
  expect(graphNoteDefinitionBytes({ ...source, presentation: { notes: large } })).toBeGreaterThan(96000);
  expect(withGraphNotes(source, large)).toBeNull(); expect(large).toEqual(copy);
  const valid = withGraphNotes(graph(), notes(1000))!;
  expect(graphNoteDefinitionBytes(valid)).toBeGreaterThan(new TextEncoder().encode(JSON.stringify(valid)).length);
});
it('bounds measured overlap and unknown layout, retaining a requested last item with no data loss', () => {
  const all = notes(), overlapping = all.map(note => ({ ...note, position: { x: 0, y: 0 } }));
  for (const size of [null, { width: 800, height: 600 }]) {
    const shown = graphNoteDisplayWindow(overlapping, graph().viewport, size, 'note_1024');
    expect(shown.shown).toHaveLength(128); expect(shown.omitted).toBe(896);
    expect(shown.shown.at(-1)!.id).toBe('note_1024');
  }
  const culled = graphNoteDisplayWindow(all, graph().viewport, { width: 800, height: 600 }, 'note_1024');
  expect(culled.shown.length).toBeLessThan(128); expect(culled.shown.some(n => n.id === 'note_1024')).toBe(true);
  expect(all).toHaveLength(1024);
});

it('matches original Python canonical boundary fixtures including signed zero, exponents and UTF-8 escapes', async () => {
  const { readFileSync } = await import('node:fs');
  const fixtures = JSON.parse(readFileSync(new URL('../../../tests/fixtures/v2_graph_note_numbers.json', import.meta.url), 'utf8')) as { input_json: string; canonical_json: string; canonical_bytes: number }[];
  for (const row of fixtures) {
    const definition = JSON.parse(row.input_json) as StudioGraphDefinition;
    expect(JSON.stringify(definition)).toBe(row.input_json);
    expect(new TextEncoder().encode(row.canonical_json).length).toBe(row.canonical_bytes);
    expect(graphNoteDefinitionBytes(definition)).toBeGreaterThanOrEqual(row.canonical_bytes);
    expect(checkedStudioGraphDraft(definition)).toEqual(definition);
  }
});

it('rejects the first byte beyond the conservative 96000-byte admission boundary with mixed Unicode content', () => {
  const source = graph(), all = notes(1000);
  source.nodes = ['first', 'second'].map(id => ({ id, definition_id: 'text_input', definition_version: 1, enabled: true,
    parameters: { text: '' }, position: { x: 0, y: 0 } }));
  source.nodes[0].parameters.text = '中文🎬"\\\n';
  const remaining = 96000 - graphNoteDefinitionBytes({ ...source, presentation: { notes: all } });
  const first = Math.min(7000, remaining);
  source.nodes[0].parameters.text += 'a'.repeat(first);
  source.nodes[1].parameters.text = 'a'.repeat(remaining - first);
  const exact = withGraphNotes(source, all)!;
  expect(exact).not.toBeNull(); expect(graphNoteDefinitionBytes(exact)).toBe(96000);
  expect(checkedStudioGraphDraft(exact)).toEqual(exact);
  source.nodes[1].parameters.text += 'a'; expect(withGraphNotes(source, all)).toBeNull();
});
