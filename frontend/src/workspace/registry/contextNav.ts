/**
 * [HERMIA-FE-20261025 U2-M6] Dual-canvas context navigation (pure reducer). Creative canvas is the default main entry.
 * A single task opens the execution canvas alone; split view only on explicit compare. Return-to-origin restores the
 * panel, canvas, selection, focus target and viewport captured BEFORE the first task jump (switching task keeps the
 * same origin). Missing links/nodes are reported, never fabricated. Read-only: produces navigation intents only.
 */
import type {NavReturnPoint, TaskRef} from '../contracts';
import type {LayoutPresetId} from './workspaceRegistry';

export interface NavState { preset: LayoutPresetId; origin: NavReturnPoint | null; task: {source: TaskRef['source']; id: string; title: string} | null; notice: NavNotice | null; }
export interface NavNotice { tone: 'info' | 'warn'; text: string; next?: string; }
export const INITIAL_NAV: NavState = {preset: 'creative', origin: null, task: null, notice: null};

export interface NavEnv { nodeExists(canvas: 'creative' | 'execution', nodeId: string): boolean; capture(): NavReturnPoint; }
export type NavIntent =
  | {kind: 'none'}
  | {kind: 'show'; preset: LayoutPresetId; select: {canvas: 'creative' | 'execution'; nodeIds: string[]} | null; focusPanel: string}
  | {kind: 'restore'; point: NavReturnPoint; preset: LayoutPresetId; missingNodes: string[]};

export function openTask(s: NavState, task: TaskRef, env: NavEnv): {state: NavState; intent: NavIntent} {
  const origin = s.origin ?? env.capture();
  const t = {source: task.source, id: task.id, title: task.title};
  if (task.stale) return {state: {...s, origin, task: t, notice: {tone: 'warn', text: `任务「${task.title}」已失效，不能定位。`, next: '刷新任务列表后重新选择。'}}, intent: {kind: 'none'}};
  const link = task.link;
  if (!link || !link.nodeId) {
    return {state: {...s, origin, task: t, preset: 'execution-single', notice: {tone: 'info', text: `任务「${task.title}」没有关联到具体画布节点。`, next: '可以在执行画布里手动查看，或回到原位置继续创作。'}},
      intent: {kind: 'show', preset: 'execution-single', select: null, focusPanel: 'execution'}};
  }
  const preset: LayoutPresetId = link.canvas === 'execution' ? 'execution-single' : 'creative';
  if (!env.nodeExists(link.canvas, link.nodeId)) {
    return {state: {...s, origin, task: t, preset, notice: {tone: 'warn', text: `任务「${task.title}」关联的节点在${link.canvas === 'execution' ? '执行' : '创作'}画布里找不到了（可能已删除）。`, next: '画布没有被修改；可以回到原位置，或在任务详情里查看来源。'}},
      intent: {kind: 'show', preset, select: null, focusPanel: link.canvas}};
  }
  return {state: {...s, origin, task: t, preset, notice: null}, intent: {kind: 'show', preset, select: {canvas: link.canvas, nodeIds: [link.nodeId]}, focusPanel: link.canvas}};
}

/** Explicit compare only (creative + execution side by side). */
export function toggleCompare(s: NavState): {state: NavState; intent: NavIntent} {
  const preset: LayoutPresetId = s.preset === 'compare' ? (s.task ? 'execution-single' : 'creative') : 'compare';
  return {state: {...s, preset, notice: null}, intent: {kind: 'show', preset, select: null, focusPanel: preset === 'creative' ? 'creative' : 'execution'}};
}

export function returnToOrigin(s: NavState, env: Pick<NavEnv, 'nodeExists'>): {state: NavState; intent: NavIntent} {
  if (!s.origin) return {state: {...s, notice: {tone: 'info', text: '没有可以返回的位置。', next: '从任务列表选择任务后才会记录原位置。'}}, intent: {kind: 'none'}};
  const p = s.origin; const missing = p.nodeIds.filter(id => !env.nodeExists(p.canvas, id));
  const point = missing.length ? {...p, nodeIds: p.nodeIds.filter(id => !missing.includes(id))} : p;
  const preset: LayoutPresetId = p.canvas === 'execution' ? 'execution-single' : 'creative';
  return {state: {...INITIAL_NAV, preset, notice: missing.length ? {tone: 'warn', text: `已回到原位置，但原来选中的 ${missing.length} 个节点已不存在。`, next: '视角已恢复，可以重新选择节点。'} : null},
    intent: {kind: 'restore', point, preset, missingNodes: missing}};
}

/** A panel was closed by the user: never reopen it on our own; fall back to the creative entry and keep the origin. */
export function panelClosed(s: NavState, panelId: string): NavState {
  if (panelId === 'execution' && s.preset !== 'creative') return {...s, preset: 'creative', notice: {tone: 'info', text: '执行画布已关闭。', next: '按 Ctrl／⌘+Alt+E 可以重新打开；原位置仍可返回。'}};
  if (panelId === 'tasks' && s.task) return {...s, notice: {tone: 'info', text: '任务面板已关闭，当前定位保留。', next: '按 Ctrl／⌘+Alt+T 重新打开任务。'}};
  return s;
}
/** Project/identity switch: navigation state never crosses scopes. */
export const resetNav = (): NavState => INITIAL_NAV;
