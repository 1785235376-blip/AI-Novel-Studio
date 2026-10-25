/**
 * [HERMIA-FE-20261025 U2-M10] Unified workspace registry: ONE declarative table for panels, layout geometry, actions'
 * shortcuts, capability states, layout presets and media slices. Existing hardcoded tables (PREVIEW_SPECS,
 * STUDIO_PREVIEW_PANELS, DEFAULT_LAYOUT_SHORTCUTS, STUDIO_SHORTCUTS, VIEW_SHORTCUTS) are reproduced exactly by the
 * derivations below (parity is asserted in u2.registry.test.ts) so the host can switch to them with a minimal patch
 * (patches/u2-registry-wiring.patch) and a new window is added by adding ONE entry here.
 * Pure data + pure functions. No network, no model calls.
 */
import type {LayoutPanelSpec, DockZone} from '../layout/model';
import type {CapabilityStatus, PanelDefinition, DockZone as WbDock} from '../../workbench/panels';
import type {CapabilityState} from '../contracts';
import {normalizeShortcut, RESERVED_SHORTCUTS} from '../actions/layoutActions';

export type MediaSlice = 'image' | 'audio';
export interface UnifiedPanelEntry {
  id: string; title: string; kind: PanelDefinition['kind'];
  capability: CapabilityStatus;
  /** Plain-language capability note shown on demand (progressive detail), never a raw code. */
  capabilityNote: string;
  docks: readonly DockZone[]; defaultDock: DockZone; defaultSize: number; minSize: number; maxSize?: number;
  requiresContext?: readonly ('project' | 'document' | 'node')[];
  /** Action that shows this panel (if any); its shortcut lives in UNIFIED_SHORTCUTS. */
  showActionId?: string;
  /** Media slice this panel belongs to; 'shared' panels serve every slice. */
  media: MediaSlice | 'shared';
  /** First-time hint: what to do here, one sentence. */
  firstStep: string;
}

export const UNIFIED_PANELS: readonly UnifiedPanelEntry[] = [
  {id: 'outline', title: '作品结构', kind: 'editor', capability: 'connected', capabilityNote: '读取服务端作品与章节。', docks: ['left', 'right', 'main', 'float'], defaultDock: 'left', defaultSize: 248, minSize: 180, media: 'shared', firstStep: '先在这里选一部作品。'},
  {id: 'creative', title: '创作画布', kind: 'canvas', capability: 'local-only', capabilityNote: '画布只存在这台浏览器的草稿里，还没有接服务端画布图。', docks: ['main', 'float'], defaultDock: 'main', defaultSize: 800, minSize: 320, requiresContext: ['project'], showActionId: 'canvas.openCreative', media: 'image', firstStep: '点选节点查看属性；Shift 拖动框选，Ctrl／⌘ 点击多选。'},
  {id: 'execution', title: '执行画布', kind: 'canvas', capability: 'local-only', capabilityNote: '执行画布同样只是本机草稿；打开它不会开始执行。', docks: ['main', 'float', 'right'], defaultDock: 'main', defaultSize: 800, minSize: 320, requiresContext: ['project'], showActionId: 'canvas.openExecution', media: 'image', firstStep: '从任务或创作节点进入这里查看执行结构。'},
  {id: 'inspector', title: '章节属性', kind: 'inspector', capability: 'connected', capabilityNote: '章节属性读写服务端；画布节点属性只写本机草稿。', docks: ['left', 'right', 'bottom', 'float'], defaultDock: 'right', defaultSize: 340, minSize: 240, maxSize: 560, media: 'shared', firstStep: '选中章节或节点后在这里查看和修改。'},
  {id: 'tasks', title: '任务', kind: 'feature', capability: 'partial', capabilityNote: '任务列表来自现有任务中心接口，没有分页；成本始终显示未知。', docks: ['bottom', 'right', 'left'], defaultDock: 'bottom', defaultSize: 200, minSize: 120, requiresContext: ['project'], showActionId: 'tasks.open', media: 'shared', firstStep: '选一个任务，可以定位到它对应的作品位置。'},
];

/** Every shortcut in the unified workspace, by action id. Mirrors the previously scattered tables exactly. */
export const UNIFIED_SHORTCUTS: Readonly<Record<string, string>> = {
  'layout.reset': 'Mod+Alt+0', 'layout.reopenPanel': 'Mod+Alt+O', 'layout.toggleCollapse': 'Mod+Alt+C',
  'layout.switchSplit': 'Mod+Alt+S', 'layout.showPanel': 'Mod+Alt+P',
  'canvas.openExecution': 'Mod+Alt+E', 'canvas.openCreative': 'Mod+Alt+I', 'tasks.open': 'Mod+Alt+T',
  'view.worksets.open': 'Mod+Alt+V', 'view.panel.next': 'Mod+Alt+N', 'view.panel.prev': 'Mod+Alt+B', 'view.panel.last': 'Mod+Alt+L',
  // [HERMIA-FE-20261025 U2-M6] context navigation (new, free keys)
  'nav.returnToOrigin': 'Mod+Alt+R', 'nav.compare': 'Mod+Alt+D',
};
export const shortcutsFor = (...prefixes: string[]): Record<string, string> =>
  Object.fromEntries(Object.entries(UNIFIED_SHORTCUTS).filter(([id]) => prefixes.some(p => id.startsWith(p))));

