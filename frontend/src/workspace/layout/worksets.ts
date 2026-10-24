/**
 * [HERMIA-FE-20261024 VW-M2] Named view worksets — pure model.
 * A workset is UI geometry only: the existing v3 layout serialization (dock/order/size/collapsed/open/z/floatRect,
 * split, focus, unknown panels preserved verbatim by the original codec). No content, drafts, graph or task data.
 * Apply goes through parseLayoutV3 (original normalisation/clamping) — never a parallel layout owner.
 */
import {parseLayoutV3, serializeLayout} from './persistence';
import type {LayoutPanelSpec, LayoutState, Viewport} from './model';
import {WORKSET_LAYOUT_MAX_BYTES, WORKSET_LIMIT, WORKSET_NAME_MAX, type StoredWorkset} from '../state/viewPreferences';

export {WORKSET_LIMIT, WORKSET_NAME_MAX};
export type WorksetResult<T> = {ok: true; value: T} | {ok: false; reason: string};

export function validateWorksetName(name: string, list: readonly StoredWorkset[], exceptId?: string): WorksetResult<string> {
  const n = name.replace(/\s+/g, ' ').trim();
  if (!n) return {ok: false, reason: '请输入视图名称。'};
  if (n.length > WORKSET_NAME_MAX) return {ok: false, reason: `视图名称最多 ${WORKSET_NAME_MAX} 个字。`};
  if (list.some(w => w.id !== exceptId && w.name.toLocaleLowerCase() === n.toLocaleLowerCase())) return {ok: false, reason: `已经有名为「${n}」的视图，请换一个名称。`};
  return {ok: true, value: n};
}

let seq = 0;
export function newWorksetId(now: number) { seq = (seq + 1) % 1e6; return `ws-${now.toString(36)}-${seq.toString(36)}`; }

/** Strip focus (a transient selection, not geometry) so applying never "jumps" focus on its own. */
function geometryOnly(state: LayoutState): LayoutState { return {...state, focusId: null}; }

export function captureWorkset(state: LayoutState, name: string, list: readonly StoredWorkset[], now = Date.now()): WorksetResult<StoredWorkset[]> {
  if (list.length >= WORKSET_LIMIT) return {ok: false, reason: `最多保存 ${WORKSET_LIMIT} 个视图，请先删除不用的视图。`};
  const v = validateWorksetName(name, list); if (!v.ok) return v;
  const layout = serializeLayout(geometryOnly(state));
  if (layout.length > WORKSET_LAYOUT_MAX_BYTES) return {ok: false, reason: '当前布局数据过大，无法保存为视图。'};
  return {ok: true, value: [...list, {id: newWorksetId(now), name: v.value, createdAt: now, layout}]};
}
export function renameWorkset(list: readonly StoredWorkset[], id: string, name: string): WorksetResult<StoredWorkset[]> {
  if (!list.some(w => w.id === id)) return {ok: false, reason: '这个视图已经不存在。'};
  const v = validateWorksetName(name, list, id); if (!v.ok) return v;
  return {ok: true, value: list.map(w => (w.id === id ? {...w, name: v.value} : w))};
}
export function deleteWorkset(list: readonly StoredWorkset[], id: string): WorksetResult<StoredWorkset[]> {
  if (!list.some(w => w.id === id)) return {ok: false, reason: '这个视图已经不存在。'};
  return {ok: true, value: list.filter(w => w.id !== id)};
}
/** Resolve a stored workset to a normalised layout state using the ORIGINAL v3 codec. */
export function resolveWorkset(w: StoredWorkset, specs: readonly LayoutPanelSpec[], vp: Viewport, current: LayoutState): WorksetResult<LayoutState> {
  let raw: unknown;
  try { raw = JSON.parse(w.layout); } catch { return {ok: false, reason: `视图「${w.name}」的数据无法读取，当前布局没有改变。`}; }
  try {
    const {state} = parseLayoutV3(raw, specs, vp);
    // Unknown panels in the current session stay preserved (merge, workset wins on conflicts).
    return {ok: true, value: {...state, focusId: current.focusId && state.frames[current.focusId]?.open ? current.focusId : null,
      preserved: {...current.preserved, ...state.preserved}, zTop: Math.max(state.zTop, current.zTop)}};
  } catch { return {ok: false, reason: `视图「${w.name}」的格式不受支持，当前布局没有改变。`}; }
}
/** Panels that are open now and would be closed by `target`. */
export function panelsClosedBy(current: LayoutState, target: LayoutState): string[] {
  return Object.values(current.frames).filter(f => f.open && target.frames[f.id] && !target.frames[f.id].open).map(f => f.id);
}
