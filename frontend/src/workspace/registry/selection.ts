/**
 * [HERMIA-FE-20261025 U2-M6] Canvas selection model (pure). Direct select, Ctrl/⌘ toggle multi-select and box select.
 * One canvas at a time: selecting on the other canvas replaces the selection (creative relations are never forced into
 * execution nodes). Multi-select exposes only parameters that are truly shared AND editable as a group — for the
 * current local canvas nodes that set is empty (title is per-node), and batch generation is never offered.
 */
import type {CanvasKind, CvNode} from '../../rebuild/canvas/RebuildCanvas';
import {NODE_TYPES} from '../../rebuild/canvas/RebuildCanvas';
import type {ParamField} from '../contracts';

export interface CanvasSelection { canvas: CanvasKind | null; ids: readonly string[]; }
export const EMPTY_SELECTION: CanvasSelection = {canvas: null, ids: []};
export interface Rect { x: number; y: number; w: number; h: number; }

export function selectDirect(_s: CanvasSelection, canvas: CanvasKind, id: string | null): CanvasSelection {
  return id ? {canvas, ids: [id]} : {canvas, ids: []};
}
export function selectToggle(s: CanvasSelection, canvas: CanvasKind, id: string): CanvasSelection {
  if (s.canvas !== canvas) return {canvas, ids: [id]};
  return s.ids.includes(id) ? {canvas, ids: s.ids.filter(x => x !== id)} : {canvas, ids: [...s.ids, id]};
}
export function normRect(a: {x: number; y: number}, b: {x: number; y: number}): Rect {
  return {x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(a.x - b.x), h: Math.abs(a.y - b.y)};
}
const hits = (r: Rect, n: Rect) => n.x < r.x + r.w && n.x + n.w > r.x && n.y < r.y + r.h && n.y + n.h > r.y;
/** Box select over node rects (screen space). additive=true keeps the existing same-canvas selection. */
export function selectBox(s: CanvasSelection, canvas: CanvasKind, box: Rect, nodes: readonly {id: string; rect: Rect}[], additive = false): CanvasSelection {
  const inBox = nodes.filter(n => hits(box, n.rect)).map(n => n.id);
  const base = additive && s.canvas === canvas ? s.ids : [];
  return {canvas, ids: [...base, ...inBox.filter(id => !base.includes(id))]};
}
/** Drop ids that no longer exist; reports which vanished so the UI can say so instead of showing a phantom node. */
export function pruneSelection(s: CanvasSelection, exists: (id: string) => boolean): {sel: CanvasSelection; missing: string[]} {
  const missing = s.ids.filter(id => !exists(id));
  return missing.length ? {sel: {canvas: s.canvas, ids: s.ids.filter(id => exists(id))}, missing} : {sel: s, missing};
}

/** Group-editable fields per node type. The local canvas only supports a per-node title (not group-editable). */
const GROUP_EDITABLE: Readonly<Record<string, readonly string[]>> = {};
export interface MultiEditSurface { count: number; fields: ParamField[]; typesLabel: string; note: string; actions: readonly string[]; }
export function multiEditSurface(canvas: CanvasKind, nodes: readonly CvNode[]): MultiEditSurface {
  const types = [...new Set(nodes.map(n => n.t))];
  const label = (t: string) => NODE_TYPES[canvas].find(x => x.id === t)?.label ?? '未知类型';
  const shared = types.reduce<string[] | null>((acc, t) => { const f = [...(GROUP_EDITABLE[t] ?? [])]; return acc === null ? f : acc.filter(x => f.includes(x)); }, null) ?? [];
  const fields: ParamField[] = [
    ...shared.map(k => ({key: k, label: k, mode: 'editable' as const})),
    {key: 'title', label: '节点标题', mode: 'unsupported', reason: '标题是每个节点各自的，不能批量改。请逐个选中修改。'},
    {key: 'generate', label: '批量生成', mode: 'unsupported', reason: '多选不提供批量生成；生成只能从单个任务的原入口明确确认后执行。'},
  ];
  return {count: nodes.length, fields, typesLabel: types.map(label).join('、'),
    note: shared.length ? '' : '这些节点没有可以一起修改的参数。', actions: ['locate', 'clear-selection']};
}