/** Layout presets. 'creative' is the default main entry; split only for explicit comparison. */
export type LayoutPresetId = 'creative' | 'execution-single' | 'compare';
export interface LayoutPreset { id: LayoutPresetId; title: string; split: 'single' | 'split-h'; mainFront: string; mainSecond?: string; }
export const LAYOUT_PRESETS: Readonly<Record<LayoutPresetId, LayoutPreset>> = {
  creative: {id: 'creative', title: '创作（默认）', split: 'single', mainFront: 'creative'},
  'execution-single': {id: 'execution-single', title: '查看执行画布', split: 'single', mainFront: 'execution'},
  compare: {id: 'compare', title: '对照（左右分屏）', split: 'split-h', mainFront: 'creative', mainSecond: 'execution'},
};
export const DEFAULT_PRESET: LayoutPresetId = 'creative';

/** Media slices: image is the active vertical slice; audio is a reserved seam (U3/U4 must stabilise first). */
export const MEDIA_SLICES: Readonly<Record<MediaSlice, {title: string; state: 'active' | 'reserved'; owner: string; note: string}>> = {
  image: {title: '图片', state: 'active', owner: 'creative/studioGraphClient (image graph)', note: '当前垂直切片。'},
  audio: {title: '音频', state: 'reserved', owner: 'creative/studioProductionClient m8.audio.*', note: '接口已在任务书清单中，等任务和结果单元稳定后再接；现在不显示任何音频入口。'},
};

// ── derivations (parity with the previous hardcoded tables) ───────────────────────────────────────────────────
export function layoutSpecs(entries: readonly UnifiedPanelEntry[] = UNIFIED_PANELS): LayoutPanelSpec[] {
  return entries.filter(e => mediaVisible(e.media)).map(e => ({id: e.id, title: e.title, defaultDock: e.defaultDock, docks: e.docks, defaultSize: e.defaultSize, minSize: e.minSize, ...(e.maxSize ? {maxSize: e.maxSize} : {})}));
}
/** workbench PanelDefinition for registry-registered panels (canvas + tasks; outline/inspector come from novelPreviewPanels). */
export function panelDefinitions(ids: readonly string[] = ['creative', 'execution', 'tasks'], entries = UNIFIED_PANELS): PanelDefinition[] {
  return ids.map(id => {
    const e = entries.find(x => x.id === id); if (!e) throw new Error(`unknown panel ${id}`);
    const docks = e.docks.filter((d): d is WbDock => d !== 'float');
    return {id: e.id, kind: e.kind, title: e.title, capability: e.capability, instancing: 'singleton', docks, defaultDock: e.defaultDock as WbDock, minWidth: e.minSize, ...(e.requiresContext ? {requiresContext: e.requiresContext} : {})};
  });
}
function mediaVisible(m: UnifiedPanelEntry['media']) { return m === 'shared' || MEDIA_SLICES[m].state === 'active'; }

const CAP_TEXT: Record<CapabilityStatus, string> = {
  connected: '已接通', partial: '部分可用', 'local-only': '仅本机草稿', 'not-implemented': '尚未实现', undetermined: '状态未确定',
};
export const capabilityLabel = (c: CapabilityStatus) => CAP_TEXT[c];
/** Capability states in contract shape; context-dependent panels are unavailable (with a next step) without a project. */
export function capabilityStates(env: {hasProject: boolean}, entries = UNIFIED_PANELS): CapabilityState[] {
  return entries.filter(e => mediaVisible(e.media)).map(e => {
    if (e.requiresContext?.includes('project') && !env.hasProject) return {id: e.id, available: false, reason: `还没有选中作品。下一步：在「作品结构」里选一部作品后再打开「${e.title}」。`};
    if (e.capability === 'not-implemented') return {id: e.id, available: false, reason: `${e.title}${CAP_TEXT[e.capability]}。`};
    return {id: e.id, available: true, reason: `${CAP_TEXT[e.capability]}：${e.capabilityNote}`};
  });
}

export interface RegistryProblem { kind: 'duplicate-panel' | 'bad-dock' | 'shortcut-conflict' | 'reserved-shortcut' | 'unknown-show-action' | 'preset-panel'; detail: string; }
export function validateRegistry(entries = UNIFIED_PANELS, shortcuts = UNIFIED_SHORTCUTS, presets = LAYOUT_PRESETS): RegistryProblem[] {
  const out: RegistryProblem[] = []; const seen = new Set<string>();
  for (const e of entries) {
    if (seen.has(e.id)) out.push({kind: 'duplicate-panel', detail: e.id}); seen.add(e.id);
    if (!e.docks.includes(e.defaultDock)) out.push({kind: 'bad-dock', detail: e.id});
    if (e.showActionId && !shortcuts[e.showActionId]) out.push({kind: 'unknown-show-action', detail: e.id});
  }
  const byKey = new Map<string, string>(); const reserved = new Set(Object.keys(RESERVED_SHORTCUTS).map(normalizeShortcut));
  for (const [id, sc] of Object.entries(shortcuts)) {
    const k = normalizeShortcut(sc);
    if (reserved.has(k)) out.push({kind: 'reserved-shortcut', detail: `${id}:${k}`});
    const prev = byKey.get(k); if (prev) out.push({kind: 'shortcut-conflict', detail: `${prev}|${id}:${k}`}); else byKey.set(k, id);
  }
  for (const p of Object.values(presets)) for (const id of [p.mainFront, p.mainSecond].filter(Boolean) as string[])
    if (!seen.has(id)) out.push({kind: 'preset-panel', detail: `${p.id}:${id}`});
  return out;
}
