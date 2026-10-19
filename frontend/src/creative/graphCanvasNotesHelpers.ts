import type { StudioGraphCanvasNote, StudioGraphDefinition } from './studioGraphTypes';
import { projectGraphDisplay, type GraphDisplayIndex } from './graphCanvasPresentation';

export const GRAPH_NOTE_WIDTH = 240, GRAPH_NOTE_HEIGHT = 160;
export const GRAPH_NOTE_LIMIT = 1024, GRAPH_NOTE_RENDER_LIMIT = 128;
/** The JSON wire loses negative zero. Safe integers within the coordinate bound
 * have identical decimal digits in JS/Python; float coercion adds only ".0".
 * Other numbers retain the previous conservative 32-byte reserve. This is an
 * admission estimate, never a replacement for original canonical/record quotas. */
export function graphNumberSpellingReserve(value: number): number {
  return Number.isSafeInteger(value) && Math.abs(value) <= 100000 ? 2 : 32;
}
export function graphNoteDefinitionBytes(definition: StudioGraphDefinition): number {
  let reserve = 0;
  const json = JSON.stringify(definition, (_key, value) => { if (typeof value === 'number') reserve += graphNumberSpellingReserve(value); return value; });
  return new TextEncoder().encode(json).length + reserve;
}
export function withGraphNotes(definition: StudioGraphDefinition, notes: StudioGraphCanvasNote[]): StudioGraphDefinition | null {
  if (notes.length > GRAPH_NOTE_LIMIT || new Set(notes.map(note => note.id)).size !== notes.length
    || notes.some(note => !/^[A-Za-z][A-Za-z0-9_-]{0,63}(?![\s\S])/.test(note.id) || Array.from(note.text).length > 256
      || !Object.values(note.position).every(value => Number.isFinite(value) && Math.abs(value) <= 100000))
    || notes.reduce((sum, note) => sum + Array.from(note.text).length, 0) > 12000) return null;
  const next = { ...definition, presentation: { ...definition.presentation } };
  if (notes.length) next.presentation.notes = notes;
  else delete next.presentation.notes;
  if (!Object.keys(next.presentation).length) delete (next as StudioGraphDefinition).presentation;
  return graphNoteDefinitionBytes(next) <= 96000 ? next : null;
}
export function graphNoteDisplayIndex(notes: readonly StudioGraphCanvasNote[]): GraphDisplayIndex {
  return { cards: notes.map(note => ({ id: note.id, bounds: { ...note.position, width: GRAPH_NOTE_WIDTH, height: GRAPH_NOTE_HEIGHT } })),
    connections: [], descriptors: new Map(), frames: [] };
}
export function graphNoteDisplayWindow(notes: readonly StudioGraphCanvasNote[], viewport: StudioGraphDefinition['viewport'],
  size: { width: number; height: number } | null, retained: string | null) {
  const display = projectGraphDisplay(graphNoteDisplayIndex(notes), viewport, size, retained ? [retained] : []);
  const candidates = notes.filter(note => display.nodeIds.has(note.id));
  const shown = candidates.slice(0, GRAPH_NOTE_RENDER_LIMIT);
  // Bound even overlapping/unknown-layout boards. Keep keyboard-selected or
  // dragged content reachable without ever dropping it from the saved graph.
  const selected = retained ? candidates.find(note => note.id === retained) : undefined;
  if (selected && !shown.includes(selected)) shown[shown.length - 1] = selected;
  return { shown, candidates: candidates.length, omitted: candidates.length - shown.length };
}
export function visibleGraphNotes(...args: Parameters<typeof graphNoteDisplayWindow>) { return graphNoteDisplayWindow(...args).shown; }
