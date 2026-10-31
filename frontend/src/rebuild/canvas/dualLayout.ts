// [HERMIA-FE-20261031 DUALCANVAS-COMFY] 双画布布局状态（纯函数 + 按身份存储）。
// - ratio = 「上画布·主线」所占高度比例（不是屏幕上方那块），所以互换位置时两块画布各自带着自己的大小走。
// - swapped 只改显示位置：主线仍是主线，丰富仍是丰富，数据和语义不变。
// - max: 'none' | 'upper' | 'lower'，指语义上的哪块画布被最大化。
// - 有身份 → localStorage（按 user/project/instance）；没有身份 → 只在内存，「仅本次会话」。
import type {WorkspaceIdentity} from '../../workspace/contracts';

export type DualLayout = {ratio: number; swapped: boolean; max: 'none' | 'upper' | 'lower'};
export const DEFAULT_LAYOUT: DualLayout = {ratio: 0.6, swapped: false, max: 'none'};
export const RATIO_MIN = 0.2, RATIO_MAX = 0.8, STEP = 0.05, BIG_STEP = 0.15;
export const LAYOUT_KEY_PREFIX = 'poemseed.dualcv.layout.v1';

export const clampRatio = (r: number) => (Number.isFinite(r) ? Math.round(Math.min(RATIO_MAX, Math.max(RATIO_MIN, r)) * 1000) / 1000 : DEFAULT_LAYOUT.ratio);
/** Share of the pane that is displayed on top (what the separator's aria-valuenow reports). */
export const topShare = (l: DualLayout) => (l.swapped ? 1 - l.ratio : l.ratio);
/** Set the on-screen top share (pointer drag / keyboard), converting back to the main-canvas ratio. */
export const withTopShare = (l: DualLayout, share: number): DualLayout => {
  const s = Math.min(RATIO_MAX, Math.max(RATIO_MIN, share));
  return {...l, ratio: clampRatio(l.swapped ? 1 - s : s), max: 'none'};
};
/** WAI-ARIA window splitter keys. Returns null for keys it does not handle. */
export function splitterKey(l: DualLayout, key: string): DualLayout | null {
  const t = topShare(l);
  switch (key) {
    case 'ArrowDown': return withTopShare(l, t + STEP);
    case 'ArrowUp': return withTopShare(l, t - STEP);
    case 'PageDown': return withTopShare(l, t + BIG_STEP);
    case 'PageUp': return withTopShare(l, t - BIG_STEP);
    case 'Home': return withTopShare(l, RATIO_MIN);
    case 'End': return withTopShare(l, RATIO_MAX);
    case 'Enter': return {...l, ratio: DEFAULT_LAYOUT.ratio, max: 'none'};
    default: return null;
  }
}
export const toggleMax = (l: DualLayout, which: 'upper' | 'lower'): DualLayout => ({...l, max: l.max === which ? 'none' : which});
export const toggleSwap = (l: DualLayout): DualLayout => ({...l, swapped: !l.swapped});

export function sanitizeLayout(raw: unknown): DualLayout {
  const r = (raw && typeof raw === 'object' ? raw : {}) as Partial<DualLayout>;
  return {ratio: clampRatio(typeof r.ratio === 'number' ? r.ratio : DEFAULT_LAYOUT.ratio), swapped: r.swapped === true,
    max: r.max === 'upper' || r.max === 'lower' ? r.max : 'none'};
}

const SESSION = new Map<string, DualLayout>();
export const sessionLayoutStore = {clear: () => SESSION.clear(), get: (k: string) => SESSION.get(k)};
export function layoutStore(kind: string, id: WorkspaceIdentity): {key: string; persist: 'local' | 'session'} {
  if (id.kind === 'real') return {key: `${LAYOUT_KEY_PREFIX}::${kind}::${id.scope.userId}::${id.scope.projectId}::${id.scope.projectInstanceId}`, persist: 'local'};
  return {key: `${LAYOUT_KEY_PREFIX}::${kind}::${id.key}`, persist: 'session'};
}
export function readLayout(s: {key: string; persist: 'local' | 'session'}): DualLayout {
  if (s.persist === 'session') return SESSION.get(s.key) ?? DEFAULT_LAYOUT;
  try { const raw = localStorage.getItem(s.key); return raw ? sanitizeLayout(JSON.parse(raw)) : DEFAULT_LAYOUT; } catch { return DEFAULT_LAYOUT; }
}
export function writeLayout(s: {key: string; persist: 'local' | 'session'}, l: DualLayout) {
  if (s.persist === 'session') { SESSION.set(s.key, l); return; }
  try { localStorage.setItem(s.key, JSON.stringify(l)); } catch { /* quota: ignore */ }
}
