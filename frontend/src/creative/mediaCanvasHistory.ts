import { checkedCanvasDefinition, type CanvasDefinition } from './studioCanvasViewClient';
type Entry = { value: CanvasDefinition; bytes: number };
export type CanvasDraftHistory = { past: Entry[]; future: Entry[] };
export const CANVAS_HISTORY_STEPS = 20, CANVAS_HISTORY_BYTES = 2_000_000;
export const emptyCanvasHistory = (): CanvasDraftHistory => ({ past: [], future: [] });
function entry(value: CanvasDefinition): Entry { const copy = checkedCanvasDefinition(value); return { value: copy, bytes: new TextEncoder().encode(JSON.stringify(copy)).length }; }
export function canvasHistoryBytes(history: CanvasDraftHistory) { return [...history.past, ...history.future].reduce((total, item) => total + item.bytes, 0); }
function bound(history: CanvasDraftHistory) { const next = { past: [...history.past], future: [...history.future] };
  while (next.past.length + next.future.length > CANVAS_HISTORY_STEPS || canvasHistoryBytes(next) > CANVAS_HISTORY_BYTES) {
    if (next.past.length) next.past.shift(); else next.future.pop();
  }
  return next;
}
export function recordCanvasEdit(history: CanvasDraftHistory, current: CanvasDefinition): CanvasDraftHistory { return bound({ past: [...history.past, entry(current)], future: [] }); }
export function travelCanvasEdit(history: CanvasDraftHistory, current: CanvasDefinition, redo: boolean) {
  const target = redo ? history.future[0] : history.past.at(-1); if (!target) return undefined;
  const next = redo ? { past: [...history.past, entry(current)], future: history.future.slice(1) } : { past: history.past.slice(0, -1), future: [entry(current), ...history.future] };
  return { definition: checkedCanvasDefinition(target.value), history: bound(next) };
}
