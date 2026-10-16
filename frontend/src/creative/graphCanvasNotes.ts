import type { StudioGraphCanvasNote, StudioGraphDefinition } from './studioGraphTypes';
import { projectGraphDisplay, type GraphDisplayIndex } from './graphCanvasPresentation';

export const GRAPH_NOTE_WIDTH = 240, GRAPH_NOTE_HEIGHT = 160;
/** Conservative UTF-8 estimate: reserve 32 bytes per number for Python's float spelling.
 * Original owner still validates canonical bytes, record/history/scope capacities and CAS. */
export function graphNoteDefinitionBytes(definition: StudioGraphDefinition): number {
  let numbers = 0;
  const json = JSON.stringify(definition, (_key, value) => { if (typeof value === 'number') numbers++; return value; });
  return new TextEncoder().encode(json).length + numbers * 32;
}
export function withGraphNotes(definition: StudioGraphDefinition, notes: StudioGraphCanvasNote[]): StudioGraphDefinition | null {
  if (notes.length > 128 || new Set(notes.map(note => note.id)).size !== notes.length
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
export function visibleGraphNotes(notes: readonly StudioGraphCanvasNote[], viewport: StudioGraphDefinition['viewport'],
  size: { width: number; height: number } | null, retained: string | null) {
  const display = projectGraphDisplay(graphNoteDisplayIndex(notes), viewport, size, retained ? [retained] : []);
  return notes.filter(note => display.nodeIds.has(note.id));
}
